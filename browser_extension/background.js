/**
 * background.js — PhishGuard service worker
 *
 * Responsibilities:
 *  1. Handle scan requests from content.js and popup.js via chrome.runtime.onMessage
 *  2. Intercept navigations: if Flask returns high-risk before page commits, redirect
 *     to warning.html; if page already loaded, tell content.js to inject overlay.
 */

"use strict";

const API_BASE = "http://localhost:5000";

// Ratio of models that must flag a URL for navigation blocking (0.8 = 80%)
const HIGH_RISK_RATIO = 0.8;

// Track pending navigations: tabId → { url, loaded }
const pendingNav = new Map();

// ---------------------------------------------------------------------------
// Message handler: content.js and popup.js send {action:"scan", url:"..."}
// ---------------------------------------------------------------------------
chrome.runtime.onMessage.addListener((msg, _sender, sendResponse) => {
  if (msg.action !== "scan") return false;

  fetchScan(msg.url)
    .then(data => sendResponse({ success: true, data }))
    .catch(err => sendResponse({ success: false, error: err.message }));

  return true; // keep channel open for async response
});

// ---------------------------------------------------------------------------
// Navigation interception
// ---------------------------------------------------------------------------
chrome.webNavigation.onBeforeNavigate.addListener((details) => {
  if (details.frameId !== 0) return;
  const { tabId, url } = details;

  if (!url.startsWith("http")) return;
  if (url.startsWith("http://localhost:5000")) return;

  pendingNav.set(tabId, { url, loaded: false });

  fetchScan(url)
    .then(data => {
      const entry = pendingNav.get(tabId);
      if (!entry || entry.url !== url) return; // user navigated away

      const { phishing_votes, total_models, verdict } = data.ensemble;

      if (verdict === "bad" && phishing_votes / total_models >= HIGH_RISK_RATIO) {
        const warnUrl =
          chrome.runtime.getURL("warning.html") +
          `?url=${encodeURIComponent(url)}` +
          `&votes=${phishing_votes}` +
          `&total=${total_models}`;

        if (entry.loaded) {
          // Page finished loading before the scan did — inject overlay instead
          chrome.tabs.sendMessage(tabId, {
            action: "showWarning",
            url,
            votes: phishing_votes,
            total: total_models,
          }).catch(() => {});
        } else {
          // Redirect the tab to the warning page before the real page renders
          chrome.tabs.update(tabId, { url: warnUrl }).catch(() => {});
        }
      }

      pendingNav.delete(tabId);
    })
    .catch(() => {
      pendingNav.delete(tabId);
    });
});

chrome.webNavigation.onCompleted.addListener((details) => {
  if (details.frameId !== 0) return;
  const entry = pendingNav.get(details.tabId);
  if (entry) entry.loaded = true;
});

chrome.webNavigation.onErrorOccurred.addListener((details) => {
  pendingNav.delete(details.tabId);
});

// ---------------------------------------------------------------------------
// Helper: POST to /api/scan with classical models only (faster)
// ---------------------------------------------------------------------------
async function fetchScan(url) {
  const res = await fetch(`${API_BASE}/api/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, include_quantum: false }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
