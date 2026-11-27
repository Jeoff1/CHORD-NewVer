// A church profile's own script (church/homepage.html, loaded with defer).
// It turns the sections into tabs and clamps long texts behind Read more.
// Without it every section shows, one under another, with its full text.
(function () {
  "use strict";

  // --- Read more ------------------------------------------------------------
  document.querySelectorAll("[data-more]").forEach(function (button) {
    var target = document.getElementById(button.getAttribute("data-more"));
    if (!target) return;
    target.classList.add("pf-clamped");
    button.hidden = false;
    button.addEventListener("click", function () {
      var open = target.classList.toggle("pf-clamped") === false;
      button.setAttribute("aria-expanded", String(open));
      button.textContent = open ? "Read less" : "Read more";
    });
  });

  // --- Tabs -------------------------------------------------------------------
  var list = document.querySelector(".pf-tabs");
  if (!list) return;
  var tabs = Array.prototype.slice.call(list.querySelectorAll('[role="tab"]'));
  if (tabs.length < 2) return; // one section: no tabs needed, it just shows
  list.hidden = false;

  function select(tab, focus) {
    tabs.forEach(function (other) {
      var on = other === tab;
      other.setAttribute("aria-selected", String(on));
      other.tabIndex = on ? 0 : -1;
      document.getElementById(other.getAttribute("aria-controls")).hidden = !on;
    });
    if (focus) tab.focus();
  }
  tabs.forEach(function (tab, index) {
    tab.addEventListener("click", function () { select(tab); });
    tab.addEventListener("keydown", function (event) {
      var step = { ArrowRight: 1, ArrowLeft: -1 }[event.key];
      if (event.key === "Home") step = -index;
      if (event.key === "End") step = tabs.length - 1 - index;
      if (step === undefined) return;
      event.preventDefault();
      select(tabs[(index + step + tabs.length) % tabs.length], true);
    });
  });
  select(tabs[0]);
})();
