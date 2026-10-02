/* PrepAI PDF viewer — PDF.js with zoom, page navigation, fullscreen and lazy page rendering.
   Markup: <div class="pdf-viewer" data-pdf-viewer data-src="/papers/x/file/"> (see components/pdf_viewer.html) */
import * as pdfjsLib from "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/build/pdf.min.mjs";

pdfjsLib.GlobalWorkerOptions.workerSrc = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.4.168/build/pdf.worker.min.mjs";

const MIN_SCALE = 0.4;
const MAX_SCALE = 4;

function initViewer(root) {
  const stage = root.querySelector("[data-stage]");
  const pageInput = root.querySelector("[data-page-input]");
  const pageCount = root.querySelector("[data-page-count]");
  const zoomLabel = root.querySelector("[data-zoom-label]");
  const status = root.querySelector("[data-status]");
  let pdf = null;
  let scale = 1;
  let fitWidth = true;
  const rendered = new Map(); // pageNumber -> scale rendered at
  let observer = null;

  const setStatus = (html) => { status.innerHTML = html; status.hidden = !html; };

  function computeFitScale(page) {
    const viewport = page.getViewport({ scale: 1 });
    const available = stage.clientWidth - 32;
    return Math.max(MIN_SCALE, Math.min(MAX_SCALE, available / viewport.width));
  }

  async function renderPage(num) {
    const canvas = stage.querySelector(`canvas[data-page="${num}"]`);
    if (!canvas || rendered.get(num) === scale) return;
    rendered.set(num, scale);
    const page = await pdf.getPage(num);
    const viewport = page.getViewport({ scale });
    const ratio = window.devicePixelRatio || 1;
    canvas.width = Math.floor(viewport.width * ratio);
    canvas.height = Math.floor(viewport.height * ratio);
    canvas.style.width = `${Math.floor(viewport.width)}px`;
    canvas.style.height = `${Math.floor(viewport.height)}px`;
    const ctx = canvas.getContext("2d");
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
    await page.render({ canvasContext: ctx, viewport }).promise;
  }

  async function layout() {
    const first = await pdf.getPage(1);
    if (fitWidth) scale = computeFitScale(first);
    zoomLabel.textContent = `${Math.round(scale * 100)}%`;
    const base = first.getViewport({ scale });
    rendered.clear();
    stage.querySelectorAll("canvas").forEach((canvas) => {
      // Placeholder size keeps scroll positions stable before a page renders.
      canvas.style.width = `${Math.floor(base.width)}px`;
      canvas.style.height = `${Math.floor(base.height)}px`;
    });
    stage.querySelectorAll("canvas").forEach((c) => observer.unobserve(c));
    stage.querySelectorAll("canvas").forEach((c) => observer.observe(c));
  }

  function currentPage() {
    const top = stage.scrollTop + stage.clientHeight / 3;
    let current = 1;
    stage.querySelectorAll("canvas").forEach((c) => { if (c.offsetTop <= top) current = Number(c.dataset.page); });
    return current;
  }

  function goTo(num) {
    num = Math.max(1, Math.min(pdf.numPages, num));
    const canvas = stage.querySelector(`canvas[data-page="${num}"]`);
    if (canvas) stage.scrollTo({ top: canvas.offsetTop - 12, behavior: "smooth" });
    pageInput.value = num;
  }

  function setScale(next) {
    fitWidth = false;
    scale = Math.max(MIN_SCALE, Math.min(MAX_SCALE, next));
    const page = currentPage();
    layout().then(() => goTo(page));
  }

  root.querySelector("[data-action='prev']").addEventListener("click", () => goTo(currentPage() - 1));
  root.querySelector("[data-action='next']").addEventListener("click", () => goTo(currentPage() + 1));
  root.querySelector("[data-action='zoom-in']").addEventListener("click", () => setScale(scale * 1.2));
  root.querySelector("[data-action='zoom-out']").addEventListener("click", () => setScale(scale / 1.2));
  root.querySelector("[data-action='fit']").addEventListener("click", () => { fitWidth = true; layout(); });
  root.querySelector("[data-action='fullscreen']").addEventListener("click", () => {
    if (document.fullscreenElement) document.exitFullscreen();
    else if (root.requestFullscreen) root.requestFullscreen().catch(() => root.classList.toggle("fs"));
    else root.classList.toggle("fs");
  });
  document.addEventListener("fullscreenchange", () => { if (fitWidth && pdf) setTimeout(layout, 150); });
  pageInput.addEventListener("change", () => goTo(Number(pageInput.value) || 1));
  stage.addEventListener("scroll", () => { if (pdf) pageInput.value = currentPage(); }, { passive: true });
  root.addEventListener("keydown", (e) => {
    if (e.target === pageInput) return;
    if (e.key === "ArrowRight" || e.key === "PageDown") { e.preventDefault(); goTo(currentPage() + 1); }
    if (e.key === "ArrowLeft" || e.key === "PageUp") { e.preventDefault(); goTo(currentPage() - 1); }
    if (e.key === "+" || e.key === "=") setScale(scale * 1.2);
    if (e.key === "-") setScale(scale / 1.2);
  });
  let resizeTimer;
  window.addEventListener("resize", () => { clearTimeout(resizeTimer); resizeTimer = setTimeout(() => { if (fitWidth && pdf) layout(); }, 200); });

  setStatus('<div class="skeleton" style="height:420px;max-width:640px;margin:0 auto"></div><p class="small text-muted mt-2">Loading PDF…</p>');
  pdfjsLib.getDocument({ url: root.dataset.src, withCredentials: true }).promise.then(async (doc) => {
    pdf = doc;
    pageCount.textContent = doc.numPages;
    pageInput.max = doc.numPages;
    const fragment = document.createDocumentFragment();
    for (let i = 1; i <= doc.numPages; i += 1) {
      const canvas = document.createElement("canvas");
      canvas.dataset.page = i;
      canvas.setAttribute("role", "img");
      canvas.setAttribute("aria-label", `Page ${i} of ${doc.numPages}`);
      fragment.appendChild(canvas);
    }
    setStatus("");
    stage.appendChild(fragment);
    observer = new IntersectionObserver((entries) => {
      entries.forEach((entry) => { if (entry.isIntersecting) renderPage(Number(entry.target.dataset.page)); });
    }, { root: stage, rootMargin: "400px 0px" });
    await layout();
  }).catch(() => {
    setStatus(`<div class="empty-state"><div class="icon-tile"><i class="bi bi-file-earmark-x"></i></div>
      <h3>Couldn't display this PDF</h3><p>Your browser may not support the viewer. You can still open or download it.</p>
      <a class="btn btn-primary" href="${root.dataset.src}" target="_blank" rel="noopener">Open PDF</a></div>`);
  });
}

document.querySelectorAll("[data-pdf-viewer]").forEach(initViewer);
