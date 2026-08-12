/* Classic FB chrome — SSE nav badges + inbox thread bump (no WS messenger UI). */
(function () {
  if (!window.EventSource) return;

  function $(id) { return document.getElementById(id); }

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

  function inboxBump(lastId) {
    var box = $("inbox-thread");
    if (!box) return;
    var conv = box.getAttribute("data-conv");
    var after = parseInt(box.getAttribute("data-last") || "0", 10);
    if (!conv || !lastId || lastId <= after) return;
    var url = "/inbox/" + conv + "/since?after=" + after;
    fetch(url, { credentials: "same-origin", headers: { "Accept": "application/json" } })
      .then(function (r) { return r.ok ? r.json() : null; })
      .then(function (data) {
        if (!data || !data.html) return;
        box.insertAdjacentHTML("beforeend", data.html);
        box.setAttribute("data-last", String(data.last_id || lastId));
        if (typeof data.unread_messages === "number") {
          setCount("nav-inbox", data.unread_messages, "Входящие");
        }
        try { box.scrollTop = box.scrollHeight; } catch (e) {}
      })
      .catch(function () {});
  }

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
    } catch (e) {}
  };
  es.onerror = function () {
    /* browser reconnects; after server MAX_TICKS stream ends and EventSource retries */
  };
})();
