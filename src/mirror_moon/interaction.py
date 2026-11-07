"""Deterministic business rules: inject timestamped Features, no devices or framework imports."""

import math
from dataclasses import replace

from .config import DEFAULTS
from .domain import Event, Shape, SpellView
from .geometry import Hold, arm_lowered, blade_combo, distance, fitted_velocity, recent_samples
from .star_ring import Circle


class Blade:
    def __init__(self, cfg=DEFAULTS):
        self.cfg, self.hold = cfg, Hold()
        self.state, self.side = "IDLE", None
        self.history = []
        self.start = self.last_t = self.emitted_t = 0.0
        self.scale = 1.0
        self.last_slash = None
        self.anchor = (0.0, 0.0)
        self.direction = 1.0
        self.reverse_pending = False
        self.motion_start = None
        self.last_seen = -1e9
        self.pose_offset = (0.0, 0.0)
        self.pose_bridge = False

    def reset_motion(self):
        self.state, self.side = "IDLE", None
        self.history.clear()
        self.hold.clear()
        self.motion_start = None

    def update(self, f):
        t, events = f.timestamp, []
        if self.last_t and (t - self.last_t > self.cfg.max_gap or t <= self.last_t):
            self.reset_motion()
        self.last_t = t
        if not f.valid:
            self.reset_motion()
        if self.state == "IDLE" and f.valid:
            for arm in f.arms:
                opposite = f.arm("right" if arm.side == "left" else "left").shoulder
                condition = (
                    arm.hand_valid
                    and distance(arm.wrist, opposite) / f.scale < 0.65
                    and distance(arm.wrist, opposite) < distance(arm.wrist, arm.shoulder) * 0.90
                )
                if self.hold.ready(arm.side, condition, t, self.cfg.blade_prepare):
                    self.side, self.state, self.start = arm.side, "ARMED", t
                    self.scale, self.anchor = f.scale, f.chest
                    self.last_seen = t
                    pose_wrist = arm.pose_wrist or arm.wrist
                    self.pose_offset = tuple(a - b for a, b in zip(arm.wrist, pose_wrist))
                    self.pose_bridge = False
                    self.motion_start = None
                    self.direction = 1.0 if arm.shoulder[0] > opposite[0] else -1.0
                    self.history = [
                        (
                            t,
                            (
                                (arm.wrist[0] - f.chest[0]) / self.scale,
                                (arm.wrist[1] - f.chest[1]) / self.scale,
                            ),
                        )
                    ]
                    break
        elif self.state in ("ARMED", "SWING"):
            arm = f.arm(self.side)
            point = arm.wrist
            available = arm.hand_valid
            invalid_return = False
            if arm.hand_valid:
                if self.pose_bridge and self.history:
                    actual = ((point[0] - f.chest[0]) / self.scale, (point[1] - f.chest[1]) / self.scale)
                    invalid_return = distance(actual, self.history[-1][1]) > 0.55
                self.last_seen = t
                pose_wrist = arm.pose_wrist or arm.wrist
                self.pose_offset = tuple(a - b for a, b in zip(arm.wrist, pose_wrist))
                self.pose_bridge = False
            elif (
                arm.tracked
                and arm.wrist_confidence >= 0.60
                and arm.elbow_visible
                and t - self.last_seen <= self.cfg.blade_pose_bridge
            ):
                # Observed, identity-anchored Pose wrist, not extrapolated velocity.
                pose_wrist = arm.pose_wrist or arm.wrist
                point = tuple(a + b for a, b in zip(pose_wrist, self.pose_offset))
                available = True
                self.pose_bridge = True
            else:
                # A reacquisition must start a new observed trajectory, never bridge an occlusion.
                self.history.clear()
                self.motion_start = None
                self.state = "ARMED"
            if (
                invalid_return
                or t - self.last_seen > 0.35
                or (self.motion_start is not None and t - self.motion_start > self.cfg.blade_max_time)
            ):
                self.reset_motion()
            elif available:
                p = ((point[0] - f.chest[0]) / self.scale, (point[1] - f.chest[1]) / self.scale)
                if not self.history:
                    self.history = [(t, p)]
                if self.history and t > self.history[-1][0]:
                    speed = distance(p, self.history[-1][1]) / (t - self.history[-1][0])
                    if speed > 18.0:
                        self.reset_motion()
                    else:
                        self.history.append((t, p))
                        self.history = self.history[-64:]
                        span = distance(self.history[0][1], p)
                        length = sum(distance(a[1], b[1]) for a, b in zip(self.history, self.history[1:]))
                        recent = recent_samples(self.history, t, 0.16, 0.35)
                        velocity = max(speed, math.hypot(*fitted_velocity(recent)))
                        if span > 0.12:
                            self.state = "SWING"
                            if self.motion_start is None:
                                self.motion_start = self.history[-2][0]
                        elif self.state == "ARMED":
                            self.start = t
                            self.history = self.history[-8:]
                        outward = p[0] - self.history[0][1][0]
                        outward_ok = outward * self.direction > 0.15
                        if (
                            self.motion_start is not None
                            and arm.hand_valid  # Pose-only motion can preserve, never fire, an attack.
                            and t - self.motion_start >= self.cfg.blade_min_time
                            and span >= self.cfg.blade_span
                            and velocity >= self.cfg.blade_speed
                            and span / max(0.001, length) >= 0.65
                            and outward_ok
                        ):
                            points = tuple(
                                (f.chest[0] + h[1][0] * self.scale, f.chest[1] + h[1][1] * self.scale)
                                for h in self.history
                            )
                            kind = "slash"
                            if self.last_slash and t - self.last_slash[0] < 1.1:
                                kind = blade_combo(
                                    self.last_slash[1][0], self.last_slash[1][-1], points[0], points[-1]
                                )
                            strength = min(1.0, 0.7 * velocity / 3.0 + 0.3 * span / 1.0)
                            events.append((kind, points, strength))
                            self.last_slash = (t, points)
                            self.emitted_t, self.state = t, "RECOVERY"
        elif self.state == "RECOVERY" and t - self.emitted_t >= self.cfg.blade_recovery:
            arm = f.arm(self.side)
            if not arm.hand_valid or t - self.emitted_t > 0.65:
                self.reset_motion()
            elif self.hold.ready("reverse", arm.tracked and arm.shape in (Shape.OPEN, Shape.FIST), t, 0.10):
                # Deliberate short recovery prepares the same arm for a reverse cut.
                self.state, self.start = "ARMED", t
                self.motion_start = None
                self.last_seen = t
                self.direction *= -1.0
                self.history = [
                    (t, ((arm.wrist[0] - f.chest[0]) / self.scale, (arm.wrist[1] - f.chest[1]) / self.scale))
                ]
        hint = (
            "手收至对侧肩前短暂停留，再向外快速挥臂"
            if self.state == "IDLE"
            else "已蓄势（尚未出刃）：向外横挥或斜挥"
            if self.state in ("ARMED", "SWING")
            else "月刃已释放，收手重新蓄势"
        )
        center = f.arm(self.side).wrist if self.side else f.chest
        return SpellView(
            "blade",
            self.state,
            center=center,
            radius=f.scale * 0.18,
            visibility=1.0 if self.state in ("ARMED", "SWING") else 0.0,
            hint=hint,
            quality="已识别" if f.valid else f.reason,
        ), events


