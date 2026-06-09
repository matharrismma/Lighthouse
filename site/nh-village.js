/* Narrow Highway — the village.
 * ---------------------------------------------------------------------------
 * Renders the verification engine as a working harbor village onto a <canvas>.
 * One renderer, shared by the homepage hero and the full Workshop page, so the
 * two never drift apart.
 *
 * Every piece of content is a card. Agents carry each card up the road, gate to
 * gate — the Harbor, the Witness Hall, the Aligning Room, the Scriptorium — and
 * only what survives reaches the Lighthouse and goes out. The Shepherd walks the
 * road and will guide whoever asks. The visitor can click any building to look
 * inside it.
 *
 *   const v = NHVillage(canvasEl, {
 *     mode:       'hero' | 'full',          // cosmetic preset
 *     live:       true,                      // poll the engine for real numbers
 *     onUpdate:   live => {...},             // after each poll / each broadcast
 *     onInside:   key => {...},              // a building was clicked
 *     onShepherd: () => {...},               // the Shepherd was clicked
 *   });
 *   v.focusStation('witness');  v.clearFocus();  v.stop();
 *
 * NHVillage.interiors — shared copy describing what happens in each building,
 * so the homepage and the Workshop tell the visitor the same story.
 * ---------------------------------------------------------------------------
 */
