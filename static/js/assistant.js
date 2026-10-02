/* PrepAI AI Study Assistant chat client. */
(function () {
  "use strict";

  const { api, toast, renderMarkdown, renderMath, escapeHtml } = window.PrepAI;
  const cfg = window.PREPAI_ASSISTANT;
  const $ = (id) => document.getElementById(id);
  const messages = $("messages");
  const input = $("chatText");
  let conversationId = cfg.conversationId;
  let busy = false;

  function scrollToBottom() { messages.scrollTop = messages.scrollHeight; }

  function autoresize() {
    input.style.height = "auto";
    input.style.height = Math.min(input.scrollHeight, 180) + "px";
  }

  function addMessage(role, content, extraClass = "") {
    $("welcome")?.remove();
    const wrap = document.createElement("div");
    wrap.className = `chat-msg ${role} ${extraClass}`.trim();
    const avatar = role === "user" ? escapeHtml(cfg.userInitial) : '<i class="bi bi-lightbulb"></i>';
    const body = role === "assistant" ? renderMarkdown(content) : escapeHtml(content);
    wrap.innerHTML = `<span class="avatar" aria-hidden="true">${avatar}</span><div class="chat-bubble ${role === "assistant" ? "prose" : ""}">${body}</div>`;
    messages.appendChild(wrap);
    if (role === "assistant") renderMath(wrap);
    scrollToBottom();
    return wrap;
  }

  function addTyping() {
    const el = addMessage("assistant", "");
    el.querySelector(".chat-bubble").innerHTML = '<span class="typing" aria-label="PrepAI is typing"><span></span><span></span><span></span></span>';
    return el;
  }

  function addError(message, text) {
    const el = addMessage("assistant", "", "error");
    el.querySelector(".chat-bubble").innerHTML = `<i class="bi bi-exclamation-triangle"></i> ${escapeHtml(message)}
      <div class="mt-2"><button type="button" class="btn btn-sm btn-ghost">Retry</button></div>`;
    el.querySelector("button").addEventListener("click", () => { el.remove(); send(text); });
  }

  async function ensureConversation() {
    if (conversationId) return conversationId;
    const body = { mode: $("modeSelect").value };
    if ($("subjectSelect").value) body.subject = Number($("subjectSelect").value);
    const conv = await api(cfg.listUrl, { method: "POST", body, quiet: true });
    conversationId = conv.id;
    history.replaceState(null, "", `/assistant/${conv.id}/`);
    $("subjectSelect").disabled = true;
    return conversationId;
  }

  function upsertSidebar(conv) {
    $("noConvs")?.remove();
    let link = document.querySelector(`[data-conv-id="${conv.id}"]`);
    if (!link) {
      link = document.createElement("a");
      link.href = `/assistant/${conv.id}/`;
      link.className = "conv-link active";
      link.dataset.convId = conv.id;
      link.innerHTML = '<i class="bi bi-chat-left-text"></i><span class="text-truncate"></span>';
      $("convList").prepend(link);
    }
    link.querySelector("span").textContent = conv.title;
    $("convTitle").textContent = conv.title;
  }

  async function send(text) {
    text = (text || "").trim();
    if (!text || busy) return;
    busy = true;
    $("sendBtn").disabled = true;
    addMessage("user", text);
    const typing = addTyping();
    try {
      const id = await ensureConversation();
      const data = await api(`${cfg.listUrl}${id}/messages/`, { method: "POST", body: { content: text }, quiet: true });
      typing.remove();
      addMessage("assistant", data.reply.content);
      upsertSidebar(data.conversation);
    } catch (err) {
      typing.remove();
      // The student's message wasn't stored on failure — drop the bubble and restore the text.
      messages.querySelectorAll(".chat-msg.user")[messages.querySelectorAll(".chat-msg.user").length - 1]?.remove();
      if (!input.value) { input.value = text; autoresize(); }
      addError(err.message || "AI service is temporarily unavailable. Please try again.", text);
    } finally {
      busy = false;
      $("sendBtn").disabled = false;
      input.focus();
    }
  }

  $("chatForm").addEventListener("submit", (e) => {
    e.preventDefault();
    const text = input.value;
    input.value = "";
    autoresize();
    send(text);
  });
  input.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey && !e.isComposing) {
      e.preventDefault();
      $("chatForm").requestSubmit();
    }
  });
  input.addEventListener("input", autoresize);

  document.addEventListener("click", (e) => {
    const chip = e.target.closest("[data-prompt]");
    if (chip) send(chip.dataset.prompt);
  });

  $("modeSelect").addEventListener("change", async () => {
    if (!conversationId) return;
    try {
      await api(`${cfg.listUrl}${conversationId}/`, { method: "PATCH", body: { mode: $("modeSelect").value }, quiet: true });
      toast("Mode updated", "success", 2000);
    } catch (err) { toast(err.message, "error"); }
  });

  scrollToBottom();
  autoresize();
  if (input.value.trim() && !input.disabled) input.focus();
})();