class Mirror:
    def __init__(self, cfg=DEFAULTS):
        self.cfg, self.hold = cfg, Hold()
        self.state = "IDLE"
        self.entered = self.opened = self.last_good = self.last_t = 0.0
        self.prev_distance = self.max_distance = 0.0
        self.center = (0.0, 0.0)
        self.size = self.angle = 0.0
        self.fold_anchor = None
        self.history = []
        self.visibility = 0.0
        self.close_candidate = None
        self.require_release = False
        self.seed_distance = 0.4
        self.hand_seen = [-1e9, -1e9]
        self.previous_angle = None
        self.open_angle = 0.0
        self.closing_peaks = []
        self.frozen_folded = False

    def transition(self, state, t):
        self.state, self.entered = state, t
        self.hold.clear()

    def update(self, f):
        t, events = f.timestamp, []
        left, right = f.arms
        visible = f.valid and all(a.hand_valid for a in f.arms)
        for i, arm in enumerate(f.arms):
            if arm.hand_valid:
                self.hand_seen[i] = t
        prepared = visible and all(a.shape in (Shape.OPEN, Shape.OTHER) for a in f.arms)
        geometry_ok = f.valid and all(
            a.hand_valid
            or (
                a.tracked
                and a.wrist_confidence >= 0.60
                and t - self.hand_seen[i] <= self.cfg.mirror_geometry_bridge
            )
            for i, a in enumerate(f.arms)
        )
        good = prepared if self.state == "IDLE" else geometry_ok
        dt = t - self.last_t
        if dt > self.cfg.max_gap:
            self.history.clear()
        self.last_t = t
        if good:
            if visible:
                self.last_good = t
            d = distance(left.wrist, right.wrist) / f.scale
            mid = ((left.wrist[0] + right.wrist[0]) / 2, (left.wrist[1] + right.wrist[1]) / 2)
            raw_angle = math.atan2(right.wrist[1] - left.wrist[1], right.wrist[0] - left.wrist[0])
            # Unwrap the unoriented hand axis; an identity flip must not spin the mirror 180°.
            if d > 0.35:
                if self.previous_angle is None:
                    self.angle = (raw_angle + math.pi / 2) % math.pi - math.pi / 2
                else:
                    self.angle += (raw_angle - self.previous_angle + math.pi / 2) % math.pi - math.pi / 2
                self.previous_angle = raw_angle
            if self.state == "IDLE":
                if d > 0.65:
                    self.require_release = False
                seed = (
                    not self.require_release and 0.15 <= d <= 0.90 and distance(mid, f.chest) / f.scale < 0.90
                )
                if self.hold.ready("seed", seed, t, self.cfg.mirror_seed):
                    self.transition("SEED", t)
                    self.seed_distance = d
            elif self.state == "SEED":
                if d > max(0.70, self.seed_distance + 0.28):
                    self.transition("OPENING", t)
                    self.opened, self.max_distance = t, d
                    self.open_angle = self.angle
                    self.history.clear()
                    self.closing_peaks.clear()
                    events.append(("mirror_open", (), 0.5))
                elif t - self.entered > 2.0:
                    self.transition("IDLE", t)
            elif self.state in ("OPENING", "MANIPULATING", "FOLDING"):
                if self.state == "OPENING" and t - self.opened >= 0.35:
                    self.transition("MANIPULATING", t)
                self.max_distance = max(self.max_distance, d)
                if not visible:
                    self.history.clear()
                    self.closing_peaks.clear()
                    self.hold.ready("slow_close", False, t, self.cfg.mirror_close_hold)
                if self.history and d > self.history[-1][1] + 0.05:
                    self.closing_peaks.clear()
                    self.history.clear()
                adjacent_speed = (
                    (self.history[-1][1] - d) / max(0.001, t - self.history[-1][0]) if self.history else 0.0
                )
                if visible:
                    self.history.append((t, d))
                self.history = [h for h in self.history if t - h[0] <= 0.4][-20:]
                recent = recent_samples(self.history, t, 0.16, 0.35)
                speed = max(
                    adjacent_speed, -fitted_velocity([(stamp, (value, 0.0)) for stamp, value in recent])[0]
                )
                if visible and len(recent) >= 2:
                    self.closing_peaks.append((t, speed))
                self.closing_peaks = [row for row in self.closing_peaks if t - row[0] <= 0.22]
                peak_speed = max((row[1] for row in self.closing_peaks), default=0.0)
                if (
                    d < 0.55
                    and speed > self.cfg.mirror_shatter_speed
                    and self.max_distance - d > 0.5 * self.max_distance
                ):
                    self.close_candidate = (t, speed)
                else:
                    self.close_candidate = None
                if t - self.opened >= self.cfg.mirror_min_age:
                    if (
                        d < 0.70
                        and visible
                        and len(recent) >= 2
                        and adjacent_speed >= -0.10
                        and peak_speed > self.cfg.mirror_shatter_speed
                        and self.max_distance - d > 0.5 * self.max_distance
                    ):
                        self.frozen_folded = self.state == "FOLDING"
                        self.transition("SHATTER", t)
                        events.append(
                            ("shatter", (self.center, (self.size, self.angle)), min(1.0, speed / 5.0))
                        )
                    elif self.hold.ready(
                        "slow_close",
                        visible and d < self.cfg.mirror_close_distance and abs(speed) < 0.8,
                        t,
                        self.cfg.mirror_close_hold,
                    ):
                        self.transition("CLOSING", t)
                if self.state == "MANIPULATING":
                    if self.hold.ready(
                        "twist", d > 0.75 and abs(self.angle - self.open_angle) > 0.50, t, 0.25
                    ):
                        self.transition("FOLDING", t)
                    if self.hold.ready("large", d > 1.5, t, 0.6):
                        if self.fold_anchor is None:
                            self.fold_anchor = mid
                        elif distance(mid, self.fold_anchor) / f.scale > 0.35:
                            self.transition("FOLDING", t)
                    else:
                        self.fold_anchor = None
            if self.state not in ("CLOSING", "SHATTER"):
                k = 1.0 - math.exp(-max(0.0, dt) * 28.0)
                self.center = tuple(a + (b - a) * k for a, b in zip(self.center if self.size else mid, mid))
                target_size = max(0.12, d * 0.5) * f.scale
                self.size += (target_size - self.size) * k if self.size else target_size
            self.prev_distance = d
        elif self.state in ("SEED", "OPENING", "MANIPULATING", "FOLDING"):
            # Missing/reacquired samples never establish closing velocity.
            self.history.clear()
            self.close_candidate = None
            self.closing_peaks.clear()
            self.hold.ready("slow_close", False, t, self.cfg.mirror_close_hold)
            if t - self.last_good > self.cfg.mirror_lost:
                self.transition("CLOSING", t)
        if (not good and any(a.hand_valid and a.shape != Shape.OPEN for a in f.arms)) or all(
            arm_lowered(a, f) for a in f.arms
        ):
            self.require_release = False
        if self.state in ("CLOSING", "SHATTER") and t - self.entered > 0.8:
            self.transition("IDLE", t)
            self.hold.clear()
            self.fold_anchor = None
            self.require_release = True
            self.previous_angle = None
        self.visibility = 0.0 if self.state in ("IDLE", "SHATTER") else 1.0
        if self.state == "CLOSING":
            self.visibility = max(0.0, 1.0 - (t - self.entered) / 0.5)
        if self.state == "OPENING":
            self.visibility = min(1.0, (t - self.opened) / 0.35)
        hints = {
            "IDLE": "双掌在胸前稍错开，停一下再拉开；无需贴掌",
            "SEED": "镜缝准备完成（尚未展开）：向两侧拉开双手",
            "OPENING": "镜面展开",
            "MANIPULATING": "慢合并稍停可收镜，快合至一拳距离碎镜；转动双手可折镜",
            "FOLDING": "万象折镜；慢合收镜，快合碎镜",
            "SHATTER": "镜界碎裂，放松双手后重新开始",
            "CLOSING": "镜界收拢",
        }
        return SpellView(
            "mirror",
            self.state,
            visibility=self.visibility,
            center=self.center,
            radius=self.size,
            mirror_angle=self.angle,
            folded=self.state == "FOLDING",
            hint=hints[self.state],
            quality="已识别" if good else "请让双手回到画面",
        ), events


