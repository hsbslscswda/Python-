"""Persistent water, damped spring following and bounded 3D ballistic visual simulation.

Monocular metric scale, palm offset and other-person collision are estimates, not measured depth.
"""

import math
from dataclasses import dataclass

from .config import DEFAULTS
from .domain import EffectObject, Shape, SpellView
from .geometry import Hold, arm_lowered, both_arms_dropped_out, distance, segment_distance


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
        self.spawned_at = -1e9
        self.recall_at = self.grip_cooldown = -1e9
        self.grip_far, self.seed = True, 0
        self.scaling = False
        self.pinch_span = None
        self.pinch_base_radius = 0.075
        self.hand_seen = {"left": -1e9, "right": -1e9}
        self.last_b_wrist = None
        self.last_b_d = 99.0
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
        self.grip_far = True
        self.pinch_span = None
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

    def _launch_orb(self, a, center, scale, t):
        normal = a.normal or (0.0, 0.0, -1.0)
        n = math.sqrt(sum(x * x for x in normal)) or 1.0
        velocity = [x / n * self.cfg.water_launch_speed + v * 0.35 for x, v in zip(normal, self.velocity)]
        self.seed += 1
        # Convert the exact displayed lift back to world space: resizing must not snap at release.
        lift = max(20.0, self.radius * scale * 1.25) / max(1.0, scale)
        spawn_pos = [self.position[0], self.position[1] - lift, self.position[2]]
        self.shots.append(Shot(spawn_pos, velocity, self.radius, t, self.seed))
        self.shots = self.shots[-8:]
        self.recall_at, self.grip_cooldown, self.grip_far = t + 0.85, t + 0.95, False
        self.pinch_span = None
        self.hold.ready("launch", False, t, self.cfg.water_grip_hold)
        self.hold.ready("fist_launch", False, t, 0.16)
        return ("water_launch", (center,), 1.0)

    def update(self, f):
        t, events = f.timestamp, []
        dt = min(0.20, max(0.0, t - self.last_t)) if self.last_t is not None else 0.0
        if self.last_t is not None and t - self.last_t > 0.5:
            self.hold.clear()
            self.grip_far = True
            self.pinch_span = None
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
            self.pinch_span = None
            return SpellView(mode="water", state="OFF", hint="水球已拍散；握拳再摊开重新召唤"), [
                ("water_close", (), 0.0)
            ]
        # Auto-dissolve when BOTH arms are lowered downward out of frame (excluding wide-span casting)
        if self.enabled and self.hold.ready(
            "lowered_close", both_arms_dropped_out(f), t, self.cfg.lowered_close_hold
        ):
            center, scale = self.project(self.position, f)
            lev_center = (center[0], center[1] - max(20.0, self.radius * scale * 1.25))
            self.seed += 1
            self.splashes.append((t, lev_center, max(45.0, self.radius * scale * 1.45), self.seed))
            self.enabled = False
            self.shots.clear()
            self.fists.clear()
            self.hold.clear()
            self.pinch_span = None
            events.append(("water_close", (), 0.0))

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
                    self.radius, self.grip_far = 0.075, True
                    self.spawned_at = t
                    self.pinch_span = None
                    self.pinch_base_radius = 0.075
                    self.recall_at = -1e9
                    events.append(("water_open", (a.palm or a.wrist,), 1.0))
                    break
        if not self.enabled:
            self.splashes = [s for s in self.splashes if t - s[0] < 1.05][-8:]
            splash_objs = tuple(
                EffectObject(3, center, radius, t - stamp, seed=seed)
                for stamp, center, radius, seed in self.splashes
            )
            return SpellView(
                mode="water",
                state="OFF",
                visibility=1.0 if splash_objs else 0.0,
                objects=splash_objs,
                hint="任意一手握拳后摊开，召唤悬浮水球；坐着也可以",
            ), events
        a, b = f.arm(self.owner), f.arm("right" if self.owner == "left" else "left")
        target = self.target(a, f) if fresh(a) else list(self.position)
        held = t >= self.recall_at
        raw_center, scale = self.project(self.position, f)
        lev_offset_px = max(20.0, self.radius * scale * 1.25)
        center = (raw_center[0], raw_center[1] - lev_offset_px)
        self.scaling = False

        def available(arm):
            return fresh(arm) or (
                (arm.upper_valid and f.valid and t - self.hand_seen[arm.side] < 0.8)
                or (arm.side == b.side and t - self.hand_seen[b.side] < 0.30 and self.last_b_d < 0.40)
            )

        if fresh(b):
            self.last_b_wrist = b.palm or b.wrist
        b_pt = (
            (b.palm or b.wrist)
            if (b.hand_valid or b.upper_valid or b.tracked)
            else (self.last_b_wrist or b.wrist)
        )
        pa = a.palm or a.wrist
        d_fore = (
            segment_distance(b_pt, a.elbow, a.wrist)[0] if a.upper_valid or a.tracked else distance(pa, b_pt)
        )
        d = min(d_fore, distance(pa, b_pt)) / max(1.0, f.scale)
        if fresh(b):
            self.last_b_d = d

        # Strict two-hand scaling gate: ONLY when both hands are freshly observed with intentional
        # OPEN/PINCH shapes (never relaxed OTHER/FIST), not lowered, not tapping the wrist (d >= 0.26),
        # and symmetrically bracketing the water ball.
        second_hand_scaling_ok = (
            held
            and fresh(a)
            and fresh(b)
            and a.shape in (Shape.OPEN, Shape.PINCH)
            and b.shape in (Shape.OPEN, Shape.PINCH)
            and not (f.valid and arm_lowered(b, f))
            and distance(pa, b_pt) / max(1.0, f.scale) >= 0.22
        )
        if self.hold.ready("resize", second_hand_scaling_ok, t, 0.12):
            pb = b.palm or b.wrist
            spacing = distance(pa, pb)
            midpoint = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
            if spacing > max(self.radius * scale * 0.75, f.scale * 0.28) and distance(
                midpoint, raw_center
            ) < max(self.radius * scale * 1.30, f.scale * 0.36):
                if self.pinch_span is None:
                    self.pinch_span = max(spacing, 36.0)
                    self.pinch_base_radius = self.radius
                tb = self.target(b, f)
                target = [0.65 * x + 0.35 * y for x, y in zip(target, tb)]
                desired = max(0.05, min(0.55, self.pinch_base_radius * (spacing / self.pinch_span)))
                self.radius += (desired - self.radius) * (1 - math.exp(-dt * 6))
                self.scaling = True
            else:
                self.pinch_span = None
        else:
            self.pinch_span = None

        if held and available(a) and available(b):
            if d > 0.36:
                self.grip_far = True
            # Only block wrist-tap launch when hands are separated (>0.24s) AND actively opposed for resize
            palm_sep = distance(pa, b_pt) / max(1.0, f.scale)
            actively_opposed_resize = (
                palm_sep > 0.24
                and d > 0.22
                and a.normal is not None
                and b.normal is not None
                and sum(x * y for x, y in zip(a.normal, b.normal)) < -0.35
            )
            support_fist_push = fresh(b) and b.shape == Shape.FIST and d < 0.48
            grip = (
                (self.grip_far and d < 0.36 and not actively_opposed_resize) or support_fist_push
            ) and t > self.grip_cooldown
            if self.hold.ready("launch", grip, t, self.cfg.water_grip_hold):
                events.append(self._launch_orb(a, center, scale, t))
                held = False
        else:
            self.hold.ready("launch", False, t, self.cfg.water_grip_hold)
            if not available(b):
                # Keep grip_far armed when second hand is out of view so bringing it in to tap wrist always works!
                self.grip_far = True

        # Additional effortless single-hand launch: deliberate fist-compress after water ball is held steady
        if (
            held
            and fresh(a)
            and a.shape == Shape.FIST
            and (a.openness is None or a.openness < 0.22)
            and t - self.spawned_at > 0.55
            and t > self.grip_cooldown
        ):
            if self.hold.ready("fist_launch", True, t, 0.16):
                events.append(self._launch_orb(a, center, scale, t))
                held = False
        else:
            self.hold.ready("fist_launch", False, t, 0.16)

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
            raw_center, scale = self.project(self.position, f)
            lev_offset_px = max(20.0, self.radius * scale * 1.25)
            center = (raw_center[0], raw_center[1] - lev_offset_px)
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
                    if abs(dz) > 1e-6:
                        candidates_alpha = (max(0.0, min(1.0, (target_z - before[2]) / dz)),)
                    else:
                        candidates_alpha = (0.0, 0.5, 1.0)
                    for alpha in candidates_alpha:
                        contact = [x + (y - x) * alpha for x, y in zip(before, shot.position)]
                        pixel, k = self.project(contact, f)
                        pad = shot.radius * k
                        if left - pad <= pixel[0] <= right + pad and top - pad <= pixel[1] <= bottom + pad:
                            hit = True
                            hit_position = contact
                            break
                    if hit:
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
        proj_c, proj_s = self.project(self.position, f)
        lev_c = (proj_c[0], proj_c[1] - max(20.0, self.radius * proj_s * 1.25))
        return SpellView(
            mode="water",
            state="SCALING" if self.scaling else "HELD" if held else "FLYING",
            visibility=1.0,
            intensity=1.0,
            center=lev_c,
            radius=self.radius * proj_s,
            caster=self.owner,
            objects=tuple(objects[-12:]),
            hint="水球悬浮掌心之上；双掌对称夹球可缩放；搭腕/握拳弹射发射；拍掌或双臂垂下收起",
            quality="水球持续保留；大开合或暂时遮挡不会消失",
        ), events
