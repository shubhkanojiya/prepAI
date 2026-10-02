/* ==========================================================================
   PrepAI core JavaScript — shared by every page.
   Exposes window.PrepAI = { api, toast, renderMarkdown, renderMath, confirm }.
   ========================================================================== */
(function () {
  "use strict";

  const PrepAI = (window.PrepAI = window.PrepAI || {});
  const THEME_KEY = "prepai-theme";

  /* ---------------- Theme ---------------- */
  function resolveTheme(pref) {
    if (pref === "light" || pref === "dark") return pref;
    return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }

  function applyTheme(pref) {
    document.documentElement.setAttribute("data-bs-theme", resolveTheme(pref));
    document.querySelectorAll("[data-theme-icon]").forEach((icon) => {
      icon.className = resolveTheme(pref) === "dark" ? "bi bi-sun" : "bi bi-moon-stars";
    });
    document.dispatchEvent(new CustomEvent("prepai:themechange"));
  }

  function currentPref() {
    try {
      return localStorage.getItem(THEME_KEY) || document.documentElement.dataset.userTheme || "system";
    } catch (e) {
      return document.documentElement.dataset.userTheme || "system";
    }
  }

  function initTheme() {
    applyTheme(currentPref());
    window.matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => {
      if (currentPref() === "system") applyTheme("system");
    });
    document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const next = resolveTheme(currentPref()) === "dark" ? "light" : "dark";
        try { localStorage.setItem(THEME_KEY, next); } catch (e) { /* storage unavailable */ }
        applyTheme(next);
        if (document.body.dataset.authenticated === "true") {
          api("/api/v1/auth/theme/", { method: "POST", body: { theme: next }, quiet: true }).catch(() => {});
        }
      });
    });
  }

  /* ---------------- API helper ---------------- */
  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(^|;\\s*)" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[2]) : null;
  }

  class ApiError extends Error {
    constructor(message, status, data) {
      super(message);
      this.status = status;
      this.data = data;
    }
  }

  /**
   * fetch wrapper: JSON by default, CSRF header, friendly errors.
   * options: { method, body (object|FormData), quiet (no toast on error), signal }
   */
  async function api(url, options = {}) {
    const headers = { Accept: "application/json", "X-Requested-With": "XMLHttpRequest" };
    const init = { method: options.method || "GET", headers, credentials: "same-origin", signal: options.signal };
    if (init.method !== "GET") headers["X-CSRFToken"] = getCookie("csrftoken") || "";
    if (options.body instanceof FormData) {
      init.body = options.body;
    } else if (options.body !== undefined) {
      headers["Content-Type"] = "application/json";
      init.body = JSON.stringify(options.body);
    }

    let response;
    try {
      response = await fetch(url, init);
    } catch (err) {
      if (err.name === "AbortError") throw err;
      const message = navigator.onLine
        ? "Couldn't reach PrepAI. Please check your connection and try again."
        : "You appear to be offline. Reconnect and try again.";
      if (!options.quiet) toast(message, "error");
      throw new ApiError(message, 0, null);
    }

    let data = null;
    const text = await response.text();
    try { data = text ? JSON.parse(text) : null; } catch (e) { data = null; }

    if (!response.ok) {
      let message = (data && data.error && data.error.message) || "Something went wrong. Please try again.";
      if (response.status === 401 || response.status === 403) {
        if (document.body.dataset.authenticated !== "true") message = "Please sign in to continue.";
      }
      if (!options.quiet) toast(message, "error");
      throw new ApiError(message, response.status, data);
    }
    return data;
  }

  /* ---------------- Toasts ---------------- */
  function toast(message, type = "info", timeout = 4500) {
    let stack = document.querySelector(".toast-stack");
    if (!stack) {
      stack = document.createElement("div");
      stack.className = "toast-stack";
      stack.setAttribute("aria-live", "polite");
      document.body.appendChild(stack);
    }
    const icons = { success: "check-circle-fill", error: "exclamation-triangle-fill", warning: "exclamation-circle-fill", info: "info-circle-fill" };
    const el = document.createElement("div");
    el.className = `pa-toast ${type}`;
    el.setAttribute("role", type === "error" ? "alert" : "status");
    el.innerHTML = `<i class="bi bi-${icons[type] || icons.info} mt-1"></i><div class="flex-grow-1"></div>
      <button type="button" class="btn-close btn-sm ms-2" aria-label="Dismiss"></button>`;
    el.querySelector(".flex-grow-1").textContent = message;
    el.querySelector(".btn-close").addEventListener("click", () => el.remove());
    stack.appendChild(el);
    if (timeout) setTimeout(() => el.remove(), timeout);
  }

  /* ---------------- Confirmation dialog ---------------- */
  function confirmDialog({ title = "Are you sure?", message = "", confirmText = "Confirm", danger = false } = {}) {
    return new Promise((resolve) => {
      const modalEl = document.getElementById("confirmModal");
      if (!modalEl || !window.bootstrap) { resolve(window.confirm(message || title)); return; }
      modalEl.querySelector(".modal-title").textContent = title;
      modalEl.querySelector(".modal-body p").textContent = message;
      const ok = modalEl.querySelector("[data-confirm-ok]");
      ok.textContent = confirmText;
      ok.className = `btn ${danger ? "btn-danger" : "btn-primary"}`;
      const modal = bootstrap.Modal.getOrCreateInstance(modalEl);
      let result = false;
      const onOk = () => { result = true; modal.hide(); };
      ok.addEventListener("click", onOk, { once: true });
      modalEl.addEventListener("hidden.bs.modal", () => { ok.removeEventListener("click", onOk); resolve(result); }, { once: true });
      modal.show();
    });
  }

  // <form data-confirm="message"> or <button data-confirm="message">
  function initConfirmForms() {
    document.addEventListener("submit", async (event) => {
      const form = event.target;
      const message = form.dataset.confirm;
      if (!message || form.dataset.confirmed === "1") return;
      event.preventDefault();
      const ok = await confirmDialog({ title: form.dataset.confirmTitle || "Please confirm", message,
        confirmText: form.dataset.confirmButton || "Confirm", danger: form.dataset.confirmDanger === "true" });
      if (ok) { form.dataset.confirmed = "1"; form.submit(); }
    });
  }

  /* ---------------- Markdown (safe: escape first) ---------------- */
  function escapeHtml(text) {
    return String(text).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  }

  function inline(text) {
    return text
      .replace(/`([^`]+)`/g, "<code>$1</code>")
      .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
      .replace(/(^|[^*\w])\*(?!\s)(.+?)(?<!\s)\*(?!\w)/g, "$1<em>$2</em>");
  }

  function renderMarkdown(source) {
    if (!source) return "";
    const lines = escapeHtml(source).replace(/\r\n/g, "\n").split("\n");
    const out = [];
    let para = [], listType = null, inCode = false, inTable = false;
    const flushPara = () => { if (para.length) { out.push("<p>" + inline(para.join("<br>")) + "</p>"); para = []; } };
    const closeList = () => { if (listType) { out.push(`</${listType}>`); listType = null; } };
    const closeTable = () => { if (inTable) { out.push("</tbody></table></div>"); inTable = false; } };

    for (const raw of lines) {
      const line = raw.trim();
      if (line.startsWith("```")) {
        flushPara(); closeList(); closeTable();
        out.push(inCode ? "</code></pre>" : "<pre><code>");
        inCode = !inCode;
        continue;
      }
      if (inCode) { out.push(raw + "\n"); continue; }
      if (/^\|.*\|$/.test(line)) {
        if (/^\|[\s:|-]+\|$/.test(line)) continue; // separator row
        flushPara(); closeList();
        const cells = line.slice(1, -1).split("|").map((c) => inline(c.trim()));
        if (!inTable) {
          out.push('<div class="table-responsive"><table class="table table-sm"><thead><tr>' +
            cells.map((c) => `<th>${c}</th>`).join("") + "</tr></thead><tbody>");
          inTable = true;
        } else {
          out.push("<tr>" + cells.map((c) => `<td>${c}</td>`).join("") + "</tr>");
        }
        continue;
      }
      closeTable();
      const heading = line.match(/^(#{1,4})\s+(.*)$/);
      const bullet = line.match(/^[-*]\s+(.*)$/);
      const numbered = line.match(/^\d+[.)]\s+(.*)$/);
      if (heading) {
        flushPara(); closeList();
        const level = Math.min(heading[1].length + 2, 6);
        out.push(`<h${level}>${inline(heading[2])}</h${level}>`);
      } else if (bullet || numbered) {
        flushPara();
        const wanted = bullet ? "ul" : "ol";
        if (listType !== wanted) { closeList(); out.push(`<${wanted}>`); listType = wanted; }
        out.push("<li>" + inline((bullet || numbered)[1]) + "</li>");
      } else if (!line) {
        flushPara(); closeList();
      } else {
        closeList();
        para.push(line);
      }
    }
    flushPara(); closeList(); closeTable();
    if (inCode) out.push("</code></pre>");
    return out.join("\n");
  }

  function renderMath(element) {
    if (!element || typeof window.renderMathInElement !== "function") return;
    try {
      window.renderMathInElement(element, {
        delimiters: [
          { left: "$$", right: "$$", display: true },
          { left: "$", right: "$", display: false },
          { left: "\\(", right: "\\)", display: false },
          { left: "\\[", right: "\\]", display: true },
        ],
        throwOnError: false,
      });
    } catch (e) { /* math rendering is progressive enhancement */ }
  }

  /* ---------------- Bookmarks ---------------- */
  function initBookmarks() {
    document.addEventListener("click", async (event) => {
      const btn = event.target.closest("[data-bookmark]");
      if (!btn) return;
      event.preventDefault();
      if (document.body.dataset.authenticated !== "true") {
        window.location.href = "/accounts/login/?next=" + encodeURIComponent(location.pathname);
        return;
      }
      btn.disabled = true;
      try {
        const data = await api("/api/v1/bookmarks/toggle/", {
          method: "POST", body: { kind: btn.dataset.kind, object_id: Number(btn.dataset.id) },
        });
        document.querySelectorAll(`[data-bookmark][data-kind="${btn.dataset.kind}"][data-id="${btn.dataset.id}"]`).forEach((b) => {
          b.classList.toggle("active", data.bookmarked);
          b.setAttribute("aria-pressed", data.bookmarked ? "true" : "false");
          const icon = b.querySelector(".bi");
          if (icon) icon.className = data.bookmarked ? "bi bi-bookmark-fill" : "bi bi-bookmark";
          const label = b.querySelector("[data-label]");
          if (label) label.textContent = data.bookmarked ? "Saved" : "Save";
        });
        if (btn.dataset.removeOnUnsave && !data.bookmarked) {
          btn.closest("[data-bookmark-row]")?.remove();
        }
        toast(data.bookmarked ? "Saved to your bookmarks" : "Removed from bookmarks", "success", 2500);
      } catch (e) { /* toast already shown */ }
      finally { btn.disabled = false; }
    });
  }

  /* ---------------- Share ---------------- */
  function initShare() {
    document.addEventListener("click", async (event) => {
      const btn = event.target.closest("[data-share]");
      if (!btn) return;
      const url = btn.dataset.url ? new URL(btn.dataset.url, location.origin).href : location.href;
      const title = btn.dataset.title || document.title;
      if (navigator.share) {
        try { await navigator.share({ title, url }); } catch (e) { /* cancelled */ }
      } else {
        try { await navigator.clipboard.writeText(url); toast("Link copied to clipboard", "success", 2500); }
        catch (e) { toast("Copy this link: " + url, "info", 8000); }
      }
    });
  }

  /* ---------------- Dependent selects & auto-submit filters ---------------- */
  function initDependentSelects() {
    document.querySelectorAll("select[data-depends-on]").forEach((child) => {
      const parent = document.getElementById(child.dataset.dependsOn);
      if (!parent) return;
      parent.addEventListener("change", async () => {
        const placeholder = child.multiple ? null : child.querySelector("option[value='']");
        child.innerHTML = "";
        if (placeholder) child.appendChild(placeholder);
        child.dispatchEvent(new Event("change"));
        if (!parent.value) return;
        try {
          const items = await api(child.dataset.source + encodeURIComponent(parent.value), { quiet: true });
          (Array.isArray(items) ? items : items.results || []).forEach((item) => {
            const opt = document.createElement("option");
            opt.value = item.id;
            opt.textContent = item.name;
            child.appendChild(opt);
          });
        } catch (e) { toast("Couldn't load options. Please try again.", "error"); }
      });
    });
  }

  function initAutoFilters() {
    document.querySelectorAll("form[data-auto-submit]").forEach((form) => {
      form.querySelectorAll("select").forEach((select) => {
        select.addEventListener("change", () => {
          // Changing a parent level resets the levels below it.
          const order = ["board", "class_level", "subject", "chapter", "topic"];
          const idx = order.indexOf(select.name);
          if (idx >= 0) {
            order.slice(idx + 1).forEach((name) => {
              const el = form.querySelector(`[name="${name}"]`);
              if (el) el.value = "";
            });
          }
          const page = form.querySelector("[name='page']");
          if (page) page.value = "";
          form.requestSubmit ? form.requestSubmit() : form.submit();
        });
      });
    });
  }

  /* ---------------- Global search suggestions ---------------- */
  function initSearch() {
    document.querySelectorAll("[data-search]").forEach((shell) => {
      const input = shell.querySelector("input[name='q']");
      const panel = shell.querySelector(".search-suggest");
      if (!input || !panel) return;
      let timer = null, controller = null, active = -1;

      const hide = () => { panel.classList.remove("show"); active = -1; };
      const icons = { subject: "book", chapter: "bookmark", topic: "diagram-3", paper: "file-earmark-text", popular: "graph-up", recent: "clock-history" };

      function render(data) {
        const suggestions = data.suggestions || [];
        const recent = data.recent || [];
        if (!suggestions.length && !recent.length) { hide(); return; }
        panel.innerHTML = "";
        const addGroup = (label, items, mapper) => {
          if (!items.length) return;
          const heading = document.createElement("div");
          heading.className = "suggest-label";
          heading.textContent = label;
          panel.appendChild(heading);
          items.forEach((item) => panel.appendChild(mapper(item)));
        };
        const link = (text, href, icon) => {
          const a = document.createElement("a");
          a.href = href;
          a.innerHTML = `<i class="bi bi-${icon} text-muted"></i><span class="text-truncate"></span>`;
          a.querySelector("span").textContent = text;
          return a;
        };
        addGroup("Recent searches", recent, (q) => link(q, "/search/?q=" + encodeURIComponent(q), icons.recent));
        addGroup("Suggestions", suggestions, (s) => link(s.text, s.url || "/search/?q=" + encodeURIComponent(s.text), icons[s.type] || "search"));
        const ask = link(`Ask AI: “${input.value.trim()}”`, "/assistant/?q=" + encodeURIComponent(input.value.trim()), "stars");
        if (input.value.trim().length > 3) panel.appendChild(ask);
        panel.classList.add("show");
      }

      async function fetchSuggestions() {
        if (controller) controller.abort();
        controller = new AbortController();
        try {
          const data = await api("/api/v1/search/suggestions/?q=" + encodeURIComponent(input.value.trim()),
            { quiet: true, signal: controller.signal });
          render(data);
        } catch (e) { /* ignore */ }
      }

      input.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(fetchSuggestions, 180); });
      input.addEventListener("focus", () => { if (!input.value.trim()) fetchSuggestions(); });
      input.addEventListener("keydown", (e) => {
        const links = [...panel.querySelectorAll("a")];
        if (!panel.classList.contains("show") || !links.length) return;
        if (e.key === "ArrowDown" || e.key === "ArrowUp") {
          e.preventDefault();
          active = (active + (e.key === "ArrowDown" ? 1 : -1) + links.length) % links.length;
          links.forEach((l, i) => l.classList.toggle("active", i === active));
        } else if (e.key === "Enter" && active >= 0) {
          e.preventDefault();
          window.location.href = links[active].href;
        } else if (e.key === "Escape") { hide(); }
      });
      document.addEventListener("click", (e) => { if (!shell.contains(e.target)) hide(); });
    });
  }

  /* ---------------- Misc ---------------- */
  function initMessages() {
    document.querySelectorAll("[data-django-message]").forEach((el) => {
      toast(el.textContent.trim(), el.dataset.level || "info");
      el.remove();
    });
  }

  function initMarkdownBlocks() {
    document.querySelectorAll("[data-render-markdown]").forEach((el) => {
      el.innerHTML = renderMarkdown(el.textContent);
      renderMath(el);
    });
    document.querySelectorAll("[data-render-math]").forEach((el) => renderMath(el));
  }

  Object.assign(PrepAI, { api, ApiError, toast, confirm: confirmDialog, renderMarkdown, renderMath, escapeHtml });

  document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    initMessages();
    initBookmarks();
    initShare();
    initDependentSelects();
    initAutoFilters();
    initSearch();
    initConfirmForms();
    initMarkdownBlocks();
  });
  // KaTeX loads with `defer`; re-render math once it is available.
  window.addEventListener("load", () => {
    document.querySelectorAll("[data-render-markdown], [data-render-math]").forEach((el) => renderMath(el));
  });
})();
