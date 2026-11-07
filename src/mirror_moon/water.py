"""Persistent water, damped spring following and bounded 3D ballistic visual simulation.

Monocular metric scale, palm offset and other-person collision are estimates, not measured depth.
"""

import math
from dataclasses import dataclass

from .config import DEFAULTS
from .domain import EffectObject, Shape, SpellView
from .geometry import Hold, distance, segment_distance


def fresh(a):
    return a.hand_valid and a.shape_age <= DEFAULTS.gesture_max_age


class Clap:
    def __init__(self, cfg=DEFAULTS):
        self.cfg, self.previous, self.approach_until = cfg, None, -1e9
        self.opposing_intent = False

    def update(self, f):
        a, b = f.arms
        if not all(fresh(x) for x in (a, b)):
            self.previous = None
            # Contact can hide fingers; only current reliable Pose wrists may
            # complete a previously observed, opposed closing trajectory.
            observed_wrists = all(x.wrist_confidence >= 0.60 and (x.tracked or x.upper_valid) for x in (a, b))
            d = distance(a.pose_wrist or a.wrist, b.pose_wrist or b.wrist) / max(1.0, f.scale)
            if (
                f.valid
                and observed_wrists
                and self.opposing_intent
                and f.timestamp <= self.approach_until
                and d < self.cfg.clap_distance
            ):
                self.approach_until = -1e9
                return True
            return False
        d = distance(a.palm or a.wrist, b.palm or b.wrist) / max(1.0, f.scale)
        opposing = (
            a.normal is None or b.normal is None or sum(x * y for x, y in zip(a.normal, b.normal)) < -0.15
        )
        open_hands = all(x.shape in (Shape.OPEN, Shape.OTHER, Shape.PINCH) for x in (a, b))
        if self.previous:
            stamp, before = self.previous
            dt = f.timestamp - stamp
            if 0 < dt < 0.35 and (before - d) / dt > self.cfg.clap_speed and before > 0.35:
                self.approach_until = f.timestamp + 0.25
                self.opposing_intent = opposing and open_hands
            elif d > before + 0.03:
                self.approach_until = -1e9
        self.previous = f.timestamp, d
        hit = (
            open_hands
            and opposing
            and self.opposing_intent
            and d < self.cfg.clap_distance
            and f.timestamp <= self.approach_until
        )
        if hit:
            self.approach_until = -1e9
        return hit


@dataclass
class Shot:
    position: list
    velocity: list
    radius: float
    born: float
    seed: int


