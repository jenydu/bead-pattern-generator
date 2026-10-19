"""Entry points for the web page (called from JS through Pyodide). Plain Python otherwise."""
import hashlib
import io

import numpy as np
from PIL import Image

from .clean import sample_cells, unify_colors
from .grid_detect import Grid, detect_grid
from .palette import BRANDS, load_palette
from .pattern import build_pattern
from .render import render_chart, render_preview, tile_boxes, to_png

_cache = {}


def brands():
    return [{"key": k, "label": v} for k, v in BRANDS.items()]


def _decode(data):
    key = hashlib.sha1(data).hexdigest()
    if _cache.get("key") != key:
        im = Image.open(io.BytesIO(data))
        rgba = np.array(im.convert("RGBA"))
        _cache.clear()
        _cache.update(key=key, rgba=rgba, grid=detect_grid(rgba))
    return _cache["rgba"], _cache["grid"]


def _manual_grid(w, h, nx, ny):
    return Grid(w / nx, h / ny, 0.0, 0.0, nx, ny, 0.0, 0.0, 1.0)


def run(data, brand="mard", cells_x=0, cells_y=0, tolerance=6.0):
    """Image bytes -> everything the page shows.

    cells_x / cells_y > 0 overrides the detected grid. Returns plain dict/list/bytes."""
    data = data.to_py().tobytes() if hasattr(data, "to_py") else bytes(data)
    rgba, auto = _decode(data)
    h, w = rgba.shape[:2]
    if cells_x > 0 and cells_y > 0:
        grid = _manual_grid(w, h, int(cells_x), int(cells_y))
    else:
        grid = auto
    cells = sample_cells(rgba, grid)
    if tolerance > 0:
        cells = unify_colors(cells, tolerance)
    pattern = build_pattern(cells, load_palette(brand))
    ny, nx = pattern.shape
    return {
        "image": {"width": w, "height": h},
        "grid": {"nx": nx, "ny": ny, "period": float(grid.period_x),
                 "confidence": float(grid.confidence), "manual": cells_x > 0 and cells_y > 0,
                 "detected": [int(auto.nx), int(auto.ny)]},
        "legend": pattern.legend(),
        "preview": to_png(render_preview(pattern, scale=max(1, min(16, 384 // max(nx, ny))))),
        "full": to_png(render_chart(pattern)),
        "tiles": [{"box": list(b), "png": to_png(render_chart(pattern, *b))}
                  for b in tile_boxes(pattern.shape)],
    }
