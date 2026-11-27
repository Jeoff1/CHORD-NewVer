// The landing page's own script (church/landing.html, loaded with defer).
// Everything here is an extra: without it the church carousel still scrolls by
// swipe, trackpad and keyboard, and the phone menu still opens and closes.
(function () {
  "use strict";

  var reduced = window.matchMedia("(prefers-reduced-motion: reduce)");

  // "United in Worship": the arrow buttons. They start hidden in the HTML, show
  // only when there is more to scroll, and each is disabled at its end. No
  // automatic scrolling.
  var track = document.getElementById("lp-church-track");
  var prev = document.getElementById("lp-church-prev");
  var next = document.getElementById("lp-church-next");
  if (track && prev && next) {
    var update = function () {
      var max = track.scrollWidth - track.clientWidth;
      var scrollable = max > 2;
      prev.hidden = !scrollable;
      next.hidden = !scrollable;
      prev.disabled = track.scrollLeft <= 2;
      next.disabled = track.scrollLeft >= max - 2;
    };
    var step = function (direction) {
      var card = track.firstElementChild;
      var gap = parseFloat(getComputedStyle(track).columnGap) || 0;
      var distance = card ? card.getBoundingClientRect().width + gap : track.clientWidth;
      track.scrollBy({ left: direction * distance, behavior: reduced.matches ? "auto" : "smooth" });
    };
    prev.addEventListener("click", function () { step(-1); });
    next.addEventListener("click", function () { step(1); });
    track.addEventListener("scroll", update, { passive: true });
    window.addEventListener("resize", update);
    if (window.ResizeObserver) {
      new ResizeObserver(update).observe(track);
    }
    update();
  }

  // The phone menu closes once a link in it is chosen.
  var menu = document.querySelector(".lp-menu");
  if (menu) {
    menu.querySelectorAll("a").forEach(function (link) {
      link.addEventListener("click", function () { menu.removeAttribute("open"); });
    });
  }
})();
