const $ = (id) => document.getElementById(id);
const worker = new Worker("worker.js");

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
let lastSheet = "";
let lastResult = null;
let swaps = {};           // {"rrggbb": bead ref} chosen in the color swap panel
let swapOpen = false;
let openRow = null;       // hex of the swap row whose picker is open
let brandInfo = {};       // key -> {symbols: bool}

function setStatus(text, isError) {
  const s = $("status");
  s.textContent = text;
  s.className = isError ? "error" : "";
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
    setStatus("Loading Python (first visit downloads about 10 MB)…");
    return;
  }
  const token = ++runToken;
  setStatus("Working…");
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
    });
    if (token !== runToken) return;
    show(r);
    setStatus("");
  } catch (err) {
    if (token === runToken) setStatus("Could not process this image: " + err.message, true);
  }
}

// ---- pixel grid panel -------------------------------------------------------------------

const ratio = () => (detected ? detected[1] / detected[0] : 1);   // rows per column

function setCustomInputs(cols, rows) {
  $("cx").value = cols;
  $("cy").value = rows;
  $("use-custom").disabled = !(cols > 0 && rows > 0);
}

$("cx").addEventListener("input", () => {
  const c = parseInt($("cx").value, 10);
  setCustomInputs(c > 0 ? c : "", c > 0 ? Math.max(1, Math.round(c * ratio())) : "");
});
$("cy").addEventListener("input", () => {
  const r = parseInt($("cy").value, 10);
  setCustomInputs(r > 0 ? Math.max(1, Math.round(r / ratio())) : "", r > 0 ? r : "");
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
  if (detected) setCustomInputs(detected[0], detected[1]);
  refresh();
});

function describeGrid(r) {
  const g = r.grid;
  if (g.manual) return `Using your custom grid, ${g.nx} × ${g.ny}.`;
  if (r.kind === "photo") {
    return `No pixel grid found, so this is treated as a regular picture and shrunk to ${g.detected[0]} × ${g.detected[1]}. Set another size under Custom.`;
  }
  if (r.kind === "pixels") return `Already one pixel per bead (${g.detected[0]} × ${g.detected[1]}). If it is scaled up, enter the size under Custom.`;
  const trimmed = g.nx !== g.detected[0] || g.ny !== g.detected[1]
    ? ` The empty background is cropped, leaving ${g.nx} × ${g.ny}.` : "";
  return `Using the detected grid: each pixel is about ${g.period.toFixed(2)} px wide in the image.${trimmed}`;
}

// ---- results ----------------------------------------------------------------------------

