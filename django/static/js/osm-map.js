/* Classic OSM maps — init Leaflet boxes with data-* markers. */
(function () {
  function ready(fn) {
    if (document.readyState !== "loading") fn();
    else document.addEventListener("DOMContentLoaded", fn);
  }

  function parseMarkers(el) {
    var raw = el.getAttribute("data-markers") || "[]";
    try {
      var list = JSON.parse(raw);
      return Array.isArray(list) ? list : [];
    } catch (e) {
      return [];
    }
  }

  function initMap(el) {
    if (!window.L || el.getAttribute("data-ready")) return;
    var lat = parseFloat(el.getAttribute("data-lat"));
    var lon = parseFloat(el.getAttribute("data-lon"));
    var zoom = parseInt(el.getAttribute("data-zoom") || "14", 10);
    if (isNaN(lat) || isNaN(lon)) return;
    el.setAttribute("data-ready", "1");
    var map = L.map(el, { scrollWheelZoom: false, attributionControl: true });
    L.tileLayer("https://tile.openstreetmap.org/{z}/{x}/{y}.png", {
      maxZoom: 19,
      attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OSM</a>',
    }).addTo(map);
    var markers = parseMarkers(el);
    var bounds = [];
    if (!markers.length) {
      markers = [{ lat: lat, lon: lon, title: "" }];
    }
    markers.forEach(function (m) {
      var la = parseFloat(m.lat), lo = parseFloat(m.lon);
      if (isNaN(la) || isNaN(lo)) return;
      var marker = L.marker([la, lo]).addTo(map);
      if (m.title) {
        var html = m.url
          ? '<a href="' + m.url.replace(/"/g, "&quot;") + '">' + String(m.title) + "</a>"
          : String(m.title);
        marker.bindPopup(html);
      }
      bounds.push([la, lo]);
    });
    if (bounds.length > 1) {
      map.fitBounds(bounds, { padding: [24, 24], maxZoom: zoom || 14 });
    } else {
      map.setView([lat, lon], zoom || 15);
    }
  }

  ready(function () {
    var nodes = document.querySelectorAll(".osm-map");
    if (!nodes.length) return;
    function boot() {
      if (!window.L) {
        setTimeout(boot, 40);
        return;
      }
      for (var i = 0; i < nodes.length; i++) initMap(nodes[i]);
    }
    boot();
  });
})();
