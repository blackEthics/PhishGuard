/**
 * popup.js — PhishGuard toolbar popup
 *
 * Auto-scans the active tab's URL on open.
 * Shows SAFE / PHISHING verdict, vote bar, and per-model badges.
 * Rescan button lets the user re-run the scan manually.
 */

(function () {
  "use strict";

  // Short names shown in model badges
  const MODEL_NAMES = {
    knn:    "KNN",
    logreg: "LogReg",
    nb:     "NaiveBayes",
    svm:    "SVM",
    rf:     "RandForest",
    mlp:    "MLP",
  };

  const states = {
    scanning: document.getElementById("state-scanning"),
    result:   document.getElementById("state-result"),
    error:    document.getElementById("state-error"),
  };

  const verdictIcon  = document.getElementById("verdict-icon");
  const verdictLabel = document.getElementById("verdict-label");
  const voteFill     = document.getElementById("vote-fill");
  const voteText     = document.getElementById("vote-text");
  const modelRow     = document.getElementById("model-row");
  const currentUrlEl = document.getElementById("current-url");
  const webappLink   = document.getElementById("webapp-link");
  const rescanBtn    = document.getElementById("rescan-btn");
  const srLive       = document.getElementById("sr-live");

  let activeTabUrl = "";

  function showState(name) {
    Object.values(states).forEach(el => el.classList.add("hidden"));
    states[name].classList.remove("hidden");
  }

  function scan(url) {
    showState("scanning");

    chrome.runtime.sendMessage({ action: "scan", url }, (response) => {
      if (chrome.runtime.lastError || !response || !response.success) {
        showState("error");
        const msg = response?.error || "Cannot connect to localhost:5000.";
        document.getElementById("err-msg").textContent = msg;
        return;
      }
      renderResult(response.data);
    });
  }

  function renderResult(data) {
    showState("result");

    const isPhishing = data.ensemble.verdict === "bad";
    const { phishing_votes, total_models } = data.ensemble;
    const pct = Math.round((phishing_votes / total_models) * 100);

    verdictIcon.textContent  = isPhishing ? "⚠️" : "✅";
    verdictLabel.textContent = isPhishing ? "PHISHING" : "SAFE";
    verdictLabel.className   = `verdict-label ${isPhishing ? "phishing" : "safe"}`;

    if (srLive) {
      srLive.textContent = isPhishing
        ? `Phishing detected: ${phishing_votes} of ${total_models} models flagged this URL.`
        : `Safe URL: ${phishing_votes} of ${total_models} models flagged this URL.`;
    }

    voteFill.style.width = pct + "%";
    voteFill.className   = `vote-fill ${isPhishing ? "phish-fill" : "safe-fill"}`;
    voteText.textContent = `${phishing_votes} of ${total_models} models flagged this URL`;

    // Per-model badges
    modelRow.innerHTML = "";
    Object.entries(MODEL_NAMES).forEach(([key, label]) => {
      const m = data[key];
      if (!m) return;
      const span = document.createElement("span");
      span.className = `model-badge ${m.verdict}`;
      span.textContent = label;
      span.title = `${label}: ${m.verdict} (${Math.round(m.confidence * 100)}%)`;
      modelRow.appendChild(span);
    });
  }

  function init() {
    chrome.tabs.query({ active: true, currentWindow: true }, (tabs) => {
      if (!tabs.length) { showState("error"); return; }

      const tab = tabs[0];
      activeTabUrl = tab.url || "";
      const display = activeTabUrl.length > 48
        ? activeTabUrl.slice(0, 45) + "…"
        : activeTabUrl;
      currentUrlEl.textContent = display || "—";
      webappLink.href = `http://localhost:5000/?url=${encodeURIComponent(activeTabUrl)}`;

      if (!activeTabUrl.startsWith("http")) {
        showState("error");
        document.getElementById("err-msg").textContent = "Not a web page.";
        document.getElementById("err-hint").textContent =
          "Navigate to an http:// or https:// URL first.";
        return;
      }

      scan(activeTabUrl);
    });
  }

  rescanBtn.addEventListener("click", () => {
    if (activeTabUrl.startsWith("http")) scan(activeTabUrl);
  });

  init();
})();
