"use strict";

(function () {
  const { fetchJSON, formatClock } = window.SEM;
  const form = document.querySelector("[data-ask-form]");
  const question = form.querySelector("#question");
  const tone = form.querySelector("#tone");
  const send = form.querySelector("[data-send]");
  const sendLabel = form.querySelector("[data-send-label]");
  const count = form.querySelector("[data-count]");
  const error = form.querySelector("[data-ask-error]");
  const messages = document.querySelector("[data-messages]");
  const maxLength = question.maxLength;

  function updateCount() {
    count.textContent = `${question.value.length} / ${maxLength} characters`;
  }

  function showError(text) {
    error.textContent = text;
    error.hidden = false;
    question.setAttribute("aria-invalid", "true");
  }

  function clearError() {
    error.hidden = true;
    error.textContent = "";
    question.setAttribute("aria-invalid", "false");
  }

  function element(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
      node.className = className;
    }
    if (text !== undefined) {
      node.textContent = text;
    }
    return node;
  }

  // Messages are built with textContent only, so answers are always shown as plain text.
  function addMessage(author, text, answeredAt, source) {
    const empty = messages.querySelector("[data-empty]");
    if (empty) {
      empty.remove();
    }
    const isAi = author === "ai";
    const item = element("li", `chat chat--${isAi ? "ai" : "user"}`);
    const avatar = element("span", "chat__avatar", isAi ? "AI" : "");
    avatar.setAttribute("aria-hidden", "true");
    if (!isAi) {
      avatar.appendChild(document.querySelector("#user-icon").content.cloneNode(true));
    }

    const meta = element("p", "chat__meta");
    meta.appendChild(element("span", "", isAi ? "AI Coach" : "You"));
    const time = element("time", "", `Today, ${formatClock(answeredAt, false)}`);
    time.dateTime = answeredAt;
    meta.appendChild(time);

    const bubble = element("div", "chat__bubble");
    bubble.appendChild(element("p", "", text));
    if (source) {
      bubble.appendChild(element("p", "chat__source", source));
    }
    item.append(avatar, meta, bubble);
    messages.appendChild(item);
  }

  function describeSource(data) {
    if (data.response_time_s === null) {
      return `Answered from ${data.source}`;
    }
    return `Answered by ${data.source} in ${data.response_time_s} s`;
  }

  function setBusy(busy) {
    send.disabled = busy;
    sendLabel.textContent = busy ? "Sending…" : "Send";
    form.setAttribute("aria-busy", String(busy));
  }

  form.addEventListener("submit", async (event) => {
    event.preventDefault();
    const text = question.value.trim();
    if (!text) {
      showError("Enter a question before sending.");
      question.focus();
      return;
    }
    if (text.length > maxLength) {
      showError(`Shorten the question to ${maxLength} characters or fewer.`);
      return;
    }

    clearError();
    setBusy(true);
    try {
      const data = await fetchJSON("/api/coach/ask", {
        method: "POST",
        body: { question: text, tone: tone.value, building: form.dataset.building },
      });
      addMessage("user", data.question, data.answered_at);
      addMessage("ai", data.answer, data.answered_at, describeSource(data));
      document.querySelector("[data-last-response]").textContent =
        data.response_time_s === null ? "No live response" : `${data.response_time_s} s`;
      document.querySelector("[data-source]").textContent = data.source;
      question.value = "";
      updateCount();
    } catch (problem) {
      showError(`No answer received. ${problem.message} Your question is still in the box; try sending it again.`);
    } finally {
      setBusy(false);
    }
  });

  question.addEventListener("input", () => {
    updateCount();
    if (!error.hidden && question.value.trim()) {
      clearError();
    }
  });

  document.querySelectorAll("[data-tip]").forEach((button) => {
    button.addEventListener("click", () => {
      question.value = `How do I do this: ${button.dataset.tip}?`;
      updateCount();
      clearError();
      question.focus();
    });
  });

  async function refreshStatus() {
    const problem = document.querySelector("[data-status-error]");
    try {
      const data = await fetchJSON("/api/coach/status");
      const pill = document.querySelector("[data-status-pill]");
      pill.className = `pill pill--${data.status}`;
      pill.textContent = data.label;
      document.querySelector("[data-status-label]").textContent = data.label;
      problem.hidden = true;
    } catch (failure) {
      const retry = element("button", "button button--secondary", "Retry");
      retry.type = "button";
      retry.addEventListener("click", refreshStatus);
      problem.replaceChildren(`Could not check the status. ${failure.message} `, retry);
      problem.hidden = false;
    }
  }

  refreshStatus();
})();
