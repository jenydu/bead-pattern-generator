"""Sync brand palettes from beadcolors and stage core/ + data/ into web/py for Pages."""
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT.parent / "beadcolors" / "raw"
DST = ROOT / "data" / "palettes"
WEB_PY = ROOT / "web" / "py"


def sync_palettes():
    if not SRC.is_dir():
        print(f"{SRC} not found, keeping existing data/palettes", file=sys.stderr)
        return
    DST.mkdir(parents=True, exist_ok=True)
    for f in sorted(SRC.glob("*.csv")):
        shutil.copy2(f, DST / f.name)
    lic = SRC.parent / "LICENSE"
    if lic.exists():
        shutil.copy2(lic, DST / "LICENSE-beadcolors")


def stage_web():
    """web/py mirrors the layout core/ expects: core/*.py and data/palettes/*.csv."""
    if WEB_PY.exists():
        shutil.rmtree(WEB_PY)
    shutil.copytree(ROOT / "core", WEB_PY / "core",
                    ignore=shutil.ignore_patterns("__pycache__"))
    shutil.copytree(DST, WEB_PY / "data" / "palettes")
    files = sorted(str(p.relative_to(WEB_PY)) for p in WEB_PY.rglob("*") if p.is_file())
    (WEB_PY / "manifest.json").write_text(json.dumps(files, indent=1))


if __name__ == "__main__":
    if "--no-sync" not in sys.argv:
        sync_palettes()
    stage_web()
    print("ok:", len(list(DST.glob("*.csv"))), "palettes")
