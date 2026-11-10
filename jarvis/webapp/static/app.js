(function () {
  "use strict";

  const pairingScreen = document.getElementById("pairing-screen");
  const app = document.getElementById("app");
  const tokenInput = document.getElementById("token-input");
  const pairBtn = document.getElementById("pair-btn");
  const pairingError = document.getElementById("pairing-error");
  const statusPill = document.getElementById("status-pill");
  const transcript = document.getElementById("transcript");
  const commandInput = document.getElementById("command-input");
  const sendBtn = document.getElementById("send-btn");
  const stopBtn = document.getElementById("stop-btn");
  const quitBtn = document.getElementById("quit-btn");
  const skillsList = document.getElementById("skills-list");
  const tabChat = document.getElementById("tab-chat");
  const tabSkills = document.getElementById("tab-skills");
  const viewChat = document.getElementById("view-chat");
  const viewSkills = document.getElementById("view-skills");

  let token = localStorage.getItem("jarvis_token");
  let lastLine = "";
  let ws = null;
  let wsRetryMs = 1000;

  // Pull ?token= from a QR-scan URL, persist it, then clean the address bar.
  const urlParams = new URLSearchParams(location.search);
  if (urlParams.has("token")) {
    token = urlParams.get("token");
    localStorage.setItem("jarvis_token", token);
    urlParams.delete("token");
    const clean = location.pathname + (urlParams.toString() ? "?" + urlParams : "");
    history.replaceState({}, "", clean);
  }

  function api(path, options) {
    options = options || {};
    options.headers = Object.assign({}, options.headers, {
      Authorization: "Bearer " + token,
      "Content-Type": "application/json",
    });
    return fetch(path, options).then(async (res) => {
      if (res.status === 401) {
        localStorage.removeItem("jarvis_token");
        token = null;
        showPairing("Session expired - please re-enter the pairing token.");
        throw new Error("unauthorized");
      }
      const data = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(data.detail || "Request failed");
      return data;
    });
  }

  function showPairing(message) {
    pairingScreen.classList.remove("hidden");
    app.classList.add("hidden");
    pairingError.textContent = message || "";
  }

  function showApp() {
    pairingScreen.classList.add("hidden");
    app.classList.remove("hidden");
  }

  function appendLine(text, cls) {
    if (text === lastLine) return;
    lastLine = text;
    const div = document.createElement("div");
    div.className = "line " + cls;
    div.textContent = text;
    transcript.appendChild(div);
    transcript.scrollTop = transcript.scrollHeight;
  }

  function classifyLine(text) {
    if (text.startsWith("You:")) return { cls: "you", text: text.slice(4).trim() };
    if (text.startsWith("Jarvis:")) return { cls: "jarvis", text: text.slice(7).trim() };
    return { cls: "system", text };
  }

  function handleEvent(event) {
    if (event.type === "status") {
      statusPill.textContent = event.status;
      statusPill.className = event.status;
    } else if (event.type === "log") {
      const { cls, text } = classifyLine(event.line);
      appendLine(text, cls);
    }
  }

  function connectWebSocket() {
    const proto = location.protocol === "https:" ? "wss:" : "ws:";
    ws = new WebSocket(`${proto}//${location.host}/ws?token=${encodeURIComponent(token)}`);
    ws.onmessage = (msg) => handleEvent(JSON.parse(msg.data));
    ws.onopen = () => { wsRetryMs = 1000; };
    ws.onclose = () => {
      setTimeout(connectWebSocket, wsRetryMs);
      wsRetryMs = Math.min(wsRetryMs * 2, 15000);
    };
    ws.onerror = () => ws.close();
  }

  function loadHistory() {
    api("/api/status")
      .then((data) => {
        statusPill.textContent = data.status;
        statusPill.className = data.status;
        data.history.forEach((event) => handleEvent(event));
      })
      .catch(() => {});
  }

  function inputFor(name, schema) {
    const input = document.createElement("input");
    input.dataset.name = name;
    input.placeholder = schema.description || name;
    input.type = schema.type === "integer" || schema.type === "number" ? "number" : "text";
    return input;
  }

  function loadSkills() {
    api("/api/skills")
      .then((data) => {
        skillsList.innerHTML = "";
        data.skills.forEach((skill) => {
          const card = document.createElement("div");
          card.className = "skill-card";

          const title = document.createElement("h3");
          title.textContent = skill.name;
          card.appendChild(title);

          if (skill.description) {
            const desc = document.createElement("p");
            desc.textContent = skill.description;
            card.appendChild(desc);
          }

          const props = (skill.parameters && skill.parameters.properties) || {};
          const inputs = Object.entries(props).map(([name, schema]) => {
            const el = inputFor(name, schema);
            card.appendChild(el);
            return el;
          });

          const runBtn = document.createElement("button");
          runBtn.textContent = "Run";
          runBtn.onclick = () => {
            const args = {};
            inputs.forEach((el) => {
              if (el.value !== "") {
                args[el.dataset.name] = el.type === "number" ? Number(el.value) : el.value;
              }
            });
            runBtn.disabled = true;
            api(`/api/skills/${encodeURIComponent(skill.name)}/invoke`, {
              method: "POST",
              body: JSON.stringify({ args }),
            })
              .catch((err) => appendLine("Error: " + err.message, "system"))
              .finally(() => { runBtn.disabled = false; });
          };
          card.appendChild(runBtn);

          skillsList.appendChild(card);
        });
      })
      .catch(() => {});
  }

  function sendCommand() {
    const text = commandInput.value.trim();
    if (!text) return;
    commandInput.value = "";
    api("/api/command", { method: "POST", body: JSON.stringify({ text }) }).catch((err) =>
      appendLine("Error: " + err.message, "system")
    );
  }

  function switchTab(tab) {
    const isChat = tab === "chat";
    tabChat.classList.toggle("active", isChat);
    tabSkills.classList.toggle("active", !isChat);
    viewChat.classList.toggle("active", isChat);
    viewSkills.classList.toggle("active", !isChat);
  }

  sendBtn.addEventListener("click", sendCommand);
  commandInput.addEventListener("keydown", (e) => { if (e.key === "Enter") sendCommand(); });
  stopBtn.addEventListener("click", () => api("/api/control/stop", { method: "POST" }));
  quitBtn.addEventListener("click", () => {
    if (confirm("Quit Jarvis on your laptop?")) api("/api/control/quit", { method: "POST" });
  });
  tabChat.addEventListener("click", () => switchTab("chat"));
  tabSkills.addEventListener("click", () => switchTab("skills"));

  pairBtn.addEventListener("click", () => {
    const value = tokenInput.value.trim();
    if (!value) return;
    token = value;
    localStorage.setItem("jarvis_token", token);
    start();
  });

  function start() {
    showApp();
    connectWebSocket();
    loadHistory();
    loadSkills();
  }

  if (token) {
    start();
  } else {
    showPairing();
  }

  if ("serviceWorker" in navigator) {
    navigator.serviceWorker.register("service-worker.js").catch(() => {});
  }
})();
