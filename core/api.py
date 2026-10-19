"""Entry points for the web page (called from JS through Pyodide). Plain Python otherwise."""
import hashlib
import json
import io

import numpy as np
from PIL import Image

from .palette import BRANDS, load_palette
from .pipeline import build, prepare
from .render import render_chart, render_preview, render_sheet, tile_boxes

_cache = {}


def brands():
    return [{"key": k, "label": v, "symbols": load_palette(k).long_codes}
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
        order="code", clean_edges=True, labels="code", swaps="{}"):
    """Image bytes -> everything the page shows.

    cells_x / cells_y > 0 replaces the detected grid (relative to the trimmed art).
    board > 0 splits the chart into pegboards of board x board cells.
    order: "code" | "group" | "count" for the bead list. Returns plain dict/list/str/bytes."""
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
    title = f"{palette.label} bead pattern: {len(legend)} colors, {total} beads"
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
        "trimmed": [prep.rgba.shape[1], prep.rgba.shape[0]],
        "grid": {"nx": nx, "ny": ny, "period": float(g.period_x),
                 "confidence": float(g.confidence), "manual": int(cells_x) > 0 and int(cells_y) > 0,
                 "detected": [int(g.nx), int(g.ny)]},
        "legend": legend,
        "total": total,
        "preview": render_preview(pattern, scale=max(1, min(16, 384 // max(nx, ny)))),
        "sheet": render_sheet(pattern, legend, title, board=board, show_groups=order == "group",
                              labels=labels),
        "conversions": pattern.conversions(),
        "palette": [{"ref": r, "rgb": c.tolist()} for r, c in zip(palette.refs, palette.rgb)],
        "tiles": tiles,
    }
