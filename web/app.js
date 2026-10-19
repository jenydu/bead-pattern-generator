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
function call(msg, transfer) {
  return new Promise((resolve, reject) => {
    const id = nextId++;
    pending.set(id, { resolve, reject });
    worker.postMessage({ id, ...msg }, transfer || []);
  });
}

let imageBytes = null;
let urls = [];
let timer = null;
let runToken = 0;

function setStatus(text, isError) {
  const s = $("status");
  s.textContent = text;
  s.className = isError ? "error" : "";
  s.hidden = !text;
}

const png = (bytes) => {
  const url = URL.createObjectURL(new Blob([bytes], { type: "image/png" }));
  urls.push(url);
  return url;
};

async function refresh() {
  if (!imageBytes) return;
  const token = ++runToken;
  setStatus("Working…");
  const cx = parseInt($("cx").value, 10) || 0;
  const cy = parseInt($("cy").value, 10) || 0;
  try {
    const r = await call({
      type: "run",
      data: imageBytes.slice(),
      brand: $("brand").value,
      cx: cx > 0 && cy > 0 ? cx : 0,
      cy: cx > 0 && cy > 0 ? cy : 0,
      tol: parseFloat($("tol").value),
    });
    if (token !== runToken) return;
    show(r);
    setStatus("");
  } catch (err) {
    if (token === runToken) setStatus("Could not process this image: " + err.message, true);
  }
}

function show(r) {
  urls.forEach(URL.revokeObjectURL);
  urls = [];
  const { grid, image } = r;
  $("cx").placeholder = grid.detected[0];
  $("cy").placeholder = grid.detected[1];
  $("gridinfo").textContent = grid.manual
    ? `Using ${grid.nx} × ${grid.ny} (set by you). Detected ${grid.detected[0]} × ${grid.detected[1]}.`
    : grid.period > 1
      ? `Detected ${grid.nx} × ${grid.ny} pixels (each about ${grid.period.toFixed(2)} px wide in the image).`
      : `The image looks like it is already 1 pixel per bead: ${grid.nx} × ${grid.ny}. If it is scaled up, enter the number of columns and rows.`;

  $("preview").src = png(r.preview);
  const total = r.legend.reduce((n, c) => n + c.count, 0);
  $("summary").textContent = `${grid.nx} × ${grid.ny}, ${r.legend.length} colors, ${total} beads.`;

  const tiles = $("tiles");
  tiles.replaceChildren();
  r.tiles.forEach((t, i) => {
    const [x0, y0, x1, y1] = t.box;
    const fig = document.createElement("figure");
    fig.className = "tile";
    fig.style.margin = "0 0 1.5rem";
    const cap = document.createElement("figcaption");
    cap.textContent = r.tiles.length > 1
      ? `Part ${i + 1} of ${r.tiles.length}: columns ${x0 + 1}–${x1}, rows ${y0 + 1}–${y1}`
      : "";
    const box = document.createElement("div");
    box.className = "scroll";
    const img = document.createElement("img");
    img.src = png(t.png);
    img.alt = `Chart part ${i + 1}`;
    box.append(img);
    fig.append(cap, box);
    tiles.append(fig);
  });

  const body = $("legend").tBodies[0];
  body.replaceChildren();
  for (const c of r.legend) {
    const tr = body.insertRow();
    const sw = document.createElement("span");
    sw.className = "swatch";
    sw.style.background = `rgb(${c.rgb.join(",")})`;
    tr.insertCell().append(sw);
    tr.insertCell().textContent = c.name === c.ref ? c.ref : `${c.ref} ${c.name}`;
    const n = tr.insertCell();
    n.className = "num";
    n.textContent = c.count;
  }
  $("total").textContent = total;

  const dl = $("download");
  dl.href = png(r.full);
  dl.classList.remove("disabled");
  $("print").disabled = false;
  $("output").hidden = false;
}

function schedule() {
  clearTimeout(timer);
  timer = setTimeout(refresh, 250);
}

$("file").addEventListener("change", async (e) => {
  const f = e.target.files[0];
  if (!f) return;
  imageBytes = new Uint8Array(await f.arrayBuffer());
  $("cx").value = $("cy").value = "";
  refresh();
});
$("brand").addEventListener("change", schedule);
$("cx").addEventListener("input", schedule);
$("cy").addEventListener("input", schedule);
$("tol").addEventListener("input", () => {
  $("tolout").textContent = $("tol").value;
  schedule();
});
$("auto").addEventListener("click", () => {
  $("cx").value = $("cy").value = "";
  refresh();
});
$("print").addEventListener("click", () => window.print());

(async () => {
  try {
    const brands = await call({ type: "brands" });
    const sel = $("brand");
    for (const b of brands) sel.add(new Option(b.label, b.key));
    sel.disabled = false;
    setStatus("Choose an image to begin.");
    if (imageBytes) refresh();
  } catch (err) {
    setStatus("Could not start Python: " + err.message, true);
  }
})();
