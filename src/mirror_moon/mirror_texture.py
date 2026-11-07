"""Bounded CPU mirror sampling shared by compatibility rendering and frozen shards."""

import cv2
import numpy as np

MIRROR_ASPECT = 0.68
MIRROR_OUTLINE = (
    (1, 0.68),
    (0.68, 1),
    (-0.68, 1),
    (-1, 0.68),
    (-1, -0.68),
    (-0.68, -1),
    (0.68, -1),
    (1, -0.68),
)


def _smoothstep(low, high, value):
    t = np.clip((value - low) / (high - low), 0, 1)
    return t * t * (3 - 2 * t)


def mirror_cells(seed):
    """48 jittered Voronoi cells, clipped to the same cut-corner mirror boundary."""
    rng = np.random.default_rng(seed)
    sites = np.array(
        [
            (
                (x + 0.5 + rng.uniform(-0.30, 0.30)) / 8 * 2 - 1,
                (y + 0.5 + rng.uniform(-0.30, 0.30)) / 6 * 2 - 1,
            )
            for y in range(6)
            for x in range(8)
        ]
    )
    cells = []
    for i, site in enumerate(sites):
        polygon = [np.array(p, dtype="f8") for p in MIRROR_OUTLINE]
        for j, other in enumerate(sites):
            if i == j:
                continue
            normal = other - site
            offset = (np.dot(other, other) - np.dot(site, site)) * 0.5
            clipped = []
            for a, b in zip(polygon, polygon[1:] + polygon[:1]):
                da, db = np.dot(a, normal) - offset, np.dot(b, normal) - offset
                if da <= 1e-10:
                    clipped.append(a)
                if (da < 0) != (db < 0):
                    clipped.append(a + (b - a) * (da / (da - db)))
            polygon = clipped
            if len(polygon) < 3:
                break
        if len(polygon) >= 3:
            cells.append(np.asarray(polygon, dtype="f4"))
    return tuple(cells)


def mirror_texture(rgb, center, radius, angle, folded, shoulder, timestamp):
    """Match the GL mirror's full-opacity interior before its frame/shard animation."""
    r = max(4.0, radius)
    width = max(8, min(1024, round(r * 2)))
    height = max(8, min(768, round(r * 2 * MIRROR_ASPECT)))
    x, y = np.meshgrid(np.linspace(-1, 1, width, dtype="f4"), np.linspace(-1, 1, height, dtype="f4"))
    sdf = np.maximum(np.maximum(np.abs(x) - 1, np.abs(y) - 1), (np.abs(x) + np.abs(y) - 1.68) * 0.70710678)
    u, v = x * 0.5 + 0.5, y * 0.5 + 0.5
    facet = np.zeros_like(x)
    t = timestamp % 4096
    if folded:
        kx, ky = x * 0.88, y * 0.88
        length = np.hypot(kx, ky)
        sector = np.pi / 6
        local_angle = (np.arctan2(ky, kx) + t * 0.18) % (2 * sector) - sector
        facet += (1 - _smoothstep(0, 0.006, np.abs(np.abs(local_angle) - sector) * length)) * 0.55
        facet += (1 - _smoothstep(0, 0.006, np.abs(length - 0.54))) * 0.48
        u = np.clip(np.cos(np.abs(local_angle)) * length * 0.72 + 0.5, 0.02, 0.98)
        v = np.clip(np.sin(np.abs(local_angle)) * length * 0.72 + 0.5, 0.02, 0.98)
    bevel = _smoothstep(-0.12, -0.008, sdf) * (1 - _smoothstep(-0.008, 0.012, sdf))
    norm = np.hypot(x + 1e-4, y + 1e-4)
    nx, ny = (x + 1e-4) / norm, (y + 1e-4) / norm
    channels = []
    for channel, factor in enumerate((1.0, 0.35, -0.75)):
        sx = center[0] + (u - 0.5 + nx * bevel * 0.02 * factor) * r * 2
        sy = center[1] + (v - 0.5 + ny * bevel * 0.02 * factor) * r * 2 * MIRROR_ASPECT
        # GL normalized LINEAR coordinates address texel centers at n + 0.5.
        sx = np.clip(sx, rgb.shape[1] * 0.002, rgb.shape[1] * 0.998) - 0.5
        sy = np.clip(sy, rgb.shape[0] * 0.002, rgb.shape[0] * 0.998) - 0.5
        sample = cv2.remap(
            rgb[:, :, channel],
            sx.astype("f4"),
            sy.astype("f4"),
            cv2.INTER_LINEAR,
            borderMode=cv2.BORDER_REPLICATE,
        )
        channels.append(sample.astype("f4") / 255.0)
    reflected = np.stack(channels, axis=-1)
    reflected = reflected * (0.991, 0.9982, 1.0108) + (0.0036, 0.009, 0.0198)
    phase = np.arctan2(y, x) * 4 + t * 0.6
    rainbow = 0.5 + 0.5 * np.cos(phase[:, :, None] + np.array((0, 2.094, 4.188)))
    sweep_pos = x * 0.65 + y * 0.75 - np.sin(t * 0.7) * 0.35
    sweep = np.exp(-((sweep_pos * 4.8) ** 2)) * 0.24
    sweep += np.exp(-(((sweep_pos - 0.16) * 12) ** 2)) * 0.32
    reflected += rainbow * bevel[:, :, None] * 0.38
    reflected += (sweep + bevel * 0.28)[:, :, None] * np.array((0.92, 0.97, 1.0))
    reflected += facet[:, :, None] * np.array((0.94, 0.84, 0.64))
    result = (np.clip(reflected, 0, 1) * 255).astype("uint8")
    result.flags.writeable = False
    return result