class Engine:
    def __init__(self, cfg=DEFAULTS):
        self.cfg = cfg
        self.circle, self.blade, self.mirror = Circle(cfg), Blade(cfg), Mirror(cfg)
        self.mode = "circle"
        self.event_id = 0
        self.last_t = None
        self.neutral_until = 0.0
        self.neutral_required = False
        self.neutral_hold = Hold()
        self.view = SpellView()

    def reset(self, now=0.0):
        bent, extended = self.circle.bent, self.circle.extended
        profiles = dict(self.circle.profiles)
        self.circle, self.blade, self.mirror = Circle(self.cfg), Blade(self.cfg), Mirror(self.cfg)
        self.circle.bent, self.circle.extended = bent, extended
        self.circle.profiles = profiles
        self.neutral_until = now + self.cfg.neutral_hold
        self.neutral_required = True
        self.neutral_hold.clear()
        self.view = SpellView(mode=self.mode)

    def update(self, features, mode=None, paused=False, cancel=False):
        t = features.timestamp
        if self.last_t is not None and t == self.last_t:
            return self.view, ()
        if self.last_t is not None and (t < self.last_t or t - self.last_t > self.cfg.max_gap):
            self.reset(t)
        self.last_t = t
        if cancel or (mode and mode != self.mode) or paused:
            self.mode = mode or self.mode
            self.reset(t)
        neutral = features.valid and all(
            arm_lowered(a, features) or (a.hand_valid and a.shape == Shape.OTHER) for a in features.arms
        )
        if self.neutral_required and self.neutral_hold.ready("neutral", neutral, t, self.cfg.neutral_hold):
            self.neutral_required = False
        if paused or t < self.neutral_until or self.neutral_required:
            self.view = replace(
                self.view, mode=self.mode, hint="已暂停" if paused else "放松双手，准备下一次动作"
            )
            return self.view, ()
        handler = {"circle": self.circle, "blade": self.blade, "mirror": self.mirror}[self.mode]
        self.view, raw = handler.update(features)
        events = []
        for kind, points, strength in raw:
            self.event_id += 1
            events.append(
                Event(
                    self.event_id,
                    kind,
                    features.frame_id,
                    t,
                    tuple(points),
                    strength,
                    self.event_id * 7919,
                    folded=self.mirror.frozen_folded if kind == "shatter" else False,
                    body_scale=features.scale,
                )
            )
        return self.view, tuple(events)
