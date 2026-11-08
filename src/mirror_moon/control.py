"""Robust continuous control; no palm-size or 2D-projection substitute for elbow depth."""

import math
import statistics
from collections import deque

from .config import DEFAULTS
from .geometry import smoothstep


def valid_endpoints(bent, extended):
    return (
        all(isinstance(x, (float, int)) and math.isfinite(x) for x in (bent, extended))
        and 20 <= bent
        and bent + 15 <= extended <= 180
    )


def fit_calibration(bent_samples, extended_samples):
    if min(len(bent_samples), len(extended_samples)) < 12:
        return None
    bent, extended = statistics.median(bent_samples), statistics.median(extended_samples)
    noise = max(
        statistics.quantiles(x, n=10)[-1] - statistics.quantiles(x, n=10)[0]
        for x in (bent_samples, extended_samples)
    )
    return (bent, extended) if valid_endpoints(bent, extended) and extended - bent >= 1.8 * noise else None


class IntensityController:
    def __init__(self):
        self.samples = deque(maxlen=7)
        self.value = 0.0
        self.last_t = None
        self.last_good = None
        self.last_target = 0.0
        self.reliable = False
        self.robust_angle = None
        self.movement_sign = self.movement_count = 0
        self.fast_until = -1e9

    def update(self, angle, now, bent=75.0, extended=134.0):
        dt = min(0.20, max(0.0, now - self.last_t)) if self.last_t is not None else 0.05
        self.last_t = now
        if angle is not None and math.isfinite(angle) and 20.0 <= angle <= 180.0:
            self.samples.append((now, angle))
            while self.samples and now - self.samples[0][0] > 0.32:
                self.samples.popleft()
            delta = angle - self.robust_angle if self.robust_angle is not None else 0.0
            sign = 1 if delta > 12.0 else -1 if delta < -12.0 else 0
            self.movement_count = (
                self.movement_count + 1 if sign and sign == self.movement_sign else int(bool(sign))
            )
            self.movement_sign = sign
            if self.movement_count >= 2:
                self.fast_until = now + 0.35
            moving = now <= self.fast_until
            samples = list(self.samples)[-3:] if moving else self.samples
            robust = statistics.median(a for _, a in samples)
            self.robust_angle = robust
            target = smoothstep((robust - bent) / max(18.0, extended - bent))
            self.last_good = now
            self.last_target = target
            self.reliable = True
        else:
            age = now - self.last_good if self.last_good is not None else 99.0
            target = self.last_target * max(
                0.0, 1.0 - max(0.0, age - DEFAULTS.control_hold) / DEFAULTS.control_fade
            )
            self.reliable = False
            moving = False
        if abs(target - self.value) < (0.025 if moving else 0.045):
            if target in (0.0, 1.0):
                self.value = target
            return self.value
        alpha = 1.0 - math.exp(-dt / (0.050 if moving else 0.24))
        proposed = self.value + alpha * (target - self.value)
        slew = 4.2 if moving else 2.0
        self.value += max(-slew * dt, min(slew * dt, proposed - self.value))
        self.value = max(0.0, min(1.0, self.value))
        if target == 0.0 and self.value < 0.015:
            self.value = 0.0
        return self.value
