// The Main scripture field's suggestions (Phase 9C): an ARIA combobox.
// HTMX fills the list as the pastor types; this script opens and closes it,
// moves through it with the arrow keys, and picks with Enter or a click.
// Picking a book ("John ") keeps typing going; picking a passage fires
// "change", which loads the passage preview.
(function () {
  "use strict";

  function setUp(input) {
    if (input.dataset.scriptureReady) return;
    input.dataset.scriptureReady = "1";
    var list = document.getElementById(input.getAttribute("aria-controls"));
    var active = -1;

    function options() {
      return Array.prototype.slice.call(list.querySelectorAll("[role=option]"));
    }

    function close() {
      list.hidden = true;
      input.setAttribute("aria-expanded", "false");
      input.removeAttribute("aria-activedescendant");
      active = -1;
    }

    function open() {
      var any = options().length > 0;
      list.hidden = !any;
      input.setAttribute("aria-expanded", any ? "true" : "false");
      active = -1;
    }

    function highlight(index) {
      var items = options();
      if (!items.length) return;
      active = (index + items.length) % items.length;
      items.forEach(function (item, i) {
        item.classList.toggle("active", i === active);
        item.setAttribute("aria-selected", i === active ? "true" : "false");
      });
      input.setAttribute("aria-activedescendant", items[active].id);
      items[active].scrollIntoView({ block: "nearest" });
    }

    function pick(item) {
      var value = item.getAttribute("data-value");
      input.value = value;
      close();
      input.focus();
      if (/\s$/.test(value)) {
        // A book: ask for its chapters.
        input.dispatchEvent(new Event("input", { bubbles: true }));
      } else {
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }

    list.addEventListener("htmx:afterSwap", open);
    input.addEventListener("keydown", function (event) {
      if (list.hidden) return;
      if (event.key === "ArrowDown") {
        event.preventDefault();
        highlight(active + 1);
      } else if (event.key === "ArrowUp") {
        event.preventDefault();
        highlight(active - 1);
      } else if (event.key === "Enter" && active >= 0) {
        event.preventDefault(); // pick, don't submit the form
        pick(options()[active]);
      } else if (event.key === "Escape") {
        close();
      }
    });
    // mousedown, not click: it comes before the input loses focus.
    list.addEventListener("mousedown", function (event) {
      var item = event.target.closest("[role=option]");
      if (item) {
        event.preventDefault();
        pick(item);
      }
    });
    input.addEventListener("blur", close);
  }

  function setUpAll() {
    document.querySelectorAll("[data-scripture-input]").forEach(setUp);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", setUpAll);
  } else {
    setUpAll();
  }
})();
