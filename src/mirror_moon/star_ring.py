"""Star ring session: summon, free support hand, observed forearm boost, explicit end."""

from collections import deque

from .config import DEFAULTS
from .control import IntensityController
from .domain import Shape, SpellView
from .geometry import Hold, arm_lowered, distance, segment_distance, smoothstep


class Circle:
    def __init__(self, cfg=DEFAULTS):
        self.cfg = cfg
        self.state, self.entered = "OFF", 0.0
        self.support = self.caster = None
        self.hold = Hold()
        self.controllers = {side: IntensityController() for side in ("left", "right")}
        self.profiles = {}
        self.bent, self.extended = 75.0, 160.0
        self.last_good = self.last_caster = 0.0
        self.last_support_hand = self.last_caster_hand = -1e9
        self.last_open = -1e9
        self.approach_until = 0.0
        self.distances = deque(maxlen=24)
        self.support_path = deque(maxlen=24)
        self.session_started = False
        self.migration = self.intensity = 0.0
        self.last_t = None

    def transition(self, state, t):
        if self.state != state:
            self.state, self.entered = state, t
            self.hold.clear()

    @staticmethod
    def raised(arm, f):
        return not arm_lowered(arm, f) and arm.wrist[1] < f.chest[1] + 0.70 * f.scale

    @staticmethod
    def chest_fist(arm, f):
        # No fixed elbow angle and no requirement to cross the forearm horizontally.
        dx = abs(arm.wrist[0] - f.chest[0]) / max(1.0, f.scale)
        dy = (arm.wrist[1] - f.chest[1]) / max(1.0, f.scale)
        return arm.hand_valid and arm.shape == Shape.FIST and dx < 0.95 and -0.75 < dy < 0.80

    def update(self, f):
        t, s = f.timestamp, max(1.0, f.scale)
        dt = min(0.2, max(0.0, t - self.last_t)) if self.last_t is not None else 0.0
        self.last_t = t
        emitted = []
        if f.valid:
            self.last_good = t
        if self.state == "OFF":
            self.support = self.caster = None
            self.session_started = False
            self.intensity = 0.0
            for arm in f.arms:
                if self.hold.ready(arm.side, f.valid and self.chest_fist(arm, f), t, self.cfg.summon_hold):
                    self.support = arm.side
                    self.caster = "right" if arm.side == "left" else "left"
                    self.controllers[self.caster] = IntensityController()
                    self.last_caster = t
                    self.transition("SUMMONING", t)
                    emitted.append(("summon", (), 0.0))
                    break
        if self.state == "SUMMONING" and t - self.entered >= self.cfg.summon_animation:
            self.transition("READY", t)
        reliable = False
        if self.support is not None:
            support, caster = f.arm(self.support), f.arm(self.caster)
            chest = f.valid and self.chest_fist(support, f)
            if support.hand_valid:
                self.last_support_hand = t
            if caster.hand_valid:
                self.last_caster_hand = t
            if caster.tracked and f.valid:
                self.last_caster = t
            observed_open = (
                f.valid and caster.hand_valid and caster.shape == Shape.OPEN and self.raised(caster, f)
            )
            if observed_open:
                self.last_open = t
            stopped_fist = self.hold.ready(
                "stop_fist", caster.hand_valid and caster.shape == Shape.FIST, t, self.cfg.stop_fist
            )
            lowered = self.hold.ready("lowered", f.valid and arm_lowered(caster, f), t, self.cfg.stop_lowered)
            active = self.state in ("CAST", "TRANSFER", "OVERDRIVE", "RETURN")
            stale = t - self.last_good > self.cfg.lost_grace or (
                self.session_started and t - self.last_caster > self.cfg.lost_grace
            )
            if stale and self.state != "FADING":
                self.transition("FADING", t)
            elif lowered and self.session_started:
                self.transition("FADING", t)
            elif stopped_fist and active:
                self.transition("READY", t)
            elif self.state == "READY":
                if self.hold.ready(
                    "open", observed_open and (chest or self.session_started), t, self.cfg.cast_hold
                ):
                    self.session_started = True
                    self.transition("CAST", t)
                elif not self.session_started and self.hold.ready("summon_lost", not chest, t, 0.85):
                    self.transition("FADING", t)

            d, along = segment_distance(support.wrist, caster.elbow, caster.wrist)
            d /= s
            relative = ((support.wrist[0] - f.chest[0]) / s, (support.wrist[1] - f.chest[1]) / s)
            reference = next((row for row in self.distances if 0.15 <= t - row[0] <= 1.20), None)
            path_ref = next((row for row in self.support_path if 0.15 <= t - row[0] <= 1.20), None)
            moving = path_ref is not None and distance(relative, path_ref[1]) > 0.075
            approach = reference is not None and reference[1] - d > 0.03
            if support.tracked and f.valid:
                if moving and approach and t - self.last_support_hand < 0.5:
                    self.approach_until = t + 0.85
                self.distances.append((t, d))
                self.support_path.append((t, relative))
            foreshortened = distance(caster.elbow, caster.wrist) / s < 0.25
            along_ok = -0.05 <= along <= 1.22 or (
                foreshortened and distance(support.wrist, caster.elbow) / s < self.cfg.grip_enter
            )
            near = (
                support.tracked
                and caster.elbow_visible
                and along_ok
                and d < self.cfg.grip_enter
                and t - self.last_support_hand < 0.50
            )
            if self.state == "CAST":
                if near or (support.tracked and moving and d < 0.65 and t <= self.approach_until):
                    if t <= self.approach_until:
                        self.transition("TRANSFER", t)
            elif self.state == "TRANSFER":
                if self.hold.ready("grip", near, t, self.cfg.grip_hold):
                    self.transition("OVERDRIVE", t)
                    emitted.append(("overdrive", (), 1.3))
                elif t - self.entered > self.cfg.transfer_window or (chest and d > self.cfg.grip_exit):
                    self.transition("CAST", t)
            elif self.state == "OVERDRIVE":
                support_lost = self.hold.ready("support_lost", not support.tracked, t, 0.3)
                outside = support.tracked and (
                    d > self.cfg.grip_exit or (not foreshortened and not -0.15 <= along <= 1.35)
                )
                detached = self.hold.ready("detach", outside, t, 0.15)
                if detached or support_lost:
                    self.transition("RETURN", t)
            elif self.state == "RETURN" and t - self.entered >= 0.25:
                self.transition("CAST", t)

            active = self.state in ("CAST", "TRANSFER", "OVERDRIVE", "RETURN")
            control = self.controllers[self.caster]
            if active:
                endpoints = self.profiles.get(self.caster, (self.bent, self.extended))
                angle = caster.angle if f.valid and caster.tracked else None
                normal = control.update(angle, t, *endpoints)
                reliable = control.reliable
                intent_age = t - min(self.last_caster_hand, self.last_open)
                intent_hold = 1.10 if self.state in ("TRANSFER", "OVERDRIVE") else 0.60
                if intent_age > intent_hold:
                    normal *= max(0.0, 1.0 - (intent_age - intent_hold) / 0.25)
                if intent_age > intent_hold + 0.30:
                    self.transition("READY", t)
                    normal = 0.0
                if self.state == "OVERDRIVE" and (
                    reliable or (control.last_good is not None and t - control.last_good < 0.60)
                ):
                    self.intensity = normal + (1.10 + 0.40 * normal - normal) * smoothstep(self.migration)
                else:
                    self.intensity = normal
            else:
                self.intensity = 0.0
        if self.state == "FADING":
            self.intensity = 0.0
            if t - self.entered >= self.cfg.fade_time:
                self.transition("OFF", t)
                self.support = self.caster = None
                self.distances.clear()
                self.support_path.clear()
        target = 1.0 if self.state == "OVERDRIVE" else 0.45 if self.state == "TRANSFER" else 0.0
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
            "OFF": "一手在胸前或肩前松握拳，即可召唤；肘角不限",
            "SUMMONING": "星环展开中",
            "READY": "另一手张开抬起开始施法；握拳停法，放下施法手收阵",
            "CAST": "施法中：召唤手可自由活动，搭住施法前臂可突破100%",
            "TRANSFER": "正在确认搭臂：靠近前臂中段并稍作保持",
            "OVERDRIVE": "搭臂增强 110–150%；放开恢复普通，放下施法手收阵",
            "RETURN": "恢复普通施法，召唤手无需回胸",
            "FADING": "收阵中，放松后可重新召唤",
        }
        quality = f.reason if not f.valid else "肘角已读" if reliable else "已识别"
        if self.state in ("CAST", "TRANSFER", "OVERDRIVE", "RETURN") and not reliable:
            quality = "肘角暂不可靠：强度保持后缓降"
        return SpellView(
            mode="circle",
            state=self.state,
            intensity=self.intensity,
            visibility=visibility,
            migration=self.migration,
            support=self.support,
            caster=self.caster,
            center=center,
            radius=s * (1.0 + 0.40 * smoothstep(self.migration)),
            hint=hints[self.state],
            quality=quality,
            control_reliable=reliable,
        ), emitted
