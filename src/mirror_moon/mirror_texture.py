"""Bounded Voronoi cells and CPU mirror texture matching the GL cut-corner mirror."""

import math

import cv2
import numpy as np

MIRROR_ASPECT = 0.68
MIRROR_OUTLINE = (
    (-0.68, -1.0),
    (0.68, -1.0),
    (1.0, -0.68),
    (1.0, 0.68),
    (0.68, 1.0),
    (-0.68, 1.0),
    (-1.0, 0.68),
    (-1.0, -0.68),
)


def _clip_half_plane(polygon, normal, offset):
    if len(polygon) == 0:
        return polygon
    out = []
    previous = polygon[-1]
    previous_inside = float(np.dot(previous, normal)) <= offset + 1e-9
    for current in polygon:
        current_inside = float(np.dot(current, normal)) <= offset + 1e-9
        if current_inside != previous_inside:
            delta = current - previous
            denom = float(np.dot(delta, normal))
            if abs(denom) > 1e-12:
                t = (offset - float(np.dot(previous, normal))) / denom
                out.append(previous + np.clip(t, 0.0, 1.0) * delta)
        if current_inside:
            out.append(current)
        previous, previous_inside = current, current_inside
    return np.asarray(out, dtype="f4") if out else np.zeros((0, 2), dtype="f4")


def mirror_cells(seed=7, count=48):
    """Partition the cut-corner mirror polygon into 48 deterministic Voronoi cells."""
    rng = np.random.default_rng(seed)
    angles = np.arange(count, dtype="f4") * (math.tau / ((1 + math.sqrt(5)) / 2))
    radii = np.sqrt((np.arange(count, dtype="f4") + 0.5) / count) * 0.86
    jitter = rng.normal(0.0, 0.045, (count, 2)).astype("f4")
    sites = np.stack((np.cos(angles) * radii, np.sin(angles) * radii), axis=1) + jitter
    sites = np.clip(sites, -0.88, 0.88)
    s = np.sum(np.abs(sites), axis=1)
    too_far = s > 1.50
    sites[too_far] *= (1.50 / s[too_far])[:, None]
    base = np.asarray(MIRROR_OUTLINE, dtype="f4")
    cells = []
    for i, site in enumerate(sites):
        poly = base
        for j, other in enumerate(sites):
            if i == j:
                continue
            normal = other - site
            offset = 0.5 * float(np.dot(other + site, normal))
            poly = _clip_half_plane(poly, normal, offset)
            if len(poly) < 3:
                break
        if len(poly) >= 3:
            cells.append(poly)
    return cells


def _smoothstep(edge0, edge1, x):
    t = np.clip((x - edge0) / (edge1 - edge0), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def mirror_texture(rgb, center, radius, angle, folded, body_scale=120.0, timestamp=0.0):
    """Sample a frozen mirror patch with the same cut-corner/fold geometry as GL."""
    del angle, body_scale  # Frozen texture lives in mirror-local coordinates.
    r = float(max(4.0, radius))
    width = int(np.clip(round(r * 2.0), 8, 1024))
    height = int(np.clip(round(r * 2.0 * MIRROR_ASPECT), 8, 768))
    x, y = np.meshgrid(np.linspace(-1, 1, width, dtype="f4"), np.linspace(-1, 1, height, dtype="f4"))
    sdf = np.maximum(np.maximum(np.abs(x) - 1, np.abs(y) - 1), (np.abs(x) + np.abs(y) - 1.68) * 0.70710678)
    u, v = x * 0.5 + 0.5, y * 0.5 + 0.5
    facet = np.zeros_like(x)
    t = timestamp % 4096
    if folded:
        kx, ky = x * 0.88, y * 0.88
        length = np.hypot(kx, ky)
        sector = np.pi / 6
        a_raw = np.arctan2(ky, kx) + t * 0.18
        local_angle = a_raw % (2 * sector) - sector
        # Clean peripheral frost-crystal rim shimmer only near the outer edge (no wireframe lines in center!)
        facet += _smoothstep(0.76, 0.96, length) * (0.5 + 0.5 * np.cos(local_angle * 6.0)) * 0.18
        u = np.clip(np.cos(np.abs(local_angle)) * length * 0.72 + 0.5, 0.02, 0.98)
        v = np.clip(np.sin(np.abs(local_angle)) * length * 0.72 + 0.5, 0.02, 0.98)
    bevel = _smoothstep(-0.12, -0.008, sdf) * (1 - _smoothstep(-0.008, 0.012, sdf))
    norm = np.hypot(x + 1e-4, y + 1e-4)
    nx, ny = (x + 1e-4) / norm, (y + 1e-4) / norm
    channels = []
    for channel, factor in enumerate((0.45, 0.15, -0.35)):
        sx = center[0] + (u - 0.5 + nx * bevel * 0.014 * factor) * r * 2
        sy = center[1] + (v - 0.5 + ny * bevel * 0.014 * factor) * r * 2 * MIRROR_ASPECT
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
    # Pure obsidian-silver & moonlit-sapphire crystal glass reflection
    reflected = reflected * (0.86, 0.93, 1.05) + (0.015, 0.032, 0.065)
    vignette = _smoothstep(0.32, 0.98, norm)
    reflected *= 1.0 - vignette[:, :, None] * 0.22
    phase = np.arctan2(y, x) * 24 + t * 0.4
    astral_etch = _smoothstep(0.45, 0.95, 0.5 + 0.5 * np.cos(phase)) * bevel
    sweep_pos = x * 0.65 + y * 0.75 - np.sin(t * 0.7) * 0.35
    sweep = np.exp(-((sweep_pos * 5.2) ** 2)) * 0.15
    sweep += np.exp(-(((sweep_pos - 0.16) * 14) ** 2)) * 0.22
    reflected += astral_etch[:, :, None] * np.array((0.88, 0.78, 0.58)) * 0.32
    reflected += (sweep + bevel * 0.22)[:, :, None] * np.array((0.78, 0.88, 0.98))
    reflected += facet[:, :, None] * np.array((0.82, 0.92, 1.00))
    result = (np.clip(reflected, 0, 1) * 255).astype("uint8")
    result.flags.writeable = False
    return result
