"""Geometry/frozen-content checks; no camera or claims of human acceptance."""

import numpy as np

from mirror_moon.domain import Event
from mirror_moon.mirror_texture import MIRROR_OUTLINE, mirror_cells
from mirror_moon.render import shard_mesh


def area(polygon):
    return (
        abs(np.sum(polygon[:, 0] * np.roll(polygon[:, 1], -1) - polygon[:, 1] * np.roll(polygon[:, 0], -1)))
        * 0.5
    )


def test_voronoi_cells_cover_cut_corner_mirror_without_gaps_or_unbounded_vertices():
    cells = mirror_cells(17)
    assert 1 <= len(cells) <= 48
    assert abs(sum(area(p) for p in cells) - area(np.array(MIRROR_OUTLINE))) < 1e-5
    for cell in cells:
        assert 3 <= len(cell) <= 56 and np.isfinite(cell).all()
        assert np.max(abs(cell)) <= 1.00001
        assert np.max(np.sum(abs(cell), axis=1)) <= 1.68001
    assert any(len(cell) > 4 for cell in cells)
    assert all(np.array_equal(a, b) for a, b in zip(cells, mirror_cells(17)))


def test_frozen_shard_uvs_stay_inside_the_same_mirror_and_are_seeded():
    event = Event(1, "shatter", 2, 3.0, ((300.0, 200.0), (120.0, 0.8)), seed=19)
    mesh = shard_mesh(event, (240, 163))
    assert mesh.shape[1] == 6 and len(mesh) % 3 == 0 and np.isfinite(mesh).all()
    uv = mesh[:, 2:4]
    assert np.min(uv) >= 0 and np.max(uv) <= 1
    assert np.max(np.sum(abs(uv * 2 - 1), axis=1)) <= 1.68001
    triangles = uv.reshape(-1, 3, 2)
    assert abs(sum(area(p) for p in triangles) - area(np.array(MIRROR_OUTLINE)) / 4) < 1e-5
    assert np.array_equal(mesh, shard_mesh(event, (240, 163)))
