const $ = (id) => document.getElementById(id);
const worker = new Worker("worker.js?v=24ac4c20");

let nextId = 1;
const pending = new Map();
worker.onmessage = (e) => {
  const { id, result, error } = e.data;
  const p = pending.get(id);
  pending.delete(id);
  if (p) error ? p.reject(new Error(error)) : p.resolve(result);
};
function call(msg) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, ...msg });
  });
}

let imageBytes = null;
let originalUrl = null;
let urls = [];
let timer = null;
let runToken = 0;
let custom = null;        // null = use the detected grid, else [columns, rows]
let detected = null;      // [columns, rows] found by Python
let lastResult = null;
let swaps = {};           // {"rrggbb": bead ref} chosen in the color swap panel
let swapOpen = false;
let openRow = null;       // hex of the swap row whose picker is open
let fileStem = "";        // uploaded file name without its extension
let brandInfo = {};       // key -> {symbols: bool}

// kind: "loading" (floating spinner banner), "error", or none
function setStatus(text, kind) {
  const s = $("status");
  s.textContent = text;
  s.className = kind || "";
  s.hidden = !text;
}

const blobUrl = (data, type) => {
  const url = URL.createObjectURL(new Blob([data], { type }));
  urls.push(url);
  return url;
};

async function refresh() {
  if (!imageBytes) return;
  if (!$("brand").value) {   // Python is still loading; the startup code calls refresh() again
    setStatus(t("loading_python"), "loading");
    return;
  }
  const token = ++runToken;
  if (!$("output").hidden) $("output").classList.add("busy");   // keep the old chart, dimmed
  setStatus(t("working"), "loading");
  try {
    const r = await call({
      type: "run",
      data: imageBytes.slice(),
      brand: $("brand").value,
      cx: custom ? custom[0] : 0,
      cy: custom ? custom[1] : 0,
      tol: parseFloat($("tol").value),
      board: parseInt($("board").value, 10) || 0,
      order: $("order").value,
      clean: $("clean").checked,
      labels: $("labels").value,
      swaps: JSON.stringify(swaps),
      texts: JSON.stringify({   // wording of the saved sheet, which Python draws
        brand: brandLabel($("brand").value),
        title: t("sheet_title"),
        subtitle: t("sheet_size"),
        subtitle_board: t("sheet_size_board"),
      }),
    });
    if (token !== runToken) return;
    show(r);
    setStatus("");
  } catch (err) {
    if (token === runToken) {
      $("output").hidden = true;
      setStatus(t("err_process") + err.message, "error");
    }
  } finally {
    if (token === runToken) $("output").classList.remove("busy");
  }
}

// ---- pixel grid panel ----

let lockRatio = null;   // rows per column fixed when the lock was switched on; null = the detected ratio
const ratio = () => lockRatio ?? (detected ? detected[1] / detected[0] : 1);

function setCustomInputs(cols, rows) {
  $("cx").value = cols;
  $("cy").value = rows;
  $("use-custom").disabled = !(cols > 0 && rows > 0);
}

// With the lock on, changing one custom dimension sets the other from the detected proportions.
const locked = () => $("lock").checked;
const rowsFor = (cols) => Math.max(1, Math.round(cols * ratio()));
const colsFor = (rows) => Math.max(1, Math.round(rows / ratio()));

$("cx").addEventListener("input", () => {
  const c = parseInt($("cx").value, 10);
  const rows = locked() ? (c > 0 ? rowsFor(c) : "") : $("cy").value;
  setCustomInputs(c > 0 ? c : "", rows);
});
$("cy").addEventListener("input", () => {
  const r = parseInt($("cy").value, 10);
  const cols = locked() ? (r > 0 ? colsFor(r) : "") : $("cx").value;
  setCustomInputs(cols, r > 0 ? r : "");
});
// Locking keeps the proportions the boxes have at that moment, not the detected ones.
$("lock").addEventListener("change", () => {
  const c = parseInt($("cx").value, 10), r = parseInt($("cy").value, 10);
  lockRatio = locked() && c > 0 && r > 0 ? r / c : null;
});
$("use-custom").addEventListener("click", () => {
  const c = parseInt($("cx").value, 10), r = parseInt($("cy").value, 10);
  if (c > 0 && r > 0) {
    custom = [Math.min(c, 200), Math.min(r, 200)];
    refresh();
  }
});
$("use-detected").addEventListener("click", () => {
  custom = null;
  lockRatio = null;
  if (detected) setCustomInputs(detected[0], detected[1]);
  refresh();
});

