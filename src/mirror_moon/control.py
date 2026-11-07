"""Robust continuous control; no palm-size or 2D-projection substitute for elbow depth."""

import math
import statistics
from collections import deque

from .geometry import smoothstep


class IntensityController:
    def __init__(self):
        self.samples = deque(maxlen=7)
        self.value = 0.0
        self.last_t = None
        self.last_good = None
        self.last_target = 0.0
        self.reliable = False

    def update(self, angle, now, bent=75.0, extended=160.0):
        dt = min(0.20, max(0.0, now - self.last_t)) if self.last_t is not None else 0.05
        self.last_t = now
        if angle is not None and math.isfinite(angle) and 20.0 <= angle <= 180.0:
            self.samples.append((now, angle))
            while self.samples and now - self.samples[0][0] > 0.32:
                self.samples.popleft()
            robust = statistics.median(a for _, a in self.samples)
            target = smoothstep((robust - bent) / max(25.0, extended - bent))
            self.last_good = now
            self.last_target = target
            self.reliable = True
        else:
            age = now - self.last_good if self.last_good is not None else 99.0
            target = self.last_target * max(0.0, 1.0 - max(0.0, age - 0.20) / 0.45)
            self.reliable = False
        if abs(target - self.value) < 0.025:
            if target in (0.0, 1.0):
                self.value = target
            return self.value
        alpha = 1.0 - math.exp(-dt / 0.17)
        proposed = self.value + alpha * (target - self.value)
        self.value += max(-2.2 * dt, min(1.8 * dt, proposed - self.value))
        self.value = max(0.0, min(1.0, self.value))
        if target == 0.0 and self.value < 0.012:
            self.value = 0.0
        return self.value
