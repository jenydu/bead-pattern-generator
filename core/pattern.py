"""A bead pattern: a grid of palette indices (-1 = no bead) plus its palette."""
from dataclasses import dataclass

import numpy as np

from .clean import transparent_mask
from .palette import Palette, delta_e2000, rgb_to_lab


# Symbols for charts. No letters or digits: they would be confused with bead codes and with
# the row / column numbers. Plain punctuation first, then geometric shapes that every
# system font has; past that, pairs of punctuation marks.
_PUNCT = list("?><~!#$%&+=@^/|")  # not * : ; which are too small to read in a cell
SYMBOLS = _PUNCT + list("■▲▼●◆□△▽○◇◐◑▣▤▥▦▧▨◢◣◤◥◉")
SYMBOLS += [a + b for a in _PUNCT[:10] for b in _PUNCT[:10] if a != b]


@dataclass
class Pattern:
    palette: Palette
    cells: np.ndarray  # (ny, nx) int, -1 = empty
    source: np.ndarray = None  # (ny, nx, 3) uint8, the color each cell was matched from

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

        Each row also lists the nearest palette colors, for swapping one in."""
        solid = self.cells >= 0
        if self.source is None or not solid.any():
            return []
        src = self.source[solid]
        uniq, inv, counts = np.unique(src, axis=0, return_inverse=True, return_counts=True)
        inv = inv.reshape(-1)
        current = np.zeros(len(uniq), int)
        current[inv] = self.cells[solid]
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
                "candidates": [{"ref": self.palette.refs[i],
                                "rgb": self.palette.rgb[i].tolist(),
                                "de": round(float(d[k, i]), 1)} for i in near]})
        return rows

    @property
    def shape(self):
        return self.cells.shape

    def counts(self):
        used, n = np.unique(self.cells[self.cells >= 0], return_counts=True)
        return dict(zip(used.tolist(), n.tolist()))

    def legend(self, order="code"):
        """Used colors: [{ref, name, rgb, count, group, symbol}, ...].

        order: "code" = the brand's own order (MARD: A1, A2, ... A10, ... B1);
        "group" = by series letter (A, B, ...) when the brand has them, otherwise by hue
        family, light to dark; "count" = most beads first."""
        counts = self.counts()
        symbols = self.symbol_map()
        rows = []
        for i in self.palette.order():
            if i in counts:
                rgb = self.palette.rgb[i]
                key, label = self.palette.group_of(i)
                rows.append({"ref": self.palette.refs[i], "name": self.palette.names[i],
                             "rgb": rgb.tolist(), "count": counts[i], "group": label,
                             "symbol": symbols[i],
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


def build_pattern(rgba, palette, metric="de2000", swaps=None):
    """Match every opaque cell of an (ny, nx, 4) array to its nearest palette color.

    swaps: {"rrggbb": ref} sends that source color to a chosen bead instead of the nearest
    one. Refs that are not in the palette (e.g. left over from another brand) are ignored."""
    rgba = np.asarray(rgba)
    cells = np.full(rgba.shape[:2], -1, int)
    solid = ~transparent_mask(rgba)
    if solid.any():
        uniq, inv = np.unique(rgba[solid][:, :3], axis=0, return_inverse=True)
        chosen = palette.match(uniq, metric)
        index = {r: i for i, r in enumerate(palette.refs)}
        for hexkey, ref in (swaps or {}).items():
            if ref in index and len(hexkey) == 6:
                rgb = [int(hexkey[i:i + 2], 16) for i in (0, 2, 4)]
                chosen[(uniq == rgb).all(axis=1)] = index[ref]
        cells[solid] = chosen[inv.reshape(-1)]
    return Pattern(palette, cells, rgba[..., :3].astype(np.uint8))
