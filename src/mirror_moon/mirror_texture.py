"""Bounded CPU equivalent of the mirror shader's image mapping, also for frozen shards."""

import cv2
import numpy as np


def mirror_texture(rgb, center, radius, angle, folded, shoulder, timestamp):
    r = max(4.0, radius)
    width, height = max(8, min(1024, round(r * 2))), max(8, min(768, round(r * 1.32)))
    x, y = np.meshgrid(
        np.linspace(-r, r, width, dtype="f4"), np.linspace(-r * 0.66, r * 0.66, height, dtype="f4")
    )
    length = np.hypot(x, y)
    sx, sy = x.copy(), y.copy()
    if folded:
        a = np.abs((np.arctan2(y, x) + angle * 0.5 + np.pi / 6) % (np.pi / 3) - np.pi / 6)
        sx, sy = np.cos(a) * length, np.sin(a) * length
    sx = -sx
    ripple = np.sin(length * 0.045 - (timestamp % 4096) * 3.2) * 2.5
    norm = np.hypot(x + 0.001, y + 0.001)
    sx += (x + 0.001) / norm * ripple
    sy += (y + 0.001) / norm * ripple
    shift_x, shift_y = x / r * shoulder * 0.015, y / (r * 0.66) * shoulder * 0.015
    channels = []
    for channel, factor in enumerate((1.0, 0.0, -1.0)):
        values = cv2.remap(
            rgb[:, :, channel],
            (center[0] + sx + factor * shift_x).astype("f4"),
            (center[1] + sy + factor * shift_y).astype("f4"),
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        channels.append(values.astype("f4") / 255.0)
    result = np.stack(channels, axis=-1) * (0.84, 0.97, 1.10) + (0.02, 0.05, 0.09)
    if folded:
        facet = np.sin(np.arctan2(y, x) * 3.0) * length
        result += np.exp(-((facet / 1.8) ** 2))[:, :, None] * np.array((0.55, 0.90, 1.0)) * 0.65
    d = np.maximum(np.abs(x) - r, np.abs(y) - r * 0.66)
    fresnel = np.clip(1 + d / max(12.0, r * 0.35), 0, 1) ** 3
    result += fresnel[:, :, None] * np.array((0.35, 0.78, 1.0)) * 0.42
    result = (np.clip(result, 0, 1) * 255).astype("uint8")
    result.flags.writeable = False
    return result
