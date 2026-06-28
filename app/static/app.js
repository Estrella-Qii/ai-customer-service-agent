const elements = {
  sessionIdInput: document.getElementById("sessionIdInput"),
  fileInput: document.getElementById("fileInput"),
  fileNameDisplay: document.getElementById("fileNameDisplay"),
  uploadBtn: document.getElementById("uploadBtn"),
  uploadStatus: document.getElementById("uploadStatus"),
  documentList: document.getElementById("documentList"),
  memoryStatus: document.getElementById("memoryStatus"),
  chatHistory: document.getElementById("chatHistory"),
  emptyState: document.getElementById("emptyState"),
  questionInput: document.getElementById("questionInput"),
  sendBtn: document.getElementById("sendBtn"),
  topKSelect: document.getElementById("topKSelect"),
  chatForm: document.getElementById("chatForm"),
  newSessionBtn: document.getElementById("newSessionBtn"),
  loadHistoryBtn: document.getElementById("loadHistoryBtn"),
  clearHistoryBtn: document.getElementById("clearHistoryBtn"),
  refreshDocsBtn: document.getElementById("refreshDocsBtn"),
};

document.addEventListener("DOMContentLoaded", () => {
  const savedSessionId = localStorage.getItem("agent_session_id");
  elements.sessionIdInput.value = savedSessionId || createSessionId();
  localStorage.setItem("agent_session_id", elements.sessionIdInput.value);

  elements.fileInput.addEventListener("change", updateSelectedFileName);
  elements.uploadBtn.addEventListener("click", uploadDocument);
  elements.chatForm.addEventListener("submit", handleChatSubmit);
  elements.newSessionBtn.addEventListener("click", generateSessionId);
  elements.loadHistoryBtn.addEventListener("click", loadHistory);
  elements.clearHistoryBtn.addEventListener("click", clearHistory);
  elements.refreshDocsBtn.addEventListener("click", loadDocuments);
  elements.sessionIdInput.addEventListener("change", saveSessionId);

  elements.questionInput.addEventListener("keydown", (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      askQuestion();
    }
  });

  elements.questionInput.addEventListener("input", resizeQuestionInput);
  loadDocuments();
});

function createSessionId() {
  if (crypto.randomUUID) {
    return `session_${crypto.randomUUID().slice(0, 8)}`;
  }
  return `session_${Math.random().toString(36).slice(2, 10)}`;
}

function saveSessionId() {
  const sessionId = getSessionId();
  localStorage.setItem("agent_session_id", sessionId);
}

function generateSessionId() {
  elements.sessionIdInput.value = createSessionId();
  saveSessionId();
  resetChat("已生成新会话，可以开始新的对话。");
  setStatus(elements.memoryStatus, "新会话已创建", "success");
}

function getSessionId() {
  const value = elements.sessionIdInput.value.trim();
  if (value) return value;

  const sessionId = createSessionId();
  elements.sessionIdInput.value = sessionId;
  return sessionId;
}

function resetChat(message) {
  elements.chatHistory.innerHTML = "";
  elements.emptyState.style.display = "block";
  elements.emptyState.querySelector("p").textContent = message;
  elements.chatHistory.appendChild(elements.emptyState);
}

function updateSelectedFileName() {
  const file = elements.fileInput.files[0];
  elements.fileNameDisplay.textContent = file ? file.name : "点击选择文档";
}

async function uploadDocument() {
  const file = elements.fileInput.files[0];
  if (!file) {
    setStatus(elements.uploadStatus, "请先选择一个 .txt、.md 或 .pdf 文件", "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);

  elements.uploadBtn.disabled = true;
  elements.uploadBtn.textContent = "上传中...";
  setStatus(elements.uploadStatus, "正在解析、切片并写入向量库...");

  try {
    const response = await fetch("/documents/upload", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "上传失败");
    }

    setStatus(
      elements.uploadStatus,
      `上传成功：${data.filename}，切片数：${data.chunks_stored}`,
      "success",
    );
    elements.fileInput.value = "";
    elements.fileNameDisplay.textContent = "点击选择文档";
    loadDocuments();
  } catch (error) {
    setStatus(elements.uploadStatus, error.message || "网络异常，无法上传文档", "error");
  } finally {
    elements.uploadBtn.disabled = false;
    elements.uploadBtn.textContent = "上传至知识库";
  }
}

async function loadDocuments() {
  elements.documentList.innerHTML = '<p class="muted-text">正在加载文档...</p>';

  try {
    const response = await fetch("/documents");
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "获取文档列表失败");
    }

    renderDocuments(data.documents || []);
  } catch (error) {
    elements.documentList.innerHTML = `<p class="muted-text">${error.message || "获取文档列表失败"}</p>`;
  }
}

function renderDocuments(documents) {
  if (documents.length === 0) {
    elements.documentList.innerHTML = '<p class="muted-text">暂无已入库文档</p>';
    return;
  }

  elements.documentList.innerHTML = "";
  documents.forEach((documentItem) => {
    const item = document.createElement("div");
    item.className = "document-item";

    const main = document.createElement("div");
    main.className = "document-main";

    const info = document.createElement("div");
    const name = document.createElement("div");
    name.className = "document-name";
    name.textContent = documentItem.filename;

    const meta = document.createElement("div");
    meta.className = "document-meta";
    meta.textContent = `${documentItem.chunks} 个片段`;

    info.appendChild(name);
    info.appendChild(meta);

    const deleteButton = document.createElement("button");
    deleteButton.className = "delete-doc-btn";
    deleteButton.type = "button";
    deleteButton.textContent = "删除";
    deleteButton.addEventListener("click", () => deleteDocument(documentItem.filename));

    main.appendChild(info);
    main.appendChild(deleteButton);
    item.appendChild(main);

    if (documentItem.preview) {
      const preview = document.createElement("div");
      preview.className = "document-preview";
      preview.textContent = documentItem.preview;
      item.appendChild(preview);
    }

    elements.documentList.appendChild(item);
  });
}

