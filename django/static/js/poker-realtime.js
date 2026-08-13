/**
 * Classic Poker realtime — Django Channels WebSocket client.
 * Live felt sync + soft acts (HTTP forms remain as fallback).
 */
(function () {
  "use strict";

  function $(sel, root) {
    return (root || document).querySelector(sel);
  }
  function $all(sel, root) {
    return Array.prototype.slice.call((root || document).querySelectorAll(sel));
  }

  function cardHtml(view, extra, dealI) {
    if (!view) {
      return '<span class="pk-slot"></span>';
    }
    var classes = ["pk-card"];
    if (view.red) classes.push("red");
    if (view.suit_name) classes.push(view.suit_name);
    if (extra) classes.push(extra);
    var rank = view.rank || "?";
    var suit = view.suit || "?";
    var style = dealI ? ' style="--deal:' + dealI + '"' : "";
    return (
      '<span class="' +
      classes.join(" ") +
      '"' +
      style +
      ' title="' +
      rank +
      suit +
      '">' +
      '<span class="pk-corner tl"><i>' +
      rank +
      "</i><u>" +
      suit +
      "</u></span>" +
      '<span class="pk-pip">' +
      suit +
      "</span>" +
      '<span class="pk-corner br"><i>' +
      rank +
      "</i><u>" +
      suit +
      "</u></span></span>"
    );
  }

  function cardBack(dealI) {
    var style = dealI != null ? ' style="--deal:' + dealI + '"' : "";
    return (
      '<span class="pk-card back"' +
      style +
      ' aria-hidden="true"><span class="pk-back-pattern"></span></span>'
    );
  }

  function chipStack(amount) {
    var n = Number(amount) || 0;
    if (n <= 0) return "";
    var layers = [];
    var rest = n;
    var steps = [
      [100000, "gold"],
      [25000, "black"],
      [5000, "purple"],
      [1000, "blue"],
      [100, "green"],
      [25, "red"],
      [5, "white"],
    ];
    var i = 0;
    steps.forEach(function (s) {
      var cnt = Math.min(4, Math.floor(rest / s[0]));
      for (var k = 0; k < cnt; k++) {
        layers.push('<span class="pk-chip ' + s[1] + '" style="--n:' + i + '"></span>');
        i += 1;
        rest -= s[0];
      }
    });
    if (!layers.length) {
      layers.push('<span class="pk-chip white" style="--n:0"></span>');
    }
    return '<span class="pk-chip-stack">' + layers.slice(0, 6).join("") + "</span>";
  }

  function setLive(on) {
    var badge = $("[data-poker-live]");
    if (!badge) return;
    badge.hidden = !on;
    badge.classList.toggle("is-on", !!on);
    badge.textContent = on ? "LIVE" : "…";
  }

  function toast(msg) {
    var box = $("[data-poker-toast]");
    if (!box) return;
    box.hidden = false;
    box.textContent = msg;
    window.clearTimeout(box._t);
    box._t = window.setTimeout(function () {
      box.hidden = true;
    }, 3200);
  }

  function coachTip(state) {
    var tip = $("[data-poker-coach]");
    if (!tip) return;
    if (!state.can_act || state.status !== "active") {
      tip.hidden = true;
      return;
    }
    var street = state.street || "";
    var map = {
      preflop: "Префлоп: сила руки + позиция. Не донатьте со слабыми руками.",
      flop: "Флоп: есть ли дро/пара? Считайте банк и ауты.",
      turn: "Тёрн: банки дороже — думайте о диапазонах, не только о своей руке.",
      river: "Ривер: блеф или вэлью? Размер ставки должен иметь историю.",
    };
    tip.textContent = map[street] || "Ваш ход — выбирайте размер осознанно.";
    tip.hidden = false;
  }

  function PokerSocket(opts) {
    this.url = opts.url;
    this.onMessage = opts.onMessage || function () {};
    this.onOpen = opts.onOpen || function () {};
    this.onClose = opts.onClose || function () {};
    this.ws = null;
    this.timer = null;
    this.closed = false;
    this.backoff = 700;
    this.open = false;
  }

  PokerSocket.prototype.connect = function () {
    var self = this;
    if (this.closed || !this.url) return;
    if (this.ws && (this.ws.readyState === 0 || this.ws.readyState === 1)) return;
    try {
      this.ws = new WebSocket(this.url);
    } catch (e) {
      this.schedule();
      return;
    }
    this.ws.onopen = function () {
      self.open = true;
      self.backoff = 700;
      setLive(true);
      self.onOpen();
      try {
        self.ws.send(JSON.stringify({ type: "sync" }));
      } catch (e) {}
    };
    this.ws.onmessage = function (ev) {
      var msg;
      try {
        msg = JSON.parse(ev.data);
      } catch (e) {
        return;
      }
      self.onMessage(msg);
    };
    this.ws.onclose = function () {
      self.open = false;
      setLive(false);
      self.onClose();
      self.schedule();
    };
    this.ws.onerror = function () {
      try {
        self.ws.close();
      } catch (e) {}
    };
  };

  PokerSocket.prototype.schedule = function () {
    var self = this;
    if (this.closed) return;
    clearTimeout(this.timer);
    this.timer = setTimeout(function () {
      self.connect();
    }, this.backoff);
    this.backoff = Math.min(Math.floor(self.backoff * 1.55), 12000);
  };

  PokerSocket.prototype.send = function (obj) {
    if (!this.ws || this.ws.readyState !== 1) return false;
    try {
      this.ws.send(JSON.stringify(obj));
      return true;
    } catch (e) {
      return false;
    }
  };

  PokerSocket.prototype.close = function () {
    this.closed = true;
    clearTimeout(this.timer);
    try {
      if (this.ws) this.ws.close();
    } catch (e) {}
  };

  function applyStreets(state) {
    var wrap = $("[data-poker-streets]");
    if (!wrap || !state.streets) return;
    wrap.innerHTML = state.streets
      .map(function (s) {
        return '<i class="' + (s.on ? "on" : "") + '">' + (s.label || "") + "</i>";
      })
      .join("");
  }

  function applyBanner(state) {
    var banner = $("[data-poker-banner]");
    if (!banner) return;
    banner.classList.remove("yours", "pending", "done");
    if (state.status === "pending") {
      banner.classList.add("pending");
      banner.textContent = "Ожидание принятия вызова · " + (state.sb_fmt || "") + "/" + (state.bb_fmt || "");
      return;
    }
    if (state.status === "done") {
      banner.classList.add("done");
      banner.textContent =
        (state.last_action || "Раздача завершена") +
        (state.hand_label ? " · " + state.hand_label : "");
      return;
    }
    if (state.can_act) {
      banner.classList.add("yours");
      banner.textContent =
        "Ваш ход · " +
        (state.street_label || "") +
        (state.last_action ? " · " + state.last_action : "");
    } else if (state.waiting) {
      banner.textContent =
        "Ход соперника · " +
        (state.street_label || "") +
        " · LIVE" +
        (state.last_action ? " · " + state.last_action : "");
    } else {
      banner.textContent =
        (state.street_label || "") + (state.last_action ? " · " + state.last_action : "");
    }
  }

  function applyBoard(state) {
    $all("[data-poker-board]").forEach(function (board) {
      var html = "";
      (state.board_slots || []).forEach(function (c, i) {
        html += c ? cardHtml(c, "lg", i) : '<span class="pk-slot"></span>';
      });
      board.innerHTML = html;
    });
    $all("[data-poker-pot]").forEach(function (pot) {
      pot.innerHTML = chipStack(state.pot) + " Банк <b>" + (state.pot_fmt || "0") + "</b>";
    });
    $all("[data-poker-strength]").forEach(function (el) {
      if (state.hand_strength) {
        el.hidden = false;
        el.innerHTML = "Комбинация: <b>" + state.hand_strength + "</b>";
      } else {
        el.hidden = true;
      }
    });
  }

  function applyHuSeats(state) {
    var top = $("[data-poker-seat='opp']");
    var bot = $("[data-poker-seat='me']");
    if (top) {
      top.classList.toggle("to-act", !!state.waiting && state.status === "active");
      var name = $("[data-poker-seat-name]", top);
      if (name) {
        name.innerHTML =
          (state.opp_name || "Соперник") +
          (state.opp_is_dealer ? '<span class="poker-dealer" title="Дилер">D</span>' : "");
      }
      var stack = $("[data-poker-seat-stack]", top);
      if (stack) stack.textContent = "стек " + (state.opp_stack_fmt || "0");
      var bet = $("[data-poker-seat-bet]", top);
      if (bet) {
        bet.innerHTML = state.opp_bet
          ? chipStack(state.opp_bet) + " " + (state.opp_bet_fmt || "")
          : "&nbsp;";
      }
      var hole = $("[data-poker-seat-cards]", top);
      if (hole) {
        if (state.opp_cards && state.opp_cards.length) {
          hole.innerHTML = state.opp_cards.map(function (c, i) {
            return cardHtml(c, "", i);
          }).join("");
        } else if (state.status === "active" || state.status === "done") {
          hole.innerHTML = cardBack(0) + cardBack(1);
        } else {
          hole.innerHTML = "";
        }
      }
    }
    if (bot) {
      bot.classList.toggle("to-act", !!state.can_act && state.status === "active");
      var stack2 = $("[data-poker-seat-stack]", bot);
      if (stack2) stack2.textContent = "стек " + (state.my_stack_fmt || "0");
      var bet2 = $("[data-poker-seat-bet]", bot);
      if (bet2) {
        bet2.innerHTML = state.my_bet
          ? chipStack(state.my_bet) + " " + (state.my_bet_fmt || "")
          : "&nbsp;";
      }
      var hole2 = $("[data-poker-seat-cards]", bot);
      if (hole2) {
        if (state.my_cards && state.my_cards.length) {
          hole2.innerHTML = state.my_cards
            .map(function (c, i) {
              return cardHtml(c, "mine", i);
            })
            .join("");
        }
      }
      var dealer = $("[data-poker-me-dealer]", bot);
      if (dealer) dealer.hidden = !state.i_am_dealer;
    }
  }

  function applyMultiSeats(state) {
    var ring = $("[data-poker-multi-ring]");
    if (!ring || !state.multi_seats) return;
    ring.innerHTML = state.multi_seats
      .map(function (s) {
        var cls =
          "poker-mseat a" +
          s.angle +
          (s.to_act ? " to-act" : "") +
          (s.me ? " me" : "") +
          (s.folded ? " folded" : "");
        var cards = "";
        if (s.folded) {
          cards = '<span class="poker-hand-hint">фолд</span>';
        } else if (s.cards && s.cards.length) {
          cards = s.cards.map(function (c, i) {
            return cardHtml(c, s.me ? "mine" : "", i);
          }).join("");
        } else if (s.hidden) {
          cards = cardBack(0) + cardBack(1);
        }
        return (
          '<div class="' +
          cls +
          '" data-poker-mseat="' +
          s.idx +
          '">' +
          '<div class="poker-nameplate"><b>' +
          (s.name || "Игрок") +
          "</b>" +
          (s.dealer ? '<span class="poker-dealer" title="Дилер">D</span>' : "") +
          '<div class="poker-stack-line">стек ' +
          (s.stack_fmt || "0") +
          (s.all_in ? " · олл-ин" : "") +
          "</div></div>" +
          '<div class="poker-bet-line">' +
          (s.bet ? chipStack(s.bet) + " " + (s.bet_fmt || "") : "&nbsp;") +
          "</div>" +
          '<div class="poker-hole">' +
          cards +
          "</div></div>"
        );
      })
      .join("");
  }

  function actionLabel(a, state) {
    if (a === "bet") return "Ставка " + (state.min_raise_fmt || "");
    if (a === "raise") return "Рейз до " + (state.min_raise_fmt || "");
    if (a === "call") return "Колл " + (state.to_call_fmt || "");
    if (a === "check") return "Чек";
    if (a === "fold") return "Фолд";
    if (a === "allin") return "Олл-ин " + (state.my_stack_fmt || "");
    return a;
  }

  function renderActions(root, state, sock) {
    var box = $("#poker-rt-actions", root);
    var ssr = $("[data-poker-ssr-actions]", root);
    if (!box) return;
    if (!state.can_act || state.status !== "active") {
      box.hidden = true;
      box.innerHTML = "";
      if (ssr) ssr.hidden = true;
      return;
    }
    if (ssr) ssr.hidden = true;
    box.hidden = false;
    var legal = state.legal || [];
    var html = "";
    legal.forEach(function (a) {
      var soft = a === "fold" ? " linkish muted" : "";
      html +=
        '<button type="button" class="inputsubmit' +
        soft +
        '" data-rt-play="' +
        a +
        '">' +
        actionLabel(a, state) +
        "</button> ";
    });
    if (legal.indexOf("raise") >= 0 || legal.indexOf("bet") >= 0) {
      var play = legal.indexOf("raise") >= 0 ? "raise" : "bet";
      html +=
        '<div class="poker-raise-form">' +
        '<div class="poker-raise-presets">' +
        '<button type="button" class="inputsubmit" data-raise-to="' +
        (state.min_raise_to || 0) +
        '">мин</button> ' +
        '<button type="button" class="inputsubmit" data-raise-to="' +
        (state.half_pot_to || 0) +
        '">½ банка</button> ' +
        '<button type="button" class="inputsubmit" data-raise-to="' +
        (state.pot_raise_to || 0) +
        '">банк</button> ' +
        '<button type="button" class="inputsubmit" data-raise-to="' +
        (state.max_raise_to || 0) +
        '">макс</button>' +
        "</div>" +
        '<label class="muted">Свой рейз/ставка до:</label> ' +
        '<input class="inputtext" id="poker-raise-input" size="10" value="' +
        (state.min_raise_to || 0) +
        '"> ' +
        '<button type="button" class="inputsubmit" data-rt-play="' +
        play +
        '" data-rt-use-input="1">Поставить</button>' +
        "</div>";
    }
    box.innerHTML = html;
    $all("[data-rt-play]", box).forEach(function (btn) {
      btn.addEventListener("click", function () {
        var play = btn.getAttribute("data-rt-play");
        var raiseTo = 0;
        if (btn.getAttribute("data-rt-use-input") === "1" || play === "raise" || play === "bet") {
          var inp = $("#poker-raise-input", box);
          raiseTo = inp ? parseInt(inp.value, 10) || 0 : state.min_raise_to || 0;
        }
        if (!sock.send({ type: "act", play: play, raise_to: raiseTo })) {
          toast("Нет связи — отправьте ход формой");
        }
      });
    });
    $all("[data-raise-to]", box).forEach(function (btn) {
      btn.addEventListener("click", function (ev) {
        ev.preventDefault();
        var inp = $("#poker-raise-input", box);
        if (inp) inp.value = btn.getAttribute("data-raise-to") || inp.value;
      });
    });
  }

  function applyActionLog(state) {
    var list = $("[data-poker-log]");
    if (!list || !state.actions) return;
    list.innerHTML = state.actions
      .map(function (a) {
        return (
          '<li><span class="muted">' +
          (a.street || "") +
          "</span> · " +
          (a.actor || "?") +
          ": " +
          (a.action || "") +
          (a.amount ? " " + (a.amount_fmt || a.amount) : "") +
          "</li>"
        );
      })
      .join("");
  }

  function applyTable(root, state, sock) {
    if (!state || state.type !== "table") return;
    var arena = $("#poker-arena", root);
    if (arena) {
      arena.setAttribute("data-status", state.status || "");
      arena.setAttribute("data-can-act", state.can_act ? "1" : "0");
      arena.setAttribute("data-mode", state.mode || "hu");
    }
    applyBanner(state);
    applyStreets(state);
    applyBoard(state);
    if (state.mode === "multi") {
      applyMultiSeats(state);
    } else {
      applyHuSeats(state);
    }
    renderActions(root, state, sock);
    applyActionLog(state);
    coachTip(state);
    root.dispatchEvent(new CustomEvent("poker:state", { detail: state, bubbles: true }));
  }

  function applyRoom(root, state) {
    if (!state || state.type !== "room") return;
    var count = $("[data-poker-seat-count]", root);
    if (count) count.textContent = state.filled_n + "/" + state.max_seats;
    var seats = $("[data-poker-seat-list]", root);
    if (seats && state.seats) {
      seats.innerHTML = state.seats
        .map(function (s) {
          return (
            '<div class="poker-seat-slot' +
            (s.me ? " me" : "") +
            (s.empty ? " empty" : "") +
            '">' +
            '<span class="muted">Место ' +
            (s.idx + 1) +
            "</span>" +
            "<div><b>" +
            (s.empty ? "свободно" : s.name || "Игрок") +
            "</b></div></div>"
          );
        })
        .join("");
    }
    var start = $("[data-poker-start-wrap]", root);
    if (start) start.hidden = !state.can_start;
    if (state.active_game_id && state.seat !== null && state.seat !== undefined) {
      var url = "/apps/poker/canvas?tab=table&id=" + state.active_game_id;
      if (window.location.href.indexOf("id=" + state.active_game_id) === -1) {
        window.location.href = url;
      }
    }
  }

  function wsUrlFromPath(path) {
    if (!path) return "";
    if (path.indexOf("ws") === 0) return path;
    var proto = window.location.protocol === "https:" ? "wss:" : "ws:";
    return proto + "//" + window.location.host + path;
  }

  function wireGame(root) {
    var path = root.getAttribute("data-ws-url");
    if (!path) return null;
    var sock = new PokerSocket({
      url: wsUrlFromPath(path),
      onMessage: function (msg) {
        if (msg.type === "error") {
          toast(msg.error || msg.detail || "Ошибка");
          return;
        }
        if (msg.type === "table" || msg.game_id) {
          applyTable(root, msg, sock);
        }
      },
    });
    sock.connect();
    setInterval(function () {
      sock.send({ type: "ping" });
    }, 25000);

    // Soft-intercept SSR forms while LIVE
    root.addEventListener(
      "submit",
      function (ev) {
        if (!sock.open) return;
        var form = ev.target;
        if (!form || form.tagName !== "FORM") return;
        var play = form.querySelector('[name="play"]');
        var action = form.querySelector('[name="action"]');
        if (!action || action.value !== "act" || !play) return;
        ev.preventDefault();
        var raise = form.querySelector('[name="raise_to"]');
        sock.send({
          type: "act",
          play: play.value,
          raise_to: raise ? parseInt(raise.value, 10) || 0 : 0,
        });
      },
      true
    );
    return sock;
  }

  function wireRoom(root) {
    var path = root.getAttribute("data-ws-url");
    if (!path) return null;
    var sock = new PokerSocket({
      url: wsUrlFromPath(path),
      onMessage: function (msg) {
        if (msg.type === "error") {
          toast(msg.error || msg.detail || "Ошибка");
          return;
        }
        if (msg.type === "hand_started" && msg.redirect) {
          window.location.href = msg.redirect;
          return;
        }
        if (msg.type === "room" || msg.room_id) {
          applyRoom(root, msg);
        }
      },
    });
    sock.connect();
    setInterval(function () {
      sock.send({ type: "ping" });
    }, 25000);
    var startForm = $("form[data-poker-start-form]", root);
    if (startForm) {
      startForm.addEventListener("submit", function (ev) {
        if (sock.send({ type: "start_hand" })) ev.preventDefault();
      });
    }
    return sock;
  }

  function boot() {
    var root = $("#poker-app");
    if (!root) return;
    var mode = root.getAttribute("data-poker-rt");
    var sock = null;
    if (mode === "game") sock = wireGame(root);
    if (mode === "room") sock = wireRoom(root);
    window.ClassicPokerRT = { sock: sock, PokerSocket: PokerSocket };
    root.setAttribute("data-rt-ready", sock ? "1" : "0");
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", boot);
  } else {
    boot();
  }
})();
