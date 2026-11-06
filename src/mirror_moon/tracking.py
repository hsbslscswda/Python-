"""MediaPipe boundary: one RGB image and one timestamp for both Tasks."""

import hashlib
import itertools
import json
import math
import time

from .domain import Arm, Features, Shape
from .geometry import OneEuro, angle3, distance
from .resources import root


def classify(points, previous=Shape.UNKNOWN):
    width = distance(points[5], points[17])
    if width < 4:
        return Shape.UNKNOWN
    extended, folded = 0, 0
    for base, joint, tip in ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)):
        a, b, c = points[base], points[joint], points[tip]
        angle = angle3((*a, 0.0), (*b, 0.0), (*c, 0.0)) or 0.0
        extension = distance(c, points[0]) / max(1.0, distance(a, points[0]))
        extended += angle > 145 and extension > 1.4
        folded += angle < 125 or extension < 1.25
    pinch = distance(points[4], points[8]) / width
    if folded >= 3:
        return Shape.FIST
    if pinch < (0.40 if previous == Shape.PINCH else 0.25):
        return Shape.PINCH
    if extended >= 3:
        return Shape.OPEN
    return Shape.OTHER


class FeatureExtractor:
    def __init__(self):
        self.scale_filter = OneEuro(1.2, 0.005)
        self.previous = {}
        self.palm_sizes = {}
        self.bones = {}
        self.last_t = None
        self.last_scale = None
        self.last_chest = None
        self.reference_scale = None

    def extract(self, hands, pose, width, height, timestamp, frame_id):
        if self.last_t is not None and timestamp - self.last_t > 0.3:
            self.previous.clear()
            self.palm_sizes.clear()
            self.bones.clear()
        self.last_t = timestamp

        def xy(p):
            return (p.x * width, p.y * height)

        landmarks = pose.pose_landmarks[0] if pose.pose_landmarks else ()
        world = pose.pose_world_landmarks[0] if pose.pose_world_landmarks else ()

        def reliable(i):
            return (
                bool(landmarks)
                and min(landmarks[i].visibility, landmarks[i].presence) > 0.5
                and all(math.isfinite(getattr(landmarks[i], axis)) for axis in ("x", "y", "z"))
            )

        shoulders_ok = reliable(11) and reliable(12)
        empty = tuple(Arm(side, (0.0, 0.0), (0.0, 0.0), (0.0, 0.0)) for side in ("left", "right"))
        if not shoulders_ok:
            return Features(
                timestamp,
                frame_id,
                width,
                height,
                self.last_chest or (width / 2, height / 2),
                self.last_scale or width * 0.25,
                empty,
                False,
                "请让双肩、双肘和手进入画面",
            )
        shoulder_width = distance(xy(landmarks[11]), xy(landmarks[12]))
        if shoulder_width < max(width * 0.07, (self.reference_scale or shoulder_width) * 0.45):
            return Features(
                timestamp,
                frame_id,
                width,
                height,
                self.last_chest or (width / 2, height / 2),
                self.last_scale or width * 0.25,
                empty,
                False,
                "请面向摄像头，避免身体过度侧转",
            )
        scale = max(1.0, self.scale_filter(shoulder_width, timestamp))
        center = tuple((a + b) / 2 for a, b in zip(xy(landmarks[11]), xy(landmarks[12])))
        direction = (0.0, 1.0)
        if reliable(23) and reliable(24):
            hips = tuple((a + b) / 2 for a, b in zip(xy(landmarks[23]), xy(landmarks[24])))
            length = max(1.0, distance(hips, center))
            direction = ((hips[0] - center[0]) / length, (hips[1] - center[1]) / length)
        chest = (center[0] + 0.25 * scale * direction[0], center[1] + 0.25 * scale * direction[1])
        self.last_scale, self.last_chest = scale, chest
        self.reference_scale = (
            shoulder_width
            if self.reference_scale is None
            else 0.99 * self.reference_scale + 0.01 * shoulder_width
        )
        hand_points = [tuple(xy(p) for p in hand) for hand in hands.hand_landmarks]

        # Small exhaustive assignment with an explicit unmatched option, no screen-left inference.
        def cost(side, hand_id):
            if hand_id is None:
                return 0.8
            wrist_id = 15 if side == "left" else 16
            if not reliable(wrist_id):
                return 10.0
            points = hand_points[hand_id]
            d = distance(points[0], xy(landmarks[wrist_id])) / scale
            prior = self.previous.get(side)
            continuity = min(0.3, distance(points[0], prior[0]) / scale) * 0.15 if prior else 0.0
            category = hands.handedness[hand_id][0].category_name.lower()
            label_penalty = 0.04 if category != side else 0.0
            return d + continuity + label_penalty

        choices = [None] + list(range(len(hand_points)))
        permutations = [
            (a, b) for a, b in itertools.product(choices, repeat=2) if a is None or b is None or a != b
        ]
        ranked = sorted(
            ((cost("left", a) + cost("right", b), a, b) for a, b in permutations), key=lambda x: x[0]
        )
        _, left_id, right_id = ranked[0]
        overlapping_wrists = (
            reliable(15) and reliable(16) and distance(xy(landmarks[15]), xy(landmarks[16])) / scale < 0.12
        )
        ambiguous = overlapping_wrists or (len(ranked) > 1 and ranked[1][0] - ranked[0][0] < 0.05)
        result = []
        for side, ids, hand_id in (("left", (11, 13, 15), left_id), ("right", (12, 14, 16), right_id)):
            s, e, w = ids
            tracked = all(reliable(i) for i in ids)
            points = (
                () if hand_id is None or ambiguous or cost(side, hand_id) > 0.65 else hand_points[hand_id]
            )
            if points:
                size = distance(points[5], points[17])
                old_size = self.palm_sizes.get(side, size)
                finite = all(math.isfinite(v) for p in points for v in p)
                in_bounds = all(
                    -0.1 * width <= p[0] <= 1.1 * width and -0.1 * height <= p[1] <= 1.1 * height
                    for p in points
                )
                if not finite or not in_bounds or size < 4 or not 0.4 < size / max(1.0, old_size) < 2.5:
                    points = ()
                else:
                    self.palm_sizes[side] = old_size * 0.8 + size * 0.2
            old_shape = self.previous.get(side, ((0.0, 0.0), Shape.UNKNOWN))[1]
            shape = classify(points, old_shape) if points else Shape.UNKNOWN
            wrist = points[0] if points else xy(landmarks[w])
            angle = None
            if tracked and world:
                coords = [tuple(getattr(world[i], axis) for axis in ("x", "y", "z")) for i in ids]
                lengths = tuple(math.dist(coords[i], coords[i + 1]) for i in range(2))
                prior = self.bones.get(side, lengths)
                stable = all(0.4 < v / max(p, 0.001) < 2.4 for v, p in zip(lengths, prior))
                if stable and all(0.05 < v < 0.7 for v in lengths):
                    angle = angle3(*coords)
                    self.bones[side] = tuple(0.9 * p + 0.1 * v for p, v in zip(prior, lengths))
            if points:
                self.previous[side] = (wrist, shape)
            result.append(
                Arm(
                    side,
                    xy(landmarks[s]),
                    xy(landmarks[e]),
                    wrist,
                    shape,
                    tracked,
                    bool(points),
                    angle,
                    points,
                )
            )
        return Features(timestamp, frame_id, width, height, chest, scale, tuple(result))


