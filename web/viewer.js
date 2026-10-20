// Zoomable, pannable image viewer for the charts. Fits the chart to its box by default.
//   wheel + Ctrl/Cmd, pinch, or the buttons zoom; drag pans; double-click toggles fit / 100%.
// On touch screens a one-finger drag scrolls the page while the chart is at "fit", and pans
// the chart once it has been zoomed in.
class Viewer {
  constructor(url, { maxHeight = () => window.innerHeight * 0.78, onKey } = {}) {
    this.maxHeight = maxHeight;
    this.onKey = onKey;
    this.scale = 1; this.tx = 0; this.ty = 0;
    this.fitMode = true;
    this.pointers = new Map();

    const el = (this.el = document.createElement("div"));
    el.className = "viewer";
    el.tabIndex = 0;
    el.setAttribute("role", "group");
    el.setAttribute("aria-label", t("viewer_aria"));
    this.stage = document.createElement("div");
    this.stage.className = "stage";
    this.img = new Image();
    this.img.draggable = false;
    this.img.alt = "";
    this.stage.append(this.img);
    el.append(this.stage, this.tools());
    this.img.onload = () => { this.w = this.img.naturalWidth; this.h = this.img.naturalHeight; this.layout(); };
    this.img.src = url;

    new ResizeObserver(() => this.layout()).observe(el);
    el.addEventListener("wheel", (e) => this.onWheel(e), { passive: false });
    el.addEventListener("pointerdown", (e) => this.down(e));
    el.addEventListener("pointermove", (e) => this.move(e));
    el.addEventListener("pointerup", (e) => this.up(e));
    el.addEventListener("pointercancel", (e) => this.up(e));
    el.addEventListener("dblclick", (e) => this.toggle(e));
    el.addEventListener("keydown", (e) => this.key(e));
  }

  tools() {
    const bar = document.createElement("div");
    bar.className = "vtools";
    const add = (text, label, fn) => {
      const b = document.createElement("button");
      b.type = "button";
      b.textContent = text;
      b.setAttribute("aria-label", label);
      b.addEventListener("click", (e) => { e.stopPropagation(); fn(); });
      b.addEventListener("pointerdown", (e) => e.stopPropagation());
      b.addEventListener("dblclick", (e) => e.stopPropagation());
      bar.append(b);
    };
    add("−", t("zoom_out"), () => this.zoomBy(1 / 1.4));
    add("+", t("zoom_in"), () => this.zoomBy(1.4));
    add(t("fit"), t("fit_aria"), () => this.fit());
    add(t("actual"), t("actual_aria"), () => this.actual());
    return bar;
  }

  get box() { return { w: this.el.clientWidth, h: this.el.clientHeight }; }
  get fitScale() {
    const { w, h } = this.box;
    return Math.min(w / this.w, h / this.h, 3);
  }
  get maxScale() { return Math.max(3, this.fitScale * 8); }

  // Called when the box or image size changes, and when the viewer becomes visible.
  layout() {
    if (!this.w || !this.el.clientWidth) return;
    // the box is as tall as the chart needs at this width, but never taller than the window
    const natural = (this.el.clientWidth * this.h) / this.w;
    this.el.style.height = Math.max(Math.min(natural, this.maxHeight()), 160) + "px";
    if (this.fitMode) this.fit(); else this.apply();
  }

  apply() {
    const { w, h } = this.box;
    const sw = this.w * this.scale, sh = this.h * this.scale;
    this.tx = sw <= w ? (w - sw) / 2 : Math.min(0, Math.max(w - sw, this.tx));
    this.ty = sh <= h ? (h - sh) / 2 : Math.min(0, Math.max(h - sh, this.ty));
    this.stage.style.transform = `translate(${this.tx}px, ${this.ty}px) scale(${this.scale})`;
    const zoomed = this.scale > this.fitScale * 1.01;
    this.el.classList.toggle("zoomed", zoomed);
    this.el.style.touchAction = zoomed ? "none" : "pan-y";
  }

