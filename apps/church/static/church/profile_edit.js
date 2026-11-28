/* The church page's editing tools (Church CMS, UI/UX owner, 28 Nov 2026), loaded only for the people
 * who manage the church (church/homepage.html):
 * - the camera menus on the cover and logo: choosing a picture shows it at once and uploads it (the
 *   page shows "Uploading…" while the real request runs); Remove posts straight away;
 * - the editor modal (church/includes/profile_editor.html): live preview of the name, logo and cover,
 *   "Remove" for each picture, a prompt before closing with unsaved changes, and the Save button's
 *   spinner while the form is sent; it reopens on its own when saving failed;
 * - View as visitor, which hides every editing tool until Exit preview;
 * - toasts for a picture that can't be used (profile.js times the page's own messages).
 * Nothing here decides what is saved: church:profile_edit checks everything on the server. */
(function () {
  "use strict";

  var IMAGE = /^image\/(png|jpeg|gif|webp)$/;
  var LIMITS = { logo: 2 * 1024 * 1024, banner: 5 * 1024 * 1024 };

  function problem(file, kind) {
    if (!IMAGE.test(file.type) || (kind === "banner" && file.type === "image/gif")) {
      return kind === "banner" ? "Choose a JPG, PNG or WebP image." : "Choose a PNG, JPEG, GIF or WebP image.";
    }
    if (file.size > LIMITS[kind]) {
      return (kind === "banner" ? "The banner must be 5 MB or smaller." : "The logo must be 2 MB or smaller.");
    }
    return "";
  }

  /* ---- Camera menus on the cover and the logo ---- */
  function setUpMenus() {
    document.querySelectorAll("[data-pic-menu]").forEach(function (box) {
      var toggle = box.querySelector("[data-pic-toggle]");
      var list = box.querySelector('[role="menu"]');
      if (!toggle || !list) return;
      function close() { list.hidden = true; toggle.setAttribute("aria-expanded", "false"); }
      toggle.addEventListener("click", function (event) {
        event.stopPropagation();
        var opening = list.hidden;
        document.querySelectorAll("[data-pic-menu] [role='menu']").forEach(function (other) { other.hidden = true; });
        list.hidden = !opening;
        toggle.setAttribute("aria-expanded", opening ? "true" : "false");
        if (opening) { var first = list.querySelector('[role="menuitem"]'); if (first) first.focus(); }
      });
      document.addEventListener("click", function (event) { if (!box.contains(event.target)) close(); });
      box.addEventListener("keydown", function (event) {
        if (event.key === "Escape" && !list.hidden) { close(); toggle.focus(); }
        if ((event.key === "Enter" || event.key === " ") && event.target.matches("label[role='menuitem']")) {
          event.preventDefault();
          event.target.querySelector("input[type=file]").click();
        }
      });
      box.querySelectorAll("[data-pic-input]").forEach(function (input) {
        input.addEventListener("change", function () {
          var file = input.files[0];
          if (!file) return;
          var kind = input.getAttribute("data-pic-input");
          var error = problem(file, kind);
          if (error) { toast(error, "error"); input.value = ""; return; }
          var url = URL.createObjectURL(file);
          if (kind === "banner") {
            var banner = document.querySelector(".pf-banner");
            banner.classList.add("pf-banner--image");
            banner.innerHTML = '<img class="pf-banner__img pf-fade-in" alt="" src="' + url + '">';
          } else {
            toggle.classList.remove("pf-logo--none");
            var current = toggle.querySelector("img, [data-logo-fallback]");
            var img = document.createElement("img");
            img.alt = ""; img.src = url; img.className = "pf-fade-in";
            if (current) current.replaceWith(img); else toggle.prepend(img);
          }
          close();
          box.classList.add("is-uploading");
          box.insertAdjacentHTML("beforeend", '<span class="pf-uploading" role="status"><span class="pf-spin" aria-hidden="true"></span>Uploading…</span>');
          input.form.submit();
        });
      });
    });
  }

  /* ---- The editor modal ---- */
  function setUpEditor() {
    var modalEl = document.getElementById("pf-editor");
    var form = modalEl && modalEl.querySelector("[data-editor-form]");
    if (!form || !window.bootstrap) return;
    var modal = window.bootstrap.Modal.getOrCreateInstance(modalEl);
    var dirty = false, sending = false, discarding = false;
    var discard = form.querySelector("[data-discard]");
    var imageError = form.querySelector("[data-image-error]");

    form.addEventListener("input", function (event) {
      dirty = true;
      if (event.target.name === "details-name") {
        form.querySelector("[data-prev-name]").textContent = event.target.value || " ";
        var initials = form.querySelector(".pf-prev__initials");
        if (initials) initials.textContent = (event.target.value || "?").charAt(0).toUpperCase();
      }
    });
    form.addEventListener("change", function () { dirty = true; });

    form.querySelectorAll("[data-preview]").forEach(function (input) {
      input.addEventListener("change", function () {
        var kind = input.getAttribute("data-preview"), file = input.files[0];
        if (!file) return;
        var error = problem(file, kind);
        imageError.hidden = !error; imageError.textContent = error;
        if (error) { input.value = ""; return; }
        var url = URL.createObjectURL(file);
        var holder = form.querySelector(kind === "banner" ? "[data-prev-cover]" : "[data-prev-logo]");
        var img = holder.querySelector("img");
        if (!img) {
          img = document.createElement("img"); img.alt = "";
          var initials = holder.querySelector(".pf-prev__initials"); if (initials) initials.remove();
          holder.prepend(img);
        }
        img.src = url; img.classList.remove("pf-fade-in"); void img.offsetWidth; img.classList.add("pf-fade-in");
        form.querySelector('[data-clear="' + kind + '"]').checked = false;
        var remove = form.querySelector('[data-remove="' + kind + '"]'); if (remove) remove.hidden = false;
      });
    });
    form.querySelectorAll("[data-remove]").forEach(function (button) {
      button.addEventListener("click", function () {
        var kind = button.getAttribute("data-remove");
        var holder = form.querySelector(kind === "banner" ? "[data-prev-cover]" : "[data-prev-logo]");
        var img = holder.querySelector("img"); if (img) img.remove();
        if (kind === "logo") {
          var span = document.createElement("span"); span.className = "pf-prev__initials";
          span.textContent = (form.querySelector('[name="details-name"]').value || "?").charAt(0).toUpperCase();
          holder.prepend(span);
        }
        form.querySelector('[data-preview="' + kind + '"]').value = "";
        form.querySelector('[data-clear="' + kind + '"]').checked = true;
        button.hidden = true; dirty = true;
      });
    });

    modalEl.addEventListener("hide.bs.modal", function (event) {
      if (dirty && !sending && !discarding) {
        event.preventDefault();
        discard.hidden = false;
        discard.querySelector("[data-discard-no]").focus();
      }
    });
    modalEl.addEventListener("hidden.bs.modal", function () { discarding = false; discard.hidden = true; });
    discard.querySelector("[data-discard-yes]").addEventListener("click", function () { discarding = true; dirty = false; form.reset(); modal.hide(); });
    discard.querySelector("[data-discard-no]").addEventListener("click", function () { discard.hidden = true; });

    form.addEventListener("submit", function () {
      sending = true;
      var save = form.querySelector("[data-save]");
      save.disabled = true;
      save.innerHTML = '<span class="pf-spin" aria-hidden="true"></span>Saving…';
    });

    if (modalEl.hasAttribute("data-open-on-load")) {
      dirty = true;
      modal.show();
      var invalid = form.querySelector(".is-invalid");
      if (invalid) modalEl.addEventListener("shown.bs.modal", function () { invalid.focus(); }, { once: true });
    }
  }

  /* ---- View as visitor ---- */
  function setUpPreview() {
    var start = document.querySelector("[data-visitor-preview]");
    var bar = document.querySelector("[data-preview-bar]");
    if (!start || !bar) return;
    start.addEventListener("click", function () {
      document.body.classList.add("pf-previewing");
      bar.hidden = false;
      bar.querySelector("[data-visitor-exit]").focus();
    });
    bar.querySelector("[data-visitor-exit]").addEventListener("click", function () {
      document.body.classList.remove("pf-previewing");
      bar.hidden = true;
      start.focus();
    });
  }

  /* ---- Toasts ---- */
  function toast(text, kind) {
    var region = document.querySelector(".pf-toasts");
    if (!region) { region = document.createElement("div"); region.className = "pf-toasts"; region.setAttribute("aria-live", "polite"); document.body.prepend(region); }
    var el = document.createElement("div");
    el.className = "pf-toast pf-toast--" + (kind || "success");
    el.setAttribute("role", kind === "error" ? "alert" : "status");
    el.innerHTML = '<span class="pf-toast__text"></span><button type="button" class="pf-toast__close" aria-label="Dismiss" data-toast-close>&times;</button><span class="pf-toast__bar" aria-hidden="true"></span>';
    el.querySelector(".pf-toast__text").textContent = text;
    region.appendChild(el);
    arm(el);
  }
  function arm(el) {
    var gone = function () { el.classList.add("is-leaving"); window.setTimeout(function () { el.remove(); }, 260); };
    var timer = window.setTimeout(gone, 5000);
    el.querySelector("[data-toast-close]").addEventListener("click", function () { window.clearTimeout(timer); gone(); });
  }

  function start() {
    setUpMenus();
    setUpEditor();
    setUpPreview();
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
