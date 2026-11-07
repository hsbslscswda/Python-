from dataclasses import dataclass, field
from enum import StrEnum

Point = tuple[float, float]
Point3 = tuple[float, float, float]


class Shape(StrEnum):
    OPEN = "OPEN"
    FIST = "FIST"
    PINCH = "PINCH"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


@dataclass(frozen=True)
class Arm:
    side: str
    shoulder: Point
    elbow: Point
    wrist: Point
    shape: Shape = Shape.UNKNOWN
    tracked: bool = False
    hand_valid: bool = False
    angle: float | None = None
    landmarks: tuple[Point, ...] = ()
    pose_confidence: float = 1.0
    elbow_visible: bool = True
    shape_age: float = 0.0
    wrist_confidence: float = 1.0
    pose_wrist: Point | None = None
    palm: Point | None = None
    normal: Point3 | None = None
    openness: float | None = None
    palm_scale: float = 0.0
    upper_valid: bool = False

    @property
    def source(self):
        if self.hand_valid and not self.upper_valid and self.pose_confidence <= 0:
            return "HAND_ONLY"
        return (
            "HAND_POSE"
            if self.hand_valid and self.tracked
            else "POSE_FALLBACK"
            if self.tracked
            else "UNKNOWN"
        )


@dataclass(frozen=True)
class Features:
    timestamp: float
    frame_id: int
    width: int
    height: int
    chest: Point
    scale: float
    arms: tuple[Arm, Arm]
    valid: bool = True
    reason: str = ""
    body_yaw: float | None = None
    people: tuple = ()  # Other detected people: (left, top, right, bottom, shoulder_width).

    def arm(self, side: str) -> Arm:
        return self.arms[0 if side == "left" else 1]


@dataclass(frozen=True)
class Event:
    event_id: int
    kind: str
    frame_id: int
    timestamp: float
    points: tuple[Point, ...] = ()
    strength: float = 0.0
    seed: int = 0
    image: object = field(default=None, repr=False, compare=False)
    folded: bool = False
    body_scale: float = 1.0


@dataclass(frozen=True)
class SpellView:
    mode: str = "circle"
    state: str = "OFF"
    intensity: float = 0.0
    visibility: float = 0.0
    migration: float = 0.0
    support: str | None = None
    caster: str | None = None
    center: Point = (0.0, 0.0)
    radius: float = 0.0
    mirror_angle: float = 0.0
    folded: bool = False
    hint: str = "一手握拳横在胸前，召唤星环"
    quality: str = "等待人物"
    control_reliable: bool = True
    objects: tuple = ()


@dataclass(frozen=True)
class EffectObject:
    """A projected, immutable effect bound to its tracking frame; depth is approximate."""

    kind: int  # 1 water, 2 flying water, 3 splash, 4 flame
    center: Point
    radius: float
    age: float = 0.0
    opacity: float = 1.0
    velocity: Point = (0.0, 0.0)
    depth: float = 1.0
    seed: float = 0.0
