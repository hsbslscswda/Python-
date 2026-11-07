"""Image-space association and within-model geometry; no MediaPipe/Qt imports."""

import itertools
import math

from .domain import Arm, Features, Shape
from .geometry import OneEuro, angle3, distance


def classify(points, previous=Shape.UNKNOWN, world=None):
    if len(points) != 21:
        return Shape.UNKNOWN
    coords = (
        tuple(tuple(p) for p in world) if world and len(world) == 21 else tuple((*p, 0.0) for p in points)
    )
    width = math.dist(coords[5], coords[17])
    if width < 1e-6 or (world is None and width < 3.0):
        return Shape.UNKNOWN
    extended = folded = 0
    for base, joint, tip in ((5, 6, 8), (9, 10, 12), (13, 14, 16), (17, 18, 20)):
        angle = angle3(coords[base], coords[joint], coords[tip]) or 0.0
        ratio = math.dist(coords[tip], coords[0]) / max(1e-6, math.dist(coords[base], coords[0]))
        extended += angle > 145.0 and ratio > (1.30 if previous == Shape.OPEN else 1.40)
        folded += angle < 145.0 or ratio < (1.55 if previous == Shape.FIST else 1.40)
    if folded >= 3 or (folded >= 2 and extended == 0):
        return Shape.FIST
    pinch = math.dist(coords[4], coords[8]) / width
    if pinch < (0.4 if previous == Shape.PINCH else 0.25):
        return Shape.PINCH
    if extended >= 3 or (extended >= 2 and folded == 0):
        return Shape.OPEN
    return Shape.OTHER


