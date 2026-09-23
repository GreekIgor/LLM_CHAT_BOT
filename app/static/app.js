const form = document.querySelector("#chat-form");
const input = document.querySelector("#message-input");
const conversation = document.querySelector("#conversation");
const sendButton = document.querySelector("#send-button");
const fileInput = document.querySelector("#application-file");
const resetButton = document.querySelector("#reset-button");
let conversationId = sessionStorage.getItem("tatek-conversation-id") || null;

function resetConversation() {
  conversationId = null;
  sessionStorage.removeItem("tatek-conversation-id");
  conversation.innerHTML = "";
  addMessage("Диалог сброшен. С чего начнём?", "assistant");
  input.focus();
}

function addMessage(text, sender, sources = []) {
  const article = document.createElement("article");
  article.className = `message ${sender}-message`;
  if (sender === "assistant") article.innerHTML = '<div class="avatar">T</div>';
  const bubble = document.createElement("div");
  bubble.className = "bubble";
  bubble.textContent = text;
  article.append(bubble);
  conversation.append(article);
  if (sources.length) {
    const details = document.createElement("details");
    details.className = "sources";
    details.innerHTML = `<summary>Источники: ${sources.length}</summary>`;
    sources.forEach((source) => { const excerpt = document.createElement("p"); excerpt.textContent = `${source.document}: ${source.excerpt}`; details.append(excerpt); });
    conversation.append(details);
  }
  conversation.scrollTop = conversation.scrollHeight;
}

function addPendingMessage() {
  const article = document.createElement("article");
  article.className = "message assistant-message pending-message";
  article.innerHTML = '<div class="avatar">T</div><div class="bubble">Проверяю информацию<span class="loading-dots" aria-hidden="true"></span></div>';
  conversation.append(article);
  conversation.scrollTop = conversation.scrollHeight;
  return article;
}

async function sendMessage(text) {
  const message = text.trim();
  if (!message) return;
  const controller = new AbortController();
  const timeoutId = window.setTimeout(() => controller.abort(), 90000);
  addMessage(message, "user"); input.value = ""; input.style.height = "auto"; sendButton.disabled = true;
  const pendingMessage = addPendingMessage();
  try {
    const response = await fetch("/api/chat", { method:"POST", headers:{"Content-Type":"application/json"}, body:JSON.stringify({message, conversation_id:conversationId}), signal:controller.signal });
    if (!response.ok) throw new Error("Chat request failed");
    const payload = await response.json(); conversationId = payload.conversation_id; sessionStorage.setItem("tatek-conversation-id", conversationId); addMessage(payload.message, "assistant", payload.sources);
  } catch (error) {
    const response = error.name === "AbortError"
      ? "Ответ занимает больше времени, чем обычно. Попробуйте отправить вопрос ещё раз или вернитесь чуть позже."
      : "Не получилось получить ответ. Проверьте подключение и попробуйте ещё раз через минуту.";
    addMessage(response, "assistant");
  } finally {
    window.clearTimeout(timeoutId);
    pendingMessage.remove();
    sendButton.disabled = false;
    input.focus();
  }
}

form.addEventListener("submit", (event) => { event.preventDefault(); sendMessage(input.value); });
input.addEventListener("input", () => { input.style.height="auto"; input.style.height=`${Math.min(input.scrollHeight,160)}px`; });
input.addEventListener("keydown", (event) => { if (event.key === "Enter" && !event.shiftKey) { event.preventDefault(); form.requestSubmit(); } });
document.querySelectorAll("[data-prompt]").forEach((button) => button.addEventListener("click", () => sendMessage(button.dataset.prompt)));
resetButton.addEventListener("click", resetConversation);
fileInput.addEventListener("change", async () => {
  const file = fileInput.files?.[0]; if (!file) return;
  if (!conversationId) { addMessage("Сначала начните оформление заявки на технические условия, затем приложите документ.", "assistant"); fileInput.value=""; return; }
  const body = new FormData(); body.append("file", file); addMessage(`Проверяю документ «${file.name}»...`, "assistant");
  try {
    const response = await fetch(`/api/conversations/${encodeURIComponent(conversationId)}/documents`, {method:"POST", body});
    const payload = await response.json(); if (!response.ok) throw new Error(payload.detail || "Upload failed"); addMessage(`${payload.document}: ${payload.message}`, "assistant");
  } catch (error) { addMessage(`Документ не принят: ${error.message}`, "assistant"); }
  finally { fileInput.value=""; }
});