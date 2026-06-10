/* nh-sabbath.js — Sabbath Mode site-wide hook.
 *
 * Reads NHHousehold.preference('sabbath_mode'). If true AND today is Sunday
 * (UTC; future: per-household timezone), adds a 'nh-sabbath-active' class
 * to <html> and surfaces a small dismissable strip explaining the mode.
 *
 * Pages can opt-in by adding CSS:
 *   html.nh-sabbath-active .nh-hide-on-sabbath { display: none; }
 *   html.nh-sabbath-active body { background: <quieter palette>; }
 *
 * Pages that should ALWAYS show (Codex, Hymns, Daily, Walk, Common Book,
 * Calendar, Reading plans, family-internal tools) don't need to do anything.
 *
 * Pages that should HIDE on Sabbath (the FAST channel marquee, channel admin,
 * sponsors page, etc.) add the .nh-hide-on-sabbath class to their key sections
 * — they remain reachable by direct URL but de-emphasized.
 *
 * To opt out for a single visit: NHSabbath.suspend()  (lasts the session)
 * To force-test: NHSabbath.force(true|false)
 */
(function (global) {
  const SUSPEND_KEY = 'narrowhighway_sabbath_suspended_session';

  function isSunday() {
    return new Date().getUTCDay() === 0;  // 0 = Sunday
  }

  function householdPrefers() {
    try {
      if (!global.NHHousehold) return false;
      return !!global.NHHousehold.preference('sabbath_mode');
    } catch (_) { return false; }
  }

  function suspended() {
    try { return sessionStorage.getItem(SUSPEND_KEY) === '1'; }
    catch (_) { return false; }
  }

  function shouldActivate(forceVal) {
    if (forceVal === true) return true;
    if (forceVal === false) return false;
    if (suspended()) return false;
    return isSunday() && householdPrefers();
  }

  function apply(state) {
    const root = document.documentElement;
    if (state) {
      root.classList.add('nh-sabbath-active');
      renderStrip();
    } else {
      root.classList.remove('nh-sabbath-active');
      removeStrip();
    }
  }

  function renderStrip() {
    if (document.getElementById('nhSabbathStrip')) return;
    const s = document.createElement('a');
    s.id = 'nhSabbathStrip';
    s.href = '/calendar.html';
    s.style.cssText = (
      'position:fixed;top:0;left:0;right:0;z-index:9999;' +
      'background:#1a3a52;color:#f4ecd5;padding:0.45em 1em;' +
      'font-family:Georgia,serif;font-size:0.88em;text-align:center;' +
      'text-decoration:none;border-bottom:1px solid #c9b48a;' +
      'box-shadow:0 1px 4px rgba(0,0,0,0.15);'
    );
    s.innerHTML =
      '<strong style="color:#c9b48a;letter-spacing:0.08em;">☧ SABBATH MODE</strong> · ' +
      'a quieter view today · ' +
      '<span style="text-decoration:underline;">today on the calendar →</span> · ' +
      '<button id="nhSabbathDismiss" style="background:none;border:1px solid #c9b48a;color:#c9b48a;margin-left:1em;padding:0.15em 0.6em;border-radius:3px;cursor:pointer;font-family:inherit;font-size:0.88em;">today only, suspend</button>';
    document.body.appendChild(s);
    // Push body down by the strip height
    document.body.style.paddingTop = (parseInt(getComputedStyle(document.body).paddingTop) || 0) + 36 + 'px';
    document.getElementById('nhSabbathDismiss').addEventListener('click', function (e) {
      e.preventDefault(); e.stopPropagation();
      try { sessionStorage.setItem(SUSPEND_KEY, '1'); } catch (_) {}
      apply(false);
    });
  }

  function removeStrip() {
    const s = document.getElementById('nhSabbathStrip');
    if (s) s.remove();
  }

  const NHSabbath = {
    apply: function () { apply(shouldActivate()); },
    force: function (v) { apply(shouldActivate(v)); },
    suspend: function () {
      try { sessionStorage.setItem(SUSPEND_KEY, '1'); } catch (_) {}
      apply(false);
    },
    resume: function () {
      try { sessionStorage.removeItem(SUSPEND_KEY); } catch (_) {}
      apply(shouldActivate());
    },
    isSunday: isSunday,
    isActive: function () { return document.documentElement.classList.contains('nh-sabbath-active'); },
  };

  global.NHSabbath = NHSabbath;

  // Auto-apply on load. Subscribe to household changes (if NHHousehold is loaded).
  function onReady() {
    NHSabbath.apply();
    if (global.NHHousehold && global.NHHousehold.subscribe) {
      global.NHHousehold.subscribe(function () { NHSabbath.apply(); });
    }
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onReady);
  } else {
    onReady();
  }
})(typeof window !== 'undefined' ? window : this);