  fit() { this.fitMode = true; this.scale = this.fitScale; this.apply(); }
  actual() { this.zoomTo(1); }
  toggle(e) {
    if (this.scale > this.fitScale * 1.01) this.fit();
    else this.zoomTo(Math.min(this.maxScale, Math.max(1, this.fitScale * 2.5)), e);
  }

  zoomTo(s, e) {
    const r = this.el.getBoundingClientRect();
    const cx = e ? e.clientX - r.left : r.width / 2;
    const cy = e ? e.clientY - r.top : r.height / 2;
    this.zoomAt(s / this.scale, cx, cy);
  }
  zoomBy(f) { this.zoomTo(this.scale * f); }
  zoomAt(f, cx, cy) {
    const s = Math.min(this.maxScale, Math.max(this.fitScale, this.scale * f));
    const k = s / this.scale;
    this.tx = cx - (cx - this.tx) * k;
    this.ty = cy - (cy - this.ty) * k;
    this.scale = s;
    this.fitMode = s <= this.fitScale * 1.001;
    this.apply();
  }

  onWheel(e) {
    const r = this.el.getBoundingClientRect();
    if (e.ctrlKey || e.metaKey) {       // also what a trackpad pinch sends
      e.preventDefault();
      this.zoomAt(Math.exp(-e.deltaY * 0.01), e.clientX - r.left, e.clientY - r.top);
    } else if (this.scale > this.fitScale * 1.01) {   // zoomed in: the wheel pans
      e.preventDefault();
      this.tx -= e.shiftKey ? e.deltaY : e.deltaX;
      this.ty -= e.shiftKey ? 0 : e.deltaY;
      this.apply();
    }                                    // at "fit" the wheel scrolls the page as usual
  }

  down(e) {
    if (e.target.closest(".vtools")) return;
    this.pointers.set(e.pointerId, { x: e.clientX, y: e.clientY });
    this.el.setPointerCapture?.(e.pointerId);
    this.pinch = null;
  }
  move(e) {
    const p = this.pointers.get(e.pointerId);
    if (!p) return;
    const prev = { ...p };
    p.x = e.clientX; p.y = e.clientY;
    const r = this.el.getBoundingClientRect();
    if (this.pointers.size === 2) {
      const [a, b] = [...this.pointers.values()];
      const d = Math.hypot(a.x - b.x, a.y - b.y);
      const mx = (a.x + b.x) / 2 - r.left, my = (a.y + b.y) / 2 - r.top;
      if (this.pinch) {
        this.zoomAt(d / this.pinch.d, mx, my);
        this.tx += mx - this.pinch.mx; this.ty += my - this.pinch.my;
        this.apply();
      }
      this.pinch = { d, mx, my };
    } else if (this.pointers.size === 1 && (this.scale > this.fitScale * 1.01 || e.pointerType === "mouse")) {
      this.tx += e.clientX - prev.x;
      this.ty += e.clientY - prev.y;
      this.el.classList.add("dragging");
      this.apply();
    }
  }
  up(e) {
    this.pointers.delete(e.pointerId);
    this.pinch = null;
    if (!this.pointers.size) this.el.classList.remove("dragging");
  }

  key(e) {
    const zoomed = this.scale > this.fitScale * 1.01;
    const step = 60;
    if (e.key === "+" || e.key === "=") this.zoomBy(1.4);
    else if (e.key === "-" || e.key === "_") this.zoomBy(1 / 1.4);
    else if (e.key === "0") this.fit();
    else if (zoomed && e.key.startsWith("Arrow")) {
      this.tx += e.key === "ArrowLeft" ? step : e.key === "ArrowRight" ? -step : 0;
      this.ty += e.key === "ArrowUp" ? step : e.key === "ArrowDown" ? -step : 0;
      this.apply();
    } else if (!zoomed && this.onKey && (e.key === "ArrowLeft" || e.key === "ArrowRight")) {
      this.onKey(e.key === "ArrowLeft" ? -1 : 1);
    } else return;
    e.preventDefault();
  }
}
