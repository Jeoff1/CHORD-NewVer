/* The signed-in sidebar (templates/includes/app_sidebar.html; dashboard redesign, 27 Nov 2026).
 *
 * It remembers how the person left it, so moving between pages never resets it:
 * - full or icon-only (the "chord_sidebar" cookie: "full" or "icons"), from 768 px up;
 * - which categories and groups are open ("chord_sidebar_open": "planning:1.songs:0...").
 * Both are cookies so the server draws the next page the same way before it shows
 * (apps/church/navigation.py, base.html): nothing opens, closes or jumps on load.
 * - where the menu was scrolled (sessionStorage "chord-sidebar-scroll"), put back by the inline
 *   script at the end of the sidebar.
 * Bootstrap does the rest: the collapsible lists, the icon-only dropdowns and, below 768 px, the
 * offcanvas panel (focus, Escape, the backdrop).
 */
(function () {
  "use strict";

  var root = document.documentElement;
  var YEAR = 60 * 60 * 24 * 365;

  function setCookie(name, value) {
    document.cookie = name + "=" + value + "; path=/; max-age=" + YEAR + "; SameSite=Lax";
  }

  function readOpen() {
    var match = document.cookie.match(/(?:^|;\s*)chord_sidebar_open=([^;]*)/);
    var found = {};
    if (match) {
      match[1].split(".").forEach(function (part) {
        var bits = part.split(":");
        if (bits.length === 2 && (bits[1] === "0" || bits[1] === "1")) found[bits[0]] = bits[1];
      });
    }
    return found;
  }

  function writeOpen(state) {
    setCookie("chord_sidebar_open", Object.keys(state).map(function (key) {
      return key + ":" + state[key];
    }).join("."));
  }

  function syncToggle(button) {
    var icons = root.classList.contains("chord-sb-icons");
    var label = icons ? "Show the full menu" : "Shrink the menu to icons";
    button.setAttribute("aria-pressed", icons ? "true" : "false");
    button.setAttribute("aria-label", label);
    button.setAttribute("title", label);
  }

  function setUp() {
    var toggle = document.querySelector("[data-chord-sidebar-toggle]");
    if (toggle) {
      syncToggle(toggle);
      toggle.addEventListener("click", function () {
        var icons = root.classList.toggle("chord-sb-icons");
        setCookie("chord_sidebar", icons ? "icons" : "full");
        syncToggle(toggle);
      });
    }

    document.querySelectorAll("[data-chord-remember]").forEach(function (panel) {
      var key = panel.getAttribute("data-chord-remember");
      function remember(open) {
        return function (event) {
          if (event.target !== panel) return;
          var state = readOpen();
          state[key] = open ? "1" : "0";
          writeOpen(state);
        };
      }
      panel.addEventListener("shown.bs.collapse", remember(true));
      panel.addEventListener("hidden.bs.collapse", remember(false));
    });

    var nav = document.getElementById("chord-sb-nav");
    if (nav) {
      var save = function () {
        try { sessionStorage.setItem("chord-sidebar-scroll", String(nav.scrollTop)); } catch (e) { /* no memory */ }
      };
      var pending = null;
      nav.addEventListener("scroll", function () {
        if (pending) return;
        pending = window.requestAnimationFrame(function () { pending = null; save(); });
      }, { passive: true });
      window.addEventListener("pagehide", save);
    }
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setUp);
  } else {
    setUp();
  }
})();
