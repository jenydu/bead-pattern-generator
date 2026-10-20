"""A bead pattern: a grid of palette indices (-1 = no bead) plus its palette."""
from dataclasses import dataclass

import numpy as np

from .clean import transparent_mask
from .palette import Palette, delta_e2000, rgb_to_lab

# Chart symbols. No letters or digits (they read as codes or row numbers), and no * : ; which
# are too small in a cell. Punctuation first, then shapes every system font has, then pairs.
_PUNCT = list("?><~!#$%&+=@^/|")
SYMBOLS = _PUNCT + list("■▲▼●◆□△▽○◇◐◑▣▤▥▦▧▨◢◣◤◥◉")
SYMBOLS += [a + b for a in _PUNCT[:10] for b in _PUNCT[:10] if a != b]


@dataclass
class Pattern:
    palette: Palette
    cells: np.ndarray  # (ny, nx) int, -1 = empty
    source: np.ndarray  # (ny, nx, 3) uint8, the image color each cell was matched from

    @property
    def shape(self):
        return self.cells.shape

    def counts(self):
        used, n = np.unique(self.cells[self.cells >= 0], return_counts=True)
        return dict(zip(used.tolist(), n.tolist()))

    def symbol_map(self):
        """{palette index: symbol} for the used colors, assigned in the brand's code order so
        a color keeps its symbol however the bead list is sorted."""
        used = self.counts()
        return {i: SYMBOLS[n % len(SYMBOLS)]
                for n, i in enumerate(j for j in self.palette.order() if j in used)}

    def labels(self, kind="code"):
        if kind == "symbol":
            return self.symbol_map()
        return {i: self.palette.refs[i] for i in self.counts()}

    def conversions(self, n_candidates=12, max_rows=80):
        """Every distinct source color and the bead it became, most used first.

        Each row also lists the nearest palette colors, for swapping one in, and the
        positions (y * nx + x) of the cells that color covers."""
        solid = self.cells >= 0
        if not solid.any():
            return []
        src = self.source[solid]
        uniq, inv, counts = np.unique(src, axis=0, return_inverse=True, return_counts=True)
        inv = inv.reshape(-1)
        current = np.zeros(len(uniq), int)
        current[inv] = self.cells[solid]
        flat = np.flatnonzero(solid.reshape(-1))   # cell index = y * nx + x
        auto = self.palette.match(uniq)
        keep = np.argsort(-counts, kind="stable")[:max_rows]
        d = delta_e2000(rgb_to_lab(uniq[keep])[:, None, :], self.palette.lab[None, :, :])
        rows = []
        for k, u in enumerate(keep):
            near = np.argsort(d[k], kind="stable")[:n_candidates]
            rows.append({
                "src": uniq[u].tolist(), "count": int(counts[u]),
                "ref": self.palette.refs[current[u]], "auto": self.palette.refs[auto[u]],
                "swapped": bool(current[u] != auto[u]),
                "cells": flat[inv == u].tolist(),
                "candidates": [{"ref": self.palette.refs[i],
                                "rgb": self.palette.rgb[i].tolist(),
                                "de": round(float(d[k, i]), 1)} for i in near]})
        return rows

    def legend(self, order="code"):
        """Used colors as [{ref, name, rgb, count, symbol}], in the brand's own order
        (MARD: A1, A2, ... A10, ... B1) or, for order="count", most beads first."""
        if order not in ("code", "count"):
            raise ValueError(f"unknown order {order!r}")
        counts = self.counts()
        symbols = self.symbol_map()
        rows = [{"ref": self.palette.refs[i], "name": self.palette.names[i],
                 "rgb": self.palette.rgb[i].tolist(), "count": counts[i], "symbol": symbols[i]}
                for i in self.palette.order() if i in counts]
        if order == "count":
            rows.sort(key=lambda r: -r["count"])   # stable, so ties stay in code order
        return rows

    def rgb_image(self, background=(255, 255, 255)):
        out = np.empty(self.cells.shape + (3,), np.uint8)
        out[:] = background
        m = self.cells >= 0
        out[m] = self.palette.rgb[self.cells[m]]
        return out


def build_pattern(rgba, palette, swaps=None):
    """Match every opaque cell of an (ny, nx, 4) array to its nearest palette color.

    swaps: {"rrggbb": ref} sends that source color to a chosen bead instead of the nearest
    one. Refs that are not in the palette (e.g. left over from another brand) are ignored."""
    rgba = np.asarray(rgba)
    cells = np.full(rgba.shape[:2], -1, int)
    solid = ~transparent_mask(rgba)
    if solid.any():
        uniq, inv = np.unique(rgba[solid][:, :3], axis=0, return_inverse=True)
        chosen = palette.match(uniq)
        index = {r: i for i, r in enumerate(palette.refs)}
        for hexkey, ref in (swaps or {}).items():
            if ref in index and len(hexkey) == 6:
                rgb = [int(hexkey[i:i + 2], 16) for i in (0, 2, 4)]
                chosen[(uniq == rgb).all(axis=1)] = index[ref]
        cells[solid] = chosen[inv.reshape(-1)]
    return Pattern(palette, cells, rgba[..., :3].astype(np.uint8))