async function deleteDocument(filename) {
  if (!confirm(`确定要删除文档「${filename}」吗？`)) {
    return;
  }

  try {
    const response = await fetch(`/documents/${encodeURIComponent(filename)}`, {
      method: "DELETE",
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "删除失败");
    }
    setStatus(elements.uploadStatus, `已删除：${filename}，片段数：${data.deleted_chunks}`, "success");
    loadDocuments();
  } catch (error) {
    setStatus(elements.uploadStatus, error.message || "删除失败", "error");
  }
}

function handleChatSubmit(event) {
  event.preventDefault();
  askQuestion();
}

async function askQuestion() {
  const question = elements.questionInput.value.trim();
  if (!question) return;

  const sessionId = getSessionId();
  saveSessionId();
  elements.emptyState.style.display = "none";
  renderMessage("user", question);

  elements.questionInput.value = "";
  resizeQuestionInput();

  const loadingId = renderLoading();
  elements.sendBtn.disabled = true;
  elements.questionInput.disabled = true;

  try {
    const response = await fetch("/rag/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        top_k: Number(elements.topKSelect.value),
        session_id: sessionId,
      }),
    });

    const data = await response.json();
    removeElement(loadingId);

    if (!response.ok) {
      throw new Error(data.detail || "问答失败");
    }

    renderMessage("ai", data.answer || data.reply || "未返回回答", data.sources || []);
    setStatus(elements.memoryStatus, `会话已保存到 ${data.memory_backend || "memory"}`, "success");
  } catch (error) {
    removeElement(loadingId);
    renderMessage("ai", `处理失败：${error.message || "无法连接到服务端"}`);
  } finally {
    elements.sendBtn.disabled = false;
    elements.questionInput.disabled = false;
    elements.questionInput.focus();
  }
}

async function loadHistory() {
  const sessionId = getSessionId();
  saveSessionId();
  setStatus(elements.memoryStatus, "正在加载历史...");

  try {
    const response = await fetch(`/sessions/${encodeURIComponent(sessionId)}/history`);
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "读取历史失败");
    }

    elements.chatHistory.innerHTML = "";
    const history = data.messages || [];

    if (history.length === 0) {
      resetChat("当前会话暂无历史记录。");
    } else {
      history.forEach((message) => {
        renderMessage(message.role === "assistant" ? "ai" : "user", message.content);
      });
    }

    setStatus(elements.memoryStatus, `已加载 ${history.length} 条历史，后端：${data.backend}`, "success");
  } catch (error) {
    setStatus(elements.memoryStatus, error.message || "读取历史失败", "error");
  }
}

async function clearHistory() {
  const sessionId = getSessionId();
  saveSessionId();

  if (!confirm("确定要清空当前会话的全部聊天记录吗？")) {
    return;
  }

  try {
    const response = await fetch(`/sessions/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
    });
    const data = await response.json();

    if (!response.ok) {
      throw new Error(data.detail || "清空失败");
    }

    resetChat("会话已清空，可以开始新的对话。");
    setStatus(elements.memoryStatus, data.message || "会话记忆已清空", "success");
  } catch (error) {
    setStatus(elements.memoryStatus, error.message || "清空历史失败", "error");
  }
}

function renderMessage(role, text, sources = []) {
  const isUser = role === "user";
  const wrapper = document.createElement("div");
  wrapper.className = `message-wrapper ${isUser ? "user" : "ai"}`;

  const bubble = document.createElement("div");
  bubble.className = "message-bubble";
  bubble.textContent = text;
  wrapper.appendChild(bubble);

  if (!isUser && sources.length > 0) {
    const sourcesContainer = document.createElement("div");
    sourcesContainer.className = "sources-container";

    sources.forEach((source) => {
      const card = document.createElement("div");
      card.className = "source-card";

      const header = document.createElement("div");
      header.className = "source-header";

      const title = document.createElement("span");
      title.textContent = `${source.source || "未知文档"} / Chunk ${source.chunk_index ?? "-"}`;

      const score = document.createElement("span");
      score.className = "source-score";
      score.textContent = `Score ${source.score ?? "N/A"}`;

      header.appendChild(title);
      header.appendChild(score);
      card.appendChild(header);
      sourcesContainer.appendChild(card);
    });

    wrapper.appendChild(sourcesContainer);
  }

  elements.chatHistory.appendChild(wrapper);
  scrollToBottom();
}

function renderLoading() {
  const id = `loading_${Date.now()}`;
  const wrapper = document.createElement("div");
  wrapper.className = "message-wrapper ai";
  wrapper.id = id;
  wrapper.innerHTML = `
    <div class="message-bubble">
      <div class="typing-indicator">
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
        <div class="typing-dot"></div>
      </div>
    </div>
  `;
  elements.chatHistory.appendChild(wrapper);
  scrollToBottom();
  return id;
}

function removeElement(id) {
  const element = document.getElementById(id);
  if (element) element.remove();
}

function scrollToBottom() {
  window.setTimeout(() => {
    elements.chatHistory.scrollTop = elements.chatHistory.scrollHeight;
  }, 50);
}

function resizeQuestionInput() {
  elements.questionInput.style.height = "auto";
  elements.questionInput.style.height = `${elements.questionInput.scrollHeight}px`;
}

function setStatus(element, message, type = "") {
  element.textContent = message;
  element.className = "status-message";
  if (type) {
    element.classList.add(`status-${type}`);
  }
}
