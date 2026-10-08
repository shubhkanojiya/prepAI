/* PrepAI AI Question Scanner — upload / camera capture → AI → structured solution. */
(function () {
  "use strict";

  const { api, toast, renderMarkdown, renderMath, escapeHtml } = window.PrepAI;
  const cfg = window.PREPAI_SCANNER;
  const $ = (id) => document.getElementById(id);
  const MAX_BYTES = cfg.maxBytes || 8 * 1024 * 1024;

  let imageBlob = null;
  let stream = null;

  /* ---------- Step indicator ---------- */
  const ORDER = ["capture", "processing", "question", "answer", "followup"];
  function setStep(step, failed = false) {
    const idx = ORDER.indexOf(step);
    document.querySelectorAll("[data-step]").forEach((el) => {
      const i = ORDER.indexOf(el.dataset.step);
      el.classList.toggle("done", i < idx && !failed);
      el.classList.toggle("active", i === idx);
    });
  }

  /* ---------- Image selection ---------- */
  function setImage(blob) {
    if (!blob) return;
    if (!/^image\/(jpeg|png|webp|gif)$/.test(blob.type)) { toast("Please choose a JPG, PNG, WEBP or GIF image.", "error"); return; }
    if (blob.size > MAX_BYTES) { toast(`That image is larger than ${Math.round(MAX_BYTES / 1048576)} MB. Try a smaller photo.`, "error"); return; }
    imageBlob = blob;
    $("previewImg").src = URL.createObjectURL(blob);
    $("previewBox").hidden = false;
    $("dropzone").hidden = true;
    setStep("capture");
  }

  function clearImage() {
    imageBlob = null;
    $("previewBox").hidden = true;
    $("dropzone").hidden = false;
    $("fileInput").value = "";
    $("cameraInput").value = "";
  }

  const dz = $("dropzone");
  dz.addEventListener("click", () => $("fileInput").click());
  dz.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); $("fileInput").click(); } });
  ["dragenter", "dragover"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.add("dragover"); }));
  ["dragleave", "drop"].forEach((ev) => dz.addEventListener(ev, (e) => { e.preventDefault(); dz.classList.remove("dragover"); }));
  dz.addEventListener("drop", (e) => setImage(e.dataTransfer.files[0]));
  $("fileInput").addEventListener("change", (e) => setImage(e.target.files[0]));
  $("cameraInput").addEventListener("change", (e) => setImage(e.target.files[0]));
  $("clearImage").addEventListener("click", clearImage);
  document.addEventListener("paste", (e) => {
    const item = [...(e.clipboardData?.items || [])].find((i) => i.type.startsWith("image/"));
    if (item) setImage(item.getAsFile());
  });

  /* ---------- Camera ---------- */
  async function openCamera() {
    if (!navigator.mediaDevices?.getUserMedia) { $("cameraInput").click(); return; }
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { ideal: "environment" }, width: { ideal: 1920 } }, audio: false });
      $("cameraVideo").srcObject = stream;
      $("cameraBox").hidden = false;
      $("openCamera").hidden = true;
    } catch (err) {
      // Permission denied or no camera → fall back to the native picker (opens camera on phones).
      $("cameraInput").click();
    }
  }

  function closeCamera() {
    if (stream) stream.getTracks().forEach((t) => t.stop());
    stream = null;
    $("cameraBox").hidden = true;
    $("openCamera").hidden = false;
  }

  function capture() {
    const video = $("cameraVideo");
    const canvas = document.createElement("canvas");
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;
    canvas.getContext("2d").drawImage(video, 0, 0);
    canvas.toBlob((blob) => { closeCamera(); setImage(blob); }, "image/jpeg", 0.9);
  }

  $("openCamera").addEventListener("click", openCamera);
  $("closeCamera").addEventListener("click", closeCamera);
  $("captureBtn").addEventListener("click", capture);
  window.addEventListener("pagehide", closeCamera);

  /* ---------- Rendering ---------- */
  const pane = $("resultPane");

  function renderProcessing() {
    pane.innerHTML = `<div class="pa-card"><div class="card-body">
      <div class="d-flex align-items-center gap-2 mb-3"><div class="spinner-border spinner-border-sm text-primary" role="status"></div>
      <span class="fw-semibold">Reading your question and preparing a step-by-step solution…</span></div>
      <div class="skeleton skeleton-line" style="width:60%"></div><div class="skeleton skeleton-line"></div>
      <div class="skeleton skeleton-line" style="width:85%"></div><div class="skeleton skeleton-line" style="width:70%"></div>
      <p class="small text-muted mb-0 mt-3">This usually takes 10–30 seconds.</p></div></div>`;
  }

  function renderError(message, retryable) {
    pane.innerHTML = `<div class="pa-card"><div class="card-body text-center py-5">
      <div class="icon-tile mx-auto mb-3" style="background:var(--pa-bad-soft);color:var(--pa-bad)"><i class="bi bi-exclamation-triangle"></i></div>
      <h3 class="h5">We couldn't solve that</h3><p class="text-2 mb-3">${escapeHtml(message)}</p>
      ${retryable !== false ? '<button type="button" class="btn btn-primary" id="retryBtn"><i class="bi bi-arrow-clockwise"></i> Try again</button>' : ""}
    </div></div>`;
    const retry = $("retryBtn");
    if (retry) retry.addEventListener("click", runScan);
  }

  function renderResult(data) {
    if (data.status !== "completed") {
      setStep("question", true);
      renderError(data.error_message || "We couldn't find a question in this image.", true);
      return;
    }
    const steps = (data.steps || []).map((s) => `<li><div class="prose">${renderMarkdown(s)}</div></li>`).join("");
    const followups = (data.follow_up_questions || []).map((q) => `
      <li class="d-flex gap-2 align-items-start mb-2"><i class="bi bi-arrow-return-right text-muted mt-1"></i>
      <span class="flex-grow-1 math">${escapeHtml(q)}</span>
      <a class="btn btn-soft btn-sm flex-shrink-0" href="/assistant/?q=${encodeURIComponent(q)}">Solve</a></li>`).join("");
    const subjectLink = data.subject_url ? `<a href="${encodeURI(data.subject_url)}" class="badge-soft">${escapeHtml(data.chapter_name || data.subject_name || data.detected_subject_name)}</a>` : "";

    pane.innerHTML = `
      <article class="pa-card mb-3 fade-in"><div class="card-body">
        <div class="d-flex flex-wrap gap-1 mb-2">
          ${data.detected_subject_name ? `<span class="badge-soft"><i class="bi bi-book"></i> ${escapeHtml(data.detected_subject_name)}</span>` : ""}
          ${data.detected_topic_name ? `<span class="badge-muted">${escapeHtml(data.detected_topic_name)}</span>` : ""}
          ${data.is_handwritten ? '<span class="badge-muted"><i class="bi bi-pencil"></i> Handwritten</span>' : ""}
          ${subjectLink}
        </div>
        <h3 class="h6 text-muted text-uppercase small fw-bold">Detected question</h3>
        <div class="question-text math">${escapeHtml(data.detected_question)}</div>
      </div></article>
      <article class="pa-card mb-3 fade-in"><div class="card-body">
        <h3 class="h6 text-muted text-uppercase small fw-bold">Answer</h3>
        <div class="prose fs-5 fw-semibold">${renderMarkdown(data.answer)}</div>
      </div></article>
      ${steps ? `<article class="pa-card mb-3 fade-in"><div class="card-body">
        <h3 class="h6 text-muted text-uppercase small fw-bold mb-3">Step-by-step explanation</h3><ol class="step-list mb-0">${steps}</ol>
      </div></article>` : ""}
      ${data.concept ? `<article class="pa-card mb-3 fade-in"><div class="card-body">
        <h3 class="h6 text-muted text-uppercase small fw-bold"><i class="bi bi-lightbulb"></i> Concept</h3><div class="prose">${renderMarkdown(data.concept)}</div>
      </div></article>` : ""}
      ${followups ? `<article class="pa-card mb-3 fade-in"><div class="card-body">
        <h3 class="h6 text-muted text-uppercase small fw-bold">Follow-up questions</h3><ul class="list-unstyled mb-0">${followups}</ul>
      </div></article>` : ""}
      <div class="d-flex flex-wrap gap-2">
        <a class="btn btn-primary" href="/questions/predictor/?q=${encodeURIComponent((data.detected_question || "").slice(0, 900))}${data.subject ? `&subject=${data.subject}` : ""}"><i class="bi bi-graph-up-arrow"></i> Check exam history &amp; chances</a>
        <a class="btn btn-ghost" href="/assistant/?q=${encodeURIComponent("Explain this in simpler words: " + (data.detected_question || ""))}"><i class="bi bi-chat-dots"></i> Discuss with AI Assistant</a>
        <button type="button" class="btn btn-ghost" id="scanAnother"><i class="bi bi-camera"></i> Scan another</button>
        ${data.url ? `<a class="btn btn-ghost" href="${encodeURI(data.url)}"><i class="bi bi-link-45deg"></i> Saved scan</a>` : ""}
      </div>
      <p class="small text-muted mt-3 mb-0"><i class="bi bi-info-circle"></i> AI can make mistakes. Check important answers with your textbook or teacher.</p>`;
    pane.querySelectorAll(".math, .prose").forEach((el) => renderMath(el));
    $("scanAnother").addEventListener("click", () => { clearImage(); $("typedQuestion").value = ""; setStep("capture"); window.scrollTo({ top: 0, behavior: "smooth" }); });
    setStep("followup");
    document.querySelectorAll("[data-step]").forEach((el) => el.classList.add("done"));
  }

  /* ---------- Submit ---------- */
  async function runScan() {
    const typed = $("typedQuestion").value.trim();
    const textTabActive = document.querySelector("#tab-text").classList.contains("active");
    if (!imageBlob && !typed) { toast("Upload an image or type a question first.", "warning"); return; }
    const form = new FormData();
    if (imageBlob && !textTabActive) form.append("image", imageBlob, `question.${(imageBlob.type.split("/")[1] || "jpg").replace("jpeg", "jpg")}`);
    if (typed && (textTabActive || !imageBlob)) form.append("question", typed);

    $("scanBtn").disabled = true;
    setStep("processing");
    renderProcessing();
    if (window.innerWidth < 992) pane.scrollIntoView({ behavior: "smooth" });
    try {
      const data = await api(cfg.endpoint, { method: "POST", body: form, quiet: true });
      setStep("question");
      renderResult(data);
    } catch (err) {
      setStep("processing", true);
      const details = err.data?.error?.details;
      const fieldMsg = details && (details.image?.[0] || details.non_field_errors?.[0]);
      renderError(fieldMsg || err.message, err.data?.error?.retryable);
    } finally {
      $("scanBtn").disabled = false;
    }
  }
  $("scanBtn").addEventListener("click", runScan);

  if (cfg.autoCamera) openCamera();
})();
