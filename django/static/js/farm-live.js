/**
 * Farm LIVE — WebSocket sync, no page reload when plots become ready.
 */
(function () {
  "use strict";

  var app = document.getElementById("farm-app");
  if (!app || !window.VdLive) return;

  var badge = app.querySelector("[data-app-live]");
  var stripEl = app.querySelector(".farm-strip");
  var field = document.getElementById("farm-field");
  var toast = app.querySelector("[data-farm-toast]");

  function showToast(msg, isErr) {
    if (!toast) return;
    toast.hidden = !msg;
    toast.textContent = msg || "";
    toast.classList.toggle("is-err", !!isErr);
  }

  function fmtChips(n) {
    try {
      return Number(n).toLocaleString("ru-RU");
    } catch (e) {
      return String(n);
    }
  }

  function patchStrip(strip) {
    if (!stripEl || !strip) return;
    var ready = strip.ready ? " · к сбору <b>" + strip.ready + "</b>" : "";
    var bankrupt = strip.bankrupt
      ? '<span class="farm-bankrupt"> · банкрот ~' + strip.bankrupt_days_left + " дн.</span>"
      : "";
    stripEl.innerHTML =
      "Фишки <b>" +
      (strip.chips_fmt || fmtChips(strip.chips)) +
      "</b> · ур. <b>" +
      strip.level +
      "</b> · серия <b>" +
      strip.streak +
      "</b> · грядки <b>" +
      strip.plots_unlocked +
      "</b> · лейки <b>" +
      strip.water_cans +
      "</b> · удобрения <b>" +
      strip.fertilizer +
      "</b>" +
      ready +
      bankrupt;
  }

  function plotActsHtml(pl, strip) {
    if (!strip || strip.bankrupt) return "";
    if (pl.state === "empty") {
      return (
        '<form method="post" class="farm-plant-form" data-live-act="plant">' +
        '<input type="hidden" name="action" value="plant">' +
        '<input type="hidden" name="plot_id" value="' +
        pl.id +
        '">' +
        '<select name="crop" class="inputtext"></select>' +
        '<button type="submit" class="inputsubmit">Посадить</button></form>'
      );
    }
    if (pl.state === "growing") {
      var html = "";
      if (!pl.watered) {
        html +=
          '<form method="post" class="inline" data-live-act="water">' +
          '<input type="hidden" name="action" value="water">' +
          '<input type="hidden" name="plot_id" value="' +
          pl.id +
          '">' +
          '<button type="submit" class="inputsubmit">Полить</button></form>';
      }
      if (!pl.fertilized && strip.fertilizer) {
        html +=
          '<form method="post" class="inline" data-live-act="fertilize">' +
          '<input type="hidden" name="action" value="fertilize">' +
          '<input type="hidden" name="plot_id" value="' +
          pl.id +
          '">' +
          '<button type="submit" class="inputbutton">Удобрить</button></form>';
      }
      if (strip.boosts) {
        html +=
          '<form method="post" class="inline" data-live-act="boost">' +
          '<input type="hidden" name="action" value="boost">' +
          '<input type="hidden" name="plot_id" value="' +
          pl.id +
          '">' +
          '<button type="submit" class="linkish">ускорить</button></form>';
      }
      return html;
    }
    if (pl.state === "ready") {
      return (
        '<form method="post" class="inline" data-live-act="harvest">' +
        '<input type="hidden" name="action" value="harvest">' +
        '<input type="hidden" name="plot_id" value="' +
        pl.id +
        '">' +
        '<button type="submit" class="inputsubmit farm-btn-harvest">Собрать</button></form>'
      );
    }
    if (pl.state === "withered") {
      return (
        '<form method="post" class="inline" data-live-act="clear">' +
        '<input type="hidden" name="action" value="clear">' +
        '<input type="hidden" name="plot_id" value="' +
        pl.id +
        '">' +
        '<button type="submit" class="linkish muted">очистить</button></form>'
      );
    }
    return "";
  }

  function fillCropSelects(crops) {
    if (!crops || !crops.length) return;
    app.querySelectorAll("select[name=crop]").forEach(function (sel) {
      var cur = sel.value;
      sel.innerHTML = crops
        .map(function (c) {
          return (
            '<option value="' +
            c.slug +
            '"' +
            (c.locked ? " disabled" : "") +
            ">" +
            c.title +
            " · " +
            c.cost +
            (c.locked ? " (ур." + c.need_level + ")" : "") +
            "</option>"
          );
        })
        .join("");
      if (cur) sel.value = cur;
    });
  }

  function patchPlots(plots, strip, crops) {
    if (!field || !plots) return;
    plots.forEach(function (pl) {
      var el = field.querySelector('[data-plot-id="' + pl.id + '"]');
      if (!el) return;
      el.className =
        "farm-plot state-" +
        pl.state +
        (pl.watered ? " is-watered" : "") +
        (pl.state === "ready" || (pl.state === "growing" && pl.left_sec === 0) ? " is-due" : "");
      el.setAttribute("data-state", pl.state);
      el.setAttribute("data-left", String(pl.left_sec || 0));
      el.setAttribute("data-ready-at", pl.ready_at || "");
      if (pl.crop && pl.crop.color) el.style.setProperty("--crop", pl.crop.color);
      var inner = el.querySelector(".farm-plot-inner");
      if (inner) {
        var title =
          pl.state === "empty"
            ? "пусто"
            : pl.state === "withered"
              ? "увяло"
              : pl.label || (pl.crop && pl.crop.title) || "";
        var timer =
          pl.state === "growing" || pl.state === "ready"
            ? '<span class="farm-plot-timer" data-farm-timer>' + (pl.left_sec || 0) + "</span>"
            : "";
        var hint = "";
        if (!pl.watered && pl.state === "growing") hint = '<span class="farm-plot-hint">нужен полив</span>';
        if (pl.stolen) hint += '<span class="farm-plot-hint">часть забрали</span>';
        inner.innerHTML =
          '<span class="farm-plot-idx">#' +
          (pl.idx + 1) +
          '</span><b class="farm-plot-title">' +
          title +
          "</b>" +
          timer +
          hint;
      }
      var acts = el.querySelector(".farm-plot-acts");
      if (acts) acts.innerHTML = plotActsHtml(pl, strip);
    });
    fillCropSelects(crops);
    if (window.FarmField && window.FarmField.refreshTimers) window.FarmField.refreshTimers();
  }

  function onState(payload) {
    if (!payload || !payload.ok) return;
    patchStrip(payload.strip);
    patchPlots(payload.plots, payload.strip, payload.crops);
    app.classList.add("is-live-tick");
    setTimeout(function () {
      app.classList.remove("is-live-tick");
    }, 280);
  }

  var client = new window.VdLive.Client({
    url: app.getAttribute("data-ws-url") || "/ws/farm/",
    onStatus: function (st) {
      window.VdLive.setBadge(badge, st);
    },
    onState: onState,
    onActionResult: function (action, result) {
      if (!result || !result.ok) {
        showToast((result && result.error) || "Не удалось", true);
        return;
      }
      showToast("Готово", false);
      setTimeout(function () {
        showToast("", false);
      }, 1200);
      if (result.state) onState(result.state);
    },
  });
  client.connect();

  app.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (!form || !form.getAttribute) return;
    var action =
      form.getAttribute("data-live-act") ||
      (form.querySelector('[name="action"]') && form.querySelector('[name="action"]').value);
    if (!action) return;
    if (!client.ws || client.ws.readyState !== 1) return; // HTTP fallback
    ev.preventDefault();
    var payload = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.disabled) return;
      if (el.type === "submit" || el.type === "button") return;
      payload[el.name] = el.value;
    });
    client.act(action, payload);
  });

  // When a timer hits zero, refresh over WS instead of reloading.
  window.FarmLive = {
    onDue: function () {
      client.refresh();
    },
  };
})();
