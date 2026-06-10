/* nh-voice.js — Read-aloud for any text on Narrow Highway.
 *
 * Surfaces a small "▶ Read aloud" pill on any element with [data-readable]
 * OR any <article> on the page. Clicking starts speech synthesis; clicking
 * again pauses; a second pill button stops.
 *
 * Three backends, picked in order:
 *   1. window.speechSynthesis (Web Speech API) — works in all modern browsers,
 *      no install required
 *   2. Future: /api/tts/piper?text=... endpoint serving Piper-generated audio,
 *      used when the household prefers offline / higher-quality voice
 *   3. Fallback: no-op + tooltip explaining unsupported
 *
 * The default voice is a calm low-rate setting suitable for scripture/hymn
 * reading. Households can override via NHHousehold.preference('voice_rate'),
 * ('voice_pitch'), ('voice_name') for personalized narration.
 *
 * To opt a section in:
 *   <article data-readable>... or
 *   <div data-readable>...</div> or
 *   <section data-readable data-voice-label="The lesson">...</section>
 *
 * Existing <article> tags get a button automatically (opt-out with
 * data-voice="off").
 */
(function (global) {
  const HAS_SPEECH = ('speechSynthesis' in global) && ('SpeechSynthesisUtterance' in global);
  let currentUtter = null;

  function pref(k, fallback) {
    try {
      if (global.NHHousehold) {
        const v = global.NHHousehold.preference(k);
        if (v !== undefined && v !== null) return v;
      }
    } catch (_) {}
    return fallback;
  }

  function pickVoice() {
    if (!HAS_SPEECH) return null;
    const voices = global.speechSynthesis.getVoices() || [];
    const preferred = pref('voice_name', null);
    if (preferred) {
      const m = voices.find(function (v) { return v.name === preferred; });
      if (m) return m;
    }
    // Default: prefer en-US then en-GB. Pick something natural-sounding.
    const enUS = voices.filter(function (v) { return v.lang === 'en-US'; });
    const enGB = voices.filter(function (v) { return v.lang === 'en-GB'; });
    const en = voices.filter(function (v) { return v.lang && v.lang.startsWith('en'); });
    return (enUS[0] || enGB[0] || en[0] || voices[0] || null);
  }

  function gatherText(el) {
    // Clone, strip script/style/buttons, then read textContent
    const clone = el.cloneNode(true);
    clone.querySelectorAll('script, style, button, .nh-voice-pill, .nh-hide-on-print').forEach(function (n) { n.remove(); });
    return (clone.textContent || '').replace(/\s+/g, ' ').trim();
  }

  function stop() {
    if (!HAS_SPEECH) return;
    global.speechSynthesis.cancel();
    currentUtter = null;
    document.querySelectorAll('.nh-voice-pill').forEach(function (p) {
      p.classList.remove('playing');
      const lbl = p.querySelector('.nh-voice-label');
      if (lbl) lbl.textContent = '▶ Read aloud';
    });
  }

  function speak(text, opts) {
    if (!HAS_SPEECH) return false;
    if (!text) return false;
    stop();
    const u = new SpeechSynthesisUtterance(text);
    u.rate = parseFloat(pref('voice_rate', 0.95));   // 0.85–1.0 reads well
    u.pitch = parseFloat(pref('voice_pitch', 1.0));
    u.volume = 1.0;
    const v = pickVoice();
    if (v) u.voice = v;
    u.onend = function () { if (opts && opts.onend) opts.onend(); };
    u.onerror = function () { if (opts && opts.onend) opts.onend(); };
    currentUtter = u;
    global.speechSynthesis.speak(u);
    return true;
  }

  function injectStyles() {
    if (document.getElementById('nh-voice-styles')) return;
    const s = document.createElement('style');
    s.id = 'nh-voice-styles';
    s.textContent = (
      '.nh-voice-pill {' +
      '  display: inline-flex; align-items: center; gap: 0.3em;' +
      '  background: #1a3a52; color: #f4ecd5;' +
      '  border: none; padding: 0.3em 0.85em; border-radius: 999px;' +
      '  font-family: inherit; font-size: 0.78em;' +
      '  cursor: pointer; transition: background 0.15s;' +
      '  margin: 0 0.3em 0.4em 0; vertical-align: middle;' +
      '}' +
      '.nh-voice-pill:hover { background: #2a5570; }' +
      '.nh-voice-pill.playing { background: #5e2a2a; }' +
      '.nh-voice-pill.playing::before { content: "❚❚ "; margin-right: 0.2em; }' +
      '@media print { .nh-voice-pill { display: none !important; } }'
    );
    document.head.appendChild(s);
  }

  function addPillTo(el) {
    if (el.dataset.voice === 'off') return;
    if (el.querySelector(':scope > .nh-voice-pill')) return;
    const btn = document.createElement('button');
    btn.className = 'nh-voice-pill nh-hide-on-print';
    btn.type = 'button';
    btn.setAttribute('aria-label', el.dataset.voiceLabel || 'Read this aloud');
    const lbl = document.createElement('span');
    lbl.className = 'nh-voice-label';
    lbl.textContent = '▶ Read aloud';
    btn.appendChild(lbl);
    if (!HAS_SPEECH) {
      btn.disabled = true;
      btn.title = 'Read-aloud not supported in this browser.';
      lbl.textContent = '▶ (unsupported)';
    } else {
      btn.addEventListener('click', function (e) {
        e.preventDefault(); e.stopPropagation();
        if (btn.classList.contains('playing')) {
          stop();
          return;
        }
        const text = gatherText(el);
        if (!text) return;
        btn.classList.add('playing');
        lbl.textContent = '⏹ Stop';
        speak(text, {
          onend: function () {
            btn.classList.remove('playing');
            lbl.textContent = '▶ Read aloud';
          },
        });
      });
    }
    el.insertBefore(btn, el.firstChild);
  }

  function scan() {
    injectStyles();
    const targets = new Set();
    document.querySelectorAll('[data-readable]').forEach(function (n) { targets.add(n); });
    document.querySelectorAll('article').forEach(function (n) { targets.add(n); });
    targets.forEach(addPillTo);
  }

  // Voice list isn't always ready immediately; re-scan once voices appear.
  function onReady() {
    scan();
    if (HAS_SPEECH && global.speechSynthesis.onvoiceschanged === null) {
      global.speechSynthesis.onvoiceschanged = function () { /* voices ready */ };
    }
    // Re-scan on dynamic content updates (light mutation observer)
    const obs = new MutationObserver(function (muts) {
      let needs = false;
      for (const m of muts) {
        for (const n of m.addedNodes) {
          if (!(n instanceof HTMLElement)) continue;
          if (n.matches && (n.matches('article, [data-readable]') || n.querySelector('article, [data-readable]'))) {
            needs = true; break;
          }
        }
        if (needs) break;
      }
      if (needs) scan();
    });
    obs.observe(document.body, { childList: true, subtree: true });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', onReady);
  } else {
    onReady();
  }

  // Stop on unload
  global.addEventListener('beforeunload', stop);

  global.NHVoice = {
    speak: function (text) { return speak(text); },
    stop: stop,
    available: HAS_SPEECH,
    scan: scan,
  };
})(typeof window !== 'undefined' ? window : this);
