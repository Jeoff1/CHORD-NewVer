// Date and time boxes (core/widgets/moment.html; the owner, 28 Nov 2026): a
// click anywhere in a box opens the browser's date or time picker, not only
// on its small icon. Typing still works. Loaded once, however many boxes.
(function () {
  "use strict";
  if (window.chordMomentInput) return;
  window.chordMomentInput = true;
  document.addEventListener("click", function (event) {
    var input = event.target.closest && event.target.closest(".chord-moment input");
    if (!input || input.disabled || input.readOnly || typeof input.showPicker !== "function") {
      return;
    }
    try {
      input.showPicker();
    } catch (error) {
      // Already open, or the browser refuses: the box still takes typing.
    }
  });
})();
