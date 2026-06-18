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
})();
