/**
 * Narrow Highway feedback widget — thumbs up / thumbs down.
 *
 * Usage:
 *   <div data-nh-feedback="<slug>" data-nh-feedback-label="optional title"></div>
 * Or programmatically:
 *   NH.Feedback.mount(el, slug, { onChange: (vote, reason) => ... })
 *
 * Storage:
 *   localStorage.nh.feedback[slug] = { vote: 'up'|'down', reason?: string, t: ts }
 *
 * Flagging:
 *   Every thumbs-down captures an optional one-tap reason. The flag is queued in
 *   localStorage.nh.flag_queue for operator review at /inbox.html.
 *
 * Server sync (when available):
 *   POSTs { visitor_id, slug, vote, reason, ts } to /feedback. Falls back gracefully.
 */
(function () {
  if (window.__NH_FEEDBACK_INSTALLED__) return;
  window.__NH_FEEDBACK_INSTALLED__ = true;

  const css = `
    .nh-fb {
      display: inline-flex; align-items: center; gap: 6px;
      font-family: 'JetBrains Mono', ui-monospace, monospace;
      font-size: 11px; letter-spacing: 0.08em;
    }
    .nh-fb-btn {
      display: inline-flex; align-items: center; gap: 5px;
      padding: 5px 10px;
      background: rgba(255,255,255,0.03);
      border: 1px solid #29232f;
      border-radius: 6px;
      color: #b3aabd;
      cursor: pointer;
      transition: all 0.15s;
      font-family: inherit; font-size: inherit;
    }
    .nh-fb-btn:hover { color: #ede7db; border-color: #3a3142; }
    .nh-fb-btn.up.on { border-color: #6fc47c; color: #6fc47c; background: rgba(111,196,124,0.1); }
    .nh-fb-btn.down.on { border-color: #c4a030; color: #c4a030; background: rgba(196,160,48,0.1); }
    .nh-fb-state {
      font-size: 10px; letter-spacing: 0.16em; text-transform: uppercase;
      color: #6e6878;
    }
    .nh-fb-state.up { color: #6fc47c; }
    .nh-fb-state.down { color: #c4a030; }
    .nh-fb-state.flagged { color: #c4a030; }

    /* Thumbs-down reason prompt */
    .nh-fb-modal {
      position: fixed; inset: 0; z-index: 100001;
      background: rgba(10,8,16,0.78);
      backdrop-filter: blur(6px);
      display: flex; align-items: center; justify-content: center;
      padding: 20px;
    }
    .nh-fb-card {
      width: min(440px, 100%);
      background: #161320;
      border: 1px solid #3a3142;
      border-radius: 12px;
      padding: 22px 24px;
      box-shadow: 0 30px 80px rgba(0,0,0,0.6);
      font-family: 'Inter', -apple-system, sans-serif;
      color: #ede7db;
    }
    .nh-fb-card-eyebrow {
      font-family: 'JetBrains Mono', monospace;
      font-size: 10px; letter-spacing: 0.22em; text-transform: uppercase;
      color: #c4a030; margin-bottom: 8px;
    }
    .nh-fb-card-title {
      font-size: 16px; font-weight: 600; line-height: 1.3;
      margin-bottom: 8px;
    }
    .nh-fb-card-sub {
      font-size: 13px; color: #b3aabd; margin-bottom: 16px; line-height: 1.5;
    }
    .nh-fb-reasons {
      display: grid; grid-template-columns: 1fr 1fr; gap: 6px;
      margin-bottom: 12px;
    }
    .nh-fb-reason {
      padding: 8px 10px;
      background: #1d1828;
      border: 1px solid #29232f;
      border-radius: 6px;
      font-size: 12px; color: #b3aabd;
      cursor: pointer; transition: all 0.15s;
      text-align: left;
    }
    .nh-fb-reason:hover { border-color: #c4a030; color: #c4a030; }
    .nh-fb-textarea {
      width: 100%; padding: 10px 12px;
      background: #1d1828;
      border: 1px solid #29232f;
      border-radius: 6px;
      color: #ede7db;
      font-family: inherit; font-size: 13px;
      resize: vertical; min-height: 70px;
      margin-bottom: 14px;
    }
    .nh-fb-textarea:focus { outline: none; border-color: #c9a87c; }
    .nh-fb-actions { display: flex; gap: 8px; justify-content: flex-end; }
    .nh-fb-action {
      padding: 9px 16px;
      border-radius: 6px;
      font-family: 'JetBrains Mono', monospace;
      font-size: 11px; letter-spacing: 0.1em; text-transform: uppercase;
      font-weight: 600;
      cursor: pointer; border: 1px solid transparent;
    }
    .nh-fb-action.primary { background: #c4a030; color: #0a0810; }
    .nh-fb-action.primary:hover { background: #d5b143; }
    .nh-fb-action.secondary { background: transparent; color: #b3aabd; border-color: #29232f; }
    .nh-fb-action.secondary:hover { color: #ede7db; border-color: #3a3142; }
  `;

  function injectStyle() {
    if (document.getElementById('nh-fb-style')) return;
    const s = document.createElement('style');
    s.id = 'nh-fb-style';
    s.textContent = css;
    document.head.appendChild(s);
  }

  // ── Storage helpers ─────────────────────────────────────
  function getStore() {
    try { return JSON.parse(localStorage.getItem('nh.feedback') || '{}'); }
    catch (e) { return {}; }
  }
  function setStore(s) {
    localStorage.setItem('nh.feedback', JSON.stringify(s || {}));
  }
  function getFlagQueue() {
    try { return JSON.parse(localStorage.getItem('nh.flag_queue') || '[]'); }
    catch (e) { return []; }
  }
  function setFlagQueue(q) {
    localStorage.setItem('nh.flag_queue', JSON.stringify(q || []));
  }
  function getLowTrustQueue() {
    try { return JSON.parse(localStorage.getItem('nh.flag_queue_lowtrust') || '[]'); }
    catch (e) { return []; }
  }
  function setLowTrustQueue(q) {
    localStorage.setItem('nh.flag_queue_lowtrust', JSON.stringify(q || []));
  }
  function getTrust() {
    try {
      const v = parseFloat(localStorage.getItem('nh.trust') || '1.0');
      return isNaN(v) ? 1.0 : Math.max(0, Math.min(1, v));
    } catch (e) { return 1.0; }
  }
  function setTrust(t) {
    localStorage.setItem('nh.trust', String(Math.max(0, Math.min(1, t))));
  }
  function visitorId() {
    let v = localStorage.getItem('nh.visitor_id');
    if (!v) {
      v = 'v_' + Math.random().toString(36).slice(2, 11) + '_' + Date.now().toString(36);
      localStorage.setItem('nh.visitor_id', v);
    }
    return v;
  }
  /**
   * Update trust based on observed pattern.
   *  - rapid: clicked thumbs-down within 5s of widget mount → trust -= 0.05
   *  - mass: 10+ downs in last 30 min with 0 ups → trust -= 0.15
   *  - balanced: thumbs-up logged → trust += 0.02 (cap at 1.0)
   *  - When operator resolves their flag as OK (cry-wolf): server-side trust -= 0.1
   *    (we mirror this client-side from the synced /feedback response if available)
   */
  function updateTrust(reason) {
    const cur = getTrust();
    let next = cur;
    if (reason === 'rapid_down') next = cur - 0.05;
    else if (reason === 'mass_down') next = cur - 0.15;
    else if (reason === 'up') next = Math.min(1.0, cur + 0.02);
    else if (reason === 'cry_wolf') next = cur - 0.10;
    setTrust(next);
    return next;
  }

  // ── Reason prompt for thumbs-down ───────────────────────
  const REASONS = [
    "Wasn't aligned",
    "Boring",
    "Wrong category for me",
    "Sound or video quality",
    "Surfaced too often",
    "Wrong family-safety rating",
  ];

  function promptForReason(slug, label, onSubmit, onCancel) {
    const modal = document.createElement('div');
    modal.className = 'nh-fb-modal';
    modal.innerHTML = `
      <div class="nh-fb-card">
        <div class="nh-fb-card-eyebrow">FLAG FOR REVIEW</div>
        <div class="nh-fb-card-title">${escapeHtml(label || slug)}</div>
        <div class="nh-fb-card-sub">Every flag is read by the operator. Help us understand — pick a quick reason or write one (optional).</div>
        <div class="nh-fb-reasons">
          ${REASONS.map(r => `<button class="nh-fb-reason" data-reason="${escapeHtml(r)}">${escapeHtml(r)}</button>`).join('')}
        </div>
        <textarea class="nh-fb-textarea" placeholder="Say more, if you want…"></textarea>
        <div class="nh-fb-actions">
          <button class="nh-fb-action secondary" data-act="cancel">Cancel</button>
          <button class="nh-fb-action primary" data-act="submit">Submit flag</button>
        </div>
      </div>
    `;
    document.body.appendChild(modal);

    const textarea = modal.querySelector('.nh-fb-textarea');
    let preset = '';

    modal.querySelectorAll('.nh-fb-reason').forEach(btn => {
      btn.addEventListener('click', () => {
        preset = btn.dataset.reason;
        textarea.placeholder = preset + ' — say more, if you want…';
        modal.querySelectorAll('.nh-fb-reason').forEach(b => b.style.borderColor = '#29232f');
        btn.style.borderColor = '#c4a030';
      });
    });

    modal.querySelector('[data-act="cancel"]').addEventListener('click', () => {
      document.body.removeChild(modal);
      onCancel && onCancel();
    });
    modal.querySelector('[data-act="submit"]').addEventListener('click', () => {
      const free = textarea.value.trim();
      const reason = [preset, free].filter(Boolean).join(' · ');
      document.body.removeChild(modal);
      onSubmit(reason);
    });

    // Esc to cancel
    function esc(e) {
      if (e.key === 'Escape') {
        try { document.body.removeChild(modal); } catch (_) {}
        document.removeEventListener('keydown', esc);
        onCancel && onCancel();
      }
    }
    document.addEventListener('keydown', esc);

    // Focus textarea soon
    setTimeout(() => textarea.focus(), 50);
  }

  // ── Server sync (best-effort, non-blocking) ─────────────
  function syncToServer(payload) {
    try {
      fetch('/feedback', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
        keepalive: true,
      }).catch(() => {});
    } catch (_) {}
  }

  // Detect a thumbs-down click on freshly-mounted content (within 5s = "rapid")
  const MOUNT_TS_BY_SLUG = {};

  // ── Main mount function ─────────────────────────────────
  function mount(el, slug, opts) {
    if (!el || !slug) return;
    opts = opts || {};
    injectStyle();
    const label = opts.label || el.dataset.nhFeedbackLabel || slug;
    const store = getStore();
    const current = store[slug] || {};
    MOUNT_TS_BY_SLUG[slug] = Date.now();

    const root = document.createElement('div');
    root.className = 'nh-fb';
    root.innerHTML = `
      <button class="nh-fb-btn up ${current.vote === 'up' ? 'on' : ''}" type="button" aria-label="Thumbs up">👍 <span class="cnt"></span></button>
      <button class="nh-fb-btn down ${current.vote === 'down' ? 'on' : ''}" type="button" aria-label="Thumbs down">👎 <span class="cnt"></span></button>
      <span class="nh-fb-state ${current.vote || ''}${current.vote === 'down' ? ' flagged' : ''}"></span>
    `;
    el.appendChild(root);
    const upBtn = root.querySelector('.up');
    const downBtn = root.querySelector('.down');
    const stateEl = root.querySelector('.nh-fb-state');

    function paint() {
      const s = getStore();
      const c = s[slug] || {};
      upBtn.classList.toggle('on', c.vote === 'up');
      downBtn.classList.toggle('on', c.vote === 'down');
      stateEl.classList.remove('up','down','flagged');
      if (c.vote === 'up') {
        // Visitor's own bookmark, not a public verdict. The crowd informs;
        // the operator decides. See /assembly.html for the rule.
        stateEl.classList.add('up');
        stateEl.textContent = 'NOTED';
      } else if (c.vote === 'down') {
        // The flag goes to the operator. Honest about what happens.
        stateEl.classList.add('down','flagged');
        stateEl.textContent = 'FLAG SENT TO OPERATOR';
      } else {
        stateEl.textContent = '';
      }
    }

    function setVote(vote, reason) {
      const s = getStore();
      // Toggle off if clicking the same vote again
      if (s[slug] && s[slug].vote === vote) {
        delete s[slug];
        setStore(s);
        paint();
        opts.onChange && opts.onChange(null, null);
        syncToServer({ visitor_id: visitorId(), slug, vote: null, ts: Date.now() });
        return;
      }
      // Trust pattern detection on thumbs-down
      let trust = getTrust();
      if (vote === 'down') {
        // Rapid: clicked < 5s after mount
        const since = Date.now() - (MOUNT_TS_BY_SLUG[slug] || Date.now());
        if (since < 5000) trust = updateTrust('rapid_down');
        // Mass: 10+ unresolved downs in last 30 min with 0 ups
        const recentDowns = getFlagQueue().filter(f => Date.now() - f.ts < 1800000).length;
        const recentUps = Object.values(getStore()).filter(v => v.vote === 'up' && Date.now() - v.t < 1800000).length;
        if (recentDowns >= 10 && recentUps === 0) trust = updateTrust('mass_down');
      } else if (vote === 'up') {
        trust = updateTrust('up');
      }

      s[slug] = { vote, reason: reason || null, t: Date.now(), trust: trust };
      setStore(s);

      // Queue flag if thumbs-down — split by trust level
      if (vote === 'down') {
        const entry = {
          visitor_id: visitorId(),
          slug,
          label,
          reason: reason || null,
          ts: Date.now(),
          resolved: false,
          trust: trust,
        };
        if (trust < 0.3) {
          // Cry-wolf bucket — silently recorded, not surfaced to operator stat row
          const lq = getLowTrustQueue();
          lq.push(entry);
          setLowTrustQueue(lq);
        } else {
          const q = getFlagQueue();
          q.push(entry);
          setFlagQueue(q);
        }
      }
      paint();
      opts.onChange && opts.onChange(vote, reason);
      syncToServer({ visitor_id: visitorId(), slug, vote, reason: reason || null, ts: Date.now(), trust: trust });
    }

    upBtn.addEventListener('click', e => { e.preventDefault(); e.stopPropagation(); setVote('up'); });
    downBtn.addEventListener('click', e => {
      e.preventDefault(); e.stopPropagation();
      // Toggle off without prompt if already on
      const c = (getStore()[slug] || {});
      if (c.vote === 'down') { setVote('down'); return; }
      promptForReason(slug, label, reason => setVote('down', reason));
    });

    paint();
  }

  function escapeHtml(s) {
    return (s || '').toString()
      .replaceAll('&','&amp;').replaceAll('<','&lt;').replaceAll('>','&gt;')
      .replaceAll('"','&quot;').replaceAll("'",'&#39;');
  }

  // ── Auto-mount declarative usage ────────────────────────
  function autoMount(root) {
    (root || document).querySelectorAll('[data-nh-feedback]').forEach(el => {
      if (el.dataset.nhFbMounted) return;
      el.dataset.nhFbMounted = '1';
      const slug = el.dataset.nhFeedback;
      mount(el, slug);
    });
  }
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => autoMount());
  } else {
    autoMount();
  }
  // Re-scan when new content is injected
  const obs = new MutationObserver(() => autoMount());
  obs.observe(document.documentElement, { childList: true, subtree: true });

  // Public API
  window.NH = window.NH || {};
  window.NH.Feedback = {
    mount,
    autoMount,
    getStore,
    getFlagQueue,
    setFlagQueue,
    getLowTrustQueue,
    setLowTrustQueue,
    getTrust,
    setTrust,
    updateTrust,
    visitorId,
  };
})();
