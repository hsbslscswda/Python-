"""Geometry has no Qt, camera, GPU or MediaPipe dependency."""

import math

from .domain import Point, Point3


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def angle3(a: Point3, b: Point3, c: Point3) -> float | None:
    u, v = tuple(x - y for x, y in zip(a, b)), tuple(x - y for x, y in zip(c, b))
    lengths = math.sqrt(sum(x * x for x in u) * sum(x * x for x in v))
    if lengths < 1e-9:
        return None
    return math.degrees(math.acos(max(-1.0, min(1.0, sum(x * y for x, y in zip(u, v)) / lengths))))


def segment_distance(p: Point, a: Point, b: Point) -> tuple[float, float]:
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = dx * dx + dy * dy
    if n < 1e-9:
        return distance(p, a), -1.0
    t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / n
    return distance(p, (a[0] + max(0.0, min(1.0, t)) * dx, a[1] + max(0.0, min(1.0, t)) * dy)), t


def crossing(a: Point, b: Point, c: Point, d: Point) -> bool:
    def cross(u, v):
        return u[0] * v[1] - u[1] * v[0]

    u, v, w = (b[0] - a[0], b[1] - a[1]), (d[0] - c[0], d[1] - c[1]), (c[0] - a[0], c[1] - a[1])
    det = cross(u, v)
    if abs(det) < 1e-8:
        return False
    t, s = cross(w, v) / det, cross(w, u) / det
    ang = angle3((u[0], u[1], 0.0), (0.0, 0.0, 0.0), (v[0], v[1], 0.0))
    return 0 <= t <= 1 and 0 <= s <= 1 and ang is not None and 35 <= ang <= 145


def blade_combo(a, b, c, d):
    if crossing(a, b, c, d):
        return "cross"
    u, v = (b[0] - a[0], b[1] - a[1], 0.0), (d[0] - c[0], d[1] - c[1], 0.0)
    angle = angle3(u, (0.0, 0.0, 0.0), v)
    return "double" if angle is not None and angle >= 150.0 else "slash"


def smoothstep(x: float) -> float:
    x = max(0.0, min(1.0, x))
    return x * x * (3.0 - 2.0 * x)


class OneEuro:
    """Original implementation of the published adaptive first-order filter equations."""

    def __init__(self, cutoff=1.5, beta=0.02):
        self.cutoff, self.beta = cutoff, beta
        self.last_t = None
        self.raw = self.value = self.derivative = 0.0

    def __call__(self, x: float, t: float) -> float:
        if self.last_t is None or t <= self.last_t or t - self.last_t > 0.3:
            self.last_t, self.raw, self.value, self.derivative = t, x, x, 0.0
            return x
        dt = t - self.last_t

        def alpha(c):
            return 1.0 / (1.0 + 1.0 / (2.0 * math.pi * c * dt))

        dx = (x - self.raw) / dt
        self.derivative += alpha(1.0) * (dx - self.derivative)
        self.value += alpha(self.cutoff + self.beta * abs(self.derivative)) * (x - self.value)
        self.last_t, self.raw = t, x
        return self.value


class Hold:
    def __init__(self):
        self.starts: dict[str, float] = {}

    def ready(self, key: str, condition: bool, now: float, duration: float) -> bool:
        if not condition:
            self.starts.pop(key, None)
            return False
        return now - self.starts.setdefault(key, now) >= duration - 1e-8

    def clear(self):
        self.starts.clear()


def recent_samples(history, now, window=0.16, max_age=0.35):
    """Keep a preceding valid observation when a slow camera exceeds the nominal window."""
    valid = [sample for sample in history if 0 <= now - sample[0] <= max_age]
    recent = [sample for sample in valid if now - sample[0] <= window]
    if len(recent) < 2:
        recent = valid[-2:]
    return recent


def fitted_velocity(history):
    """Least-squares velocity, in the input coordinate unit per second."""
    if len(history) < 2:
        return (0.0, 0.0)
    ts = [item[0] - history[0][0] for item in history]
    mean_t = sum(ts) / len(ts)
    denominator = sum((t - mean_t) ** 2 for t in ts)
    if denominator < 1e-8:
        return (0.0, 0.0)
    return tuple(
        sum((t - mean_t) * item[1][axis] for t, item in zip(ts, history)) / denominator for axis in (0, 1)
    )


def arm_lowered(arm, frame):
    """Visible elbow and downward wrist estimate suffice when the hand is below the image."""
    return (
        arm.elbow_visible
        and arm.elbow[1] > arm.shoulder[1] + 0.16 * frame.scale
        and (
            arm.wrist[1] > frame.chest[1] + 0.65 * frame.scale
            or (
                not arm.hand_valid
                and arm.upper_valid
                and arm.elbow[1] > frame.chest[1] + 0.35 * frame.scale
                and arm.wrist[1] >= arm.elbow[1] - 0.1 * frame.scale
            )
        )
    )


def wide_casting_span(frame) -> bool:
    """True when arms are in a wide vertical (one up, one down) or horizontal (left-right) opening pose."""
    left, right = frame.arms
    s = max(1.0, frame.scale)
    horiz_span = (
        abs(left.wrist[0] - right.wrist[0]) > 1.25 * s or abs(left.elbow[0] - right.elbow[0]) > 1.15 * s
    )
    vert_span = (
        min(left.wrist[1], right.wrist[1]) < frame.chest[1] + 0.15 * s
        and abs(left.wrist[1] - right.wrist[1]) > 0.45 * s
    ) or (
        min(left.elbow[1], right.elbow[1]) < min(left.shoulder[1], right.shoulder[1]) + 0.08 * s
        and abs(left.elbow[1] - right.elbow[1]) > 0.25 * s
    )
    return horiz_span or vert_span


def both_arms_dropped_out(frame) -> bool:
    """True when body is tracked, arms are NOT in a wide opening pose, and both hands hang down out of view."""
    if not frame.valid or wide_casting_span(frame):
        return False
    return all(
        not a.hand_valid
        and (a.upper_valid or a.tracked)
        and arm_lowered(a, frame)
        and a.wrist[1] >= frame.height
        for a in frame.arms
    )
