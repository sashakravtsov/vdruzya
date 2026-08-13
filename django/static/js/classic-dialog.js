/* Facebook-2006-styled modal dialog (blue title bar, classic buttons). */
(function () {
  function $(sel, root) { return (root || document).querySelector(sel); }

  function ensureRoot() {
    var root = $("#classic-dialog-root");
    if (root) return root;
    root = document.createElement("div");
    root.id = "classic-dialog-root";
    root.innerHTML =
      '<div class="fb-dialog-mask" data-dialog-close="1"></div>' +
      '<div class="fb-dialog" role="dialog" aria-modal="true">' +
      '  <div class="fb-dialog-title"><span class="fb-dialog-title-text"></span>' +
      '    <a href="#" class="fb-dialog-x" data-dialog-close="1" title="Закрыть">×</a></div>' +
      '  <div class="fb-dialog-body"></div>' +
      '  <div class="fb-dialog-footer"></div>' +
      '</div>';
    document.body.appendChild(root);
    root.addEventListener("click", function (ev) {
      if (ev.target && ev.target.getAttribute("data-dialog-close")) {
        ev.preventDefault();
        close();
      }
    });
    document.addEventListener("keydown", function (ev) {
      if (ev.key === "Escape" && root.classList.contains("is-open")) close();
    });
    return root;
  }

  function open(opts) {
    opts = opts || {};
    var root = ensureRoot();
    $(".fb-dialog-title-text", root).textContent = opts.title || "ВДрузья";
    var body = $(".fb-dialog-body", root);
    body.innerHTML = "";
    if (opts.html) body.innerHTML = opts.html;
    else body.textContent = opts.message || "";
    var foot = $(".fb-dialog-footer", root);
    foot.innerHTML = "";
    (opts.buttons || [{ label: "OK", primary: true, close: true }]).forEach(function (btn) {
      var el;
      if (btn.href) {
        el = document.createElement("a");
        el.href = btn.href;
        el.className = btn.primary ? "inputsubmit fb-dialog-btn" : "fb-dialog-btn linkish";
        el.textContent = btn.label;
      } else {
        el = document.createElement("button");
        el.type = "button";
        el.className = btn.primary ? "inputsubmit fb-dialog-btn" : "inputbutton fb-dialog-btn";
        el.textContent = btn.label;
        el.addEventListener("click", function () {
          if (typeof btn.onClick === "function") btn.onClick();
          if (btn.close !== false) close();
        });
      }
      foot.appendChild(el);
      foot.appendChild(document.createTextNode(" "));
    });
    root.classList.add("is-open");
    document.body.classList.add("fb-dialog-open");
  }

  function close() {
    var root = $("#classic-dialog-root");
    if (!root) return;
    root.classList.remove("is-open");
    document.body.classList.remove("fb-dialog-open");
  }

  function confirm(opts) {
    return new Promise(function (resolve) {
      open({
        title: opts.title || "Подтверждение",
        message: opts.message || "",
        html: opts.html,
        buttons: [
          {
            label: opts.okLabel || "OK",
            primary: true,
            onClick: function () { resolve(true); },
          },
          {
            label: opts.cancelLabel || "Отмена",
            onClick: function () { resolve(false); },
          },
        ],
      });
    });
  }

  function bindDataApi() {
    document.addEventListener("click", function (ev) {
      var t = ev.target.closest("[data-fb-dialog]");
      if (!t) return;
      ev.preventDefault();
      var title = t.getAttribute("data-fb-dialog-title") || "ВДрузья";
      var msg = t.getAttribute("data-fb-dialog-message") || "";
      var href = t.getAttribute("href");
      var formSel = t.getAttribute("data-fb-dialog-form");
      confirm({ title: title, message: msg }).then(function (ok) {
        if (!ok) return;
        if (formSel) {
          var form = document.querySelector(formSel);
          if (form) form.submit();
        } else if (href) {
          window.location = href;
        }
      });
    });
  }

  window.FBDialog = { open: open, close: close, confirm: confirm };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindDataApi);
  } else {
    bindDataApi();
  }
})();
