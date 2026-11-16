from pathlib import Path
import yaml

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"
RAW = DATA / "raw"
PARQ = DATA / "parquet"
DER = DATA / "derived"
WEB_DATA = ROOT / "web" / "public" / "data"


def load_config(path=None):
    p = Path(path) if path else ROOT / "configs" / "default.yaml"
    with open(p, encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_yaml(rel):
    with open(ROOT / rel, encoding="utf-8") as f:
        return yaml.safe_load(f)


def ensure_dirs():
    for d in (RAW, PARQ, DER, WEB_DATA):
        d.mkdir(parents=True, exist_ok=True)
