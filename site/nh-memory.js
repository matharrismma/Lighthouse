/* nh-memory.js — the user's own second brain, on-device.
 *
 * Everything you keep already lives in localStorage (nh_kept_v1) — your notes,
 * documents, lists, drafts, verified claims. It never leaves the device, there
 * is no account, and nothing is tracked: this file CANNOT phone home, there is
 * nowhere for it to send anything. It simply reads what you have kept and
 * recalls what relates to what you bring next — so the workspace remembers and
 * routes for YOU, the same way the operator's memory does for the operator.
 *
 *   NHMemory.recall(text, n)  -> [{kind, ts, label, text}]  related kept items
 *   NHMemory.recent(n)        -> [{...}]                     latest kept items
 *   NHMemory.themes(n)        -> ["anxiety","fractions",...] what you return to
 *   NHMemory.count()          -> number kept
 */
(function () {
  "use strict";
  var KEY = "nh_kept_v1";
  var STOP = {};
  ("the and for you your that this with have has was are not but from about what when how why can will would "
   + "should there their them they been were more some just like into than then out get got our use using "
   + "one two who which while where any all its it's i'm i've don't").split(/\s+/).forEach(function (w) { STOP[w] = 1; });

  function load() { try { return JSON.parse(localStorage.getItem(KEY) || "[]") || []; } catch (_) { return []; } }
  function textOf(it) {
    var o = (it && it.obj) || {};
    var p = [o.title, o.note, o.claim, o.answer, o.body, o.subject, o.list, o.query, o.topic, o.what];
    if (Array.isArray(o.items)) p.push(o.items.join(" "));
    return p.filter(Boolean).join(" ");
  }
  function toks(s) { return (String(s || "").toLowerCase().match(/[a-z0-9']{3,}/g) || []); }
  function keyToks(s) { return toks(s).filter(function (t) { return !STOP[t]; }); }

  function summarize(it) {
    var o = (it && it.obj) || {};
    var label = o.title || o.claim || o.list || o.topic || o.query
      || (o.note || o.answer || o.body || "").slice(0, 60)
      || (Array.isArray(o.items) ? o.items.join(", ") : "") || it.kind || "kept";
    return { kind: it.kind, ts: it.ts, label: String(label).slice(0, 80), text: textOf(it).slice(0, 600) };
  }

  function recall(query, limit) {
    var q = keyToks(query);
    if (!q.length) return [];
    var qset = {}; q.forEach(function (t) { qset[t] = 1; });
    var scored = [];
    load().forEach(function (it) {
      var its = keyToks(textOf(it)); if (!its.length) return;
      var hit = 0, seen = {};
      its.forEach(function (t) { if (qset[t] && !seen[t]) { hit++; seen[t] = 1; } });
      if (hit > 0) scored.push({ score: hit, it: it });
    });
    scored.sort(function (a, b) { return b.score - a.score || (b.it.ts || 0) - (a.it.ts || 0); });
    return scored.slice(0, limit || 3).map(function (s) { return summarize(s.it); });
  }

  function recent(limit) { return load().slice(0, limit || 3).map(summarize); }

  function themes(limit) {
    var freq = {};
    load().forEach(function (it) {
      var seen = {};
      keyToks(textOf(it)).forEach(function (t) { if (!seen[t]) { freq[t] = (freq[t] || 0) + 1; seen[t] = 1; } });
    });
    return Object.keys(freq).filter(function (t) { return freq[t] >= 2; })
      .sort(function (a, b) { return freq[b] - freq[a]; }).slice(0, limit || 6);
  }

  window.NHMemory = { recall: recall, recent: recent, themes: themes, count: function () { return load().length; } };

  // ── NHDocs — the user's documents, as cards they can return to ──────────
  // Your writing lives here (nh_docs_v1), on-device. Each document is one card;
  // editing updates the SAME card (a stable id) instead of spawning a new one,
  // so going back to an old document is just opening its card. Nothing leaves
  // the device.
  var DKEY = "nh_docs_v1", CUR = "nh_cur_doc";
  function dload() { try { return JSON.parse(localStorage.getItem(DKEY) || "[]") || []; } catch (_) { return []; } }
  function dsave(a) { try { localStorage.setItem(DKEY, JSON.stringify(a.slice(0, 300))); } catch (_) {} }
  function curId() { try { return localStorage.getItem(CUR) || ""; } catch (_) { return ""; } }
  function setCur(id) { try { localStorage.setItem(CUR, id || ""); } catch (_) {} }
  function newId() { return "d" + Date.now().toString(36) + Math.random().toString(36).slice(2, 6); }
  function titleOf(text) {
    var lines = String(text || "").split("\n");
    for (var i = 0; i < lines.length; i++) { var l = lines[i].trim(); if (l) return l.length > 70 ? l.slice(0, 70) + "…" : l; }
    return "Untitled document";
  }
  var NHDocs = {
    list: function () { return dload().slice().sort(function (a, b) { return (b.updated || 0) - (a.updated || 0); }); },
    get: function (id) { var a = dload(); for (var i = 0; i < a.length; i++) if (a[i].id === id) return a[i]; return null; },
    currentId: curId,
    newDoc: function () { setCur(""); },
    openId: function (id) { setCur(id); },
    remove: function (id) { dsave(dload().filter(function (x) { return x.id !== id; })); if (curId() === id) setCur(""); },
    // Save/update the CURRENT document. Returns its id.
    upsert: function (html, text) {
      var id = curId(), a = dload(), now = Date.now();
      var rec = { id: id || newId(), title: titleOf(text), text: String(text || "").slice(0, 40000),
                  html: String(html || "").slice(0, 80000), updated: now };
      var idx = -1; for (var i = 0; i < a.length; i++) if (a[i].id === rec.id) { idx = i; break; }
      if (idx >= 0) { rec.ts = a[idx].ts || now; a[idx] = rec; } else { rec.ts = now; a.unshift(rec); }
      setCur(rec.id); dsave(a); try { if (window.NHSync) NHSync.push(); } catch (_) {} return rec.id;
    }
  };
  window.NHDocs = NHDocs;

  // ── NHPrefs — which face the user chose, so routing can learn ───────────
  // When the user picks a face for what they brought, remember it; next time
  // a similar input arrives, surface that face first. On-device, deterministic.
  var PKEY = "nh_route_pref";
  function pload() { try { return JSON.parse(localStorage.getItem(PKEY) || "[]") || []; } catch (_) { return []; } }
  window.NHPrefs = {
    record: function (text, face) {
      try {
        var a = pload(); a.unshift({ t: keyToks(text).slice(0, 12), f: face, ts: Date.now() });
        localStorage.setItem(PKEY, JSON.stringify(a.slice(0, 100)));
        if (window.NHSync) NHSync.push();
      } catch (_) {}
    },
    // Faces the user has chosen before for input overlapping this text, ranked.
    preferredFor: function (text) {
      var q = {}; keyToks(text).forEach(function (t) { q[t] = 1; });
      var score = {};
      pload().forEach(function (p) {
        var hit = 0; (p.t || []).forEach(function (t) { if (q[t]) hit++; });
        if (hit > 0) score[p.f] = (score[p.f] || 0) + hit;
      });
      return Object.keys(score).sort(function (a, b) { return score[b] - score[a]; });
    }
  };

  // ── NHSync — cross-device, OPT-IN. Carry your household key (hh_ id) and
  // your keeping/documents/preferences follow you to any device. On-device
  // first; it syncs ONLY if you hold a key. The id is the key — like the keep
  // token; the server stores your own blob, readable only by whoever holds it.
  function hhId() { try { return (window.NHHousehold && NHHousehold.get() && NHHousehold.get().id) || ""; } catch (_) { return ""; } }
  var _pushT = null;
  function doPush() {
    var id = hhId(); if (!id) return;
    try {
      fetch("/me/memory", { method: "POST", headers: { "Content-Type": "application/json", "X-Household-Id": id },
        body: JSON.stringify({ kept: load(), docs: dload(), prefs: pload(), v: 1, updated: Date.now() }) }).catch(function () {});
    } catch (_) {}
  }
  function mergeIn(blob) {
    if (!blob) return false; var changed = false;
    try {
      var bk = {}; load().concat(blob.kept || []).forEach(function (x) { if (x && x.ts) bk[x.ts + "_" + (x.kind || "")] = x; });
      var mk = Object.keys(bk).map(function (k) { return bk[k]; }).sort(function (a, b) { return (b.ts || 0) - (a.ts || 0); }).slice(0, 200);
      if (mk.length !== load().length) changed = true;
      localStorage.setItem(KEY, JSON.stringify(mk));
      var bd = {}; dload().concat(blob.docs || []).forEach(function (x) { if (x && x.id) { if (!bd[x.id] || (x.updated || 0) > (bd[x.id].updated || 0)) bd[x.id] = x; } });
      var md = Object.keys(bd).map(function (i) { return bd[i]; }).sort(function (a, b) { return (b.updated || 0) - (a.updated || 0); });
      if (md.length !== dload().length) changed = true;
      dsave(md);
      if (blob.prefs && blob.prefs.length) { try { localStorage.setItem(PKEY, JSON.stringify(pload().concat(blob.prefs).slice(0, 150))); } catch (_) {} }
    } catch (_) {}
    return changed;
  }
  function pull(cb) {
    var id = hhId(); if (!id) { if (cb) cb(false); return; }
    fetch("/me/memory", { headers: { "X-Household-Id": id } }).then(function (r) { return r.ok ? r.json() : null; }).then(function (d) {
      var ch = d && d.blob ? mergeIn(d.blob) : false;
      if (ch) { try { window.dispatchEvent(new Event("nh-synced")); } catch (_) {} }
      if (cb) cb(ch);
    }).catch(function () { if (cb) cb(false); });
  }
  window.NHSync = { push: function () { if (!hhId()) return; clearTimeout(_pushT); _pushT = setTimeout(doPush, 1500); }, pull: pull, hh: hhId };
  try { pull(); } catch (_) {}
})();
