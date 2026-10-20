import io
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from core.clean import (clear_background, crop_to_content, sample_cells, trim_border,
                        unify_colors)
from core.grid_detect import detect_grid
from core.palette import load_palette
from core.pattern import build_pattern
from core.render import render_chart, render_sheet, tile_boxes

SAMPLE = Path("/Users/u1082736/Downloads/cataloe-128.png")


def make_art(n, seed=0, k=8, m=None):
    """n rows x m columns (square by default) of random ellipses on a plain background."""
    m = m or n
    rng = np.random.default_rng(seed)
    pal = rng.integers(0, 256, (k, 3))
    a = np.zeros((n, m), int)
    yy, xx = np.mgrid[:n, :m]
    for _ in range(max(25, n * m // 40)):
        cy, cx = rng.uniform(0, n), rng.uniform(0, m)
        ry, rx = rng.uniform(1, n / 5), rng.uniform(1, m / 5)
        inside = ((yy - cy) / ry) ** 2 + ((xx - cx) / rx) ** 2 < 1
        a[inside] = rng.integers(1, k)
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


@pytest.mark.parametrize("nx,ny,scale", [(48, 20, 6), (20, 60, 7), (60, 30, 8), (64, 40, 50)])
def test_detect_non_square(nx, ny, scale):
    g = detect_grid(upscale(make_art(ny, seed=nx, m=nx), scale))
    assert (g.nx, g.ny) == (nx, ny)
    assert g.period_x == pytest.approx(scale, rel=0.01)


def test_detect_large_image_is_fast():
    import time
    img = upscale(make_art(32, seed=7), 100)  # 3200 x 3200
    t = time.time()
    g = detect_grid(img)
    assert (g.nx, g.ny) == (32, 32) and time.time() - t < 2


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
    p = build_pattern(a, load_palette("mard_291"))
    assert p.cells[0, 0] >= 0 and (p.cells.ravel()[1:] == -1).all()
    assert sum(c["count"] for c in p.legend()) == 1


def test_legend_in_brand_order():
    pal = load_palette("mard_291")
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


def test_render_chart_is_vector_svg():
    pal = load_palette("mard_291")
    a = np.zeros((2, 3, 4), np.uint8)
    a[..., 3] = 255
    a[0, 0, :3] = pal.rgb[pal.refs.index("A1")]
    p = build_pattern(a, pal)
    svg = render_chart(p, cell=20)
    ET.fromstring(svg)  # well-formed XML, or the browser shows a broken image
    assert svg.startswith("<svg") and svg.endswith("</svg>")
    assert ">A1</text>" in svg and "font-weight" not in svg  # real text, not bold
    assert 'width="78"' in svg  # margin 16 + 3 cells * 20 + 2


def test_sheet_lists_counts_in_legend_order():
    p = _three_color_pattern()
    svg = render_sheet(p, p.legend(), "T & <x>")
    ET.fromstring(svg)
    assert "T &amp; &lt;x&gt;" in svg and ">A10<" in svg


@pytest.mark.skipif(not SAMPLE.exists(), reason="sample image not available")
def test_sample_image():
    g = detect_grid(np.array(Image.open(SAMPLE).convert("RGBA")))
    assert (g.nx, g.ny, g.period_x) == (32, 32, 4.0)


def test_api_run():
    from core import api
    art = make_art(24, seed=1)
    buf = io.BytesIO()
    Image.fromarray(upscale(art, 5)).save(buf, "PNG")
    out = api.run(buf.getvalue(), "mard_291")
    assert (out["grid"]["nx"], out["grid"]["ny"]) == (24, 24)
    assert out["legend"] and out["tiles"] and out["preview"][:4] == b"\x89PNG" and out["sheet"].startswith("<svg")
    out = api.run(buf.getvalue(), "perler", cells_x=12, cells_y=12)
    assert out["grid"]["manual"] and out["grid"]["nx"] == 12


def _three_color_pattern():
    pal = load_palette("mard_291")
    a = np.zeros((1, 4, 4), np.uint8)
    a[..., 3] = 255
    for i, ref in enumerate(["B1", "A10", "H7", "A10"]):
        a[0, i, :3] = pal.rgb[pal.refs.index(ref)]
    return build_pattern(a, pal)


def test_legend_orders():
    p = _three_color_pattern()
    assert [c["ref"] for c in p.legend("code")] == ["A10", "B1", "H7"]
    assert [c["ref"] for c in p.legend("count")][0] == "A10"
    with pytest.raises(ValueError):
        p.legend("nope")


def test_board_tiles():
    boxes = tile_boxes((40, 70), board=29)
    assert len(boxes) == 3 * 2  # 70 cols -> 3 boards wide, 40 rows -> 2 boards tall
    assert boxes[0] == (0, 0, 29, 29) and boxes[-1] == (58, 29, 70, 40)


def test_api_board_and_order():
    from core import api
    buf = io.BytesIO()
    Image.fromarray(upscale(make_art(40, seed=1, m=70), 5)).save(buf, "PNG")
    out = api.run(buf.getvalue(), "mard_221", board=29, order="count")
    assert (out["grid"]["nx"], out["grid"]["ny"]) == (70, 40)
    assert len(out["tiles"]) == 6 and out["tiles"][4]["board"] == [2, 2]
    assert out["total"] == sum(c["count"] for c in out["legend"])


def test_non_square_image():
    from core import api
    buf = io.BytesIO()
    Image.fromarray(upscale(make_art(20, seed=2, m=48), 6)).save(buf, "PNG")
    assert api.run(buf.getvalue())["grid"]["nx"] == 48


def test_trim_border_removes_frame_shadow_and_canvas():
    art = make_art(24, seed=11)
    img = upscale(art, 10)  # 240 x 240
    framed = np.full((400, 420, 3), 185, np.uint8)  # gray frame
    framed[40:380, 40:400] = 255  # white canvas
    framed[378:388, 44:404] = 225  # faint shadow strip below/right of the canvas
    framed[100:340, 90:330] = img
    cropped, (x0, y0, x1, y1) = trim_border(framed)
    assert abs(x0 - 90) <= 12 and abs(y0 - 100) <= 12
    assert abs(cropped.shape[1] - 240) <= 24 and abs(cropped.shape[0] - 240) <= 24


def test_trim_keeps_dark_ring_that_is_part_of_the_art():
    art = make_art(16, seed=2)
    art[0, :] = art[-1, :] = art[:, 0] = art[:, -1] = 0  # black ring
    img = upscale(art, 8)
    assert trim_border(img)[0].shape[:2] == img.shape[:2]


def test_gridlines_on_white_do_not_confuse_detection():
    art = np.full((20, 30, 3), 255, np.uint8)
    art[5:15, 8:22] = make_art(10, seed=4, m=14)
    art[5:15, 8:22][art[5:15, 8:22].sum(-1) > 700] = (30, 30, 30)
    img = upscale(art, 12).copy()
    img[::12, :] = 235  # faint editor grid
    img[:, ::12] = 235
    g = detect_grid(trim_border(img)[0])
    assert g.period_x == pytest.approx(12, rel=0.01)


def test_stretched_pixels_get_separate_periods():
    art = make_art(24, seed=5, m=32)
    im = Image.fromarray(art).resize((32 * 17, 24 * 15), Image.NEAREST)
    g = detect_grid(np.array(im))
    assert (g.nx, g.ny) == (32, 24)
    assert g.period_x == pytest.approx(17, rel=0.01) and g.period_y == pytest.approx(15, rel=0.01)


def test_clear_background_keeps_enclosed_white():
    a = np.zeros((5, 5, 4), np.uint8)
    a[..., :3] = 255
    a[..., 3] = 255
    a[1, 1:4] = a[3, 1:4] = (0, 0, 0, 255)
    a[2, 1] = a[2, 3] = (0, 0, 0, 255)  # ring around the white cell at (2, 2)
    out = clear_background(a)
    assert out[0, 0, 3] == 0 and out[4, 4, 3] == 0   # outside is empty
    assert out[2, 2, 3] == 255                       # enclosed white stays a bead


def test_crop_to_content():
    a = np.zeros((6, 6, 4), np.uint8)
    a[2:4, 1:3] = 255
    assert crop_to_content(a).shape[:2] == (2, 2)


def test_photo_without_pixel_grid_is_shrunk_not_exploded():
    from core import api
    rng = np.random.default_rng(0)
    yy, xx = np.mgrid[:400, :600]
    photo = np.stack([127 + 120 * np.sin(xx / 70), 127 + 120 * np.sin(yy / 50),
                      127 + 120 * np.sin((xx + yy) / 90)], -1)
    photo = np.clip(photo + rng.normal(0, 3, photo.shape), 0, 255).astype(np.uint8)
    buf = io.BytesIO()
    Image.fromarray(photo).save(buf, "PNG")
    out = api.run(buf.getvalue())
    assert out["kind"] == "photo"
    assert out["grid"]["nx"] == 50 and out["grid"]["ny"] == 33
    assert api.run(buf.getvalue(), cells_x=20, cells_y=13)["grid"]["nx"] == 20


def test_tiny_image_is_taken_pixel_for_pixel():
    from core import api
    buf = io.BytesIO()
    Image.fromarray(make_art(24, seed=9)).save(buf, "PNG")
    out = api.run(buf.getvalue())
    assert out["kind"] == "pixels" and out["grid"]["nx"] == 24


def test_unknown_or_empty_brand_falls_back_to_default():
    from core import api
    buf = io.BytesIO()
    Image.fromarray(upscale(make_art(16, seed=3), 6)).save(buf, "PNG")
    assert api.run(buf.getvalue(), brand="")["legend"]


def test_symbols_are_unique_stable_and_not_alphanumeric():
    from core.pattern import SYMBOLS
    assert len(set(SYMBOLS)) == len(SYMBOLS)
    assert not any(ch.isalnum() for s in SYMBOLS for ch in s)
    p = _three_color_pattern()
    sym = p.symbol_map()
    assert len(set(sym.values())) == len(sym) == 3
    # a color keeps its symbol whatever order the bead list is shown in
    by_ref = lambda order: {c["ref"]: c["symbol"] for c in p.legend(order)}
    assert by_ref("code") == by_ref("count")


def test_symbol_chart_and_sheet_render():
    p = _three_color_pattern()
    svg = render_chart(p, labels="symbol")
    ET.fromstring(svg)
    assert ">A1<" not in svg and any(s in svg for s in p.symbol_map().values())
    sheet = render_sheet(p, p.legend(), "t", labels="symbol")
    ET.fromstring(sheet)


def test_long_code_brands_prefer_symbols():
    assert load_palette("perler").prefers_symbols and load_palette("dmc").prefers_symbols
    assert not load_palette("mard_291").prefers_symbols and not load_palette("hama").prefers_symbols


def test_color_swap_changes_one_source_color_only():
    pal = load_palette("mard_291")
    a = np.zeros((1, 3, 4), np.uint8)
    a[..., 3] = 255
    a[0, 0, :3] = (10, 120, 40)    # two similar greens...
    a[0, 1, :3] = (12, 122, 42)
    a[0, 2, :3] = (240, 240, 20)
    base = build_pattern(a, pal)
    assert base.cells[0, 0] == base.cells[0, 1]  # ...land on the same bead
    rows = base.conversions()
    assert {r["count"] for r in rows} == {1} and len(rows) == 3
    row = next(r for r in rows if r["src"] == [12, 122, 42])
    other = next(c["ref"] for c in row["candidates"] if c["ref"] != row["ref"])
    swapped = build_pattern(a, pal, swaps={"0c7a2a": other, "zz": "A1", "0a7828": "NOPE"})
    assert pal.refs[swapped.cells[0, 1]] == other
    assert swapped.cells[0, 0] == base.cells[0, 0] and swapped.cells[0, 2] == base.cells[0, 2]
    assert next(r for r in swapped.conversions() if r["src"] == [12, 122, 42])["swapped"]


def test_api_swaps_labels_and_conversions():
    import json
    from core import api
    buf = io.BytesIO()
    Image.fromarray(upscale(make_art(20, seed=6), 6)).save(buf, "PNG")
    out = api.run(buf.getvalue(), brand="perler", labels="symbol")
    assert out["conversions"] and out["palette"] and out["legend"][0]["symbol"]
    row = out["conversions"][0]
    key = "%02x%02x%02x" % tuple(row["src"])
    pick = row["candidates"][-1]["ref"]
    out2 = api.run(buf.getvalue(), brand="perler", labels="symbol", swaps=json.dumps({key: pick}))
    assert next(r for r in out2["conversions"] if r["src"] == row["src"])["ref"] == pick
    assert any(b["symbols"] for b in api.brands())


def test_sheet_wording_can_be_translated():
    import json
    from core import api
    buf = io.BytesIO()
    Image.fromarray(upscale(make_art(20, seed=8), 6)).save(buf, "PNG")
    zh = {"brand": "MARD 291（完整版）", "title": "{brand} 拼豆图纸：{colors} 种颜色，共 {beads} 颗",
          "subtitle": "{cols} × {rows} 格", "subtitle_board": "{cols} × {rows} 格，红线表示每 {board} 格一块拼豆板"}
    sheet = api.run(buf.getvalue(), board=52, texts=json.dumps(zh))["sheet"]
    ET.fromstring(sheet)
    assert "MARD 291（完整版） 拼豆图纸：" in sheet and "20 × 20 格，红线表示每 52 格一块拼豆板" in sheet
    assert "PingFang SC" in sheet                      # a font that can draw the Chinese
    plain = api.run(buf.getvalue(), board=52)["sheet"]  # default wording unchanged
    assert "bead pattern:" in plain and "red lines every 52 cells" in plain
