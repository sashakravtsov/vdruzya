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

  function setWide(root, wide) {
    var dlg = $(".fb-dialog", root);
    dlg.className = "fb-dialog";
    if (wide === "photo") dlg.classList.add("fb-dialog-photo");
    else if (wide) dlg.classList.add("fb-dialog-wide");
  }

  function open(opts) {
    opts = opts || {};
    var root = ensureRoot();
    setWide(root, opts.wide);
    $(".fb-dialog-title-text", root).textContent = opts.title || "ВДрузья";
    var body = $(".fb-dialog-body", root);
    body.innerHTML = "";
    if (opts.html) body.innerHTML = opts.html;
    else body.textContent = opts.message || "";
    var foot = $(".fb-dialog-footer", root);
    foot.innerHTML = "";
    var hideFoot = opts.hideFooter;
    foot.style.display = hideFoot ? "none" : "";
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
    setWide(root, null);
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

  function photoModalUrlFromHref(href) {
    if (!href) return null;
    var m = String(href).match(/^(\/albums\/\d+\/photos\/\d+)\/?(?:[?#].*)?$/);
    return m ? m[1] + "/modal" : null;
  }

  function openPhotoModal(url) {
    fetch(url, {
      credentials: "same-origin",
      headers: { "X-Requested-With": "XMLHttpRequest", "Accept": "text/html" },
    })
      .then(function (r) {
        if (!r.ok) throw new Error("photo modal");
        return r.text();
      })
      .then(function (html) {
        open({
          title: "Фотография",
          html: html,
          wide: "photo",
          buttons: [{ label: "Закрыть", primary: true, close: true }],
        });
      })
      .catch(function () {
        window.location = url.replace(/\/modal\/?$/, "");
      });
  }

  function bindDataApi() {
    document.addEventListener("click", function (ev) {
      var photoLink = ev.target.closest("a[data-fb-photo-modal], a[href]");
      if (photoLink && !ev.metaKey && !ev.ctrlKey && !ev.shiftKey && !ev.altKey) {
        var modalUrl = photoLink.getAttribute("data-fb-photo-modal");
        if (!modalUrl) {
          // Auto-open album photo pages in 2006 dialog (wall / gallery thumbs).
          var raw = photoLink.getAttribute("href") || "";
          if (photoLink.closest(".photo-modal-full")) {
            /* keep full-page link inside modal */
          } else {
            modalUrl = photoModalUrlFromHref(raw);
          }
        }
        if (modalUrl) {
          ev.preventDefault();
          if (photoLink.closest("#classic-dialog-root") && photoLink.getAttribute("data-fb-photo-modal")) {
            openPhotoModal(modalUrl);
            return;
          }
          openPhotoModal(modalUrl);
          return;
        }
      }

      var t = ev.target.closest("[data-fb-dialog]");
      if (!t) return;
      ev.preventDefault();
      var title = t.getAttribute("data-fb-dialog-title") || "ВДрузья";
      var msg = t.getAttribute("data-fb-dialog-message") || "";
      var html = t.getAttribute("data-fb-dialog-html") || "";
      var href = t.getAttribute("href");
      var formSel = t.getAttribute("data-fb-dialog-form");
      confirm({ title: title, message: msg, html: html || undefined }).then(function (ok) {
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

  window.FBDialog = { open: open, close: close, confirm: confirm, openPhotoModal: openPhotoModal };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindDataApi);
  } else {
    bindDataApi();
  }
})();
