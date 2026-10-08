/* Homepage hero: board → class paper finder, and the example paper sheet. */
(function () {
  "use strict";

  function readJSON(id) {
    var el = document.getElementById(id);
    try { return el ? JSON.parse(el.textContent) : null; } catch (e) { return null; }
  }

  var boards = readJSON("ph-finder-data") || [];
  var showcase = readJSON("ph-showcase-data") || [];
  var boardSelect = document.getElementById("ph-board");
  var classSelect = document.getElementById("ph-class");
  var cta = document.querySelector("[data-ph-cta]");
  var swaps = document.querySelectorAll("[data-ph-swap]");
  var timer = null;

  function plural(n) { return n.toLocaleString("en-IN") + " paper" + (n === 1 ? "" : "s"); }

  function setSheet(values) {
    swaps.forEach(function (el) { el.classList.add("is-out"); });
    setTimeout(function () {
      swaps.forEach(function (el) {
        var key = el.getAttribute("data-ph-swap");
        if (values[key]) el.textContent = values[key];
        el.classList.remove("is-out");
      });
    }, 220);
  }

  function selectedBoard() {
    for (var i = 0; i < boards.length; i++) if (boards[i].slug === boardSelect.value) return boards[i];
    return null;
  }

  function updateCount() {
    var opt = classSelect.options[classSelect.selectedIndex];
    var n = opt ? parseInt(opt.getAttribute("data-count"), 10) : 0;
    if (cta) cta.textContent = n ? "Show " + plural(n) : "Show papers";
  }

  function fillClasses() {
    var board = selectedBoard();
    if (!board) return;
    var keep = classSelect.value;
    classSelect.innerHTML = "";
    board.classes.forEach(function (c) {
      var opt = document.createElement("option");
      opt.value = c.slug;
      opt.textContent = c.name;
      opt.setAttribute("data-count", c.count);
      if (c.slug === keep) opt.selected = true;
      classSelect.appendChild(opt);
    });
    updateCount();
  }

  function userChoice() {
    if (timer) { clearInterval(timer); timer = null; }
    var board = selectedBoard();
    var opt = classSelect.options[classSelect.selectedIndex];
    if (!board || !opt) return;
    var short = board.name.replace(/^.*\((.*)\)$/, "$1");
    setSheet({ board: short, "class": opt.textContent, subject: "All subjects" });
  }

  if (boardSelect && classSelect) {
    boardSelect.addEventListener("change", function () { fillClasses(); userChoice(); });
    classSelect.addEventListener("change", function () { updateCount(); userChoice(); });
    fillClasses();
  }

  // Until the student uses the finder, the sheet cycles through real examples.
  var reduce = window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  if (!reduce && showcase.length > 1 && swaps.length) {
    var i = 0;
    timer = setInterval(function () {
      if (document.hidden) return;
      i = (i + 1) % showcase.length;
      setSheet(showcase[i]);
    }, 3200);
  }
})();