(function (global) {
  "use strict";

  function clamp(lo, v, hi) { return v < lo ? lo : v > hi ? hi : v; }

  // What the visitor sees when they look inside a building. Plain language —
  // this is the hook, not documentation.
  var INTERIORS = {
    harbor: {
      name: "The Harbor",
      tag: "where cards arrive",
      role: "Agents crawl the open internet and carry back whatever was asked " +
            "for — a film, an article, a hymn, a claim. Nothing here is trusted " +
            "yet. Every arrival is only a candidate, waiting to be carried up the road.",
      rule: "We gather widely. We keep narrowly.",
      ref: "the open web",
      link: "/packets.html", linkLabel: "See the substrate"
    },
    witness: {
      name: "The Witness Hall",
      tag: "two or three must agree",
      role: "A card carried in alone waits here. It does not pass on one voice. " +
            "It passes when a second and a third independent source say the same " +
            "thing. One unsupported claim is never enough.",
      rule: "“At the mouth of two or three witnesses shall the matter be established.”",
      ref: "Deuteronomy 19:15",
      link: "/almanac.html", linkLabel: "See verified claims"
    },
    align: {
      name: "The Aligning Room",
      tag: "does it fit a Christian family?",
      role: "What survived the witnesses is read again — for alignment. True but " +
            "not edifying, or fine for grown-ups but not for children at this hour: " +
            "it is sorted, given its right place and time. Nothing is merely stamped.",
      rule: "The filter is the value. We keep what is true and what is good.",
      ref: "Philippians 4:8",
      link: "/about.html", linkLabel: "How we align"
    },
    scribe: {
      name: "The Scriptorium",
      tag: "the trail is written down",
      role: "Everything that passed is recorded — its sources, its witnesses, the " +
            "verdict, the reasoning. Then it is sealed with a signature that cannot " +
            "be quietly changed later. You can always read why a thing was kept.",
      rule: "The trail is the reasoning. Every verdict is signed.",
      ref: "Ed25519 receipts",
      link: "/receipts.html", linkLabel: "See the receipts"
    },
    tower: {
      name: "The Lighthouse",
      tag: "what survived is broadcast",
      role: "Verified cards become the channel, the library, the daily reading. " +
            "The light only ever carries what passed every gate. This is the part " +
            "of the village the world outside actually sees.",
      rule: "The light shows the narrow way by what survives.",
      ref: "Matthew 7:14",
      link: "/watch.html", linkLabel: "Watch the channel"
    },
    residue: {
      name: "The Residue Pile",
      tag: "what was turned away",
      role: "Cards that failed a gate are not deleted in secret. They are set " +
            "down here, in plain sight. You can always see what did not make it — " +
            "and the trail will tell you which gate turned it away, and why.",
      rule: "We eliminate in the open. Nothing is hidden.",
      ref: "honest by design",
      link: "/misalignments.html", linkLabel: "See disagreements"
    },
    shepherd: {
      name: "The Shepherd",
      tag: "your guide through the village",
      role: "Lost, or just new here? Ask the Shepherd. He shapes your question, " +
            "walks you to the right cards, and stays as quiet or as close as you " +
            "want. He is how you find the narrow path without reading every sign.",
      rule: "Here when you ask — and only when you ask.",
      ref: "John 10:11",
      link: "/walk.html", linkLabel: "Walk with the Shepherd"
    }
  };

  // The built-in "look inside" panel. A page can override by passing its own
  // onInside callback; otherwise the renderer shows this modal itself.
  var PANEL_CSS =
    ".nhv-panel{position:fixed;inset:0;z-index:9990;display:flex;align-items:center;" +
    "justify-content:center;background:rgba(8,6,14,.82);opacity:0;transition:opacity .2s;" +
    "padding:16px;font-family:'Inter',-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;}" +
    ".nhv-panel.open{opacity:1;}" +
    ".nhv-card{width:min(450px,94vw);background:#161320;border:1px solid #3a3142;" +
    "border-top:3px solid #c9a87c;border-radius:14px;padding:22px 24px 24px;" +
    "box-shadow:0 30px 80px rgba(0,0,0,.6);transform:translateY(16px);transition:transform .2s;" +
    "position:relative;}" +
    ".nhv-panel.open .nhv-card{transform:translateY(0);}" +
    ".nhv-close{position:absolute;top:8px;right:12px;background:none;border:0;color:#9b94ac;" +
    "font-size:25px;line-height:1;cursor:pointer;}.nhv-close:hover{color:#fff;}" +
    ".nhv-tag{font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.18em;" +
    "text-transform:uppercase;color:#c9a87c;margin-bottom:5px;}" +
    ".nhv-title{font-family:'Crimson Pro',Georgia,serif;font-weight:400;font-size:1.55rem;" +
    "color:#f4ecd5;margin:0 0 11px;}" +
    ".nhv-role{font-size:14px;color:#cfc8dc;line-height:1.6;margin:0 0 14px;}" +
    ".nhv-rule{margin:0 0 16px;padding:10px 14px;background:rgba(201,168,124,.07);" +
    "border-left:3px solid #c9a87c;border-radius:0 8px 8px 0;font-family:'Crimson Pro',Georgia,serif;" +
    "font-style:italic;color:#e3c498;font-size:14px;line-height:1.45;}" +
    ".nhv-rule cite{display:block;margin-top:6px;font-style:normal;" +
    "font-family:'JetBrains Mono',monospace;font-size:10px;letter-spacing:.1em;color:#9b94ac;}" +
    ".nhv-link{display:inline-flex;align-items:center;gap:6px;padding:9px 16px;background:#c9a87c;" +
    "color:#1a1820;border-radius:7px;font-family:'JetBrains Mono',monospace;font-size:11px;" +
    "letter-spacing:.1em;text-transform:uppercase;font-weight:600;text-decoration:none;}" +
    ".nhv-link:hover{background:#e8c896;}";

  // The five buildings, in road order. Positions are fractions of the canvas;
  // sizes are virtual pixels scaled by `u` so proportions stay constant.
  // `lift` raises a building (and its door) above the road for a gentle stagger.
  var PLAN = [
    { key: "harbor",  name: "The Harbor",        sign: "gathering",     fx: 0.105, w: 138, h: 90,  lift: 10, kind: "house" },
    { key: "witness", name: "The Witness Hall",  sign: "the witnesses", fx: 0.323, w: 156, h: 120, lift: 34, kind: "house" },
    { key: "align",   name: "The Aligning Room", sign: "alignment",     fx: 0.532, w: 134, h: 102, lift: 16, kind: "house" },
    { key: "scribe",  name: "The Scriptorium",   sign: "the scribe",    fx: 0.730, w: 130, h: 110, lift: 30, kind: "house" },
    { key: "tower",   name: "The Lighthouse",    sign: "broadcast",     fx: 0.918, w: 84,  h: 214, lift: 0,  kind: "tower" }
  ];

  function NHVillage(canvas, opts) {
    opts = opts || {};
    var ctx = canvas.getContext("2d");
    var MODE = opts.mode || "full";
    var HERO = MODE === "hero";
    var LIVE = opts.live !== false;
    var onUpdate = typeof opts.onUpdate === "function" ? opts.onUpdate : null;
    var onInside = typeof opts.onInside === "function" ? opts.onInside : null;
    var onShepherd = typeof opts.onShepherd === "function" ? opts.onShepherd : null;

    var W = 1, H = 1, DPR = 1, u = 1;
    var roadY = 0, waterY = 0, skyH = 0;
    var ST = [], RESIDUE = { x: 0, y: 0 }, hitResidue = null, shepHit = null;
    var focusKey = null, hoverKey = null;

    // ---- ambient state ----
    var perf = 0, last = 0, raf = 0, running = true, visible = true, paused = false;
    var stars = [];
    for (var i = 0; i < 80; i++) {
      stars.push({ fx: Math.random(), fy: Math.random() * 0.62,
                   r: Math.random() * 1.3 + 0.3, t: Math.random() * 6.283 });
    }
    var motes = [];
    for (var m = 0; m < 14; m++) {
      motes.push({ fx: Math.random(), fy: 0.14 + Math.random() * 0.82,
                   t: Math.random() * 6.283, sp: 0.15 + Math.random() * 0.25 });
    }
    var pulses = [];
    var beamAngle = 0, beamFlare = 0;

    // ---- live numbers ----
    var live = { cards: null, passed: null, queue: null, ok: false, bcast: 0 };

    // ---- layout -----------------------------------------------------------
    // In hero mode the village is lifted into the upper portion of the canvas
    // so the headline card below it never hides a building.
    function layout() {
      u = clamp(0.5, Math.min(W / 1180, H / 560), 1.35);
      if (HERO) {
        skyH = H * 0.30; waterY = H * 0.355; roadY = H * 0.475;
      } else {
        skyH = H * 0.60; waterY = H * 0.66; roadY = H * 0.815;
      }
      var groundBase = roadY + 4 * u;
      ST = PLAN.map(function (p) {
        var w = p.w * u, h = p.h * u;
        var cx = W * p.fx, cy, doorY;
        if (p.kind === "tower") {
          cy = roadY - h / 2;            // lighthouse stands on the road line
          doorY = roadY;
        } else {
          cy = groundBase - h / 2 - p.lift * u;
          doorY = cy + h / 2 + 14 * u;   // the door — and the road — sits below
        }
        return { key: p.key, name: p.name, sign: p.sign, kind: p.kind,
                 cx: cx, cy: cy, w: w, h: h,
                 door: { x: cx, y: doorY }, glow: 0, flash: 0 };
      });
      if (HERO) {
        RESIDUE = { x: W * 0.085, y: roadY + (H - roadY) * 0.26 };
      } else {
        RESIDUE = { x: W * 0.40, y: clamp(roadY + 56 * u, H * 0.93, H - 14 * u) };
      }
      hitResidue = { x: RESIDUE.x - 34 * u, y: RESIDUE.y - 42 * u,
                     w: 68 * u, h: 58 * u };
      // the three witnesses stand outside the Witness Hall
      var wh = ST[1];
      witnesses = [
        { x: wh.cx - 36 * u, y: wh.door.y - 4 * u, bob: 0 },
        { x: wh.cx,          y: wh.door.y + 1 * u, bob: 2 },
        { x: wh.cx + 36 * u, y: wh.door.y - 4 * u, bob: 4 }
      ];
      // the Shepherd patrols the road in front of the village
      shepLane = { x0: W * 0.045, x1: W * (HERO ? 0.27 : 0.32),
                   y: ST[0].door.y + 16 * u };
      if (!shep.init) {
        shep.x = (shepLane.x0 + shepLane.x1) / 2;
        shep.y = shepLane.y; shep.init = true;
      } else {
        shep.y = shepLane.y;
      }
    }
    var witnesses = [];
    var shepLane = { x0: 0, x1: 0, y: 0 };
    var shep = { init: false, x: 0, y: 0, dir: 1, leg: 0, bob: Math.random() * 6,
                 pause: 0, glow: 0 };

    function resize() {
      DPR = Math.min(global.devicePixelRatio || 1, 2);
      var r = canvas.getBoundingClientRect();
      W = Math.max(1, Math.round(r.width));
      H = Math.max(1, Math.round(r.height));
      canvas.width = Math.round(W * DPR);
      canvas.height = Math.round(H * DPR);
      layout();
    }

    // ---- live poll --------------------------------------------------------
    var liveTimer = 0;
    function poll() {
      fetch("/witness-gate/health", { cache: "no-store" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (w) {
          if (!w) return;
          if (w.total_cards != null) live.cards = w.total_cards;
          var bs = w.by_status || {};
          if (bs.passed != null || bs.pass != null) {
            live.passed = (bs.passed != null ? bs.passed : bs.pass);
          } else if (live.cards != null) {
            var bad = 0;
            for (var k in bs) { if (k !== "passed" && k !== "pass") bad += bs[k] || 0; }
            live.passed = Math.max(0, live.cards - bad);
          }
        }).catch(function () {});
      fetch("/engine/queue.stats", { cache: "no-store" })
        .then(function (r) { return r.ok ? r.json() : null; })
        .then(function (q) {
          if (q && q.counts_by_status) {
            live.queue = q.counts_by_status.quarantined || 0;
          }
        }).catch(function () {});
      fetch("/health", { cache: "no-store" })
        .then(function (r) { live.ok = !!(r && r.ok); })
        .catch(function () { live.ok = false; })
        .then(function () { if (onUpdate) onUpdate(live); });
    }

    // ---- carriers (the agents) -------------------------------------------
    var jobs = [], jobSeq = 0, spawnTimer = 1.2;
    function spawn() {
      if (jobs.length >= 5) return;
      jobs.push({
        id: ++jobSeq, stage: 0, state: "toStation",
        pos: { x: ST[0].door.x - 70 * u, y: roadY + 8 * u },
        workTo: 0, parcel: "fresh",
        leg: Math.random() * 6.28, bob: Math.random() * 6.28,
        speed: (40 + Math.random() * 18), facing: 1, carry: true, fade: 1
      });
    }
    function stepJob(j, dt) {
      j.bob += dt * 3;
      var tgt = null;
      if (j.state === "toStation") tgt = ST[j.stage].door;
      else if (j.state === "diverting") tgt = RESIDUE;
      else if (j.state === "returning") tgt = { x: ST[0].door.x - 92 * u, y: roadY + 14 * u };
      if (tgt) {
        var dx = tgt.x - j.pos.x, dy = tgt.y - j.pos.y;
        var d = Math.hypot(dx, dy);
        if (d < 3) {
          if (j.state === "toStation") {
            j.state = "working";
            j.workTo = perf + 1.0 + Math.random() * 0.8;
            ST[j.stage].glow = 1;
          } else if (j.state === "diverting") {
            j.carry = false; j.state = "returning";
          } else if (j.state === "returning") {
            j.fade -= dt * 0.9;
            if (j.fade <= 0) j.dead = true;
          }
        } else {
          var v = j.speed * u * dt;
          j.pos.x += dx / d * Math.min(v, d);
          j.pos.y += dy / d * Math.min(v, d);
          j.leg += dt * 9;
          j.facing = dx >= 0 ? 1 : -1;
        }
      }
      if (j.state === "working" && perf >= j.workTo) {
        var st = ST[j.stage];
        if (st.key === "witness") {
          if (Math.random() < 0.12) { j.parcel = "rejected"; j.state = "diverting"; return; }
          j.parcel = "verified";
        }
        if (j.stage >= ST.length - 1) {
          beamFlare = 1; live.bcast++;
          pulses.push({ x: ST[ST.length - 1].cx, y: ST[ST.length - 1].cy - ST[ST.length - 1].h / 2, r: 8 * u, a: 1 });
          if (onUpdate) onUpdate(live);
          j.carry = false; j.state = "returning";
        } else {
          j.stage++; j.state = "toStation";
        }
      }
    }

    // ---- drawing ----------------------------------------------------------
    function roundRect(x, y, w, h, r) {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.arcTo(x + w, y, x + w, y + h, r);
      ctx.arcTo(x + w, y + h, x, y + h, r);
      ctx.arcTo(x, y + h, x, y, r);
      ctx.arcTo(x, y, x + w, y, r);
      ctx.closePath();
    }
    function drawSky() {
      var g = ctx.createLinearGradient(0, 0, 0, H);
      g.addColorStop(0, "#140f28");
      g.addColorStop(0.42, "#241a3a");
      g.addColorStop(0.60, "#4a3450");
      g.addColorStop(0.70, "#7a4f4c");
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
      for (var i = 0; i < stars.length; i++) {
        var s = stars[i];
        var tw = 0.5 + 0.5 * Math.sin(perf * 1.4 + s.t);
        ctx.globalAlpha = 0.22 + 0.55 * tw;
        ctx.fillStyle = "#fff";
        ctx.beginPath();
        ctx.arc(s.fx * W, s.fy * skyH, s.r, 0, 6.283);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      // moon
      var mx = W * 0.16, my = skyH * 0.30, mr = clamp(20, 34 * u, 40);
      ctx.fillStyle = "#f6eccf";
      ctx.shadowColor = "#f6eccf"; ctx.shadowBlur = 38;
      ctx.beginPath(); ctx.arc(mx, my, mr, 0, 6.283); ctx.fill();
      ctx.shadowBlur = 0;
      ctx.fillStyle = "#241a3a";
      ctx.beginPath(); ctx.arc(mx + mr * 0.5, my - mr * 0.34, mr * 0.88, 0, 6.283); ctx.fill();
    }
    function drawWater() {
      var g = ctx.createLinearGradient(0, waterY, 0, H);
      g.addColorStop(0, "#23304a"); g.addColorStop(1, "#10182a");
      ctx.fillStyle = g; ctx.fillRect(0, waterY, W, H - waterY);
      ctx.strokeStyle = "rgba(180,200,235,.16)"; ctx.lineWidth = 1.3;
      for (var i = 0; i < 6; i++) {
        var y = waterY + 14 + i * 20 * u;
        ctx.beginPath();
        for (var x = 0; x <= W; x += 20) {
          var yy = y + Math.sin(x * 0.05 + perf * 1.05 + i) * 2.3;
          x === 0 ? ctx.moveTo(x, yy) : ctx.lineTo(x, yy);
        }
        ctx.stroke();
      }
      // moon glint
      ctx.globalAlpha = 0.45; ctx.fillStyle = "#f6eccf";
      for (var k = 0; k < 4; k++) {
        var gy = waterY + 16 + k * 26 * u;
        ctx.fillRect(W * 0.16 - 13, gy + Math.sin(perf + k) * 2, 26 + k * 6, 2);
      }
      ctx.globalAlpha = 1;
    }
    function drawGround() {
      var g = ctx.createLinearGradient(0, waterY, 0, H);
      g.addColorStop(0, "#2a2433"); g.addColorStop(1, "#1c1726");
      ctx.fillStyle = g;
      ctx.fillRect(0, roadY - 34 * u, W, H - (roadY - 34 * u));
      // the road through the doors
      ctx.strokeStyle = "rgba(214,200,170,.30)";
      ctx.lineWidth = clamp(5, 9 * u, 11);
      ctx.lineCap = "round";
      ctx.setLineDash([2, 12 * u]);
      ctx.beginPath();
      ctx.moveTo(ST[0].door.x - 84 * u, roadY + 10 * u);
      for (var i = 0; i < ST.length; i++) ctx.lineTo(ST[i].door.x, roadY);
      ctx.stroke();
      // spur to the residue pile
      ctx.beginPath();
      ctx.moveTo(ST[1].door.x, roadY);
      ctx.lineTo(RESIDUE.x, RESIDUE.y);
      ctx.stroke();
      ctx.setLineDash([]);
    }
    function drawBoats() {
      for (var i = 0; i < 2; i++) {
        var bx = W * 0.06 + i * 132 * u + Math.sin(perf * 0.4 + i) * 9;
        var by = waterY + 30 * u + i * 24 * u;
        ctx.fillStyle = "#3a3147";
        ctx.beginPath();
        ctx.moveTo(bx - 16 * u, by); ctx.lineTo(bx + 16 * u, by);
        ctx.lineTo(bx + 10 * u, by + 9 * u); ctx.lineTo(bx - 10 * u, by + 9 * u);
        ctx.closePath(); ctx.fill();
        ctx.strokeStyle = "#d8d2e8"; ctx.lineWidth = 1.5;
        ctx.beginPath(); ctx.moveTo(bx, by); ctx.lineTo(bx, by - 20 * u); ctx.stroke();
        ctx.fillStyle = "#cfc8dc";
        ctx.beginPath();
        ctx.moveTo(bx, by - 20 * u); ctx.lineTo(bx, by - 4 * u);
        ctx.lineTo(bx + 12 * u, by - 7 * u); ctx.closePath(); ctx.fill();
      }
    }
    function labelStation(s, x, y) {
      if (u < 0.6) return;
      ctx.textAlign = "center";
      ctx.fillStyle = "#f4efe4";
      ctx.font = "600 " + (13 * u).toFixed(1) + "px Inter,system-ui,sans-serif";
      ctx.fillText(s.name, x, y);
      if (u >= 0.74) {
        ctx.fillStyle = "#9b8fae";
        ctx.font = "500 " + (10.5 * u).toFixed(1) + "px Inter,system-ui,sans-serif";
        ctx.fillText(s.sign, x, y + 13 * u);
      }
    }
    function drawHouse(s) {
      var x = s.cx - s.w / 2, y = s.cy - s.h / 2, w = s.w, h = s.h;
      var glow = s.glow || 0;
      var sel = (focusKey === s.key) ? 1 : (hoverKey === s.key ? 0.55 : 0);
      var halo = Math.max(glow * 0.5, sel);
      if (halo > 0) {
        ctx.save();
        ctx.globalAlpha = halo;
        ctx.fillStyle = "#ffd98a";
        ctx.shadowColor = "#ffd98a"; ctx.shadowBlur = 34;
        roundRect(x - 7, y - 7, w + 14, h + 14, 12); ctx.fill();
        ctx.restore();
      }
      // walls
      ctx.fillStyle = "#322a3e"; roundRect(x, y, w, h, 7); ctx.fill();
      ctx.strokeStyle = "rgba(255,255,255,.07)"; ctx.lineWidth = 1.4; ctx.stroke();
      // roof
      ctx.fillStyle = "#b4694a";
      ctx.beginPath();
      ctx.moveTo(x - 9 * u, y + 4); ctx.lineTo(x + w / 2, y - 26 * u);
      ctx.lineTo(x + w + 9 * u, y + 4); ctx.closePath(); ctx.fill();
      // windows
      var lit = 0.55 + 0.45 * glow;
      ctx.fillStyle = "rgba(255,217,138," + (0.34 + 0.5 * lit) + ")";
      ctx.shadowColor = "#ffd98a"; ctx.shadowBlur = 12 * lit;
      var cols = w > 130 * u ? 3 : 2;
      for (var c = 0; c < cols; c++) {
        var wx = x + w * (c + 1) / (cols + 1) - 9 * u;
        ctx.fillRect(wx, y + h * 0.32, 18 * u, 20 * u);
      }
      ctx.shadowBlur = 0;
      // door
      ctx.fillStyle = "#1c1726";
      roundRect(x + w / 2 - 11 * u, y + h - 30 * u, 22 * u, 30 * u, 5); ctx.fill();
      // chimney smoke
      for (var i = 0; i < 3; i++) {
        var t = (perf * 0.5 + i * 0.5) % 1;
        ctx.globalAlpha = (1 - t) * 0.2;
        ctx.fillStyle = "#cfc8dc";
        ctx.beginPath();
        ctx.arc(x + w * 0.74, y - 26 * u - t * 40 * u, (4 + t * 9) * u, 0, 6.283);
        ctx.fill();
      }
      ctx.globalAlpha = 1;
      labelStation(s, s.cx, y - 36 * u);
    }
    function drawLighthouse(s) {
      var cx = s.cx, baseY = s.cy + s.h / 2, topY = s.cy - s.h / 2;
      var sel = (focusKey === s.key) ? 1 : (hoverKey === s.key ? 0.5 : 0);
      // beam
      ctx.save();
      ctx.translate(cx, topY + 18 * u);
      for (var k = 0; k < 2; k++) {
        ctx.rotate(beamAngle + k * Math.PI);
        var bg = ctx.createLinearGradient(0, 0, 280 * u, 0);
        var a = 0.15 + 0.24 * beamFlare;
        bg.addColorStop(0, "rgba(255,243,196," + a + ")");
        bg.addColorStop(1, "rgba(255,243,196,0)");
        ctx.fillStyle = bg;
        ctx.beginPath();
        ctx.moveTo(0, 0); ctx.lineTo(280 * u, -48 * u);
        ctx.lineTo(280 * u, 48 * u); ctx.closePath(); ctx.fill();
      }
      ctx.restore();
      if (sel > 0) {
        ctx.save(); ctx.globalAlpha = sel;
        ctx.fillStyle = "#ffd98a"; ctx.shadowColor = "#ffd98a"; ctx.shadowBlur = 30;
        roundRect(cx - 30 * u, topY - 6 * u, 60 * u, s.h + 12 * u, 12); ctx.fill();
        ctx.restore();
      }
      // tapered tower
      ctx.fillStyle = "#d9cdb4";
      ctx.beginPath();
      ctx.moveTo(cx - 15 * u, topY + 20 * u); ctx.lineTo(cx + 15 * u, topY + 20 * u);
      ctx.lineTo(cx + 26 * u, baseY); ctx.lineTo(cx - 26 * u, baseY);
      ctx.closePath(); ctx.fill();
      // red bands
      ctx.fillStyle = "#b4534a";
      for (var b = 0; b < 3; b++) {
        var yy = topY + 34 * u + b * ((baseY - topY - 34 * u) / 3);
        ctx.fillRect(cx - 26 * u, yy, 52 * u, 13 * u);
      }
      // lamp room
      ctx.fillStyle = "#2a2334";
      roundRect(cx - 17 * u, topY, 34 * u, 22 * u, 4); ctx.fill();
      var lampA = 0.6 + 0.4 * beamFlare;
      ctx.fillStyle = "rgba(255,243,196," + lampA + ")";
      ctx.shadowColor = "#fff3c4"; ctx.shadowBlur = 26 * lampA;
      ctx.beginPath(); ctx.arc(cx, topY + 11 * u, 8 * u, 0, 6.283); ctx.fill();
      ctx.shadowBlur = 0;
      // cap
      ctx.fillStyle = "#3a3147";
      ctx.beginPath();
      ctx.moveTo(cx - 19 * u, topY); ctx.lineTo(cx, topY - 16 * u);
      ctx.lineTo(cx + 19 * u, topY); ctx.closePath(); ctx.fill();
      labelStation(s, cx, baseY + 18 * u);
    }
    function drawResidue() {
      var sel = (focusKey === "residue") ? 1 : (hoverKey === "residue" ? 0.5 : 0);
      if (sel > 0) {
        ctx.save(); ctx.globalAlpha = sel * 0.5;
        ctx.fillStyle = "#ffd98a"; ctx.shadowColor = "#ffd98a"; ctx.shadowBlur = 24;
        ctx.beginPath();
        ctx.arc(RESIDUE.x, RESIDUE.y - 8 * u, 26 * u, 0, 6.283); ctx.fill();
        ctx.restore();
      }
      ctx.fillStyle = "#55525e";
      var heap = [[0,0],[-9,-2],[9,-3],[-3,-11],[6,-12],[0,-21]];
      for (var i = 0; i < heap.length; i++) {
        roundRect(RESIDUE.x + heap[i][0] * u - 6 * u, RESIDUE.y + heap[i][1] * u - 6 * u,
                  12 * u, 12 * u, 2); ctx.fill();
      }
      if (u >= 0.6) {
        ctx.textAlign = "center";
        ctx.fillStyle = "#9b8fae";
        ctx.font = "500 " + (10.5 * u).toFixed(1) + "px Inter,system-ui,sans-serif";
        ctx.fillText("the residue pile", RESIDUE.x, RESIDUE.y + 24 * u);
      }
    }
    function drawFigure(x, y, leg, facing, parcel, carry, bob, alpha) {
      ctx.save();
      ctx.globalAlpha = alpha == null ? 1 : alpha;
      ctx.translate(x, y + Math.sin(bob) * 1.2);
      ctx.scale(u, u);
      var f = facing || 1;
      var sw = Math.sin(leg) * 4;
      ctx.strokeStyle = "#d8d2e8"; ctx.lineWidth = 2.6; ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(0, 2); ctx.lineTo(sw, 12);
      ctx.moveTo(0, 2); ctx.lineTo(-sw, 12); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(0, -10); ctx.lineTo(0, 2); ctx.stroke();
      ctx.beginPath();
      if (carry) { ctx.moveTo(0, -6); ctx.lineTo(7 * f, -2); }
      else { ctx.moveTo(0, -6); ctx.lineTo(-sw * 0.7, 0); ctx.moveTo(0, -6); ctx.lineTo(sw * 0.7, 0); }
      ctx.stroke();
      ctx.fillStyle = "#ece8f4";
      ctx.beginPath(); ctx.arc(0, -15, 4.4, 0, 6.283); ctx.fill();
      if (carry) {
        var col = parcel === "verified" ? "#8fd6a0"
                : parcel === "rejected" ? "#6b6b72" : "#ffb347";
        ctx.fillStyle = col;
        ctx.shadowColor = col; ctx.shadowBlur = 10;
        roundRect(7 * f - 5, -8, 11, 11, 2); ctx.fill();
        ctx.shadowBlur = 0;
      }
      ctx.restore();
    }
    function drawShepherd() {
      var sel = shep.glow;
      ctx.save();
      ctx.translate(shep.x, shep.y + Math.sin(shep.bob) * 1.4);
      var s = u * 1.34;
      ctx.scale(s, s);
      var f = shep.dir;
      // selection / hover halo
      if (sel > 0) {
        ctx.save();
        ctx.globalAlpha = sel * 0.6;
        ctx.fillStyle = "#ffd98a"; ctx.shadowColor = "#ffd98a"; ctx.shadowBlur = 26;
        ctx.beginPath(); ctx.arc(0, -8, 19, 0, 6.283); ctx.fill();
        ctx.restore();
      }
      var lg = Math.sin(shep.leg) * 3.4;
      // robe
      ctx.fillStyle = "#3c5e74";
      ctx.beginPath();
      ctx.moveTo(0, -12);
      ctx.lineTo(8.5, 13); ctx.lineTo(-8.5, 13);
      ctx.closePath(); ctx.fill();
      ctx.strokeStyle = "#5c8aa6"; ctx.lineWidth = 1; ctx.stroke();
      // walking foot hint
      ctx.strokeStyle = "#2a4658"; ctx.lineWidth = 2.4; ctx.lineCap = "round";
      ctx.beginPath();
      ctx.moveTo(lg * 0.4, 12); ctx.lineTo(lg, 15);
      ctx.moveTo(-lg * 0.4, 12); ctx.lineTo(-lg, 15); ctx.stroke();
      // head + simple hood
      ctx.fillStyle = "#ece8f4";
      ctx.beginPath(); ctx.arc(0, -17, 5, 0, 6.283); ctx.fill();
      ctx.fillStyle = "#3c5e74";
      ctx.beginPath(); ctx.arc(0, -19, 5.6, Math.PI, 6.283); ctx.fill();
      // staff with a lantern
      ctx.strokeStyle = "#caa46e"; ctx.lineWidth = 2.2;
      ctx.beginPath();
      ctx.moveTo(9 * f, -22); ctx.lineTo(9 * f, 14); ctx.stroke();
      var lanA = 0.65 + 0.35 * Math.sin(perf * 2.2);
      ctx.fillStyle = "rgba(255,221,138," + lanA + ")";
      ctx.shadowColor = "#ffd98a"; ctx.shadowBlur = 16;
      ctx.beginPath(); ctx.arc(9 * f, -24, 4.2, 0, 6.283); ctx.fill();
      ctx.shadowBlur = 0;
      ctx.restore();
      // label
      if (u >= 0.58) {
        ctx.textAlign = "center";
        ctx.fillStyle = "#ffd98a";
        ctx.font = "600 " + (11.5 * u).toFixed(1) + "px Inter,system-ui,sans-serif";
        ctx.fillText("Shepherd", shep.x, shep.y + 30 * u);
        if (u >= 0.74) {
          ctx.fillStyle = "#9b8fae";
          ctx.font = "500 " + (9.6 * u).toFixed(1) + "px Inter,system-ui,sans-serif";
          ctx.fillText("ask me — I’ll guide you", shep.x, shep.y + 42 * u);
        }
      }
    }
    function drawVignette() {
      var g = ctx.createRadialGradient(W / 2, H * 0.46, Math.min(W, H) * 0.30,
                                       W / 2, H * 0.5, Math.max(W, H) * 0.72);
      g.addColorStop(0, "rgba(0,0,0,0)");
      g.addColorStop(1, "rgba(6,4,12,0.55)");
      ctx.fillStyle = g; ctx.fillRect(0, 0, W, H);
    }

    // ---- step + render ----------------------------------------------------
    function step(dt) {
      perf += dt;
      beamAngle += dt * 0.7;
      beamFlare = Math.max(0, beamFlare - dt * 1.4);
      for (var i = 0; i < ST.length; i++) {
        if (ST[i].glow) ST[i].glow = Math.max(0, ST[i].glow - dt * 0.8);
      }
      for (var p = pulses.length - 1; p >= 0; p--) {
        pulses[p].r += dt * 72 * u; pulses[p].a -= dt * 0.8;
        if (pulses[p].a <= 0) pulses.splice(p, 1);
      }
      for (var w = 0; w < witnesses.length; w++) witnesses[w].bob += dt * 4;
      for (var mo = 0; mo < motes.length; mo++) {
        motes[mo].t += dt * motes[mo].sp;
      }
      // shepherd patrol
      shep.bob += dt * 2.4;
      var wantGlow = (hoverKey === "shepherd") ? 1 : 0;
      shep.glow += (wantGlow - shep.glow) * Math.min(1, dt * 8);
      if (shep.pause > 0) {
        shep.pause -= dt;
      } else {
        shep.x += shep.dir * 26 * u * dt;
        shep.leg += dt * 7;
        if (shep.x > shepLane.x1) { shep.x = shepLane.x1; shep.dir = -1; shep.pause = 1.4 + Math.random(); }
        if (shep.x < shepLane.x0) { shep.x = shepLane.x0; shep.dir = 1; shep.pause = 1.4 + Math.random(); }
      }
      // carriers
      spawnTimer -= dt;
      if (spawnTimer <= 0) { spawn(); spawnTimer = 2.4 + Math.random() * 2.4; }
      for (var j = 0; j < jobs.length; j++) stepJob(jobs[j], dt);
      for (var d = jobs.length - 1; d >= 0; d--) if (jobs[d].dead) jobs.splice(d, 1);
    }
    function render() {
      ctx.setTransform(DPR, 0, 0, DPR, 0, 0);
      ctx.clearRect(0, 0, W, H);
      drawSky();
      drawWater();
      drawGround();
      drawBoats();
      drawResidue();
      // drifting lantern motes for life
      for (var mo = 0; mo < motes.length; mo++) {
        var m = motes[mo];
        var mx = (m.fx + Math.sin(m.t) * 0.03) * W;
        var my = m.fy * roadY + Math.cos(m.t * 1.3) * 6 * u;
        ctx.globalAlpha = 0.28 + 0.22 * Math.sin(m.t * 2);
        ctx.fillStyle = "#ffd98a";
        ctx.beginPath(); ctx.arc(mx, my, 1.5 * u, 0, 6.283); ctx.fill();
      }
      ctx.globalAlpha = 1;
      // buildings, left to right
      for (var i = 0; i < ST.length; i++) {
        if (ST[i].kind === "tower") drawLighthouse(ST[i]);
        else drawHouse(ST[i]);
      }
      // the three witnesses
      var busy = false;
      for (var b = 0; b < jobs.length; b++) {
        if (jobs[b].stage === 1 && jobs[b].state === "working") busy = true;
      }
      for (var wi = 0; wi < witnesses.length; wi++) {
        var wt = witnesses[wi];
        drawFigure(wt.x, wt.y, 0, 1, null, false,
                   wt.bob + (busy ? Math.sin(perf * 6 + wi) * 0.6 : 0), 1);
      }
      // broadcast ripples
      for (var pp = 0; pp < pulses.length; pp++) {
        ctx.strokeStyle = "rgba(255,243,196," + pulses[pp].a + ")";
        ctx.lineWidth = 2;
        ctx.beginPath();
        ctx.arc(pulses[pp].x, pulses[pp].y, pulses[pp].r, 0, 6.283);
        ctx.stroke();
      }
      // carriers
      for (var c = 0; c < jobs.length; c++) {
        var jb = jobs[c];
        drawFigure(jb.pos.x, jb.pos.y, jb.leg, jb.facing, jb.parcel, jb.carry, jb.bob, jb.fade);
      }
      drawShepherd();
      drawVignette();
    }
    function frame(now) {
      if (!running) return;
      var dt = Math.min(0.05, (now - last) / 1000);
      last = now;
      if (visible && !paused) { step(dt); render(); }
      raf = global.requestAnimationFrame(frame);
    }

    // ---- interaction ------------------------------------------------------
    function toLocal(e) {
      var r = canvas.getBoundingClientRect();
      var cx = (e.touches && e.touches[0]) ? e.touches[0].clientX : e.clientX;
      var cy = (e.touches && e.touches[0]) ? e.touches[0].clientY : e.clientY;
      return { x: cx - r.left, y: cy - r.top };
    }
    function pick(pt) {
      // shepherd first — generous round hit box
      var sr = 26 * u;
      if (Math.hypot(pt.x - shep.x, pt.y - shep.y - 4 * u) < sr) return "shepherd";
      for (var i = 0; i < ST.length; i++) {
        var s = ST[i];
        var topPad = (s.kind === "tower") ? 18 * u : 44 * u; // include roof/cap + label
        var x0 = s.cx - s.w / 2 - 8 * u, x1 = s.cx + s.w / 2 + 8 * u;
        var y0 = s.cy - s.h / 2 - topPad, y1 = s.cy + s.h / 2 + 8 * u;
        if (pt.x >= x0 && pt.x <= x1 && pt.y >= y0 && pt.y <= y1) return s.key;
      }
      if (hitResidue && pt.x >= hitResidue.x && pt.x <= hitResidue.x + hitResidue.w &&
          pt.y >= hitResidue.y && pt.y <= hitResidue.y + hitResidue.h) return "residue";
      return null;
    }
    function onMove(e) {
      var hit = pick(toLocal(e));
      hoverKey = hit;
      canvas.style.cursor = hit ? "pointer" : "default";
    }
    // ---- the built-in look-inside panel ----------------------------------
    var panelEl = null;
    function makePanel() {
      if (!NHVillage._cssDone) {
        NHVillage._cssDone = true;
        var s = document.createElement("style");
        s.textContent = PANEL_CSS;
        document.head.appendChild(s);
      }
      var el = document.createElement("div");
      el.className = "nhv-panel";
      el.hidden = true;
      el.innerHTML =
        '<div class="nhv-card" role="dialog" aria-modal="true">' +
        '<button class="nhv-close" aria-label="Close">&times;</button>' +
        '<div class="nhv-tag"></div><h2 class="nhv-title"></h2>' +
        '<p class="nhv-role"></p>' +
        '<blockquote class="nhv-rule"><span class="nhv-ruletext"></span>' +
        '<cite class="nhv-ref"></cite></blockquote>' +
        '<a class="nhv-link" href="#"><span class="nhv-linklabel"></span> &rarr;</a></div>';
      document.body.appendChild(el);
      el.querySelector(".nhv-close").addEventListener("click", closeInside);
      el.addEventListener("click", function (e) { if (e.target === el) closeInside(); });
      return el;
    }
    function openInside(key) {
      var d = INTERIORS[key];
      if (!d) return;
      if (!panelEl) panelEl = makePanel();
      panelEl.querySelector(".nhv-tag").textContent = d.tag;
      panelEl.querySelector(".nhv-title").textContent = d.name;
      panelEl.querySelector(".nhv-role").textContent = d.role;
      panelEl.querySelector(".nhv-ruletext").textContent = d.rule;
      panelEl.querySelector(".nhv-ref").textContent = d.ref ? "— " + d.ref : "";
      panelEl.querySelector(".nhv-linklabel").textContent = d.linkLabel || "Open";
      panelEl.querySelector(".nhv-link").setAttribute("href", d.link || "#");
      panelEl.hidden = false;
      var p = panelEl;
      requestAnimationFrame(function () { p.classList.add("open"); });
      focusKey = key;
      paused = true;
    }
    function closeInside() {
      if (!panelEl) return;
      panelEl.classList.remove("open");
      var p = panelEl;
      setTimeout(function () { p.hidden = true; }, 220);
      focusKey = null;
      paused = false;
      last = global.performance.now();
    }
    function showInterior(key) {
      var st = ST.filter(function (s) { return s.key === key; })[0];
      if (st) st.flash = 1;
      if (onInside) { focusKey = key; onInside(key); }
      else openInside(key);
    }

    function onClick(e) {
      var hit = pick(toLocal(e));
      if (!hit) return;
      if (hit === "shepherd") {
        if (onShepherd) onShepherd();
        else showInterior("shepherd");
        return;
      }
      showInterior(hit);
    }
    function onKey(e) {
      if (e.key === "Escape" && panelEl && !panelEl.hidden) closeInside();
    }
    canvas.addEventListener("pointermove", onMove);
    canvas.addEventListener("pointerleave", function () {
      hoverKey = null; canvas.style.cursor = "default";
    });
    canvas.addEventListener("click", onClick);
    document.addEventListener("keydown", onKey);

    function onVis() {
      visible = !document.hidden;
      if (visible) last = global.performance.now();
    }
    document.addEventListener("visibilitychange", onVis);
    global.addEventListener("resize", resize);

    // ---- boot -------------------------------------------------------------
    resize();
    if (LIVE) { poll(); liveTimer = global.setInterval(poll, 9000); }
    last = global.performance.now();
    raf = global.requestAnimationFrame(frame);

    return {
      live: live,
      focusStation: function (key) { focusKey = key; },
      clearFocus: function () { focusKey = null; },
      setPaused: function (b) {
        paused = !!b;
        if (!paused) last = global.performance.now();
      },
      stop: function () {
        running = false;
        global.cancelAnimationFrame(raf);
        if (liveTimer) global.clearInterval(liveTimer);
        global.removeEventListener("resize", resize);
        document.removeEventListener("visibilitychange", onVis);
        document.removeEventListener("keydown", onKey);
        if (panelEl && panelEl.parentNode) panelEl.parentNode.removeChild(panelEl);
      }
    };
  }

  NHVillage.interiors = INTERIORS;
  global.NHVillage = NHVillage;
})(window);
