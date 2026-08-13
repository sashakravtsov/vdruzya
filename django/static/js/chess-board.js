/* Chess canvas: click / drag moves + live clocks (classic chrome). */
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

  function setFields(form, fromSq, toSq) {
    var fromEl = form.querySelector('[name="from_sq"]');
    var toEl = form.querySelector('[name="to_sq"]');
    if (fromEl) fromEl.value = fromSq || "";
    if (toEl) toEl.value = toSq || "";
  }

  function submitMove(form, fromSq, toSq) {
    if (!form || !fromSq || !toSq) return;
    setFields(form, fromSq, toSq);
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

    function legalFor(sq) {
      return legalMap[sq] || [];
    }

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
      if (legalMap[sq]) {
        selectSq(sq);
        return;
      }
      selectSq("");
    });

    if (!canMove && board.getAttribute("data-mode") !== "puzzle") return;

    $all("td[data-sq]", board).forEach(function (td) {
      var sq = td.getAttribute("data-sq");
      var piece = td.getAttribute("data-piece") || "";
      var glyph = $(".chess-sq", td);
      if (!glyph) return;
      var mine = !!legalMap[sq] || (piece && board.getAttribute("data-my-side") &&
        ((board.getAttribute("data-my-side") === "w" && piece === piece.toUpperCase()) ||
         (board.getAttribute("data-my-side") === "b" && piece === piece.toLowerCase() && piece !== piece.toUpperCase())));
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
        if (!dragFrom && !(ev.dataTransfer && ev.dataTransfer.types)) return;
        ev.preventDefault();
        td.classList.add("drag-over");
      });
      td.addEventListener("dragleave", function () {
        td.classList.remove("drag-over");
      });
      td.addEventListener("drop", function (ev) {
        ev.preventDefault();
        td.classList.remove("drag-over");
        var from = dragFrom || (ev.dataTransfer && ev.dataTransfer.getData("text/plain")) || selected;
        var to = (td.getAttribute("data-sq") || "").toLowerCase();
        from = (from || "").toLowerCase();
        if (from && to && legalFor(from).indexOf(to) >= 0) {
          submitMove(form, from, to);
        }
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
        if (typeof flagForm.requestSubmit === "function") flagForm.requestSubmit();
        else flagForm.submit();
      }
    }
    tick();
    setInterval(tick, 250);
  }

  function init() {
    $all("[data-chess-live]").forEach(bindBoard);
    var clocks = $("#chess-clocks");
    if (clocks) bindClocks(clocks);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
