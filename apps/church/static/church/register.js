/*
 * Registering a church (Design-System.md, "Registering a church"): shows the one-page form as four
 * steps, checks each step before the next, previews the logo and fills the review.
 * Only a convenience: the form is sent once and the server checks everything (RegisterChurchView),
 * coming back on the first step with an error. Without this script every step shows at once.
 * Loaded before auth.js, so a submit that only moves to the next step never reaches its busy button.
 */
(function () {
  "use strict";

  var root = document.querySelector("[data-au-wizard]");
  var form = document.querySelector("[data-au-wizard-form]");
  if (!root || !form) return;

  // The order of the steps (owner, 27 Nov 2026): the church first, the account last before review.
  var NAMES = { 1: "Church information", 2: "Church profile", 3: "Account information", 4: "Review and confirm" };
  var CHURCH = 1, PROFILE = 2, ACCOUNT = 3;
  var LAST = 4;
  var MAX_LOGO = 2 * 1024 * 1024;
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)");
  var $ = function (selector) { return root.querySelector(selector); };
  var named = function (name) { return form.querySelector('[name="' + name + '"]'); };
  var value = function (name) { var input = named(name); return input ? input.value.trim() : ""; };

  var current = Math.min(Math.max(parseInt(root.getAttribute("data-au-start"), 10) || 1, 1), LAST);
  var done = {};
  var furthest = current;   // any step reached once can be opened again from the stepper
  // Back from the server with a correction: every step was filled once, so all can be opened.
  if (root.hasAttribute("data-au-bound")) {
    for (var n = 1; n <= LAST; n++) done[n] = true;
    furthest = LAST;
  }

  root.classList.add("au-rg--steps");
  root.querySelectorAll("[data-au-steps-only]").forEach(function (el) { el.hidden = false; });
  var prev = $("[data-au-prev]");
  var next = $("[data-au-next]");
  var complete = $("[data-au-complete]");

  // --- Checking a step -----------------------------------------------------------------------

  function fieldOf(input) { return input.closest("[data-au-field]") || input.closest(".au-field"); }

  function clearError(input) {
    var field = fieldOf(input);
    if (!field) return;
    var mine = field.querySelector("[data-au-client-error]");
    if (mine) mine.remove();
    if (!field.querySelector(".au-errors")) {
      field.classList.remove("au-field--error");
      input.removeAttribute("aria-invalid");
      input.classList.remove("is-invalid");
    }
  }

  function setError(input, message) {
    var field = fieldOf(input);
    clearError(input);
    var box = document.createElement("div");
    box.className = "au-errors";
    box.id = input.id + "_client_error";
    box.setAttribute("data-au-client-error", "");
    var text = document.createElement("p");
    text.className = "au-error";
    text.textContent = message;
    box.appendChild(text);
    var control = field.querySelector(".au-control, .au-drop");
    control.insertAdjacentElement("afterend", box);
    field.classList.add("au-field--error");
    input.setAttribute("aria-invalid", "true");
    var described = (input.getAttribute("aria-describedby") || "").split(" ").filter(Boolean);
    if (described.indexOf(box.id) === -1) input.setAttribute("aria-describedby", described.concat(box.id).join(" "));
  }

  var emailOk = function (text) { return /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(text); };

  // Close stand-ins for the server's checks; the server has the final word.
  function validate(step) {
    var problems = [];
    function check(name, ok, message) {
      var input = named(name);
      if (!input) return;
      if (ok) clearError(input);
      else { setError(input, message); problems.push(input); }
    }
    if (step === ACCOUNT && named("password1")) {
      check("first_name", value("first_name"), "Enter your first name.");
      check("last_name", value("last_name"), "Enter your last name.");
      var email = value("email");
      check("email", emailOk(email), email ? "Enter a valid email address." : "Enter your email address.");
      var p1 = named("password1").value, p2 = named("password2").value;
      check("password1", p1.length >= 8 && !/^\d+$/.test(p1),
        !p1 ? "Enter a password." : p1.length < 8 ? "This password is too short. It must contain at least 8 characters." : "This password is entirely numeric.");
      check("password2", p1 === p2, p2 ? "The two password fields didn’t match." : "Enter the same password again.");
    }
    if (step === CHURCH) {
      check("church-name", value("church-name"), "Give the church’s name.");
      var churchEmail = value("church-email");
      check("church-email", !churchEmail || emailOk(churchEmail), "Enter a valid email address.");
    }
    if (step === PROFILE) {
      var logo = named("church-logo");
      var file = logo && logo.files && logo.files[0];
      check("church-logo", !file || file.size <= MAX_LOGO, "The logo must be 2 MB or smaller.");
    }
    if (problems.length) problems[0].focus();
    return !problems.length;
  }

  // --- Moving between steps --------------------------------------------------------------------

  function renderSteps() {
    root.querySelectorAll("[data-au-step]").forEach(function (item) {
      var number = parseInt(item.getAttribute("data-au-step"), 10);
      var finished = !!done[number] && number !== current;
      item.classList.toggle("is-active", number === current);
      item.classList.toggle("is-done", finished);
      var button = item.querySelector(".au-step__btn");
      button.disabled = number === current || number > furthest;
      if (number === current) button.setAttribute("aria-current", "step");
      else button.removeAttribute("aria-current");
    });
  }

  function go(step, back, focus) {
    var moved = step !== current;
    current = step;
    furthest = Math.max(furthest, step);
    root.querySelectorAll("[data-au-pane]").forEach(function (pane) {
      var on = parseInt(pane.getAttribute("data-au-pane"), 10) === step;
      pane.classList.toggle("is-on", on);
      pane.classList.toggle("is-back", !!back);
    });
    var percent = step * 25;
    $("[data-au-prog-fill]").style.width = percent + "%";
    $("[data-au-prog-pct]").textContent = percent + "%";
    $("[data-au-prog-bar]").setAttribute("aria-valuenow", String(percent));
    $("[data-au-prog-label]").textContent = "Step " + step + " of " + LAST + " · " + NAMES[step];
    $("[data-au-nav-step]").textContent = "Step " + step + " of " + LAST;
    prev.hidden = step === 1;
    next.hidden = step === LAST;
    complete.hidden = step !== LAST;
    if (step === LAST) renderReview();
    renderSteps();
    if (moved || focus) {
      var heading = root.querySelector('[data-au-pane="' + step + '"] .au-pane__title');
      if (heading) heading.focus({ preventScroll: true });
      window.scrollTo({ top: 0, behavior: reduced.matches ? "auto" : "smooth" });
    }
  }

  function forward() {
    if (!validate(current)) return;
    done[current] = true;
    go(current + 1, false);
  }

  next.addEventListener("click", forward);
  prev.addEventListener("click", function () { if (current > 1) go(current - 1, true); });
  root.querySelectorAll("[data-au-goto]").forEach(function (button) {
    button.addEventListener("click", function () {
      var step = parseInt(button.getAttribute("data-au-goto"), 10);
      if (step !== current && step <= furthest) go(step, step < current);
    });
  });

  // Enter in a field before the last step moves on, and the last step checks every step first.
  // Only a submit that gets through reaches auth.js, which shows the busy button.
  form.addEventListener("submit", function (event) {
    if (current < LAST) {
      event.preventDefault();
      event.stopImmediatePropagation();
      forward();
      return;
    }
    for (var step = 1; step < LAST; step++) {
      if (!validate(step)) {
        event.preventDefault();
        event.stopImmediatePropagation();
        go(step, true);
        validate(step);
        return;
      }
    }
  });

  form.addEventListener("input", function (event) {
    if (event.target.matches("input, textarea") && event.target.type !== "file") {
      var field = fieldOf(event.target);
      if (field && field.querySelector("[data-au-client-error]")) clearError(event.target);
    }
  });

  // --- The logo --------------------------------------------------------------------------------

  var logo = named("church-logo");
  var thumb = $("[data-au-logo-thumb]");
  var logoName = $("[data-au-logo-name]");
  var clear = $("[data-au-logo-clear]");
  var placeholder = thumb ? thumb.innerHTML : "";
  var hint = logoName ? logoName.textContent : "";
  var logoUrl = null;

  function showLogo() {
    if (logoUrl) URL.revokeObjectURL(logoUrl);
    logoUrl = null;
    var file = logo.files && logo.files[0];
    if (!file) {
      thumb.innerHTML = placeholder;
      logoName.textContent = hint;
      clear.hidden = true;
      return;
    }
    logoUrl = URL.createObjectURL(file);
    var image = document.createElement("img");
    image.alt = "";
    image.src = logoUrl;
    thumb.replaceChildren(image);
    logoName.textContent = file.name + " · " + (file.size / 1048576).toFixed(1) + " MB";
    clear.hidden = false;
    validate(PROFILE);
  }
  if (logo && thumb) {
    logo.addEventListener("change", showLogo);
    clear.addEventListener("click", function () {
      logo.value = "";
      showLogo();
      clearError(logo);
      logo.focus();
    });
  }

  // --- The description's count ----------------------------------------------------------------

  var about = named("church-about");
  var count = $("[data-au-count]");
  function countAbout() { if (about && count) count.textContent = String(about.value.length); }
  if (about) about.addEventListener("input", countAbout);
  countAbout();

  // --- Review ----------------------------------------------------------------------------------

  function row(list, term, text) {
    var dt = document.createElement("dt");
    var dd = document.createElement("dd");
    dt.textContent = term;
    dd.textContent = text || "Not given";
    if (!text) dd.className = "au-kv__none";
    list.appendChild(dt);
    list.appendChild(dd);
  }

  function renderReview() {
    var account = $('[data-au-review="account"]');
    if (named("password1")) {
      account.replaceChildren();
      var name = ["first_name", "middle_name", "last_name", "suffix"].map(value).filter(Boolean).join(" ");
      row(account, "Name", name);
      row(account, "Email", value("email"));
      row(account, "Password", "Set (hidden)");
    }
    var church = $('[data-au-review="church"]');
    church.replaceChildren();
    row(church, "Name", value("church-name"));
    row(church, "Address", value("church-address"));
    row(church, "Contact number", value("church-phone"));
    row(church, "Email", value("church-email"));
    $("[data-au-pv-name]").textContent = value("church-name");
    $("[data-au-pv-about]").textContent = value("church-about") || "No description yet.";
    var preview = $("[data-au-pv-logo]");
    if (logoUrl) {
      var image = document.createElement("img");
      image.alt = "";
      image.src = logoUrl;
      preview.replaceChildren(image);
    } else {
      preview.innerHTML = placeholder.replace(/width="28" height="28"/, 'width="30" height="30"');
    }
    var publicChoice = form.querySelector('[name="church-show_in_directory"][value="public"]');
    var isPublic = !publicChoice || publicChoice.checked;
    var pill = $("[data-au-pv-vis]");
    pill.classList.toggle("is-off", !isPublic);
    pill.lastElementChild.textContent = isPublic ? "Public: listed in the directory" : "Not public";
  }

  go(current, false, root.hasAttribute("data-au-bound"));
})();
