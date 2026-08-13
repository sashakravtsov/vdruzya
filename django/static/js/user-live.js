/**
 * Soft per-user LIVE pings for first-party apps (chess/dating) — not Messenger.
 */
(function () {
  "use strict";
  if (!window.VdLive) return;
  var root = document.querySelector("[data-user-live]") || document.body;
  var url = (root && root.getAttribute("data-user-live")) || "/ws/live/user/";
  var toast = document.querySelector("[data-user-live-toast]");

  function show(msg) {
    if (!toast || !msg) return;
    toast.hidden = false;
    toast.textContent = msg;
    window.setTimeout(function () {
      toast.hidden = true;
    }, 4000);
  }

  var client = new window.VdLive.Client({
    url: url,
    onEvent: function (type, payload) {
      if (type === "dating_match") {
        show("Новый матч в Знакомствах");
        return;
      }
      if (type === "chess_update") {
        var gid = payload && payload.game_id;
        show(gid ? "Обновление партии #" + gid : "Ход в шахматах");
        return;
      }
      if (type === "farm_touch") {
        show("Сосед заглянул на ферму");
      }
    },
  });
  client.connect();
})();
