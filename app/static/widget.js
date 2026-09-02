(function () {
  var scriptTag = document.currentScript;
  var channelId = scriptTag.getAttribute("data-channel-id");
  if (!channelId) {
    console.error("[chat-widget] data-channel-id is required");
    return;
  }

  var wsProtocol = window.location.protocol === "https:" ? "wss:" : "ws:";
  var apiHost = scriptTag.src.match(/^(https?:)\/\/([^/]+)/);
  var host = apiHost ? apiHost[2] : window.location.host;

  var STORAGE_KEY = "chat_widget_visitor_id_" + channelId;
  var visitorId = localStorage.getItem(STORAGE_KEY);
  if (!visitorId) {
    visitorId = (crypto.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
    localStorage.setItem(STORAGE_KEY, visitorId);
  }

  var isOpen = false;
  var socket = null;
  var reconnectAttempts = 0;

  // ---------- UI ----------
  var container = document.createElement("div");
  container.id = "cw-widget-root";
  container.innerHTML =
    '<button id="cw-toggle-btn" aria-label="Open chat">💬</button>' +
    '<div id="cw-window" style="display:none;">' +
      '<div id="cw-header">Chat</div>' +
      '<div id="cw-messages"></div>' +
      '<form id="cw-form">' +
        '<input id="cw-input" type="text" placeholder="Type a message..." autocomplete="off" />' +
        '<button type="submit">Send</button>' +
      "</form>" +
    "</div>";

  var style = document.createElement("style");
  style.textContent =
    "#cw-widget-root{position:fixed;bottom:20px;right:20px;z-index:999999;font-family:sans-serif;}" +
    "#cw-toggle-btn{width:56px;height:56px;border-radius:50%;border:none;background:#4f46e5;color:#fff;font-size:24px;cursor:pointer;box-shadow:0 2px 10px rgba(0,0,0,.2);}" +
    "#cw-window{position:fixed;bottom:90px;right:20px;width:320px;height:440px;background:#fff;border-radius:12px;box-shadow:0 4px 20px rgba(0,0,0,.25);display:flex;flex-direction:column;overflow:hidden;}" +
    "#cw-header{background:#4f46e5;color:#fff;padding:12px 16px;font-weight:600;}" +
    "#cw-messages{flex:1;overflow-y:auto;padding:12px;font-size:14px;}" +
    ".cw-msg{margin-bottom:8px;padding:8px 12px;border-radius:8px;max-width:80%;word-wrap:break-word;}" +
    ".cw-msg-customer{background:#4f46e5;color:#fff;margin-left:auto;}" +
    ".cw-msg-bot,.cw-msg-owner{background:#f1f1f4;color:#111;margin-right:auto;}" +
    "#cw-form{display:flex;border-top:1px solid #eee;}" +
    "#cw-input{flex:1;border:none;padding:10px;font-size:14px;outline:none;}" +
    "#cw-form button{border:none;background:#4f46e5;color:#fff;padding:0 16px;cursor:pointer;}";

  document.head.appendChild(style);
  document.body.appendChild(container);

  var toggleBtn = document.getElementById("cw-toggle-btn");
  var windowEl = document.getElementById("cw-window");
  var messagesEl = document.getElementById("cw-messages");
  var formEl = document.getElementById("cw-form");
  var inputEl = document.getElementById("cw-input");

  toggleBtn.addEventListener("click", function () {
    isOpen = !isOpen;
    windowEl.style.display = isOpen ? "flex" : "none";
    if (isOpen && !socket) {
      connect();
    }
  });

  formEl.addEventListener("submit", function (e) {
    e.preventDefault();
    var text = inputEl.value.trim();
    if (!text || !socket || socket.readyState !== WebSocket.OPEN) return;
    socket.send(JSON.stringify({ text: text }));
    inputEl.value = "";
  });

  function appendMessage(sender, content) {
    var el = document.createElement("div");
    el.className = "cw-msg cw-msg-" + sender;
    el.textContent = content;
    messagesEl.appendChild(el);
    messagesEl.scrollTop = messagesEl.scrollHeight;
  }

  // ---------- WebSocket ----------
  function connect() {
    var url =
      wsProtocol + "//" + host + "/ws/widget/" + channelId + "?visitor_id=" + encodeURIComponent(visitorId);
    socket = new WebSocket(url);

    socket.onmessage = function (event) {
      var payload;
      try {
        payload = JSON.parse(event.data);
      } catch (err) {
        return;
      }
      if (payload.type === "message") {
        appendMessage(payload.data.sender, payload.data.content);
      }
    };

    socket.onclose = function () {
      socket = null;
      if (reconnectAttempts < 5) {
        reconnectAttempts++;
        setTimeout(connect, 1000 * reconnectAttempts);
      }
    };

    socket.onopen = function () {
      reconnectAttempts = 0;
    };
  }
})();