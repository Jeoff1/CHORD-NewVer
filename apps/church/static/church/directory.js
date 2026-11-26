// The Church Directory's own script (church/directory.html, loaded with defer
// after HTMX). HTMX fetches the results and the suggestions (the server
// marks the match); this opens and closes the suggestions, moves through them
// with the keyboard, keeps the search field in step with the results, and
// shows the placeholder cards or an error. Without it the page is a plain
// search form.
(function () {
  "use strict";

  var form = document.getElementById("dir-search");
  var input = document.getElementById("dir-q");
  var clear = document.getElementById("dir-clear");
  var sortValue = document.getElementById("dir-sort-value");
  var panel = document.getElementById("dir-suggest");
  var body = document.getElementById("dir-suggest-body");
  var area = document.getElementById("dir-area");
  if (!form || !input || !panel || !body || !area) return;

  var MIN_LENGTH = 2;
  var active = -1;
  var slowTimer = 0;

  // --- Suggestions ---------------------------------------------------------

  function options() {
    return Array.prototype.slice.call(panel.querySelectorAll('[role="option"]'));
  }
  function openPanel() {
    panel.hidden = false;
    input.setAttribute("aria-expanded", "true");
  }
  function closePanel() {
    panel.hidden = true;
    input.setAttribute("aria-expanded", "false");
    input.removeAttribute("aria-activedescendant");
    active = -1;
  }
  function setActive(index) {
    var all = options();
    all.forEach(function (option) { option.setAttribute("aria-selected", "false"); });
    if (!all.length) { active = -1; return; }
    active = (index + all.length) % all.length;
    all[active].setAttribute("aria-selected", "true");
    input.setAttribute("aria-activedescendant", all[active].id);
    all[active].scrollIntoView({ block: "nearest" });
  }

  input.addEventListener("input", function () {
    syncClear();
    if (input.value.trim().length < MIN_LENGTH) closePanel();
  });
  input.addEventListener("keydown", function (event) {
    if (event.key === "ArrowDown" && !panel.hidden) { event.preventDefault(); setActive(active + 1); }
    else if (event.key === "ArrowUp" && !panel.hidden) { event.preventDefault(); setActive(active - 1); }
    else if (event.key === "Enter" && active >= 0) { event.preventDefault(); options()[active].click(); }
    else if (event.key === "Escape" && !panel.hidden) { event.preventDefault(); closePanel(); }
  });
  document.addEventListener("pointerdown", function (event) {
    if (!panel.hidden && !form.contains(event.target)) closePanel();
  });
  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && !panel.hidden) closePanel();
  });

  // --- The field, the clear button and the sort ----------------------------

  function syncClear() {
    if (clear) clear.hidden = !input.value;
  }
  if (clear) {
    clear.addEventListener("click", function () {
      input.value = "";
      syncClear();
      closePanel();
      // A search is showing: bring back every church, without reloading.
      var showAll = document.querySelector("#dir-results [data-show-all]");
      if (showAll) showAll.click();
      input.focus();
    });
  }
  form.addEventListener("submit", closePanel);

  // --- HTMX events --------------------------------------------------------

  document.body.addEventListener("htmx:afterSettle", function (event) {
    if (event.detail.target === body) {
      if (input.value.trim().length >= MIN_LENGTH && document.activeElement === input) {
        active = -1;
        openPanel();
      } else {
        closePanel();
      }
      return;
    }
    var results = document.getElementById("dir-results");
    var swapped = event.detail.elt === results || (event.detail.target && event.detail.target.id === "dir-results");
    if (results && swapped) {
      // Keep the field and its hidden sort in step with what is showing.
      input.value = results.getAttribute("data-q") || "";
      if (sortValue) sortValue.value = results.getAttribute("data-sort") || "newest";
      syncClear();
      closePanel();
    }
  });

  // Placeholder cards only when an update takes longer than a moment, so a
  // quick answer never flickers. No delay is ever added to the answer.
  document.body.addEventListener("htmx:beforeRequest", function (event) {
    if (event.detail.target && event.detail.target.id === "dir-results") {
      clearTimeout(slowTimer);
      slowTimer = setTimeout(function () { area.classList.add("is-slow"); }, 200);
      area.setAttribute("aria-busy", "true");
    }
  });
  document.body.addEventListener("htmx:afterRequest", function (event) {
    if (event.detail.target && event.detail.target.id === "dir-results") {
      clearTimeout(slowTimer);
      area.classList.remove("is-slow");
      area.removeAttribute("aria-busy");
    }
  });

  // A failed update: say so in the results, with a way to try again.
  function showError(event) {
    var target = event.detail.target;
    if (target && target.id === "dir-suggest-body") { closePanel(); return; }
    if (!target || target.id !== "dir-results") return;
    var box = document.createElement("div");
    box.className = "dir-empty";
    box.setAttribute("role", "alert");
    var title = document.createElement("strong");
    title.textContent = "Couldn't load the churches.";
    var text = document.createElement("p");
    text.textContent = "Check your connection and try again.";
    var retry = document.createElement("button");
    retry.type = "button";
    retry.className = "lp-btn lp-btn--line";
    retry.textContent = "Try again";
    retry.addEventListener("click", function () { box.remove(); form.requestSubmit(); });
    box.append(title, text, retry);
    target.querySelectorAll(".dir-grid, .dir-empty, .dir-pager").forEach(function (el) { el.remove(); });
    target.appendChild(box);
  }
  document.body.addEventListener("htmx:responseError", showError);
  document.body.addEventListener("htmx:sendError", showError);
})();
