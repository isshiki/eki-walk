from pathlib import Path

from eki_walk.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_load_territory_config():
    c = load_config(ROOT / "configs" / "territory-tokyo.toml")
    assert c.region == "tokyo"
    assert c.limit_m == 1200
    assert c.band_m == 240
    assert c.merge_same_name_m == 600
    assert c.chunk_cells == 64
    assert c.min_island_cells == 64 and c.min_hole_m2 == 100000


def test_trial_config_uses_oizumi_region():
    assert load_config(ROOT / "configs" / "territory-oizumi.toml").region == "oizumi-test"


def test_region_configs_load_with_ekiwalk():
    from ekiwalk.config import load_region

    r = load_region("tokyo", root=ROOT)
    assert r.cell_m == 25 and r.access_radius_m == 100 and r.max_offroad_m == 300
    assert r.build_dir == ROOT / "data" / "build" / "tokyo"


def test_edge_simplification_is_shared_by_the_metropolitan_regions():
    names = ["tokyo", "saitama", "chiba", "kanagawa"]
    for n in names:
        c = load_config(ROOT / "configs" / f"territory-{n}.toml")
        assert c.edge_regions == tuple(names) and c.edge_simplify_m == 5
    trial = load_config(ROOT / "configs" / "territory-oizumi.toml")
    assert trial.edge_regions == () and trial.edge_simplify_m == 0
