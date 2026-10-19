"""Estimate the true pixel grid of a (possibly rescaled / blurred) pixel-art image.

Pixel borders show up as a periodic pulse train in the per-axis edge profile (summed
gradient magnitude). A pulse train has spectral lines at f, 2f, 3f...; the real pixel
size is the *lowest* frequency line that stands out from the noise floor. The line's
exact position gives the (fractional) period and its phase gives the grid offset.
"""
from dataclasses import dataclass

import numpy as np

PAD = 4  # zero-padding factor for the coarse spectrum
MAX_LINES = 256  # rows (or columns) sampled for the edge profiles; more adds nothing


@dataclass
class Grid:
    period_x: float
    period_y: float
    off_x: float  # position of a cell border, in [0, period)
    off_y: float
    nx: int
    ny: int
    start_x: float  # left border of the first cell (< 0 if the first cell is cropped)
    start_y: float
    confidence: float  # prominence of the spectral line; 0 means 1:1 / no structure

    def x_edges(self):
        return self.start_x + self.period_x * np.arange(self.nx + 1)

    def y_edges(self):
        return self.start_y + self.period_y * np.arange(self.ny + 1)


NOISE = 30.0  # gradient (summed over channels, 0..255 each) below this is treated as noise


def _highpass(prof):
    w = max(9, (len(prof) // 5) | 1)
    padded = np.pad(prof, w // 2, mode="reflect")
    return prof - np.convolve(padded, np.ones(w) / w, mode="valid")


def _edge_profile(arr, axis):
    """(soft, hard) edge profiles between neighbouring columns (axis=1) or rows (axis=0).

    Both have length n-1 and bin i sits at border coordinate i+1. Small gradients (JPEG
    blocks, dithering) are dropped and the rest compressed so a few high-contrast edges
    don't dominate. `hard` is the first difference only (peaks at borders of sharp pixels);
    `soft` adds the second difference so bilinear ramps, whose only features are kinks at
    cell centers, still show their period. `soft` is high-passed so smooth large features
    don't look like a low-frequency grid."""
    other = 1 - axis
    n_lines = arr.shape[other]
    if n_lines > MAX_LINES:  # the profile only needs a spread of lines, not every pixel
        arr = np.take(arr, np.linspace(0, n_lines - 1, MAX_LINES).astype(int), axis=other)
    a = arr.astype(np.float32)
    d1 = np.abs(np.diff(a, axis=axis)).sum(axis=-1)
    hard = np.sqrt(np.maximum(d1 - NOISE, 0)).sum(axis=other).astype(np.float64)
    d2 = np.abs(np.diff(a, n=2, axis=axis)).sum(axis=-1)  # bin j at coordinate j+1.5
    g2 = np.sqrt(np.maximum(d2 - NOISE, 0)).sum(axis=other).astype(np.float64)
    g2c = np.zeros_like(hard)
    g2c[1:-1] = (g2[:-1] + g2[1:]) / 2  # resample to border coordinates i+1
    return _highpass(hard + g2c), hard


def _spectrum(prof, nfft):
    """Power spectrum on a frequency grid shared by both axes (cycles per bin)."""
    x = prof * np.hanning(len(prof))
    return np.fft.rfftfreq(nfft), np.abs(np.fft.rfft(x, n=nfft)) ** 2


def _noise_floor(p, width):
    from numpy.lib.stride_tricks import sliding_window_view
    pad = np.pad(p, width // 2, mode="edge")
    return np.median(sliding_window_view(pad, width), axis=1)


def _comb_candidates(profs, min_period, max_period, harmonics=4):
    """[(period, comb_score, prominence)] for local maxima of the summed power spectrum.

    comb_score is the mean log prominence over the line and its harmonics: a real
    fundamental has strong lines at f, 2f, 3f; f/2 has weak lines at f/2, 3f/2."""
    nfft = PAD * max(len(p) for p in profs)
    prom = 0.0
    for prof in profs:
        f, p = _spectrum(prof, nfft)
        p = p / max(p.sum(), 1e-12)
        # each axis against its own noise floor; the window is ~8 natural bins of that axis
        width = int(8 * nfft / len(prof)) | 1
        prom = prom + p / np.maximum(_noise_floor(p, width), 1e-18)
    prom = prom / len(profs)  # mean over axes
    total = prom
    lp = np.log1p(prom)
    band = (f >= 1 / max_period) & (f <= 1 / min_period)
    peak = np.zeros(len(f), bool)
    peak[1:-1] = (total[1:-1] > total[:-2]) & (total[1:-1] >= total[2:])
    out = []
    for i in np.nonzero(peak & band)[0]:
        vals = []
        for k in range(1, harmonics + 1):
            j = int(round(i * k))
            if j + 2 >= len(f) or f[j] > 0.5:
                break
            vals.append(lp[max(j - 2, 0):j + 3].max())
        if vals:
            out.append((1 / f[i], float(np.mean(vals)), float(prom[i])))
    return out


def _refine(soft, hard, p0, span=0.04):
    """Fine search of the period around p0 by direct DFT, then the grid phase."""
    n = len(soft)
    pos = np.arange(n) + 1.0  # coordinate of the border after bin i
    fs = (1 / p0) * (1 + np.linspace(-span, span, 161))
    ph = np.exp(-2j * np.pi * fs[:, None] * pos[None, :])
    a = ph @ soft
    j = int(np.abs(a).argmax())
    p = 1 / fs[j]
    return p, _phase(soft, hard, p)


def _phase(soft, hard, p):
    pos = np.arange(len(soft)) + 1.0
    a = np.exp(-2j * np.pi * pos / p) @ soft
    off = float((-np.angle(a) / (2 * np.pi) * p) % p)
    # sharp pixels: hard edges sit on the borders. Bilinear ramps: the soft line marks
    # cell *centers* and the hard profile is flat there, so shift by half a cell.
    k = np.floor((pos - off) / p + 0.5)
    on = np.abs(pos - off - k * p) < max(0.5, 0.1 * p)
    if on.any() and hard[on].mean() < 1.15 * hard.mean():
        off = (off + p / 2) % p
    return off


def _layout(n, p, off):
    """Cells whose span is at least half inside the image."""
    start = off - p if off > 0.5 * p else off
    count = int(np.floor((n - start) / p + 0.5))
    return start, max(count, 1)


def _harmonic(a, b, tol=0.04):
    """True if a and b differ by roughly a whole factor (2x, 3x, 4x), not a real aspect."""
    r = max(a, b) / min(a, b)
    return any(abs(r - n) < tol * n for n in (2, 3, 4))


def detect_grid(arr, square=None, min_cells=6, min_prominence=8.0):
    """arr: (H, W, C) array. Returns a Grid; period 1 if no pixel structure is found.

    square: None = decide (pixels may be wider than tall if the image was stretched),
    True = force one period for both axes, False = always fit the axes separately."""
    arr = np.asarray(arr)
    h, w = arr.shape[:2]
    sizes = {"x": w, "y": h}
    soft, hard = {}, {}
    soft["x"], hard["x"] = _edge_profile(arr, 1)
    soft["y"], hard["y"] = _edge_profile(arr, 0)

    def pick(axes):
        n = min(sizes[a] for a in axes)
        if n / min_cells <= 2:
            return None, 0.0
        used = [soft[a] for a in axes if np.abs(soft[a]).sum() > 0]
        if not used:
            return None, 0.0
        cands = _comb_candidates(used, 2.0, n / min_cells)
        if not cands:
            return None, 0.0
        # lowest-frequency line whose comb score is close to the best
        top = max(c[1] for c in cands)
        good = [c for c in cands if c[1] >= 0.85 * top and c[2] >= min_prominence]
        if not good:
            return None, max(c[2] for c in cands)
        p, _, prom = max(good, key=lambda c: c[0])
        return p, prom

    p, conf = pick(["x", "y"])
    periods = {"x": p, "y": p}
    use_square = True
    if square is not True:
        px, cx = pick(["x"])
        py, cy = pick(["y"])
        stretched = (px and py and abs(px - py) > 0.04 * max(px, py)
                     and not _harmonic(px, py))
        if square is False or stretched:
            periods, conf, use_square = {"x": px, "y": py}, min(cx, cy), False

    if any(periods[a] is None or np.abs(soft[a]).sum() == 0 for a in "xy"):
        periods = {"x": None, "y": None} if use_square else periods
    fitted = {a: _refine(soft[a], hard[a], periods[a]) for a in "xy" if periods[a]}
    for a, (p, _) in list(fitted.items()):
        # images are usually exactly n cells wide: snap to size/n when we are that close
        q = sizes[a] / max(round(sizes[a] / p), 1)
        if abs(q - p) < 0.006 * p:
            fitted[a] = (q, _phase(soft[a], hard[a], q))
    if use_square and len(fitted) == 2:
        p = (fitted["x"][0] + fitted["y"][0]) / 2  # square pixels: share one period
        fitted = {a: (p, _phase(soft[a], hard[a], p)) for a in "xy"}
    out, final = {}, {}
    for a in "xy":
        if a not in fitted:
            final[a], out[a] = 1.0, (0.0, 0.0, sizes[a])
        else:
            p, off = fitted[a]
            start, n = _layout(sizes[a], p, off)
            final[a], out[a] = p, (off, start, n)
    return Grid(final["x"], final["y"], out["x"][0], out["y"][0], out["x"][2],
                out["y"][2], out["x"][1], out["y"][1], float(conf))
