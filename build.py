"""Sync brand palettes from beadcolors and stage core/ + data/ into web/py for Pages."""
import json
import re
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SRC = ROOT.parent / "beadcolors" / "raw"
DST = ROOT / "data" / "palettes"
WEB_PY = ROOT / "web" / "py"


# MARD "basic" chart: series A-H and M (221 codes). The code list matches the 221-color
# palette in github.com/Jett-Wu/Perler_Beads_Generator (MIT); RGB values stay beadcolors'.
MARD_221 = re.compile(r"[A-HM]\d+$")


def sync_palettes():
    if not SRC.is_dir():
        print(f"{SRC} not found, keeping existing data/palettes", file=sys.stderr)
        return
    DST.mkdir(parents=True, exist_ok=True)
    for old in DST.glob("*.csv"):
        old.unlink()
    for f in sorted(SRC.glob("*.csv")):
        if f.stem == "mard":
            continue  # shipped as mard_291 / mard_221
        shutil.copy2(f, DST / f.name)
    rows = (SRC / "mard.csv").read_text(encoding="utf-8").splitlines()
    (DST / "mard_291.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    basic = [r for r in rows if MARD_221.match(r.split(",")[0])]
    (DST / "mard_221.csv").write_text("\n".join(basic) + "\n", encoding="utf-8")
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