function describeGrid(r) {
  const g = r.grid, [dx, dy] = g.detected;
  if (g.manual) return t("g_custom_used", { nx: g.nx, ny: g.ny });
  if (r.kind === "photo") return t("g_photo", { dx, dy });
  if (r.kind === "pixels") return t("g_pixels", { dx, dy });
  const cropped = g.nx !== dx || g.ny !== dy ? t("g_cropped", { nx: g.nx, ny: g.ny }) : "";
  return t("g_detected_used", { p: g.period.toFixed(2), cropped });
}

// ---- chart: one zoomable viewer per part, shown one at a time or all ----

let viewers = [];
let figures = [];
let captions = [];
let positions = [];
let active = 0;
let viewAll = false;

function buildTiles(r) {
  const tiles = $("tiles");
  tiles.replaceChildren();
  viewers = [];
  figures = [];
  const n = r.tiles.length;
  positions = r.tiles.map((tile, i) =>
    n < 2 ? "" : tile.board ? t("pos_board", { i: i + 1, n }) : t("pos_part", { i: i + 1, n }));
  captions = r.tiles.map((tile, i) => {
    if (n < 2) return "";   // nothing to number
    const [x0, y0, x1, y1] = tile.box;
    const range = { c0: x0 + 1, c1: x1, r0: y0 + 1, r1: y1 };
    return tile.board
      ? t("cap_board", { i: i + 1, n, r: tile.board[0], c: tile.board[1], ...range })
      : t("cap_part", { i: i + 1, n, ...range });
  });
  r.tiles.forEach((tile, i) => {
    const fig = document.createElement("figure");
    fig.className = "tile";
    fig.style.margin = "0 0 1.5rem";
    const cap = document.createElement("figcaption");
    cap.textContent = captions[i];
    const v = new Viewer(blobUrl(tile.svg, "image/svg+xml"), { onKey: (d) => go(active + d) });
    fig.append(cap, v.el);
    tiles.append(fig);
    viewers.push(v);
    figures.push(fig);
  });
  active = Math.min(active, viewers.length - 1);
  updateView();
}

function go(i) {
  if (viewAll || i < 0 || i >= viewers.length) return;
  active = i;
  updateView();
  viewers[i].el.focus({ preventScroll: true });
}

function updateView() {
  const n = viewers.length;
  $("pager").hidden = n < 2;
  $("tiles").classList.toggle("slide", n > 1 && !viewAll);
  $("view-one").setAttribute("aria-pressed", String(!viewAll));
  $("view-all").setAttribute("aria-pressed", String(viewAll));
  $("nav").hidden = viewAll;
  $("pos").textContent = positions[active] ?? "";
  $("prev").disabled = active === 0;
  $("next").disabled = active === n - 1;
  figures.forEach((f, i) => f.classList.toggle("active", i === active));
  requestAnimationFrame(() => viewers.forEach((v) => v.layout()));
}

$("prev").addEventListener("click", () => go(active - 1));
$("next").addEventListener("click", () => go(active + 1));
$("view-one").addEventListener("click", () => { viewAll = false; updateView(); });
$("view-all").addEventListener("click", () => { viewAll = true; updateView(); });

// ---- results ----

// Empty the page while a different image is processed.
function clearResult() {
  $("output").hidden = true;
  $("output").classList.remove("busy");
  $("tiles").replaceChildren();
  viewers = []; figures = []; captions = []; positions = []; active = 0;
  for (const id of ["orig", "preview"]) $(id).removeAttribute("src");
  $("legend").tBodies[0].replaceChildren();
  $("swap-table").tBodies[0].replaceChildren();
  $("save-png").disabled = $("save-pdf").disabled = true;
  urls.forEach(URL.revokeObjectURL);
  urls = [];
  lastResult = null;
  $("gridbox").hidden = true;
  setCustomInputs("", "");
}

