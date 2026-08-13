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

  var MD_MODE_KEY = "vd-md-mode";

  function mdNotify(ta) {
    try { ta.dispatchEvent(new Event("input", { bubbles: true })); } catch (e) {}
  }

  function mdSel(ta) {
    var start = typeof ta.selectionStart === "number" ? ta.selectionStart : ta.value.length;
    var end = typeof ta.selectionEnd === "number" ? ta.selectionEnd : start;
    return { start: start, end: end, val: ta.value, selected: ta.value.slice(start, end) };
  }

  function mdReplace(ta, start, end, text, selStart, selEnd) {
    ta.focus();
    ta.value = ta.value.slice(0, start) + text + ta.value.slice(end);
    try {
      ta.selectionStart = selStart;
      ta.selectionEnd = selEnd;
    } catch (e) {}
    mdNotify(ta);
  }

  function insertAtCursor(ta, text) {
    if (!ta || !text) return;
    var s = mdSel(ta);
    mdReplace(ta, s.start, s.end, text, s.start + text.length, s.start + text.length);
  }

  function wrapSelection(ta, before, after, placeholder) {
    if (!ta) return;
    var s = mdSel(ta);
    var selected = s.selected;
    if (selected && selected.indexOf(before) === 0 && selected.length >= before.length + after.length
        && selected.slice(selected.length - after.length) === after) {
      var un = selected.slice(before.length, selected.length - after.length);
      mdReplace(ta, s.start, s.end, un, s.start, s.start + un.length);
      return;
    }
    if (!selected && s.start >= before.length
        && s.val.slice(s.start - before.length, s.start) === before
        && s.val.slice(s.end, s.end + after.length) === after) {
      mdReplace(ta, s.start - before.length, s.end + after.length, "", s.start - before.length, s.start - before.length);
      return;
    }
    var inner = selected || placeholder || "";
    var block = before + inner + after;
    if (selected) mdReplace(ta, s.start, s.end, block, s.start, s.start + block.length);
    else mdReplace(ta, s.start, s.end, block, s.start + before.length, s.start + before.length + inner.length);
  }

  function linePrefix(ta, prefix, emptyLabel) {
    if (!ta) return;
    var s = mdSel(ta);
    var lineStart = s.val.lastIndexOf("\n", s.start - 1) + 1;
    var lineEnd = s.val.indexOf("\n", s.end);
    if (lineEnd < 0) lineEnd = s.val.length;
    var chunk = s.val.slice(lineStart, lineEnd);
    var lines = chunk.split("\n");
    var allOn = lines.every(function (ln) { return !ln || ln.indexOf(prefix) === 0; });
    var out = lines.map(function (ln) {
      if (!ln) return allOn ? "" : prefix + (emptyLabel || "текст");
      if (allOn && ln.indexOf(prefix) === 0) return ln.slice(prefix.length);
      if (ln.indexOf(prefix) === 0) return ln;
      return prefix + ln;
    }).join("\n");
    mdReplace(ta, lineStart, lineEnd, out, lineStart, lineStart + out.length);
  }

  function applyMdAction(ta, action) {
    if (!ta) return;
    if (action === "bold") wrapSelection(ta, "**", "**", "жирный");
    else if (action === "italic") wrapSelection(ta, "*", "*", "курсив");
    else if (action === "strike") wrapSelection(ta, "~~", "~~", "зачёркнутый");
    else if (action === "code") wrapSelection(ta, "`", "`", "код");
    else if (action === "codeblock") wrapSelection(ta, "```\n", "\n```", "код");
    else if (action === "link") wrapSelection(ta, "[", "](https://)", "текст");
    else if (action === "h3") linePrefix(ta, "### ", "заголовок");
    else if (action === "ul") linePrefix(ta, "- ");
    else if (action === "ol") linePrefix(ta, "1. ");
    else if (action === "quote") linePrefix(ta, "> ");
    else if (action === "hr") insertAtCursor(ta, "\n\n---\n\n");
  }

  function continueListOnEnter(ta, ev) {
    var s = mdSel(ta);
    if (s.start !== s.end) return false;
    var lineStart = s.val.lastIndexOf("\n", s.start - 1) + 1;
    var line = s.val.slice(lineStart, s.start);
    var m = line.match(/^(\s*)([-*] |\d+\. |> )(.*)$/);
    if (!m) return false;
    ev.preventDefault();
    if (!(m[3] || "").trim()) {
      mdReplace(ta, lineStart, s.start, "", lineStart, lineStart);
      return true;
    }
    var next = m[2];
    if (/^\d+\. $/.test(next)) next = (parseInt(next, 10) + 1) + ". ";
    insertAtCursor(ta, "\n" + m[1] + next);
    return true;
  }

  function autosizeMd(ta) {
    if (!ta || ta.hidden) return;
    ta.style.height = "auto";
    ta.style.height = Math.min(280, Math.max(96, ta.scrollHeight)) + "px";
  }

  function setPop(wrap, on) {
    if (!wrap) return;
    var panel = wrap.querySelector("[data-pop-panel]");
    var btn = wrap.querySelector(".msg-pop-btn");
    if (!panel) return;
    if (on) closeAllPops(panel);
    panel.hidden = !on;
    if (btn) {
      if (on) btn.classList.add("is-on");
      else btn.classList.remove("is-on");
      btn.setAttribute("aria-expanded", on ? "true" : "false");
    }
  }

  function closeAllPops(except) {
    var pops = document.querySelectorAll(".msg-pop");
    for (var i = 0; i < pops.length; i++) {
      if (except && pops[i] === except) continue;
      setPop(pops[i].closest(".msg-pop-wrap"), false);
    }
  }

  function wirePop(wrap) {
    var panel = wrap && wrap.querySelector("[data-pop-panel]");
    var btn = wrap && wrap.querySelector(".msg-pop-btn");
    if (!wrap || !panel || !btn) return;
    var timer = 0;
    function later(fn, ms) {
      clearTimeout(timer);
      timer = setTimeout(fn, ms);
    }
    btn.setAttribute("aria-expanded", "false");
    btn.addEventListener("click", function (ev) {
      ev.preventDefault();
      ev.stopPropagation();
      setPop(wrap, panel.hidden);
    });
    wrap.addEventListener("mouseenter", function () {
      later(function () { setPop(wrap, true); }, 100);
    });
    wrap.addEventListener("mouseleave", function () {
      later(function () { setPop(wrap, false); }, 320);
    });
  }

  function wireFromAlbum(form) {
    if (!form || form.getAttribute("data-from-album-wired") === "1") return;
    form.setAttribute("data-from-album-wired", "1");
    var picks = form.querySelector("[data-from-album]");
    var openBtns = form.querySelectorAll("[data-from-album-open]");
    if (!picks || !openBtns.length) return;
    var baseUrl = "/compose/albums";
    var ed = form.querySelector(".msg-editor[data-from-album-url]");
    if (ed) baseUrl = ed.getAttribute("data-from-album-url") || baseUrl;

    function syncPicksVisibility() {
      picks.hidden = !picks.querySelectorAll("input[name='album_photo']").length;
    }
    function addPick(id, url) {
      if (!id || picks.querySelector("input[value='" + id + "']")) return;
      if (picks.querySelectorAll("input[name='album_photo']").length >= 5) return;
      var wrap = document.createElement("span");
      wrap.className = "compose-from-thumb";
      wrap.innerHTML = "<img alt=\"\"><button type=\"button\" class=\"compose-from-x\" title=\"убрать\">×</button>"
        + "<input type=\"hidden\" name=\"album_photo\" value=\"" + id + "\">";
      wrap.querySelector("img").src = url || "";
      wrap.querySelector(".compose-from-x").addEventListener("click", function () {
        wrap.remove();
        syncPicksVisibility();
      });
      picks.appendChild(wrap);
      syncPicksVisibility();
    }
    function bindPickerBody(root) {
      root = root || document;
      var back = root.querySelector("[data-from-album-back]");
      if (back) {
        back.addEventListener("click", function (ev) {
          ev.preventDefault();
          loadPicker(baseUrl);
        });
      }
      var opens = root.querySelectorAll("[data-from-album-id]");
      for (var i = 0; i < opens.length; i++) {
        opens[i].addEventListener("click", function (ev) {
          ev.preventDefault();
          var id = this.getAttribute("data-from-album-id");
          if (id) loadPicker(baseUrl.replace(/\/$/, "") + "/" + id);
        });
      }
      var thumbs = root.querySelectorAll("[data-photo-id]");
      for (var t = 0; t < thumbs.length; t++) {
        thumbs[t].addEventListener("click", function (ev) {
          ev.preventDefault();
          addPick(this.getAttribute("data-photo-id"), this.getAttribute("data-photo-url") || "");
        });
      }
    }
    function loadPicker(url) {
      if (!window.FBDialog) return;
      fetch(url, {
        credentials: "same-origin",
        headers: { "X-Requested-With": "XMLHttpRequest", "Accept": "text/html" },
      }).then(function (r) { return r.ok ? r.text() : null; })
        .then(function (html) {
          if (!html) return;
          FBDialog.open({
            title: "Фото из альбома",
            html: html,
            wide: true,
            buttons: [{ label: "Готово", primary: true, close: true }],
          });
          var body = document.querySelector("#classic-dialog-root .fb-dialog-body");
          bindPickerBody(body);
        });
    }
    for (var b = 0; b < openBtns.length; b++) {
      openBtns[b].addEventListener("click", function (ev) {
        ev.preventDefault();
        loadPicker(baseUrl);
      });
    }
  }

  function wireEmojiEditors(root) {
    root = root || document;
    var editors = root.querySelectorAll ? root.querySelectorAll(".msg-editor") : [];
    for (var i = 0; i < editors.length; i++) {
      (function (ed) {
        if (ed.getAttribute("data-wired") === "1") return;
        ed.setAttribute("data-wired", "1");
        var targetId = ed.getAttribute("data-emoji-for");
        var previewUrl = ed.getAttribute("data-preview-url") || "/compose/preview";
        // data-md-limit on editor — never reuse data-md-max (status counter), or querySelector
        // matches the editor itself and textContent wipes the whole toolbar.
        var maxLen = parseInt(ed.getAttribute("data-md-limit") || ed.getAttribute("data-md-max") || "4000", 10) || 4000;
        var shell = ed.closest ? ed.closest(".msg-md-shell") : null;
        var form = ed.closest ? ed.closest("form") : null;
        var stage = (shell && shell.querySelector("[data-md-stage]")) || null;
        var ta = targetId ? document.getElementById(targetId) : null;
        var clearWrap = ed.querySelector(".msg-sticker-clear");
        var preview = (stage && stage.querySelector("[data-md-preview]"))
          || (form && form.querySelector("[data-md-preview]"));
        var modeBtns = ed.querySelectorAll(".msg-md-mode-btn");
        var statusEl = shell && shell.querySelector(".msg-md-status");
        var countEl = statusEl && statusEl.querySelector("[data-md-count]");
        var maxEl = statusEl && statusEl.querySelector("[data-md-max]");
        var previewTimer = null;
        var previewReq = 0;
        var mode = "write";
        if (maxEl && maxEl !== ed) maxEl.textContent = String(maxLen);
        if (form) wireFromAlbum(form);
        var wraps = ed.querySelectorAll(".msg-pop-wrap");
        for (var w = 0; w < wraps.length; w++) wirePop(wraps[w]);

        function getTa() {
          if (!ta || !ta.isConnected) ta = targetId ? document.getElementById(targetId) : null;
          return ta;
        }
        function getPreview() {
          if (preview && preview.isConnected) return preview;
          preview = (stage && stage.querySelector("[data-md-preview]"))
            || (form && form.querySelector("[data-md-preview]"));
          return preview;
        }
        function getStage() {
          if (stage && stage.isConnected) return stage;
          stage = (shell && shell.querySelector("[data-md-stage]")) || null;
          return stage;
        }
        function syncCount() {
          var field = getTa();
          var n = field ? (field.value || "").length : 0;
          if (countEl) countEl.textContent = String(n);
          if (statusEl) {
            if (n >= maxLen - 200) statusEl.classList.add("is-warn");
            else statusEl.classList.remove("is-warn");
          }
        }
        function refreshPreview() {
          var pane = getPreview();
          if (!pane || pane.hidden) return;
          var field = getTa();
          var body = field ? field.value : "";
          var id = ++previewReq;
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
              if (id !== previewReq) return;
              pane.innerHTML = (data && data.html) || "<p class=\"muted\">не удалось показать превью</p>";
            }).catch(function () {
              if (id !== previewReq) return;
              pane.innerHTML = "<p class=\"muted\">не удалось показать превью</p>";
            });
        }
        function schedulePreview() {
          if (mode === "write") return;
          if (previewTimer) clearTimeout(previewTimer);
          previewTimer = setTimeout(refreshPreview, 220);
        }
        function setMode(next) {
          mode = (next === "split" || next === "preview") ? next : "write";
          try { sessionStorage.setItem(MD_MODE_KEY, mode); } catch (e) {}
          for (var m = 0; m < modeBtns.length; m++) {
            if (modeBtns[m].getAttribute("data-md-mode") === mode) modeBtns[m].classList.add("is-on");
            else modeBtns[m].classList.remove("is-on");
          }
          var st = getStage();
          var field = getTa();
          var pane = getPreview();
          if (st) {
            st.classList.remove("is-write", "is-split", "is-preview");
            st.classList.add("is-" + mode);
          }
          if (field) field.hidden = mode === "preview";
          if (pane) pane.hidden = mode === "write";
          if (mode !== "write") refreshPreview();
          if (field && mode !== "preview") { field.focus(); autosizeMd(field); }
        }
        for (var mb = 0; mb < modeBtns.length; mb++) {
          modeBtns[mb].addEventListener("click", function (ev) {
            ev.preventDefault();
            setMode(this.getAttribute("data-md-mode") || "write");
          });
        }
        var mdBtns = ed.querySelectorAll(".msg-md-btn[data-md]");
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
            var k = (ev.key || "").toLowerCase();
            if (ev.key === "Enter" && !ev.shiftKey && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
              if (continueListOnEnter(field, ev)) return;
            }
            if (ev.key === "Tab" && !ev.ctrlKey && !ev.metaKey && !ev.altKey) {
              ev.preventDefault();
              insertAtCursor(field, "  ");
              return;
            }
            if (!(ev.ctrlKey || ev.metaKey)) return;
            if (k === "b") { ev.preventDefault(); applyMdAction(field, "bold"); }
            else if (k === "i") { ev.preventDefault(); applyMdAction(field, "italic"); }
            else if (k === "e") { ev.preventDefault(); applyMdAction(field, "code"); }
            else if (k === "k") { ev.preventDefault(); applyMdAction(field, "link"); }
            else if (k === "p" && ev.shiftKey) {
              ev.preventDefault();
              setMode(mode === "write" ? "split" : (mode === "split" ? "preview" : "write"));
            }
          });
          field.addEventListener("input", function () {
            syncCount();
            autosizeMd(field);
            schedulePreview();
          });
          syncCount();
          autosizeMd(field);
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
        var sid = ed.getAttribute("data-sticker-input")
          || (stickerGrid && stickerGrid.getAttribute("data-sticker-input"));
        if (sid) stickerInput = document.getElementById(sid);
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

        var saved = "";
        try { saved = sessionStorage.getItem(MD_MODE_KEY) || ""; } catch (e2) {}
        setMode(saved === "split" || saved === "preview" ? saved : "write");
      })(editors[i]);
    }
    if (!document.documentElement.getAttribute("data-md-pop-doc")) {
      document.documentElement.setAttribute("data-md-pop-doc", "1");
      document.addEventListener("click", function (ev) {
        if (!ev.target.closest(".msg-pop-wrap")) closeAllPops();
      });
      document.addEventListener("keydown", function (ev) {
        if (ev.key === "Escape") closeAllPops();
      });
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
