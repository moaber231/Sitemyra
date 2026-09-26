const statusEl = document.getElementById("status");
const connectEl = document.getElementById("connect");
const actionsEl = document.getElementById("actions");

function say(message, kind = "") {
  statusEl.textContent = message;
  statusEl.className = kind;
}

function send(type, extra = {}) {
  return new Promise((resolve) => chrome.runtime.sendMessage({ type, ...extra }, resolve));
}

async function render() {
  const { connected } = await send("status");
  connectEl.classList.toggle("hidden", connected);
  actionsEl.classList.toggle("hidden", !connected);
  if (!connected) say("Not connected yet.");
}

document.querySelectorAll("button[data-recipe]").forEach((button) => {
  button.addEventListener("click", async () => {
    button.disabled = true;
    say("Working…");
    const result = await send("monitor", { recipe: button.dataset.recipe });
    button.disabled = false;
    if (result?.ok) {
      say(
        result.data?.created
          ? "Monitoring started. Sitemyra is reading the page now."
          : result.data?.detail || "Already monitored.",
        "ok",
      );
    } else {
      say(result?.error || result?.data?.detail || "Could not start monitoring.", "err");
    }
  });
});

document.getElementById("openApp").addEventListener("click", (event) => {
  event.preventDefault();
  send("open", { path: "/dashboard" });
  window.close();
});

document.getElementById("openSettings").addEventListener("click", (event) => {
  event.preventDefault();
  send("open", { path: "/dashboard/extension" });
  window.close();
});

void render();