function show(r) {
  urls.forEach(URL.revokeObjectURL);
  urls = [];
  const g = r.grid;
  const firstTime = !detected || detected[0] !== g.detected[0] || detected[1] !== g.detected[1];
  detected = g.detected;
  if (firstTime && !custom) setCustomInputs(detected[0], detected[1]);

  $("gridbox").hidden = false;
  $("d-original").textContent = `${r.original[0]} × ${r.original[1]} px`;
  $("d-current").textContent = t("cells_n", { nx: g.nx, ny: g.ny });
  $("d-detected").textContent = `${detected[0]} × ${detected[1]}`;
  $("use-detected").disabled = false;
  $("cx").disabled = $("cy").disabled = false;
  $("gridinfo").textContent = describeGrid(r);

  $("orig").src = originalUrl;
  $("preview").src = blobUrl(r.preview, "image/png");
  $("cap-orig").textContent = t("cap_original", { w: r.original[0], h: r.original[1] });
  $("cap-preview").textContent = t("cap_pattern", { nx: g.nx, ny: g.ny });
  $("orig").alt = t("alt_original");
  $("preview").alt = t("alt_preview");
  $("summary").textContent = t("summary", { nx: g.nx, ny: g.ny, colors: r.legend.length, beads: r.total });

  buildTiles(r);

  const body = $("legend").tBodies[0];
  body.replaceChildren();
  for (const c of r.legend) {
    const tr = body.insertRow();
    const sw = document.createElement("span");
    sw.className = "swatch";
    sw.style.background = `rgb(${c.rgb.join(",")})`;
    if ($("labels").value === "symbol") {
      sw.textContent = c.symbol;
      sw.style.color = textOn(c.rgb);
    }
    tr.insertCell().append(sw);
    tr.insertCell().textContent = c.name === c.ref ? c.ref : `${c.ref} ${c.name}`;
    const n = tr.insertCell();
    n.className = "num";
    n.textContent = c.count;
  }
  $("total").textContent = r.total;

  lastResult = r;
  renderSwap();
  preparePng();
  $("save-png").disabled = $("save-pdf").disabled = false;
  $("output").hidden = false;
}

// ---- color swap ----

const hexOf = (rgb) => rgb.map((v) => v.toString(16).padStart(2, "0")).join("");
const textOn = (rgb) => (0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2] > 140 ? "#000" : "#fff");

function swatch(rgb, text) {
  const s = document.createElement("span");
  s.className = "swatch";
  s.style.background = `rgb(${rgb.join(",")})`;
  if (text) {
    s.textContent = text;
    s.style.color = textOn(rgb);
  }
  return s;
}

function applySwap(hex, ref, auto) {
  if (ref === auto) delete swaps[hex];
  else swaps[hex] = ref;
  refresh();
}

// Outline the cells of the open row's color on the pattern preview.
function highlight() {
  const frame = $("frame-preview");
  frame.querySelector(".marks")?.remove();
  const r = lastResult;
  const row = swapOpen && r && r.conversions.find((c) => hexOf(c.src) === openRow);
  if (!row) return;
  const nx = r.grid.nx;
  const NS = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(NS, "svg");
  svg.setAttribute("class", "marks");
  svg.setAttribute("viewBox", `0 0 ${nx} ${r.grid.ny}`);
  svg.setAttribute("preserveAspectRatio", "none");
  const path = document.createElementNS(NS, "path");
  path.setAttribute("d", row.cells.map((c) => `M${c % nx} ${Math.floor(c / nx)}h1v1h-1z`).join(""));
  svg.append(path);
  frame.append(svg);
}

