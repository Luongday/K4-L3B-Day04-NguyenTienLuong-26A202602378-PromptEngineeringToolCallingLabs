const state = {
  sessionId: null,
  busy: false,
};

const elements = {
  artifact: document.querySelector("#artifact-value"),
  provider: document.querySelector("#provider-value"),
  model: document.querySelector("#model-value"),
  transcript: document.querySelector("#transcript-value"),
  statusDot: document.querySelector("#status-dot"),
  statusText: document.querySelector("#status-text"),
  messages: document.querySelector("#messages"),
  form: document.querySelector("#chat-form"),
  input: document.querySelector("#message-input"),
  send: document.querySelector("#send-button"),
  newSession: document.querySelector("#new-session"),
  charCount: document.querySelector("#char-count"),
};

async function requestJson(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...options,
  });
  const payload = await response.json();
  if (!response.ok) {
    throw new Error(payload.message || payload.error || `HTTP ${response.status}`);
  }
  return payload;
}

function setStatus(label, kind = "ready") {
  elements.statusText.textContent = label;
  elements.statusDot.className = kind;
}

function setBusy(value) {
  state.busy = value;
  elements.input.disabled = value;
  elements.send.disabled = value;
  elements.newSession.disabled = value;
  setStatus(value ? "Agent đang xử lý" : "Sẵn sàng", value ? "busy" : "ready");
}

function applySession(session) {
  state.sessionId = session.session_id;
  elements.artifact.textContent = session.artifact_version;
  elements.provider.textContent = session.provider;
  elements.model.textContent = session.model || "default";
  elements.transcript.textContent = session.transcript_path;
}

function createElement(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function appendMessage(role, text, turn = null) {
  const article = createElement("article", `message ${role}-message`);
  const avatar = createElement("div", "avatar", role === "user" ? "YOU" : "AI");
  const content = createElement("div", "message-content");
  const meta = createElement("div", "message-meta", role === "user" ? "User" : "Helpdesk agent");
  const paragraph = createElement("p", "", text || "(Không có nội dung trả lời)");
  content.append(meta, paragraph);

  if (turn && Array.isArray(turn.tool_events) && turn.tool_events.length > 0) {
    content.appendChild(buildTrace(turn.tool_events));
  }
  if (turn?.error) {
    content.appendChild(createElement("div", "turn-error", `Provider error: ${turn.error}`));
  }

  if (role === "user") article.append(content, avatar);
  else article.append(avatar, content);
  elements.messages.appendChild(article);
  elements.messages.scrollTop = elements.messages.scrollHeight;
  return article;
}

function buildTrace(events) {
  const details = createElement("details", "trace");
  details.open = true;
  const summary = createElement("summary", "", `${events.length} tool event${events.length > 1 ? "s" : ""}`);
  const grid = createElement("div", "trace-grid");

  for (const event of events) {
    const result = event.result || {};
    const hasError = Boolean(result.error);
    const card = createElement("section", `tool-card${hasError ? " error" : ""}`);
    const header = createElement("div", "tool-header");
    header.append(
      createElement("span", "tool-name", event.tool || "unknown_tool"),
      createElement("span", "tool-state", hasError ? "error" : "result"),
    );
    card.append(
      header,
      createElement("div", "code-label", "Input arguments"),
      createElement("pre", "", JSON.stringify(event.args || {}, null, 2)),
      createElement("div", "code-label", hasError ? "Error result" : "Tool result"),
      createElement("pre", "", JSON.stringify(result, null, 2)),
    );
    grid.appendChild(card);
  }

  details.append(summary, grid);
  return details;
}

async function createSession({ clearMessages = false } = {}) {
  setBusy(true);
  try {
    const session = await requestJson("/api/session", { method: "POST", body: "{}" });
    applySession(session);
    if (clearMessages) {
      elements.messages.replaceChildren();
      appendMessage("assistant", "Phiên mới đã sẵn sàng. Hãy nhập một tình huống IT Helpdesk dùng dữ liệu giả lập.");
    }
    elements.input.focus();
  } catch (error) {
    setStatus("Lỗi khởi tạo", "error");
    appendMessage("assistant", `Không thể tạo phiên UI: ${error.message}`);
  } finally {
    setBusy(false);
  }
}

async function sendMessage(message) {
  if (!state.sessionId || state.busy) return;
  appendMessage("user", message);
  setBusy(true);
  try {
    const payload = await requestJson("/api/chat", {
      method: "POST",
      body: JSON.stringify({ session_id: state.sessionId, message }),
    });
    elements.transcript.textContent = payload.transcript_path;
    appendMessage("assistant", payload.turn.assistant_text, payload.turn);
    if (payload.turn.status === "provider_error") setStatus("Provider error", "error");
  } catch (error) {
    setStatus("Lỗi yêu cầu", "error");
    appendMessage("assistant", `UI request failed: ${error.message}`);
  } finally {
    setBusy(false);
    elements.input.focus();
  }
}

elements.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const message = elements.input.value.trim();
  if (!message) return;
  elements.input.value = "";
  elements.charCount.textContent = "0 / 8000";
  await sendMessage(message);
});

elements.input.addEventListener("input", () => {
  elements.charCount.textContent = `${elements.input.value.length} / 8000`;
});

elements.input.addEventListener("keydown", (event) => {
  if (event.key === "Enter" && event.ctrlKey) {
    event.preventDefault();
    elements.form.requestSubmit();
  }
});

elements.newSession.addEventListener("click", () => createSession({ clearMessages: true }));

createSession();
