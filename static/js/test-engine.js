/* ==========================================================================
   PrepAI test engine (client).
   - Server is the source of truth for time and answers.
   - Every change is saved via the API; unsaved changes are also kept in
     localStorage and retried, so a refresh or a network drop loses nothing.
   ========================================================================== */
(function () {
  "use strict";

  const cfg = window.PREPAI_TEST;
  const payload = JSON.parse(document.getElementById("test-payload").textContent);
  const { api, toast, renderMath, escapeHtml } = window.PrepAI;
  const STORAGE_KEY = `prepai-attempt-${cfg.attemptId}`;

  const questions = payload.questions;
  const state = {}; // id -> { selected:[], text:"", marked:false, visited:false }
  const pending = {}; // id -> payload awaiting save
  let current = 0;
  let shownAt = Date.now();
  let submitting = false;
  let saveTimer = null;
  const deadline = Date.now() + payload.attempt.remaining_seconds * 1000;

  const el = (id) => document.getElementById(id);
  const pane = el("questionPane");

  /* ---------- State & persistence ---------- */
  questions.forEach((q) => { state[q.id] = { ...q.state }; });

  function loadBackup() {
    try {
      const saved = JSON.parse(localStorage.getItem(STORAGE_KEY) || "{}");
      Object.entries(saved).forEach(([id, data]) => {
        if (!state[id]) return;
        Object.assign(state[id], data.state);
        pending[id] = data.payload;
      });
    } catch (e) { /* storage unavailable */ }
  }

  function writeBackup() {
    try {
      const data = {};
      Object.keys(pending).forEach((id) => { data[id] = { state: state[id], payload: pending[id] }; });
      if (Object.keys(data).length) localStorage.setItem(STORAGE_KEY, JSON.stringify(data));
      else localStorage.removeItem(STORAGE_KEY);
    } catch (e) { /* storage unavailable */ }
  }

  function isAnswered(id) {
    const s = state[id];
    return (s.selected && s.selected.length > 0) || (s.text && s.text.trim().length > 0);
  }

  function setSaveStatus(text, tone) {
    const status = el("saveStatus");
    status.textContent = text;
    status.className = "save-status" + (tone ? ` tone-${tone}` : "");
  }

  function queueSave(id, extra = {}) {
    const s = state[id];
    const q = questions.find((x) => x.id === Number(id));
    const prev = pending[id] || { time_spent: 0 };
    pending[id] = {
      test_question: Number(id),
      marked_for_review: s.marked,
      time_spent: (prev.time_spent || 0) + (extra.time_spent || 0),
      ...(q.options.length ? { options: s.selected } : { text_answer: s.text || "" }),
    };
    writeBackup();
    setSaveStatus("Saving…");
    clearTimeout(saveTimer);
    saveTimer = setTimeout(flush, extra.immediate ? 0 : 700);
  }

  async function flush() {
    const ids = Object.keys(pending);
    for (const id of ids) {
      const body = pending[id];
      try {
        await api(cfg.answerUrl, { method: "POST", body, quiet: true });
        if (pending[id] === body) delete pending[id];
      } catch (err) {
        if (err.status === 409) { // test closed (time up / already submitted)
          delete pending[id];
          writeBackup();
          window.removeEventListener("beforeunload", beforeUnload);
          toast("Time is up — your test was submitted.", "warning");
          window.location.href = (err.data && err.data.result_url) || cfg.resultUrl;
          return false;
        }
        if (err.status === 400) { delete pending[id]; toast(err.message, "error"); continue; }
        writeBackup();
        setSaveStatus("Offline — answers kept on this device, retrying…", "warn");
        return false;
      }
    }
    writeBackup();
    if (!Object.keys(pending).length) setSaveStatus("All answers saved", "good");
    return true;
  }

  setInterval(() => { if (Object.keys(pending).length && !submitting) flush(); }, 10000);
  window.addEventListener("online", () => flush());

  function recordTime() {
    const id = questions[current].id;
    const spent = Math.round((Date.now() - shownAt) / 1000);
    shownAt = Date.now();
    if (spent > 0 && spent < 3600) {
      const prev = pending[id];
      if (prev) prev.time_spent = (prev.time_spent || 0) + spent;
      else if (spent >= 3) queueSave(id, { time_spent: spent });
    }
  }

  /* ---------- Rendering ---------- */
  const TYPE_LABELS = {
    mcq: "Single correct answer", multi: "One or more correct answers", true_false: "True / False",
    numeric: "Numerical answer", fill_blank: "Fill in the blank", short: "Short answer", long: "Long answer",
  };

  function renderQuestion() {
    const q = questions[current];
    const s = state[q.id];
    if (!s.visited) { s.visited = true; queueSave(q.id); }
    const multi = q.type === "multi";
    const letters = "ABCDEFGH";
    let answerHtml = "";
    if (q.options.length) {
      answerHtml = `<fieldset><legend class="visually-hidden">Options</legend>` + q.options.map((o, i) => `
        <label class="answer-option ${s.selected.includes(o.id) ? "selected" : ""}">
          <input type="${multi ? "checkbox" : "radio"}" name="answer" value="${o.id}" ${s.selected.includes(o.id) ? "checked" : ""}>
          <span><span class="fw-bold me-2">${letters[i]}.</span><span class="math">${escapeHtml(o.text)}</span></span>
        </label>`).join("") + `</fieldset>`;
    } else if (q.type === "short" || q.type === "long") {
      answerHtml = `<label for="textAnswer" class="form-label">Your answer</label>
        <textarea id="textAnswer" class="form-control" rows="${q.type === "long" ? 8 : 4}" placeholder="Type your answer…">${escapeHtml(s.text || "")}</textarea>
        <div class="form-text">Written answers aren't auto-graded; you'll compare with the model answer in your results.</div>`;
    } else {
      answerHtml = `<label for="textAnswer" class="form-label">Your answer</label>
        <input id="textAnswer" class="form-control" ${q.type === "numeric" ? 'inputmode="decimal"' : ""} value="${escapeHtml(s.text || "")}" placeholder="${q.type === "numeric" ? "Enter a number" : "Type the missing word(s)"}" autocomplete="off">`;
    }

    pane.innerHTML = `
      <div class="d-flex flex-wrap justify-content-between align-items-center gap-2 mb-3">
        <h2 id="qHeading" class="h5 mb-0">Question ${q.number} <span class="text-muted fw-normal fs-6">of ${questions.length}</span></h2>
        <div class="d-flex flex-wrap gap-1">
          <span class="badge-muted">${escapeHtml(TYPE_LABELS[q.type] || q.type)}</span>
          <span class="badge-good">+${q.marks}</span>
          ${q.negative_marks ? `<span class="badge-bad">−${q.negative_marks}</span>` : ""}
          ${s.marked ? '<span class="badge-soft"><i class="bi bi-flag-fill"></i> Marked</span>' : ""}
        </div>
      </div>
      ${q.chapter ? `<p class="small text-muted mb-2">${escapeHtml(q.subject)} · ${escapeHtml(q.chapter)}</p>` : ""}
      <div class="question-text mb-3 math">${escapeHtml(q.text)}</div>
      ${q.image ? `<img src="${encodeURI(q.image)}" alt="Figure for question ${q.number}" class="img-fluid rounded-xl mb-3">` : ""}
      ${answerHtml}`;

    pane.querySelectorAll("input[name='answer']").forEach((input) => {
      input.addEventListener("change", () => {
        const id = Number(input.value);
        if (multi) {
          s.selected = input.checked ? [...new Set([...s.selected, id])] : s.selected.filter((x) => x !== id);
        } else {
          s.selected = [id];
        }
        pane.querySelectorAll(".answer-option").forEach((label) => {
          label.classList.toggle("selected", label.querySelector("input").checked);
        });
        queueSave(q.id);
        renderPalette();
      });
    });
    const text = el("textAnswer");
    if (text) {
      text.addEventListener("input", () => { s.text = text.value; queueSave(q.id); renderPalette(); });
    }
    pane.querySelectorAll(".math").forEach((m) => renderMath(m));

    el("prevBtn").disabled = current === 0;
    el("nextBtn").innerHTML = current === questions.length - 1
      ? 'Save <i class="bi bi-check2"></i>' : 'Save &amp; Next <i class="bi bi-chevron-right"></i>';
    el("markBtn").innerHTML = s.marked
      ? '<i class="bi bi-flag-fill"></i><span class="d-none d-sm-inline"> Unmark</span>'
      : '<i class="bi bi-flag"></i><span class="d-none d-sm-inline"> Mark for review</span>';
    renderPalette();
  }

  function counts() {
    const c = { answered: 0, marked: 0, visited: 0, notVisited: 0 };
    questions.forEach((q) => {
      const s = state[q.id];
      if (s.marked) c.marked += 1;
      if (isAnswered(q.id)) c.answered += 1;
      else if (s.visited) c.visited += 1;
      else c.notVisited += 1;
    });
    return c;
  }

  function renderPalette() {
    const c = counts();
    const html = `
      <div class="d-flex justify-content-between align-items-center mb-3">
        <h2 class="h6 mb-0">Question palette</h2>
        <span class="small text-muted">${c.answered}/${questions.length} answered</span>
      </div>
      <div class="palette-grid mb-3">
        ${questions.map((q, i) => {
          const s = state[q.id];
          const cls = [isAnswered(q.id) ? "answered" : s.visited ? "visited" : "", s.marked ? "marked" : "", i === current ? "current" : ""].join(" ");
          const label = `Question ${q.number}: ${isAnswered(q.id) ? "answered" : s.visited ? "not answered" : "not visited"}${s.marked ? ", marked for review" : ""}`;
          return `<button type="button" class="palette-btn ${cls}" data-goto="${i}" aria-label="${label}" ${i === current ? 'aria-current="true"' : ""}>${q.number}</button>`;
        }).join("")}
      </div>
      <ul class="list-unstyled small text-muted mb-0 d-grid gap-1">
        <li><span class="legend-dot" style="background:var(--pa-good);border-color:var(--pa-good)"></span>Answered (${c.answered})</li>
        <li><span class="legend-dot" style="background:var(--pa-bad-soft);border-color:var(--pa-bad)"></span>Not answered (${c.visited})</li>
        <li><span class="legend-dot"></span>Not visited (${c.notVisited})</li>
        <li><span class="legend-dot" style="background:var(--pa-mark);border-color:var(--pa-mark)"></span>Marked for review (${c.marked})</li>
      </ul>`;
    el("paletteDesktop").innerHTML = html;
    el("paletteMobile").innerHTML = html;
  }

  function goTo(index) {
    if (index < 0 || index >= questions.length) return;
    recordTime();
    current = index;
    renderQuestion();
    window.scrollTo({ top: 0, behavior: "smooth" });
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest("[data-goto]");
    if (!btn) return;
    goTo(Number(btn.dataset.goto));
    const sheet = bootstrap.Offcanvas.getInstance(el("paletteSheet"));
    if (sheet) sheet.hide();
  });

  el("prevBtn").addEventListener("click", () => goTo(current - 1));
  el("nextBtn").addEventListener("click", () => {
    queueSave(questions[current].id, { immediate: true });
    if (current < questions.length - 1) goTo(current + 1);
    else toast("That was the last question. Review your answers or submit.", "info", 3000);
  });
  el("markBtn").addEventListener("click", () => {
    const q = questions[current];
    state[q.id].marked = !state[q.id].marked;
    queueSave(q.id, { immediate: true });
    if (state[q.id].marked && current < questions.length - 1) goTo(current + 1);
    else renderQuestion();
  });
  el("clearBtn").addEventListener("click", () => {
    const q = questions[current];
    state[q.id].selected = [];
    state[q.id].text = "";
    queueSave(q.id, { immediate: true });
    renderQuestion();
  });

  document.addEventListener("keydown", (e) => {
    if (["INPUT", "TEXTAREA"].includes(e.target.tagName) && e.target.type !== "radio" && e.target.type !== "checkbox") return;
    if (e.key === "ArrowRight") goTo(current + 1);
    if (e.key === "ArrowLeft") goTo(current - 1);
  });

  /* ---------- Timer ---------- */
  function tick() {
    const remaining = Math.max(0, Math.round((deadline - Date.now()) / 1000));
    const h = Math.floor(remaining / 3600);
    const m = Math.floor((remaining % 3600) / 60);
    const s = remaining % 60;
    el("timerText").textContent = (h ? `${h}:` : "") + `${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
    const timer = el("timer");
    timer.classList.toggle("warning", remaining <= 300 && remaining > 60);
    timer.classList.toggle("danger", remaining <= 60);
    if (remaining === 300) toast("5 minutes left.", "warning");
    if (remaining === 60) toast("1 minute left — your test will be submitted automatically.", "warning");
    if (remaining <= 0) { submit(true); return; }
    setTimeout(tick, 1000 - (Date.now() % 1000));
  }

  /* ---------- Submission ---------- */
  async function submit(auto) {
    if (submitting) return;
    submitting = true;
    recordTime();
    setSaveStatus(auto ? "Time's up — submitting…" : "Submitting…");
    await flush();
    try {
      await api(cfg.submitUrl, { method: "POST", body: { auto: Boolean(auto) }, quiet: true });
      try { localStorage.removeItem(STORAGE_KEY); } catch (e) { /* ignore */ }
      window.removeEventListener("beforeunload", beforeUnload);
      window.location.href = cfg.resultUrl;
    } catch (err) {
      submitting = false;
      if (auto) {
        // Server will auto-submit on next access; keep retrying.
        setSaveStatus("Couldn't reach the server — retrying submission…", "warn");
        setTimeout(() => submit(true), 3000);
      } else {
        toast(err.message || "Couldn't submit. Please try again.", "error");
      }
    }
  }

  function openSubmitModal() {
    const c = counts();
    el("submitSummary").innerHTML = [
      ["Answered", c.answered, "good"], ["Not answered", questions.length - c.answered, "bad"], ["Marked", c.marked, ""],
    ].map(([label, n, tone]) => `<div class="col-4"><div class="bg-surface-2 rounded-xl p-2"><div class="fs-4 fw-bold ${tone ? "tone-" + tone : ""}">${n}</div><div class="small text-muted">${label}</div></div></div>`).join("");
    bootstrap.Modal.getOrCreateInstance(el("submitModal")).show();
  }
  el("submitBtnTop").addEventListener("click", openSubmitModal);
  el("submitBtnBottom").addEventListener("click", openSubmitModal);
  el("confirmSubmit").addEventListener("click", () => {
    el("confirmSubmit").disabled = true;
    submit(false);
  });

  function beforeUnload(e) {
    if (submitting) return undefined;
    recordTime();
    writeBackup();
    e.preventDefault();
    e.returnValue = "";
    return "";
  }
  window.addEventListener("beforeunload", beforeUnload);
  document.addEventListener("visibilitychange", () => { if (document.hidden) { recordTime(); flush(); } });

  /* ---------- Start ---------- */
  loadBackup();
  if (Object.keys(pending).length) { toast("Restored answers saved on this device.", "info", 3000); flush(); }
  const firstUnanswered = questions.findIndex((q) => !state[q.id].visited);
  current = firstUnanswered > 0 ? firstUnanswered : 0;
  renderQuestion();
  tick();
})();
