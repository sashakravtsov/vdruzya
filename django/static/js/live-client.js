/**
 * Shared WebSocket helper for first-party canvas LIVE (farm/dating/chess/poker).
 * Not used for Messenger.
 */
(function (global) {
  "use strict";

  function LiveClient(opts) {
    this.url = opts.url || "";
    this.onState = opts.onState || function () {};
    this.onEvent = opts.onEvent || function () {};
    this.onStatus = opts.onStatus || function () {};
    this.onActionResult = opts.onActionResult || function () {};
    this.ws = null;
    this._closed = false;
    this._retry = 0;
    this._pingTimer = null;
  }

  LiveClient.prototype.connect = function () {
    if (!this.url || this._closed) return;
    var self = this;
    var proto = location.protocol === "https:" ? "wss://" : "ws://";
    var full = this.url.indexOf("ws") === 0 ? this.url : proto + location.host + this.url;
    var ws;
    try {
      ws = new WebSocket(full);
    } catch (e) {
      self.onStatus("error");
      self._scheduleReconnect();
      return;
    }
    this.ws = ws;
    this.onStatus("connecting");
    ws.onopen = function () {
      self._retry = 0;
      self.onStatus("live");
      self._pingTimer = setInterval(function () {
        self.send({ action: "ping" });
      }, 25000);
    };
    ws.onclose = function () {
      if (self._pingTimer) {
        clearInterval(self._pingTimer);
        self._pingTimer = null;
      }
      self.onStatus("offline");
      self._scheduleReconnect();
    };
    ws.onerror = function () {
      self.onStatus("error");
    };
    ws.onmessage = function (ev) {
      var data;
      try {
        data = JSON.parse(ev.data);
      } catch (e) {
        return;
      }
      if (!data || !data.type) return;
      if (data.type === "state") {
        self.onState(data.payload || {}, data);
        return;
      }
      if (data.type === "action_result") {
        self.onActionResult(data.action, data.payload || {});
        return;
      }
      if (data.type === "pong" || data.type === "hello") return;
      self.onEvent(data.type, data.payload || data);
    };
  };

  LiveClient.prototype._scheduleReconnect = function () {
    if (this._closed) return;
    var self = this;
    var wait = Math.min(15000, 800 * Math.pow(1.6, this._retry || 0));
    this._retry = (this._retry || 0) + 1;
    setTimeout(function () {
      self.connect();
    }, wait);
  };

  LiveClient.prototype.send = function (obj) {
    if (!this.ws || this.ws.readyState !== 1) return false;
    try {
      this.ws.send(JSON.stringify(obj || {}));
      return true;
    } catch (e) {
      return false;
    }
  };

  LiveClient.prototype.refresh = function () {
    return this.send({ action: "refresh" });
  };

  LiveClient.prototype.act = function (action, payload) {
    var msg = Object.assign({ action: action }, payload || {});
    return this.send(msg);
  };

  LiveClient.prototype.close = function () {
    this._closed = true;
    if (this._pingTimer) clearInterval(this._pingTimer);
    if (this.ws) {
      try {
        this.ws.close();
      } catch (e) {}
    }
  };

  function setLiveBadge(el, status) {
    if (!el) return;
    el.hidden = false;
    el.removeAttribute("hidden");
    el.setAttribute("data-live", status || "offline");
    el.textContent =
      status === "live" ? "LIVE" : status === "connecting" ? "…" : "офлайн";
    el.classList.toggle("is-live", status === "live");
    el.classList.toggle("is-on", status === "live");
  }

  function csrfToken() {
    var m = document.cookie.match(/(?:^|; )csrftoken=([^;]*)/);
    if (!m) return "";
    try {
      return decodeURIComponent(m[1]);
    } catch (e) {
      return m[1] || "";
    }
  }

  function csrfFieldHtml() {
    var t = csrfToken();
    if (!t) return "";
    return (
      '<input type="hidden" name="csrfmiddlewaretoken" value="' +
      t.replace(/"/g, "&quot;") +
      '">'
    );
  }

  /** Ensure a form has csrfmiddlewaretoken (for dynamically rebuilt LIVE forms). */
  function ensureCsrf(form) {
    if (!form || !form.querySelector) return;
    if (form.querySelector('input[name="csrfmiddlewaretoken"]')) return;
    var t = csrfToken();
    if (!t) return;
    var input = document.createElement("input");
    input.type = "hidden";
    input.name = "csrfmiddlewaretoken";
    input.value = t;
    form.insertBefore(input, form.firstChild);
  }

  global.VdLive = {
    Client: LiveClient,
    setBadge: setLiveBadge,
    csrfToken: csrfToken,
    csrfFieldHtml: csrfFieldHtml,
    ensureCsrf: ensureCsrf,
  };
})(window);
