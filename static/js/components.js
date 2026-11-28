/* Shared UI behaviour (UI/UX Phase 3, 28 Nov 2026; UI-UX-Master-Plan.md §8, Animation-Plan.md).
 * Loaded by base.html on every page that extends it. Each part is progressive: without JavaScript
 * the page still works (messages stay in the page, forms post, links open).
 * - Messages become toasts: success and info close after 5 s (hover or focus pauses; reduced motion
 *   still closes them), warnings and errors stay until dismissed; the X or Escape dismisses.
 * - Busy buttons: the button that sent a POST form shows a spinner and can't be pressed twice; it
 *   resets if the page comes back from the browser's cache or a download leaves it in place (8 s).
 * - Confirm dialog: forms or buttons with data-confirm ask first in CHORD's own dialog; htmx's
 *   hx-confirm uses the same dialog.
 * - Search: the clear button appears while the box has text.
 * - Rows with data-href open their record when clicked outside a link, button or form control.
 * Nothing here decides anything: the server checks every request. */
(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function later(fn, ms) { return window.setTimeout(fn, reduced ? 0 : ms); }

  /* ---- Toasts ---- */
  function dismiss(toast) {
    if (!toast || toast.classList.contains("is-leaving")) return;
    toast.classList.add("is-leaving");
    later(function () { toast.remove(); }, 220);
  }
  function setUpToasts() {
    var region = document.querySelector("[data-chord-msgs]");
    if (!region) return;
    region.classList.add("is-floating");
    region.querySelectorAll(".chord-msg").forEach(function (toast) {
      var close = toast.querySelector("[data-msg-close]");
      if (close) close.hidden = false;
      if (close) close.addEventListener("click", function () { dismiss(toast); });
      if (!toast.hasAttribute("data-msg-auto")) return;
      var ms = 5000, left = ms, started = Date.now(), timer = null;
      function run() { started = Date.now(); timer = window.setTimeout(function () { dismiss(toast); }, left); }
      function pause() { if (!timer) return; window.clearTimeout(timer); timer = null; left -= Date.now() - started; toast.classList.add("is-paused"); }
      function resume() { if (timer) return; toast.classList.remove("is-paused"); run(); }
      toast.addEventListener("mouseenter", pause);
      toast.addEventListener("mouseleave", resume);
      toast.addEventListener("focusin", pause);
      toast.addEventListener("focusout", resume);
      run();
    });
    document.addEventListener("keydown", function (event) {
      if (event.key !== "Escape") return;
      var last = region.querySelector(".chord-msg:last-child");
      if (last && !document.querySelector("dialog[open], .modal.show")) dismiss(last);
    });
  }

  /* ---- Confirm dialog ---- */
  var dialog = null;
  function confirmDialog(message, options) {
    options = options || {};
    return new Promise(function (resolve) {
      if (typeof HTMLDialogElement === "undefined") { resolve(window.confirm(message)); return; }
      if (!dialog) {
        dialog = document.createElement("dialog");
        dialog.className = "chord-confirm";
        dialog.setAttribute("aria-labelledby", "chord-confirm-title");
        dialog.setAttribute("aria-describedby", "chord-confirm-text");
        dialog.innerHTML =
          '<div class="chord-confirm__body"><span class="chord-confirm__icon" aria-hidden="true">' +
          '<svg class="chord-icon" width="22" height="22" viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" focusable="false"><path d="M12 2a10 10 0 1 1 0 20 10 10 0 0 1 0-20zm0 13a1.25 1.25 0 1 0 0 2.5 1.25 1.25 0 0 0 0-2.5zM12 6a1.1 1.1 0 0 0-1.1 1.2l.4 5.6a.7.7 0 0 0 1.4 0l.4-5.6A1.1 1.1 0 0 0 12 6z"/></svg>' +
          '</span><div><h2 class="chord-confirm__title" id="chord-confirm-title"></h2><p class="chord-confirm__text" id="chord-confirm-text"></p></div></div>' +
          '<div class="chord-confirm__foot"><button type="button" class="btn btn-outline-secondary" data-answer="no">Cancel</button><button type="button" class="btn" data-answer="yes"></button></div>';
        document.body.appendChild(dialog);
      }
      var danger = options.danger !== false;
      dialog.classList.toggle("is-danger", danger);
      dialog.querySelector(".chord-confirm__title").textContent = options.title || "Are you sure?";
      dialog.querySelector(".chord-confirm__text").textContent = message;
      var yes = dialog.querySelector('[data-answer="yes"]');
      var no = dialog.querySelector('[data-answer="no"]');
      yes.className = "btn " + (danger ? "btn-danger" : "btn-primary");
      yes.textContent = options.action || "Continue";
      var opener = document.activeElement;
      function finish(answer) {
        yes.onclick = no.onclick = null;
        dialog.oncancel = null;
        dialog.classList.add("is-closing");
        later(function () {
          dialog.classList.remove("is-closing");
          if (dialog.open) dialog.close();
          if (opener && opener.focus) opener.focus();
          resolve(answer);
        }, 150);
      }
      yes.onclick = function () { finish(true); };
      no.onclick = function () { finish(false); };
      dialog.oncancel = function (event) { event.preventDefault(); finish(false); };
      dialog.showModal();
      no.focus();
    });
  }
  window.chordConfirm = confirmDialog;

  function confirmOptions(el) {
    return {
      title: el.getAttribute("data-confirm-title"),
      action: el.getAttribute("data-confirm-action"),
      danger: el.getAttribute("data-confirm-danger") !== "false",
    };
  }

  /* ---- Forms: confirm, then busy ---- */
  document.addEventListener("submit", function (event) {
    var form = event.target;
    if (!(form instanceof HTMLFormElement) || event.defaultPrevented) return;
    var submitter = event.submitter || form.querySelector('[type="submit"]');
    var asking = (submitter && submitter.getAttribute("data-confirm")) ? submitter : (form.hasAttribute("data-confirm") ? form : null);
    if (asking && !form._confirmed) {
      event.preventDefault();
      confirmDialog(asking.getAttribute("data-confirm"), confirmOptions(asking)).then(function (ok) {
        if (!ok) return;
        form._confirmed = true;
        if (form.requestSubmit) form.requestSubmit(submitter && submitter.form === form ? submitter : undefined); else form.submit();
      });
      return;
    }
    form._confirmed = false;
    if ((form.getAttribute("method") || "get").toLowerCase() !== "post") return;
    if (form.hasAttribute("data-no-busy") || form.hasAttribute("hx-post") || form.target === "_blank") return;
    if (form._busy) { event.preventDefault(); return; }
    form._busy = true;
    if (submitter && submitter.classList && submitter.classList.contains("btn")) {
      submitter.classList.add("is-busy");
      submitter.setAttribute("aria-busy", "true");
    }
    window.setTimeout(function () { reset(form); }, 8000);
  });
  function reset(form) {
    form._busy = false;
    form.querySelectorAll(".is-busy").forEach(function (b) { b.classList.remove("is-busy"); b.removeAttribute("aria-busy"); });
    document.querySelectorAll('[form="' + form.id + '"].is-busy').forEach(function (b) { b.classList.remove("is-busy"); b.removeAttribute("aria-busy"); });
  }
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) document.querySelectorAll("form").forEach(reset);
  });
  /* A button with data-confirm outside a form (or a link). */
  document.addEventListener("click", function (event) {
    var link = event.target.closest("a[data-confirm]");
    if (!link || link._confirmed) return;
    event.preventDefault();
    confirmDialog(link.getAttribute("data-confirm"), confirmOptions(link)).then(function (ok) {
      if (ok) window.location.href = link.href;
    });
  });
  /* htmx's hx-confirm, in the same dialog. */
  document.addEventListener("htmx:confirm", function (event) {
    if (!event.detail || !event.detail.question) return;
    event.preventDefault();
    confirmDialog(event.detail.question, confirmOptions(event.detail.elt || document.body)).then(function (ok) {
      if (ok) event.detail.issueRequest(true);
    });
  });

  /* ---- Search clear button ---- */
  function setUpSearch(root) {
    (root || document).querySelectorAll("[data-chord-search]").forEach(function (box) {
      if (box._ready) return;
      box._ready = true;
      var input = box.querySelector('input[type="search"]');
      var clear = box.querySelector("[data-search-clear]");
      if (!input || !clear) return;
      function sync() { clear.hidden = !input.value; }
      input.addEventListener("input", sync);
      if (clear.tagName === "BUTTON") {
        clear.addEventListener("click", function () { input.value = ""; sync(); input.focus(); if (box.hasAttribute("data-submit-on-clear")) input.form.submit(); });
      }
      sync();
    });
  }

  /* ---- The header bell's popover (UI/UX Phase 9) ---- */
  function setUpBell() {
    var root = document.querySelector("[data-chord-bell]");
    if (!root || !window.fetch || !window.DOMParser) return;
    var button = root.querySelector("[data-bell-button]");
    var pop = root.querySelector(".chord-bell__pop");
    var body = root.querySelector("[data-bell-body]");
    var loaded = false;
    function failed() {
      body.innerHTML = "";
      var note = document.createElement("p");
      note.className = "chord-bell__loading";
      note.textContent = "Notifications couldn't be loaded. ";
      var link = document.createElement("a");
      link.href = button.href;
      link.textContent = "Open the page";
      note.appendChild(link);
      body.appendChild(note);
    }
    function open() {
      pop.hidden = false;
      pop.classList.remove("is-closing");
      button.setAttribute("aria-expanded", "true");
      if (loaded) return;
      fetch(button.href, { credentials: "same-origin", headers: { Accept: "text/html" } })
        .then(function (response) { if (!response.ok) throw new Error("status"); return response.text(); })
        .then(function (html) {
          var list = new DOMParser().parseFromString(html, "text/html").querySelector("[data-notif-list]");
          if (!list) throw new Error("list");
          Array.prototype.slice.call(list.children, 8).forEach(function (extra) { extra.remove(); });
          body.innerHTML = "";
          body.appendChild(document.importNode(list, true));
          loaded = true;
        })
        .catch(failed);
    }
    function close(focus) {
      if (pop.hidden) return;
      button.setAttribute("aria-expanded", "false");
      pop.classList.add("is-closing");
      later(function () { pop.hidden = true; pop.classList.remove("is-closing"); }, 150);
      if (focus) button.focus();
    }
    button.addEventListener("click", function (event) {
      if (event.ctrlKey || event.metaKey || event.shiftKey) return;
      event.preventDefault();
      if (pop.hidden) open(); else close(false);
    });
    document.addEventListener("click", function (event) { if (!root.contains(event.target)) close(false); });
    root.addEventListener("keydown", function (event) { if (event.key === "Escape") close(true); });
  }

  /* ---- Clickable rows ---- */
  document.addEventListener("click", function (event) {
    var row = event.target.closest("tr[data-href]");
    if (!row || event.target.closest("a, button, input, select, textarea, label, form, summary")) return;
    if (window.getSelection && String(window.getSelection())) return;
    if (event.ctrlKey || event.metaKey) { window.open(row.getAttribute("data-href"), "_blank"); return; }
    window.location.href = row.getAttribute("data-href");
  });

  /* ---- Dashboard figures count up once per browser session (UI/UX Phase 11) ---- */
  function countUp() {
    var values = document.querySelectorAll(".chord-kpi__value");
    if (!values.length || reduced) return;
    try { if (sessionStorage.getItem("chord-kpi-counted")) return; sessionStorage.setItem("chord-kpi-counted", "1"); } catch (e) { return; }
    values.forEach(function (el) {
      var node = el.firstChild;
      if (!node || node.nodeType !== 3) return;
      var target = parseInt(node.nodeValue, 10);
      if (!(target > 1) || String(target) !== node.nodeValue.trim()) return;
      var began = null;
      function step(now) {
        if (began === null) began = now;
        var t = Math.min(1, (now - began) / 600);
        node.nodeValue = String(Math.round(target * (1 - Math.pow(1 - t, 3))));
        if (t < 1) window.requestAnimationFrame(step); else node.nodeValue = String(target);
      }
      window.requestAnimationFrame(step);
    });
  }

  function start() {
    setUpToasts();
    setUpSearch();
    setUpBell();
    countUp();
  }
  document.addEventListener("htmx:afterSwap", function (event) { setUpSearch(event.target); });
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
