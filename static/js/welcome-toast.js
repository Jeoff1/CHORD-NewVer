/*
 * The welcome toast (templates/includes/welcome_toast.html; Design-System.md, "The welcome toast"):
 * closes itself after its time (the gold bar shows what is left), pauses while hovered or
 * focused, and closes at once with its X. Fades out, or just goes with reduced motion.
 */
(function () {
  "use strict";

  var toast = document.querySelector("[data-chord-toast]");
  if (!toast) return;
  var total = parseInt(toast.getAttribute("data-chord-toast-ms"), 10) || 5000;
  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  var left = total;
  var started = null;
  var timer = null;
  var closed = false;

  function close() {
    if (closed) return;
    closed = true;
    clearTimeout(timer);
    var region = toast.parentNode;
    var remove = function () { if (region && region.parentNode) region.parentNode.removeChild(region); };
    if (reduced) { remove(); return; }
    toast.classList.add("is-leaving");
    toast.addEventListener("animationend", remove, { once: true });
    setTimeout(remove, 600);   // in case the animation never runs
  }

  function run() {
    if (closed) return;
    started = Date.now();
    toast.classList.remove("is-paused");
    timer = setTimeout(close, left);
  }

  function pause() {
    if (closed || started === null) return;
    clearTimeout(timer);
    left = Math.max(0, left - (Date.now() - started));
    started = null;
    toast.classList.add("is-paused");
  }

  toast.style.setProperty("--chord-toast-ms", total + "ms");
  toast.querySelector("[data-chord-toast-close]").addEventListener("click", close);
  toast.addEventListener("mouseenter", pause);
  toast.addEventListener("mouseleave", function () { if (!toast.contains(document.activeElement)) run(); });
  toast.addEventListener("focusin", pause);
  toast.addEventListener("focusout", function () { if (!toast.matches(":hover")) run(); });
  document.addEventListener("keydown", function (event) { if (event.key === "Escape") close(); });
  toast.classList.add("is-shown");
  run();
})();
