from eki_walk.cli import build_parser


def test_parser():
    p = build_parser()
    a = p.parse_args(["import-raw", "--from", "../rail-gap-map"])
    assert a.command == "import-raw" and a.src == "../rail-gap-map"
    a = p.parse_args(["build", "--config", "configs/territory-tokyo.toml", "--from", "territory"])
    assert a.start == "territory"


def test_parser_fetch_and_combine():
    p = build_parser()
    a = p.parse_args(["fetch", "abr-town-11", "abr-town-pos-11"])
    assert a.keys == ["abr-town-11", "abr-town-pos-11"]
    a = p.parse_args(["combine", "--region", "tokyo", "--region", "saitama"])
    assert a.regions == ["tokyo", "saitama"]
