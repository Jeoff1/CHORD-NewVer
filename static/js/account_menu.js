/* The account menu on public pages (templates/includes/public_account.html; 28 Nov 2026): opens
 * on click, closes on a click outside, Escape, or choosing an item; arrow keys move between items.
 * The menu slides in (landing.css); reduced motion skips the animation. */
(function () {
  "use strict";

  function setUp(root) {
    var button = root.querySelector("[data-account-button]");
    var menu = root.querySelector('[role="menu"]');
    if (!button || !menu) return;
    var items = function () { return Array.prototype.slice.call(menu.querySelectorAll('[role="menuitem"]')); };

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
      window.setTimeout(function () { menu.hidden = true; menu.classList.remove("is-closing"); }, 150);
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
      if (menu.hidden || (event.key !== "ArrowDown" && event.key !== "ArrowUp")) return;
      event.preventDefault();
      var list = items(), at = list.indexOf(document.activeElement);
      var next = event.key === "ArrowDown" ? (at + 1) % list.length : (at - 1 + list.length) % list.length;
      list[next].focus();
    });
  }

  function start() {
    document.querySelectorAll("[data-account-menu]").forEach(setUp);
  }
  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start); else start();
})();
