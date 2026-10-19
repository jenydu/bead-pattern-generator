# bead-pattern-generator

Upload pixel art, get a printable bead chart in a chosen brand's colors (MARD, Perler, Hama, Artkal, ...).
Python (numpy + Pillow) runs in the browser through Pyodide; there is no server. See `ARCHITECTURE.md`.

## Run locally

```
pip install numpy pillow pytest
python build.py                 # syncs ../beadcolors/raw, stages web/py
python -m http.server -d web    # open http://localhost:8000
python cli.py image.png --brand mard --out out/   # same pipeline from the terminal
python -m pytest
```

Colors come from [beadcolors](https://github.com/maxcleme/beadcolors) (MIT). Rerun `python build.py` to refresh them.