function renderSwap() {
  const r = lastResult;
  $("swap").hidden = !swapOpen;
  $("swap-toggle").setAttribute("aria-expanded", String(swapOpen));
  $("swap-toggle").dataset.state = t(swapOpen ? "hide" : "show");
  $("swap-reset").disabled = Object.keys(swaps).length === 0;
  highlight();
  const body = $("swap-table").tBodies[0];
  body.replaceChildren();
  if (!swapOpen || !r) return;
  const palRgb = Object.fromEntries(r.palette.map((p) => [p.ref, p.rgb]));
  // grouped by the bead they became (in the brand's code order), biggest color first in each group
  const rows = [...r.conversions].sort((a, b) =>
    a.ref.localeCompare(b.ref, undefined, { numeric: true }) || b.count - a.count);
  for (const row of rows) {
    const hex = hexOf(row.src);
    const tr = body.insertRow();
    tr.className = "swaprow" + (row.swapped ? " swapped" : "") + (openRow === hex ? " open" : "");
    tr.tabIndex = 0;
    tr.setAttribute("role", "button");
    const toggle = () => { openRow = openRow === hex ? null : hex; renderSwap(); };
    tr.addEventListener("click", toggle);
    tr.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); toggle(); } });
    const a = tr.insertCell();
    a.append(swatch(row.src), ` #${hex}`);
    const b = tr.insertCell();
    b.append(swatch(palRgb[row.ref]), ` ${row.ref}`);
    if (row.swapped) b.append(t("swap_swapped"));
    const n = tr.insertCell();
    n.className = "num";
    n.textContent = row.count;
    if (openRow !== hex) continue;

    const pr = body.insertRow();
    pr.className = "picker";
    const cell = pr.insertCell();
    cell.colSpan = 3;
    const intro = document.createElement("p");
    intro.className = "note";
    intro.textContent = t("swap_replace", { ref: row.ref });
    cell.append(intro);
    const list = document.createElement("div");
    list.className = "cands";
    for (const c of row.candidates) {
      const btn = document.createElement("button");
      btn.type = "button";
      btn.setAttribute("aria-pressed", String(c.ref === row.ref));
      btn.append(swatch(c.rgb), ` ${c.ref} · ${c.de}`);
      btn.addEventListener("click", (e) => { e.stopPropagation(); applySwap(hex, c.ref, row.auto); });
      list.append(btn);
    }
    cell.append(list);
    const any = document.createElement("select");
    any.setAttribute("aria-label", t("swap_any_aria"));
    any.add(new Option(t("swap_any"), ""));
    for (const p of r.palette) any.add(new Option(p.ref, p.ref));
    any.addEventListener("change", () => { if (any.value) applySwap(hex, any.value, row.auto); });
    cell.append(any);
    if (row.swapped) {
      const undo = document.createElement("button");
      undo.type = "button";
      undo.textContent = t("swap_back", { ref: row.auto });
      undo.addEventListener("click", () => applySwap(hex, row.auto, row.auto));
      cell.append(undo);
    }
  }
}

$("swap-toggle").addEventListener("click", () => { swapOpen = !swapOpen; renderSwap(); });
$("swap-reset").addEventListener("click", () => { swaps = {}; openRow = null; refresh(); });

// ---- outputs: the PNG opens in a new tab to be saved; the PDF goes through the print dialog ----

const outputName = () => `${$("brand").value}_${fileStem || "pattern"}`;

// Draw an SVG onto a canvas. Safari on iOS cannot make a canvas above about 16 million pixels,
// so the scale is lowered for big sheets.
async function svgToCanvas(svg, scale, maxPixels) {
  const m = svg.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  const w = parseFloat(m[1]), h = parseFloat(m[2]);
  scale = Math.min(scale, 12000 / Math.max(w, h), Math.sqrt(maxPixels / (w * h)));
  const url = URL.createObjectURL(new Blob([svg], { type: "image/svg+xml" }));
  try {
    const img = new Image();
    img.src = url;
    await img.decode();
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    return canvas;
  } finally {
    URL.revokeObjectURL(url);
  }
}

async function makePng(svg) {
  for (let scale = 3; scale >= 0.75; scale /= 2) {   // smaller if the browser refuses
    try {
      const blob = await new Promise((resolve) =>
        svgToCanvas(svg, scale, 12e6).then((c) => c.toBlob(resolve, "image/png")));
      if (blob) return blob;
    } catch (err) { /* try a smaller canvas */ }
  }
  return null;
}

// The PNG is made once per result, shortly after it appears, so a click finds it ready.
let pngJob = { result: null };
function pngFor(result) {
  if (pngJob.result !== result) {
    pngJob = { result, made: makePng(result.sheet).then((blob) => blob && URL.createObjectURL(blob)) };
  }
  return pngJob.made;
}
let prepareTimer = null;
function preparePng() {
  clearTimeout(prepareTimer);
  prepareTimer = setTimeout(() => { if (lastResult) pngFor(lastResult); }, 800);
}

