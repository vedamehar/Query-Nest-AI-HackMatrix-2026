/**
 * SiteSense AI — Embeddable Chat Widget
 *
 * Usage (2 lines on any website):
 *   <script src="http://localhost:3000/widget.js"
 *     data-bot-id="YOUR_BOT_ID"
 *     data-api="http://localhost:8000"
 *     data-position="right">
 *   </script>
 *
 * Zero dependencies · Shadow DOM isolated · Works everywhere
 */
(function () {
  "use strict";

  /* ================================================================
     CONFIGURATION (from script tag attributes)
     ================================================================ */
  const SCRIPT = document.currentScript || document.querySelector("script[data-bot-id]");
  const BOT_ID = SCRIPT?.getAttribute("data-bot-id") || "";
  const API_BASE = (SCRIPT?.getAttribute("data-api") || "http://localhost:8000").replace(/\/+$/, "");
  const POSITION = SCRIPT?.getAttribute("data-position") || "right";
  let WIDGET_TOKEN = null;

  /* ================================================================
     STATE
     ================================================================ */
  let isOpen = false;
  let initialized = false;
  let sessionId = "ss_" + Math.random().toString(36).substring(2, 11);
  let history = [];
  let config = {
    bot_name: "AI Assistant",
    welcome_message: "Hi! How can I help you?",
    primary_color: "#2563eb",
    suggested_questions: [],
  };

  /* ================================================================
     CSS (injected into Shadow DOM)
     ================================================================ */
  const WIDGET_CSS = `
    :host { all: initial; font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    *, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }

    /* ---------- CSS Variable ---------- */
    :host { --c: ${config.primary_color}; --radius: 14px; }

    /* ---------- Bubble ---------- */
    .ss-bubble {
      position: fixed; bottom: 20px; ${POSITION}: 20px;
      width: 58px; height: 58px; border-radius: 50%;
      background: var(--c); color: #fff; border: none; cursor: pointer;
      display: flex; align-items: center; justify-content: center;
      z-index: 2147483647;
      box-shadow: 0 4px 14px rgba(0,0,0,.25);
      transition: transform .25s cubic-bezier(.4,0,.2,1), box-shadow .25s;
    }
    .ss-bubble:hover { transform: scale(1.08); box-shadow: 0 6px 20px rgba(0,0,0,.3); }
    .ss-bubble svg { width: 26px; height: 26px; transition: transform .3s ease; }
    .ss-bubble.open svg { transform: rotate(90deg); }
    .ss-bubble .icon-chat, .ss-bubble .icon-close { position: absolute; transition: opacity .25s, transform .3s; }
    .ss-bubble .icon-close { opacity: 0; transform: rotate(-90deg); }
    .ss-bubble.open .icon-chat { opacity: 0; transform: rotate(90deg); }
    .ss-bubble.open .icon-close { opacity: 1; transform: rotate(0deg); }

    .ss-notif {
      position: absolute; top: -2px; right: -2px;
      width: 14px; height: 14px; border-radius: 50%;
      background: #ef4444; border: 2px solid #fff;
      transition: transform .2s;
    }
    .ss-notif.hide { transform: scale(0); }

    /* ---------- Window ---------- */
    .ss-window {
      position: fixed; bottom: 90px; ${POSITION}: 20px;
      width: 380px; height: 580px;
      border-radius: var(--radius);
      background: #ffffff; 
      color: #1e293b;
      display: flex; flex-direction: column;
      box-shadow: 0 10px 40px rgba(0,0,0,0.15);
      z-index: 2147483646;
      opacity: 0; transform: translateY(16px);
      pointer-events: none;
      transition: opacity .4s cubic-bezier(0.23, 1, 0.32, 1), transform .4s cubic-bezier(0.23, 1, 0.32, 1);
      overflow: hidden;
      border: 1px solid rgba(0,0,0,0.05);
    }
    .ss-window.open { opacity: 1; transform: translateY(0); pointer-events: auto; }

    /* ---------- Header ---------- */
    .ss-header {
      display: flex; align-items: center; gap: 12px;
      padding: 18px 20px;
      background: linear-gradient(135deg, var(--c), #1e293b); 
      color: #fff;
      border-radius: var(--radius) var(--radius) 0 0;
      flex-shrink: 0;
    }
    .ss-avatar {
      width: 40px; height: 40px; border-radius: 12px;
      background: rgba(255,255,255,0.15);
      display: flex; align-items: center; justify-content: center;
      flex-shrink: 0; font-size: 20px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.15);
    }
    .ss-header-info { flex: 1; min-width: 0; }
    .ss-header-name { font-weight: 800; font-size: 16px; letter-spacing: -0.02em; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
    .ss-header-status { font-size: 11px; opacity: .85; display: flex; align-items: center; gap: 4px; margin-top: 2px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em; }
    .ss-header-status .dot { width: 8px; height: 8px; border-radius: 50%; background: #22c55e; display: inline-block; box-shadow: 0 0 10px rgba(34, 197, 94, 0.5); }
    .ss-close-btn {
      background: rgba(255,255,255,0.1); border: none; color: #fff; cursor: pointer;
      width: 32px; height: 32px; border-radius: 10px;
      display: flex; align-items: center; justify-content: center;
      transition: all .2s;
    }
    .ss-close-btn:hover { background: rgba(255,255,255,0.2); transform: scale(1.05); }
    .ss-close-btn svg { width: 18px; height: 18px; }

    /* ---------- Messages area ---------- */
    .ss-messages {
      flex: 1; overflow-y: auto; padding: 20px 16px;
      display: flex; flex-direction: column; gap: 12px;
      scroll-behavior: smooth;
      background: #ffffff;
    }
    .ss-messages::-webkit-scrollbar { width: 5px; }
    .ss-messages::-webkit-scrollbar-track { background: transparent; }
    .ss-messages::-webkit-scrollbar-thumb { background: #e2e8f0; border-radius: 10px; }

    /* ---------- Message rows ---------- */
    .ss-msg-row { display: flex; gap: 10px; max-width: 88%; animation: ssSlideUp .4s cubic-bezier(0.23, 1, 0.32, 1); }
    .ss-msg-row.bot { align-self: flex-start; }
    .ss-msg-row.user { align-self: flex-end; flex-direction: row-reverse; }
    .ss-msg-avatar {
      width: 30px; height: 30px; border-radius: 10px; flex-shrink: 0;
      background: linear-gradient(135deg, var(--c), #6366f1); color: #fff;
      display: flex; align-items: center; justify-content: center;
      font-size: 14px; font-weight: 700; margin-top: 2px;
      box-shadow: 0 4px 10px rgba(0,0,0,0.1);
    }
    .ss-msg-row.user .ss-msg-avatar { display: none; }

    .ss-msg-bubble {
      padding: 12px 16px; border-radius: 18px; font-size: 14px; line-height: 1.6;
      word-break: break-word; position: relative;
    }
    .ss-msg-row.bot .ss-msg-bubble { 
      background: #f1f5f9; 
      color: #1e293b; 
      border-bottom-left-radius: 4px; 
    }
    .ss-msg-row.user .ss-msg-bubble { 
      background: var(--c); 
      color: #fff; 
      border-bottom-right-radius: 4px; 
      box-shadow: 0 4px 12px -2px rgba(139, 92, 246, 0.2);
    }

    .ss-msg-bubble ul { margin: 4px 0 4px 16px; padding: 0; }
    .ss-msg-bubble li { margin: 2px 0; }
    .ss-msg-bubble strong { font-weight: 600; }
    .ss-msg-bubble code { background: rgba(0,0,0,.06); padding: 1px 5px; border-radius: 4px; font-size: 12.5px; font-family: monospace; }
    .ss-msg-row.user .ss-msg-bubble code { background: rgba(255,255,255,.18); }

    /* Confidence badge */
    .ss-badge { display: inline-block; font-size: 10px; font-weight: 600; padding: 1px 7px; border-radius: 8px; margin-top: 5px; }
    .ss-badge.high { background: #dcfce7; color: #166534; }
    .ss-badge.medium { background: #fef9c3; color: #854d0e; }
    .ss-badge.low { background: #fee2e2; color: #991b1b; }

    /* ---------- Chips ---------- */
    .ss-chips { display: flex; flex-wrap: wrap; gap: 6px; margin-top: 8px; }
    .ss-chip {
      font-size: 12.5px; padding: 6px 12px;
      border-radius: 20px; border: 1px solid #e2e8f0;
      background: #fff; color: #334155; cursor: pointer;
      transition: background .15s, border-color .15s;
      line-height: 1.3;
    }
    .ss-chip:hover { background: #f1f5f9; border-color: var(--c); color: var(--c); }
    .ss-chip.source { border-color: var(--c); color: var(--c); cursor: default; font-size: 11.5px; padding: 4px 10px; }
    .ss-chip.source:hover { background: #fff; }

    /* ---------- Handoff banner ---------- */
    .ss-handoff {
      margin-top: 8px; padding: 10px 12px; border-radius: 10px;
      background: #fffbeb; border: 1px solid #fde68a;
      font-size: 12.5px; color: #92400e;
      display: flex; align-items: center; gap: 8px;
    }
    .ss-handoff button {
      background: var(--c); color: #fff; font-size: 11.5px; font-weight: 600;
      border: none; border-radius: 8px; padding: 5px 12px; cursor: pointer;
      white-space: nowrap; transition: opacity .15s;
    }
    .ss-handoff button:hover { opacity: .88; }

    /* ---------- Skeleton / Thinking indicator ---------- */
    .ss-skeleton { 
      display: flex; flex-direction: column; gap: 8px; padding: 12px 16px; 
      width: 200px; background: #f8fafc; border-radius: 18px;
      border: 1px solid #e2e8f0;
    }
    .ss-skeleton-bar {
      height: 10px; background: #e2e8f0; border-radius: 5px;
      position: relative; overflow: hidden;
    }
    .ss-skeleton-bar::after {
      content: ""; position: absolute; top: 0; left: 0; right: 0; bottom: 0;
      background: linear-gradient(90deg, transparent, rgba(255,255,255,0.6), transparent);
      animation: ssPulse 1.8s infinite cubic-bezier(0.4, 0, 0.6, 1);
    }
    .ss-skeleton-bar:nth-child(2) { width: 85%; }
    .ss-skeleton-bar:nth-child(3) { width: 60%; }

    @keyframes ssPulse {
      0% { transform: translateX(-100%); }
      100% { transform: translateX(100%); }
    }
    @keyframes ssSlideUp { from { opacity: 0; transform: translateY(12px); } to { opacity: 1; transform: translateY(0); } }

    /* ---------- Privacy notice ---------- */
    .ss-privacy {
      padding: 8px 14px; background: #f8fafc; font-size: 11px; color: #64748b;
      text-align: center; border-top: 1px solid #f1f5f9;
      display: flex; align-items: center; justify-content: center; gap: 6px;
    }
    .ss-privacy button {
      background: none; border: none; color: #94a3b8; cursor: pointer; font-size: 14px;
      line-height: 1; padding: 0 2px;
    }

    /* ---------- Input area ---------- */
    .ss-input-area {
      display: flex; align-items: flex-end; gap: 8px;
      padding: 16px; border-top: 1px solid #f1f5f9;
      background: #ffffff; flex-shrink: 0;
    }
    .ss-input {
      flex: 1; resize: none; border: 1px solid #e2e8f0; border-radius: 14px;
      padding: 12px 16px; font-size: 14px; font-family: inherit;
      line-height: 1.5; outline: none; min-height: 44px; max-height: 100px;
      color: #1e293b; background: #f8fafc;
      transition: all .2s;
    }
    .ss-input::placeholder { color: #94a3b8; }
    .ss-input:focus { border-color: var(--c); background: #ffffff; box-shadow: 0 0 0 3px rgba(139, 92, 246, 0.05); }
    .ss-send-btn, .ss-mic-btn {
      width: 40px; height: 40px; border-radius: 12px; border: none;
      display: flex; align-items: center; justify-content: center;
      cursor: pointer; flex-shrink: 0; transition: all .2s;
    }
    .ss-send-btn { background: var(--c); color: #fff; opacity: .4; }
    .ss-send-btn.active { opacity: 1; box-shadow: 0 4px 12px rgba(139, 92, 246, 0.2); }
    .ss-send-btn:hover.active { transform: scale(1.05); }
    .ss-send-btn svg, .ss-mic-btn svg { width: 20px; height: 20px; }
    .ss-mic-btn { background: #f8fafc; color: #94a3b8; }
    .ss-mic-btn:hover { background: #f1f5f9; color: #1e293b; }

    /* ---------- Footer ---------- */
    .ss-footer {
      text-align: center; padding: 6px; font-size: 10.5px; color: #94a3b8;
      background: #fff; flex-shrink: 0;
      border-radius: 0 0 var(--radius) var(--radius);
    }
    .ss-footer a { color: var(--c); text-decoration: none; font-weight: 600; }

    /* ---------- Animations ---------- */
    @keyframes ssSlideIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }
    @keyframes ssBounce {
      0%, 60%, 100% { transform: translateY(0); }
      30% { transform: translateY(-6px); }
    }

    /* ---------- Mobile fullscreen ---------- */
    @media (max-width: 768px) {
      .ss-window {
        width: 100%; height: 100%;
        bottom: 0; left: 0; right: 0; top: 0;
        border-radius: 0;
        z-index: 2147483647;
      }
      .ss-window.open { border-radius: 0; }
      .ss-header { border-radius: 0; }
      .ss-input-area, .ss-footer { border-radius: 0; }
      .ss-bubble { bottom: 16px; right: 16px; }
    }
  `;

  /* ================================================================
     SVG ICONS
     ================================================================ */
  const ICON_CHAT = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>`;
  const ICON_CLOSE = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M6 18L18 6M6 6l12 12"/></svg>`;
  const ICON_SEND = `<svg xmlns="http://www.w3.org/2000/svg" fill="currentColor" viewBox="0 0 24 24"><path d="M2.01 21L23 12 2.01 3 2 10l15 2-15 2z"/></svg>`;
  const ICON_MIC = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="2"><path stroke-linecap="round" stroke-linejoin="round" d="M12 1a3 3 0 00-3 3v8a3 3 0 006 0V4a3 3 0 00-3-3z"/><path stroke-linecap="round" stroke-linejoin="round" d="M19 10v2a7 7 0 01-14 0v-2"/><line x1="12" y1="19" x2="12" y2="23"/><line x1="8" y1="23" x2="16" y2="23"/></svg>`;
  const ICON_BOT = `<svg xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24" stroke="currentColor" stroke-width="1.5"><path stroke-linecap="round" stroke-linejoin="round" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z"/></svg>`;

  /* ================================================================
     DOM REFERENCES
     ================================================================ */
  let shadowRoot, bubbleEl, windowEl, messagesEl, inputEl, sendBtn, notifEl;

  /* ================================================================
     BUILD WIDGET
     ================================================================ */
  function build() {
    const host = document.createElement("div");
    host.id = "sitesense-host";
    host.style.cssText = "position:relative; z-index:2147483647; border:none; padding:0; margin:0;";
    document.body.appendChild(host);
    shadowRoot = host.attachShadow({ mode: "open" });

    // --- Style ---
    const style = document.createElement("style");
    style.textContent = WIDGET_CSS;
    shadowRoot.appendChild(style);

    // --- Bubble ---
    bubbleEl = document.createElement("button");
    bubbleEl.className = "ss-bubble";
    bubbleEl.setAttribute("aria-label", "Chat");
    bubbleEl.innerHTML = `
      <span class="icon-chat">${ICON_CHAT}</span>
      <span class="icon-close">${ICON_CLOSE}</span>
      <span class="ss-notif hide"></span>`;
    bubbleEl.addEventListener("click", toggle);
    shadowRoot.appendChild(bubbleEl);
    notifEl = bubbleEl.querySelector(".ss-notif");

    // --- Window ---
    windowEl = document.createElement("div");
    windowEl.className = "ss-window";
    windowEl.innerHTML = `
      <div class="ss-header">
        <div class="ss-avatar">${ICON_BOT}</div>
        <div class="ss-header-info">
          <div class="ss-header-name">${esc(config.bot_name)}</div>
          <div class="ss-header-status"><span class="dot"></span> Online</div>
        </div>
        <button class="ss-close-btn" aria-label="Close">${ICON_CLOSE}</button>
      </div>
      <div class="ss-messages"></div>
      <div class="ss-privacy">
        🔒 Messages are used to improve responses
        <button class="ss-privacy-close" aria-label="Dismiss">×</button>
      </div>
      <div class="ss-input-area">
        <textarea class="ss-input" placeholder="Type a message…" rows="1"></textarea>
        <button class="ss-mic-btn" aria-label="Voice input">${ICON_MIC}</button>
        <button class="ss-send-btn" aria-label="Send">${ICON_SEND}</button>
      </div>
      <div class="ss-footer">Powered by <a href="#">SiteSense</a></div>`;
    shadowRoot.appendChild(windowEl);

    // --- Refs ---
    messagesEl = windowEl.querySelector(".ss-messages");
    inputEl = windowEl.querySelector(".ss-input");
    sendBtn = windowEl.querySelector(".ss-send-btn");

    // --- Events ---
    windowEl.querySelector(".ss-close-btn").addEventListener("click", toggle);
    windowEl.querySelector(".ss-privacy-close").addEventListener("click", function () {
      windowEl.querySelector(".ss-privacy").style.display = "none";
    });

    inputEl.addEventListener("input", onInput);
    inputEl.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); sendMessage(); }
    });
    sendBtn.addEventListener("click", function () { sendMessage(); });

    // Show notification dot after 2s
    setTimeout(function () { if (!isOpen) notifEl.classList.remove("hide"); }, 2000);
  }

  /* ================================================================
     TOGGLE
     ================================================================ */
  function toggle() {
    isOpen = !isOpen;
    bubbleEl.classList.toggle("open", isOpen);
    windowEl.classList.toggle("open", isOpen);
    notifEl.classList.add("hide");

    if (isOpen) {
      if (!initialized) { renderWelcome(); initialized = true; }
      setTimeout(function () { inputEl.focus(); }, 350);
    }
  }

  /* ================================================================
     WELCOME
     ================================================================ */
  function renderWelcome() {
    appendBotMessage(config.welcome_message);

    if (config.suggested_questions && config.suggested_questions.length) {
      var chips = document.createElement("div");
      chips.className = "ss-chips";
      config.suggested_questions.forEach(function (q) {
        var chip = document.createElement("button");
        chip.className = "ss-chip";
        chip.textContent = q;
        chip.addEventListener("click", function () {
          chips.remove();
          sendMessage(q);
        });
        chips.appendChild(chip);
      });
      messagesEl.appendChild(chips);
      scrollToBottom();
    }
  }

  /* ================================================================
     SEND MESSAGE
     ================================================================ */
  async function sendMessage(override) {
    var text = override || inputEl.value.trim();
    if (!text) return;

    if (!override) { inputEl.value = ""; inputEl.style.height = "38px"; updateSendBtn(); }

    // Remove any existing suggestion chips
    shadowRoot.querySelectorAll(".ss-chips.suggestions").forEach(function (el) { el.remove(); });

    appendUserMessage(text);
    history.push({ role: "user", content: text });
    if (history.length > 20) history = history.slice(-20);

    var typingEl = appendTyping();

    try {
      const headers = {
        "Content-Type": "application/json",
        "X-Bot-Id": BOT_ID,
        ...(WIDGET_TOKEN ? { "Authorization": `Bearer ${WIDGET_TOKEN}` } : {})
      };

      var resp = await fetch(API_BASE + "/api/chat", {
        method: "POST",
        headers: headers,
        body: JSON.stringify({
          message: text,
          session_id: sessionId,
          history: history.slice(-10),
        }),
      });

      if (resp.status === 401) {
        const refreshed = await initWidget();
        if (refreshed) {
          return await sendMessage(override || text);
        }
      }

      typingEl.remove();

      if (!resp.ok) {
        appendBotMessage("Sorry, something went wrong. Please try again.");
        return;
      }

      var data = await resp.json();

      if (data.refresh_token) {
        initWidget(); // Refresh in background
      }

      renderBotResponse(data);
      history.push({ role: "assistant", content: data.answer || "" });
      if (history.length > 20) history = history.slice(-20);
    } catch (err) {
      if (typingEl) typingEl.remove();
      appendBotMessage("Unable to connect. Please check your internet and try again.");
    }
  }

  /* ================================================================
     RENDER BOT RESPONSE
     ================================================================ */
  function renderBotResponse(data) {
    var msgEl = appendBotMessage(data.answer || config.fallback_message || "I'm not sure how to help with that.");
    var bubble = msgEl.querySelector(".ss-msg-bubble");

    // Confidence badge
    if (data.was_answered && data.confidence) {
      var badge = document.createElement("div");
      badge.className = "ss-badge " + data.confidence;
      badge.textContent = data.confidence === "high" ? "✓ High confidence"
        : data.confidence === "medium" ? "~ Medium confidence" : "Low confidence";
      bubble.appendChild(badge);
    }

    // Source chips
    if (data.was_answered && data.sources && data.sources.length) {
      var srcWrap = document.createElement("div");
      srcWrap.style.cssText = "margin-top:8px;font-size:12px;color:#64748b;";
      srcWrap.textContent = "📄 Sources: ";
      var srcChips = document.createElement("span");
      srcChips.className = "ss-chips";
      srcChips.style.display = "inline-flex";
      data.sources.forEach(function (s) {
        var chip = document.createElement("span");
        chip.className = "ss-chip source";
        chip.textContent = s;
        srcChips.appendChild(chip);
      });
      srcWrap.appendChild(srcChips);
      bubble.appendChild(srcWrap);
    }

    // Follow-up question chips
    if (data.was_answered && data.follow_up_questions && data.follow_up_questions.length) {
      var fuChips = document.createElement("div");
      fuChips.className = "ss-chips suggestions";
      fuChips.style.marginTop = "10px";
      data.follow_up_questions.forEach(function (q) {
        var chip = document.createElement("button");
        chip.className = "ss-chip";
        chip.textContent = q;
        chip.addEventListener("click", function () {
          shadowRoot.querySelectorAll(".ss-chips.suggestions").forEach(function (el) { el.remove(); });
          sendMessage(q);
        });
        fuChips.appendChild(chip);
      });
      // Append outside the bubble, after the message row
      msgEl.after(fuChips);
    }

    // Handoff banner (fallback / not answered)
    if (!data.was_answered || data.response_type === "fallback") {
      var handoff = document.createElement("div");
      handoff.className = "ss-handoff";
      handoff.innerHTML = "Need more help? ";
      var hBtn = document.createElement("button");
      hBtn.textContent = "Talk to a human";
      hBtn.addEventListener("click", function () {
        handoff.remove();
        appendBotMessage("Please email us at <strong>support@sitesense.ai</strong> and we'll get back to you shortly!");
      });
      handoff.appendChild(hBtn);
      bubble.appendChild(handoff);
    }

    scrollToBottom();
  }

  /* ================================================================
     MESSAGE HELPERS
     ================================================================ */
  function appendBotMessage(text) {
    var row = document.createElement("div");
    row.className = "ss-msg-row bot";
    row.innerHTML = `
      <div class="ss-msg-avatar">${ICON_BOT}</div>
      <div class="ss-msg-bubble">${formatText(text)}</div>`;
    messagesEl.appendChild(row);
    scrollToBottom();
    return row;
  }

  function appendUserMessage(text) {
    var row = document.createElement("div");
    row.className = "ss-msg-row user";
    row.innerHTML = `<div class="ss-msg-bubble">${esc(text)}</div>`;
    messagesEl.appendChild(row);
    scrollToBottom();
    return row;
  }

  function appendTyping() {
    var row = document.createElement("div");
    row.className = "ss-msg-row bot";
    row.innerHTML = `
      <div class="ss-msg-avatar">${ICON_BOT}</div>
      <div class="ss-skeleton">
        <div class="ss-skeleton-bar"></div>
        <div class="ss-skeleton-bar"></div>
        <div class="ss-skeleton-bar"></div>
      </div>`;
    messagesEl.appendChild(row);
    scrollToBottom();
    return row;
  }

  /* ================================================================
     TEXT FORMATTING
     ================================================================ */
  function formatText(text) {
    if (!text) return "";
    var s = esc(text);
    // Bold: **text**
    s = s.replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>");
    // Inline code: `code`
    s = s.replace(/`([^`]+)`/g, "<code>$1</code>");
    // Bullet lists
    var lines = s.split("\n");
    var out = [], inList = false;
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var bullet = /^(\s*[-•]\s+)(.*)/.exec(line);
      if (bullet) {
        if (!inList) { out.push("<ul>"); inList = true; }
        out.push("<li>" + bullet[2] + "</li>");
      } else {
        if (inList) { out.push("</ul>"); inList = false; }
        out.push(line);
      }
    }
    if (inList) out.push("</ul>");
    s = out.join("\n");
    // Paragraphs & line breaks
    s = s.replace(/\n\n/g, "<br><br>");
    s = s.replace(/\n/g, "<br>");
    return s;
  }

  function esc(str) {
    var el = document.createElement("span");
    el.textContent = str;
    return el.innerHTML;
  }

  /* ================================================================
     INPUT HELPERS
     ================================================================ */
  function onInput() {
    inputEl.style.height = "38px";
    inputEl.style.height = Math.min(inputEl.scrollHeight, 80) + "px";
    updateSendBtn();
  }

  function updateSendBtn() {
    var hasText = inputEl.value.trim().length > 0;
    sendBtn.classList.toggle("active", hasText);
  }

  function scrollToBottom() {
    requestAnimationFrame(function () {
      messagesEl.scrollTop = messagesEl.scrollHeight;
    });
  }

  /* ================================================================
     UPDATE CSS VARIABLE
     ================================================================ */
  function applyColor(color) {
    if (!shadowRoot) return;
    var styleEl = shadowRoot.querySelector("style");
    styleEl.textContent = styleEl.textContent.replace(
      /--c:\s*[^;]+;/,
      "--c: " + color + ";"
    );
  }

  /* ================================================================
     INIT
     ================================================================ */
  async function initWidget() {
    try {
      const res = await fetch(`${API_BASE}/api/widget/init`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ bot_id: BOT_ID })
      });

      if (!res.ok) {
        console.warn("SiteSense: Widget not authorized for this domain");
        return false;
      }

      const data = await res.json();
      WIDGET_TOKEN = data.token;

      config = {
        bot_name: data.bot_name || config.bot_name,
        welcome_message: data.welcome_message || config.welcome_message,
        fallback_message: data.fallback_message || config.fallback_message,
        primary_color: data.primary_color || config.primary_color,
        suggested_questions: data.suggested_questions || [],
        powered_by: data.powered_by || "SiteSense"
      };

      return true;
    } catch (err) {
      console.warn("SiteSense: Failed to initialize", err);
      return false;
    }
  }

  async function start() {
    console.log("[SiteSense] Widget starting...");
    if (!BOT_ID) { 
      console.warn("[SiteSense] Missing data-bot-id on script tag."); 
      return; 
    }

    // Wait for body to be available (useful for scripts in <head>)
    if (!document.body) {
      setTimeout(start, 50);
      return;
    }

    console.log("[SiteSense] Validating bot:", BOT_ID, "at", API_BASE);
    const authorized = await initWidget();
    
    if (!authorized) {
      console.error("[SiteSense] Connection failed. Check CORS settings or Bot ID.");
      return;
    }

    console.log("[SiteSense] Initialized successfully. Building UI...");
    build();
    applyColor(config.primary_color);
    console.log("[SiteSense] Widget ready!");
  }

  // Run when DOM is ready
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", start);
  } else {
    start();
  }
})();
