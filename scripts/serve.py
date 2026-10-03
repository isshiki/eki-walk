"""Serve the current map locally without downloading or building anything."""

from __future__ import annotations

import argparse
import json
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8815)
    args = parser.parse_args()
    web = Path(__file__).resolve().parents[1] / "web"
    if not (web / "data" / "regions.json").is_file():
        parser.error("web/data/regions.json がありません。README のデータ作成手順を先に実行してください。")
    manifest = json.loads((web / "data" / "regions.json").read_text(encoding="utf-8"))
    required = [web / manifest["overview"]] if manifest.get("overview") else []
    for region in manifest["regions"]:
        required.extend(web / region["path"] / name for name in (
            "meta.json", "stations.json", "territories.geojson", "aoi.geojson",
            "far.geojson", "band.geojson", "lines.geojson", "places.json",
        ))
    missing = [str(path.relative_to(web)) for path in required if not path.is_file()]
    if missing:
        parser.error("画面用データが未完成です。全地域のビルドと combine の終了後に起動してください: " + ", ".join(missing))
    handler = partial(SimpleHTTPRequestHandler, directory=str(web))
    with ThreadingHTTPServer(("127.0.0.1", args.port), handler) as server:
        print(f"http://127.0.0.1:{args.port}/ (Ctrl+C で停止)", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
