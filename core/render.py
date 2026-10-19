"""Draw a Pattern as PNG: chart tiles (bead code in each cell) and a full printable sheet."""
import io

import numpy as np
from PIL import Image, ImageDraw, ImageFont

GRID_MINOR = (205, 205, 205)
GRID_MAJOR = (110, 110, 110)
BOARD_LINE = (214, 40, 57)
INK = (25, 25, 25)
MUTED = (110, 110, 110)


def _font(size):
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # Pillow < 10.1
        return ImageFont.load_default()


def _text_color(rgb):
    r, g, b = (int(v) for v in rgb)
    return (0, 0, 0) if 0.299 * r + 0.587 * g + 0.114 * b > 140 else (255, 255, 255)


def _bold(d, xy, text, fill, font, anchor="mm", weight=1):
    """Pillow only ships a regular face; a stroke in the same color makes it bold."""
    d.text(xy, text, fill=fill, font=font, anchor=anchor, stroke_width=weight, stroke_fill=fill)


def render_chart(pattern, x0=0, y0=0, x1=None, y1=None, cell=44, major=5,
                 local_numbers=False, board=None):
    """Render cells [y0:y1, x0:x1] with every row/column numbered. Returns a PIL image.

    local_numbers: number from 1 at the top-left of this crop (for a pegboard tile),
    otherwise numbers are positions in the whole pattern. board: draw red lines between
    boards of that many cells (whole-pattern coordinates)."""
    ny, nx = pattern.shape
    x1 = nx if x1 is None else x1
    y1 = ny if y1 is None else y1
    w, h = x1 - x0, y1 - y0
    margin = int(cell * 0.8)
    img = Image.new("RGB", (margin + w * cell + 2, margin + h * cell + 2), "white")
    d = ImageDraw.Draw(img)
    code_font = _font(max(int(cell * 0.38), 9))
    num_font = _font(max(int(cell * 0.32), 9))
    for j in range(h):
        for i in range(w):
            idx = pattern.cells[y0 + j, x0 + i]
            if idx < 0:
                continue
            px, py = margin + i * cell, margin + j * cell
            rgb = tuple(int(v) for v in pattern.palette.rgb[idx])
            d.rectangle([px, py, px + cell, py + cell], fill=rgb)
            _bold(d, (px + cell / 2 + 1, py + cell / 2 + 1), pattern.palette.refs[idx],
                  _text_color(rgb), code_font, weight=0 if cell < 30 else 1)

    def number(pos, local):
        return local if local_numbers else pos + local

    for i in range(w + 1):
        n = number(x0, i)
        major_line = n % major == 0
        x = margin + i * cell
        d.line([x, margin, x, margin + h * cell], fill=GRID_MAJOR if major_line else GRID_MINOR,
               width=2 if major_line else 1)
    for j in range(h + 1):
        n = number(y0, j)
        major_line = n % major == 0
        y = margin + j * cell
        d.line([margin, y, margin + w * cell, y], fill=GRID_MAJOR if major_line else GRID_MINOR,
               width=2 if major_line else 1)
    if board:
        for i in range(w + 1):
            if (x0 + i) % board == 0 and 0 < x0 + i < nx:
                x = margin + i * cell
                d.line([x, margin, x, margin + h * cell], fill=BOARD_LINE, width=4)
        for j in range(h + 1):
            if (y0 + j) % board == 0 and 0 < y0 + j < ny:
                y = margin + j * cell
                d.line([margin, y, margin + w * cell, y], fill=BOARD_LINE, width=4)
    for i in range(w):
        _bold(d, (margin + i * cell + cell / 2, margin / 2), str(number(x0, i + 1)), INK,
              num_font, weight=0)
    for j in range(h):
        _bold(d, (margin / 2, margin + j * cell + cell / 2), str(number(y0, j + 1)), INK,
              num_font, weight=0)
    return img


def tile_boxes(shape, tile=(32, 40), board=None):
    """(x0, y0, x1, y1) crops covering (ny, nx).

    With board: pegboard-sized squares from the top-left (edge ones may be smaller).
    Otherwise evenly sized pieces of at most tile=(cols, rows)."""
    ny, nx = shape
    if board:
        return [(x, y, min(x + board, nx), min(y + board, ny))
                for y in range(0, ny, board) for x in range(0, nx, board)]
    cols, rows = -(-nx // tile[0]), -(-ny // tile[1])
    xs = [round(i * nx / cols) for i in range(cols + 1)]
    ys = [round(i * ny / rows) for i in range(rows + 1)]
    return [(xs[i], ys[j], xs[i + 1], ys[j + 1]) for j in range(rows) for i in range(cols)]


def render_preview(pattern, scale=12):
    """Small unlabeled overview of the whole pattern."""
    img = Image.fromarray(pattern.rgb_image())
    return img.resize((img.width * scale, img.height * scale), Image.NEAREST)


def render_sheet(pattern, legend, title, board=None, show_groups=False, cell=44):
    """Printable sheet: title, whole chart (red lines between boards), bead counts."""
    chart = render_chart(pattern, cell=cell, board=board)
    pad = 36
    width = max(chart.width, 900) + 2 * pad
    chip_w, chip_h, gap = 190, 52, 14
    title_font, sub_font = _font(40), _font(22)
    chip_font, count_font, fam_font = _font(24), _font(26), _font(22)

    # lay the legend out first so the sheet height is known
    items, x, y = [], pad, 0
    per_row = max((width - 2 * pad + gap) // (chip_w + gap), 1)
    last, col = None, 0
    for c in legend:
        if show_groups and c["group"] != last:
            if col:
                y += chip_h + gap
            items.append(("family", c["group"], pad, y))
            y += 34
            last, col = c["group"], 0
        if col == per_row:
            y += chip_h + gap
            col = 0
        items.append(("chip", c, pad + col * (chip_w + gap), y))
        col += 1
    legend_h = y + chip_h

    head = 110
    sheet = Image.new("RGB", (width, head + chart.height + 30 + legend_h + pad), "white")
    d = ImageDraw.Draw(sheet)
    d.text((pad, 24), title, fill=INK, font=title_font)
    sub = f"{pattern.shape[1]} x {pattern.shape[0]} cells"
    if board:
        sub += f", red lines every {board} cells (one pegboard)"
    d.text((pad, 74), sub, fill=MUTED, font=sub_font)
    sheet.paste(chart, (pad, head))
    top = head + chart.height + 30
    for kind, c, x, y in items:
        y += top
        if kind == "family":
            d.text((x, y), c, fill=MUTED, font=fam_font)
            continue
        d.rounded_rectangle([x, y, x + chip_w, y + chip_h], radius=8, outline=(190, 190, 190),
                            width=2, fill=(250, 250, 250))
        rgb = tuple(c["rgb"])
        d.rounded_rectangle([x + 6, y + 6, x + 96, y + chip_h - 6], radius=6, fill=rgb)
        _bold(d, (x + 51, y + chip_h / 2 + 1), c["ref"], _text_color(rgb), chip_font)
        d.text((x + chip_w - 12, y + chip_h / 2 + 1), str(c["count"]), fill=INK,
               font=count_font, anchor="rm")
    return sheet


def to_png(img):
    b = io.BytesIO()
    img.save(b, "PNG")
    return b.getvalue()
