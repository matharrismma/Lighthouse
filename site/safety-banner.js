/* safety-banner.js — the crisis safety net, rendered identically on every surface.
 *
 * The backend (api/safety.py, via the floor) decides WHEN to show it; this file
 * decides HOW, once, so every page that someone in crisis might reach renders the
 * same unmissable, caring banner. Self-contained: no dependencies, injects its own
 * styles on first use.
 *
 *   const html = NHSafety.render(resp.safety);   // '' when no safety block
 *   if (html) container.insertAdjacentHTML('afterbegin', html);   // safety leads
 *
 * A remedy — or an answer, or a lesson — must never stand between a person in
 * danger and immediate, real help.
 */
(function () {
  "use strict";
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  var _styled = false;
  function ensureStyles() {
    if (_styled || document.getElementById("nh-safety-styles")) { _styled = true; return; }
    var css = [
      ".nh-safety{max-width:720px;margin:0 auto 22px;padding:20px 24px;",
      "border:2px solid #c98a2b;border-left:6px solid #c98a2b;border-radius:10px;",
      "background:rgba(201,138,43,0.10);font-family:'Crimson Pro',Georgia,serif;",
      "color:var(--text,#eee);line-height:1.5;}",
      ".nh-safety-headline{font-size:1.2rem;font-weight:700;line-height:1.35;margin-bottom:14px;}",
      ".nh-safety-list{margin:0 0 14px;padding-left:20px;line-height:1.6;}",
      ".nh-safety-list li{margin-bottom:8px;}",
      ".nh-safety-action{font-weight:700;color:#e6a94d;}",
      ".nh-safety-detail{font-size:0.92rem;color:var(--muted-2,#aaa);font-style:italic;}",
      ".nh-safety-person{margin:10px 0;}",
      ".nh-safety-christ{margin:10px 0;font-style:italic;}",
      ".nh-safety-limit{margin:12px 0 0;padding-top:12px;border-top:1px solid rgba(201,138,43,0.35);",
      "font-size:0.92rem;color:var(--muted-2,#aaa);}",
      "@media print{.nh-safety{border-color:#000;background:#fff;color:#000;}",
      ".nh-safety-action{color:#000;}.nh-safety-detail,.nh-safety-limit{color:#333;}}"
    ].join("");
    var el = document.createElement("style");
    el.id = "nh-safety-styles";
    el.textContent = css;
    (document.head || document.documentElement).appendChild(el);
    _styled = true;
  }

  function render(s) {
    if (!s || !s.triggered) return "";
    ensureStyles();
    var opts = (s.immediate || []).map(function (o) {
      return "<li><b>" + esc(o.name) + "</b> — <span class=\"nh-safety-action\">" + esc(o.action) + "</span>"
        + (o.detail ? "<br><span class=\"nh-safety-detail\">" + esc(o.detail) + "</span>" : "") + "</li>";
    }).join("");
    return [
      "<section class=\"nh-safety\" role=\"alert\">",
      "<div class=\"nh-safety-headline\">" + esc(s.headline || "") + "</div>",
      "<ul class=\"nh-safety-list\">" + opts + "</ul>",
      s.a_real_person ? "<p class=\"nh-safety-person\">" + esc(s.a_real_person) + "</p>" : "",
      s.in_christ ? "<p class=\"nh-safety-christ\">" + esc(s.in_christ) + "</p>" : "",
      s.honest_limit ? "<p class=\"nh-safety-limit\">" + esc(s.honest_limit) + "</p>" : "",
      "</section>"
    ].join("");
  }

  window.NHSafety = { render: render, ensureStyles: ensureStyles };
})();
