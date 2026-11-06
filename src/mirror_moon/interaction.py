"""Deterministic business rules: inject timestamped Features, no devices or framework imports."""

import math
from collections import deque
from dataclasses import replace

from .config import DEFAULTS
from .domain import Event, Shape, SpellView
from .geometry import Hold, crossing, distance, segment_distance, smoothstep


class Circle:
    def __init__(self, cfg=DEFAULTS):
        self.cfg = cfg
        self.state, self.entered = "OFF", 0.0
        self.hold = Hold()
        self.support = self.caster = None
        self.last_good = self.last_support = 0.0
        self.last_depth = 0.0
        self.last_intensity = self.intensity = 0.0
        self.migration = 0.0
        self.previous_distance = None
        self.approach_until = 0.0
        self.distance_history = deque(maxlen=32)
        self.bent, self.extended = 75.0, 160.0
        self.last_t = None

    def transition(self, state, t):
        self.state, self.entered = state, t
        self.hold.clear()

    def update(self, f):
        t, s = f.timestamp, max(f.scale, 1.0)
        dt = min(0.1, max(0.0, t - self.last_t)) if self.last_t is not None else 0.0
        self.last_t = t
        emitted = []
        if f.valid:
            self.last_good = t
        if self.state == "OFF":
            self.support = self.caster = None
            for arm in f.arms:
                if self.hold.ready(arm.side, self.chest_fist(arm, f) and f.valid, t, self.cfg.summon_hold):
                    self.support = arm.side
                    self.caster = "right" if arm.side == "left" else "left"
                    self.transition("SUMMONING", t)
                    self.last_support = t
                    emitted.append(("summon", (), 0.0))
                    break
        if self.state == "SUMMONING" and t - self.entered >= self.cfg.summon_animation:
            self.transition("READY", t)
        if self.support:
            support, caster = f.arm(self.support), f.arm(self.caster)
            chest = f.valid and self.chest_fist(support, f)
            if support.tracked and f.valid:
                self.last_support = t
            open_cast = (
                f.valid
                and caster.tracked
                and caster.hand_valid
                and caster.shape == Shape.OPEN
                and self.raised(caster, f)
            )
            explicit_stop = self.hold.ready(
                "fist", caster.hand_valid and caster.shape == Shape.FIST, t, self.cfg.stop_fist
            ) or self.hold.ready(
                "lowered", caster.tracked and not self.raised(caster, f), t, self.cfg.stop_lowered
            )
            d, along = segment_distance(support.wrist, caster.elbow, caster.wrist)
            d /= s
            reference = next(
                (old for old in reversed(self.distance_history) if 0.08 <= t - old[0] <= 0.25), None
            )
            approaching = reference is not None and (reference[1] - d) / max(0.01, t - reference[0]) > 0.12
            if approaching and support.hand_valid and support.tracked:
                self.approach_until = t + 0.3
            if f.valid and support.tracked and caster.tracked:
                self.previous_distance = d
                self.distance_history.append((t, d))
            stale = t - self.last_good > self.cfg.lost_grace
            if stale and self.state != "FADING":
                self.transition("FADING", t)
            elif self.state == "READY":
                if self.hold.ready("open", open_cast and chest, t, self.cfg.cast_hold):
                    self.transition("CAST", t)
                elif self.hold.ready("chest_lost", not chest, t, self.cfg.lost_grace):
                    self.transition("FADING", t)
            elif self.state == "CAST":
                if explicit_stop:
                    self.transition("READY" if chest else "RETURN", t)
                elif not chest and open_cast and support.hand_valid and d < 0.8 and t <= self.approach_until:
                    # TRANSFER precedes the ordinary chest-maintenance cancellation.
                    self.transition("TRANSFER", t)
                elif self.hold.ready("chest_lost", not chest, t, self.cfg.lost_grace):
                    self.transition("FADING", t)
            elif self.state == "TRANSFER":
                if explicit_stop:
                    self.transition("READY" if chest else "RETURN", t)
                elif chest:
                    self.transition("CAST" if open_cast else "READY", t)
                elif self.hold.ready(
                    "grip",
                    open_cast
                    and support.hand_valid
                    and support.tracked
                    and 0.15 <= along <= 0.85
                    and d < self.cfg.grip_enter,
                    t,
                    self.cfg.grip_hold,
                ):
                    self.transition("OVERDRIVE", t)
                    emitted.append(("overdrive", (), 1.0))
                elif t - self.entered > self.cfg.transfer_window:
                    self.transition("FADING", t)
            elif self.state == "OVERDRIVE":
                if chest:
                    self.transition("CAST" if open_cast else "READY", t)
                elif explicit_stop or t - self.last_support > self.cfg.lost_grace:
                    self.transition("RETURN", t)
                elif support.tracked and (d > self.cfg.grip_exit or not 0.05 <= along <= 0.95):
                    self.transition("RETURN", t)
            elif self.state == "RETURN":
                if chest:
                    self.transition("CAST" if open_cast and not explicit_stop else "READY", t)
                elif t - self.entered > self.cfg.transfer_window:
                    self.transition("FADING", t)
            # Confidence loss is distinct from an explicit stop. No 2D depth replacement.
            active = self.state in ("CAST", "TRANSFER", "OVERDRIVE") and not explicit_stop
            if active and open_cast and caster.angle is not None:
                self.intensity = smoothstep((caster.angle - self.bent) / max(20.0, self.extended - self.bent))
                self.last_depth, self.last_intensity = t, self.intensity
            elif active:
                age = t - self.last_depth
                self.intensity = self.last_intensity * max(
                    0.0, 1.0 - max(0.0, age - self.cfg.depth_hold) / self.cfg.depth_fade
                )
            else:
                self.intensity = 0.0
            if active and not open_cast and t - self.last_depth > self.cfg.depth_hold + self.cfg.depth_fade:
                self.transition("READY" if chest else "RETURN", t)
        if self.state == "FADING" and t - self.entered > self.cfg.fade_time:
            self.transition("OFF", t)
            self.support = self.caster = None
            self.previous_distance = None
            self.distance_history.clear()
        target = 1.0 if self.state == "OVERDRIVE" else 0.0
        self.migration += max(-dt / 0.35, min(dt / 0.35, target - self.migration))
        visibility = 0.0 if self.state == "OFF" else 1.0
        if self.state == "FADING":
            visibility = max(0.0, 1.0 - (t - self.entered) / self.cfg.fade_time)
        elif self.state == "SUMMONING":
            visibility = min(1.0, (t - self.entered) / self.cfg.summon_animation)
        center = f.chest
        if self.caster:
            palm = f.arm(self.caster).wrist
            m = smoothstep(self.migration)
            center = tuple(a + (b - a) * m for a, b in zip(center, palm))
        hints = {
            "OFF": "一手握拳横在胸前，召唤星环",
            "SUMMONING": "保持胸前拳，星环正在展开",
            "READY": "另一手张开并抬起；伸直增强，收回减弱",
            "CAST": "持续施法；召唤手可移向施法前臂",
            "TRANSFER": "正在连接双手：让支撑手靠近前臂中段",
            "OVERDRIVE": "极限施法；支撑手回胸可恢复",
            "RETURN": "输出已停止，请将支撑手握拳放回胸前",
            "FADING": "星环收束，重新握拳即可召唤",
        }
        return SpellView(
            "circle",
            self.state,
            self.intensity,
            visibility,
            self.migration,
            self.support,
            self.caster,
            center,
            s * (1.0 + 0.4 * smoothstep(self.migration)),
            hint=hints[self.state],
            quality=f.reason if not f.valid else "已识别",
        ), emitted

    @staticmethod
    def raised(arm, f):
        return arm.wrist[1] < f.chest[1] + 0.6 * f.scale

    @staticmethod
    def chest_fist(arm, f):
        inward = abs(arm.wrist[0] - f.chest[0]) < abs(arm.elbow[0] - f.chest[0]) + 0.15 * f.scale
        return (
            arm.tracked
            and arm.hand_valid
            and arm.shape == Shape.FIST
            and distance(arm.wrist, f.chest) < 0.58 * f.scale
            and inward
        )


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

    def reset_motion(self):
        self.state, self.side = "IDLE", None
        self.history.clear()
        self.hold.clear()

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
                    and arm.shape in (Shape.OPEN, Shape.FIST)
                    and distance(arm.wrist, opposite) / f.scale < 0.43
                )
                if self.hold.ready(arm.side, condition, t, self.cfg.blade_prepare):
                    self.side, self.state, self.start = arm.side, "ARMED", t
                    self.scale, self.anchor = f.scale, f.chest
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
            if not arm.hand_valid or not arm.tracked or t - self.start > self.cfg.blade_max_time:
                self.reset_motion()
            else:
                p = ((arm.wrist[0] - f.chest[0]) / self.scale, (arm.wrist[1] - f.chest[1]) / self.scale)
                if self.history and t > self.history[-1][0]:
                    speed = distance(p, self.history[-1][1]) / (t - self.history[-1][0])
                    if speed > 14.0:
                        self.reset_motion()
                    else:
                        self.history.append((t, p))
                        span = distance(self.history[0][1], p)
                        length = sum(distance(a[1], b[1]) for a, b in zip(self.history, self.history[1:]))
                        recent = [h for h in self.history if t - h[0] <= 0.12]
                        velocity = distance(recent[0][1], p) / max(0.01, t - recent[0][0])
                        if span > 0.12:
                            self.state = "SWING"
                        outward = p[0] - self.history[0][1][0]
                        outward_ok = outward * self.direction > 0.3
                        if (
                            t - self.start >= self.cfg.blade_min_time
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
                            if self.last_slash and t - self.last_slash[0] < 0.8:
                                kind = (
                                    "cross"
                                    if crossing(
                                        self.last_slash[1][0], self.last_slash[1][-1], points[0], points[-1]
                                    )
                                    else "double"
                                )
                            strength = min(1.0, 0.7 * velocity / 4.0 + 0.3 * span / 1.2)
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
                self.direction *= -1.0
                self.history = [
                    (t, ((arm.wrist[0] - f.chest[0]) / self.scale, (arm.wrist[1] - f.chest[1]) / self.scale))
                ]
        hint = (
            "手收至对侧肩前短暂停留，再向外快速挥臂"
            if self.state == "IDLE"
            else "已蓄势，向外横挥或斜挥"
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

    def transition(self, state, t):
        self.state, self.entered = state, t
        self.hold.clear()

    def update(self, f):
        t, events = f.timestamp, []
        left, right = f.arms
        good = f.valid and all(a.hand_valid and a.tracked and a.shape == Shape.OPEN for a in f.arms)
        dt = t - self.last_t
        if dt > self.cfg.max_gap:
            self.history.clear()
        self.last_t = t
        if good:
            self.last_good = t
            d = distance(left.wrist, right.wrist) / f.scale
            mid = ((left.wrist[0] + right.wrist[0]) / 2, (left.wrist[1] + right.wrist[1]) / 2)
            raw_angle = math.atan2(right.wrist[1] - left.wrist[1], right.wrist[0] - left.wrist[0])
            # Left/right pose order may be reversed in unmirrored images. Axis is unoriented.
            raw_angle = (raw_angle + math.pi / 2) % math.pi - math.pi / 2
            self.angle = max(-0.6, min(0.6, raw_angle))
            if self.state == "IDLE":
                if d > 0.65:
                    self.require_release = False
                seed = (
                    not self.require_release and 0.20 <= d <= 0.52 and distance(mid, f.chest) / f.scale < 0.8
                )
                if self.hold.ready("seed", seed, t, self.cfg.mirror_seed):
                    self.transition("SEED", t)
            elif self.state == "SEED":
                if d > 0.65:
                    self.transition("OPENING", t)
                    self.opened, self.max_distance = t, d
                    self.history.clear()
                    events.append(("mirror_open", (), 0.5))
                elif t - self.entered > 2.0:
                    self.transition("IDLE", t)
            elif self.state in ("OPENING", "MANIPULATING", "FOLDING"):
                if self.state == "OPENING" and t - self.opened >= 0.35:
                    self.transition("MANIPULATING", t)
                self.max_distance = max(self.max_distance, d)
                self.history.append((t, d))
                self.history = [h for h in self.history if t - h[0] <= 0.14][-20:]
                speed = (self.history[0][1] - d) / max(0.01, t - self.history[0][0])
                if (
                    d < 0.55
                    and speed > self.cfg.mirror_shatter_speed
                    and self.max_distance - d > 0.5 * self.max_distance
                ):
                    self.close_candidate = (t, speed)
                else:
                    self.close_candidate = None
                if d < 0.40 and t - self.opened >= self.cfg.mirror_min_age:
                    if (
                        speed > self.cfg.mirror_shatter_speed
                        and self.max_distance - d > 0.5 * self.max_distance
                    ):
                        self.transition("SHATTER", t)
                        events.append(
                            ("shatter", (self.center, (self.size, self.angle)), min(1.0, speed / 5.0))
                        )
                    else:
                        self.transition("CLOSING", t)
                if self.state == "MANIPULATING":
                    if self.hold.ready("large", d > 1.5, t, 0.6):
                        if self.fold_anchor is None:
                            self.fold_anchor = mid
                        elif distance(mid, self.fold_anchor) / f.scale > 0.35:
                            self.transition("FOLDING", t)
                    else:
                        self.fold_anchor = None
            if self.state not in ("CLOSING", "SHATTER"):
                k = 1.0 - math.exp(-max(0.0, dt) * 14.0)
                self.center = tuple(a + (b - a) * k for a, b in zip(self.center if self.size else mid, mid))
                target_size = max(0.12, d * 0.5) * f.scale
                self.size += (target_size - self.size) * k if self.size else target_size
            self.prev_distance = d
        elif self.state in ("SEED", "OPENING", "MANIPULATING", "FOLDING"):
            # At most 150 ms to REACQUIRE an already observed closing trajectory.
            # Missing hands never produce a shatter event or predicted final distance.
            if not self.close_candidate or t - self.close_candidate[0] > 0.15:
                self.history.clear()
                self.close_candidate = None
            if t - self.last_good > self.cfg.mirror_lost:
                self.transition("CLOSING", t)
        if not good and any(a.hand_valid and a.shape != Shape.OPEN for a in f.arms):
            self.require_release = False
        if self.state in ("CLOSING", "SHATTER") and t - self.entered > 0.8:
            self.transition("IDLE", t)
            self.hold.clear()
            self.fold_anchor = None
            self.require_release = True
        self.visibility = 0.0 if self.state in ("IDLE", "SHATTER") else 1.0
        if self.state == "CLOSING":
            self.visibility = max(0.0, 1.0 - (t - self.entered) / 0.5)
        if self.state == "OPENING":
            self.visibility = min(1.0, (t - self.opened) / 0.35)
        hints = {
            "IDLE": "双手在胸前靠近开掌，停留后向两侧拉开",
            "SEED": "向两侧拉开双手，展开镜界",
            "OPENING": "镜面展开",
            "MANIPULATING": "移动双手操纵镜面；慢合收镜，快合碎镜",
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
        self.circle, self.blade, self.mirror = Circle(self.cfg), Blade(self.cfg), Mirror(self.cfg)
        self.circle.bent, self.circle.extended = bent, extended
        self.neutral_until = now + self.cfg.neutral_hold
        self.neutral_required = True
        self.neutral_hold.clear()
        self.view = SpellView(mode=self.mode)

    def update(self, features, mode=None, paused=False, cancel=False):
        t = features.timestamp
        if self.last_t is not None and t == self.last_t:
            return self.view, ()
        if self.last_t is not None and t < self.last_t:
            self.reset(t)
        self.last_t = t
        if cancel or (mode and mode != self.mode) or paused:
            self.mode = mode or self.mode
            self.reset(t)
        neutral = features.valid and all(
            a.tracked and (a.wrist[1] > features.chest[1] + 0.6 * features.scale or a.shape == Shape.OTHER)
            for a in features.arms
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
                    self.event_id, kind, features.frame_id, t, tuple(points), strength, self.event_id * 7919
                )
            )
        return self.view, tuple(events)
