/* Chess canvas: click/drag moves, clocks, sounds, auto-refresh. */
(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }
  function $all(sel, root) { return Array.prototype.slice.call((root || document).querySelectorAll(sel)); }

  function readJsonScript(id) {
    var el = document.getElementById(id);
    if (!el) return {};
    try { return JSON.parse(el.textContent || "{}"); } catch (e) { return {}; }
  }

  function formatClock(ms) {
    ms = Math.max(0, ms | 0);
    var total = Math.floor(ms / 1000);
    var days = Math.floor(total / 86400);
    var h = Math.floor((total % 86400) / 3600);
    var m = Math.floor((total % 3600) / 60);
    var s = total % 60;
    function z(n) { return n < 10 ? "0" + n : String(n); }
    if (days > 0) return days + "д " + z(h) + ":" + z(m) + ":" + z(s);
    if (h > 0) return h + ":" + z(m) + ":" + z(s);
    return z(m) + ":" + z(s);
  }

  var audioCtx = null;
  var muted = false;
  try { muted = window.localStorage.getItem("chess-muted") === "1"; } catch (e) {}

  function setMuted(on) {
    muted = !!on;
    try { window.localStorage.setItem("chess-muted", muted ? "1" : "0"); } catch (e) {}
    var btn = $("#chess-mute");
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
        move: [520, 0.05, 0.04],
        capture: [220, 0.08, 0.06],
        check: [780, 0.12, 0.05],
        start: [440, 0.1, 0.05],
        end: [330, 0.18, 0.08],
        puzzle: [660, 0.12, 0.05],
        wrong: [160, 0.14, 0.07]
      };
      var cfg = map[kind] || map.move;
      o.type = kind === "capture" || kind === "wrong" ? "triangle" : "sine";
      o.frequency.value = cfg[0];
      g.gain.setValueAtTime(0.0001, now);
      g.gain.exponentialRampToValueAtTime(0.08, now + 0.01);
      g.gain.exponentialRampToValueAtTime(0.0001, now + cfg[1]);
      o.start(now);
      o.stop(now + cfg[1] + 0.02);
      if (kind === "check" || kind === "end") {
        setTimeout(function () { beep(kind === "end" ? "move" : "capture"); }, 90);
      }
    } catch (e) {}
  }

  function setFields(form, fromSq, toSq) {
    var fromEl = form.querySelector('[name="from_sq"]');
    var toEl = form.querySelector('[name="to_sq"]');
    if (fromEl) fromEl.value = fromSq || "";
    if (toEl) toEl.value = toSq || "";
  }

  var liveClient = null;

  function submitMove(form, fromSq, toSq) {
    if (!form || !fromSq || !toSq) return;
    setFields(form, fromSq, toSq);
    var app = $("#chess-app");
    if (app) app.classList.add("chess-flash");
    if (liveClient && liveClient.ws && liveClient.ws.readyState === 1) {
      liveClient.act("move", { from_sq: fromSq, to_sq: toSq });
      return;
    }
    if (typeof form.requestSubmit === "function") form.requestSubmit();
    else form.submit();
  }

  function paintSelection(board, selected, legal) {
    $all("td[data-sq]", board).forEach(function (td) {
      var sq = td.getAttribute("data-sq");
      td.classList.toggle("selected", !!selected && sq === selected);
      td.classList.toggle("hint", !!selected && legal.indexOf(sq) >= 0);
    });
  }

  function bindBoard(board) {
    var formId = board.getAttribute("data-form") || "chess-move-form";
    var form = document.getElementById(formId);
    if (!form) return;
    var canMove = board.getAttribute("data-can-move") === "1";
    var legalMap = readJsonScript(board.getAttribute("data-legal-script") || "chess-legal-map");
    var selected = (board.getAttribute("data-selected") || "").toLowerCase();
    var dragFrom = "";

    function legalFor(sq) { return legalMap[sq] || []; }

    function selectSq(sq) {
      selected = sq || "";
      board.setAttribute("data-selected", selected);
      paintSelection(board, selected, legalFor(selected));
      setFields(form, selected, "");
    }

    if (selected) paintSelection(board, selected, legalFor(selected));

    board.addEventListener("click", function (ev) {
      var td = ev.target.closest ? ev.target.closest("td[data-sq]") : null;
      if (!td || !board.contains(td)) return;
      var sq = (td.getAttribute("data-sq") || "").toLowerCase();
      if (!sq) return;
      ev.preventDefault();
      if (!canMove && board.getAttribute("data-mode") !== "puzzle") return;
      if (selected && legalFor(selected).indexOf(sq) >= 0) {
        submitMove(form, selected, sq);
        return;
      }
      if (legalMap[sq]) { selectSq(sq); return; }
      selectSq("");
    });

    if (!canMove && board.getAttribute("data-mode") !== "puzzle") {
      // Waiting for opponent: LIVE WebSocket pushes state (no page reload).
      return;
    }

    $all("td[data-sq]", board).forEach(function (td) {
      var sq = td.getAttribute("data-sq");
      var glyph = $(".chess-sq", td);
      if (!glyph) return;
      if (!legalMap[sq]) {
        glyph.setAttribute("draggable", "false");
        return;
      }
      glyph.setAttribute("draggable", "true");
      glyph.addEventListener("dragstart", function (ev) {
        dragFrom = sq;
        selectSq(sq);
        try {
          ev.dataTransfer.setData("text/plain", sq);
          ev.dataTransfer.effectAllowed = "move";
        } catch (e) {}
        td.classList.add("dragging");
      });
      glyph.addEventListener("dragend", function () {
        td.classList.remove("dragging");
        dragFrom = "";
      });
    });

    $all("td[data-sq]", board).forEach(function (td) {
      td.addEventListener("dragover", function (ev) {
        ev.preventDefault();
        td.classList.add("drag-over");
      });
      td.addEventListener("dragleave", function () { td.classList.remove("drag-over"); });
      td.addEventListener("drop", function (ev) {
        ev.preventDefault();
        td.classList.remove("drag-over");
        var from = dragFrom || (ev.dataTransfer && ev.dataTransfer.getData("text/plain")) || selected;
        var to = (td.getAttribute("data-sq") || "").toLowerCase();
        from = (from || "").toLowerCase();
        if (from && to && legalFor(from).indexOf(to) >= 0) submitMove(form, from, to);
      });
    });
  }

  function bindClocks(root) {
    if (!root || root.getAttribute("data-enabled") !== "1") return;
    var whiteMs = parseInt(root.getAttribute("data-white-ms") || "0", 10) || 0;
    var blackMs = parseInt(root.getAttribute("data-black-ms") || "0", 10) || 0;
    var turn = root.getAttribute("data-turn") || "w";
    var active = root.getAttribute("data-active") === "1";
    var whiteEl = $("[data-clock-side=w]", root);
    var blackEl = $("[data-clock-side=b]", root);
    var flagForm = document.getElementById("chess-flag-form");
    var claimed = false;
    var t0 = Date.now();

    function tick() {
      var elapsed = active ? (Date.now() - t0) : 0;
      var w = whiteMs;
      var b = blackMs;
      if (active) {
        if (turn === "w") w = Math.max(0, whiteMs - elapsed);
        else b = Math.max(0, blackMs - elapsed);
      }
      if (whiteEl) {
        whiteEl.textContent = formatClock(w);
        whiteEl.parentElement.classList.toggle("is-running", active && turn === "w");
        whiteEl.parentElement.classList.toggle("is-low", w > 0 && w < 30000);
        whiteEl.parentElement.classList.toggle("is-flag", w === 0 && active && turn === "w");
      }
      if (blackEl) {
        blackEl.textContent = formatClock(b);
        blackEl.parentElement.classList.toggle("is-running", active && turn === "b");
        blackEl.parentElement.classList.toggle("is-low", b > 0 && b < 30000);
        blackEl.parentElement.classList.toggle("is-flag", b === 0 && active && turn === "b");
      }
      var cur = turn === "w" ? w : b;
      if (active && cur === 0 && flagForm && !claimed) {
        claimed = true;
        beep("end");
        if (typeof flagForm.requestSubmit === "function") flagForm.requestSubmit();
        else flagForm.submit();
      }
    }
    tick();
    setInterval(tick, 250);
  }

  function bindHints() {
    $all(".chess-hint-toggle").forEach(function (btn) {
      btn.addEventListener("click", function () {
        var id = btn.getAttribute("data-hint-target");
        var el = id ? document.getElementById(id) : null;
        if (!el) return;
        var open = !el.classList.contains("is-open");
        el.classList.toggle("is-open", open);
        btn.textContent = open ? "Скрыть подсказку" : "Показать подсказку";
      });
    });
    $all(".chess-hint-text.is-open").forEach(function (el) {
      var btn = document.querySelector('.chess-hint-toggle[data-hint-target="' + el.id + '"]');
      if (btn) btn.textContent = "Скрыть подсказку";
    });
  }

  function paintBoardFromState(state) {
    var board = $("[data-chess-live]");
    if (!board || !state || !state.board_rows) return;
    var last = state.last_move || {};
    var checkSq = state.check_sq || "";
    var attrs = {
      "data-chess-live": board.getAttribute("data-chess-live") || "1",
      "data-can-move": state.can_move ? "1" : "0",
      "data-my-side": state.my_side || "",
      "data-form": board.getAttribute("data-form") || "chess-move-form",
      "data-legal-script": board.getAttribute("data-legal-script") || "chess-legal-map",
      "data-selected": "",
      "data-waiting": !state.can_move && state.result === "*" && !state.is_pending ? "1" : "0",
      class: board.className,
      cellspacing: "0",
      cellpadding: "0",
    };
    var html = "";
    state.board_rows.forEach(function (row) {
      html += "<tr><th class=\"chess-coord rank\">" + row[0].rank + "</th>";
      row.forEach(function (cell) {
        var cls = cell.light ? "light" : "dark";
        if (last.from_sq && cell.sq === last.from_sq) cls += " last-from";
        if (last.to_sq && cell.sq === last.to_sq) cls += " last-to";
        if (checkSq && cell.sq === checkSq) cls += " in-check";
        html +=
          '<td class="' +
          cls +
          '" data-sq="' +
          cell.sq +
          '" data-piece="' +
          (cell.piece || "") +
          '"><span class="chess-sq" title="' +
          cell.sq +
          '">' +
          (cell.glyph || "&nbsp;") +
          "</span></td>";
      });
      html += "</tr>";
    });
    html += '<tr class="chess-files-row"><th class="chess-coord"></th>';
    (state.board_files || []).forEach(function (f) {
      html += '<th class="chess-coord file">' + f + "</th>";
    });
    html += "</tr>";
    var attrHtml = Object.keys(attrs)
      .map(function (k) {
        return k + '="' + String(attrs[k]).replace(/"/g, "&quot;") + '"';
      })
      .join(" ");
    var wrap = board.parentNode;
    var tmp = document.createElement("div");
    tmp.innerHTML = "<table " + attrHtml + ">" + html + "</table>";
    var neu = tmp.firstChild;
    wrap.replaceChild(neu, board);
    wrap.classList.toggle("can-move", !!state.can_move);
    var legalScript = document.getElementById(attrs["data-legal-script"]);
    if (legalScript) legalScript.textContent = JSON.stringify(state.legal_map || {});
    var clocks = $("#chess-clocks");
    if (clocks && state.clock) {
      clocks.setAttribute("data-white-ms", String(state.clock.white_ms || 0));
      clocks.setAttribute("data-black-ms", String(state.clock.black_ms || 0));
      clocks.setAttribute("data-turn", state.turn || "w");
      clocks.setAttribute("data-active", state.clock.active ? "1" : "0");
      clocks.setAttribute("data-enabled", state.clock.enabled ? "1" : "0");
    }
    bindBoard(neu);
    if (state.result && state.result !== "*") beep("end");
    else if (state.status === "check") beep("check");
    else if (last.san && last.san.indexOf("×") >= 0) beep("capture");
    else if (last.from_sq) beep("move");
  }

  function initLive() {
    var app = $("#chess-app");
    if (!app || !window.VdLive) return;
    var wsUrl = app.getAttribute("data-ws-url");
    if (!wsUrl) return;
    var badge = app.querySelector("[data-app-live]");
    liveClient = new window.VdLive.Client({
      url: wsUrl,
      onStatus: function (st) {
        window.VdLive.setBadge(badge, st);
      },
      onState: function (payload) {
        if (!payload || !payload.ok) return;
        paintBoardFromState(payload);
        app.classList.remove("chess-flash");
      },
      onActionResult: function (action, result) {
        if (!result || !result.ok) {
          app.classList.remove("chess-flash");
          return;
        }
        if (result.state) paintBoardFromState(result.state);
      },
    });
    liveClient.connect();

    app.addEventListener("submit", function (ev) {
      var form = ev.target;
      if (!form || !liveClient || !liveClient.ws || liveClient.ws.readyState !== 1) return;
      var actionEl = form.querySelector('[name="action"]');
      var action = actionEl ? actionEl.value : "";
      if (
        [
          "resign",
          "draw_offer",
          "draw_accept",
          "draw_decline",
          "claim_flag",
          "accept_challenge",
          "decline_challenge",
          "cancel_challenge",
          "move",
        ].indexOf(action) < 0
      ) {
        return;
      }
      ev.preventDefault();
      var payload = {};
      Array.prototype.forEach.call(form.elements, function (el) {
        if (!el.name || el.disabled) return;
        if (el.type === "submit" || el.type === "button") return;
        payload[el.name] = el.value;
      });
      liveClient.act(action, payload);
    });
  }

  function init() {
    $all("[data-chess-live]").forEach(bindBoard);
    var clocks = $("#chess-clocks");
    if (clocks) bindClocks(clocks);
    bindHints();
    setMuted(muted);
    var muteBtn = $("#chess-mute");
    if (muteBtn) {
      muteBtn.addEventListener("click", function (ev) {
        ev.preventDefault();
        setMuted(!muted);
      });
    }
    var app = $("#chess-app");
    if (app) {
      var sfx = app.getAttribute("data-sfx") || "";
      if (sfx) beep(sfx);
    }
    initLive();
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
