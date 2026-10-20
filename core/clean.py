"""Turn an image and its grid into one color per cell, and strip borders and backgrounds."""
import numpy as np

from .palette import rgb_to_lab

ALPHA_CUTOFF = 128  # alpha below this means no bead


def sample_cells(arr, grid, window=0.5, reduce="median"):
    """One color per cell -> (ny, nx, 4) uint8.

    Pixel art: the median of the central `window` fraction of the cell, since blur and
    resampling damage sits at the borders. A photo (window=1, reduce="mean") is averaged."""
    stat = np.median if reduce == "median" else np.mean
    arr = np.asarray(arr)
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.full(arr.shape[:2] + (1,), 255, arr.dtype)], axis=2)
    h, w = arr.shape[:2]
    xe, ye = grid.x_edges(), grid.y_edges()
    out = np.zeros((grid.ny, grid.nx, 4), np.uint8)
    for j in range(grid.ny):
        y0, y1 = _span(ye[j], ye[j + 1], window, h)
        for i in range(grid.nx):
            x0, x1 = _span(xe[i], xe[i + 1], window, w)
            out[j, i] = stat(arr[y0:y1, x0:x1].reshape(-1, 4), axis=0)
    return out


def _span(a, b, window, limit):
    """Pixel index range of the central part of [a, b), clipped to the image, >= 1 px."""
    lo, hi = max(a, 0.0), min(b, float(limit))
    mid, half = (lo + hi) / 2, max((hi - lo) * window / 2, 0.5)
    i0 = int(np.clip(np.floor(mid - half + 0.5), 0, limit - 1))
    i1 = int(np.clip(np.ceil(mid + half - 0.5), i0 + 1, limit))
    return i0, i1


def unify_colors(rgba, tolerance=6.0):
    """Merge near-identical colors (left by blur / JPEG) into the most common one.

    Colors are visited most common first; each joins the first kept color within
    `tolerance` (Lab distance), otherwise it is kept."""
    rgba = np.asarray(rgba)
    out = rgba.copy()
    solid = rgba[..., 3] >= ALPHA_CUTOFF
    if not solid.any():
        return out
    colors, inv, counts = np.unique(rgba[solid][:, :3], axis=0, return_inverse=True,
                                    return_counts=True)
    lab = rgb_to_lab(colors)
    kept, target = [], np.zeros(len(colors), int)
    for i in np.argsort(-counts):
        for k in kept:
            if np.linalg.norm(lab[i] - lab[k]) <= tolerance:
                target[i] = k
                break
        else:
            kept.append(i)
            target[i] = i
    out[..., :3][solid] = colors[target[inv.reshape(-1)]]
    return out


def transparent_mask(rgba):
    return np.asarray(rgba)[..., 3] < ALPHA_CUTOFF


_SAMPLES = 512  # pixels per line used to judge whether a row/column is plain


def _plain_lines(rgb, axis, tol=75, frac=0.98, min_light=150, min_gray=90, max_tint=20):
    """Bool per row (axis=0) or column (axis=1): a light or mid-gray, near-uniform line.

    Light or neutral gray (a screenshot frame), so a dark or colored ring that is part of the
    art is never taken for a frame; near-uniform
    (within `tol` summed RGB of the median for `frac` of its pixels), so JPEG noise and faint
    grid lines don't count as content."""
    other = 1 - axis
    n = rgb.shape[other]
    if n > _SAMPLES:
        rgb = np.take(rgb, np.linspace(0, n - 1, _SAMPLES).astype(int), axis=other)
    med = np.median(rgb, axis=other)
    shape = (-1, 1, 3) if axis == 0 else (1, -1, 3)
    dist = np.abs(rgb.astype(np.int32) - med.reshape(shape)).sum(axis=-1)
    uniform = (dist <= tol).mean(axis=other) >= frac
    light = med.mean(axis=-1)
    gray = (light >= min_gray) & (med.max(axis=-1) - med.min(axis=-1) <= max_tint)
    return uniform & ((light >= min_light) | gray)


def _over_white(rgba):
    if rgba.shape[-1] == 3 or rgba[..., 3].min() == 255:  # opaque: no blending needed
        return rgba[..., :3]
    a = rgba[..., 3:4].astype(np.float32) / 255
    return (rgba[..., :3] * a + 255 * (1 - a)).astype(np.uint8)


def trim_border(rgba):
    """Crop plain light margins (white canvas, screenshot frame, drop shadow).

    Repeats on all sides, since a frame only turns into plain rows once the frame across
    the other axis is gone. Returns (cropped, (x0, y0, x1, y1))."""
    rgba = np.asarray(rgba)
    rgb = _over_white(rgba)
    y0, y1, x0, x1 = 0, rgb.shape[0], 0, rgb.shape[1]
    for _ in range(12):
        view = rgb[y0:y1, x0:x1]
        rows, cols = _plain_lines(view, 0), _plain_lines(view, 1)
        if rows.all() or cols.all():
            return rgba, (0, 0, rgba.shape[1], rgba.shape[0])
        t = int(np.argmin(rows))
        b = int(np.argmin(rows[::-1]))
        l = int(np.argmin(cols))
        r = int(np.argmin(cols[::-1]))
        if t == b == l == r == 0:
            break
        y0, y1, x0, x1 = y0 + t, y1 - b, x0 + l, x1 - r
    return rgba[y0:y1, x0:x1], (x0, y0, x1, y1)


def clear_background(rgba, min_lightness=92.0, max_chroma=8.0):
    """Empty the transparent or near-white cells that connect to the outside.

    White inside an outline (a face, a highlight) stays: a 4-neighbour flood fill from the
    edge cannot reach it."""
    rgba = np.asarray(rgba).copy()
    lab = rgb_to_lab(rgba[..., :3])
    chroma = np.hypot(lab[..., 1], lab[..., 2])
    bg = (rgba[..., 3] < ALPHA_CUTOFF) | ((lab[..., 0] >= min_lightness) & (chroma <= max_chroma))
    ny, nx = bg.shape
    reach = np.zeros_like(bg)
    stack = [(y, x) for y in range(ny) for x in (0, nx - 1)] + \
            [(y, x) for x in range(nx) for y in (0, ny - 1)]
    while stack:
        y, x = stack.pop()
        if 0 <= y < ny and 0 <= x < nx and bg[y, x] and not reach[y, x]:
            reach[y, x] = True
            stack += [(y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)]
    rgba[reach, 3] = 0
    return rgba


def content_box(rgba):
    """(x0, y0, x1, y1) of the cells that hold a bead; the whole array if there are none."""
    solid = np.asarray(rgba)[..., 3] >= ALPHA_CUTOFF
    if not solid.any():
        return 0, 0, solid.shape[1], solid.shape[0]
    ys, xs = np.nonzero(solid)
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def crop_to_content(rgba):
    """Drop empty outer rows and columns."""
    x0, y0, x1, y1 = content_box(rgba)
    return rgba[y0:y1, x0:x1]
