/*
 * The sign-in and sign-up pages (Design-System.md, "The sign-in and sign-up pages"): show or
 * hide a password, a busy button while the form is sent, and on sign-up the password checklist
 * and whether the two passwords match.
 * Only conveniences: the server checks everything and shows its own errors. Without this script
 * the pages still work; the show buttons stay hidden.
 */
(function () {
  "use strict";

  var form = document.querySelector("[data-au-form]");
  if (!form) return;

  // Show or hide a password.
  var reveals = [];
  form.querySelectorAll("[data-au-reveal]").forEach(function (button) {
    var input = document.getElementById(button.getAttribute("data-au-reveal"));
    if (!input) return;
    var show = button.querySelector(".au-eye__show");
    var hide = button.querySelector(".au-eye__hide");
    function set(visible) {
      input.type = visible ? "text" : "password";
      button.setAttribute("aria-pressed", visible ? "true" : "false");
      button.setAttribute("aria-label", visible ? "Hide password" : "Show password");
      show.hidden = visible;
      hide.hidden = !visible;
    }
    reveals.push(set);
    button.hidden = false;
    button.addEventListener("click", function () {
      set(input.type === "password");
    });
  });

  // While the form is sent: the button shows a spinner and the busy words, and a second press
  // (or Enter) does nothing. No delay is added; the next page replaces this one.
  var submit = form.querySelector("[data-au-busy]");
  var spinner = submit && submit.querySelector(".au-spinner");
  var label = submit && submit.querySelector("[data-au-label]");
  var idleLabel = label ? label.textContent : "";
  var sending = false;

  function setBusy(busy) {
    sending = busy;
    if (!submit) return;
    submit.disabled = busy;
    if (busy) submit.setAttribute("aria-busy", "true");
    else submit.removeAttribute("aria-busy");
    if (spinner) spinner.hidden = !busy;
    if (label) label.textContent = busy ? submit.getAttribute("data-au-busy") || idleLabel : idleLabel;
  }

  form.addEventListener("submit", function (event) {
    if (sending) {
      event.preventDefault();
      return;
    }
    // Hidden again before sending, so password managers see a password field.
    reveals.forEach(function (set) { set(false); });
    setBusy(true);
  });

  // Coming back with the browser's Back button shows the page as it was left: make it usable.
  window.addEventListener("pageshow", function (event) {
    if (event.persisted) setBusy(false);
  });

  // --- Sign-up only: the checklist and the match line ------------------------

  var password = form.querySelector('input[name="password1"]');
  var confirm = form.querySelector('input[name="password2"]');
  var rules = form.querySelector("[data-au-rules]");
  var match = form.querySelector("[data-au-match]");
  if (!password) return;
  var personal = ["username", "first_name", "last_name", "email"].map(function (name) {
    return form.querySelector('input[name="' + name + '"]');
  }).filter(Boolean);

  // A close stand-in for Django's similarity check; the server has the final word.
  function similar(value) {
    var lower = value.toLowerCase();
    return personal.some(function (input) {
      var text = input.value.trim().toLowerCase();
      if (input.name === "email") text = text.split("@")[0];
      if (text.length < 3) return false;
      return lower.indexOf(text) !== -1 || (lower.length >= 3 && text.indexOf(lower) !== -1);
    });
  }

  function updateRules() {
    if (!rules) return;
    var value = password.value;
    var typed = value.length > 0;
    var met = {
      length: value.length >= 8,
      numeric: !/^\d+$/.test(value),
      similar: !similar(value),
    };
    rules.querySelectorAll("[data-au-rule]").forEach(function (item) {
      var done = typed && met[item.getAttribute("data-au-rule")];
      item.classList.toggle("au-rule--met", done);
      var state = item.querySelector("[data-au-rule-state]");
      if (state) state.textContent = typed ? (done ? " (done)" : " (not yet)") : "";
    });
  }

  var matchHint = match ? match.textContent : "";
  function updateMatch() {
    if (!match || !confirm) return;
    if (!confirm.value) {
      match.textContent = matchHint;
      match.classList.remove("au-help--ok");
      return;
    }
    var same = confirm.value === password.value;
    match.textContent = same ? "✓ Passwords match" : "Passwords don’t match yet";
    match.classList.toggle("au-help--ok", same);
  }

  form.addEventListener("input", function () {
    updateRules();
    updateMatch();
  });
  updateRules();
  updateMatch();
})();
