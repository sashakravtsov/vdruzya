/* Poker canvas: auto-refresh while waiting, raise presets, soft sounds. */
(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  var root = $("#poker-app");
  if (!root) return;

  var audioCtx = null;
  var muted = false;
  try { muted = window.localStorage.getItem("poker-muted") === "1"; } catch (e) {}

  function setMuted(on) {
    muted = !!on;
    try { window.localStorage.setItem("poker-muted", muted ? "1" : "0"); } catch (e) {}
    var btn = $("#poker-mute");
    if (btn) {
      btn.classList.toggle("is-off", muted);
      btn.textContent = muted ? "звук выкл" : "звук";
    }
  }

  function beep(kind) {
    try {
      if (muted) return;
      if (!window.AudioContext && !window.webkitAudioContext) return;
      audioCtx = audioCtx || new (window.AudioContext || window.webkitAudioContext)();
      var o = audioCtx.createOscillator();
      var g = audioCtx.createGain();
      o.connect(g); g.connect(audioCtx.destination);
      var now = audioCtx.currentTime;
      var map = {
        deal: [480, 0.05, 0.04],
        chip: [320, 0.06, 0.05],
        turn: [620, 0.1, 0.05],
        win: [740, 0.14, 0.06],
        fold: [180, 0.1, 0.06]
      };
      var cfg = map[kind] || map.chip;
      o.type = "sine";
      o.frequency.value = cfg[0];
      g.gain.setValueAtTime(0.0001, now);
      g.gain.exponentialRampToValueAtTime(0.05, now + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, now + cfg[1]);
      o.start(now);
      o.stop(now + cfg[1] + cfg[2]);
    } catch (e) {}
  }

  var muteBtn = $("#poker-mute");
  if (muteBtn) {
    setMuted(muted);
    muteBtn.addEventListener("click", function (ev) {
      ev.preventDefault();
      setMuted(!muted);
    });
  }

  var arena = $("#poker-arena");
  if (arena) {
    if (arena.getAttribute("data-can-act") === "1") beep("turn");
    else if (arena.getAttribute("data-status") === "done") beep("win");
    else if (arena.getAttribute("data-status") === "active") beep("deal");
  }

  $all("[data-raise-to]", root).forEach(function (btn) {
    btn.addEventListener("click", function (ev) {
      ev.preventDefault();
      var input = $("#poker-raise-input");
      if (!input) return;
      input.value = btn.getAttribute("data-raise-to") || input.value;
      input.focus();
      beep("chip");
    });
  });

  // Prefer Channels LIVE; HTTP poll only as fallback while waiting.
  var waiting = root.getAttribute("data-waiting") === "1";
  var pollUrl = root.getAttribute("data-poll-url") || "";
  var hasRt = root.getAttribute("data-poker-rt") === "game";
  if (waiting && pollUrl && !hasRt) {
    var tries = 0;
    var timer = window.setInterval(function () {
      tries += 1;
      if (tries > 45) {
        window.clearInterval(timer);
        return;
      }
      fetch(pollUrl, { credentials: "same-origin", headers: { "X-Requested-With": "XMLHttpRequest" } })
        .then(function (r) { return r.text(); })
        .then(function (html) {
          if (!html) return;
          if (html.indexOf("data-can-act=\"1\"") !== -1 || html.indexOf("data-status=\"done\"") !== -1) {
            window.clearInterval(timer);
            window.location.reload();
          }
        })
        .catch(function () {});
    }, 4000);
  }

  root.addEventListener("poker:state", function (ev) {
    var st = ev.detail || {};
    if (st.can_act) beep("turn");
    else if (st.status === "done") beep("win");
    else if (st.event === "deal" || st.event === "acted") beep("chip");
  });
})();
