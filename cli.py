"""Image -> bead pattern from the terminal (same pipeline the web page runs)."""
import argparse
import sys
from pathlib import Path

import numpy as np
from PIL import Image

from core.palette import BRANDS, load_palette
from core.pipeline import build, prepare
from core.render import render_chart, render_sheet, tile_boxes


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--brand", default="mard_291", choices=list(BRANDS))
    ap.add_argument("--cells", type=int, nargs=2, metavar=("NX", "NY"),
                    help="use this grid instead of the detected one")
    ap.add_argument("--tolerance", type=float, default=6.0,
                    help="merge colors closer than this (Lab); 0 disables")
    ap.add_argument("--board", type=int, default=0, help="pegboard size; splits the chart")
    ap.add_argument("--order", default="code", choices=["code", "count"])
    ap.add_argument("--keep-edges", action="store_true",
                    help="do not trim borders or remove the white/transparent background")
    ap.add_argument("--mirror", action="store_true", help="flip the pattern left to right")
    ap.add_argument("--out", type=Path, help="directory for the SVG charts")
    a = ap.parse_args(argv)

    rgba = np.array(Image.open(a.image).convert("RGBA"))
    prep = prepare(rgba, clean_edges=not a.keep_edges)
    g = prep.grid
    print(f"image {prep.original_size[0]}x{prep.original_size[1]} -> {prep.rgba.shape[1]}x"
          f"{prep.rgba.shape[0]} after trimming; {prep.kind}; grid {g.nx}x{g.ny}  period "
          f"{g.period_x:.3f}x{g.period_y:.3f}  confidence {g.confidence:.1f}")
    nx, ny = a.cells or (0, 0)
    pattern = build(prep, load_palette(a.brand), nx, ny, a.tolerance, not a.keep_edges,
                    mirror=a.mirror)
    legend = pattern.legend(a.order)
    print(f"pattern {pattern.shape[1]}x{pattern.shape[0]}, {len(legend)} colors, "
          f"{sum(c['count'] for c in legend)} beads")
    for c in legend:
        print(f"  {c['ref']:>5}  {c['count']:>5}  {c['name']}")
    if a.out:
        a.out.mkdir(parents=True, exist_ok=True)
        board = a.board or None
        title = f"{pattern.palette.label}: {len(legend)} colors"
        (a.out / "sheet.svg").write_text(
            render_sheet(pattern, legend, title, board), encoding="utf-8")
        for n, box in enumerate(tile_boxes(pattern.shape, board=board), 1):
            (a.out / f"chart_{n}.svg").write_text(
                render_chart(pattern, *box, local_numbers=bool(board)), encoding="utf-8")
        print("wrote", a.out)


if __name__ == "__main__":
    sys.exit(main())
