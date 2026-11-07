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
        a = np.abs((np.arctan2(y, x) + angle * 0.65 + np.pi / 6) % (np.pi / 3) - np.pi / 6)
        sx, sy = np.cos(a) * length, np.sin(a) * length
    sx = -sx
    ripple = np.sin(length * 0.045 - (timestamp % 4096) * 3.2) * 2.5
    norm = np.hypot(x + 0.001, y + 0.001)
    sx += (x + 0.001) / norm * ripple
    sy += (y + 0.001) / norm * ripple
    shift_x, shift_y = x / r * shoulder * 0.016, y / (r * 0.66) * shoulder * 0.016
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
    result = np.stack(channels, axis=-1) * (0.86, 0.97, 1.12) + (0.02, 0.05, 0.09)
    if folded:
        fa = np.arctan2(y, x) + angle * 0.5
        facet = np.sin(fa * 3.0) * length
        rosette = length - r * (0.42 + 0.08 * np.cos(fa * 12.0))

        def sharp_line(values, width):
            t = np.clip((np.abs(values) - width * 0.2) / (width * 1.2), 0, 1)
            return 1 - t * t * (3 - 2 * t) + np.exp(-np.abs(values) / (width * 2.2)) * 0.45

        engraving = sharp_line(facet, 1.5) * 0.70 + sharp_line(rosette, 1.6) * 0.85
        result += engraving[:, :, None] * np.array((0.82, 0.88, 1.0))
    d = np.maximum(np.abs(x) - r, np.abs(y) - r * 0.66)
    fresnel = np.clip(1 + d / max(14.0, r * 0.38), 0, 1) ** 2.8
    result += fresnel[:, :, None] * np.array((0.45, 0.82, 1.0)) * 0.52
    result = (np.clip(result, 0, 1) * 255).astype("uint8")
    result.flags.writeable = False
    return result
