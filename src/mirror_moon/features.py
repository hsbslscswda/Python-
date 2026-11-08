"""Image-space association and within-model geometry; no MediaPipe/Qt imports."""

import itertools
import math
from dataclasses import replace

from .domain import Arm, Features, Shape
from .geometry import OneEuro, angle3, distance, smoothstep


def palm_geometry(hand, world, side):
    if len(hand) != 21:
        return {}
    palm = tuple(sum(hand[i][axis] for i in (0, 5, 9, 13, 17)) / 5 for axis in (0, 1))
    width = max(distance(hand[5], hand[17]), distance(hand[0], hand[9]) * 0.8)
    coords = world if world and len(world) == 21 else tuple((*p, 0.0) for p in hand)
    u = tuple(coords[5][i] - coords[0][i] for i in range(3))
    v = tuple(coords[17][i] - coords[0][i] for i in range(3))
    n = (u[1] * v[2] - u[2] * v[1], u[2] * v[0] - u[0] * v[2], u[0] * v[1] - u[1] * v[0])
    length = math.sqrt(sum(x * x for x in n))
    sign = -1 if side == "left" else 1
    normal = tuple(sign * x / length for x in n) if length > 1e-9 else None
    extension = []
    for base, tip in ((5, 8), (9, 12), (13, 16), (17, 20)):
        ratio = math.dist(coords[tip], coords[0]) / max(1e-6, math.dist(coords[base], coords[0]))
        extension.append(max(0.0, min(1.0, (ratio - 0.85) / 0.8)))
    return dict(palm=palm, palm_scale=width, normal=normal, openness=sum(extension) / 4)


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
        self.scale_filter = OneEuro(1.2, 0.003)
        self.yaw_filter = OneEuro(0.45, 0.001)
        self.previous = {}
        self.last_seen = {}
        self.palm_sizes = {}
        self.bones = {}
        self.last_t = None
        self.last_scale = self.last_chest = self.reference_scale = self.reference_torso = None
        self.last_body = None
        self.last_yaw = 0.0
        self.pose_anchor = None
        self.arm_offsets = {}

    def extract(self, hands, pose, width, height, timestamp, frame_id):
        if self.last_t is not None and (timestamp - self.last_t > 0.5 or timestamp < self.last_t):
            self.previous.clear()
            self.last_seen.clear()
            self.palm_sizes.clear()
            self.bones.clear()
        self.last_t = timestamp
        sets = pose.pose_landmarks
        worlds = pose.pose_world_landmarks
        owner = 0
        if sets:

            def person_cost(ps):
                anchor = ((ps[11].x + ps[12].x) * width / 2, (ps[11].y + ps[12].y) * height / 2)
                return distance(anchor, self.pose_anchor or (width / 2, height / 2))

            owner = min(range(len(sets)), key=lambda i: person_cost(sets[i]))
            self.pose_anchor = (
                (sets[owner][11].x + sets[owner][12].x) * width / 2,
                (sets[owner][11].y + sets[owner][12].y) * height / 2,
            )
        points = sets[owner] if sets else ()
        world = worlds[owner] if len(worlds) > owner else ()
        people = []
        for i, ps in enumerate(sets):
            if i == owner:
                continue
            visible = [p for p in ps if min(p.visibility, p.presence) > 0.4]
            if len(visible) >= 6:
                left_x = min(p.x for p in visible) * width
                top_y = min(p.y for p in visible) * height
                right_x = max(p.x for p in visible) * width
                bot_y = max(p.y for p in visible) * height
                sh_span = abs(ps[11].x - ps[12].x) * width
                est_shoulder = max(sh_span, (bot_y - top_y) * 0.22)
                people.append((left_x, top_y, right_x, bot_y, est_shoulder))

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
            elif not valid:
                category, _ = label(index)
                geometric = 0.25 if category == side else 0.80
            else:
                return 1.30
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
            upper_valid = reliable(shoulder, 0.40) and reliable(elbow, 0.45)
            if upper_valid and (hand or reliable(wrist, 0.50)):
                new_offset = (image_wrist[0] - xy(elbow)[0], image_wrist[1] - xy(elbow)[1])
                if side in self.arm_offsets:
                    old_off = self.arm_offsets[side]
                    self.arm_offsets[side] = (
                        0.7 * old_off[0] + 0.3 * new_offset[0],
                        0.7 * old_off[1] + 0.3 * new_offset[1],
                    )
                else:
                    self.arm_offsets[side] = new_offset
            elif upper_valid and side in self.arm_offsets:
                offset = self.arm_offsets[side]
                image_wrist = (xy(elbow)[0] + offset[0], xy(elbow)[1] + offset[1])
            tracked = bool(hand) or (reliable(wrist, 0.50) and reliable(elbow, 0.40))
            other = right_id if side == "left" else left_id
            if not hand and other is not None and distance(xy(wrist), raw[other][0]) / scale < 0.12:
                own_prior = self.previous.get(side)
                if not own_prior or shape_age > 0.35 or distance(xy(wrist), own_prior[0]) / scale > 0.40:
                    tracked = False
            angle = None
            q = min(confidence(i) for i in ids)
            if world and q >= 0.24:
                coordinates = [tuple(getattr(world[i], axis) for axis in ("x", "y", "z")) for i in ids]
                lengths = tuple(math.dist(coordinates[i], coordinates[i + 1]) for i in (0, 1))
                previous = self.bones.get(side, lengths)
                if all(
                    0.025 < length < 1.15 and 0.38 < length / max(0.001, before) < 2.6
                    for length, before in zip(lengths, previous)
                ):
                    angle = angle3(*coordinates)
                    self.bones[side] = tuple(0.92 * a + 0.08 * b for a, b in zip(previous, lengths))
            result.append(
                replace(
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
                    ),
                    **palm_geometry(hand, local_world, side),
                    upper_valid=upper_valid,
                )
            )
        yaw = None
        if world and reliable(11, 0.55) and reliable(12, 0.55):
            v = tuple(getattr(world[12], axis) - getattr(world[11], axis) for axis in ("x", "y", "z"))
            if all(math.isfinite(x) for x in v) and 0.12 < math.dist(v, (0.0, 0.0, 0.0)) < 0.85:
                raw_yaw = max(-0.52, min(0.52, math.atan2(v[2], max(0.10, abs(v[0])))))
                # Suppress monocular raised-arm Z distortion when 2D shoulders are wide-open facing camera
                if self.reference_scale and shoulder_width > 0:
                    foreshorten = 1.0 - min(1.0, shoulder_width / max(1.0, self.reference_scale))
                    gate = 0.28 + 0.72 * smoothstep(foreshorten / 0.22)
                    raw_yaw *= gate
                if abs(raw_yaw) < 0.16:
                    raw_yaw = 0.0
                yaw = self.yaw_filter(raw_yaw, timestamp)
                if abs(yaw) < 0.035:
                    yaw = 0.0
                self.last_yaw = yaw
        elif valid and self.last_yaw:
            self.last_yaw *= 0.90
            yaw = self.last_yaw if abs(self.last_yaw) >= 0.035 else 0.0
        if not valid and any(a.hand_valid for a in result):
            reason = "仅手部识别：水球/火焰可用"
            if self.last_body is None:
                scale = max(
                    50.0,
                    sum(a.palm_scale for a in result if a.hand_valid) / sum(a.hand_valid for a in result) * 4,
                )
        return Features(
            timestamp, frame_id, width, height, chest, scale, tuple(result), valid, reason, yaw, tuple(people)
        )
