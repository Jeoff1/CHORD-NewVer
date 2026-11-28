// The sign-up pop-up on a public service request (occasions/includes/signup_modal.html; 28 Nov
// 2026): open it as the page loads, put the cursor in its first box, and count down "Send a new
// code" until another code may be sent.
document.addEventListener("DOMContentLoaded", function () {
  "use strict";
  var box = document.querySelector("[data-open-on-load]");
  if (!box || !window.bootstrap) return;
  var modal = window.bootstrap.Modal.getOrCreateInstance(box);
  box.addEventListener("shown.bs.modal", function () {
    var first = box.querySelector(".is-invalid, .modal-body input:not([type=hidden])");
    if (first) first.focus();
  });
  modal.show();

  var resend = box.querySelector("[data-resend-wait]");
  if (!resend) return;
  var label = resend.textContent;
  var wait = parseInt(resend.getAttribute("data-resend-wait"), 10) || 0;
  function tick() {
    if (wait <= 0) {
      resend.disabled = false;
      resend.textContent = label;
      return;
    }
    resend.disabled = true;
    resend.textContent = label + " (" + wait + " s)";
    wait -= 1;
    setTimeout(tick, 1000);
  }
  tick();
});
