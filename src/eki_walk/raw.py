"""Reuse raw files that rail-gap-map already downloaded (no new download), checking SHA-256."""

from __future__ import annotations

import hashlib
import json
import shutil
import tomllib
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def load_sources(root: Path) -> dict:
    return tomllib.loads((root / "configs" / "sources.toml").read_text(encoding="utf-8"))


def import_raw(src_root: Path, dst_root: Path, keys=None) -> dict:
    """Copy data/raw/<file> for each source key from src_root, verified against src_root's manifest."""
    sources = load_sources(dst_root)
    keys = list(keys or sources)
    src_manifest = json.loads((src_root / "data" / "raw" / "manifest.json").read_text(encoding="utf-8"))
    dst_dir = dst_root / "data" / "raw"
    dst_dir.mkdir(parents=True, exist_ok=True)
    man_path = dst_dir / "manifest.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {}
    for key in keys:
        entry = src_manifest.get(key)
        if entry is None:
            raise KeyError(f"rail-gap-map の取得記録に {key} がありません")
        file = sources[key]["file"]
        if entry["file"] != file:
            raise ValueError(f"{key}: ファイル名が違います ({entry['file']} / {file})")
        dst = dst_dir / file
        if not dst.exists() or sha256_file(dst) != entry["sha256"]:
            shutil.copyfile(src_root / "data" / "raw" / file, dst)
        if sha256_file(dst) != entry["sha256"]:
            dst.unlink()
            raise ValueError(f"{file}: SHA-256 が取得記録と一致しません")
        manifest[key] = {
            **entry,
            "copied_from": "rail-gap-map data/raw",
            "copied_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
