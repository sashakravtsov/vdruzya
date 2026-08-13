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
    // Drop modal DOM so leftover #c-* / id_body never steal wall :target
    var body = $(".fb-dialog-body", root);
    if (body) body.innerHTML = "";
    var foot = $(".fb-dialog-footer", root);
    if (foot) foot.innerHTML = "";
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

  function openCommentForm(formId) {
    if (!formId) return false;
    var form = document.getElementById(formId);
    if (!form || !form.classList.contains("wall-comment-compose")) return false;
    var scope = form.closest(".wallpost, .discuss-open, .photo-comments, .photo-modal, #content") || document;
    scope.querySelectorAll(".wall-comment-compose.is-open").forEach(function (f) {
      if (f !== form) f.classList.remove("is-open");
    });
    form.classList.add("is-open");
    var input = form.querySelector("input[name='body'], textarea[name='body']");
    if (input) {
      try { input.focus(); } catch (e) {}
    }
    if (history.replaceState) {
      try { history.replaceState(null, "", "#" + formId); } catch (e) {}
    }
    return true;
  }

  function bindDataApi() {
    document.addEventListener("click", function (ev) {
      // Wall/group comment reveal — open the exact form (not a colliding :target)
      var cOpen = ev.target.closest("[data-comment-open], a.wall-act[href^='#c-']");
      if (cOpen && !ev.metaKey && !ev.ctrlKey && !ev.shiftKey) {
        var cid = cOpen.getAttribute("data-comment-open");
        if (!cid) {
          var hrefC = cOpen.getAttribute("href") || "";
          if (hrefC.charAt(0) === "#") cid = hrefC.slice(1);
        }
        if (cid && openCommentForm(cid)) {
          ev.preventDefault();
          return;
        }
      }

      var photoLink = ev.target.closest("a[data-fb-photo-modal]");
      if (!photoLink) {
        // Auto-modal only for media thumbs, not every album permalink on the page
        photoLink = ev.target.closest(
          ".wall-media a[href], .photo-gallery a.photo-thumb[href], .news-photo-row a[href], a.photo-thumb[href]"
        );
      }
      if (photoLink && !ev.metaKey && !ev.ctrlKey && !ev.shiftKey && !ev.altKey) {
        var modalUrl = photoLink.getAttribute("data-fb-photo-modal");
        if (!modalUrl) {
          var raw = photoLink.getAttribute("href") || "";
          if (!photoLink.closest(".photo-modal-full")) {
            modalUrl = photoModalUrlFromHref(raw);
          }
        }
        if (modalUrl) {
          ev.preventDefault();
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
        var form = null;
        if (formSel) form = document.querySelector(formSel);
        if (!form) form = t.closest("form");
        if (form) form.submit();
        else if (href) window.location = href;
      });
    });

    // Deep-link #c-wall-123 on load
    if (location.hash && location.hash.indexOf("#c-") === 0) {
      openCommentForm(location.hash.slice(1));
    }
  }

  window.FBDialog = {
    open: open, close: close, confirm: confirm,
    openPhotoModal: openPhotoModal, openCommentForm: openCommentForm,
  };
  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", bindDataApi);
  } else {
    bindDataApi();
  }
})();
