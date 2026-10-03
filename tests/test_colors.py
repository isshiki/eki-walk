import numpy as np
import pytest

from eki_walk.territory.colors import dsatur, raster_adjacency


def test_adjacency_includes_diagonals_and_skips_blank():
    lab = np.array([[0, 1], [2, -1]])
    assert raster_adjacency(lab) == {(0, 1), (0, 2), (1, 2)}


def test_dsatur_gives_neighbours_different_colours():
    lab = np.array([[0, 0, 1, 1], [2, 2, 3, 3], [4, 4, 5, 5]])
    pairs = raster_adjacency(lab)
    col = dsatur(range(6), pairs, max_colors=6)
    assert all(col[a] != col[b] for a, b in pairs)
    assert max(col.values()) < 4


def test_dsatur_raises_when_too_few_colours():
    pairs = {(a, b) for a in range(5) for b in range(5) if a < b}  # K5
    with pytest.raises(ValueError):
        dsatur(range(5), pairs, max_colors=4)
