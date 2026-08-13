/* Classic FB chrome — SSE nav badges + inbox thread bump + typing/voice (no WS messenger UI). */
(function () {
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

  function applyReadReceipts(iso) {
    var box = $("inbox-thread");
    if (!box || !iso) return;
    box.setAttribute("data-peer-read", iso);
    var peerMs = Date.parse(iso);
    if (!peerMs) return;
    var lines = box.querySelectorAll(".msg-line.is-mine");
    for (var i = 0; i < lines.length; i++) {
      var line = lines[i];
      var created = line.getAttribute("data-created");
      var createdMs = created ? Date.parse(created) : 0;
      var receipt = line.querySelector(".msg-receipt");
      if (createdMs && createdMs <= peerMs) {
        line.classList.add("is-read");
        if (receipt) receipt.textContent = " · прочитано";
      }
    }
  }

  function inboxBump(lastId) {
    var box = $("inbox-thread");
    if (!box) return;
    var conv = box.getAttribute("data-conv");
    var after = parseInt(box.getAttribute("data-last") || "0", 10);
    if (!conv || !lastId || lastId <= after) {
      if (box.getAttribute("data-peer-read")) applyReadReceipts(box.getAttribute("data-peer-read"));
      return;
    }
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
        if (data.peer_read_at) applyReadReceipts(data.peer_read_at);
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

  function pickMime() {
    if (!window.MediaRecorder) return "";
    var cands = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
    for (var i = 0; i < cands.length; i++) {
      if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(cands[i])) return cands[i];
    }
    return "";
  }

  function uploadVoice(blob, mime) {
    var box = $("inbox-thread");
    var form = $("inbox-compose");
    if (!box || !form || !blob) return;
    var url = box.getAttribute("data-message-url") || form.getAttribute("action");
    if (!url) return;
    var fd = new FormData(form);
    var ext = (mime || "").indexOf("ogg") >= 0 ? "ogg" : ((mime || "").indexOf("mp4") >= 0 ? "m4a" : "webm");
    fd.set("voice", blob, "voice." + ext);
    fd.delete("photo");
    fd.set("body", "");
    var hint = $("inbox-voice-hint");
    if (hint) hint.textContent = "отправляем…";
    fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken() },
      body: fd,
      redirect: "follow",
    }).then(function () {
      window.location.href = "/inbox?c=" + encodeURIComponent(box.getAttribute("data-conv") || "");
    }).catch(function () {
      if (hint) hint.textContent = "не удалось отправить — попробуйте ещё раз";
    });
  }

  function wireOlder() {
    var link = $("inbox-older-link");
    var box = $("inbox-thread");
    if (!link || !box) return;
    link.addEventListener("click", function (ev) {
      ev.preventDefault();
      var url = link.getAttribute("data-older-url");
      var before = link.getAttribute("data-before") || box.getAttribute("data-first") || "0";
      var tq = link.getAttribute("data-tq") || "";
      if (!url || !before) return;
      var q = url + (url.indexOf("?") >= 0 ? "&" : "?") + "before=" + encodeURIComponent(before);
      if (tq) q += "&tq=" + encodeURIComponent(tq);
      link.textContent = "загружаем…";
      fetch(q, { credentials: "same-origin", headers: { "Accept": "application/json" } })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (data) {
          if (!data || !data.html) {
            link.textContent = "← более ранние сообщения";
            return;
          }
          box.insertAdjacentHTML("afterbegin", data.html);
          if (data.first_id) {
            box.setAttribute("data-first", String(data.first_id));
            link.setAttribute("data-before", String(data.first_id));
          }
          if (data.has_older) {
            link.textContent = "← более ранние сообщения";
          } else {
            link.textContent = "это начало переписки";
            link.removeAttribute("href");
            link.onclick = function (e) { e.preventDefault(); };
          }
        })
        .catch(function () {
          link.textContent = "← более ранние сообщения";
        });
    });
  }

  function wireBulkChecks() {
    var all = $("inbox-check-all");
    if (!all) return;
    all.addEventListener("change", function () {
      var boxes = document.querySelectorAll(".inbox-check");
      for (var i = 0; i < boxes.length; i++) boxes[i].checked = all.checked;
    });
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
    var hint = $("inbox-voice-hint");
    if (!voiceBtn) return;
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia || !window.MediaRecorder) {
      if (hint) hint.textContent = "запись недоступна в этом браузере — можно выбрать файл";
      var file = $("id_voice_file");
      if (file) file.style.display = "inline";
      return;
    }

    var rec = null;
    var chunks = [];
    var voiceTimer = null;
    var mime = pickMime();

    voiceBtn.addEventListener("click", function () {
      if (rec) {
        try { rec.stop(); } catch (e) {}
        return;
      }
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        chunks = [];
        try {
          rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
        } catch (e) {
          rec = new MediaRecorder(stream);
        }
        var used = rec.mimeType || mime || "audio/webm";
        rec.ondataavailable = function (ev) {
          if (ev.data && ev.data.size) chunks.push(ev.data);
        };
        rec.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          if (voiceTimer) { clearInterval(voiceTimer); voiceTimer = null; }
          voiceBtn.textContent = "● Голосовое";
          var blob = new Blob(chunks, { type: used });
          rec = null;
          if (blob.size < 64) {
            if (hint) hint.textContent = "слишком короткая запись";
            return;
          }
          uploadVoice(blob, used);
        };
        rec.start(250);
        pingTyping("voice");
        voiceBtn.textContent = "● Стоп и отправить";
        if (hint) hint.textContent = "идёт запись…";
        voiceTimer = setInterval(function () { pingTyping("voice"); }, 3000);
      }).catch(function () {
        if (hint) hint.textContent = "нет доступа к микрофону — выберите файл";
        var file = $("id_voice_file");
        if (file) file.style.display = "inline";
      });
    });
  }

  wireBulkChecks();
  wireOlder();
  wireComposer();

  if (!window.EventSource) return;
  var snav = $("snav");
  var streamUrl = snav && snav.getAttribute("data-rt");
  if (!streamUrl) return;

  var box = $("inbox-thread");
  if (box && box.getAttribute("data-conv")) {
    streamUrl += (streamUrl.indexOf("?") >= 0 ? "&" : "?") + "c=" + encodeURIComponent(box.getAttribute("data-conv"));
  }

  var es = new EventSource(streamUrl);
  es.onmessage = function (ev) {
    try {
      var d = JSON.parse(ev.data);
      applyBadges(d);
      if (typeof d.last_message_id === "number") inboxBump(d.last_message_id);
      if (Object.prototype.hasOwnProperty.call(d, "typing")) applyTyping(d.typing || []);
      if (d.peer_read_at) applyReadReceipts(d.peer_read_at);
    } catch (e) {}
  };
  es.onerror = function () {
    /* browser reconnects; after server MAX_TICKS stream ends and EventSource retries */
  };
})();
