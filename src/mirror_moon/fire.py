"""Two independent hands. No body requirement and no missing-sample-as-fist rule."""

from .config import DEFAULTS
from .domain import EffectObject, Shape, SpellView
from .geometry import Hold


class Flame:
    def __init__(self):
        self.unlocked = self.saw_open = self.active = False
        self.hold = Hold()
        self.last_seen = -1e9
        self.center = (0.0, 0.0)
        self.size = 0.0
        self.born = 0.0
        self.opacity = 0.0


class Fire:
    def __init__(self, cfg=DEFAULTS):
        self.cfg = cfg
        self.hands = {s: Flame() for s in ("left", "right")}
        self.last_t = None

    def update(self, f):
        t, objects, events = f.timestamp, [], []
        if self.last_t is not None and t - self.last_t > 0.35:
            for flame in self.hands.values():
                flame.hold.clear()
        self.last_t = t
        charging = 0
        for arm in f.arms:
            flame = self.hands[arm.side]
            fresh = arm.hand_valid and arm.shape_age <= self.cfg.gesture_max_age
            fraction = arm.openness if arm.openness is not None else (0.0 if arm.shape == Shape.FIST else 1.0)
            fist = fresh and arm.shape == Shape.FIST and fraction < 0.20
            opened = fresh and arm.shape != Shape.UNKNOWN and not fist
            if opened:
                flame.saw_open = True
            if not flame.unlocked:
                if flame.hold.ready("unlock", flame.saw_open and fist, t, self.cfg.fire_unlock):
                    flame.unlocked = True
                    events.append(("fire_unlock", (), 1.0))
                if fist and flame.saw_open:
                    charging += 1
                if not fresh:
                    flame.hold.ready("unlock", False, t, self.cfg.fire_unlock)
            # Palm normal is inferred from this hand's own landmarks, never Pose world subtraction.
            down = fresh and arm.normal is not None and arm.normal[1] > self.cfg.fire_palm_down
            if flame.hold.ready("down", down, t, self.cfg.gesture_hold) or flame.hold.ready(
                "fist", fist, t, self.cfg.gesture_hold
            ):
                if flame.active:
                    events.append(("fire_out", (), 0.0))
                flame.active = False
            if flame.unlocked and flame.hold.ready("open", opened and not down, t, self.cfg.gesture_hold):
                if not flame.active:
                    flame.active, flame.born = True, t
                    events.append(("ignite", (arm.palm or arm.wrist,), 1.0))
            if fresh:
                flame.last_seen = t
                flame.center = arm.palm or arm.wrist
                if arm.shape != Shape.UNKNOWN:
                    flame.size = max(12.0, arm.palm_scale * 0.8 or f.scale * 0.20) * max(
                        0.0, min(1.0, fraction)
                    )
            age = t - flame.last_seen
            fade = max(0.0, 1.0 - max(0.0, age - self.cfg.fire_loss_hold) / self.cfg.fire_loss_fade)
            flame.opacity = fade if flame.active else 0.0
            if age > self.cfg.fire_loss_hold + self.cfg.fire_loss_fade:
                flame.active = False
            if flame.active and flame.size > 0.5:
                objects.append(EffectObject(4, flame.center, flame.size, t - flame.born, fade))
        ready = any(h.unlocked for h in self.hands.values())
        hint = (
            "火焰跟随掌心；收拳逐渐熄灭，翻掌朝下熄灭"
            if objects
            else "保持握拳满2秒，解锁该手"
            if charging
            else "张开手掌点火；左右手独立"
            if ready
            else "先张开手，再握拳保持2秒解锁；随后张开点火"
        )
        return SpellView(
            mode="fire",
            state="BURNING" if objects else "READY" if ready else "LOCKED",
            visibility=float(bool(objects)),
            intensity=float(bool(objects)),
            objects=tuple(objects),
            hint=hint,
            quality="只需手部入画，无需站立或露出身体",
        ), events
