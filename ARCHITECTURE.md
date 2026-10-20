# Architecture

Pixel Art to Beads (PA2B) turns existing pixel art into a bead (or cross-stitch) chart in a chosen
brand's colors. Everything runs in the browser from static files on GitHub Pages: no server.

## How it runs

The image-processing code is plain Python (numpy + Pillow) that runs in the browser through
Pyodide (CPython on WebAssembly) inside a Web Worker. The JavaScript only draws the UI and passes
messages. The same `core/` runs under pytest and in a CLI. The first visit downloads about 10 MB
(Pyodide, numpy, Pillow); the browser caches it afterwards.

```
core/             pure Python, no browser imports
  grid_detect.py  find the true pixel grid of a scaled / blurred / compressed image
  clean.py        trim borders, sample one color per cell, clear the background, merge shades
  palette.py      brand palettes, RGB -> Lab, nearest color (CIEDE2000)
  pattern.py      Pattern: palette indices per cell, counts, legend, symbols, color-swap data
  pipeline.py     image -> Pattern (shared by the page and the CLI)
  render.py       Pattern -> SVG charts and sheet, PNG preview
  api.py          the entry points the page calls through Pyodide
data/             palettes/*.csv (generated, committed) and dmc_threadcolors.xlsx
web/              the GitHub Pages root: index.html style.css app.js viewer.js i18n.js worker.js
tools/            scrape_threadcolors.py
build.py          sync palettes, build dmc.csv, version the page files, stage web/py
cli.py            the same pipeline from the terminal
tests/
```

## Data

Row format of `data/palettes/*.csv`: `ref, name, r, g, b, contributor`, no header.

- **Bead brands** are copied by `build.py` from `../beadcolors/raw` (MIT; its LICENSE is kept next
  to them). Pages cannot read a sibling repo, so the snapshot is committed; rerun `build.py` to
  refresh. Diamond Dotz is skipped: it is diamond painting.
- **MARD** ships as `mard_291` (all of beadcolors' `mard.csv`) and `mard_221` (series A-H and M,
  the standard range according to pixel-beads.com).
- **DMC** comes from `data/dmc_threadcolors.xlsx` (454 threads, scraped from threadcolors.com by
  `tools/scrape_threadcolors.py`); `build.py` turns it into `dmc.csv`.
- `BRANDS` in `palette.py` lists the offered brands. Brands with long codes (Perler) and DMC
  default to symbols on the chart.

## Pipeline

```
image -> trim_border -> detect_grid -> sample_cells -> clear_background -> crop_to_content
      -> unify_colors -> match to palette (Pattern) -> render
```

**trim_border** crops plain light rows and columns on every side until stable, which removes
white canvas, screenshot frames and drop shadows. It tolerates JPEG noise and faint grid lines
and never trims a dark ring that is part of the art.

**detect_grid**
- Per axis, an edge profile is built from thresholded first and second differences, using at most
  256 evenly spread lines, so the cost does not depend on image size (3200 x 2000 takes ~0.05 s).
  Pixel borders form a periodic pulse train in it.
- In its spectrum the real pixel size is the lowest-frequency line whose harmonics are also
  strong. That rejects f/2 (weak odd harmonics) and multiples of f. The period is refined by a
  direct DFT and the phase comes from the DFT angle. If the image is almost exactly n cells wide
  the period snaps to width / n. First-difference edges decide whether the phase marks borders
  (sharp pixels) or cell centers (bilinear ramps).
- x and y get separate periods when they differ by more than 4% and are not a 2-4x harmonic
  (stretched pixels).
- No structure (under 0.1% edge pixels, or no spectral line above prominence 8): images up to
  150 px are used pixel for pixel, bigger ones are treated as a photo and averaged to 50 cells
  on the long side. The user can always type a grid size.
- Known limits: scales of 2x or less, and heavy blur on sparse art, can be missed.

**sample_cells** takes the median of each cell's central half, where blur and resampling damage
is smallest. **clear_background** empties near-white or transparent cells connected to the edge
(4-neighbour flood fill, so white inside an outline stays). **unify_colors** merges shades within
a small Lab distance, most common first.

**Matching** uses CIEDE2000 over the unique colors only. `Pattern.conversions()` lists each image
color, its bead and the 12 nearest alternatives; the page sends back `{rrggbb: ref}` swaps and
`build_pattern(swaps=...)` applies them per image color. Symbols are punctuation and shapes (no
letters or digits), assigned in code order so a color keeps its symbol.

**render** produces SVG, because text and lines stay sharp when zoomed, on high-DPI screens and
in a printed PDF, where a raster would be resampled. Pegboard size (default 52) splits the chart
into boards numbered from 1, with red board lines on the full sheet.

## Frontend

- `app.js` holds the state and renders results; `worker.js` loads Pyodide and calls `core.api`.
  Python files are fetched with `no-cache` so a new deploy never mixes old Python with a new page.
- `viewer.js` shows each chart part fitted to its box, with zoom (buttons, Ctrl/Cmd + wheel,
  pinch), drag to pan and double-click to toggle. Several boards are shown one at a time with
  Prev / Next, or all at once.
- Outputs: "Save PNG" / "Save PDF" open a new tab (inside the click, as browsers require) and
  fill it once the file exists; the user saves it from there. Both rasterize the SVGs on a
  canvas (capped at 12M pixels, since iOS Safari cannot go much higher). The PDF is written by a
  small builder in `app.js`: one deflated RGB image per A4 page, the sheet first and then one
  page per board.
- `i18n.js` holds the English and Simplified Chinese text (`t(key, values)`; `{name}` marks a
  filled-in value; `data-i18n` marks static HTML). The language is remembered in `localStorage`.
  Python never knows the language: the page passes the wording of the saved sheet to
  `api.run(texts=...)`. `tests/test_i18n.py` checks both languages have the same keys and
  placeholders. Color names and bead codes are not translated.
- The status message floats at the top while Python loads or an image is processed, so a phone
  user sees it. Settings are fixed in a card on wide screens and scroll on their own.
- `build.py` stamps the page's own files with a content hash (`style.css?v=...`) because GitHub
  Pages lets browsers reuse files for ten minutes.

## Deploy

`.github/workflows/pages.yml` runs the tests and `build.py --no-sync`, then publishes `web/`.