class FeatureExtractor:
    def __init__(self):
        self.scale_filter = OneEuro(1.8, 0.005)
        self.previous = {}
        self.last_seen = {}
        self.palm_sizes = {}
        self.bones = {}
        self.last_t = None
        self.last_scale = self.last_chest = self.reference_scale = self.reference_torso = None
        self.last_body = None

    def extract(self, hands, pose, width, height, timestamp, frame_id):
        if self.last_t is not None and (timestamp - self.last_t > 0.5 or timestamp < self.last_t):
            self.previous.clear()
            self.last_seen.clear()
            self.palm_sizes.clear()
            self.bones.clear()
        self.last_t = timestamp
        points = pose.pose_landmarks[0] if pose.pose_landmarks else ()
        world = pose.pose_world_landmarks[0] if pose.pose_world_landmarks else ()

        def finite(i):
            return bool(points) and all(math.isfinite(getattr(points[i], axis)) for axis in ("x", "y", "z"))

        def confidence(i):
            return min(points[i].visibility, points[i].presence) if finite(i) else 0.0

        def reliable(i, threshold=0.25):
            return confidence(i) >= threshold

        def xy(i):
            return (points[i].x * width, points[i].y * height) if finite(i) else (0.0, 0.0)

        shoulder_width = distance(xy(11), xy(12)) if finite(11) and finite(12) else 0.0
        body = shoulder_width > width * 0.03 and max(confidence(11), confidence(12)) >= 0.45
        if body:
            mid = tuple((a + b) / 2 for a, b in zip(xy(11), xy(12)))
            direction = (0.0, 1.0)
            torso = None
            if reliable(23, 0.35) and reliable(24, 0.35):
                hips = tuple((a + b) / 2 for a, b in zip(xy(23), xy(24)))
                torso = distance(hips, mid)
                if torso > 1.0:
                    direction = ((hips[0] - mid[0]) / torso, (hips[1] - mid[1]) / torso)
            reference = self.reference_scale or shoulder_width
            if torso and self.reference_torso:
                reference *= max(0.6, min(1.7, torso / self.reference_torso))
            effective = max(shoulder_width, reference * 0.72)
            scale = max(1.0, self.scale_filter(effective, timestamp))
            chest = (mid[0] + direction[0] * 0.25 * scale, mid[1] + direction[1] * 0.25 * scale)
            if shoulder_width >= reference * 0.75:
                self.reference_scale = (
                    shoulder_width
                    if self.reference_scale is None
                    else 0.96 * self.reference_scale + 0.04 * shoulder_width
                )
                if torso:
                    self.reference_torso = (
                        torso if self.reference_torso is None else 0.96 * self.reference_torso + 0.04 * torso
                    )
            self.last_scale, self.last_chest, self.last_body = scale, chest, timestamp
        else:
            scale = self.last_scale or width * 0.25
            chest = self.last_chest or (width / 2, height / 2)
        valid = body or (self.last_body is not None and timestamp - self.last_body < 0.35)
        reason = "" if valid else "请让肩部与上半身进入画面"

        raw = [tuple((p.x * width, p.y * height) for p in hand) for hand in hands.hand_landmarks]
        hand_world = getattr(hands, "hand_world_landmarks", ())
        candidates = []
        for index, hand in enumerate(raw):
            if len(hand) != 21 or not all(math.isfinite(v) for p in hand for v in p):
                continue
            if not all(
                -0.15 * width <= p[0] <= 1.15 * width and -0.15 * height <= p[1] <= 1.15 * height
                for p in hand
            ):
                continue
            if distance(hand[5], hand[17]) < 3.0:
                continue
            candidates.append(index)

        def label(index):
            category = hands.handedness[index][0]
            return category.category_name.lower(), getattr(category, "score", 0.7)

        def cost(side, index):
            if index is None:
                return 0.95
            wrist = 15 if side == "left" else 16
            hand = raw[index]
            q = confidence(wrist)
            prior = self.previous.get(side)
            age = timestamp - self.last_seen.get(side, -99.0)
            if q >= 0.35:
                geometric = distance(hand[0], xy(wrist)) / scale * (0.55 + 0.45 * q)
            elif prior and age < 0.35:
                geometric = distance(hand[0], prior[0]) / scale + 0.15
            else:
                return 1.30  # No localization evidence must cost MORE than leaving it unmatched.
            continuity = 0.0
            if prior and age < 0.45:
                delta = distance(hand[0], prior[0]) / scale
                if delta > 1.8 and age < 0.2:
                    return 9.0
                continuity = min(1.4, delta) * 0.55
            category, score = label(index)
            return geometric + continuity + (0.30 * score if category != side else 0.0)

        choices = [None] + candidates
        mappings = [
            (a, b) for a, b in itertools.product(choices, repeat=2) if a is None or b is None or a != b
        ]
        ranked = sorted(
            ((cost("left", a) + cost("right", b), a, b) for a, b in mappings), key=lambda row: row[0]
        )
        _, left_id, right_id = ranked[0]
        ambiguous = len(ranked) > 1 and ranked[1][0] - ranked[0][0] < 0.035
        duplicate = len(candidates) == 2 and distance(raw[candidates[0]][0], raw[candidates[1]][0]) < max(
            2.0, scale * 0.015
        )
        if duplicate:
            left_id = right_id = None
        elif ambiguous:
            plausible = [row[1:] for row in ranked if row[0] <= ranked[0][0] + 0.035]
            kept = [None, None]
            for side_id, side in enumerate(("left", "right")):
                alternatives = {pair[side_id] for pair in plausible}
                if len(alternatives) == 1:
                    kept[side_id] = next(iter(alternatives))
            # Preserve individually identifiable hands, including the one-hand case.
            # Never reuse an index or rescue a truly coincident identity by arbitrary side.
            for index in candidates:
                if index in kept:
                    continue
                distances = [
                    distance(raw[index][0], self.previous[side][0]) / scale
                    if side in self.previous and timestamp - self.last_seen.get(side, -99.0) < 0.35
                    else 99.0
                    for side in ("left", "right")
                ]
                winner = 0 if distances[0] < distances[1] else 1
                if (
                    distances[winner] < 0.40
                    and distances[1 - winner] - distances[winner] > 0.10
                    and kept[winner] is None
                ):
                    kept[winner] = index
            left_id, right_id = kept

        result = []
        for side, ids, index in (("left", (11, 13, 15), left_id), ("right", (12, 14, 16), right_id)):
            shoulder, elbow, wrist = ids
            hand = raw[index] if index is not None and cost(side, index) < 1.15 else ()
            if hand:
                size = distance(hand[5], hand[17])
                prior_size = (
                    self.palm_sizes.get(side, size)
                    if timestamp - self.last_seen.get(side, -99.0) < 0.45
                    else size
                )
                if not 0.3 < size / max(1.0, prior_size) < 3.0:
                    hand = ()
                else:
                    self.palm_sizes[side] = 0.8 * prior_size + 0.2 * size
            old_shape = self.previous.get(side, ((0.0, 0.0), Shape.UNKNOWN))[1]
            local_world = None
            if hand and index < len(hand_world):
                local_world = tuple((p.x, p.y, p.z) for p in hand_world[index])
                if not all(math.isfinite(v) for p in local_world for v in p):
                    local_world = None
            shape = classify(hand, old_shape, local_world) if hand else Shape.UNKNOWN
            if hand:
                self.previous[side] = (hand[0], shape)
                self.last_seen[side] = timestamp
            shape_age = timestamp - self.last_seen.get(side, -99.0)
            if not hand and shape_age <= 0.25:
                shape = old_shape
            image_wrist = hand[0] if hand else xy(wrist)
            tracked = bool(hand) or (reliable(wrist, 0.50) and reliable(elbow, 0.40))
            other = right_id if side == "left" else left_id
            if not hand and other is not None and distance(xy(wrist), raw[other][0]) / scale < 0.12:
                own_prior = self.previous.get(side)
                if not own_prior or shape_age > 0.35 or distance(xy(wrist), own_prior[0]) / scale > 0.40:
                    tracked = False  # An unseen arm cannot be established by the other hand's wrist.
            angle = None
            q = min(confidence(i) for i in ids)
            if world and q >= 0.28:
                coordinates = [tuple(getattr(world[i], axis) for axis in ("x", "y", "z")) for i in ids]
                lengths = tuple(math.dist(coordinates[i], coordinates[i + 1]) for i in (0, 1))
                previous = self.bones.get(side, lengths)
                if all(
                    0.035 < length < 1.0 and 0.45 < length / max(0.001, before) < 2.2
                    for length, before in zip(lengths, previous)
                ):
                    angle = angle3(*coordinates)
                    self.bones[side] = tuple(0.92 * a + 0.08 * b for a, b in zip(previous, lengths))
            result.append(
                Arm(
                    side,
                    xy(shoulder),
                    xy(elbow),
                    image_wrist,
                    shape,
                    tracked,
                    bool(hand),
                    angle,
                    hand,
                    q,
                    reliable(elbow, 0.25),
                    shape_age,
                    confidence(wrist),
                    xy(wrist),
                )
            )
        yaw = None
        if world and reliable(11, 0.60) and reliable(12, 0.60):
            v = tuple(getattr(world[12], axis) - getattr(world[11], axis) for axis in ("x", "y", "z"))
            if all(math.isfinite(x) for x in v) and 0.15 < math.dist(v, (0.0, 0.0, 0.0)) < 0.8:
                yaw = max(-1.1, min(1.1, math.atan2(v[2], abs(v[0]))))
        return Features(timestamp, frame_id, width, height, chest, scale, tuple(result), valid, reason, yaw)
