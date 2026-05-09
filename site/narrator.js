/* ═══════════════════════════════════════════════════
   Concordance — narrator (shared across the project)

   One voice. Drop a button anywhere with class
   `.listen-btn` and the right data attributes; the
   narrator handles fetch, cache, playback, and the
   one-at-a-time discipline.

   Two ways to use it:

   A) Declarative (auto-attach on load):
      <button class="listen-btn"
              data-narrate-target="#prefaceText">
        ▶ Listen
      </button>
      <p id="prefaceText">Whatever this paragraph says.</p>

   B) Programmatic (custom narration text per click):
      <button class="listen-btn" id="readVerdict">▶ Listen</button>
      <script>
        Narrator.attach(document.getElementById('readVerdict'),
          () => 'The composite verdict is concordant.');
      </script>

   Voice: whatever ELEVENLABS_VOICE_ID the server has set.
   The whole project uses one voice. This module does not
   pick voices; it asks /speak and trusts the server.
═══════════════════════════════════════════════════ */
(function () {
  const API = (location.hostname === 'localhost' || location.hostname === '127.0.0.1')
    ? 'http://localhost:8000' : '';

  // Cache audio blob URLs keyed by exact narration text — so
  // re-clicking the same button doesn't re-pay TTS cost.
  const audioCache = new Map();
  let activeButton = null;
  let activeAudio = null;

  function _stopActive() {
    if (activeAudio && !activeAudio.paused) {
      activeAudio.pause();
      activeAudio.currentTime = 0;
    }
    if (activeButton) _setIdle(activeButton);
    activeButton = null;
    activeAudio = null;
  }

  function _setIdle(btn) {
    btn.classList.remove('loading', 'playing', 'error');
    btn.dataset.state = 'idle';
    const glyph = btn.querySelector('.listen-glyph');
    if (glyph) glyph.textContent = '▶';
    const label = btn.querySelector('.listen-label');
    if (label) label.textContent = btn.dataset.idleLabel || 'Listen';
  }

  function _setLoading(btn) {
    btn.classList.add('loading');
    btn.classList.remove('playing', 'error');
    btn.dataset.state = 'loading';
    const glyph = btn.querySelector('.listen-glyph');
    if (glyph) glyph.textContent = '…';
  }

  function _setPlaying(btn) {
    btn.classList.remove('loading', 'error');
    btn.classList.add('playing');
    btn.dataset.state = 'playing';
    const glyph = btn.querySelector('.listen-glyph');
    if (glyph) glyph.textContent = '◼';
    const label = btn.querySelector('.listen-label');
    if (label) label.textContent = 'Stop';
  }

  function _setError(btn, msg) {
    btn.classList.remove('loading', 'playing');
    btn.classList.add('error');
    btn.dataset.state = 'error';
    const glyph = btn.querySelector('.listen-glyph');
    if (glyph) glyph.textContent = '!';
    if (msg) btn.title = String(msg).slice(0, 200);
    setTimeout(() => _setIdle(btn), 4000);
  }

  // The engine surface the audio attaches to. If the button declares
  // `data-narrate-audio="#someAudio"` we use that <audio>; otherwise
  // we create one inline next to the button.
  function _audioFor(btn) {
    const sel = btn.dataset.narrateAudio;
    if (sel) {
      const el = document.querySelector(sel);
      if (el) return el;
    }
    let el = btn._inlineAudio;
    if (!el) {
      el = document.createElement('audio');
      el.preload = 'none';
      el.controls = !btn.dataset.narrateInline;  // visible by default
      el.style.display = 'block';
      el.style.marginTop = '10px';
      el.style.maxWidth = '100%';
      btn._inlineAudio = el;
      // Insert right after the button or its parent block
      const host = btn.dataset.narrateInline === 'parent'
        ? btn.parentElement
        : btn;
      host.parentElement.insertBefore(el, host.nextSibling);
    }
    return el;
  }

  async function speak(text, button) {
    text = (text || '').trim();
    if (!text || !button) return;

    // Toggle pause if already playing this button
    if (activeButton === button && activeAudio && !activeAudio.paused) {
      _stopActive();
      return;
    }
    _stopActive();

    const audio = _audioFor(button);
    activeAudio = audio;
    activeButton = button;
    audio.onended = () => {
      if (button === activeButton) {
        _setIdle(button);
        activeButton = null;
        activeAudio = null;
      }
    };

    if (audioCache.has(text)) {
      audio.src = audioCache.get(text);
      _setPlaying(button);
      try { await audio.play(); } catch (_) { _setError(button, 'play blocked'); }
      return;
    }

    _setLoading(button);
    try {
      const r = await fetch(API + '/speak', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ text }),
      });
      if (!r.ok) {
        let msg = 'speak unavailable';
        try { const e = await r.json(); msg = e.detail || msg; } catch (_) {}
        throw new Error(msg);
      }
      const blob = await r.blob();
      const url = URL.createObjectURL(blob);
      audioCache.set(text, url);
      audio.src = url;
      _setPlaying(button);
      try { await audio.play(); } catch (_) { _setError(button, 'play blocked'); }
    } catch (err) {
      _setError(button, err.message || String(err));
      if (activeButton === button) {
        activeButton = null;
        activeAudio = null;
      }
    }
  }

  /* ── Public API ───────────────────────────────────── */

  // Programmatic: attach a text provider to a button.
  function attach(button, textProvider) {
    if (!button) return;
    if (button._narratorBound) return;
    button._narratorBound = true;
    _ensureGlyph(button);
    button.addEventListener('click', () => {
      const text = (typeof textProvider === 'function')
        ? textProvider()
        : String(textProvider || '');
      speak(text, button);
    });
  }

  // Resolve the narration text for a declarative button.
  function _declarativeText(btn) {
    if (btn.dataset.narrateText) return btn.dataset.narrateText;
    const sel = btn.dataset.narrateTarget;
    if (sel) {
      const el = document.querySelector(sel);
      if (el) return el.innerText.trim();
    }
    // Fall back to the button's own text (minus the glyph and label)
    return (btn.dataset.narrateFallback || '').trim();
  }

  function _ensureGlyph(btn) {
    if (btn.querySelector('.listen-glyph')) return;
    // If the button is empty, fill it with a standard label.
    if (!btn.textContent.trim()) {
      btn.innerHTML = '<span class="listen-glyph">▶</span> <span class="listen-label">Listen</span>';
      return;
    }
    // If the user provided custom inner content, leave it alone — they
    // wrote what they wanted; we only manage state if .listen-glyph
    // and .listen-label are present.
  }

  // Declarative auto-attach: scan once on load and once on
  // DOMNodeInserted-equivalent (a small mutation observer) so
  // dynamically-added buttons get wired without extra code.
  function _scan(root) {
    (root || document).querySelectorAll('.listen-btn').forEach(btn => {
      if (btn._narratorBound) return;
      btn._narratorBound = true;
      _ensureGlyph(btn);
      btn.addEventListener('click', () => speak(_declarativeText(btn), btn));
    });
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => _scan(document));
  } else {
    _scan(document);
  }
  // Observe additions for late-rendered content (e.g. /almanac.html
  // builds entries after fetching the JSON).
  const mo = new MutationObserver(muts => {
    for (const m of muts) {
      m.addedNodes && m.addedNodes.forEach(n => {
        if (n.nodeType === 1) _scan(n);
      });
    }
  });
  mo.observe(document.body, { childList: true, subtree: true });

  window.Narrator = { speak, attach, _scan };
})();
