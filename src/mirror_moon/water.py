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
        self.has_orb = False
        self.owner = None
        self.fists = set()
        self.fist_times = {}
        self.position, self.velocity = [0.0, 0.0, 2.0], [0.0] * 3
        self.radius = 0.075
        self.shots, self.splashes = [], []
        self.last_t = None
        self.spawned_at = -1e9
        self.recall_at = self.grip_cooldown = self.reopen_cooldown = -1e9
        self.grip_far, self.seed = True, 0
        self.scaling = False
        self.scaling_grace_until = -1e9
        self.scale_blend = 0.0
        self.resize_target = None
        self.pinch_span = None
        self.pinch_base_radius = 0.075
        self.hand_seen = {"left": -1e9, "right": -1e9}
        self.last_b_wrist = None
        self.last_b_d = 99.0
        self.last_projection = (0.0, 0.0)
        self.last_frame = None

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
        self.reopen_cooldown += delta
        self.scaling_grace_until += delta
        for side in list(self.fist_times):
            self.fist_times[side] += delta
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

    def _resize_midpoint(self, a, b, f):
        # Both hands share one estimated depth so projection remains an exact 50/50 screen anchor.
        depth = (self.target(a, f)[2] + self.target(b, f)[2]) * 0.5
        pa, pb = a.palm or a.wrist, b.palm or b.wrist
        focal = self.camera(f)
        return [
            ((pa[0] + pb[0]) * 0.5 - f.width * 0.5) * depth / focal,
            ((pa[1] + pb[1]) * 0.5 - f.height * 0.5) * depth / focal,
            depth,
        ]

    def _aim_direction(self, a, f):
        """Estimate a horizontal launch direction from observed forearm, fingers and palm."""
        normal = a.normal or (0.0, 0.0, -1.0)
        pa = a.palm or a.wrist
        fore_dx = fore_dy = 0.0
        if f is not None and (a.upper_valid or a.tracked) and distance(a.elbow, pa) > 12.0:
            s = max(40.0, f.scale)
            fore_dx = (pa[0] - a.elbow[0]) / s
            fore_dy = (pa[1] - a.elbow[1]) / s
        finger_dx = 0.0
        if a.landmarks and len(a.landmarks) > 9:
            finger_dx = (a.landmarks[9][0] - a.landmarks[0][0]) / max(18.0, a.palm_scale)

        if abs(fore_dx) > 0.26 or abs(finger_dx) > 0.36:
            aim_x = max(-0.92, min(0.92, fore_dx * 0.82 + finger_dx * 0.32 + normal[0] * 0.20))
        else:
            aim_x = max(-0.68, min(0.68, normal[0] * 0.55 + fore_dx * 0.45))

        # Keep vertical launch trajectory flat (linear translation / 平移) rather than shooting up when palm is up!
        aim_y = max(-0.08, min(0.08, fore_dy * 0.14))
        aim_z = -math.sqrt(max(0.18, 1.0 - min(0.82, aim_x * aim_x + aim_y * aim_y)))
        norm = math.sqrt(aim_x * aim_x + aim_y * aim_y + aim_z * aim_z) or 1.0
        return (aim_x / norm, aim_y / norm, aim_z / norm)

    def _launch_orb(self, a, center, scale, t, f=None):
        ref_f = f or self.last_frame
        direction = self._aim_direction(a, ref_f)
        velocity = [d * self.cfg.water_launch_speed for d in direction]
        self.seed += 1
        # Convert the exact displayed lift back to world space: resizing must not snap at release.
        lift = max(20.0, self.radius * scale * 1.25) / max(1.0, scale)
        spawn_pos = [self.position[0], self.position[1] - lift, self.position[2]]
        self.shots.append(Shot(spawn_pos, velocity, self.radius, t, self.seed))
        self.shots = self.shots[-8:]
        # Once launched, the orb flies away and does NOT auto-respawn in place after 0.85s!
        # A fresh FIST -> OPEN gesture is required to summon the next water orb.
        self.has_orb = False
        self.recall_at = float("inf")
        self.grip_cooldown = t + 0.75
        self.reopen_cooldown = t + self.cfg.water_reopen_cooldown
        self.grip_far = False
        self.fists.clear()
        self.fist_times.clear()
        self.pinch_span = None
        self.scaling = False
        self.scaling_grace_until = -1e9
        self.scale_blend = 0.0
        self.hold.clear()
        self.resize_target = None
        return ("water_launch", (center,), 1.0)

    def update(self, f):
        self.last_frame = f
        t, events = f.timestamp, []
        dt = min(0.20, max(0.0, t - self.last_t)) if self.last_t is not None else 0.0
        if self.last_t is not None and t - self.last_t > 0.5:
            self.hold.clear()
            self.grip_far = True
            self.pinch_span = None
            self.scaling_grace_until = -1e9
            self.clap.previous = None
        self.last_t = t
        for arm in f.arms:
            if fresh(arm):
                self.hand_seen[arm.side] = t
        if self.enabled and self.clap.update(f):
            self.enabled = False
            self.has_orb = False
            self.shots.clear()
            self.splashes.clear()
            self.fists.clear()
            self.fist_times.clear()
            self.hold.clear()
            self.pinch_span = None
            self.scaling = False
            self.scaling_grace_until = -1e9
            self.scale_blend = 0.0
            self.reopen_cooldown = t + self.cfg.water_reopen_cooldown
            return SpellView(mode="water", state="OFF", hint="水球已拍散；握拳再摊开重新召唤"), [
                ("water_close", (), 0.0)
            ]
        # Auto-dissolve when BOTH arms are lowered downward out of frame (excluding wide-span casting)
        if self.enabled and self.hold.ready(
            "lowered_close", both_arms_dropped_out(f), t, self.cfg.lowered_close_hold
        ):
            if self.has_orb:
                center, scale = self.project(self.position, f)
                lev_center = (center[0], center[1] - max(20.0, self.radius * scale * 1.25))
                self.seed += 1
                self.splashes.append((t, lev_center, max(45.0, self.radius * scale * 1.45), self.seed))
            self.enabled = False
            self.has_orb = False
            self.shots.clear()
            self.fists.clear()
            self.fist_times.clear()
            self.hold.clear()
            self.pinch_span = None
            self.scaling = False
            self.scaling_grace_until = -1e9
            self.scale_blend = 0.0
            self.reopen_cooldown = t + self.cfg.water_reopen_cooldown
            events.append(("water_close", (), 0.0))

        # Intentional summon: only when no held orb exists and after post-close/post-launch cooldown.
        # Requires a fresh FIST followed within 2.2s by a genuine OPEN palm (never relaxed OTHER!).
        if (not self.enabled or not self.has_orb) and t >= self.reopen_cooldown:
            for a in f.arms:
                not_lowered = not (f.valid and arm_lowered(a, f))
                is_summon_fist = (
                    fresh(a)
                    and not_lowered
                    and a.shape == Shape.FIST
                    and (a.openness is None or a.openness < 0.28)
                )
                if self.hold.ready(a.side + "fist", is_summon_fist, t, self.cfg.gesture_hold):
                    self.fists.add(a.side)
                    self.fist_times[a.side] = t
                fist_recent = a.side in self.fists and (t - self.fist_times.get(a.side, -1e9) <= 2.2)
                if not fist_recent:
                    self.fists.discard(a.side)
                is_summon_open = (
                    fist_recent
                    and fresh(a)
                    and not_lowered
                    and a.shape == Shape.OPEN
                    and (a.openness is None or a.openness >= 0.45)
                )
                if self.hold.ready(a.side + "open", is_summon_open, t, self.cfg.gesture_hold):
                    self.enabled, self.has_orb, self.owner = True, True, a.side
                    self.radius = 0.075
                    self.position, self.velocity = self.target(a, f), [0.0] * 3
                    self.grip_far = True
                    self.spawned_at = t
                    self.pinch_span = None
                    self.pinch_base_radius = 0.075
                    self.scaling = False
                    self.scaling_grace_until = -1e9
                    self.scale_blend = 0.0
                    self.recall_at = -1e9
                    self.fists.clear()
                    self.fist_times.clear()
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
        held = self.has_orb and t >= self.recall_at
        raw_center, scale = self.project(self.position, f)
        lev_offset_px = max(20.0, self.radius * scale * 1.25)
        center = (raw_center[0], raw_center[1] - lev_offset_px)
        self.scaling = False

        def available(arm):
            return fresh(arm) or (
                (
                    (arm.upper_valid or arm.tracked)
                    and f.valid
                    and arm.wrist_confidence >= 0.55
                    and not arm_lowered(arm, f)
                )
                or (arm.side == b.side and t - self.hand_seen[b.side] < 0.35 and self.last_b_d < 0.44)
            )

        if fresh(b):
            self.last_b_wrist = b.palm or b.wrist
        b_pt = (
            (b.palm or b.wrist)
            if (b.hand_valid or b.upper_valid or b.tracked)
            else (self.last_b_wrist or b.wrist)
        )
        pa = a.palm or a.wrist
        s_norm = max(1.0, f.scale)
        b_candidates = [b_pt]
        if b.wrist and b.wrist != b_pt:
            b_candidates.append(b.wrist)
        d_fore = min(
            (
                segment_distance(pt, a.elbow, a.wrist)[0]
                if (a.upper_valid or a.tracked) and distance(a.elbow, a.wrist) > 8.0
                else distance(pa, pt)
            )
            for pt in b_candidates
        )
        d_wrist = min(distance(a.wrist, pt) for pt in b_candidates)
        d_palm = min(distance(pa, pt) for pt in b_candidates)
        d = min(d_fore, d_wrist, d_palm) / s_norm
        if fresh(b) or b.upper_valid or b.tracked:
            self.last_b_d = d

        # Smooth two-hand scaling with hysteresis:
        # 1. Entry requires both hands OPEN/PINCH (never OTHER/FIST) and not lowered.
        # 2. Once scaling is active (pinch_span is not None), a 0.22s continuity grace tolerates brief OTHER shape flicker,
        #    and the orb anchors smoothly at the 50/50 midpoint between both hands without snapping or oscillating!
        not_lowered_b = not (f.valid and arm_lowered(b, f))
        not_lowered_a = not (f.valid and arm_lowered(a, f))
        palm_span_norm = distance(pa, b_pt) / s_norm
        entry_shapes_ok = a.shape in (Shape.OPEN, Shape.PINCH) and b.shape in (Shape.OPEN, Shape.PINCH)
        continue_shapes_ok = (
            self.pinch_span is not None
            and t <= self.scaling_grace_until
            and a.shape in (Shape.OPEN, Shape.PINCH, Shape.OTHER)
            and b.shape in (Shape.OPEN, Shape.PINCH, Shape.OTHER)
        )
        second_hand_scaling_ok = (
            held
            and fresh(a)
            and fresh(b)
            and not_lowered_a
            and not_lowered_b
            and (entry_shapes_ok or continue_shapes_ok)
            and palm_span_norm >= (0.18 if self.pinch_span is not None else 0.22)
        )
        resize_ready = self.hold.ready("resize", second_hand_scaling_ok, t, 0.10) or (
            self.pinch_span is not None and t <= self.scaling_grace_until and second_hand_scaling_ok
        )
        if resize_ready:
            pb = b.palm or b.wrist
            spacing = distance(pa, pb)
            midpoint = ((pa[0] + pb[0]) / 2, (pa[1] + pb[1]) / 2)
            min_spacing = max(self.radius * scale * 0.55, f.scale * 0.22)
            entry_center_ok = self.pinch_span is not None or distance(midpoint, raw_center) < max(
                self.radius * scale * 2.60, f.scale * 1.45
            )
            if spacing > min_spacing and entry_center_ok:
                if self.pinch_span is None:
                    self.pinch_span = max(spacing, 36.0)
                    self.pinch_base_radius = self.radius
                if entry_shapes_ok:
                    self.scaling_grace_until = t + 0.22
                self.scale_blend = min(
                    1.0, self.scale_blend + (1.0 - self.scale_blend) * min(1.0, dt * 14.0 + 0.35)
                )
                span_ratio = (spacing / self.pinch_span) ** 1.18
                desired = max(0.045, min(0.58, self.pinch_base_radius * span_ratio))
                self.radius += (desired - self.radius) * (1 - math.exp(-dt * 11.0))
                mid_target = self._resize_midpoint(a, b, f)
                self.resize_target = mid_target
                target = [x + (m - x) * self.scale_blend for x, m in zip(target, mid_target)]
                self.scaling = True
            elif t > self.scaling_grace_until:
                self.pinch_span = None
        elif t > self.scaling_grace_until:
            self.pinch_span = None

        # A brief missing/UNKNOWN observation holds the last measured midpoint; never snap to the owner.
        if (
            not self.scaling
            and held
            and self.pinch_span is not None
            and t <= self.scaling_grace_until
            and self.resize_target is not None
            and not_lowered_a
            and not_lowered_b
            and not any(fresh(h) and h.shape == Shape.FIST for h in (a, b))
        ):
            target = list(self.resize_target)
            self.scaling = True
        if not self.scaling and held and fresh(a) and fresh(b) and self.scale_blend > 0.01:
            self.scale_blend = max(0.0, self.scale_blend - dt * 5.0)
            mid_target = self._resize_midpoint(a, b, f)
            target = [x + (m - x) * self.scale_blend for x, m in zip(target, mid_target)]
        elif not self.scaling:
            self.scale_blend = 0.0

        if held and available(a) and available(b):
            if d > 0.36:
                self.grip_far = True
            palm_sep = d_palm / s_norm
            opposed_normals = (
                a.normal is not None
                and b.normal is not None
                and sum(x * y for x, y in zip(a.normal, b.normal)) < -0.35
            )
            wrist_or_forearm_tap = min(d_fore, d_wrist) / s_norm < 0.38 and (
                d_palm >= min(d_fore, d_wrist) * 0.95 or not self.scaling
            )
            actively_opposed_resize = (
                opposed_normals
                and palm_sep > 0.24
                and d > 0.24
                and (self.scaling or not wrist_or_forearm_tap)
            )
            support_fist_push = fresh(b) and b.shape == Shape.FIST and d < 0.50
            palm_forward_or_sideways = a.normal is not None and (
                abs(a.normal[2]) > 0.42 or abs(a.normal[0]) > 0.42
            )
            tap_threshold = 0.42 if palm_forward_or_sideways else 0.38
            grip = (
                (self.grip_far and d < tap_threshold and not actively_opposed_resize) or support_fist_push
            ) and t > self.grip_cooldown
            if self.hold.ready("launch", grip, t, self.cfg.water_grip_hold):
                events.append(self._launch_orb(a, center, scale, t, f))
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
                events.append(self._launch_orb(a, center, scale, t, f))
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
            visibility=1.0 if (held or objects) else 0.0,
            intensity=1.0 if (held or objects) else 0.0,
            center=lev_c,
            radius=self.radius * proj_s,
            caster=self.owner,
            objects=tuple(objects[-12:]),
            hint=(
                "水球悬浮掌心之上；双掌对称夹球可缩放；掌向前/侧身搭腕或握拳发射；拍掌或双臂垂下收起"
                if held
                else "水球已高速平飞发射；再次握拳后摊开可召唤新水球"
            ),
            quality="水球持续保留；大开合或暂时遮挡不会消失",
        ), events