class Tracker:
    def __init__(self):
        import mediapipe as mp

        self.mp = mp
        self.extractor = FeatureExtractor()
        self.last_ms = -1
        directory = root() / "assets" / "models"
        if not (directory / "manifest.json").exists():
            raise RuntimeError("缺少模型清单。请运行 tools/prepare_models.py 准备本地模型。")
        manifest = json.loads((directory / "manifest.json").read_text("utf-8"))
        for name in ("hand_landmarker.task", "pose_landmarker_lite.task"):
            path = directory / name
            if not path.exists() or hashlib.sha256(path.read_bytes()).hexdigest() != manifest[name]["sha256"]:
                raise RuntimeError("缺少模型或校验失败。请运行 tools/prepare_models.py 后再启动。")
        base, vision = mp.tasks.BaseOptions, mp.tasks.vision
        self.hands = vision.HandLandmarker.create_from_options(
            vision.HandLandmarkerOptions(
                base_options=base(model_asset_path=str(directory / "hand_landmarker.task")),
                running_mode=vision.RunningMode.VIDEO,
                num_hands=2,
            )
        )
        try:
            self.pose = vision.PoseLandmarker.create_from_options(
                vision.PoseLandmarkerOptions(
                    base_options=base(model_asset_path=str(directory / "pose_landmarker_lite.task")),
                    running_mode=vision.RunningMode.VIDEO,
                    num_poses=1,
                )
            )
        except Exception:
            self.hands.close()
            raise

    def process(self, rgb, timestamp, frame_id):
        ms = round(timestamp * 1000)
        if ms <= self.last_ms:
            return None
        self.last_ms = ms
        image = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=rgb)
        started = time.perf_counter()
        hands = self.hands.detect_for_video(image, ms)
        hand_finished = time.perf_counter()
        pose = self.pose.detect_for_video(image, ms)
        pose_finished = time.perf_counter()
        self.timings = {
            "hand_ms": (hand_finished - started) * 1000.0,
            "pose_ms": (pose_finished - hand_finished) * 1000.0,
            "hand_timestamp_ms": ms,
            "pose_timestamp_ms": ms,
        }
        return self.extractor.extract(hands, pose, rgb.shape[1], rgb.shape[0], timestamp, frame_id)

    def close(self):
        self.hands.close()
        self.pose.close()
