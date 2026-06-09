/* Eval Workbench — client behaviors: theme toggle + step-rail scroll-spy.
   No framework; plain listeners robust to Dash's render timing. */
(function () {
  "use strict";

  /* ── Theme: persist light/dark on <html data-theme>, default = system. ──── */
  var KEY = "wb-theme";
  try {
    var saved = localStorage.getItem(KEY);
    if (saved === "light" || saved === "dark") {
      document.documentElement.setAttribute("data-theme", saved);
    }
  } catch (e) { /* localStorage blocked — fall back to system preference */ }

  // Note: toggling is handled by a Dash clientside callback (app.py) so the
  // chosen theme can be shared with server-side Plotly figures via a Store.
  // This file only applies the *initial* theme (above) to avoid a flash.

  /* ── Scroll-spy: highlight the rail step whose section is in view. ──────── */
  function initSpy(attempt) {
    var sections = document.querySelectorAll(".wb-section[id]");
    var links = document.querySelectorAll(".wb-rail__step[data-step]");
    if (!sections.length || !links.length) {
      if ((attempt || 0) < 25) {
        return void requestAnimationFrame(function () { initSpy((attempt || 0) + 1); });
      }
      return; // give up quietly
    }

    var byId = {};
    links.forEach(function (l) { byId[l.getAttribute("data-step")] = l; });

    function setActive(id) {
      links.forEach(function (l) { l.classList.remove("is-active"); });
      if (byId[id]) byId[id].classList.add("is-active");
    }

    if (!("IntersectionObserver" in window)) { return; }
    var visible = {};
    var obs = new IntersectionObserver(function (entries) {
      entries.forEach(function (en) { visible[en.target.id] = en.intersectionRatio; });
      // Pick the most-visible section as active.
      var best = null, bestRatio = 0;
      Object.keys(visible).forEach(function (id) {
        if (visible[id] > bestRatio) { bestRatio = visible[id]; best = id; }
      });
      if (best) setActive(best);
    }, { rootMargin: "-45% 0px -45% 0px", threshold: [0, 0.25, 0.5, 1] });

    sections.forEach(function (s) { obs.observe(s); });
    setActive(sections[0].id);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", function () { initSpy(0); });
  } else {
    initSpy(0);
  }
})();
