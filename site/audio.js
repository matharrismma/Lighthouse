/**
 * audio.js — Site-wide audio/TTS + voice input.
 *
 * FLOOR (always available): browser-native Web Speech Synthesis.
 *   ~50 languages, offline, $0, zero key management.
 *
 * CEILING (if ELEVENLABS_API_KEY configured server-side): MP3 streamed
 *   from /speak. M.R. Harris voice. Better timbre, slower pace.
 *   Auto-detected via a probe to /voices on first use.
 *
 * For voice input: Web Speech Recognition (Chrome/Edge native; no key
 * required). Falls back gracefully on browsers that don't support it.
 *
 * Public API:
 *   window._audio.speak(text, lang?)    — speak a string, respecting reader lang
 *   window._audio.stop()                 — stop current utterance
 *   window._audio.isAvailable()          — TTS feature detection
 *   window._audio.listen(opts)           — start voice input; returns Promise<string>
 *   window._audio.canListen()            — voice-input feature detection
 *
 * Auto-wires:
 *   [data-speak="<selector>"]   — click to speak the matched text
 *   [data-listen-target="<id>"] — click to speak into the input with that id
 */
(function () {
  'use strict';

  // Feature detection — bail silently if unsupported (older browsers)
  if (!('speechSynthesis' in window)) {
    window._audio = {
      speak: function () {},
      stop: function () {},
      isAvailable: function () { return false; },
    };
    return;
  }

  let currentUtterance = null;
  let currentAudio = null;          // HTMLAudioElement when using /speak
  let elevenlabsAvailable = null;   // null = unprobed, true/false = result

  // Probe ElevenLabs availability once (cheap GET /voices); cache result.
  async function probeElevenlabs() {
    if (elevenlabsAvailable !== null) return elevenlabsAvailable;
    try {
      const r = await fetch('/voices', { method: 'GET' });
      elevenlabsAvailable = r.ok;
    } catch (e) {
      elevenlabsAvailable = false;
    }
    return elevenlabsAvailable;
  }
  // Kick off the probe in the background; first speak() will use the result.
  probeElevenlabs();

  function getReaderLang() {
    if (window._i18n && window._i18n.lang) return window._i18n.lang;
    try {
      const stored = localStorage.getItem('lang');
      if (stored) return stored;
    } catch (e) {}
    return (navigator.language || 'en').split('-')[0].toLowerCase();
  }

  // Map our 2-letter lang codes to BCP-47 codes that match available voices
  const LANG_BCP47 = {
    en: 'en-US', es: 'es-ES', fr: 'fr-FR', pt: 'pt-BR', de: 'de-DE',
    it: 'it-IT', nl: 'nl-NL', ro: 'ro-RO', ru: 'ru-RU', uk: 'uk-UA',
    ar: 'ar-SA', fa: 'fa-IR', he: 'he-IL', hi: 'hi-IN', sw: 'sw-KE',
    zh: 'zh-CN', ja: 'ja-JP', ko: 'ko-KR', vi: 'vi-VN', my: 'my-MM',
    ht: 'ht-HT', la: 'la',
  };

  // Pick the best voice for a given lang code. Prefers exact match,
  // falls back to language-only match, falls back to default.
  function pickVoice(lang) {
    const voices = window.speechSynthesis.getVoices();
    if (!voices || !voices.length) return null;
    const bcp = LANG_BCP47[lang] || lang;
    // Exact match (e.g. "es-ES")
    let v = voices.find(x => x.lang === bcp);
    if (v) return v;
    // Language-prefix match (e.g. any "es-*")
    const prefix = bcp.split('-')[0];
    v = voices.find(x => x.lang && x.lang.toLowerCase().startsWith(prefix.toLowerCase()));
    if (v) return v;
    return null;
  }

  async function speak(text, lang) {
    if (!text || typeof text !== 'string') return;
    text = text.trim();
    if (!text) return;
    stop();
    const targetLang = lang || getReaderLang();

    // Ceiling: ElevenLabs (only for English; ElevenLabs voices are
    // language-specific and we ship M.R. Harris in English).
    if (targetLang === 'en' && elevenlabsAvailable === true && text.length <= 4000) {
      try {
        const r = await fetch('/speak', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ text }),
        });
        if (r.ok) {
          const blob = await r.blob();
          const url = URL.createObjectURL(blob);
          const audio = new Audio(url);
          audio.onended = () => { currentAudio = null; URL.revokeObjectURL(url); };
          audio.onerror = () => { currentAudio = null; URL.revokeObjectURL(url); };
          currentAudio = audio;
          audio.play().catch(() => { /* autoplay blocked etc. */ });
          if (window._a11y && window._a11y.announce) window._a11y.announce('Speaking aloud');
          return;
        }
        // 503 = not configured. Fall through to Web Speech.
      } catch (e) { /* network etc. — fall through to floor */ }
    }

    // Floor: Web Speech Synthesis (always available)
    const utterance = new SpeechSynthesisUtterance(text);
    utterance.lang = LANG_BCP47[targetLang] || targetLang;
    const voice = pickVoice(targetLang);
    if (voice) utterance.voice = voice;
    utterance.rate = 1.0;
    utterance.pitch = 1.0;
    utterance.onend = () => { currentUtterance = null; };
    utterance.onerror = () => { currentUtterance = null; };
    currentUtterance = utterance;
    window.speechSynthesis.speak(utterance);
    if (window._a11y && window._a11y.announce) window._a11y.announce('Speaking aloud');
  }

  function stop() {
    try { window.speechSynthesis.cancel(); } catch (e) {}
    if (currentAudio) {
      try { currentAudio.pause(); currentAudio.currentTime = 0; } catch (e) {}
      currentAudio = null;
    }
    currentUtterance = null;
  }

  // ── Voice input via Web Speech Recognition ──────────────────────
  // Chrome/Edge native; Safari iOS 14.5+; Firefox needs about:config flag.
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  function canListen() { return !!SpeechRecognition; }

  // Returns a Promise<string> that resolves with the transcript, or
  // rejects on error/timeout. Single-utterance, no interim updates.
  function listen(opts) {
    return new Promise(function (resolve, reject) {
      if (!SpeechRecognition) {
        reject(new Error('SpeechRecognition not supported in this browser'));
        return;
      }
      opts = opts || {};
      const rec = new SpeechRecognition();
      rec.lang = opts.lang || LANG_BCP47[getReaderLang()] || 'en-US';
      rec.continuous = false;
      rec.interimResults = false;
      rec.maxAlternatives = 1;
      let timeoutId = setTimeout(function () {
        try { rec.stop(); } catch (e) {}
        reject(new Error('Voice input timed out'));
      }, opts.timeoutMs || 15000);

      rec.onresult = function (ev) {
        clearTimeout(timeoutId);
        const transcript = (ev.results[0] && ev.results[0][0] && ev.results[0][0].transcript) || '';
        resolve(transcript.trim());
      };
      rec.onerror = function (ev) {
        clearTimeout(timeoutId);
        reject(new Error('SpeechRecognition error: ' + (ev.error || 'unknown')));
      };
      rec.onend = function () { clearTimeout(timeoutId); };

      try {
        rec.start();
        if (window._a11y && window._a11y.announce) window._a11y.announce('Listening…');
      } catch (e) {
        clearTimeout(timeoutId);
        reject(e);
      }
    });
  }

  // Auto-wire [data-listen-target="id"] buttons — click to dictate into
  // the input with that id. Adds a subtle "listening" indicator.
  function wireListenButtons() {
    if (!canListen()) {
      document.querySelectorAll('[data-listen-target]').forEach(btn => {
        btn.style.display = 'none'; // hide on unsupported browsers
      });
      return;
    }
    document.querySelectorAll('[data-listen-target]:not([data-listen-wired])').forEach(btn => {
      btn.setAttribute('data-listen-wired', '1');
      btn.setAttribute('aria-label',
        (window._i18n && _i18n.t('a11y.voice_input', 'Speak your question')) || 'Speak your question');
      if (!btn.style.cursor) btn.style.cursor = 'pointer';
      btn.addEventListener('click', async function (e) {
        e.preventDefault();
        const targetId = btn.getAttribute('data-listen-target');
        const input = document.getElementById(targetId);
        if (!input) return;
        const orig = btn.textContent;
        btn.textContent = '🎙 listening…';
        btn.disabled = true;
        try {
          const text = await listen();
          if (text) {
            input.value = (input.value ? input.value + ' ' : '') + text;
            input.dispatchEvent(new Event('input', { bubbles: true }));
            input.focus();
          }
        } catch (err) {
          console.warn('[audio] listen failed:', err.message);
        } finally {
          btn.textContent = orig;
          btn.disabled = false;
        }
      });
    });
  }

  window._audio = {
    speak: speak,
    stop: stop,
    isAvailable: function () { return true; },
    listen: listen,
    canListen: canListen,
  };

  // Auto-wire any [data-speak] elements
  function wireSpeakButtons() {
    document.querySelectorAll('[data-speak]:not([data-speak-wired])').forEach(el => {
      el.setAttribute('data-speak-wired', '1');
      el.setAttribute('aria-label',
        (window._i18n && window._i18n.t('a11y.speak_aloud', 'Speak aloud')) || 'Speak aloud');
      el.style.cursor = el.style.cursor || 'pointer';
      el.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        const sel = el.getAttribute('data-speak');
        let text = '';
        if (sel && sel.trim()) {
          // Selector form
          const target = document.querySelector(sel);
          if (target) text = target.textContent || '';
        } else {
          // Default: read the previous element's text content
          const prev = el.previousElementSibling;
          if (prev) text = prev.textContent || '';
        }
        if (currentUtterance) {
          stop();
        } else {
          speak(text);
        }
      });
    });
  }

  function onReady(fn) {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', fn);
    } else {
      fn();
    }
  }

  onReady(function () {
    wireSpeakButtons();
    wireListenButtons();
  });

  // Voices load async on some browsers; re-wire if voices arrive late
  if (window.speechSynthesis.onvoiceschanged !== undefined) {
    window.speechSynthesis.onvoiceschanged = wireSpeakButtons;
  }

  // Stop speaking when user navigates away
  window.addEventListener('beforeunload', stop);
})();
