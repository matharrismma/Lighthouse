/* Narrow Highway — site shell injector.
 *
 * Adds a unified header + footer to any page that includes this script.
 * Single source of truth for site chrome; per-page edit is just adding
 * the <link> and <script> tags.
 *
 * Usage in any page <head>:
 *   <link rel="stylesheet" href="/nh-shell.css">
 *   <script defer src="/nh-shell.js"></script>
 *
 * Opt-out (operator surfaces, special-purpose pages):
 *   <html data-nh-shell="off">
 */
(function () {
  if (window.__NH_SHELL_INSTALLED__) return;
  window.__NH_SHELL_INSTALLED__ = true;

  // Opt-out switch
  if (document.documentElement.dataset.nhShell === "off") return;

  // ── Phase banner (GOV.UK pattern) ────────────────────────────────
  // The operator's honesty discipline turned into chrome. One sentence,
  // permanent, not dismissible — replaces the "what is this?" modal.
  const PHASE_BANNER_HTML = `
<div class="nh-shell-phase" role="note">
  <span class="nh-phase-tag">BETA</span>
  <span class="nh-phase-msg">The engine is still learning. Read the trail — and flag what looks off. Every flag reaches the operator.</span>
</div>`;

  // ── Site-wide radio player markup (persistent across navigation) ──
  // Audio doesn't survive a full page reload on its own, but localStorage
  // + auto-resume on each page load makes it feel continuous. User-gesture
  // requirements: once a click on /radio starts playback, same-origin
  // navigations inherit the activation and autoplay works.
  const PLAYER_HTML = `
<div class="nh-player" id="nh-player" hidden role="region" aria-label="Radio player">
  <div class="nh-player-now">
    <span class="nh-player-dot"></span>
    <div class="nh-player-info">
      <div class="nh-player-name" id="nh-player-name">—</div>
      <div class="nh-player-meta" id="nh-player-meta"></div>
    </div>
  </div>
  <audio id="nh-player-audio" controls preload="none"></audio>
  <button class="nh-player-stop" type="button" onclick="window.nhRadio && window.nhRadio.stop()" title="Stop radio across the site">stop</button>
</div>`;

  // ── Inline styles for phase banner, footer status, on-page TOC, and player ──
  const SHELL_EXTRAS_CSS = `
<style id="nh-shell-extras">
.nh-shell-phase{background:#1a141d;border-bottom:1px solid #29232f;color:#b3aabd;font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:.03em;text-align:center;padding:5px 14px;line-height:1.55;}
.nh-shell-phase .nh-phase-tag{display:inline-block;background:rgba(201,168,124,.15);color:#e3c498;font-weight:700;letter-spacing:.18em;padding:1px 7px;border-radius:3px;margin-right:9px;font-size:10px;}
.nh-shell-phase .nh-phase-msg{color:#9b94ac;font-family:'Crimson Pro',Georgia,serif;font-style:italic;font-size:12.5px;letter-spacing:normal;}
@media(max-width:640px){.nh-shell-phase .nh-phase-msg{display:block;margin-top:2px;}.nh-shell-phase .nh-phase-tag{margin-right:0;}}

.nh-shell-status{display:flex;align-items:center;justify-content:center;gap:8px;font-family:'JetBrains Mono',monospace;font-size:10.5px;letter-spacing:.08em;color:#6e6878;margin-top:10px;flex-wrap:wrap;}
.nh-shell-status .nh-status-dot{width:7px;height:7px;border-radius:50%;background:#6e6878;display:inline-block;}
.nh-shell-status.ok .nh-status-dot{background:#6fc47c;box-shadow:0 0 7px #6fc47c;}
.nh-shell-status.down .nh-status-dot{background:#c96c6c;box-shadow:0 0 7px #c96c6c;}
.nh-shell-status .nh-status-sep{color:#3a3142;}

/* "On this page" right-rail TOC. Auto-built on any page with 3+ H2s.
   Hidden on narrow screens — never competes with content. */
.nh-shell-toc{position:fixed;top:128px;right:18px;width:200px;max-height:calc(100vh - 200px);overflow-y:auto;font-family:'JetBrains Mono',monospace;font-size:10.5px;letter-spacing:.04em;line-height:1.6;z-index:10;}
.nh-shell-toc .nh-toc-h{color:#6e6878;font-size:9.5px;letter-spacing:.18em;text-transform:uppercase;margin-bottom:6px;}
.nh-shell-toc a{display:block;color:#9b94ac;padding:2px 0 2px 8px;border-left:1px solid #29232f;text-decoration:none;font-family:'Crimson Pro',Georgia,serif;font-style:normal;font-size:12px;letter-spacing:normal;line-height:1.45;}
.nh-shell-toc a:hover{color:#e3c498;border-left-color:#c9a87c;}
.nh-shell-toc a.active{color:#f4ecd5;border-left-color:#c9a87c;border-left-width:2px;padding-left:7px;}
@media(max-width:1100px){.nh-shell-toc{display:none;}}

/* Site-wide radio player. Fixed strip at bottom; survives nav via localStorage + auto-resume. */
.nh-player{position:fixed;bottom:0;left:0;right:0;background:#0e0c14;border-top:1px solid #29232f;padding:8px 14px;display:flex;align-items:center;gap:12px;z-index:60;box-shadow:0 -2px 12px rgba(0,0,0,.5);}
.nh-player[hidden]{display:none !important;}
.nh-player-now{display:flex;align-items:center;gap:10px;flex:1;min-width:0;}
.nh-player-dot{width:8px;height:8px;border-radius:50%;background:#6fc47c;box-shadow:0 0 7px #6fc47c;animation:nh-pulse 2s ease-in-out infinite;flex:none;}
@keyframes nh-pulse{0%,100%{opacity:1;}50%{opacity:.45;}}
.nh-player-info{min-width:0;flex:1;overflow:hidden;}
.nh-player-name{font-family:'Crimson Pro',Georgia,serif;font-size:13px;color:#f4ecd5;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.nh-player-meta{font-family:'JetBrains Mono',monospace;font-size:10.5px;letter-spacing:.04em;color:#9b94ac;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;}
.nh-player audio{width:240px;height:34px;flex:none;}
@media(max-width:640px){.nh-player audio{width:150px;}.nh-player-info{font-size:11px;}}
.nh-player-stop{background:transparent;border:1px solid #3a3142;color:#9b94ac;font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.13em;text-transform:uppercase;padding:6px 11px;border-radius:4px;cursor:pointer;flex:none;}
.nh-player-stop:hover{color:#e3c498;border-color:#c9a87c;}
body.nh-radio-on{padding-bottom:62px;}
</style>`;

  // ── Header markup ────────────────────────────────────────────────
  // Five destinations; identity tagline under the wordmark.
  const HEADER_HTML = `
<header class="nh-shell-top">
  <div class="nh-shell-bar">
    <a href="/" class="nh-shell-brand" data-nh-key="home">
      <span class="nh-shell-wordmark">Narrow Highway</span>
      <span class="nh-shell-tag">a curated internet for Christian families</span>
    </a>
    <nav class="nh-shell-nav" aria-label="Site sections">
      <a href="/" data-nh-key="desk">Workspace</a>
      <a href="/walk.html"     data-nh-key="discern">Discern</a>
      <a href="/family.html"    data-nh-key="family">Family</a>
      <a href="/marketplace.html" data-nh-key="market">Market</a>
      <a href="/learn-deep.html" data-nh-key="learn">Learn</a>
      <a href="/tools.html"     data-nh-key="tools">Tools</a>
      <a href="/media-center.html" data-nh-key="watch">Media</a>
      <a href="/codex-deep.html" data-nh-key="codex">Codex</a>
    </nav>
    <a href="/take-part.html" class="nh-shell-support" data-nh-key="take_part">Take part &rarr;</a>
  </div>
</header>`;

  // ── Footer markup ────────────────────────────────────────────────
  // 5-column sitemap grouped by purpose. Same on every page. Surfaces
  // every user-facing page that was reachable only by URL guess.
  const FOOTER_HTML = `
<footer class="nh-shell-bot">
  <div class="nh-shell-bot-inner">
    <div class="nh-shell-bot-cols">
      <div class="nh-shell-col">
        <h4>Discern</h4>
        <a href="/">The work area &middot; bring anything</a>
        <a href="/workspace.html">Desks &middot; libraries &amp; contribute</a>
        <a href="/walk.html">The engine</a>
        <a href="/try.html">Verify a claim</a>
        <a href="/walk.html">Discern this teaching</a>
        <a href="/almanac.html">Almanac</a>
        <a href="/verifiers.html">69 verifiers</a>
        <a href="/how-it-works.html">How it works</a>
      </div>
      <div class="nh-shell-col">
        <h4>Family life</h4>
        <a href="/family.html"><strong>The family desk</strong></a>
        <a href="/marketplace.html">Marketplace &middot; buy &amp; sell</a>
        <a href="/apothecary.html">Apothecary &middot; remedies</a>
        <a href="/recipes.html">Heritage recipes</a>
        <a href="/maker.html">Maker &middot; projects</a>
        <a href="/calendar.html">Family calendar</a>
        <a href="/prayer.html">Prayer board</a>
        <a href="/games.html">Games</a>
        <a href="/bible-trivia.html">Bible trivia</a>
        <a href="/hearth.html">The Hearth</a>
        <a href="/household.html">Household</a>
      </div>
      <div class="nh-shell-col">
        <h4>Learn</h4>
        <a href="/learn.html">Learn &middot; homeschool</a>
        <a href="/tools.html">Tools</a>
        <a href="/encyclopedia.html">Encyclopedia</a>
        <a href="/bibles.html">Bibles in parallel</a>
        <a href="/reading.html">Reading plans</a>
        <a href="/library.html">The Library</a>
        <a href="/reading-room.html">Reading room</a>
        <a href="/places.html">Bible places</a>
      </div>
      <div class="nh-shell-col">
        <h4>Media Center</h4>
        <a href="/media-center.html"><strong>The Media Center</strong></a>
        <a href="/channels.html">The channel</a>
        <a href="/live.html">Live now</a>
        <a href="/schedule.html">Tonight's lineup</a>
        <a href="/radio.html">Radio</a>
        <a href="/hymns.html">Hymns</a>
        <a href="/kids.html">Kids</a>
        <a href="/podcast.html">Podcast</a>
        <a href="/podcast-theatre.html">Theatre podcast</a>
        <a href="/church-streams.html">Church streams</a>
        <a href="/listen.html">Audiobooks</a>
        <a href="/pilots.html">Pilots</a>
      </div>
      <div class="nh-shell-col">
        <h4>Codex</h4>
        <a href="/codex-deep.html"><strong>The codex desk</strong></a>
        <a href="/codex.html">The Codex (manuscript)</a>
        <a href="/guidance.html">Guidance</a>
        <a href="/canon.html">Canon</a>
        <a href="/organic-design.html">Organic Design (OI)</a>
        <a href="/tradition.html">Tradition</a>
        <a href="/assembly.html">Assembly</a>
        <a href="/testimony.html">Testimony</a>
        <a href="/witnesses.html">Witness Roll</a>
        <a href="/refuge.html">Refuge</a>
        <a href="/works.html">M.R. Harris &middot; works</a>
      </div>
      <div class="nh-shell-col">
        <h4>Take part</h4>
        <a href="/take-part.html"><strong>The take-part desk</strong></a>
        <a href="/support.html">Support &middot; covenant tiers</a>
        <a href="/pitch.html">Pitch a show</a>
        <a href="/submit-content.html">Submit content</a>
        <a href="/submit-recipe.html">Submit a recipe</a>
        <a href="/submit-curriculum.html">Submit a lesson</a>
        <a href="/witness.html">Attest as a witness</a>
        <a href="/scribe.html">Scribe</a>
        <a href="/sponsors.html">Sponsors</a>
        <a href="/contact.html">Contact</a>
      </div>
    </div>
    <div class="nh-shell-colophon">
      <p><em>A curated internet for Christian families. Built on a discernment engine.</em></p>
      <p>Narrow Highway &middot; Lighthouse &middot; Concordance Engine</p>
      <p>narrowhighway.com &middot; Scripture quoted from the public-domain KJV.</p>
      <p>No ads, no tracking, no login.</p>
      <p class="nh-shell-status" id="nh-shell-status">
        <span class="nh-status-dot"></span>
        <span id="nh-status-text">engine: …</span>
      </p>
    </div>
  </div>
</footer>`;

  // ── Section detection — which top-level nav item is "here" ───────
  // Map URL path prefix → nav data-nh-key
  const SECTION_PATTERNS = [
    [/^\/(workspace|desk|deposit)\b/, "desk"],
    [/^\/(marketplace|market)\b/, "market"],
    [/^\/(family|apothecary|recipes|maker|calendar|prayer|hearth|household|games|bible-trivia)\b/, "family"],
    [/^\/(learn|learn-deep|phonics|reading|writing|math|science|social_studies|bible_curriculum|workready|curriculum|encyclopedia|bibles|library|reading-room|fieldkit|atlas|places|chronicle)\b/, "learn"],
    [/^\/(codex|codex-deep|guidance|tradition|assembly|testimony|witnesses|refuge|canon|organic-design|works)\b/, "codex"],
    [/^\/(take-part|support|sponsors|pitch|submit|scribe|witness|contact)\b/, "take_part"],
    [/^\/(tools)\b/, "tools"],
    [/^\/(map|skills)\b/, "tools"],
    [/^\/(walks|walk|workshop|how-it-works|verifiers|almanac|poly|packets|misalignments|receipts|try|search)\b/, "discern"],
    [/^\/(media-center|watch-listen|channels|pilots|hymns|kids|radio|watch|listen|live|podcast|podcast-theatre|church-streams|schedule)\b/, "watch"],
    [/^\/(daily|today)\b/, "today"],
    [/^\/(about|welcome)\b/, "about"],
    [/^\/(wallet-transparency|wallet-help)\b/, "take_part"],
  ];
  function currentSection() {
    const path = location.pathname.replace(/\/index\.html$/, "/");
    if (path === "/" || path === "") return "home";
    for (const [re, key] of SECTION_PATTERNS) {
      if (re.test(path)) return key;
    }
    return null;
  }

  // ── Inject ───────────────────────────────────────────────────────
  function injectShell() {
    if (!document.body) return;
    if (document.querySelector(".nh-shell-top")) return; // already injected (or pasted)

    // Inline styles for phase banner + status line + TOC (head)
    if (!document.getElementById("nh-shell-extras")) {
      document.head.insertAdjacentHTML("beforeend", SHELL_EXTRAS_CSS);
    }
    // Phase banner above the header
    document.body.insertAdjacentHTML("afterbegin", PHASE_BANNER_HTML);
    // Header
    document.body.insertAdjacentHTML("afterbegin", HEADER_HTML);
    // Footer
    document.body.insertAdjacentHTML("beforeend", FOOTER_HTML);

    // Phase banner sits BEFORE the header in source order; CSS-wise it
    // appears below since we afterbegin'd both. Move header to truly first.
    const ph = document.querySelector(".nh-shell-phase");
    const top = document.querySelector(".nh-shell-top");
    if (ph && top && top.nextSibling !== ph) {
      document.body.insertBefore(ph, top.nextSibling);
    }

    // Mark current section as 'here'
    const section = currentSection();
    if (section) {
      document
        .querySelectorAll(`.nh-shell-top [data-nh-key="${section}"]`)
        .forEach((a) => a.classList.add("here"));
    }

    // Footer status line — pulls from /health
    fetchStatus();
    // Build the on-page TOC if eligible
    buildToc();
    // Site-wide radio player — injected on every page, restores last station
    document.body.insertAdjacentHTML("beforeend", PLAYER_HTML);
    nhRadioInit();
  }

  // ── Site-wide radio (window.nhRadio API) ─────────────────────────
  function nhRadioInit() {
    const player = document.getElementById("nh-player");
    const audio = document.getElementById("nh-player-audio");
    const name = document.getElementById("nh-player-name");
    const meta = document.getElementById("nh-player-meta");
    if (!player || !audio) return;

    // Persistent volume
    const v = parseFloat(localStorage.getItem("nh_radio_volume") || "0.7");
    if (!isNaN(v)) audio.volume = Math.max(0, Math.min(1, v));
    audio.addEventListener("volumechange", () => {
      localStorage.setItem("nh_radio_volume", String(audio.volume));
    });

    // Auto-resume if the user had the radio on last time
    if (localStorage.getItem("nh_radio_on") === "1") {
      const station = nhRadioGetStation();
      if (station && station.stream) {
        showPlayer(station);
        audio.src = station.stream;
        audio.play().catch(() => {
          // Autoplay blocked — show "tap play" hint
          meta.textContent = "tap play to resume — " + (station.format || "");
        });
      }
    }
  }

  function showPlayer(station) {
    const player = document.getElementById("nh-player");
    const name = document.getElementById("nh-player-name");
    const meta = document.getElementById("nh-player-meta");
    if (!player) return;
    name.textContent = station.name || "Radio";
    meta.textContent = (station.city || "") + (station.format ? " · " + station.format : "");
    player.hidden = false;
    document.body.classList.add("nh-radio-on");
  }

  function hidePlayer() {
    const player = document.getElementById("nh-player");
    if (player) player.hidden = true;
    document.body.classList.remove("nh-radio-on");
  }

  function nhRadioGetStation() {
    try { return JSON.parse(localStorage.getItem("nh_radio_station") || "null"); }
    catch (e) { return null; }
  }

  function nhRadioPlay(station) {
    const audio = document.getElementById("nh-player-audio");
    if (!audio || !station || !station.stream) return;
    audio.src = station.stream;
    audio.play().catch(() => {});
    showPlayer(station);
    localStorage.setItem("nh_radio_on", "1");
    localStorage.setItem("nh_radio_station", JSON.stringify({
      name: station.name || "",
      city: station.city || "",
      format: station.format || "",
      stream: station.stream,
    }));
  }

  function nhRadioStop() {
    const audio = document.getElementById("nh-player-audio");
    if (audio) { audio.pause(); audio.src = ""; }
    hidePlayer();
    localStorage.setItem("nh_radio_on", "0");
  }

  window.nhRadio = {
    play: nhRadioPlay,
    stop: nhRadioStop,
    isOn: () => localStorage.getItem("nh_radio_on") === "1",
    getStation: nhRadioGetStation,
  };

  // ── nhFeedback — "did this help?" two-button widget ─────────────
  // Any result card on the site can call:
  //   nhFeedback.attach(cardEl, {card_id, topic, surface})
  // and a small row appears at the bottom:
  //   "did this help?  [yes]  [no, I wanted...]"
  // "yes" posts {helped:true} to /feedback/card.
  // "no" reveals a one-line input. The text becomes a new airlock
  // classification — the API responds with the right route + URL, and
  // the widget offers to take the user there.
  //
  // The widget is intentionally TINY (40 lines of HTML) and reuses the
  // dark palette via inline styles so it works on cream-themed pages too.
  const NH_FB_CSS = `
.nh-fb{margin-top:14px;padding-top:10px;border-top:1px dashed #29232f;font-family:'JetBrains Mono',monospace;font-size:11px;letter-spacing:.05em;color:#9b94ac;display:flex;flex-wrap:wrap;align-items:center;gap:10px;}
.nh-fb-q{color:#6e6878;text-transform:uppercase;letter-spacing:.16em;font-size:10px;}
.nh-fb-btn{background:transparent;border:1px solid #3a3142;color:#b3aabd;font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.10em;text-transform:uppercase;padding:5px 11px;border-radius:4px;cursor:pointer;transition:all .12s;}
.nh-fb-btn:hover{color:#f4ecd5;border-color:#c9a87c;}
.nh-fb-btn.yes:hover{color:#6fc47c;border-color:#6fc47c;}
.nh-fb-btn.no:hover{color:#e3c498;border-color:#e3c498;}
.nh-fb-thanks{color:#6fc47c;font-style:italic;font-family:'Crimson Pro',Georgia,serif;font-size:13px;letter-spacing:normal;}
.nh-fb-refine{display:none;flex:1;min-width:200px;align-items:center;gap:8px;}
.nh-fb-refine.show{display:flex;}
.nh-fb-input{flex:1;background:#1d1828;border:1px solid #3a3142;color:#ede7db;font-family:'Crimson Pro',Georgia,serif;font-size:13px;padding:6px 10px;border-radius:4px;outline:none;letter-spacing:normal;}
.nh-fb-input:focus{border-color:#c9a87c;}
.nh-fb-go{background:#c9a87c;color:#1a1208;border:none;font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.10em;text-transform:uppercase;padding:6px 12px;border-radius:4px;cursor:pointer;}
.nh-fb-go:hover{background:#e3c498;}
.nh-fb-routed{color:#e3c498;font-family:'Crimson Pro',Georgia,serif;font-size:13px;letter-spacing:normal;}
.nh-fb-routed a{color:#f4ecd5;text-decoration:underline;text-decoration-color:#c9a87c;}
`;

  function nhFeedbackEnsureCss() {
    if (document.getElementById("nh-fb-css")) return;
    const s = document.createElement("style");
    s.id = "nh-fb-css";
    s.textContent = NH_FB_CSS;
    document.head.appendChild(s);
  }

  async function nhFeedbackPost(payload) {
    try {
      const r = await fetch("/feedback/card", {
        method: "POST",
        headers: {"Content-Type": "application/json"},
        body: JSON.stringify(payload),
      });
      if (!r.ok) return null;
      return await r.json();
    } catch (e) { return null; }
  }

  function nhFeedbackAttach(cardEl, opts) {
    if (!cardEl || cardEl.querySelector(".nh-fb")) return; // idempotent
    nhFeedbackEnsureCss();
    const card_id = (opts && opts.card_id) || cardEl.dataset.cardId || "";
    const topic   = (opts && opts.topic)   || cardEl.dataset.topic   || "";
    const surface = (opts && opts.surface) || location.pathname;
    const wrap = document.createElement("div");
    wrap.className = "nh-fb";
    wrap.innerHTML = `
      <span class="nh-fb-q">did this help?</span>
      <button class="nh-fb-btn yes" type="button">yes</button>
      <button class="nh-fb-btn no"  type="button">no, I wanted…</button>
      <span class="nh-fb-refine">
        <input class="nh-fb-input" type="text" placeholder="I was looking for…" maxlength="500">
        <button class="nh-fb-go" type="button">go</button>
      </span>`;
    const yes    = wrap.querySelector(".nh-fb-btn.yes");
    const no     = wrap.querySelector(".nh-fb-btn.no");
    const refine = wrap.querySelector(".nh-fb-refine");
    const input  = wrap.querySelector(".nh-fb-input");
    const go     = wrap.querySelector(".nh-fb-go");
    yes.addEventListener("click", async () => {
      yes.disabled = true; no.disabled = true;
      await nhFeedbackPost({card_id, topic, surface, helped: true});
      wrap.innerHTML = '<span class="nh-fb-thanks">Thanks — noted.</span>';
    });
    no.addEventListener("click", () => {
      no.style.display = "none";
      yes.style.display = "none";
      refine.classList.add("show");
      input.focus();
    });
    const submitRefine = async () => {
      const text = (input.value || "").trim();
      if (!text) { input.focus(); return; }
      go.disabled = true; input.disabled = true;
      const res = await nhFeedbackPost({
        card_id, topic, surface, helped: false, refinement: text,
      });
      if (res && res.refined_url) {
        wrap.innerHTML =
          '<span class="nh-fb-routed">Try <a href="' + escHtml(res.refined_url) + '">' +
          escHtml(res.destination_label || "this page") +
          '</a> &middot; <em>' + escHtml(res.refined_why || "") + '</em></span>';
      } else {
        wrap.innerHTML = '<span class="nh-fb-thanks">Thanks — noted.</span>';
      }
    };
    go.addEventListener("click", submitRefine);
    input.addEventListener("keydown", (e) => { if (e.key === "Enter") submitRefine(); });
    cardEl.appendChild(wrap);
  }

  window.nhFeedback = { attach: nhFeedbackAttach };

  // ── nhFloor — the one airlock renderer, shared by every room ─────
  // Every scoped airlock (workspace, family, learn, codex, take-part) used
  // to carry its own copy of result-rendering, and they drifted apart. This
  // is the single renderer: post to /floor/stand, show the standing cleanly.
  // Palette-neutral inline styles (brass + translucency + inherited text) so
  // it reads on both the cream desks and the dark front door. Branches:
  //   rejected  → the floor refused it
  //   navigate  → a room to open (no gate noise on "play chess")
  //   discern   → a claim → walk the four gates
  //   judgment  → apothecary/scripture/reckon: the standing + choices
  const _FL = {
    card: "text-align:left;background:rgba(155,124,60,.06);border:1px solid rgba(155,124,60,.28);border-left:3px solid #9b7c3c;border-radius:0 8px 8px 0;padding:13px 16px;margin-top:10px;font-family:'Crimson Pro',Georgia,serif;",
    hd:   "font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:#9b7c3c;margin-bottom:5px;",
    why:  "font-style:italic;opacity:.85;font-size:14px;line-height:1.5;",
    mono: "font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.06em;margin-top:7px;",
    go:   "display:inline-block;margin-top:11px;padding:7px 15px;background:#9b7c3c;color:#fff;border-radius:6px;font-family:'JetBrains Mono',monospace;font-size:10.5px;letter-spacing:.12em;text-transform:uppercase;font-weight:700;text-decoration:none;",
    chip: "cursor:pointer;background:rgba(155,124,60,.08);border:1px solid rgba(155,124,60,.32);color:inherit;font-family:'Crimson Pro',Georgia,serif;font-size:13.5px;padding:6px 13px;border-radius:7px;",
    cd:   "margin-top:8px;padding:9px 13px;background:rgba(155,124,60,.07);border-left:2px solid #c9a851;border-radius:0 7px 7px 0;",
  };

  async function nhFloorStand(text, box) {
    if (!box) return;
    text = (text || "").trim();
    if (!text) return;
    box.classList.add("show");
    box.innerHTML = '<div style="font-style:italic;opacity:.6;padding:8px 0;">Weighing it on the floor…</div>';
    let s = null;
    try {
      const r = await fetch("/floor/stand", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      });
      s = await r.json();
    } catch (e) {}
    const E = escHtml;
    if (!s || !s.gates) {
      box.innerHTML = '<div style="' + _FL.card + '"><span style="' + _FL.why + '">The engine is quiet — open a room below directly.</span></div>';
      return;
    }
    if (s.gates.admitted === false) {
      const w = (s.gates.verdicts && s.gates.verdicts[0]) || {};
      box.innerHTML = '<div style="' + _FL.card + 'border-left-color:#c96c6c;"><div style="' + _FL.hd + 'color:#c96c6c;">Did not pass the floor</div><div style="' + _FL.why + '">' + E(w.why || "a gate rejected it") + '</div></div>';
      return;
    }
    const lens = s.lens || {}, route = s.route || {}, nc = s.nested_control || null, ver = s.verifier || {};
    if (lens.name === "navigate") {
      box.innerHTML = '<div style="' + _FL.card + '"><div style="' + _FL.why + '">' + E(route.why || "opening the room") + '</div>' +
        (route.url ? '<a style="' + _FL.go + '" href="' + E(route.url) + '">Open &rarr;</a>' : '') + '</div>';
      return;
    }
    if (lens.name === "discern") {
      box.innerHTML = '<div style="' + _FL.card + '"><div style="' + _FL.why + '">a claim to weigh against the floor</div>' +
        '<a style="' + _FL.go + '" href="/walk.html">Walk the four gates &rarr;</a>' +
        (window.nhGatesHtml ? window.nhGatesHtml() : "") + '</div>';
      return;
    }
    // judgment lens — apothecary / scripture / reckon
    let h = '<div style="' + _FL.card + '"><div style="' + _FL.hd + '">Stood on the floor &middot; ' + E(lens.label || "weighed") + '</div>';
    h += '<div style="' + _FL.why + '">' + E(route.why || lens.frame || "") + '</div>';
    h += '<div style="' + _FL.mono + 'color:#4f7a3a;">RED ✓ &nbsp; FLOOR ✓ &nbsp;<span style="opacity:.6;">&middot; BROTHERS / GOD pending</span></div>';
    if (ver.applies) h += '<div style="' + _FL.mono + 'opacity:.6;">wall &middot; ' + E(ver.applies) + '</div>';
    if (nc && nc.primary_layer) {
      h += '<div style="color:#a8791f;font-size:13px;margin-top:9px;">Control layer &middot; ' + E(nc.primary_layer) + '</div>';
      if (nc.referral_note) h += '<div style="font-style:italic;opacity:.7;font-size:11.5px;margin-top:3px;">' + E(nc.referral_note) + '</div>';
    }
    if (s.choices && s.choices.options && s.choices.options.length) {
      h += '<div style="' + _FL.mono + 'opacity:.7;text-transform:uppercase;letter-spacing:.14em;">' + E(s.choices.prompt || "Narrow it") + '</div>';
      h += '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-top:7px;">';
      s.choices.options.forEach((o, i) =>
        h += '<button type="button" style="' + _FL.chip + '" onclick="nhFloor.pick(this,\'nhflc' + i + '\')">' + E(o.label || "") + '</button>');
      h += '</div>';
      s.choices.options.forEach((o, i) => {
        h += '<div id="nhflc' + i + '" class="nh-fl-cd" style="display:none;' + _FL.cd + '">';
        if (o.why) h += '<div style="font-style:italic;opacity:.7;font-size:12px;margin-bottom:6px;">often shows as: ' + E(o.why) + '</div>';
        (o.detail || []).forEach(d => h += '<div style="font-size:13px;line-height:1.5;opacity:.9;">&middot; ' + E(d) + '</div>');
        h += '</div>';
      });
    }
    if (route.url) h += '<a style="' + _FL.go + '" href="' + E(route.url) + '">Open ' + E(lens.label || "the room") + ' &rarr;</a>';
    h += '</div>';
    box.innerHTML = h;
  }

  function nhFloorPick(btn, id) {
    const card = (btn && btn.closest && btn.closest("div")) || document;
    card.querySelectorAll(".nh-fl-cd").forEach((d) => (d.style.display = "none"));
    const el = document.getElementById(id);
    if (el) el.style.display = "block";
  }

  window.nhFloor = { stand: nhFloorStand, pick: nhFloorPick };

  // ── The four gates' grounding — Scripture (floor) + the Didache (witness) ──
  // Fixed per gate (mirrors api/didache.GATE_ANCHORS). Surfaced wherever the
  // gates appear, so a person weighing a teaching sees the Word it rests on and
  // the Church's oldest application of the same test, standing with it.
  window.nhGates = [
    { gate: "RED",      principle: "by their fruits, not by claim",
      scripture: { ref: "Matthew 7:16",      text: "Ye shall know them by their fruits." },
      didache:   { ref: "Didache 11:8",      text: "From their ways the false and the true prophet shall be known." } },
    { gate: "FLOOR",    principle: "the way of life, not the way of death",
      scripture: { ref: "Deuteronomy 30:19", text: "I have set before you life and death; choose life." },
      didache:   { ref: "Didache 1:1",       text: "There are two ways, one of life and one of death." } },
    { gate: "BROTHERS", principle: "two or three witnesses",
      scripture: { ref: "Deuteronomy 19:15", text: "At the mouth of two or three witnesses shall the matter be established." },
      didache:   { ref: "Didache 12:1",      text: "Receive everyone who comes; then prove and know him." } },
    { gate: "GOD",      principle: "endure; time is the witness",
      scripture: { ref: "Matthew 24:13",     text: "He that endureth to the end shall be saved." },
      didache:   { ref: "Didache 16:1",      text: "Watch; be ready, for you know not the hour." } },
  ];

  // Compact, palette-neutral grounding block. The verse words are rendered
  // INLINE (visible) — not hidden in a hover-only title attribute, which is
  // inaccessible on touch, keyboard, and screen readers. The title stays as a
  // bonus for mouse users; the words no longer depend on it.
  window.nhGatesHtml = function () {
    var rows = window.nhGates.map(function (g) {
      var tip = g.scripture.ref + " — " + g.scripture.text + "  |  " + g.didache.ref + " — " + g.didache.text;
      return '<div title="' + escHtml(tip) + '" style="margin-top:6px;">' +
        '<span style="color:#9b7c3c;font-weight:600;">' + g.gate + '</span>' +
        '<span style="opacity:.7;"> · ' + escHtml(g.principle) + '</span>' +
        '<div style="opacity:.75;margin-top:2px;font-style:italic;">' + escHtml(g.scripture.ref) + ' — ' + escHtml(g.scripture.text) + '</div>' +
        '<div style="opacity:.5;">' + escHtml(g.didache.ref) + ' — ' + escHtml(g.didache.text) + '</div></div>';
    }).join("");
    return '<div style="margin-top:14px;padding-top:10px;border-top:1px dashed rgba(155,124,60,.3);' +
      "font-family:'JetBrains Mono',monospace;font-size:10.5px;letter-spacing:.04em;line-height:1.5;\">" +
      '<div style="text-transform:uppercase;letter-spacing:.16em;opacity:.6;margin-bottom:5px;">' +
      'The four gates rest on Scripture, witnessed by the Didache</div>' + rows + '</div>';
  };

  // ── Footer status line: engine state + numeric trust row ────────
  // Shows what's actually running, not marketing — engine ok/down, packet
  // count, verifier count, gates, and freshness of the last snapshot. All
  // values pulled from /health, which is background-refreshed every 30s.
  function nhFmtCount(n) {
    if (n == null || isNaN(n)) return "—";
    if (n >= 1e6) return (n / 1e6).toFixed(1).replace(/\.0$/, "") + "M";
    if (n >= 1e3) return (n / 1e3).toFixed(1).replace(/\.0$/, "") + "k";
    return String(n);
  }
  async function fetchStatus() {
    const root = document.getElementById("nh-shell-status");
    const txt = document.getElementById("nh-status-text");
    if (!root || !txt) return;
    try {
      const r = await fetch("/health", { cache: "no-store" });
      if (!r.ok) throw new Error("not ok");
      const j = await r.json();
      const ok = (j.status === "ok") && (j.engine_available !== false);
      const ts = j.timestamp || Math.floor(Date.now() / 1000);
      const age = Math.max(0, Math.floor(Date.now() / 1000 - ts));
      const ageTxt = age < 60 ? "fresh" : (age < 3600 ? Math.floor(age/60) + "m" : Math.floor(age/3600) + "h");
      root.classList.add(ok ? "ok" : "down");

      // Pull module counters with graceful fallbacks. Different deployments
      // expose slightly different keys; try the most-likely shapes.
      const mods = j.modules || {};
      const packets =
        (mods.keeping && (mods.keeping.count || mods.keeping.packets || mods.keeping.entries)) ||
        j.ledger_entries ||
        null;
      const verifiers =
        (mods.verifiers && (mods.verifiers.count || mods.verifiers.registered)) ||
        69; // known stable
      const witnesses =
        (mods.trust_index && (mods.trust_index.count || mods.trust_index.witnesses)) || null;

      const sep = " <span class='nh-status-sep'>·</span> ";
      const parts = [
        "engine: " + (ok ? "ok" : "down"),
        packets   ? nhFmtCount(packets) + " packets"     : null,
        verifiers ? verifiers + " verifiers"             : null,
        witnesses ? nhFmtCount(witnesses) + " witnesses" : null,
        "four gates",
        "checked " + ageTxt + " ago",
      ].filter(Boolean);

      txt.innerHTML = parts.join(sep);
    } catch (e) {
      root.classList.add("down");
      txt.innerHTML = "engine: unreachable";
    }
  }

  // ── On-this-page anchor list (MDN/Stripe Docs pattern) ──────────
  // Auto-enables on any page with 3+ H2s. Pages can disable by setting
  // data-nh-toc="off" on <html> or <body>. Hidden on screens < 1100px.
  function buildToc() {
    if (document.documentElement.dataset.nhToc === "off" ||
        document.body.dataset.nhToc === "off") return;
    // Look in the main content area first; fall back to anywhere.
    const scope = document.querySelector("main, article, .well, .ln-wrap") || document.body;
    const headings = Array.from(scope.querySelectorAll("h2"))
      .filter(h => h.offsetParent !== null && (h.textContent || "").trim().length > 0);
    if (headings.length < 3) return;
    // Assign ids and build links
    const links = headings.map((h, i) => {
      if (!h.id) {
        h.id = "s-" + (h.textContent || ("section-" + i))
          .toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "").slice(0, 50);
      }
      return { id: h.id, text: (h.textContent || "").trim() };
    });
    const html = '<div class="nh-shell-toc" aria-label="On this page">' +
      '<div class="nh-toc-h">On this page</div>' +
      links.map(l => '<a href="#' + l.id + '">' + escHtml(l.text) + '</a>').join("") +
      '</div>';
    document.body.insertAdjacentHTML("beforeend", html);
    // Active-on-scroll highlighting
    const tocEls = Array.from(document.querySelectorAll(".nh-shell-toc a"));
    const headEls = headings;
    const onScroll = () => {
      let active = 0;
      for (let i = 0; i < headEls.length; i++) {
        if (headEls[i].getBoundingClientRect().top <= 100) active = i;
        else break;
      }
      tocEls.forEach((a, i) => a.classList.toggle("active", i === active));
    };
    onScroll();
    let scrollTimer = null;
    window.addEventListener("scroll", () => {
      if (scrollTimer) return;
      scrollTimer = requestAnimationFrame(() => { onScroll(); scrollTimer = null; });
    }, { passive: true });
  }

  function escHtml(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, c =>
      ({ "&":"&amp;","<":"&lt;",">":"&gt;","\"":"&quot;","'":"&#39;" }[c]));
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", injectShell);
  } else {
    injectShell();
  }
})();