class Water:
    def __init__(self, cfg=DEFAULTS):
        self.cfg, self.hold, self.clap = cfg, Hold(), Clap(cfg)
        self.enabled = False
        self.owner = None
        self.fists = set()
        self.position, self.velocity = [0.0, 0.0, 2.0], [0.0] * 3
        self.radius = 0.075
        self.shots, self.splashes = [], []
        self.last_t = None
        self.recall_at = self.grip_cooldown = -1e9
        self.grip_far, self.seed = False, 0
        self.scaling = False
        self.hand_seen = {"left": -1e9, "right": -1e9}
        self.last_projection = (0.0, 0.0)

    @staticmethod
    def camera(f):
        return f.width * 0.9

    def pause(self, timestamp):
        delta = max(0.0, timestamp - self.last_t) if self.last_t is not None else 0.0
        self.last_t = timestamp
        for shot in self.shots:
            shot.born += delta
        self.splashes = [(stamp + delta, c, r, seed) for stamp, c, r, seed in self.splashes]
        self.recall_at += delta
        self.grip_cooldown += delta
        self.hold.clear()
        self.grip_far = False
        self.clap.previous = None
        self.clap.approach_until = -1e9

    def project(self, p, f):
        z = max(0.18, p[2])
        k = self.camera(f) / z
        return (f.width / 2 + p[0] * k, f.height / 2 + p[1] * k), k

    def target(self, a, f):
        focal = self.camera(f)
        z = focal * 0.40 / max(50.0, f.scale) if f.valid else focal * 0.08 / max(15.0, a.palm_scale)
        z = max(0.4, min(6.0, z))
        palm = a.palm or a.wrist
        normal = a.normal or (0.0, -0.65, -0.76)
        offset = self.radius + self.cfg.water_palm_offset
        return [
            (palm[0] - f.width / 2) * z / focal + normal[0] * offset,
            (palm[1] - f.height / 2) * z / focal + normal[1] * offset,
            max(0.30, z + normal[2] * offset),
        ]

    def update(self, f):
        t, events = f.timestamp, []
        dt = min(0.20, max(0.0, t - self.last_t)) if self.last_t is not None else 0.0
        if self.last_t is not None and t - self.last_t > 0.5:
            self.hold.clear()
            self.grip_far = False
            self.clap.previous = None
        self.last_t = t
        for arm in f.arms:
            if fresh(arm):
                self.hand_seen[arm.side] = t
        if self.enabled and self.clap.update(f):
            self.enabled = False
            self.shots.clear()
            self.splashes.clear()
            self.fists.clear()
            self.hold.clear()
            return SpellView(mode="water", state="OFF", hint="水球已拍散；握拳再摊开重新召唤"), [
                ("water_close", (), 0.0)
            ]
        if not self.enabled:
            for a in f.arms:
                if self.hold.ready(
                    a.side + "fist", fresh(a) and a.shape == Shape.FIST, t, self.cfg.gesture_hold
                ):
                    self.fists.add(a.side)
                if self.hold.ready(
                    a.side + "open",
                    a.side in self.fists and fresh(a) and a.shape in (Shape.OPEN, Shape.OTHER, Shape.PINCH),
                    t,
                    self.cfg.gesture_hold,
                ):
                    self.enabled, self.owner = True, a.side
                    self.radius = 0.075
                    self.position, self.velocity = self.target(a, f), [0.0] * 3
                    self.radius, self.grip_far = 0.075, False
                    self.recall_at = -1e9
                    events.append(("water_open", (a.palm or a.wrist,), 1.0))
                    break
        if not self.enabled:
            return SpellView(
                mode="water", state="OFF", hint="任意一手握拳后摊开，召唤水球；坐着也可以"
            ), events
        a, b = f.arm(self.owner), f.arm("right" if self.owner == "left" else "left")
        target = self.target(a, f) if fresh(a) else list(self.position)
        held = t >= self.recall_at
        center, scale = self.project(self.position, f)
        self.scaling = False

        def available(arm):
            return fresh(arm) or (arm.upper_valid and f.valid and t - self.hand_seen[arm.side] < 0.8)

        if held and available(a) and available(b):
            pa, pb = a.palm or a.wrist, b.palm or b.wrist
            spacing = distance(pa, pb)
            midpoint = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
            # Capture the ball between palms, then let separation control its radius.
            if spacing > self.radius * scale * 0.7 and distance(midpoint, center) < max(
                self.radius * scale * 1.8, f.scale * 0.45
            ):
                tb = self.target(b, f)
                target = [(x + y) / 2 for x, y in zip(target, tb)]
                desired = max(0.05, min(0.60, spacing / scale * 0.48))
                self.radius += (desired - self.radius) * (1 - math.exp(-dt * 6))
                self.scaling = True
            d = (
                segment_distance(b.wrist, a.elbow, a.wrist)[0]
                if a.upper_valid or a.tracked
                else distance(pa, pb)
            )
            d = min(d, distance(pa, pb)) / max(1.0, f.scale)
            if d > 0.55:
                self.grip_far = True
            parallel = (
                a.normal is None or b.normal is None or sum(x * y for x, y in zip(a.normal, b.normal)) > -0.15
            )
            grip = self.grip_far and d < 0.28 and parallel and t > self.grip_cooldown
            if self.hold.ready("launch", grip, t, self.cfg.water_grip_hold):
                normal = a.normal or (0.0, 0.0, -1.0)
                n = math.sqrt(sum(x * x for x in normal)) or 1.0
                velocity = [
                    x / n * self.cfg.water_launch_speed + v * 0.35 for x, v in zip(normal, self.velocity)
                ]
                self.seed += 1
                self.shots.append(Shot(list(self.position), velocity, self.radius, t, self.seed))
                self.shots = self.shots[-8:]
                self.recall_at, self.grip_cooldown, self.grip_far = t + 0.85, t + 1.2, False
                self.hold.ready("launch", False, t, self.cfg.water_grip_hold)
                events.append(("water_launch", (center,), 1.0))
                held = False
        else:
            self.hold.ready("launch", False, t, self.cfg.water_grip_hold)
            if not available(a) or not available(b):
                self.grip_far = False
        previous_positions = {id(shot): list(shot.position) for shot in self.shots}
        steps = max(1, math.ceil(dt / (1 / 90)))
        step = dt / steps
        for _ in range(steps):
            if held:
                for i in range(3):
                    acc = (target[i] - self.position[i]) * self.cfg.water_spring - self.velocity[
                        i
                    ] * self.cfg.water_damping
                    self.velocity[i] += acc * step
                    self.position[i] += self.velocity[i] * step
            for shot in self.shots:
                shot.velocity[1] += self.cfg.water_gravity * step
                for i in range(3):
                    shot.position[i] += shot.velocity[i] * step
        objects = []
        if held:
            center, scale = self.project(self.position, f)
            objects.append(
                EffectObject(
                    1,
                    center,
                    self.radius * scale,
                    t,
                    velocity=(self.velocity[0] * scale, self.velocity[1] * scale),
                    depth=self.position[2],
                )
            )
        alive = []
        for shot in self.shots:
            center, scale = self.project(shot.position, f)
            hit = shot.position[2] < 0.25
            before = previous_positions[id(shot)]
            hit_position = list(shot.position)
            if hit:
                alpha = max(0.0, min(1.0, (before[2] - 0.25) / max(1e-6, before[2] - shot.position[2])))
                hit_position = [x + (y - x) * alpha for x, y in zip(before, shot.position)]
            for left, top, right, bottom, shoulder in f.people:
                target_z = self.camera(f) * 0.4 / max(30.0, shoulder)
                low, high = sorted((before[2], shot.position[2]))
                if low - shot.radius - 0.30 <= target_z <= high + shot.radius + 0.30:
                    dz = shot.position[2] - before[2]
                    alpha = max(0.0, min(1.0, (target_z - before[2]) / dz)) if abs(dz) > 1e-6 else 1.0
                    contact = [x + (y - x) * alpha for x, y in zip(before, shot.position)]
                    pixel, k = self.project(contact, f)
                    pad = shot.radius * k
                    if left - pad <= pixel[0] <= right + pad and top - pad <= pixel[1] <= bottom + pad:
                        hit = True
                        hit_position = contact
                        break
            if hit or t - shot.born > 4.0:
                center, scale = self.project(hit_position, f)
                impact_center = (max(0.0, min(f.width, center[0])), max(0.0, min(f.height, center[1])))
                radius = min(f.height * 0.7, max(45.0, shot.radius * scale * 1.5))
                self.splashes.append((t, impact_center, radius, shot.seed))
                events.append(("water_hit", (impact_center,), 1.0))
            else:
                alive.append(shot)
                objects.append(
                    EffectObject(
                        2,
                        center,
                        shot.radius * scale,
                        t - shot.born,
                        velocity=(shot.velocity[0] * scale, shot.velocity[1] * scale),
                        depth=shot.position[2],
                        seed=shot.seed,
                    )
                )
        self.shots = alive
        self.splashes = [s for s in self.splashes if t - s[0] < 1.1][-8:]
        for stamp, center, radius, seed in self.splashes:
            objects.append(EffectObject(3, center, radius, t - stamp, seed=seed))
        return SpellView(
            mode="water",
            state="SCALING" if self.scaling else "HELD" if held else "FLYING",
            visibility=1.0,
            intensity=1.0,
            center=self.project(self.position, f)[0],
            radius=self.radius * self.project(self.position, f)[1],
            caster=self.owner,
            objects=tuple(objects[-12:]),
            hint="双掌夹住水球拉开可放大；另一手搭腕/前臂发射；拍掌结束",
            quality="水球持续保留；暂时丢手会停在原处，不会自动消失",
        ), events
