// A new worship service's date and time (the owner, 28 Nov 2026): the form
// arrives with the chosen template's next usual day and time filled in.
// Choosing another template fills in that template's, until the person
// changes the date or time themselves; after that their choice stays.
document.addEventListener("DOMContentLoaded", function () {
  var template = document.getElementById("id_template");
  var date = document.getElementById("id_starts_at_0");
  var time = document.getElementById("id_starts_at_1");
  if (!template || !date || !time) return;
  var changedByPerson = false;
  [date, time].forEach(function (box) {
    box.addEventListener("input", function () { changedByPerson = true; });
  });
  template.addEventListener("change", function () {
    var option = template.options[template.selectedIndex];
    var next = option && option.getAttribute("data-next-start");
    if (!next || changedByPerson) return;
    var parts = next.split("T");
    date.value = parts[0];
    time.value = parts[1];
  });
});
