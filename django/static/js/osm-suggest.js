/* Nominatim suggest for classic formtable fields (data-osm-suggest). */
(function () {
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function debounce(fn, ms) {
    var t;
    return function () {
      var ctx = this, args = arguments;
      clearTimeout(t);
      t = setTimeout(function () { fn.apply(ctx, args); }, ms);
    };
  }

  function bindField(input) {
    var wrap = document.createElement("div");
    wrap.className = "osm-suggest-wrap";
    input.parentNode.insertBefore(wrap, input);
    wrap.appendChild(input);
    var box = document.createElement("div");
    box.className = "osm-suggest-box";
    box.style.display = "none";
    wrap.appendChild(box);

    var lat = document.querySelector(input.getAttribute("data-osm-lat") || "");
    var lon = document.querySelector(input.getAttribute("data-osm-lon") || "");
    var city = document.querySelector(input.getAttribute("data-osm-city") || "");
    var addr = document.querySelector(input.getAttribute("data-osm-address") || "");

    function hide() { box.style.display = "none"; box.innerHTML = ""; }

    var fetchSuggest = debounce(function () {
      var q = (input.value || "").trim();
      if (q.length < 3) { hide(); return; }
      fetch("/geo/suggest?q=" + encodeURIComponent(q), {
        credentials: "same-origin",
        headers: { Accept: "application/json" },
      })
        .then(function (r) { return r.ok ? r.json() : { results: [] }; })
        .then(function (data) {
          var rows = (data && data.results) || [];
          if (!rows.length) { hide(); return; }
          box.innerHTML = "";
          rows.forEach(function (row) {
            var a = document.createElement("a");
            a.href = "#";
            a.className = "osm-suggest-item";
            a.textContent = row.label;
            a.addEventListener("click", function (ev) {
              ev.preventDefault();
              if (lat) lat.value = row.lat;
              if (lon) lon.value = row.lon;
              var parts = (row.label || "").split(",");
              if (input.getAttribute("data-osm-fill") === "name" && parts[0]) {
                input.value = parts[0].trim();
              } else if (input.getAttribute("data-osm-fill") !== "keep") {
                input.value = row.label;
              }
              if (city && parts.length > 1) {
                city.value = parts[parts.length - 3]
                  ? parts[parts.length - 3].trim()
                  : parts[0].trim();
              }
              if (addr && parts.length > 1) {
                addr.value = parts.slice(0, Math.min(3, parts.length)).join(",").trim();
              }
              hide();
            });
            box.appendChild(a);
          });
          box.style.display = "block";
        })
        .catch(hide);
    }, 350);

    input.addEventListener("input", fetchSuggest);
    input.addEventListener("blur", function () { setTimeout(hide, 200); });
  }

  ready(function () {
    var nodes = document.querySelectorAll("[data-osm-suggest]");
    for (var i = 0; i < nodes.length; i++) bindField(nodes[i]);
  });
})();
