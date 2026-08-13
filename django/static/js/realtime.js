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
          wireVoicePlayers(box);
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

  var VOICE_BARS = 40;
  var VOICE_MAX_MS = 300000;
  var activeVoice = null;

  function voiceCfg() {
    var box = $("inbox-thread");
    var bars = box ? parseInt(box.getAttribute("data-voice-bars") || "40", 10) : VOICE_BARS;
    var maxMs = box ? parseInt(box.getAttribute("data-voice-max-ms") || "300000", 10) : VOICE_MAX_MS;
    return { bars: bars > 0 ? bars : VOICE_BARS, maxMs: maxMs > 0 ? maxMs : VOICE_MAX_MS };
  }

  function pickMime() {
    if (!window.MediaRecorder) return "";
    var cands = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg;codecs=opus", "audio/mp4"];
    for (var i = 0; i < cands.length; i++) {
      if (MediaRecorder.isTypeSupported && MediaRecorder.isTypeSupported(cands[i])) return cands[i];
    }
    return "";
  }

  function fmtDur(ms) {
    var s = Math.max(0, Math.floor((ms || 0) / 1000));
    return Math.floor(s / 60) + ":" + ("0" + (s % 60)).slice(-2);
  }

  function ensureBars(el, n) {
    if (!el) return;
    n = n || voiceCfg().bars;
    if (el.children.length === n) return;
    var html = "";
    for (var i = 0; i < n; i++) html += '<i style="height:18%"></i>';
    el.innerHTML = html;
  }

  function setBarHeights(el, heights) {
    if (!el) return;
    ensureBars(el, heights ? heights.length : voiceCfg().bars);
    var kids = el.children;
    for (var i = 0; i < kids.length; i++) {
      kids[i].style.height = Math.max(4, Math.min(100, heights && heights[i] != null ? heights[i] : 18)) + "%";
    }
  }

  function paintPeaks(el, csv) {
    if (!el) return;
    var parts = (csv || "").split(",");
    var heights = [];
    for (var i = 0; i < parts.length; i++) {
      var n = parseInt(parts[i], 10);
      if (!isNaN(n)) heights.push(n);
    }
    if (heights.length < 8) {
      ensureBars(el);
      return;
    }
    setBarHeights(el, heights);
  }

  function peaksFromBuffer(buf, bars) {
    bars = bars || voiceCfg().bars;
    var data = buf.getChannelData(0);
    if (!data || !data.length) return "";
    var bucket = Math.max(1, Math.floor(data.length / bars));
    var peaks = [];
    var i, j, peak, v, max = 0.0001;
    for (i = 0; i < bars; i++) {
      peak = 0;
      for (j = 0; j < bucket; j++) {
        v = Math.abs(data[i * bucket + j] || 0);
        if (v > peak) peak = v;
      }
      peaks.push(peak);
      if (peak > max) max = peak;
    }
    return peaks.map(function (p) {
      return String(Math.max(4, Math.min(100, Math.round((p / max) * 100))));
    }).join(",");
  }

  function extractWaveform(blob) {
    return new Promise(function (resolve) {
      if (!blob || !(window.AudioContext || window.webkitAudioContext)) {
        resolve({ peaks: "", ms: 0 });
        return;
      }
      var AC = window.AudioContext || window.webkitAudioContext;
      var ctx = new AC();
      blob.arrayBuffer().then(function (ab) {
        return ctx.decodeAudioData(ab.slice(0));
      }).then(function (buf) {
        var peaks = peaksFromBuffer(buf, voiceCfg().bars);
        var ms = Math.round((buf.duration || 0) * 1000);
        try { ctx.close(); } catch (e) {}
        resolve({ peaks: peaks, ms: ms });
      }).catch(function () {
        try { ctx.close(); } catch (e) {}
        resolve({ peaks: "", ms: 0 });
      });
    });
  }

  function paintLiveWave(el, analyser) {
    if (!el || !analyser) return;
    var bars = voiceCfg().bars;
    ensureBars(el, bars);
    var data = new Uint8Array(analyser.frequencyBinCount);
    analyser.getByteTimeDomainData(data);
    var step = Math.max(1, Math.floor(data.length / bars));
    var heights = [];
    for (var i = 0; i < bars; i++) {
      var v = data[i * step] || 128;
      heights.push(Math.max(8, Math.min(100, Math.round(Math.abs(v - 128) / 128 * 100))));
    }
    setBarHeights(el, heights);
  }

  function setWaveProgress(wave, ratio) {
    if (!wave) return;
    var bars = wave.children;
    var n = bars.length;
    var on = Math.round(Math.max(0, Math.min(1, ratio || 0)) * n);
    for (var i = 0; i < n; i++) {
      if (i < on) bars[i].classList.add("is-played");
      else bars[i].classList.remove("is-played");
    }
    wave.setAttribute("aria-valuenow", String(Math.round(Math.max(0, Math.min(1, ratio || 0)) * 100)));
  }

  function setVoicePlaying(wrap, on) {
    if (!wrap) return;
    var btn = wrap.querySelector(".msg-voice-play");
    if (btn) {
      btn.textContent = on ? "❚❚" : "▶";
      if (on) btn.classList.add("is-on");
      else btn.classList.remove("is-on");
    }
    if (on) wrap.classList.add("is-playing");
    else wrap.classList.remove("is-playing");
  }

  function pauseVoice(wrap) {
    if (!wrap) return;
    var audio = wrap.querySelector("audio");
    if (audio && !audio.paused) {
      try { audio.pause(); } catch (e) {}
    }
    setVoicePlaying(wrap, false);
    if (activeVoice === wrap) activeVoice = null;
  }

  function playVoice(wrap) {
    if (!wrap) return;
    var audio = wrap.querySelector("audio");
    if (!audio) return;
    if (activeVoice && activeVoice !== wrap) pauseVoice(activeVoice);
    audio.play().catch(function () {});
    setVoicePlaying(wrap, true);
    activeVoice = wrap;
  }

  function seekVoice(wrap, ratio, andPlay) {
    var audio = wrap.querySelector("audio");
    var wave = wrap.querySelector(".msg-wave");
    if (!audio) return;
    var baseMs = parseInt(wrap.getAttribute("data-ms") || "0", 10) || 0;
    var t = audio.duration || (baseMs / 1000) || 0;
    if (!t) return;
    ratio = Math.max(0, Math.min(1, ratio));
    audio.currentTime = ratio * t;
    setWaveProgress(wave, ratio);
    if (andPlay) playVoice(wrap);
  }

  function wireOneVoice(wrap) {
    if (!wrap || wrap.getAttribute("data-wired") === "1" || wrap.classList.contains("is-draft")) return;
    wrap.setAttribute("data-wired", "1");
    var btn = wrap.querySelector(".msg-voice-play");
    var wave = wrap.querySelector(".msg-wave");
    var dur = wrap.querySelector(".msg-voice-dur");
    var audio = wrap.querySelector("audio");
    if (!btn || !audio) return;
    var baseMs = parseInt(wrap.getAttribute("data-ms") || "0", 10) || 0;
    if (dur && baseMs) dur.textContent = fmtDur(baseMs);

    function totalSec() {
      return audio.duration || (baseMs / 1000) || 0;
    }
    function syncLabel() {
      if (!dur) return;
      var t = totalSec();
      if (!t || audio.paused) {
        dur.textContent = fmtDur(baseMs || t * 1000);
        return;
      }
      dur.textContent = fmtDur(Math.max(0, t - audio.currentTime) * 1000);
    }

    btn.addEventListener("click", function () {
      if (audio.paused) playVoice(wrap);
      else pauseVoice(wrap);
    });
    audio.addEventListener("timeupdate", function () {
      var t = totalSec();
      setWaveProgress(wave, t ? audio.currentTime / t : 0);
      syncLabel();
    });
    audio.addEventListener("ended", function () {
      setVoicePlaying(wrap, false);
      setWaveProgress(wave, 0);
      if (activeVoice === wrap) activeVoice = null;
      syncLabel();
    });
    audio.addEventListener("pause", function () {
      if (audio.ended) return;
      setVoicePlaying(wrap, false);
      if (activeVoice === wrap) activeVoice = null;
      syncLabel();
    });
    audio.addEventListener("loadedmetadata", function () {
      if (!baseMs && audio.duration) {
        baseMs = Math.round(audio.duration * 1000);
        wrap.setAttribute("data-ms", String(baseMs));
        syncLabel();
      }
    });

    function ratioFromEvent(ev) {
      var rect = wave.getBoundingClientRect();
      if (!rect.width) return 0;
      var x = (ev.touches && ev.touches[0] ? ev.touches[0].clientX : ev.clientX) - rect.left;
      return x / rect.width;
    }
    if (wave) {
      wave.addEventListener("pointerdown", function (ev) {
        ev.preventDefault();
        try { wave.setPointerCapture(ev.pointerId); } catch (e) {}
        seekVoice(wrap, ratioFromEvent(ev), true);
      });
      wave.addEventListener("pointermove", function (ev) {
        if ((ev.buttons || 0) === 0 && ev.pressure === 0) return;
        seekVoice(wrap, ratioFromEvent(ev), false);
      });
      wave.addEventListener("keydown", function (ev) {
        var t = totalSec();
        if (!t) return;
        var cur = audio.currentTime || 0;
        if (ev.key === "ArrowRight") { ev.preventDefault(); seekVoice(wrap, (cur + 2) / t, !audio.paused); }
        else if (ev.key === "ArrowLeft") { ev.preventDefault(); seekVoice(wrap, (cur - 2) / t, !audio.paused); }
        else if (ev.key === "Home") { ev.preventDefault(); seekVoice(wrap, 0, !audio.paused); }
        else if (ev.key === "End") { ev.preventDefault(); seekVoice(wrap, 1, !audio.paused); }
        else if (ev.key === " " || ev.key === "Enter") {
          ev.preventDefault();
          if (audio.paused) playVoice(wrap); else pauseVoice(wrap);
        }
      });
    }
  }

  function wireVoicePlayers(root) {
    root = root || document;
    var nodes = root.querySelectorAll ? root.querySelectorAll(".msg-voice") : [];
    for (var i = 0; i < nodes.length; i++) wireOneVoice(nodes[i]);
  }

  function uploadVoice(blob, mime, meta) {
    var box = $("inbox-thread");
    var form = $("inbox-compose");
    var hint = $("inbox-voice-hint");
    if (!box || !form || !blob) return Promise.reject();
    var url = box.getAttribute("data-message-url") || form.getAttribute("action");
    if (!url) return Promise.reject();
    var fd = new FormData(form);
    var ext = (mime || "").indexOf("ogg") >= 0 ? "ogg" : ((mime || "").indexOf("mp4") >= 0 ? "m4a" : "webm");
    fd.set("voice", blob, "voice." + ext);
    fd.delete("photo");
    fd.set("body", "");
    if (meta && meta.peaks) fd.set("waveform", meta.peaks);
    if (meta && meta.ms) fd.set("duration_ms", String(meta.ms));
    if (hint) hint.textContent = "отправляем…";
    return fetch(url, {
      method: "POST",
      credentials: "same-origin",
      headers: { "X-CSRFToken": csrfToken(), "Accept": "application/json" },
      body: fd,
    }).then(function (r) { return r.json().then(function (d) { return { ok: r.ok, data: d }; }); })
      .then(function (res) {
        if (!res.ok || !res.data || !res.data.ok) {
          throw new Error((res.data && res.data.error) || "fail");
        }
        if (hint) hint.textContent = "запись · прослушать · отправить · до 5 мин";
        inboxBump(res.data.last_id);
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
          wireVoicePlayers(box);
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
    var cancelBtn = $("inbox-voice-cancel");
    var hint = $("inbox-voice-hint");
    var live = $("inbox-voice-live");
    var liveWave = $("inbox-voice-live-wave");
    var liveDur = $("inbox-voice-live-dur");
    var draft = $("inbox-voice-draft");
    var draftWave = $("inbox-voice-draft-wave");
    var draftDur = $("inbox-voice-draft-dur");
    var draftPlay = $("inbox-voice-draft-play");
    var sendBtn = $("inbox-voice-send");
    var discardBtn = $("inbox-voice-discard");
    var fileInput = $("id_voice_file");
    if (!voiceBtn) return;

    var rec = null;
    var chunks = [];
    var voiceTimer = null;
    var liveRaf = 0;
    var startedAt = 0;
    var cancelled = false;
    var mime = pickMime();
    var audioCtx = null;
    var analyser = null;
    var draftBlob = null;
    var draftMime = "";
    var draftMeta = null;
    var draftUrl = "";
    var draftAudio = null;
    var canRecord = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);

    function setHint(text) { if (hint) hint.textContent = text; }
    function idleHint() { setHint("запись · прослушать · отправить · до 5 мин"); }

    function stopLiveMeter() {
      if (liveRaf) { cancelAnimationFrame(liveRaf); liveRaf = 0; }
      if (audioCtx) {
        try { audioCtx.close(); } catch (e) {}
        audioCtx = null;
        analyser = null;
      }
      if (live) { live.hidden = true; live.setAttribute("aria-hidden", "true"); }
      if (cancelBtn) cancelBtn.hidden = true;
    }

    function clearDraft() {
      if (draftAudio) {
        try { draftAudio.pause(); } catch (e) {}
        draftAudio = null;
      }
      if (draftUrl) {
        try { URL.revokeObjectURL(draftUrl); } catch (e) {}
        draftUrl = "";
      }
      draftBlob = null;
      draftMime = "";
      draftMeta = null;
      if (draft) draft.hidden = true;
      if (draftPlay) { draftPlay.textContent = "▶"; draftPlay.classList.remove("is-on"); }
      if (fileInput) fileInput.value = "";
    }

    function showDraft(blob, usedMime, meta) {
      clearDraft();
      draftBlob = blob;
      draftMime = usedMime || "audio/webm";
      draftMeta = meta || { peaks: "", ms: 0 };
      draftUrl = URL.createObjectURL(blob);
      draftAudio = new Audio(draftUrl);
      draftAudio.preload = "metadata";
      draftAudio.onended = function () {
        if (draftPlay) { draftPlay.textContent = "▶"; draftPlay.classList.remove("is-on"); }
        setWaveProgress(draftWave, 0);
        if (draftDur) draftDur.textContent = fmtDur((draftMeta && draftMeta.ms) || 0);
      };
      draftAudio.ontimeupdate = function () {
        var t = draftAudio.duration || ((draftMeta && draftMeta.ms) || 0) / 1000;
        setWaveProgress(draftWave, t ? draftAudio.currentTime / t : 0);
        if (draftDur && t) draftDur.textContent = fmtDur(Math.max(0, t - draftAudio.currentTime) * 1000);
      };
      paintPeaks(draftWave, draftMeta.peaks);
      if (draftDur) draftDur.textContent = fmtDur(draftMeta.ms || 0);
      if (draft) draft.hidden = false;
      setHint("прослушайте и отправьте, или сбросьте");
      voiceBtn.textContent = "● Голосовое";
    }

    function tickLive() {
      if (!analyser || !liveWave) return;
      var elapsed = Date.now() - startedAt;
      paintLiveWave(liveWave, analyser);
      if (liveDur) liveDur.textContent = fmtDur(elapsed);
      if (elapsed >= voiceCfg().maxMs && rec) {
        cancelled = false;
        try { rec.stop(); } catch (e) {}
        return;
      }
      liveRaf = requestAnimationFrame(tickLive);
    }

    if (!canRecord) {
      setHint("запись недоступна — выберите аудиофайл");
      if (fileInput) fileInput.style.display = "inline";
    }

    if (cancelBtn) {
      cancelBtn.addEventListener("click", function () {
        if (!rec) return;
        cancelled = true;
        try { rec.stop(); } catch (e) {}
      });
    }
    if (discardBtn) {
      discardBtn.addEventListener("click", function () {
        clearDraft();
        idleHint();
      });
    }
    if (draftPlay) {
      draftPlay.addEventListener("click", function () {
        if (!draftAudio) return;
        if (draftAudio.paused) {
          if (activeVoice) pauseVoice(activeVoice);
          draftAudio.play().catch(function () {});
          draftPlay.textContent = "❚❚";
          draftPlay.classList.add("is-on");
        } else {
          draftAudio.pause();
          draftPlay.textContent = "▶";
          draftPlay.classList.remove("is-on");
        }
      });
    }

    if (sendBtn) {
      sendBtn.addEventListener("click", function () {
        if (!draftBlob) return;
        sendBtn.disabled = true;
        uploadVoice(draftBlob, draftMime, draftMeta).then(function () {
          clearDraft();
          idleHint();
        }).catch(function (err) {
          setHint((err && err.message) || "не удалось отправить — попробуйте ещё раз");
        }).then(function () {
          sendBtn.disabled = false;
        });
      });
    }

    if (fileInput) {
      fileInput.addEventListener("change", function () {
        var f = fileInput.files && fileInput.files[0];
        if (!f) return;
        setHint("строим дорожку…");
        extractWaveform(f).then(function (meta) {
          if ((meta.ms || 0) > voiceCfg().maxMs) {
            setHint("файл длиннее 5 минут");
            fileInput.value = "";
            return;
          }
          showDraft(f, f.type || "audio/webm", meta);
        });
      });
    }

    voiceBtn.addEventListener("click", function () {
      if (!canRecord) {
        if (fileInput) fileInput.click();
        return;
      }
      if (rec) {
        cancelled = false;
        try { rec.stop(); } catch (e) {}
        return;
      }
      clearDraft();
      navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
        chunks = [];
        cancelled = false;
        try {
          rec = mime ? new MediaRecorder(stream, { mimeType: mime }) : new MediaRecorder(stream);
        } catch (e) {
          rec = new MediaRecorder(stream);
        }
        var used = rec.mimeType || mime || "audio/webm";
        try {
          var AC = window.AudioContext || window.webkitAudioContext;
          audioCtx = new AC();
          var src = audioCtx.createMediaStreamSource(stream);
          analyser = audioCtx.createAnalyser();
          analyser.fftSize = 256;
          src.connect(analyser);
          if (live) { live.hidden = false; live.setAttribute("aria-hidden", "false"); }
          if (cancelBtn) cancelBtn.hidden = false;
          startedAt = Date.now();
          ensureBars(liveWave);
          tickLive();
        } catch (e) {}
        rec.ondataavailable = function (ev) {
          if (ev.data && ev.data.size) chunks.push(ev.data);
        };
        rec.onstop = function () {
          stream.getTracks().forEach(function (t) { t.stop(); });
          if (voiceTimer) { clearInterval(voiceTimer); voiceTimer = null; }
          stopLiveMeter();
          voiceBtn.textContent = "● Голосовое";
          var blob = new Blob(chunks, { type: used });
          rec = null;
          if (cancelled) {
            setHint("запись отменена");
            return;
          }
          if (blob.size < 64) {
            setHint("слишком короткая запись");
            return;
          }
          setHint("строим дорожку…");
          extractWaveform(blob).then(function (meta) {
            showDraft(blob, used, meta);
          });
        };
        rec.start(250);
        pingTyping("voice");
        voiceBtn.textContent = "■ Стоп";
        setHint("идёт запись… стоп → прослушать → отправить");
        voiceTimer = setInterval(function () { pingTyping("voice"); }, 3000);
      }).catch(function () {
        setHint("нет доступа к микрофону — выберите файл");
        if (fileInput) fileInput.style.display = "inline";
      });
    });
  }

  function insertAtCursor(ta, text) {
    if (!ta || !text) return;
    ta.focus();
    var start = typeof ta.selectionStart === "number" ? ta.selectionStart : ta.value.length;
    var end = typeof ta.selectionEnd === "number" ? ta.selectionEnd : start;
    var before = ta.value.slice(0, start);
    var after = ta.value.slice(end);
    ta.value = before + text + after;
    var pos = start + text.length;
    try {
      ta.selectionStart = pos;
      ta.selectionEnd = pos;
    } catch (e) {}
    try {
      ta.dispatchEvent(new Event("input", { bubbles: true }));
    } catch (e2) {}
  }

  function wrapSelection(ta, before, after, placeholder) {
    if (!ta) return;
    ta.focus();
    var start = typeof ta.selectionStart === "number" ? ta.selectionStart : ta.value.length;
    var end = typeof ta.selectionEnd === "number" ? ta.selectionEnd : start;
    var selected = ta.value.slice(start, end);
    var inner = selected || placeholder || "";
    var block = before + inner + after;
    ta.value = ta.value.slice(0, start) + block + ta.value.slice(end);
    if (selected) {
      try {
        ta.selectionStart = start;
        ta.selectionEnd = start + block.length;
      } catch (e) {}
    } else {
      try {
        ta.selectionStart = start + before.length;
        ta.selectionEnd = start + before.length + inner.length;
      } catch (e2) {}
    }
    try { ta.dispatchEvent(new Event("input", { bubbles: true })); } catch (e3) {}
  }

  function linePrefix(ta, prefix) {
    if (!ta) return;
    ta.focus();
    var start = typeof ta.selectionStart === "number" ? ta.selectionStart : 0;
    var end = typeof ta.selectionEnd === "number" ? ta.selectionEnd : start;
    var val = ta.value;
    var lineStart = val.lastIndexOf("\n", start - 1) + 1;
    var lineEnd = val.indexOf("\n", end);
    if (lineEnd < 0) lineEnd = val.length;
    var chunk = val.slice(lineStart, lineEnd);
    var lines = chunk.split("\n");
    var out = lines.map(function (ln) {
      if (!ln) return prefix + "текст";
      if (ln.indexOf(prefix) === 0) return ln;
      return prefix + ln;
    }).join("\n");
    ta.value = val.slice(0, lineStart) + out + val.slice(lineEnd);
    try {
      ta.selectionStart = lineStart;
      ta.selectionEnd = lineStart + out.length;
    } catch (e) {}
    try { ta.dispatchEvent(new Event("input", { bubbles: true })); } catch (e2) {}
  }

  function applyMdAction(ta, action) {
    if (!ta) return;
    if (action === "bold") wrapSelection(ta, "**", "**", "жирный");
    else if (action === "italic") wrapSelection(ta, "*", "*", "курсив");
    else if (action === "strike") wrapSelection(ta, "~~", "~~", "зачёркнутый");
    else if (action === "code") wrapSelection(ta, "`", "`", "код");
    else if (action === "link") wrapSelection(ta, "[", "](https://)", "текст");
    else if (action === "ul") linePrefix(ta, "- ");
    else if (action === "quote") linePrefix(ta, "> ");
  }

  function wireEmojiEditors(root) {
    root = root || document;
    var editors = root.querySelectorAll ? root.querySelectorAll(".msg-editor") : [];
    for (var i = 0; i < editors.length; i++) {
      (function (ed) {
        if (ed.getAttribute("data-wired") === "1") return;
        ed.setAttribute("data-wired", "1");
        var targetId = ed.getAttribute("data-emoji-for");
        var previewUrl = ed.getAttribute("data-preview-url") || "/inbox/preview";
        var ta = targetId ? document.getElementById(targetId) : null;
        var tabs = ed.querySelectorAll(".msg-editor-tab");
        var panes = ed.querySelectorAll("[data-pane-body]");
        var clearWrap = ed.querySelector(".msg-sticker-clear");
        var form = ed.closest ? ed.closest("form") : null;
        var preview = (form && form.querySelector("[data-md-preview]")) || ed.querySelector("[data-md-preview]");
        var modeBtns = ed.querySelectorAll(".msg-md-mode-btn");
        var previewTimer = null;
        var mode = "write";

        function getTa() {
          if (!ta) ta = document.getElementById(targetId);
          return ta;
        }

        function getPreview() {
          if (preview && preview.isConnected) return preview;
          form = ed.closest ? ed.closest("form") : form;
          preview = (form && form.querySelector("[data-md-preview]")) || ed.querySelector("[data-md-preview]");
          return preview;
        }

        function showPane(name) {
          for (var t = 0; t < tabs.length; t++) {
            if (tabs[t].getAttribute("data-pane") === name) tabs[t].classList.add("is-on");
            else tabs[t].classList.remove("is-on");
          }
          for (var p = 0; p < panes.length; p++) {
            panes[p].hidden = panes[p].getAttribute("data-pane-body") !== name;
          }
        }

        function setMode(next) {
          mode = next === "preview" ? "preview" : "write";
          for (var m = 0; m < modeBtns.length; m++) {
            if (modeBtns[m].getAttribute("data-md-mode") === mode) modeBtns[m].classList.add("is-on");
            else modeBtns[m].classList.remove("is-on");
          }
          var field = getTa();
          var pane = getPreview();
          if (mode === "preview") {
            if (field) field.hidden = true;
            if (pane) pane.hidden = false;
            refreshPreview();
          } else {
            if (field) field.hidden = false;
            if (pane) pane.hidden = true;
            if (field) field.focus();
          }
        }

        function refreshPreview() {
          var pane = getPreview();
          if (!pane) return;
          var field = getTa();
          var body = field ? field.value : "";
          pane.innerHTML = "<p class=\"muted\">обновляем…</p>";
          var fd = new FormData();
          fd.set("body", body);
          fetch(previewUrl, {
            method: "POST",
            credentials: "same-origin",
            headers: { "X-CSRFToken": csrfToken(), "Accept": "application/json" },
            body: fd,
          }).then(function (r) { return r.ok ? r.json() : null; })
            .then(function (data) {
              if (!data) {
                pane.innerHTML = "<p class=\"muted\">не удалось показать превью</p>";
                return;
              }
              pane.innerHTML = data.html || "";
            }).catch(function () {
              pane.innerHTML = "<p class=\"muted\">не удалось показать превью</p>";
            });
        }

        for (var t = 0; t < tabs.length; t++) {
          tabs[t].addEventListener("click", function (ev) {
            ev.preventDefault();
            showPane(this.getAttribute("data-pane") || "emoji");
          });
        }

        for (var mb = 0; mb < modeBtns.length; mb++) {
          modeBtns[mb].addEventListener("click", function (ev) {
            ev.preventDefault();
            setMode(this.getAttribute("data-md-mode") || "write");
          });
        }

        var mdBtns = ed.querySelectorAll(".msg-md-btn");
        for (var mb2 = 0; mb2 < mdBtns.length; mb2++) {
          mdBtns[mb2].addEventListener("click", function (ev) {
            ev.preventDefault();
            if (mode === "preview") setMode("write");
            applyMdAction(getTa(), this.getAttribute("data-md") || "");
          });
        }

        var field = getTa();
        if (field) {
          field.addEventListener("keydown", function (ev) {
            if (!(ev.ctrlKey || ev.metaKey)) return;
            var k = (ev.key || "").toLowerCase();
            if (k === "b") { ev.preventDefault(); applyMdAction(field, "bold"); }
            else if (k === "i") { ev.preventDefault(); applyMdAction(field, "italic"); }
            else if (k === "e") { ev.preventDefault(); applyMdAction(field, "code"); }
            else if (k === "k") { ev.preventDefault(); applyMdAction(field, "link"); }
            else if (k === "p" && ev.shiftKey) {
              ev.preventDefault();
              setMode(mode === "preview" ? "write" : "preview");
            }
          });
          field.addEventListener("input", function () {
            if (mode !== "preview") return;
            if (previewTimer) clearTimeout(previewTimer);
            previewTimer = setTimeout(refreshPreview, 280);
          });
        }

        var emojiBtns = ed.querySelectorAll(".msg-emoji-btn");
        for (var e = 0; e < emojiBtns.length; e++) {
          emojiBtns[e].addEventListener("click", function (ev) {
            ev.preventDefault();
            if (mode === "preview") setMode("write");
            insertAtCursor(getTa(), this.getAttribute("data-emoji") || "");
          });
        }

        var stickerGrid = ed.querySelector(".msg-sticker-grid");
        var stickerInput = null;
        if (stickerGrid) {
          var sid = stickerGrid.getAttribute("data-sticker-input");
          stickerInput = sid ? document.getElementById(sid) : null;
        }
        function syncStickerUI() {
          var val = stickerInput ? (stickerInput.value || "") : "";
          var btns = ed.querySelectorAll(".msg-sticker-btn");
          for (var b = 0; b < btns.length; b++) {
            if (btns[b].getAttribute("data-sticker-id") === val) btns[b].classList.add("is-on");
            else btns[b].classList.remove("is-on");
          }
          if (clearWrap) clearWrap.hidden = !val;
        }
        var sbtns = ed.querySelectorAll(".msg-sticker-btn");
        for (var s = 0; s < sbtns.length; s++) {
          sbtns[s].addEventListener("click", function (ev) {
            ev.preventDefault();
            if (!stickerInput) return;
            var id = this.getAttribute("data-sticker-id") || "";
            stickerInput.value = (stickerInput.value === id) ? "" : id;
            syncStickerUI();
            showPane("stickers");
          });
        }
        var clearBtn = ed.querySelector("[data-sticker-clear]");
        if (clearBtn) {
          clearBtn.addEventListener("click", function (ev) {
            ev.preventDefault();
            if (stickerInput) stickerInput.value = "";
            syncStickerUI();
          });
        }
        syncStickerUI();
      })(editors[i]);
    }
  }

  wireBulkChecks();
  wireOlder();
  wireComposer();
  wireVoicePlayers(document);
  wireEmojiEditors(document);

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
