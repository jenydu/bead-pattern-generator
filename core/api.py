"""Entry points for the web page (called from JS through Pyodide). Plain Python otherwise."""
import hashlib
import io
import json

import numpy as np
from PIL import Image

from .palette import BRANDS, load_palette
from .pipeline import build, prepare
from .render import render_chart, render_preview, render_sheet, tile_boxes

_cache = {}

# Wording of the saved sheet. The page passes translations of these.
SHEET_TEXTS = {
    "title": "{brand} bead pattern: {colors} colors, {beads} beads",
    "subtitle": "{cols} x {rows} cells",
    "subtitle_board": "{cols} x {rows} cells, red lines every {board} cells (one pegboard)",
}


def brands():
    return [{"key": k, "label": v, "symbols": load_palette(k).prefers_symbols}
            for k, v in BRANDS.items()]


def _prepare(data, clean_edges):
    """Decode and prepare the image. Cached for the last image, so changing the brand,
    colors or board size does not repeat the (relatively slow) grid detection."""
    key = (hashlib.sha1(data).hexdigest(), clean_edges)
    if _cache.get("key") != key:
        rgba = np.array(Image.open(io.BytesIO(data)).convert("RGBA"))
        _cache.clear()
        _cache.update(key=key, prep=prepare(rgba, clean_edges))
    return _cache["prep"]


def run(data, brand="mard_291", cells_x=0, cells_y=0, tolerance=6.0, board=0,
        order="code", clean_edges=True, labels="code", swaps="{}", texts="{}"):
    """Image bytes -> everything the page shows.

    cells_x / cells_y > 0 replaces the detected grid (relative to the trimmed art).
    board > 0 splits the chart into pegboards of board x board cells.
    order: "code" or "count" for the bead list. Returns plain dict/list/str/bytes."""
    data = data.to_py().tobytes() if hasattr(data, "to_py") else bytes(data)
    prep = _prepare(data, bool(clean_edges))
    if brand not in BRANDS:
        brand = "mard_291"
    palette = load_palette(brand)
    pattern = build(prep, palette, int(cells_x), int(cells_y), tolerance, bool(clean_edges),
                    json.loads(swaps or "{}"))
    labels = "symbol" if labels == "symbol" else "code"
    ny, nx = pattern.shape
    board = int(board) if board and board > 0 else None
    legend = pattern.legend(order)
    total = sum(c["count"] for c in legend)
    words = {**SHEET_TEXTS, "brand": palette.label, **json.loads(texts or "{}")}
    title = words["title"].format(brand=words["brand"], colors=len(legend), beads=total)
    subtitle = words["subtitle_board" if board else "subtitle"].format(
        cols=nx, rows=ny, board=board)
    tiles = []
    for box in tile_boxes(pattern.shape, board=board):
        tile = {"box": list(box),
                "svg": render_chart(pattern, *box, local_numbers=bool(board), labels=labels)}
        if board:
            tile["board"] = [box[1] // board + 1, box[0] // board + 1]
        tiles.append(tile)
    g = prep.grid
    return {
        "kind": prep.kind,
        "original": list(prep.original_size),
        "grid": {"nx": nx, "ny": ny, "period": float(g.period_x),
                 "manual": int(cells_x) > 0 and int(cells_y) > 0,
                 "detected": [int(g.nx), int(g.ny)]},
        "footprint": [float(v) for v in pattern.footprint],
        "legend": legend,
        "total": total,
        "preview": render_preview(pattern, scale=max(1, min(16, 384 // max(nx, ny)))),
        "sheet": render_sheet(pattern, legend, title, board=board, labels=labels,
                              subtitle=subtitle),
        "conversions": pattern.conversions(),
        "palette": [{"ref": r, "rgb": c.tolist()} for r, c in zip(palette.refs, palette.rgb)],
        "tiles": tiles,
    }
