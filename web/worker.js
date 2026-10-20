// Runs Python (Pyodide) off the main thread. Protocol: {id, type, ...} -> {id, result|error}
importScripts("https://cdn.jsdelivr.net/pyodide/v0.29.5/full/pyodide.js");

let api = null;

async function init() {
  const py = await loadPyodide();
  await py.loadPackage(["numpy", "pillow"]);
  // "no-cache": revalidate every time, so a new deploy never mixes old Python with a new page
  const files = await (await fetch("py/manifest.json", { cache: "no-cache" })).json();
  for (const f of files) {
    const res = await fetch("py/" + f, { cache: "no-cache" });
    const path = "/app/" + f;
    py.FS.mkdirTree(path.slice(0, path.lastIndexOf("/")));
    py.FS.writeFile(path, new Uint8Array(await res.arrayBuffer()));
  }
  py.runPython("import sys; sys.path.insert(0, '/app')");
  api = py.pyimport("core.api");
}

function toJs(proxy) {
  const out = proxy.toJs({ dict_converter: Object.fromEntries });
  proxy.destroy();
  return out;
}

const ready = init();

self.onmessage = async (e) => {
  const { id, type } = e.data;
  try {
    await ready;
    let result;
    if (type === "brands") {
      result = toJs(api.brands());
    } else if (type === "run") {
      const { data, brand, cx, cy, tol, board, order, clean, labels, swaps, texts } = e.data;
      result = toJs(api.run(data, brand, cx, cy, tol, board, order, clean, labels, swaps, texts));
    }
    self.postMessage({ id, result });
  } catch (err) {
    self.postMessage({ id, error: String(err) });
  }
};
