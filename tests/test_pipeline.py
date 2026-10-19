import io
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.clean import sample_cells, unify_colors
from core.grid_detect import detect_grid
from core.palette import load_palette
from core.pattern import build_pattern
from core.render import render_chart, tile_boxes

SAMPLE = Path("/Users/u1082736/Downloads/cataloe-128.png")


def make_art(n, seed=0, k=8):
    rng = np.random.default_rng(seed)
    pal = rng.integers(0, 256, (k, 3))
    a = np.zeros((n, n), int)
    yy, xx = np.mgrid[:n, :n]
    for _ in range(25):
        cy, cx = rng.uniform(0, n, 2)
        ry, rx = rng.uniform(1, n / 5, 2)
        m = ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 < 1
        a[m] = rng.integers(1, k)
    return pal[a].astype(np.uint8)


def upscale(art, scale, resample=Image.NEAREST, jpeg=None):
    im = Image.fromarray(art).resize(
        (round(art.shape[1] * scale), round(art.shape[0] * scale)), resample)
    if jpeg:
        b = io.BytesIO()
        im.save(b, "JPEG", quality=jpeg)
        im = Image.open(b).convert("RGB")
    return np.array(im)


@pytest.mark.parametrize("n,scale", [(32, 4), (32, 7), (48, 10), (40, 5), (32, 3.37)])
def test_detect_sharp_upscale(n, scale):
    g = detect_grid(upscale(make_art(n, seed=n), scale))
    assert (g.nx, g.ny) == (n, n)
    assert g.period_x == pytest.approx(scale, rel=0.01)


def test_detect_jpeg_noise():
    g = detect_grid(upscale(make_art(32, seed=3), 6, jpeg=70))
    assert (g.nx, g.ny) == (32, 32)


def test_detect_one_to_one():
    g = detect_grid(make_art(48, seed=5))
    assert g.period_x == 1.0 and (g.nx, g.ny) == (48, 48)


def test_roundtrip_recovers_art():
    art = make_art(32, seed=2)
    img = upscale(art, 6, jpeg=80)
    g = detect_grid(img)
    cells = sample_cells(img, g)
    cells = unify_colors(cells, 10)
    assert cells.shape[:2] == art.shape[:2]
    close = np.abs(cells[..., :3].astype(int) - art.astype(int)).sum(axis=-1) < 40
    assert close.mean() > 0.98


def test_unify_merges_close_colors():
    a = np.zeros((2, 2, 4), np.uint8)
    a[..., 3] = 255
    a[0, 0, :3] = (100, 100, 100)
    a[0, 1, :3] = (101, 100, 100)
    a[1, 0, :3] = (100, 100, 100)
    a[1, 1, :3] = (200, 0, 0)
    out = unify_colors(a, 3)
    assert (out[0, 1, :3] == (100, 100, 100)).all() and (out[1, 1, :3] == (200, 0, 0)).all()


def test_transparent_cells_have_no_bead():
    a = np.zeros((2, 2, 4), np.uint8)
    a[0, 0] = (255, 255, 255, 255)
    p = build_pattern(a, load_palette("mard"))
    assert p.cells[0, 0] >= 0 and (p.cells.ravel()[1:] == -1).all()
    assert sum(c["count"] for c in p.legend()) == 1


def test_legend_in_brand_order():
    pal = load_palette("mard")
    a = np.zeros((1, 3, 4), np.uint8)
    a[..., 3] = 255
    for i, ref in enumerate(["B1", "A10", "A2"]):
        a[0, i, :3] = pal.rgb[pal.refs.index(ref)]
    refs = [c["ref"] for c in build_pattern(a, pal).legend()]
    assert refs == sorted(refs, key=lambda r: (r[0], int(r[1:])))


def test_tiles_cover_pattern_evenly():
    boxes = tile_boxes((32, 61), tile=(32, 40))
    assert len(boxes) == 2  # 61 columns -> 2 tiles of ~30
    covered = np.zeros((32, 61), int)
    for x0, y0, x1, y1 in boxes:
        covered[y0:y1, x0:x1] += 1
    assert (covered == 1).all()


def test_render_chart_size():
    a = np.full((4, 6, 4), 255, np.uint8)
    img = render_chart(build_pattern(a, load_palette("mard")), cell=20)
    assert img.size == (18 + 6 * 20 + 1, 18 + 4 * 20 + 1)


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample image not available")
def test_sample_image():
    g = detect_grid(np.array(Image.open(SAMPLE).convert("RGBA")))
    assert (g.nx, g.ny, g.period_x) == (32, 32, 4.0)


def test_api_run():
    from core import api
    art = make_art(24, seed=1)
    buf = io.BytesIO()
    Image.fromarray(upscale(art, 5)).save(buf, "PNG")
    out = api.run(buf.getvalue(), "mard")
    assert (out["grid"]["nx"], out["grid"]["ny"]) == (24, 24)
    assert out["legend"] and out["tiles"] and out["preview"][:4] == b"\x89PNG"
    out = api.run(buf.getvalue(), "perler", cells_x=12, cells_y=12)
    assert out["grid"]["manual"] and out["grid"]["nx"] == 12
