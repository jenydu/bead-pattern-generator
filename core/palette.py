"""Brand palettes (beadcolors raw CSVs), RGB->Lab, nearest-color matching."""
import csv
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np

PALETTE_DIR = Path(__file__).resolve().parent.parent / "data" / "palettes"

# file stem -> label. diamondDotz is diamond painting, so it is not offered.
BRANDS = {
    "mard": "MARD",
    "perler": "Perler",
    "perler_mini": "Perler Mini",
    "perler_caps": "Perler Caps",
    "hama": "Hama Midi",
    "hama_mini": "Hama Mini",
    "hama_maxi": "Hama Maxi",
    "nabbi": "Nabbi",
    "artkal_a": "Artkal A (2.6mm)",
    "artkal_c": "Artkal C (2.6mm)",
    "artkal_m": "Artkal M (2.6mm)",
    "artkal_r": "Artkal R (5mm)",
    "artkal_s": "Artkal S (5mm)",
    "yant": "Yant",
}


def natural_key(ref):
    """A2 < A10 < B1; non-numeric parts compare as text."""
    return [int(p) if p.isdigit() else p for p in re.split(r"(\d+)", ref) if p]


def rgb_to_lab(rgb):
    """(..., 3) uint8/float RGB -> (..., 3) CIELAB (D65)."""
    c = np.asarray(rgb, dtype=np.float64) / 255.0
    c = np.where(c > 0.04045, ((c + 0.055) / 1.055) ** 2.4, c / 12.92)
    m = np.array([[0.4124564, 0.3575761, 0.1804375],
                  [0.2126729, 0.7151522, 0.0721750],
                  [0.0193339, 0.1191920, 0.9503041]])
    xyz = c @ m.T / np.array([0.95047, 1.0, 1.08883])
    f = np.where(xyz > 216 / 24389, np.cbrt(xyz), (24389 / 27 * xyz + 16) / 116)
    return np.stack([116 * f[..., 1] - 16,
                     500 * (f[..., 0] - f[..., 1]),
                     200 * (f[..., 1] - f[..., 2])], axis=-1)


def delta_e2000(lab1, lab2):
    """CIEDE2000, broadcasting over leading dims. Inputs (..., 3)."""
    L1, a1, b1 = (lab1[..., i] for i in range(3))
    L2, a2, b2 = (lab2[..., i] for i in range(3))
    C1, C2 = np.hypot(a1, b1), np.hypot(a2, b2)
    Cm7 = ((C1 + C2) / 2) ** 7
    G = 0.5 * (1 - np.sqrt(Cm7 / (Cm7 + 25.0 ** 7)))
    a1p, a2p = (1 + G) * a1, (1 + G) * a2
    C1p, C2p = np.hypot(a1p, b1), np.hypot(a2p, b2)
    h1p = np.degrees(np.arctan2(b1, a1p)) % 360
    h2p = np.degrees(np.arctan2(b2, a2p)) % 360
    dLp, dCp = L2 - L1, C2p - C1p
    dh = h2p - h1p
    dh = np.where(dh > 180, dh - 360, np.where(dh < -180, dh + 360, dh))
    dh = np.where(C1p * C2p == 0, 0, dh)
    dHp = 2 * np.sqrt(C1p * C2p) * np.sin(np.radians(dh) / 2)
    Lbp, Cbp = (L1 + L2) / 2, (C1p + C2p) / 2
    hs = h1p + h2p
    hb = np.where(np.abs(h1p - h2p) <= 180, hs / 2,
                  np.where(hs < 360, (hs + 360) / 2, (hs - 360) / 2))
    hb = np.where(C1p * C2p == 0, hs, hb)
    T = (1 - 0.17 * np.cos(np.radians(hb - 30)) + 0.24 * np.cos(np.radians(2 * hb))
         + 0.32 * np.cos(np.radians(3 * hb + 6)) - 0.20 * np.cos(np.radians(4 * hb - 63)))
    dth = 30 * np.exp(-(((hb - 275) / 25) ** 2))
    Cb7 = Cbp ** 7
    Rc = 2 * np.sqrt(Cb7 / (Cb7 + 25.0 ** 7))
    Sl = 1 + 0.015 * (Lbp - 50) ** 2 / np.sqrt(20 + (Lbp - 50) ** 2)
    Sc, Sh = 1 + 0.045 * Cbp, 1 + 0.015 * Cbp * T
    Rt = -np.sin(np.radians(2 * dth)) * Rc
    return np.sqrt((dLp / Sl) ** 2 + (dCp / Sc) ** 2 + (dHp / Sh) ** 2
                   + Rt * (dCp / Sc) * (dHp / Sh))


@dataclass
class Palette:
    key: str
    label: str
    refs: list
    names: list
    rgb: np.ndarray  # (n, 3) uint8
    lab: np.ndarray  # (n, 3)

    def __len__(self):
        return len(self.refs)

    def subset(self, refs):
        """Palette restricted to the given refs ("colors I own")."""
        want = set(refs)
        idx = [i for i, r in enumerate(self.refs) if r in want]
        if not idx:
            raise ValueError("no matching refs")
        return Palette(self.key, self.label, [self.refs[i] for i in idx],
                       [self.names[i] for i in idx], self.rgb[idx], self.lab[idx])

    def order(self):
        """Indices in the brand's own order (natural sort of ref)."""
        return sorted(range(len(self)), key=lambda i: natural_key(self.refs[i]))

    def match(self, rgb, metric="de2000"):
        """(..., 3) RGB -> (...) palette indices. Only unique colors are compared."""
        rgb = np.asarray(rgb, dtype=np.uint8)
        flat = rgb.reshape(-1, 3)
        uniq, inv = np.unique(flat, axis=0, return_inverse=True)
        ulab = rgb_to_lab(uniq)
        if metric == "de2000":
            d = delta_e2000(ulab[:, None, :], self.lab[None, :, :])
        else:
            d = np.linalg.norm(ulab[:, None, :] - self.lab[None, :, :], axis=-1)
        return d.argmin(axis=1)[inv.reshape(-1)].reshape(rgb.shape[:-1])


def parse_palette(key, text):
    refs, names, rgb = [], [], []
    for row in csv.reader(text.splitlines()):
        if not row:
            continue
        if len(row) < 5:
            raise ValueError(f"{key}: bad row {row}")
        ref = row[0].strip()
        if ref in refs:
            raise ValueError(f"{key}: duplicate ref {ref}")
        refs.append(ref)
        names.append(row[1].strip())
        rgb.append([int(v) for v in row[2:5]])
    rgb = np.array(rgb, dtype=np.uint8)
    return Palette(key, BRANDS.get(key, key), refs, names, rgb, rgb_to_lab(rgb))


def load_palette(key, directory=PALETTE_DIR):
    return parse_palette(key, (Path(directory) / f"{key}.csv").read_text(encoding="utf-8"))