function show(r) {
  urls.forEach(URL.revokeObjectURL);
  urls = [];
  const g = r.grid;
  const firstTime = !detected || detected[0] !== g.detected[0] || detected[1] !== g.detected[1];
  detected = g.detected;
  if (firstTime && !custom) setCustomInputs(detected[0], detected[1]);

  $("gridbox").hidden = false;
  $("d-original").textContent = `${r.original[0]} × ${r.original[1]} px`;
  $("d-current").textContent = `${g.nx} × ${g.ny} cells`;
  $("d-detected").textContent = `${detected[0]} × ${detected[1]}`;
  $("use-detected").disabled = false;
  $("cx").disabled = $("cy").disabled = false;
  $("gridinfo").textContent = describeGrid(r);

  $("orig").src = originalUrl;
  $("preview").src = blobUrl(r.preview, "image/png");
  $("cap-preview").textContent = `Pattern, ${g.nx} × ${g.ny}`;
  $("summary").textContent = `${g.nx} × ${g.ny}, ${r.legend.length} colors, ${r.total} beads.`;

  const tiles = $("tiles");
  tiles.replaceChildren();
  r.tiles.forEach((t, i) => {
    const [x0, y0, x1, y1] = t.box;
    const fig = document.createElement("figure");
    fig.className = "tile";
    const cap = document.createElement("figcaption");
    cap.textContent = t.board
      ? `Board ${i + 1} of ${r.tiles.length} (board row ${t.board[0]}, column ${t.board[1]}); pattern columns ${x0 + 1}–${x1}, rows ${y0 + 1}–${y1}`
      : r.tiles.length > 1
        ? `Part ${i + 1} of ${r.tiles.length}: columns ${x0 + 1}–${x1}, rows ${y0 + 1}–${y1}`
        : "";
    const box = document.createElement("div");
    box.className = "scroll";
    const img = document.createElement("img");
    img.src = blobUrl(t.svg, "image/svg+xml");
    img.alt = `Chart part ${i + 1}`;
    box.append(img);
    fig.append(cap, box);
    tiles.append(fig);
  });

  const body = $("legend").tBodies[0];
  body.replaceChildren();
  let group = null;
  for (const c of r.legend) {
    if ($("order").value === "group" && c.group !== group) {
      group = c.group;
      const hr = body.insertRow();
      hr.className = "group";
      const th = document.createElement("th");
      th.colSpan = 3;
      th.textContent = group;
      hr.append(th);
    }
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
  lastSheet = r.sheet;
  $("print").disabled = $("dl-png").disabled = $("dl-svg").disabled = false;
  $("output").hidden = false;
}

// ---- color swap -------------------------------------------------------------------------

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

function renderSwap() {
  const r = lastResult;
  $("swap").hidden = !swapOpen;
  $("swap-toggle").setAttribute("aria-expanded", String(swapOpen));
  $("swap-reset").disabled = Object.keys(swaps).length === 0;
  const body = $("swap-table").tBodies[0];
  body.replaceChildren();
  if (!swapOpen || !r) return;
  const palRgb = Object.fromEntries(r.palette.map((p) => [p.ref, p.rgb]));
  for (const row of r.conversions) {
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
    if (row.swapped) b.append(" (swapped)");
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
    intro.textContent = `Replace ${row.ref} for this image color. Closest first; the number is the color difference (lower is closer).`;
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
    any.setAttribute("aria-label", "Any color");
    any.add(new Option("Any other color…", ""));
    for (const p of r.palette) any.add(new Option(p.ref, p.ref));
    any.addEventListener("change", () => { if (any.value) applySwap(hex, any.value, row.auto); });
    cell.append(any);
    if (row.swapped) {
      const undo = document.createElement("button");
      undo.type = "button";
      undo.textContent = `Back to automatic (${row.auto})`;
      undo.addEventListener("click", () => applySwap(hex, row.auto, row.auto));
      cell.append(undo);
    }
  }
}

$("swap-toggle").addEventListener("click", () => { swapOpen = !swapOpen; renderSwap(); });
$("swap-reset").addEventListener("click", () => { swaps = {}; openRow = null; refresh(); });

// ---- downloads --------------------------------------------------------------------------

function save(blob, name) {
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
}

$("dl-svg").addEventListener("click", () =>
  save(new Blob([lastSheet], { type: "image/svg+xml" }), "bead-pattern.svg"));

$("dl-png").addEventListener("click", () => {
  const m = lastSheet.match(/viewBox="0 0 ([\d.]+) ([\d.]+)"/);
  const w = parseFloat(m[1]), h = parseFloat(m[2]);
  const scale = Math.min(3, 12000 / Math.max(w, h));   // sharp, but within canvas limits
  const img = new Image();
  img.onload = () => {
    const canvas = document.createElement("canvas");
    canvas.width = Math.round(w * scale);
    canvas.height = Math.round(h * scale);
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff";
    ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    canvas.toBlob((b) => save(b, "bead-pattern.png"), "image/png");
  };
  img.src = blobUrl(lastSheet, "image/svg+xml");
});

$("print").addEventListener("click", () => window.print());

// ---- wiring -----------------------------------------------------------------------------

function schedule() {
  clearTimeout(timer);
  timer = setTimeout(refresh, 250);
}

$("file").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  imageBytes = new Uint8Array(await f.arrayBuffer());
  if (originalUrl) URL.revokeObjectURL(originalUrl);
  originalUrl = URL.createObjectURL(f);
  custom = null;
  detected = null;
  swaps = {};
  openRow = null;
  $("gridbox").hidden = true;
  setCustomInputs("", "");
  refresh();
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
  detected = null;
  schedule();
});
$("tol").addEventListener("input", () => {
  $("tolout").textContent = $("tol").value;
  schedule();
});

(async () => {
  try {
    const brands = await call({ type: "brands" });
    const sel = $("brand");
    for (const b of brands) {
      sel.add(new Option(b.label, b.key));
      brandInfo[b.key] = b;
    }
    sel.disabled = false;
    $("file").disabled = false;
    $("file-note").hidden = true;
    applyBrandDefaults();
    setStatus("Choose an image to begin.");
    if (imageBytes) refresh();
  } catch (err) {
    setStatus("Could not start Python: " + err.message, true);
  }
})();
