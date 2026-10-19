"""Turn an image + detected grid into one color per pixel-art cell."""
import numpy as np

from .palette import rgb_to_lab


def sample_cells(arr, grid, window=0.5):
    """Median color of the central `window` fraction of every cell -> (ny, nx, 4) uint8.

    The cell borders are where blur and resampling artifacts live, so they are ignored.
    A 1:1 grid (period 1) simply returns the image."""
    arr = np.asarray(arr)
    if arr.ndim == 2:
        arr = np.stack([arr] * 3, axis=-1)
    if arr.shape[2] == 3:
        arr = np.concatenate([arr, np.full(arr.shape[:2] + (1,), 255, arr.dtype)], axis=2)
    h, w = arr.shape[:2]
    xe, ye = grid.x_edges(), grid.y_edges()
    out = np.zeros((grid.ny, grid.nx, 4), np.uint8)
    for j in range(grid.ny):
        y0, y1 = _span(ye[j], ye[j + 1], window, h)
        for i in range(grid.nx):
            x0, x1 = _span(xe[i], xe[i + 1], window, w)
            out[j, i] = np.median(arr[y0:y1, x0:x1].reshape(-1, 4), axis=0)
    return out


def _span(a, b, window, limit):
    """Pixel index range of the central part of [a, b), clipped to the image, >= 1 px."""
    lo, hi = max(a, 0.0), min(b, float(limit))
    mid, half = (lo + hi) / 2, max((hi - lo) * window / 2, 0.5)
    i0 = int(np.clip(np.floor(mid - half + 0.5), 0, limit - 1))
    i1 = int(np.clip(np.ceil(mid + half - 0.5), i0 + 1, limit))
    return i0, i1


def unify_colors(rgba, tolerance=6.0, alpha_cutoff=128):
    """Merge near-identical colors (left over from blur / JPEG) into the most common one.

    Greedy: colors are visited by popularity; each joins the first kept color within
    `tolerance` (CIE76 distance in Lab), otherwise becomes a new kept color."""
    rgba = np.asarray(rgba)
    out = rgba.copy()
    solid = rgba[..., 3] >= alpha_cutoff
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
    rgb = out[..., :3]
    rgb[solid] = colors[target[inv.reshape(-1)]]
    out[..., :3] = rgb
    return out


def transparent_mask(rgba, alpha_cutoff=128):
    return np.asarray(rgba)[..., 3] < alpha_cutoff
