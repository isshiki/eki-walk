"""Build all four regions, then combine them; no data downloads."""

from __future__ import annotations

import argparse

from ekiwalk import admin
from ekiwalk.config import load_region
from ekiwalk.fetch import raw_path

from eki_walk import paths, pipeline
from eki_walk.config import load_config
from eki_walk.territory.combine import combine

REGIONS = ("tokyo", "saitama", "chiba", "kanagawa")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--from", dest="start", choices=pipeline.STEPS, default="network")
    parser.add_argument("--dry-run", action="store_true", help="show the steps without changing data")
    args = parser.parse_args()
    configs = [load_config(paths.ROOT / "configs" / f"territory-{name}.toml") for name in REGIONS]
    # On a fresh build, every admin boundary must exist before the first territory step.
    if pipeline.STEPS.index(args.start) <= pipeline.STEPS.index("admin"):
        for name in REGIONS:
            print(f"prepare admin: {name}", flush=True)
            if not args.dry_run:
                region = load_region(name, root=paths.ROOT)
                admin.run(region, [raw_path(paths.ROOT, f"n03-{c}") for c in region.n03_prefectures])
    for cfg in configs:
        print(f"build: {cfg.region} from {args.start}", flush=True)
        if not args.dry_run:
            pipeline.run_build(cfg, args.start)
    print("combine: " + ", ".join(REGIONS), flush=True)
    if not args.dry_run:
        combine(paths.WEB / "data", list(REGIONS), max_colors=6)


if __name__ == "__main__":
    main()
