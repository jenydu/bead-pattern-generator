"""The whole image -> Pattern pipeline, shared by the web page (api.py) and the CLI."""
from dataclasses import dataclass

import numpy as np

from .clean import clear_background, crop_to_content, sample_cells, trim_border, unify_colors
from .grid_detect import Grid, detect_grid
from .pattern import build_pattern

MAX_AUTO_CELLS = 150   # a 1:1 image up to this size is used pixel for pixel
PHOTO_LONG_SIDE = 50   # a bigger image with no pixel grid is shrunk to this many cells
MAX_CELLS = 200        # per side, for a custom grid


@dataclass
class Prepared:
    rgba: np.ndarray    # after border trimming
    grid: Grid
    kind: str           # "grid" (scaled pixel art), "pixels" (already 1:1) or "photo"
    original_size: tuple


def prepare(rgba, clean_edges=True):
    """Trim borders (optional) and work out the cell grid."""
    rgba = np.asarray(rgba)
    original = (rgba.shape[1], rgba.shape[0])
    if clean_edges:
        rgba, _ = trim_border(rgba)
    h, w = rgba.shape[:2]
    grid = detect_grid(rgba)
    if grid.period_x > 1 or grid.period_y > 1:
        kind = "grid"
    elif max(w, h) <= MAX_AUTO_CELLS:
        kind = "pixels"
    else:
        # no pixel structure and too many pixels to be beads: treat it as a picture
        kind = "photo"
        p = max(w, h) / PHOTO_LONG_SIDE
        grid = Grid(p, p, max(round(w / p), 1), max(round(h / p), 1), 0.0, 0.0, 0.0)
    return Prepared(rgba, grid, kind, original)


def custom_grid(prep, cells_x, cells_y):
    h, w = prep.rgba.shape[:2]
    cx = int(np.clip(cells_x, 1, MAX_CELLS))
    cy = int(np.clip(cells_y, 1, MAX_CELLS))
    return Grid(w / cx, h / cy, cx, cy, 0.0, 0.0, 1.0)


def build(prep, palette, cells_x=0, cells_y=0, tolerance=6.0, clean_edges=True, swaps=None):
    """Prepared image -> Pattern. cells_x/cells_y > 0 replaces the detected grid; swaps is
    {"rrggbb": ref} (see build_pattern)."""
    custom = cells_x > 0 and cells_y > 0
    grid = custom_grid(prep, cells_x, cells_y) if custom else prep.grid
    if prep.kind == "photo":
        cells = sample_cells(prep.rgba, grid, window=1.0, reduce="mean")
    else:
        cells = sample_cells(prep.rgba, grid)
    if clean_edges:
        cells = crop_to_content(clear_background(cells))
    if tolerance > 0:
        cells = unify_colors(cells, tolerance)
    return build_pattern(cells, palette, swaps=swaps)
