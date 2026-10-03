import hashlib
import json

import pytest

from eki_walk.raw import import_raw


def setup(tmp_path, content=b"pbf-bytes", recorded=None):
    src, dst = tmp_path / "src", tmp_path / "dst"
    (src / "data" / "raw").mkdir(parents=True)
    (dst / "configs").mkdir(parents=True)
    (src / "data" / "raw" / "a.pbf").write_bytes(content)
    sha = recorded or hashlib.sha256(content).hexdigest()
    (src / "data" / "raw" / "manifest.json").write_text(
        json.dumps({"osm": {"url": "https://example/a.pbf", "file": "a.pbf", "bytes": len(content), "sha256": sha}}),
        encoding="utf-8",
    )
    (dst / "configs" / "sources.toml").write_text('[osm]\nurl = "https://example/a.pbf"\nfile = "a.pbf"\n', encoding="utf-8")
    return src, dst


def test_import_copies_and_records(tmp_path):
    src, dst = setup(tmp_path)
    man = import_raw(src, dst)
    assert (dst / "data" / "raw" / "a.pbf").read_bytes() == b"pbf-bytes"
    assert man["osm"]["copied_from"] == "rail-gap-map data/raw"
    saved = json.loads((dst / "data" / "raw" / "manifest.json").read_text(encoding="utf-8"))
    assert saved["osm"]["sha256"] == hashlib.sha256(b"pbf-bytes").hexdigest()


def test_import_rejects_sha_mismatch(tmp_path):
    src, dst = setup(tmp_path, recorded="0" * 64)
    with pytest.raises(ValueError, match="SHA-256"):
        import_raw(src, dst)
    assert not (dst / "data" / "raw" / "a.pbf").exists()
