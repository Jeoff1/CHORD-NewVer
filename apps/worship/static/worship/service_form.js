// A new worship service's date and time (the owner, 28 Nov 2026): the form
// arrives with the chosen template's next usual day and time filled in.
// Choosing another template fills in that template's, until the person
// changes the date themselves; after that their date stays.
document.addEventListener("DOMContentLoaded", function () {
  var template = document.getElementById("id_template");
  var startsAt = document.getElementById("id_starts_at");
  if (!template || !startsAt) return;
  var changedByPerson = false;
  startsAt.addEventListener("input", function () { changedByPerson = true; });
  template.addEventListener("change", function () {
    var option = template.options[template.selectedIndex];
    var next = option && option.getAttribute("data-next-start");
    if (next && !changedByPerson) startsAt.value = next;
  });
});
