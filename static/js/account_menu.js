/* The account popover and Edit Profile modal (UI/UX Phase 2, 28 Nov 2026;
 * templates/includes/account_popover.html and profile_modal.html).
 * - Popover: opens on click, closes on a click outside, Escape or choosing an item; arrow keys,
 *   Home and End move between items.
 * - Appearance: Light, Dark or Device switches the page at once (window.chordSetTheme, set by each
 *   page's head script), the thumb slides to it, and the choice saves in the background.
 * - Edit Profile: a native dialog with a live preview of the initials and full name. Saving posts in
 *   the background (Accept: application/json); on success the name and initials change everywhere
 *   on the page and a toast confirms it; on errors each field shows its message. Closing with
 *   unsaved changes asks first. The server checks everything (accounts:profile_edit).
 * Reduced motion: account.css turns the animations off; the timings here only wait for them. */
(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  function later(fn, ms) { window.setTimeout(fn, reduced ? 0 : ms); }

  function initials(first, last, fallback) {
    var letters = (first.trim().charAt(0) + last.trim().charAt(0)).toUpperCase();
    return letters || fallback;
  }
  function fullName(parts, fallback) {
    var name = parts.map(function (p) { return p.trim().replace(/\s+/g, " "); }).filter(Boolean).join(" ");
    return name || fallback;
  }

  /* ---- Popover ---- */
  function setUpMenu(root) {
    var button = root.querySelector("[data-account-button]");
    var menu = root.querySelector('[role="menu"]');
    if (!button || !menu) return null;
    var items = function () { return Array.prototype.slice.call(menu.querySelectorAll('[role="menuitem"], [role="menuitemradio"]')); };

    function open() {
      menu.hidden = false;
      menu.classList.remove("is-closing");
      button.setAttribute("aria-expanded", "true");
      var first = items()[0];
      if (first) first.focus();
    }
    function close(focusButton) {
      if (menu.hidden) return;
      button.setAttribute("aria-expanded", "false");
      menu.classList.add("is-closing");
      later(function () { menu.hidden = true; menu.classList.remove("is-closing"); }, 150);
      if (focusButton) button.focus();
    }

    button.addEventListener("click", function (event) {
      event.stopPropagation();
      if (menu.hidden) open(); else close(false);
    });
    document.addEventListener("click", function (event) {
      if (!root.contains(event.target)) close(false);
    });
    root.addEventListener("keydown", function (event) {
      if (event.key === "Escape") { close(true); return; }
      if (menu.hidden) return;
      var list = items(), at = list.indexOf(document.activeElement), next = null;
      if (event.key === "ArrowDown") next = (at + 1) % list.length;
      else if (event.key === "ArrowUp") next = (at - 1 + list.length) % list.length;
      else if (event.key === "Home") next = 0;
      else if (event.key === "End") next = list.length - 1;
      else if (event.key === "Tab") { close(false); return; }
      if (next === null) return;
      event.preventDefault();
      list[next].focus();
    });
    return { close: close, button: button };
  }

  /* ---- Appearance ---- */
  function setUpTheme(form) {
    form.addEventListener("click", function (event) {
      var choice = event.target.closest('button[name="theme"]');
      if (!choice) return;
      event.preventDefault();
      var value = choice.value;
      if (form.getAttribute("data-current") === value) return;
      form.setAttribute("data-current", value);
      form.querySelectorAll('button[name="theme"]').forEach(function (b) { b.setAttribute("aria-checked", b === choice ? "true" : "false"); });
      var root = document.documentElement;
      if (!reduced) {
        root.classList.add("chord-theme-fade");
        window.clearTimeout(form._fade);
        form._fade = window.setTimeout(function () { root.classList.remove("chord-theme-fade"); }, 320);
      }
      if (typeof window.chordSetTheme === "function") window.chordSetTheme(value);
      var data = new FormData(form);
      data.set("theme", value);
      fetch(form.action, { method: "POST", body: data, headers: { Accept: "application/json" }, credentials: "same-origin" })
        .then(function (response) { if (!response.ok) throw new Error(); })
        .catch(function () { toast("Your appearance couldn't be saved. Try again.", true); });
    });
  }

  /* ---- Toast ---- */
  function toast(text, failed) {
    var box = document.querySelector("[data-account-toast]");
    if (!box) return;
    box.classList.toggle("is-error", !!failed);
    box.querySelector("[data-toast-text]").textContent = text;
    box.classList.remove("is-leaving");
    box.hidden = false;
    window.clearTimeout(box._timer);
    box._timer = window.setTimeout(function () {
      box.classList.add("is-leaving");
      later(function () { box.hidden = true; }, 200);
    }, 3500);
  }

  /* ---- Edit Profile ---- */
  function setUpModal(menu) {
    var dialog = document.querySelector("[data-profile-modal]");
    if (!dialog || typeof dialog.showModal !== "function") return;
    var form = dialog.querySelector("[data-profile-form]");
    var save = dialog.querySelector("[data-profile-save]");
    var saveLabel = save.querySelector("[data-save-label]");
    var banner = dialog.querySelector("[data-profile-error]");
    var previewName = dialog.querySelector("[data-preview-name]");
    var previewInitials = dialog.querySelector("[data-preview-initials]");
    var fields = {};
    dialog.querySelectorAll("[data-name-part]").forEach(function (input) { fields[input.getAttribute("data-name-part")] = input; });
    var fallbackName = previewName.textContent, fallbackInitials = previewInitials.textContent;
    var saved = snapshot();

    function snapshot() { return Object.keys(fields).map(function (k) { return fields[k].value; }).join("\u0000"); }
    function dirty() { return snapshot() !== saved; }

    function clearErrors() {
      banner.hidden = true;
      dialog.querySelectorAll("[data-error-for]").forEach(function (p) { p.hidden = true; p.textContent = ""; });
      dialog.querySelectorAll("input[aria-invalid]").forEach(function (input) { input.removeAttribute("aria-invalid"); input.removeAttribute("aria-describedby"); });
    }
    function showError(name, message) {
      var p = dialog.querySelector('[data-error-for="' + name + '"]');
      var input = form.elements[name];
      if (!p || !input) { banner.textContent = message; banner.hidden = false; return; }
      p.id = p.id || "acct-error-" + name;
      p.textContent = message;
      p.hidden = false;
      input.setAttribute("aria-invalid", "true");
      input.setAttribute("aria-describedby", p.id);
    }

    function preview() {
      var name = fullName([fields.first.value, fields.middle.value, fields.last.value, fields.suffix.value], fallbackName);
      var letters = initials(fields.first.value, fields.last.value, fallbackInitials);
      previewName.textContent = name;
      if (previewInitials.textContent !== letters) {
        previewInitials.textContent = letters;
        previewInitials.classList.remove("is-changed");
        void previewInitials.offsetWidth;
        previewInitials.classList.add("is-changed");
      }
    }
    Object.keys(fields).forEach(function (k) {
      fields[k].addEventListener("input", function () {
        preview();
        if (fields[k].getAttribute("aria-invalid")) {
          fields[k].removeAttribute("aria-invalid");
          var p = dialog.querySelector('[data-error-for="' + fields[k].name + '"]');
          if (p) p.hidden = true;
        }
      });
    });

    function open() {
      if (menu) menu.close(false);
      clearErrors();
      dialog.classList.remove("is-closing");
      dialog.showModal();
      later(function () { fields.first.focus(); fields.first.select(); }, 30);
    }
    function close(force) {
      if (!dialog.open) return;
      if (!force && dirty() && !window.confirm("Discard your changes to your profile?")) return;
      if (!force) {
        // Put the fields back as they were saved.
        var values = saved.split("\u0000");
        Object.keys(fields).forEach(function (k, i) { fields[k].value = values[i]; });
        preview();
      }
      dialog.classList.add("is-closing");
      later(function () {
        dialog.classList.remove("is-closing");
        dialog.close();
        if (menu) menu.button.focus();
      }, 160);
    }

    document.querySelectorAll("[data-profile-open]").forEach(function (b) { b.addEventListener("click", open); });
    dialog.querySelectorAll("[data-profile-close]").forEach(function (b) { b.addEventListener("click", function () { close(false); }); });
    dialog.addEventListener("cancel", function (event) { event.preventDefault(); close(false); });
    dialog.addEventListener("click", function (event) { if (event.target === dialog) close(false); });

    form.addEventListener("submit", function (event) {
      event.preventDefault();
      clearErrors();
      var missing = false;
      ["first", "last"].forEach(function (k) {
        if (!fields[k].value.trim()) { showError(fields[k].name, "This field is required."); missing = true; }
      });
      if (missing) { form.querySelector('[aria-invalid="true"]').focus(); return; }

      save.classList.add("is-busy");
      save.disabled = true;
      saveLabel.textContent = "Saving…";
      fetch(form.action, {
        method: "POST",
        body: new FormData(form),
        headers: { Accept: "application/json" },
        credentials: "same-origin",
      }).then(function (response) {
        return response.json().then(function (data) { return { ok: response.ok, data: data }; });
      }).then(function (result) {
        if (!result.ok) {
          var errors = result.data.errors || {};
          Object.keys(errors).forEach(function (name) { showError(name, errors[name].join(" ")); });
          var first = form.querySelector('[aria-invalid="true"]');
          if (first) first.focus();
          return;
        }
        fallbackName = result.data.name;
        fallbackInitials = result.data.initials;
        document.querySelectorAll("[data-account-name]").forEach(function (el) { el.textContent = result.data.name; });
        document.querySelectorAll("[data-account-initials]").forEach(function (el) {
          el.textContent = result.data.initials;
          el.classList.remove("is-changed");
          void el.offsetWidth;
          el.classList.add("is-changed");
        });
        saved = snapshot();
        close(true);
        toast("Your profile was saved.");
      }).catch(function () {
        banner.textContent = "Your profile couldn't be saved. Check your connection and try again.";
        banner.hidden = false;
      }).then(function () {
        save.classList.remove("is-busy");
        save.disabled = false;
        saveLabel.textContent = "Save changes";
      });
    });
  }

  function start() {
    var menu = null;
    document.querySelectorAll("[data-account-menu]").forEach(function (root) { menu = setUpMenu(root) || menu; });
    setUpModal(menu);
    document.querySelectorAll("[data-theme-form]").forEach(setUpTheme);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
