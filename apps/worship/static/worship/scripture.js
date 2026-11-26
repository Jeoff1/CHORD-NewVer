// The Main scripture field's suggestions (Phase 9C): an ARIA combobox for
// browsing the Bible. Clicking the empty field lists every book; picking a
// book lists its chapters, and picking a chapter its verses (with the whole
// chapter first). HTMX fills the list; this script opens and closes it,
// moves through it with the arrow keys, and picks with Enter or a click.
// The passage's text shows below as soon as the field names one: while
// typing or browsing ("live", which shows nothing for half a reference),
// and when a passage is picked ("change").
(function () {
  "use strict";

  function setUp(input) {
    if (input.dataset.scriptureReady) return;
    input.dataset.scriptureReady = "1";
    var list = document.getElementById(input.getAttribute("aria-controls"));
    var passage = document.getElementById(input.id + "-passage");
    var active = -1;
    var timer = null;

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
      list.scrollTop = 0;
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

    function preview() {
      if (!passage || !window.htmx) return;
      window.htmx.ajax("GET", passage.getAttribute("hx-get"), {
        target: passage,
        swap: "innerHTML",
        values: { scripture: input.value, live: "1" },
      });
    }

    function pick(item) {
      input.value = item.getAttribute("data-value");
      input.focus();
      if (item.hasAttribute("data-more")) {
        // A book or a chapter: list what is in it, and show the chapter.
        input.dispatchEvent(new Event("input", { bubbles: true }));
      } else {
        close();
        input.dispatchEvent(new Event("change", { bubbles: true }));
      }
    }

    list.addEventListener("htmx:afterSwap", function () {
      if (document.activeElement === input) open();
    });
    input.addEventListener("input", function () {
      clearTimeout(timer);
      timer = setTimeout(preview, 300);
    });
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
    // mousedown, not click: it comes before the input loses focus. Every
    // mousedown in the list keeps the focus, so dragging its scrollbar
    // doesn't close it.
    list.addEventListener("mousedown", function (event) {
      event.preventDefault();
      var item = event.target.closest("[role=option]");
      if (item) pick(item);
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
