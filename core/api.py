"""Entry points for the web page (called from JS through Pyodide). Plain Python otherwise."""
import hashlib
import io

import numpy as np
from PIL import Image

from .clean import (clear_background, crop_to_content, sample_cells, trim_border,
                    unify_colors)
from .grid_detect import Grid, detect_grid
from .palette import BRANDS, load_palette
from .pattern import build_pattern
from .render import render_chart, render_preview, render_sheet, tile_boxes, to_png

_cache = {}


def brands():
    return [{"key": k, "label": v} for k, v in BRANDS.items()]


def _prepare(data, clean_edges):
    """Decode, optionally trim the border, detect the grid. Cached for the last image."""
    key = (hashlib.sha1(data).hexdigest(), clean_edges)
    if _cache.get("key") != key:
        rgba = np.array(Image.open(io.BytesIO(data)).convert("RGBA"))
        if clean_edges:
            rgba, _ = trim_border(rgba)
        _cache.clear()
        _cache.update(key=key, rgba=rgba, grid=detect_grid(rgba))
    return _cache["rgba"], _cache["grid"]


def _manual_grid(w, h, nx, ny):
    return Grid(w / nx, h / ny, 0.0, 0.0, nx, ny, 0.0, 0.0, 1.0)


def run(data, brand="mard_291", cells_x=0, cells_y=0, tolerance=6.0, board=0,
        order="code", clean_edges=True):
    """Image bytes -> everything the page shows.

    cells_x / cells_y > 0 overrides the detected grid. board > 0 splits the chart into
    pegboards of board x board cells. order: "code" | "group" | "count" for the bead list.
    clean_edges: trim plain borders/frames and empty the white or transparent background
    (cells_x / cells_y then refer to the trimmed art).
    Returns plain dict/list/bytes."""
    data = data.to_py().tobytes() if hasattr(data, "to_py") else bytes(data)
    rgba, auto = _prepare(data, bool(clean_edges))
    h, w = rgba.shape[:2]
    manual = cells_x > 0 and cells_y > 0
    grid = _manual_grid(w, h, int(cells_x), int(cells_y)) if manual else auto
    cells = sample_cells(rgba, grid)
    if clean_edges:
        cells = crop_to_content(clear_background(cells))
    if tolerance > 0:
        cells = unify_colors(cells, tolerance)
    palette = load_palette(brand)
    pattern = build_pattern(cells, palette)
    ny, nx = pattern.shape
    board = int(board) if board and board > 0 else None
    legend = pattern.legend(order)
    total = sum(c["count"] for c in legend)
    title = f"{palette.label} bead pattern: {len(legend)} colors, {total} beads"
    tiles = []
    for box in tile_boxes(pattern.shape, board=board):
        tile = {"box": list(box),
                "png": to_png(render_chart(pattern, *box, local_numbers=bool(board)))}
        if board:
            tile["board"] = [box[1] // board + 1, box[0] // board + 1]
        tiles.append(tile)
    return {
        "image": {"width": w, "height": h},
        "grid": {"nx": nx, "ny": ny, "period": float(grid.period_x),
                 "confidence": float(grid.confidence), "manual": manual,
                 "detected": [int(auto.nx), int(auto.ny)]},
        "legend": legend,
        "total": total,
        "preview": to_png(render_preview(pattern, scale=max(1, min(16, 384 // max(nx, ny))))),
        "full": to_png(render_sheet(pattern, legend, title, board=board,
                                    show_groups=order == "group")),
        "tiles": tiles,
    }
