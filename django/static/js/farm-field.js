/* Ферма: live timers on plots/animals — due → WS refresh, no page reload */
(function () {
  function fmt(sec) {
    sec = Math.max(0, parseInt(sec, 10) || 0);
    if (sec < 60) return sec + "с";
    var m = Math.floor(sec / 60);
    var s = sec % 60;
    if (m < 60) return m + "м " + s + "с";
    var h = Math.floor(m / 60);
    m = m % 60;
    return h + "ч " + m + "м";
  }

  function refreshTimers() {
    document.querySelectorAll("[data-farm-timer]").forEach(function (el) {
      var host = el.closest("[data-left]");
      var left = host ? host.getAttribute("data-left") : el.textContent;
      el.textContent = fmt(left);
    });
  }

  function tick() {
    var nodes = document.querySelectorAll("[data-farm-timer]");
    var due = false;
    nodes.forEach(function (el) {
      var host = el.closest("[data-left], .farm-animal, .farm-plot");
      var left = host
        ? parseInt(host.getAttribute("data-left") || el.textContent, 10)
        : parseInt(el.textContent, 10);
      if (isNaN(left)) return;
      left = Math.max(0, left - 1);
      if (host) host.setAttribute("data-left", String(left));
      el.textContent = fmt(left);
      if (left === 0 && host && host.getAttribute("data-state") === "growing") {
        host.classList.add("is-due");
        due = true;
      }
      if (left === 0 && host && host.classList.contains("farm-animal")) {
        host.classList.add("is-due");
        due = true;
      }
    });
    if (due && window.FarmLive && typeof window.FarmLive.onDue === "function") {
      window.FarmLive.onDue();
    }
  }

  refreshTimers();

  var field = document.getElementById("farm-field");
  if (field) field.classList.add("is-in");

  window.setInterval(tick, 1000);
  window.FarmField = { refreshTimers: refreshTimers };
})();
