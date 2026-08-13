/* Classic FB chrome — SSE nav badges + inbox thread bump + typing (no WS messenger UI). */
(function () {
  if (!window.EventSource) return;

  function $(id) { return document.getElementById(id); }

  function csrfToken() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    return m ? decodeURIComponent(m[1]) : "";
  }

  function setCount(linkId, n, base) {
    var a = $(linkId);
    if (!a) return;
    var label = base || a.getAttribute("data-label") || a.textContent.replace(/\s*\(\d+\)\s*$/, "");
    a.setAttribute("data-label", label);
    a.textContent = n > 0 ? label + " (" + n + ")" : label;
  }

  function applyBadges(d) {
    if (!d) return;
    if (typeof d.unread_messages === "number") setCount("nav-inbox", d.unread_messages, "Входящие");
    if (typeof d.notifications === "number") setCount("nav-notifications", d.notifications, "Уведомления");
    if (typeof d.pokes === "number") setCount("nav-pokes", d.pokes, "Подмигивания");
    if (typeof d.friend_requests === "number") setCount("nav-friends", d.friend_requests, "Мои друзья");
  }

  function formatTyping(rows) {
    if (!rows || !rows.length) return "";
    var voice = [];
    var typing = [];
    for (var i = 0; i < rows.length; i++) {
      var r = rows[i];
      if (!r || !r.name) continue;
      if (r.state === "voice") voice.push(r.name);
      else typing.push(r.name);
    }
    var parts = [];
    if (typing.length === 1) parts.push(typing[0] + " печатает…");
    else if (typing.length > 1) parts.push(typing.join(", ") + " печатают…");
    if (voice.length === 1) parts.push(voice[0] + " записывает голосовое…");
    else if (voice.length > 1) parts.push(voice.join(", ") + " записывают голосовое…");
    return parts.join(" · ");
  }

  function applyTyping(rows) {
    var el = $("inbox-typing");
    if (!el) return;
    var text = formatTyping(rows);
    if (text) {
      el.textContent = text;
      el.hidden = false;
    } else {
      el.textContent = "";
      el.hidden = true;
    }
  }

  function inboxBump(lastId) {
    var box = $("inbox-thread");
    if (!box) return;
    var conv = box.getAttribute("data-conv");
    var after = parseInt(box.getAttribute("data-last") || "0", 10);
    if (!conv || !lastId || lastId <= after) return;
    var url = "/inbox/" + conv + "/since?after=" + after;
    fetch(url, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data) return;
        if (data.html) {
          box.insertAdjacentHTML("beforeend", data.html);
          box.setAttribute("data-last", String(data.last_id || lastId));
          try { box.scrollTop = box.scrollHeight; } catch (e) {}
        }
        if (typeof data.unread_messages === "number") {
          setCount("nav-inbox", data.unread_messages, "Входящие");
        }
        if (data.typing) applyTyping(data.typing);
      })
      .catch(function () {});
  }

  function pingTyping(state) {
    var box = $("inbox-thread");
    if (!box) return;
    var url = box.getAttribute("data-typing-url");
    if (!url) return;
    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/x-www-form-urlencoded",
        "X-CSRFToken": csrfToken(),
      },
      body: "state=" + encodeURIComponent(state || "typing"),
    }).catch(function () {});
  }

  function wireComposer() {
    var form = $("inbox-compose");
    var box = $("inbox-thread");
    if (!form || !box) return;
    var last = 0;
    var ta = form.querySelector("textarea");
    function onType() {
      var now = Date.now();
      if (now - last < 2500) return;
      last = now;
      pingTyping("typing");
    }
    if (ta) {
      ta.addEventListener("input", onType);
      ta.addEventListener("keydown", onType);
    }
    var voiceBtn = $("inbox-voice-btn");
    if (!voiceBtn) return;
    var voiceTimer = null;
    voiceBtn.addEventListener("click", function () {
      if (voiceTimer) {
        clearInterval(voiceTimer);
        voiceTimer = null;
        voiceBtn.textContent = "● Голосовое";
        return;
      }
      pingTyping("voice");
      voiceBtn.textContent = "● Запись… (стоп)";
      voiceTimer = setInterval(function () { pingTyping("voice"); }, 3000);
    });
  }

  var snav = $("snav");
  var streamUrl = snav && snav.getAttribute("data-rt");
  if (!streamUrl) return;

  var box = $("inbox-thread");
  if (box && box.getAttribute("data-conv")) {
    streamUrl += (streamUrl.indexOf("?") >= 0 ? "&" : "?") + "c=" + encodeURIComponent(box.getAttribute("data-conv"));
  }

  wireComposer();

  var es = new EventSource(streamUrl);
  es.onmessage = function (ev) {
    try {
      var d = JSON.parse(ev.data);
      applyBadges(d);
      if (typeof d.last_message_id === "number") inboxBump(d.last_message_id);
      if (Object.prototype.hasOwnProperty.call(d, "typing")) applyTyping(d.typing || []);
    } catch (e) {}
  };
  es.onerror = function () {
    /* browser reconnects; after server MAX_TICKS stream ends and EventSource retries */
  };
})();
