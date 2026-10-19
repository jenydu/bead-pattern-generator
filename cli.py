"""Image -> bead pattern from the terminal (same pipeline the web page runs)."""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from core.clean import sample_cells, unify_colors
from core.grid_detect import Grid, detect_grid
from core.palette import BRANDS, load_palette
from core.pattern import build_pattern
from core.render import render_chart, render_preview, tile_boxes


def manual_grid(w, h, nx, ny):
    px, py = w / nx, h / ny
    return Grid(px, py, 0.0, 0.0, nx, ny, 0.0, 0.0, 1.0)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--brand", default="mard", choices=list(BRANDS))
    ap.add_argument("--cells", type=int, nargs=2, metavar=("NX", "NY"),
                    help="override detection with a manual grid size")
    ap.add_argument("--tolerance", type=float, default=6.0,
                    help="merge colors closer than this (Lab); 0 disables")
    ap.add_argument("--out", type=Path, help="directory for chart PNGs")
    a = ap.parse_args(argv)

    rgba = np.array(Image.open(a.image).convert("RGBA"))
    h, w = rgba.shape[:2]
    grid = manual_grid(w, h, *a.cells) if a.cells else detect_grid(rgba)
    print(f"image {w}x{h}  grid {grid.nx}x{grid.ny}  period {grid.period_x:.3f}x"
          f"{grid.period_y:.3f}  offset ({grid.off_x:.2f}, {grid.off_y:.2f})  "
          f"confidence {grid.confidence:.1f}")
    cells = sample_cells(rgba, grid)
    if a.tolerance > 0:
        cells = unify_colors(cells, a.tolerance)
    pattern = build_pattern(cells, load_palette(a.brand))
    legend = pattern.legend()
    print(f"{len(legend)} colors, {sum(c['count'] for c in legend)} beads")
    for c in legend:
        print(f"  {c['ref']:>5}  {c['count']:>5}  {c['name']}")
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        render_preview(pattern).save(a.out / "preview.png")
        for n, box in enumerate(tile_boxes(pattern.shape), 1):
            render_chart(pattern, *box).save(a.out / f"chart_{n}.png")
        print("wrote", a.out)


if __name__ == "__main__":
    sys.exit(main())
