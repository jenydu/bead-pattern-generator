"""A bead pattern: a grid of palette indices (-1 = no bead) plus its palette."""
from dataclasses import dataclass

import numpy as np

from .clean import transparent_mask
from .palette import Palette, rgb_to_lab


@dataclass
class Pattern:
    palette: Palette
    cells: np.ndarray  # (ny, nx) int, -1 = empty

    @property
    def shape(self):
        return self.cells.shape

    def counts(self):
        used, n = np.unique(self.cells[self.cells >= 0], return_counts=True)
        return dict(zip(used.tolist(), n.tolist()))

    def legend(self, order="code"):
        """Used colors: [{ref, name, rgb, count, group}, ...].

        order: "code" = the brand's own order (MARD: A1, A2, ... A10, ... B1);
        "group" = by series letter (A, B, ...) when the brand has them, otherwise by hue
        family, light to dark; "count" = most beads first."""
        counts = self.counts()
        rows = []
        for i in self.palette.order():
            if i in counts:
                rgb = self.palette.rgb[i]
                key, label = self.palette.group_of(i)
                rows.append({"ref": self.palette.refs[i], "name": self.palette.names[i],
                             "rgb": rgb.tolist(), "count": counts[i], "group": label,
                             "_key": key, "_light": float(rgb_to_lab(rgb)[0])})
        if order == "group":
            if self.palette.grouping == "series":  # rows are already in code order
                rows.sort(key=lambda r: r["_key"])
            else:
                rows.sort(key=lambda r: (r["_key"], -r["_light"]))
        elif order == "count":
            rows.sort(key=lambda r: -r["count"])  # stable: ties stay in code order
        elif order != "code":
            raise ValueError(f"unknown order {order!r}")
        for r in rows:
            del r["_key"], r["_light"]
        return rows

    def rgb_image(self, background=(255, 255, 255)):
        out = np.empty(self.cells.shape + (3,), np.uint8)
        out[:] = background
        m = self.cells >= 0
        out[m] = self.palette.rgb[self.cells[m]]
        return out


def build_pattern(rgba, palette, metric="de2000"):
    """Match every opaque cell of an (ny, nx, 4) array to its nearest palette color."""
    rgba = np.asarray(rgba)
    cells = np.full(rgba.shape[:2], -1, int)
    solid = ~transparent_mask(rgba)
    if solid.any():
        cells[solid] = palette.match(rgba[solid][:, :3], metric)
    return Pattern(palette, cells)
