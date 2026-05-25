/**
 * content.js — PhishGuard content script
 *
 * Features:
 *  1. Hover tooltip on <a> tags: debounced 400ms, routes scan through background.js
 *  2. Result cache per URL (clears on page navigation)
 *  3. Warning overlay injection when background.js detects a high-risk navigation
 */

(function () {
  "use strict";

  const HOVER_DELAY_MS = 400;
  const CACHE_MAX_SIZE  = 200;  // prevent unbounded growth in long sessions

  // Cache scan results for this page session to avoid redundant API calls
  const cache = new Map();

  let tooltipEl    = null;
  let hoverTimer   = null;
  let currentLink  = null;
  let lastMouseEvt = null;  // always holds the latest mousemove event

  // Inject keyframe stylesheet once so showLoadingTooltip doesn't duplicate <style> tags
  (function injectStyles() {
    const s = document.createElement("style");
    s.textContent = "@keyframes phishguard-spin { to { transform: rotate(360deg); } }";
    document.documentElement.appendChild(s);
  })();

  document.addEventListener("mousemove", (e) => { lastMouseEvt = e; }, true);

  // ---------------------------------------------------------------------------
  // Tooltip element (created once, reused)
  // ---------------------------------------------------------------------------
  function getTooltip() {
    if (tooltipEl) return tooltipEl;

    tooltipEl = document.createElement("div");
    tooltipEl.id = "phishguard-tooltip";
    Object.assign(tooltipEl.style, {
      position: "fixed",
      zIndex: "2147483647",
      background: "#1a1a2e",
      border: "2px solid #6c21ff",
      borderRadius: "10px",
      padding: "10px 14px",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
      fontSize: "13px",
      color: "#e0e0e0",
      boxShadow: "0 4px 24px rgba(0,0,0,0.5)",
      minWidth: "210px",
      maxWidth: "320px",
      pointerEvents: "none",
      display: "none",
      lineHeight: "1.4",
    });
    document.documentElement.appendChild(tooltipEl);
    return tooltipEl;
  }

  function positionTooltip(e) {
    const tip = getTooltip();
    const x = Math.min(e.clientX + 16, window.innerWidth - 340);
    const y = Math.min(e.clientY + 16, window.innerHeight - 130);
    tip.style.left = x + "px";
    tip.style.top = y + "px";
  }

  function showLoadingTooltip(e) {
    const tip = getTooltip();
    tip.style.borderColor = "#6c21ff";
    tip.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;color:#888;font-size:12px;">
        <span style="
          display:inline-block;
          width:12px;height:12px;
          border:2px solid #444;
          border-top-color:#6c21ff;
          border-radius:50%;
          animation:phishguard-spin 0.7s linear infinite;
        "></span>
        Scanning with PhishGuard…
      </div>
    `;
    positionTooltip(e);
    tip.style.display = "block";
  }

  function showResultTooltip(e, data) {
    const tip = getTooltip();
    const isPhishing = data.ensemble.verdict === "bad";
    const { phishing_votes, total_models } = data.ensemble;
    const pct = Math.round((phishing_votes / total_models) * 100);
    const color = isPhishing ? "#dc3545" : "#28a745";
    const icon = isPhishing ? "⚠️" : "✅";
    const label = isPhishing ? "PHISHING" : "SAFE";

    tip.style.borderColor = color;
    tip.innerHTML = `
      <div style="display:flex;align-items:center;gap:8px;margin-bottom:7px;">
        <span style="font-size:15px;">${icon}</span>
        <span style="color:${color};font-weight:700;font-size:14px;">PhishGuard: ${label}</span>
      </div>
      <div style="height:5px;background:#2a2a4a;border-radius:3px;overflow:hidden;margin-bottom:5px;">
        <div style="height:100%;width:${pct}%;background:${color};"></div>
      </div>
      <div style="color:#888;font-size:11px;">
        ${phishing_votes} of ${total_models} models flagged this URL
      </div>
    `;
    positionTooltip(e);
    tip.style.display = "block";
  }

  function hideTooltip() {
    if (tooltipEl) tooltipEl.style.display = "none";
  }

  // ---------------------------------------------------------------------------
  // Hover listeners
  // ---------------------------------------------------------------------------
  document.addEventListener("mouseover", (e) => {
    const link = e.target.closest("a[href]");
    if (!link) return;

    const href = link.href;
    if (!href || !href.startsWith("http")) return;

    currentLink = link;
    clearTimeout(hoverTimer);

    hoverTimer = setTimeout(() => {
      if (currentLink !== link) return;

      // Return cached result immediately
      if (cache.has(href)) {
        showResultTooltip(e, cache.get(href));
        return;
      }

      showLoadingTooltip(lastMouseEvt || e);

      chrome.runtime.sendMessage({ action: "scan", url: href }, (resp) => {
        if (currentLink !== link) return hideTooltip();
        if (!resp || !resp.success) return hideTooltip();

        // Enforce cache size limit — evict oldest entry when full
        if (cache.size >= CACHE_MAX_SIZE) {
          cache.delete(cache.keys().next().value);
        }
        cache.set(href, resp.data);
        showResultTooltip(lastMouseEvt || e, resp.data);
      });
    }, HOVER_DELAY_MS);
  }, true);

  document.addEventListener("mouseout", (e) => {
    if (!e.target.closest("a[href]")) return;
    clearTimeout(hoverTimer);
    currentLink = null;
    setTimeout(hideTooltip, 150);
  }, true);

  // ---------------------------------------------------------------------------
  // Warning overlay (injected by background.js for high-risk navigations)
  // ---------------------------------------------------------------------------
  chrome.runtime.onMessage.addListener((msg) => {
    if (msg.action === "showWarning") {
      injectWarningOverlay(msg.url, msg.votes, msg.total);
    }
  });

  function injectWarningOverlay(url, votes, total) {
    if (document.getElementById("phishguard-warning-overlay")) return;

    const pct = total > 0 ? Math.round((votes / total) * 100) : 0;

    const overlay = document.createElement("div");
    overlay.id = "phishguard-warning-overlay";
    Object.assign(overlay.style, {
      position: "fixed",
      inset: "0",
      zIndex: "2147483646",
      background: "rgba(0,0,0,0.95)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontFamily: "-apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif",
    });

    // Build overlay with DOM APIs to avoid XSS from URL content in innerHTML
    const card = document.createElement("div");
    Object.assign(card.style, {
      background: "#1a1a2e", border: "2px solid #dc3545", borderRadius: "18px",
      padding: "44px 40px", maxWidth: "520px", width: "90%", textAlign: "center",
      color: "#e0e0e0", boxShadow: "0 8px 48px rgba(220,53,69,0.25)",
      animation: "phishguard-fadein 0.3s ease",
    });

    const shield = document.createElement("div");
    shield.setAttribute("aria-hidden", "true");
    shield.style.cssText = "font-size:64px;margin-bottom:16px;";
    shield.textContent = "⚠️";

    const heading = document.createElement("h2");
    heading.style.cssText = "color:#dc3545;margin:0 0 12px;font-size:22px;font-weight:700;";
    heading.textContent = "Phishing Page Detected";

    const desc = document.createElement("p");
    desc.style.cssText = "color:#999;font-size:14px;line-height:1.6;margin-bottom:20px;";
    desc.innerHTML = `PhishGuard flagged this page as a likely phishing site.<br>
      <strong style="color:#dc3545;">${votes} of ${total} models</strong>
      (${pct}%) identified it as malicious.`;

    const urlBox = document.createElement("div");
    Object.assign(urlBox.style, {
      background: "#0d0d1a", borderLeft: "3px solid #dc3545", borderRadius: "0 8px 8px 0",
      padding: "12px 14px", marginBottom: "24px", textAlign: "left",
      wordBreak: "break-all", fontSize: "12px", color: "#777",
    });
    urlBox.textContent = url; // safe — textContent never executes HTML

    const actions = document.createElement("div");
    actions.style.cssText = "display:flex;gap:12px;justify-content:center;flex-wrap:wrap;";

    const backBtn = document.createElement("button");
    backBtn.id = "phishguard-back";
    backBtn.style.cssText = "background:#198754;color:white;border:none;padding:12px 26px;border-radius:10px;cursor:pointer;font-size:14px;font-weight:600;";
    backBtn.textContent = "← Go Back (Safe)";

    const proceedBtn = document.createElement("button");
    proceedBtn.id = "phishguard-proceed";
    proceedBtn.style.cssText = "background:transparent;color:#dc3545;border:1px solid #dc3545;padding:12px 26px;border-radius:10px;cursor:pointer;font-size:14px;";
    proceedBtn.textContent = "Proceed Anyway";

    actions.appendChild(backBtn);
    actions.appendChild(proceedBtn);

    const footer = document.createElement("p");
    footer.style.cssText = "margin-top:16px;font-size:11px;color:#444;";
    footer.textContent = "Powered by PhishGuard · Quantum-Classical ML";

    // Inject once-used keyframe for card entrance animation
    const fadeinStyle = document.createElement("style");
    fadeinStyle.textContent = "@keyframes phishguard-fadein { from { opacity:0; transform:translateY(-14px); } to { opacity:1; transform:translateY(0); } }";
    card.appendChild(fadeinStyle);

    card.appendChild(shield);
    card.appendChild(heading);
    card.appendChild(desc);
    card.appendChild(urlBox);
    card.appendChild(actions);
    card.appendChild(footer);
    overlay.appendChild(card);

    document.body.appendChild(overlay);
    document.body.style.overflow = "hidden";

    backBtn.onclick = () => window.history.back();
    proceedBtn.onclick = () => {
      overlay.remove();
      document.body.style.overflow = "";
    };
  }
})();
