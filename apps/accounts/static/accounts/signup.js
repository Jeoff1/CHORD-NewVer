/*
 * The sign-up page (Design-System.md, "The sign-up page"): show or hide a password, tick the
 * password checklist as the person types, and say whether the two passwords match.
 * Only a convenience: the server checks every rule (AUTH_PASSWORD_VALIDATORS) and shows its own
 * errors. Without this script the page still works; the show buttons stay hidden.
 */
(function () {
  "use strict";

  var form = document.querySelector("[data-au-signup]");
  if (!form) return;

  // Show or hide a password.
  form.querySelectorAll("[data-au-reveal]").forEach(function (button) {
    var input = document.getElementById(button.getAttribute("data-au-reveal"));
    if (!input) return;
    var show = button.querySelector(".au-eye__show");
    var hide = button.querySelector(".au-eye__hide");
    button.hidden = false;
    button.addEventListener("click", function () {
      var visible = input.type === "password";
      input.type = visible ? "text" : "password";
      button.setAttribute("aria-pressed", visible ? "true" : "false");
      button.setAttribute("aria-label", visible ? "Hide password" : "Show password");
      show.hidden = visible;
      hide.hidden = !visible;
    });
  });

  var password = form.querySelector('input[name="password1"]');
  var confirm = form.querySelector('input[name="password2"]');
  var rules = form.querySelector("[data-au-rules]");
  var match = form.querySelector("[data-au-match]");
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
    if (!rules || !password) return;
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
    if (!match || !confirm || !password) return;
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
