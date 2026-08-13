/**
 * Dating LIVE — swipe/match over WebSocket without page reload.
 */
(function () {
  "use strict";

  var app = document.getElementById("dating-app");
  if (!app || !window.VdLive) return;

  var badge = app.querySelector("[data-app-live]");
  var stripEl = app.querySelector(".dating-strip");
  var stage = document.getElementById("dating-stage");
  var toast = app.querySelector("[data-dating-toast]");

  function showToast(msg, isErr) {
    if (!toast) return;
    toast.hidden = !msg;
    toast.textContent = msg || "";
    toast.classList.toggle("is-err", !!isErr);
  }

  function patchStrip(strip) {
    if (!stripEl || !strip) return;
    var unseen = strip.unseen_likes ? " · вас лайкнули <b>" + strip.unseen_likes + "</b>" : "";
    var neu = strip.new_matches ? " · новые матчи <b>" + strip.new_matches + "</b>" : "";
    stripEl.innerHTML =
      "Серия <b>" +
      strip.streak +
      "</b> · искры <b>" +
      strip.spark_points +
      "</b> · матчи <b>" +
      strip.matches_n +
      "</b> · суперлайки сегодня <b>" +
      strip.superlikes_left +
      "</b>" +
      unseen +
      neu +
      " · анкета <b>" +
      (strip.completeness && strip.completeness.pct) +
      "%</b>";
  }

  function escapeHtml(s) {
    return String(s || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;");
  }

  function renderCard(card) {
    if (!stage) return;
    if (!card) {
      stage.innerHTML = '<p class="muted">Лента пуста — загляните позже или расширьте предпочтения в анкете.</p>';
      return;
    }
    var prompts = (card.prompts || [])
      .map(function (pr) {
        return (
          "<li><span class=\"muted\">" +
          escapeHtml(pr.label || pr.key || "") +
          "</span><br><b>" +
          escapeHtml(pr.answer || "") +
          "</b></li>"
        );
      })
      .join("");
    var photo = card.avatar
      ? '<img src="' + escapeHtml(card.avatar) + '" alt="" width="180" height="180" class="avatar">'
      : '<span class="avatar dating-avatar-fallback">' +
        escapeHtml((card.name || "?").charAt(0)) +
        "</span>";
    var csrf =
      (window.VdLive && window.VdLive.csrfFieldHtml && window.VdLive.csrfFieldHtml()) || "";
    stage.innerHTML =
      '<div class="dating-hero">' +
      '<div class="dating-hero-photo"><a href="' +
      escapeHtml(card.profile_url || "/profile/" + card.id) +
      '">' +
      photo +
      '</a><div class="dating-compat" title="' +
      escapeHtml(card.note) +
      '"><b>' +
      card.score +
      "%</b><span>совместимость</span></div></div>" +
      '<div class="dating-hero-copy"><h5 class="dating-name"><a href="' +
      escapeHtml(card.profile_url || "/profile/" + card.id) +
      '">' +
      escapeHtml(card.name) +
      "</a>" +
      (card.age ? '<span class="muted"> · ' + card.age + "</span>" : "") +
      (card.is_friend ? '<span class="dating-tag">друг</span>' : "") +
      '</h5><p class="dating-meta">' +
      escapeHtml((card.city ? card.city + " · " : "") + (card.intent || "") + " · " + (card.note || "")) +
      "</p>" +
      (card.headline ? '<p class="dating-headline">' + escapeHtml(card.headline) + "</p>" : "") +
      (card.about ? '<p class="dating-about">' + escapeHtml(card.about) + "</p>" : "") +
      (prompts ? '<ul class="dating-prompts">' + prompts + "</ul>" : "") +
      '<div class="dating-acts">' +
      '<form method="post" data-live-act="swipe" class="inline">' +
      csrf +
      '<input type="hidden" name="action" value="swipe">' +
      '<input type="hidden" name="target_id" value="' +
      card.id +
      '">' +
      '<input type="hidden" name="swipe_action" value="pass">' +
      '<button type="submit" class="inputbutton">Пропустить</button></form> ' +
      '<form method="post" data-live-act="swipe" class="inline">' +
      csrf +
      '<input type="hidden" name="action" value="swipe">' +
      '<input type="hidden" name="target_id" value="' +
      card.id +
      '">' +
      '<input type="hidden" name="swipe_action" value="like">' +
      '<button type="submit" class="inputsubmit">Лайк</button></form> ' +
      '<form method="post" data-live-act="swipe" class="inline">' +
      csrf +
      '<input type="hidden" name="action" value="swipe">' +
      '<input type="hidden" name="target_id" value="' +
      card.id +
      '">' +
      '<input type="hidden" name="swipe_action" value="super">' +
      '<button type="submit" class="inputsubmit dating-super">Суперлайк</button></form>' +
      "</div></div></div>";
    stage.classList.remove("is-in");
    void stage.offsetWidth;
    stage.classList.add("is-in");
  }

  function onState(payload, meta) {
    if (!payload || !payload.ok) return;
    patchStrip(payload.strip);
    if (app.getAttribute("data-tab") === "discover") {
      renderCard(payload.card);
    }
    if (meta && meta.event === "match") {
      showToast("Взаимная симпатия!", false);
    }
  }

  var client = new window.VdLive.Client({
    url: app.getAttribute("data-ws-url") || "/ws/dating/",
    onStatus: function (st) {
      window.VdLive.setBadge(badge, st);
    },
    onState: onState,
    onEvent: function (type, payload) {
      if (type === "match" || type === "dating_match") {
        showToast("Новый матч!", false);
        client.refresh();
      }
    },
    onActionResult: function (action, result) {
      if (!result || !result.ok) {
        showToast((result && result.error) || "Не удалось", true);
        return;
      }
      if (result.matched) {
        showToast("Взаимная симпатия с " + (result.peer_name || "") + "!", false);
      }
      if (result.state) onState(result.state);
    },
  });
  client.connect();

  app.addEventListener("submit", function (ev) {
    var form = ev.target;
    if (!form || !form.querySelector) return;
    if (window.VdLive && window.VdLive.ensureCsrf) window.VdLive.ensureCsrf(form);
    var actionEl = form.querySelector('[name="action"]');
    var action = (form.getAttribute("data-live-act") || (actionEl && actionEl.value) || "").trim();
    if (action !== "swipe") return;
    if (!client.ws || client.ws.readyState !== 1) return;
    ev.preventDefault();
    var payload = {};
    Array.prototype.forEach.call(form.elements, function (el) {
      if (!el.name || el.disabled) return;
      if (el.type === "submit" || el.type === "button") return;
      if (el.name === "csrfmiddlewaretoken") return;
      payload[el.name] = el.value;
    });
    client.act("swipe", payload);
  });
})();
