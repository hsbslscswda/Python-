"""Two independent hands. No body requirement and no missing-sample-as-fist rule."""

import math

from .config import DEFAULTS
from .domain import EffectObject, Shape, SpellView
from .geometry import Hold


class Flame:
    def __init__(self):
        self.unlocked = self.saw_open = self.active = False
        self.hold = Hold()
        self.last_seen = -1e9
        self.center = (0.0, 0.0)
        self.velocity = (0.0, 0.0)
        self.size = 0.0
        self.born = 0.0
        self.opacity = 0.0
        self.unlock_seconds = 0.0
        self.last_fist_seen = -1e9
        self.previous_fist = False


class Fire:
    def __init__(self, cfg=DEFAULTS):
        self.cfg = cfg
        self.hands = {s: Flame() for s in ("left", "right")}
        self.last_t = None

    def update(self, f):
        t, objects, events = f.timestamp, [], []
        dt = max(0.0, t - self.last_t) if self.last_t is not None else 0.0
        if self.last_t is not None and dt > self.cfg.max_gap:
            for flame in self.hands.values():
                flame.hold.clear()
                flame.unlock_seconds = 0.0
                flame.previous_fist = False
        self.last_t = t
        charging = 0
        for arm in f.arms:
            flame = self.hands[arm.side]
            fresh = arm.hand_valid and arm.shape_age <= self.cfg.gesture_max_age
            fraction = arm.openness if arm.openness is not None else (0.0 if arm.shape == Shape.FIST else 1.0)
            fist = fresh and arm.shape == Shape.FIST and fraction < 0.22
            partial_fist = fresh and arm.shape == Shape.FIST and 0.22 <= fraction < 0.38
            opened = fresh and arm.shape not in (Shape.UNKNOWN, Shape.FIST) and not fist
            if opened:
                flame.saw_open = True
            if not flame.unlocked:
                if fist and flame.saw_open:
                    if flame.previous_fist:
                        flame.unlock_seconds += dt
                    elif t - flame.last_fist_seen > self.cfg.fire_unlock_dropout:
                        flame.unlock_seconds = 0.0
                    flame.last_fist_seen = t
                    flame.previous_fist = True
                    charging += 1
                    if flame.unlock_seconds + 1e-9 >= self.cfg.fire_unlock:
                        flame.unlocked = True
                        events.append(("fire_unlock", (), 1.0))
                else:
                    flame.previous_fist = False
                    if partial_fist:
                        # A currently observed borderline fist pauses; it is not a tracking dropout.
                        flame.last_fist_seen = t
                    uncertain = not fresh or arm.shape == Shape.UNKNOWN or partial_fist
                    if not uncertain or (
                        not partial_fist and t - flame.last_fist_seen > self.cfg.fire_unlock_dropout
                    ):
                        flame.unlock_seconds = 0.0
                    elif flame.unlock_seconds > 0:
                        charging += 1
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
                raw_palm = arm.palm or arm.wrist
                if arm.shape != Shape.UNKNOWN:
                    target_size = max(12.0, arm.palm_scale * 0.8 or f.scale * 0.20) * max(
                        0.0, min(1.0, fraction)
                    )
                    flame.size = (
                        target_size
                        if flame.size <= 0.5 or dt <= 0
                        else flame.size + (target_size - flame.size) * (1.0 - math.exp(-dt * 18.0))
                    )
                # Levitate the flame clearly ABOVE the palm center so it never sticks to the hand!
                lev_y = max(18.0, flame.size * self.cfg.flame_levitation)
                target_center = (raw_palm[0], raw_palm[1] - lev_y)
                if flame.last_seen < -1e8 or dt <= 0 or dt > 0.25:
                    flame.center = target_center
                    flame.velocity = (0.0, 0.0)
                else:
                    k = 1.0 - math.exp(-dt * 22.0)
                    vx = (target_center[0] - flame.center[0]) / max(0.008, dt)
                    vy = (target_center[1] - flame.center[1]) / max(0.008, dt)
                    flame.velocity = (
                        0.65 * flame.velocity[0] + 0.35 * vx,
                        0.65 * flame.velocity[1] + 0.35 * vy,
                    )
                    flame.center = (
                        flame.center[0] + (target_center[0] - flame.center[0]) * k,
                        flame.center[1] + (target_center[1] - flame.center[1]) * k,
                    )
                flame.last_seen = t
            else:
                flame.velocity = (flame.velocity[0] * 0.85, flame.velocity[1] * 0.85)
            age = t - flame.last_seen
            fade = max(0.0, 1.0 - max(0.0, age - self.cfg.fire_loss_hold) / self.cfg.fire_loss_fade)
            flame.opacity = fade if flame.active else 0.0
            if age > self.cfg.fire_loss_hold + self.cfg.fire_loss_fade:
                flame.active = False
            if flame.active and flame.size > 0.5:
                objects.append(
                    EffectObject(4, flame.center, flame.size, t - flame.born, fade, velocity=flame.velocity)
                )
        ready = any(h.unlocked for h in self.hands.values())
        hint = (
            "圣焰悬浮于掌心之上；收拳逐渐收缩熄灭，翻掌朝下熄灭"
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
