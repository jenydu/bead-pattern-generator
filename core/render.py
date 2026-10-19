"""Draw a Pattern as PNG chart pages (cell color + bead code, gridlines every 5/10)."""
import io

import numpy as np
from PIL import Image, ImageDraw, ImageFont

GRID_MINOR = (200, 200, 200)
GRID_MAJOR = (90, 90, 90)


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _text_color(rgb):
    r, g, b = (int(v) for v in rgb)
    return (0, 0, 0) if 0.299 * r + 0.587 * g + 0.114 * b > 140 else (255, 255, 255)


def render_chart(pattern, x0=0, y0=0, x1=None, y1=None, cell=30, major=5, labels=True):
    """Render cells [y0:y1, x0:x1] with row/column numbers. Returns a PIL image."""
    ny, nx = pattern.shape
    x1 = nx if x1 is None else x1
    y1 = ny if y1 is None else y1
    w, h = x1 - x0, y1 - y0
    margin = int(cell * 0.9)
    img = Image.new("RGB", (margin + w * cell + 1, margin + h * cell + 1), "white")
    d = ImageDraw.Draw(img)
    code_font, num_font = _font(max(cell // 3, 8)), _font(max(cell // 3, 8))
    for j in range(h):
        for i in range(w):
            idx = pattern.cells[y0 + j, x0 + i]
            px, py = margin + i * cell, margin + j * cell
            if idx < 0:
                continue
            rgb = tuple(int(v) for v in pattern.palette.rgb[idx])
            d.rectangle([px, py, px + cell, py + cell], fill=rgb)
            if labels:
                d.text((px + cell / 2, py + cell / 2), pattern.palette.refs[idx],
                       fill=_text_color(rgb), font=code_font, anchor="mm")
    for i in range(w + 1):
        gx = x0 + i
        c = GRID_MAJOR if gx % major == 0 else GRID_MINOR
        d.line([margin + i * cell, margin, margin + i * cell, margin + h * cell], fill=c)
    for j in range(h + 1):
        gy = y0 + j
        c = GRID_MAJOR if gy % major == 0 else GRID_MINOR
        d.line([margin, margin + j * cell, margin + w * cell, margin + j * cell], fill=c)
    for i in range(w):
        n = x0 + i + 1
        if n % major == 0 or i == 0:
            d.text((margin + i * cell + cell / 2, margin / 2), str(n), fill="black",
                   font=num_font, anchor="mm")
    for j in range(h):
        n = y0 + j + 1
        if n % major == 0 or j == 0:
            d.text((margin / 2, margin + j * cell + cell / 2), str(n), fill="black",
                   font=num_font, anchor="mm")
    return img


def tile_boxes(shape, tile=(32, 40)):
    """Split (ny, nx) into evenly sized (x0, y0, x1, y1) tiles of at most tile=(cols, rows)."""
    ny, nx = shape
    cols, rows = -(-nx // tile[0]), -(-ny // tile[1])
    xs = [round(i * nx / cols) for i in range(cols + 1)]
    ys = [round(i * ny / rows) for i in range(rows + 1)]
    return [(xs[i], ys[j], xs[i + 1], ys[j + 1]) for j in range(rows) for i in range(cols)]


def render_preview(pattern, scale=12):
    """Small unlabeled overview of the whole pattern."""
    img = Image.fromarray(pattern.rgb_image())
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)


def to_png(img):
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()
