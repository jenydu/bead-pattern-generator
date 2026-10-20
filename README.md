# Pixel Art to Beads (PA2B)

A minimalistic bead and cross-stitch pattern generator specialized for pixel art. Supports a variety of brands, including MARD, Perler, DMC, and more.

**[Open the generator](https://jenydu.github.io/pixel-art-to-beads/)**: it runs entirely in your browser, and your image is never uploaded.

## What makes it different

Most pattern generators take a photo and shrink it to a grid of beads, which blurs edges and loses detail. This one starts from the other end: your image is already pixel art, so the job is to recover that art exactly.

Pixel art found online rarely arrives clean. It has been scaled up by some odd factor, stretched, saved as a JPEG, blurred by a resize, screenshotted with a frame and drop shadow, or drawn over an editor's grid lines. The generator works out the real pixel grid, looks at the middle of each pixel where the damage is smallest, and puts back one clean color per pixel. Then it matches those colors to the beads or thread you pick. A 32 x 32 sprite saved as a 3200 x 3200 JPEG comes out as the 32 x 32 sprite.

## Features

**Cleaning up the image**
- Finds the true pixel size, including fractional scales and pixels that are wider than they are tall, and tolerates blur and JPEG artifacts.
- Trims borders: screenshot frames, drop shadows and white margins. Faint editor grid lines are ignored.
- Empties the white or transparent background, while keeping white that sits inside the artwork.
- "Merge similar colors" folds leftover stray shades into one color.
- Pictures with no pixel grid are treated as ordinary photos and shrunk to a bead-sized grid, and you can always set the grid size yourself (the proportions stay locked).

**Making the pattern**
- Matches every color to the nearest bead or thread in perceptual (CIELAB, CIEDE2000) distance.
- Color swap: see which image color became which bead, and send any one of them to a different, similar bead.
- Chart cells show the bead code or a symbol. Symbols are the default for brands with long or purely numeric codes (Perler, DMC).
- Pegboard size (52 by default) splits larger patterns into boards, each numbered from 1, with red board lines on the full sheet.
- Bead list with counts and a total, ordered by code or by count.

**Viewing and exporting**
- The chart fits your screen; zoom with the buttons, pinch or Ctrl/Cmd + scroll, drag to pan, and step through boards with Prev / Next or show them all.
- Download a PNG sheet (chart plus bead counts) or print / save as PDF. Charts are vector graphics, so they stay sharp when zoomed or printed. Files are named `<brand>_<your file name>`.
- Works on phones and desktops.

## Supported brands

| Brand | Colors | Codes look like | Source |
| --- | ---: | --- | --- |
| MARD (full) | 291 | A1, B12, ZG3 | [beadcolors](https://github.com/maxcleme/beadcolors), values from the [pixel-beads.com MARD chart (2026 revised edition)](https://www.pixel-beads.com/mard-bead-color-chart) |
| MARD (basic) | 221 | A1 ... H23, M1 ... M15 | Series A-H and M of the full chart, which is how pixel-beads.com defines the standard 221 range |
| Perler | 103 | 80-15179 | [beadcolors](https://github.com/maxcleme/beadcolors) |
| Perler Mini | 41 | 80-15179 | beadcolors |
| Perler Caps | 26 | 80-16086 | beadcolors |
| Hama Midi | 92 | H01 | beadcolors |
| Hama Mini | 78 | H01 | beadcolors |
| Hama Maxi | 25 | H01 | beadcolors |
| Nabbi | 30 | N01 | beadcolors |
| Artkal A (2.6 mm) | 145 | A01 | beadcolors |
| Artkal C (2.6 mm) | 174 | C01 | beadcolors |
| Artkal M (2.6 mm) | 220 | MA1 | beadcolors |
| Artkal R (5 mm) | 89 | R01 | beadcolors |
| Artkal S (5 mm) | 199 | S01 | beadcolors |
| Yant | 119 | Y002 | beadcolors |
| DMC (cross-stitch thread) | 454 | 310, 3865, B5200 | [threadcolors.com](https://threadcolors.com/), scraped by `tools/scrape_threadcolors.py` |

The bead colors come from [beadcolors](https://github.com/maxcleme/beadcolors), a community-maintained collection (MIT licensed; the contributors are credited in `data/palettes/*.csv`). `build.py` copies it into `data/palettes/`. The beadcolors repo also lists Diamond Dotz, which is copied but not offered, since those are not fuse beads.

All colors are on-screen approximations. Real beads and thread vary with the batch, and so does how they look under different light, so check a swatch before a big project.

## How it works

1. **Trim** plain light borders and frames from the image.
2. **Detect the grid**: edge strength along each axis forms a repeating pattern whose period is the pixel size and whose phase is the grid offset. Only a spread of sampled rows and columns is read, so a huge image is no slower than a small one.
3. **Sample** the median color of the middle of every cell, clear the background, and merge near-identical shades.
4. **Match** each color to the chosen palette, then count and render.

The Python runs in your browser through [Pyodide](https://pyodide.org/) (numpy and Pillow in WebAssembly); the page itself is plain HTML, CSS and JavaScript with no build step. `ARCHITECTURE.md` has the details.

## Limits

- Very blurry, sparse art can fall back to "no grid found"; enter the grid size by hand in that case.
- Images scaled up by 2x or less are not detected automatically.
- Images much larger than about 4000 px per side may exhaust the browser's memory.

## Run locally

```
pip install numpy pillow pytest openpyxl
python build.py                 # sync ../beadcolors/raw, build dmc.csv, stage web/py
python -m http.server -d web    # open http://localhost:8000
python cli.py image.png --brand mard_291 --board 52 --out out/    # same pipeline, in the terminal
python -m pytest
```

`python tools/scrape_threadcolors.py` re-downloads the DMC table. Pushing to `main` deploys `web/` to GitHub Pages through `.github/workflows/pages.yml` (set Pages to "GitHub Actions" in the repository settings).
