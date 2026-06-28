const sessionInput = document.querySelector("#session-id");
const messages = document.querySelector("#messages");
const chatForm = document.querySelector("#chat-form");
const questionInput = document.querySelector("#question-input");
const uploadForm = document.querySelector("#upload-form");
const fileInput = document.querySelector("#file-input");
const uploadStatus = document.querySelector("#upload-status");
const memoryStatus = document.querySelector("#memory-status");
const historyButton = document.querySelector("#history-button");
const clearButton = document.querySelector("#clear-button");
const topKSelect = document.querySelector("#top-k");

const savedSessionId = localStorage.getItem("agent_session_id");
sessionInput.value = savedSessionId || crypto.randomUUID();
localStorage.setItem("agent_session_id", sessionInput.value);

sessionInput.addEventListener("change", () => {
  localStorage.setItem("agent_session_id", sessionInput.value.trim());
});

function setStatus(element, text, type = "") {
  element.textContent = text;
  element.className = `status ${type}`.trim();
}

function appendMessage(role, text, sources = []) {
  const row = document.createElement("div");
  row.className = `message ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;

  if (sources.length > 0) {
    const sourceBox = document.createElement("div");
    sourceBox.className = "sources";
    sourceBox.innerHTML = "<strong>引用来源</strong>";

    const list = document.createElement("ul");
    sources.forEach((source) => {
      const item = document.createElement("li");
      item.textContent = `${source.source || "unknown"} / chunk ${source.chunk_index ?? "-"} / score ${source.score ?? "-"}`;
      list.appendChild(item);
    });
    sourceBox.appendChild(list);
    bubble.appendChild(sourceBox);
  }

  row.appendChild(bubble);
  messages.appendChild(row);
  messages.scrollTop = messages.scrollHeight;
}

uploadForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const file = fileInput.files[0];
  if (!file) {
    setStatus(uploadStatus, "请先选择一个文件", "error");
    return;
  }

  const formData = new FormData();
  formData.append("file", file);
  setStatus(uploadStatus, "正在上传并向量化...");

  try {
    const response = await fetch("/documents/upload", {
      method: "POST",
      body: formData,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "上传失败");
    }
    setStatus(uploadStatus, `${data.filename} 已入库，切片数：${data.chunks_stored}`, "ok");
  } catch (error) {
    setStatus(uploadStatus, error.message, "error");
  }
});

chatForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const question = questionInput.value.trim();
  const sessionId = sessionInput.value.trim();
  if (!question || !sessionId) {
    return;
  }

  appendMessage("user", question);
  questionInput.value = "";

  const submitButton = chatForm.querySelector("button");
  submitButton.disabled = true;

  try {
    const response = await fetch("/rag/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        question,
        session_id: sessionId,
        top_k: Number(topKSelect.value),
      }),
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "问答失败");
    }
    appendMessage("assistant", data.answer, data.sources || []);
    setStatus(memoryStatus, `会话已保存到 ${data.memory_backend}`, "ok");
  } catch (error) {
    appendMessage("assistant", `处理失败：${error.message}`);
  } finally {
    submitButton.disabled = false;
    questionInput.focus();
  }
});

historyButton.addEventListener("click", async () => {
  const sessionId = sessionInput.value.trim();
  if (!sessionId) return;

  try {
    const response = await fetch(`/sessions/${encodeURIComponent(sessionId)}/history`);
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "读取历史失败");
    }
    const count = data.messages?.length || 0;
    setStatus(memoryStatus, `当前会话共有 ${count} 条消息，后端：${data.backend}`, "ok");
  } catch (error) {
    setStatus(memoryStatus, error.message, "error");
  }
});

clearButton.addEventListener("click", async () => {
  const sessionId = sessionInput.value.trim();
  if (!sessionId) return;

  try {
    const response = await fetch(`/sessions/${encodeURIComponent(sessionId)}`, {
      method: "DELETE",
    });
    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.detail || "清空失败");
    }
    setStatus(memoryStatus, data.message, "ok");
  } catch (error) {
    setStatus(memoryStatus, error.message, "error");
  }
});
