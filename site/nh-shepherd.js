/* Narrow Highway — Shepherd OS conversational layer
 * Loads on every page. Adds a chip bottom-right that opens a conversation panel.
 * Shepherd serves four modes — Guide / Big Brother / Coach / Parent — based
 * on the user's tone. Default is quiet servant. Proselytizes only when invited.
 * See memory/project_shepherd_os_proselytize_on_ask_2026-05-17.md for the spine.
 */
(function() {
  if (window.__nhShepherdLoaded) return;
  window.__nhShepherdLoaded = true;

  // ---- styles ----
  const css = `
    .nh-shep-chip { position: fixed; bottom: 18px; right: 18px; background: #1a3a52; color: #fff;
      padding: 0.6em 1em; border-radius: 999px; box-shadow: 0 4px 12px rgba(0,0,0,0.25);
      cursor: pointer; font-family: Georgia, serif; font-size: 0.95em; z-index: 9998;
      display: flex; align-items: center; gap: 0.4em; user-select: none;
      transition: transform 0.1s, background 0.1s; }
    .nh-shep-chip:hover { background: #2b5275; transform: translateY(-1px); }
    .nh-shep-chip .dot { width: 8px; height: 8px; background: #5c8a3a; border-radius: 50%;
      box-shadow: 0 0 8px #5c8a3a; }
    .nh-shep-panel { position: fixed; bottom: 0; right: 0; width: 380px; max-width: 100vw;
      height: 70vh; max-height: 600px; background: #fafaf6; border-left: 1px solid #c9b48a;
      border-top: 1px solid #c9b48a; box-shadow: -4px 0 16px rgba(0,0,0,0.15);
      z-index: 9999; display: flex; flex-direction: column; font-family: Georgia, serif;
      transform: translateY(100%); transition: transform 0.25s ease-out; }
    .nh-shep-panel.open { transform: translateY(0); }
    .nh-shep-header { position: relative; height: 122px; overflow: hidden;
      background: #171029; border-bottom: 1px solid #c9b48a; }
    .nh-shep-portrait { position: absolute; inset: 0; width: 100%; height: 100%; display: block; }
    .nh-shep-id { position: absolute; left: 15px; bottom: 10px; }
    .nh-shep-id .title { font-weight: bold; color: #f4ecd5; font-size: 1.12em;
      text-shadow: 0 1px 5px rgba(0,0,0,.85); }
    .nh-shep-id .sub { font-size: 0.76em; color: #e3c498;
      text-shadow: 0 1px 5px rgba(0,0,0,.85); }
    .nh-shep-header .close { position: absolute; top: 5px; right: 12px; cursor: pointer;
      font-size: 1.5em; line-height: 1; color: #cfc8dc;
      text-shadow: 0 1px 6px rgba(0,0,0,.9); }
    .nh-shep-header .close:hover { color: #fff; }
    .nh-shep-body { flex: 1; overflow-y: auto; padding: 1em; background: #fafaf6;
      color: #2a2a28; font-size: 0.95em; line-height: 1.5; }
    .nh-shep-msg { margin-bottom: 0.8em; }
    .nh-shep-msg.user { text-align: right; }
    .nh-shep-msg .bubble { display: inline-block; padding: 0.5em 0.8em; border-radius: 12px;
      max-width: 86%; text-align: left; word-wrap: break-word; }
    .nh-shep-msg.user .bubble { background: #1a3a52; color: #fff; border-bottom-right-radius: 3px; }
    .nh-shep-msg.shep .bubble { background: #fff; border: 1px solid #d4c8a5;
      border-bottom-left-radius: 3px; color: #2a2a28; }
    .nh-shep-msg.shep .bubble cite { display: block; font-size: 0.78em; color: #5c4a2a;
      margin-top: 0.4em; font-style: italic; }
    .nh-shep-input { padding: 0.6em; border-top: 1px solid #d4c8a5; background: #fff;
      display: flex; gap: 0.4em; }
    .nh-shep-input input { flex: 1; font: inherit; padding: 0.5em 0.7em; border: 1px solid #c9b48a;
      border-radius: 4px; background: #fafaf6; }
    .nh-shep-input button { font: inherit; padding: 0.5em 0.9em; background: #1a3a52; color: #fff;
      border: 0; border-radius: 4px; cursor: pointer; }
    .nh-shep-input button:disabled { opacity: 0.5; cursor: wait; }
    .nh-shep-suggest { padding: 0.5em 1em 0.8em; background: #fafaf6; }
    .nh-shep-suggest button { font: inherit; font-size: 0.85em; background: #f4ecd5;
      color: #5c4a2a; border: 1px solid #c9b48a; border-radius: 999px;
      padding: 0.25em 0.7em; margin: 0.15em 0.2em 0 0; cursor: pointer; }
    .nh-shep-suggest button:hover { background: #e6dcb8; }
    @media (max-width: 480px) {
      .nh-shep-panel { width: 100%; height: 85vh; }
    }
  `;
  const style = document.createElement('style');
  style.textContent = css;
  document.head.appendChild(style);

  // ---- ui ----
  const chip = document.createElement('div');
  chip.className = 'nh-shep-chip';
  chip.innerHTML = '<span class="dot"></span> Ask Shepherd';
  document.body.appendChild(chip);

  const panel = document.createElement('div');
  panel.className = 'nh-shep-panel';
  panel.innerHTML = `
    <div class="nh-shep-header">
      <canvas class="nh-shep-portrait" id="nhShepPortrait" aria-hidden="true"></canvas>
      <div class="nh-shep-id">
        <div class="title">Shepherd</div>
        <div class="sub">your guide — here when you ask</div>
      </div>
      <div class="close" title="Close">×</div>
    </div>
    <div class="nh-shep-body" id="nhShepBody"></div>
    <div class="nh-shep-suggest" id="nhShepSuggest"></div>
    <div class="nh-shep-input">
      <input id="nhShepInput" type="text" placeholder="Type a question…" autocomplete="off">
      <button id="nhShepSend">Ask</button>
    </div>
  `;
  document.body.appendChild(panel);

  const $body = panel.querySelector('#nhShepBody');
  const $suggest = panel.querySelector('#nhShepSuggest');
  const $input = panel.querySelector('#nhShepInput');
  const $send = panel.querySelector('#nhShepSend');
  const $close = panel.querySelector('.close');

  chip.addEventListener('click', () => openPanel());
  $close.addEventListener('click', () => closePanel());

  let portrait = null;
  function openPanel() {
    panel.classList.add('open');
    setTimeout(() => $input.focus(), 250);
    if (!$body.dataset.greeted) {
      greet();
      $body.dataset.greeted = '1';
    }
    if (!portrait) portrait = startPortrait(panel.querySelector('#nhShepPortrait'));
    else portrait.resume();
  }
  function closePanel() {
    panel.classList.remove('open');
    if (portrait) portrait.pause();
  }

  // ---- session ----
  function getSessionId() {
    let sid = localStorage.getItem('nh_shep_session');
    if (!sid) {
      sid = 's_' + Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
      localStorage.setItem('nh_shep_session', sid);
    }
    return sid;
  }

  // ---- ui helpers ----
  function append(role, text, sources) {
    const msg = document.createElement('div');
    msg.className = 'nh-shep-msg ' + role;
    let inner = `<div class="bubble">${escapeHtml(text)}`;
    if (sources && sources.length) {
      const cite = sources.map(s => s.label && s.url ? `<a href="${escapeHtml(s.url)}">${escapeHtml(s.label)}</a>` : escapeHtml(s)).join(' · ');
      inner += `<cite>${cite}</cite>`;
    }
    inner += `</div>`;
    msg.innerHTML = inner;
    $body.appendChild(msg);
    $body.scrollTop = $body.scrollHeight;
  }
  function escapeHtml(s) {
    return String(s||'').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  }
  function suggest(items) {
    $suggest.innerHTML = '';
    for (const s of items) {
      const b = document.createElement('button');
      b.textContent = s;
      b.addEventListener('click', () => { $input.value = s; ask(); });
      $suggest.appendChild(b);
    }
  }

  // ---- greeting + suggestions per page context ----
  function pageContext() {
    const path = window.location.pathname;
    if (path === '/' || path === '/index.html') return 'landing';
    const m = path.match(/^\/([a-z_\-]+)\.html$/);
    if (m) return m[1];
    if (path.startsWith('/tools/')) return 'tool';
    return 'other';
  }
  function greet() {
    const ctx = pageContext();
    const greetings = {
      landing: ['Welcome. I\'m the Shepherd. What can I help you find?',
                ['Show me something to watch', 'Find me a calculator', 'I have a question about God']],
      watch:   ['I see you\'re browsing TV. What kind of mood?',
                ['Something funny', 'Something for kids', 'Something I\'ve never heard of']],
      kids:    ['Kid\'s deck. I can help you pick.',
                ['Read a story', 'Sing a hymn', 'Learn a Bible verse']],
      tools:   ['Tools deck. Anything I can show you how to use?',
                ['How does the calculator work?', 'Find Bethlehem on the map', 'What word should I learn today?']],
      tool:    ['I see you\'re using a tool. Need help?',
                ['How do I use this?', 'Try something else']],
      walk:    ['I\'m here. Tell me what you\'re thinking through.',
                ['I\'m worried about something', 'I made a mistake', 'How do I know what\'s right?']],
      pitch:   ['You can pitch a show idea. Want help shaping it?',
                ['Help me write a log-line', 'What stories are public-domain?', 'How do votes work?']],
    };
    const g = greetings[ctx] || ['I\'m the Shepherd. Ask me anything.',
                                  ['Where do I start?', 'What is this site?', 'I have a question about God']];
    append('shep', g[0]);
    suggest(g[1]);
  }

  // ---- ask flow ----
  $send.addEventListener('click', ask);
  $input.addEventListener('keydown', e => { if (e.key === 'Enter') ask(); });

  async function ask() {
    const q = $input.value.trim();
    if (!q) return;
    append('user', q);
    $input.value = '';
    $suggest.innerHTML = '';
    $send.disabled = true;
    append('shep', '…');
    const placeholder = $body.lastElementChild;
    try {
      const r = await fetch('/api/shepherd/ask', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          question: q,
          page: pageContext(),
          session_id: getSessionId(),
        }),
      });
      if (!r.ok) throw new Error(`HTTP ${r.status}`);
      const data = await r.json();
      placeholder.remove();
      append('shep', data.answer || '(no response)', data.sources);
      if (data.suggest && data.suggest.length) suggest(data.suggest);
    } catch (e) {
      placeholder.remove();
      append('shep', 'I\'m here, but I\'m still being wired in. Try the decks meanwhile — TV, Radio, Codex, Tools, Kids, Walk. (' + e.message + ')');
    } finally {
      $send.disabled = false;
      $input.focus();
    }
  }

  // ---- the Shepherd portrait — a small animated dusk scene in the header ----
  function startPortrait(canvas) {
    if (!canvas) return { pause: function () {}, resume: function () {} };
    const ctx = canvas.getContext('2d');
    let raf = 0, running = false;
    const t0 = performance.now();
    let W = 1, H = 1, DPR = 1;
    const stars = [];
    for (let i = 0; i < 30; i++) {
      stars.push({ fx: Math.random(), fy: Math.random() * 0.62,
                   r: Math.random() * 1.1 + 0.3, p: Math.random() * 6.283 });
    }
    function size() {
      DPR = Math.min(window.devicePixelRatio || 1, 2);
      const r = canvas.getBoundingClientRect();
      W = Math.max(1, r.width); H = Math.max(1, r.height);
      canvas.width = Math.round(W * DPR);
      canvas.height = Math.round(H * DPR);
    }
    function rr(x, y, w, h, rad) {
      ctx.beginPath();
      ctx.moveTo(x + rad, y);
      ctx.arcTo(x + w, y, x + w, y + h, rad);
      ctx.arcTo(x + w, y + h, x, y + h, rad);
      ctx.arcTo(x, y + h, x, y, rad);
      ctx.arcTo(x, y, x + w, y, rad);
      ctx.closePath();
    }
    function drawShepherd(cx, gy, scale, t) {
      ctx.save();
      ctx.translate(cx, gy + Math.sin(t * 1.7) * 1.3);
      ctx.scale(scale, scale);
      // robe
      ctx.fillStyle = '#3a5c72';
      ctx.beginPath();
      ctx.moveTo(0, -52);
      ctx.bezierCurveTo(-9, -52, -15, -22, -16, 0);
      ctx.lineTo(16, 0);
      ctx.bezierCurveTo(15, -22, 9, -52, 0, -52);
      ctx.closePath();
      ctx.fill();
      ctx.strokeStyle = 'rgba(0,0,0,0.18)'; ctx.lineWidth = 1.2;
      ctx.beginPath(); ctx.moveTo(0, -46); ctx.lineTo(0, -3); ctx.stroke();
      // shoulder mantle
      ctx.fillStyle = '#4a6f86';
      ctx.beginPath();
      ctx.moveTo(0, -54);
      ctx.quadraticCurveTo(-13, -50, -11, -34);
      ctx.quadraticCurveTo(0, -40, 11, -34);
      ctx.quadraticCurveTo(13, -50, 0, -54);
      ctx.closePath(); ctx.fill();
      // head + beard + head-wrap
      ctx.fillStyle = '#e7c6a0';
      ctx.beginPath(); ctx.arc(0, -61, 6.6, 0, 6.283); ctx.fill();
      ctx.fillStyle = '#d8ccbc';
      ctx.beginPath(); ctx.arc(0, -57.5, 5, 0.18, Math.PI - 0.18); ctx.fill();
      ctx.fillStyle = '#3a5c72';
      ctx.beginPath();
      ctx.moveTo(-7.4, -62); ctx.quadraticCurveTo(0, -54, 7.4, -62);
      ctx.lineTo(6.4, -67); ctx.quadraticCurveTo(0, -73, -6.4, -67);
      ctx.closePath(); ctx.fill();
      // staff with a crook
      const sx = 20;
      ctx.strokeStyle = '#9a7846'; ctx.lineWidth = 3.2; ctx.lineCap = 'round';
      ctx.beginPath(); ctx.moveTo(sx, 4); ctx.lineTo(sx, -50); ctx.stroke();
      ctx.beginPath(); ctx.arc(sx - 5, -50, 5.2, Math.PI * 1.95, Math.PI * 0.7, false); ctx.stroke();
      // arm reaching the staff
      ctx.strokeStyle = '#4a6f86'; ctx.lineWidth = 4.4;
      ctx.beginPath(); ctx.moveTo(3, -43); ctx.lineTo(sx, -29); ctx.stroke();
      // lantern hanging from the crook
      const lx = sx - 9, ly = -43 + Math.sin(t * 1.5) * 1.2;
      ctx.strokeStyle = '#9a7846'; ctx.lineWidth = 1;
      ctx.beginPath(); ctx.moveTo(sx - 9, -53); ctx.lineTo(lx, ly - 5); ctx.stroke();
      const fl = 0.72 + 0.28 * Math.sin(t * 5);
      const lg = ctx.createRadialGradient(lx, ly, 1, lx, ly, 17);
      lg.addColorStop(0, 'rgba(255,221,138,' + (0.85 * fl) + ')');
      lg.addColorStop(1, 'rgba(255,221,138,0)');
      ctx.fillStyle = lg;
      ctx.beginPath(); ctx.arc(lx, ly, 17, 0, 6.283); ctx.fill();
      ctx.fillStyle = '#caa46e'; rr(lx - 3, ly - 4, 6, 8, 1.5); ctx.fill();
      ctx.fillStyle = 'rgba(255,243,200,' + fl + ')'; rr(lx - 2, ly - 3, 4, 6, 1); ctx.fill();
      ctx.restore();
    }
    function frame(now) {
      if (!running) return;
      const t = (now - t0) / 1000;
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      // dusk sky
      const g = ctx.createLinearGradient(0, 0, 0, H);
      g.addColorStop(0, '#171029'); g.addColorStop(0.5, '#352145');
      g.addColorStop(0.78, '#6f4a4e'); g.addColorStop(1, '#3a2733');
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      // stars
      for (let i = 0; i < stars.length; i++) {
        const st = stars[i];
        ctx.globalAlpha = 0.22 + 0.5 * (0.5 + 0.5 * Math.sin(t * 1.5 + st.p));
        ctx.fillStyle = '#fff';
        ctx.beginPath(); ctx.arc(st.fx * W, st.fy * H, st.r, 0, 6.283); ctx.fill();
      }
      ctx.globalAlpha = 1;
      // crescent moon
      const mx = W * 0.13, my = H * 0.25, mr = H * 0.11;
      ctx.fillStyle = '#f6eccf'; ctx.shadowColor = '#f6eccf'; ctx.shadowBlur = 14;
      ctx.beginPath(); ctx.arc(mx, my, mr, 0, 6.283); ctx.fill();
      ctx.shadowBlur = 0;
      ctx.fillStyle = '#352145';
      ctx.beginPath(); ctx.arc(mx + mr * 0.55, my - mr * 0.32, mr * 0.85, 0, 6.283); ctx.fill();
      // ground
      ctx.fillStyle = '#241a2e'; ctx.fillRect(0, H * 0.82, W, H);
      // lighthouse at the right edge, with a slow beam
      const lx = W * 0.9, lbase = H * 0.83, ltop = H * 0.22;
      ctx.save(); ctx.translate(lx, ltop + 3);
      for (let k = 0; k < 2; k++) {
        ctx.save(); ctx.rotate(t * 0.6 + k * Math.PI);
        const bg = ctx.createLinearGradient(0, 0, W * 0.55, 0);
        bg.addColorStop(0, 'rgba(255,243,196,0.13)');
        bg.addColorStop(1, 'rgba(255,243,196,0)');
        ctx.fillStyle = bg;
        ctx.beginPath(); ctx.moveTo(0, 0);
        ctx.lineTo(W * 0.55, -20); ctx.lineTo(W * 0.55, 20);
        ctx.closePath(); ctx.fill();
        ctx.restore();
      }
      ctx.restore();
      ctx.fillStyle = '#cabfa6';
      ctx.beginPath();
      ctx.moveTo(lx - 6, ltop + 3); ctx.lineTo(lx + 6, ltop + 3);
      ctx.lineTo(lx + 11, lbase); ctx.lineTo(lx - 11, lbase);
      ctx.closePath(); ctx.fill();
      ctx.fillStyle = '#b4534a';
      ctx.fillRect(lx - 11, ltop + (lbase - ltop) * 0.42, 22, 6);
      ctx.fillStyle = '#fff3c4'; ctx.shadowColor = '#fff3c4'; ctx.shadowBlur = 12;
      ctx.beginPath(); ctx.arc(lx, ltop + 1, 3.6, 0, 6.283); ctx.fill();
      ctx.shadowBlur = 0;
      // the Shepherd
      drawShepherd(W * 0.52, H * 0.84, H / 128, t);
      raf = requestAnimationFrame(frame);
    }
    function resume() {
      if (running) return;
      size(); running = true;
      raf = requestAnimationFrame(frame);
    }
    function pause() {
      running = false;
      cancelAnimationFrame(raf);
    }
    window.addEventListener('resize', function () { if (running) size(); });
    resume();
    return { pause: pause, resume: resume };
  }

})();
