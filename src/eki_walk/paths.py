"""Local data locations (all under the git-ignored data/ directory)."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
INTERIM = DATA / "interim"
BUILD = DATA / "build"
WEB = ROOT / "web"
