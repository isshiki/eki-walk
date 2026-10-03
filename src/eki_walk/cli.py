"""eki-walk import-raw --from ../rail-gap-map | eki-walk build --config configs/territory-tokyo.toml"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eki_walk import paths, pipeline
from eki_walk.config import load_config
from eki_walk.raw import import_raw


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="eki-walk")
    sub = p.add_subparsers(dest="command", required=True)
    i = sub.add_parser("import-raw", help="copy raw files from a local rail-gap-map checkout (SHA-256 checked)")
    i.add_argument("--from", dest="src", required=True)
    i.add_argument("keys", nargs="*")
    f = sub.add_parser("fetch", help="download raw files listed in configs/sources.toml (ask the user first)")
    f.add_argument("keys", nargs="+")
    c = sub.add_parser("combine", help="shared colours across regions and data/regions.json")
    c.add_argument("--region", dest="regions", action="append", required=True)
    c.add_argument("--max-colors", type=int, default=6)
    c.add_argument("--manifest", default="regions.json", help="file name under web/data (e.g. regions-oizumi.json for a trial)")
    b = sub.add_parser("build", help="run ekiwalk steps, then the territory step")
    b.add_argument("--config", required=True)
    b.add_argument("--from", dest="start", choices=pipeline.STEPS, default="network")
    return p


def main(argv=None) -> None:
    a = build_parser().parse_args(argv)
    if a.command == "import-raw":
        man = import_raw(Path(a.src).resolve(), paths.ROOT, a.keys or None)
        print(json.dumps({k: {"file": v["file"], "bytes": v["bytes"]} for k, v in man.items()}, ensure_ascii=False, indent=2))
    elif a.command == "fetch":
        from ekiwalk.fetch import download

        from eki_walk.raw import load_sources

        sources = load_sources(paths.ROOT)
        for key in a.keys:
            print(key, json.dumps(download(paths.ROOT, key, sources[key]), ensure_ascii=False))
    elif a.command == "combine":
        from eki_walk.territory.combine import combine

        out = combine(paths.WEB / "data", a.regions, a.max_colors, manifest_name=a.manifest)
        print(json.dumps({"colours": max(out["colors"].values()) + 1, "edges": out["edges"], "regions": [r["name"] for r in out["regions"]]}))
    elif a.command == "build":
        pipeline.run_build(load_config(a.config), a.start)


if __name__ == "__main__":
    main()