// The tab is opened inside the click, which browsers require, and filled in once the file exists.
$("save-png").addEventListener("click", async () => {
  const tab = window.open("", "_blank");
  if (!tab) {
    setStatus(t("err_popup"), "error");
    return;
  }
  tab.document.title = outputName();
  tab.document.body.textContent = t("working");
  try {
    const url = await pngFor(lastResult);
    if (!url) throw new Error("no file");
    tab.location.href = url;
  } catch (err) {
    tab.close();
    setStatus(t("err_file"), "error");
  }
});

// "Save as PDF" in the print dialog proposes the page title as the file name.
$("save-pdf").addEventListener("click", () => {
  const title = document.title;
  document.title = outputName();
  window.addEventListener("afterprint", () => { document.title = title; }, { once: true });
  window.print();
});

// ---- wiring ----

function schedule() {
  clearTimeout(timer);
  timer = setTimeout(refresh, 250);
}

async function loadImage(blob, name) {
  imageBytes = new Uint8Array(await blob.arrayBuffer());
  fileStem = name.replace(/\.[^.]*$/, "").replace(/[^\w.-]+/g, "-");
  if (originalUrl) URL.revokeObjectURL(originalUrl);
  originalUrl = URL.createObjectURL(blob);
  custom = null;
  lockRatio = null;
  detected = null;
  swaps = {};
  openRow = null;
  clearResult();
  refresh();
}

$("file").addEventListener("change", (e) => {
  const f = e.target.files[0];
  if (f) loadImage(f, f.name);
});
$("sample").addEventListener("click", async () => {
  try {
    const res = await fetch("sample.jpg");
    if (!res.ok) throw new Error(res.status);
    $("file").value = "";
    await loadImage(await res.blob(), "sample.jpg");
  } catch (err) {
    setStatus(t("err_process") + err.message, "error");
  }
});
function applyBrandDefaults() {
  // brands with long codes (Perler's 80-15179) read better as symbols
  $("labels").value = brandInfo[$("brand").value]?.symbols ? "symbol" : "code";
}
$("brand").addEventListener("change", () => {
  swaps = {};   // swaps name beads of the old brand
  openRow = null;
  applyBrandDefaults();
  schedule();
});
$("labels").addEventListener("change", schedule);
$("board").addEventListener("input", schedule);
$("order").addEventListener("change", schedule);
$("clean").addEventListener("change", () => {
  custom = null;   // the trimmed art changes, so a custom size no longer means the same thing
  lockRatio = null;
  detected = null;
  schedule();
});
$("tol").addEventListener("input", () => {
  $("tolout").textContent = $("tol").value;
  schedule();
});

// ---- language ----

const brandLabel = (key) =>
  I18N[lang]["brand_" + key] ?? I18N.en["brand_" + key] ?? brandInfo[key]?.label ?? key;

function relabelBrands() {
  for (const opt of $("brand").options) opt.textContent = brandLabel(opt.value);
}

function markLanguage() {
  for (const b of document.querySelectorAll("#lang button")) {
    b.setAttribute("aria-pressed", String(b.dataset.lang === lang));
  }
}

function changeLanguage(l) {
  if (l === lang) return;
  setLang(l);
  markLanguage();
  relabelBrands();
  const s = $("status");
  if (!imageBytes && !s.hidden && !s.classList.contains("error")) {
    setStatus($("brand").disabled ? t("loading_python") : t("choose_image"), $("brand").disabled ? "loading" : "");
  }
  if (imageBytes) refresh();   // redraw the captions, the legend and the saved sheet
}

for (const b of document.querySelectorAll("#lang button")) {
  b.addEventListener("click", () => changeLanguage(b.dataset.lang));
}

initLang();
applyStatic();
markLanguage();
setStatus(t("loading_python"), "loading");
(async () => {
  try {
    const brands = await call({ type: "brands" });
    const sel = $("brand");
    for (const b of brands) {
      brandInfo[b.key] = b;
      sel.add(new Option(brandLabel(b.key), b.key));
    }
    sel.disabled = false;
    $("file").disabled = $("sample").disabled = false;
    applyBrandDefaults();
    setStatus(t("choose_image"));
    if (imageBytes) refresh();
  } catch (err) {
    setStatus(t("err_start") + err.message, "error");
  }
})();
