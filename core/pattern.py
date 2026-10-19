"""A bead pattern: a grid of palette indices (-1 = no bead) plus its palette."""
from dataclasses import dataclass

import numpy as np

from .clean import transparent_mask
from .palette import Palette


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

    def legend(self):
        """Used colors in the brand's own order: [{ref, name, rgb, count}, ...]."""
        counts = self.counts()
        return [{"ref": self.palette.refs[i], "name": self.palette.names[i],
                 "rgb": self.palette.rgb[i].tolist(), "count": counts[i]}
                for i in self.palette.order() if i in counts]

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
