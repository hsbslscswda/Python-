"""Star ring session: summon, free support hand, observed forearm/dual-palm boost, explicit end."""

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
        self.bent, self.extended = 75.0, 134.0
        self.last_good = self.last_caster = 0.0
        self.last_support_hand = self.last_caster_hand = -1e9
        self.last_open = -1e9
        self.approach_until = 0.0
        self.distances = deque(maxlen=2048)
        self.support_path = deque(maxlen=2048)
        self.session_started = False
        self.migration = self.intensity = 0.0
        self.last_t = None

    def transition(self, state, t):
        if self.state != state:
            self.state, self.entered = state, t
            self.hold.clear()

    @staticmethod
    def raised(arm, f):
        return not arm_lowered(arm, f) and arm.wrist[1] < f.chest[1] + 0.65 * f.scale

    @staticmethod
    def chest_fist(arm, f):
        # Reject lowered/resting hands on lap, desk, or chair armrests so circle never false-summons when hands are down.
        if arm_lowered(arm, f):
            return False
        dx = abs(arm.wrist[0] - f.chest[0]) / max(1.0, f.scale)
        dy = (arm.wrist[1] - f.chest[1]) / max(1.0, f.scale)
        horizontal = abs(arm.wrist[1] - arm.elbow[1]) < 0.48 * f.scale
        wrist_not_hanging = not arm.elbow_visible or arm.wrist[1] <= arm.elbow[1] + 0.22 * f.scale
        return (
            wrist_not_hanging
            and (
                arm.hand_valid
                and arm.shape in (Shape.FIST, Shape.PINCH)
                or horizontal
                and (arm.hand_valid or arm.upper_valid and arm.wrist_confidence >= 0.55)
            )
            and dx < 1.15
            and (-1.40 < dy <= 0.38 or (horizontal and -1.9 < dy <= 0.32))
        )

    def update(self, f):
        t, s = f.timestamp, max(1.0, f.scale)
        raw_dt = t - self.last_t if self.last_t is not None else 0.0
        dt = min(0.2, max(0.0, raw_dt))
        if raw_dt > 0.18:
            self.hold.starts.pop("direct_near", None)
            self.hold.starts.pop("dual_res", None)
        self.last_t = t
        emitted = []
        if f.valid:
            self.last_good = t
        if self.state == "OFF":
            self.support = self.caster = None
            self.session_started = False
            self.intensity = 0.0
            for arm in sorted(f.arms, key=lambda a: a.shape not in (Shape.FIST, Shape.PINCH)):
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
            if (caster.tracked or caster.upper_valid) and f.valid:
                self.last_caster = t
            observed_open = (
                f.valid
                and caster.hand_valid
                and caster.shape in (Shape.OPEN, Shape.OTHER, Shape.PINCH)
                and self.raised(caster, f)
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

            # Support-to-caster distance: focus on forearm (elbow->wrist) and wrist to avoid
            # false overdrive when the support hand simply rests near the upper arm/chest!
            d_fore, along = segment_distance(support.wrist, caster.elbow, caster.wrist)
            d_upper, along_upper = segment_distance(support.wrist, caster.shoulder, caster.elbow)
            d_wrist = distance(support.wrist, caster.wrist)
            is_extended_arm = (caster.angle is not None and caster.angle > 115.0) or (
                distance(caster.elbow, caster.wrist) / s < 0.42
            )
            d = min(d_fore, d_upper if (is_extended_arm and 0.55 <= along_upper <= 1.0) else d_fore) / s
            for history in (self.distances, self.support_path):
                while history and t - history[0][0] > 1.35:
                    history.popleft()
            relative = ((support.wrist[0] - f.chest[0]) / s, (support.wrist[1] - f.chest[1]) / s)
            reference = next((row for row in self.distances if 0.12 <= t - row[0] <= 1.25), None)
            path_ref = next((row for row in self.support_path if 0.12 <= t - row[0] <= 1.25), None)
            moving = path_ref is not None and distance(relative, path_ref[1]) > 0.06
            approach = reference is not None and reference[1] - d > 0.025
            if support.tracked and f.valid:
                if moving and approach and t - self.last_support_hand < 0.65:
                    self.approach_until = t + 0.90
                self.distances.append((t, d))
                self.support_path.append((t, relative))

            along_ok = -0.10 <= along <= 1.32 or (
                is_extended_arm
                and (
                    d_wrist / s < self.cfg.grip_enter * 1.20
                    or distance(support.wrist, caster.elbow) / s < self.cfg.grip_enter * 1.20
                    or 0.55 <= along_upper <= 1.05
                )
            )
            near = (
                support.tracked
                and not arm_lowered(support, f)
                and (caster.elbow_visible or caster.tracked)
                and along_ok
                and d < self.cfg.grip_enter * (1.18 if is_extended_arm else 1.0)
                and t - self.last_support_hand < 0.65
            )
            # Zero-occlusion alternative overdrive: Dual-Palm Resonance (双掌同辉共鸣结印)
            # Raising and opening the support palm alongside the casting hand triggers overdrive without hand-on-arm occlusion!
            dual_palm_open = (
                f.valid
                and support.hand_valid
                and support.shape == Shape.OPEN
                and (support.openness is None or support.openness >= 0.55)
                and self.raised(support, f)
                and 0.22 <= d_wrist / s <= 0.85
                and abs(support.wrist[1] - caster.wrist[1]) / s <= 0.38
            )
            sustained_near = self.hold.ready(
                "direct_near",
                near and support.hand_valid and (d_wrist / s < 0.35 or along >= 0.25),
                t,
                0.10,
            )
            sustained_dual = self.hold.ready("dual_res", dual_palm_open, t, 0.14)

            if self.state == "CAST":
                if (
                    ((near or (support.tracked and moving and d < 0.65)) and t <= self.approach_until)
                    or sustained_near
                    or sustained_dual
                ):
                    self.transition("TRANSFER", t)
            elif self.state == "TRANSFER":
                if self.hold.ready("grip", near or dual_palm_open, t, self.cfg.grip_hold):
                    self.transition("OVERDRIVE", t)
                    emitted.append(("overdrive", (), 1.3))
                elif t - self.entered > self.cfg.transfer_window or (
                    chest and d > self.cfg.grip_exit and not dual_palm_open
                ):
                    self.transition("CAST", t)
            elif self.state == "OVERDRIVE":
                if chest and d > self.cfg.grip_exit and not dual_palm_open:
                    self.transition("CAST", t)
                else:
                    support_lost = self.hold.ready("support_lost", not support.tracked, t, 0.30)
                    outside = (
                        support.tracked
                        and not dual_palm_open
                        and (
                            d > self.cfg.grip_exit * 1.15
                            or (not is_extended_arm and not -0.20 <= along <= 1.40)
                        )
                    )
                    detached = self.hold.ready("detach", outside, t, 0.22)
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
                if (
                    self.state in ("CAST", "TRANSFER", "OVERDRIVE", "RETURN")
                    and not caster.hand_valid
                    and (caster.tracked or caster.upper_valid)
                    and self.raised(caster, f)
                ):
                    self.last_open = max(self.last_open, t - 0.30)
                    self.last_caster_hand = max(self.last_caster_hand, t - 0.30)
                intent_age = t - min(self.last_caster_hand, self.last_open)
                intent_hold = 1.10 if self.state in ("TRANSFER", "OVERDRIVE") else 0.70
                if intent_age > intent_hold:
                    normal *= max(0.0, 1.0 - (intent_age - intent_hold) / 0.25)
                if intent_age > intent_hold + 0.30:
                    self.transition("READY", t)
                    normal = 0.0
                if self.state == "OVERDRIVE" and (
                    reliable or (control.last_good is not None and t - control.last_good < 0.75)
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
            "OFF": "一手抬至胸前/颈前握拳或横臂召唤（双手垂放桌面不会误触）",
            "SUMMONING": "极寒冰魄法阵展开中…",
            "READY": "另一手张开抬起开始施法；握拳停法，放下施法手收阵",
            "CAST": "施法中：伸臂增强；副手搭腕或双掌同时张开共鸣可突破 100% 过载",
            "TRANSFER": "极寒冰魄共鸣中：保持搭腕或双掌同辉即可解放暴风雪过载",
            "OVERDRIVE": "冰魔法暴风雪过载 110–150%；松开副手恢复常态，放下施法手收阵",
            "RETURN": "恢复常态施法，召唤手无需回胸",
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
