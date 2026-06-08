/* nh-household.js — Narrow Highway household identity primitive.
 *
 * Stored in localStorage as 'narrowhighway_household_v1'. Privacy-first:
 * nothing leaves the device by default. Optional wallet-signed sync to
 * the engine for cross-device household data is a future addition.
 *
 * The schema is small on purpose. Tools (Common Book, Reading Plans,
 * Calendar, future Family Letters) extend it via their own localStorage
 * keys keyed by household_id.
 *
 * Usage:
 *   NHHousehold.get()                  — returns the current household, or null
 *   NHHousehold.create(hh)             — set / overwrite the household
 *   NHHousehold.patch(partial)         — shallow merge into the current household
 *   NHHousehold.clear()                — remove the household
 *   NHHousehold.id()                   — household id (creates one if missing)
 *   NHHousehold.members()              — array of members
 *   NHHousehold.addMember(member)      — append a member
 *   NHHousehold.removeMember(name)     — remove by name (case-insensitive)
 *   NHHousehold.preference(key, val?)  — get-or-set a preference
 *   NHHousehold.subscribe(handler)     — call handler on any change
 *
 * Member schema:
 *   { name: "Sarah", role: "parent"|"child"|"member", birth_year?: 1985 }
 *
 * Preferences:
 *   sabbath_mode: bool       — when true, sites that respect it show quiet-Sunday view
 *   kids_safe_mode: bool     — when true, kid-friendly defaults across decks
 *   default_reading_plan: "mcheyne"|"chronological"|"90day"|"codex_pilgrim"|null
 *   default_age_tier: "k"|"1-2"|"3-5"|"6-8"|"9-12"|null  (curriculum default)
 */
(function (global) {
  const KEY = 'narrowhighway_household_v1';
  const VERSION = 1;
  const subs = [];

  function emit() {
    const cur = read();
    subs.forEach(function (h) {
      try { h(cur); } catch (e) { console.warn('NHHousehold subscriber:', e); }
    });
  }

  function read() {
    try {
      const raw = localStorage.getItem(KEY);
      if (!raw) return null;
      const obj = JSON.parse(raw);
      if (!obj || obj.schema_version !== VERSION) return null;
      return obj;
    } catch (e) { return null; }
  }

  function write(obj) {
    try {
      obj.schema_version = VERSION;
      obj.updated_at = new Date().toISOString();
      localStorage.setItem(KEY, JSON.stringify(obj));
      emit();
      return obj;
    } catch (e) {
      console.warn('NHHousehold write failed:', e);
      return null;
    }
  }

  function genId() {
    const buf = new Uint8Array(8);
    if (window.crypto && crypto.getRandomValues) crypto.getRandomValues(buf);
    else for (let i = 0; i < 8; i++) buf[i] = Math.floor(Math.random() * 256);
    return 'hh_' + Array.from(buf).map(function (b) { return b.toString(16).padStart(2, '0'); }).join('');
  }

  const NHHousehold = {
    /** Get the current household, or null if not set up. */
    get: read,

    /** Create or overwrite the household. */
    create: function (hh) {
      const obj = Object.assign({
        id: hh.id || genId(),
        name: 'Our household',
        created_at: new Date().toISOString(),
        members: [],
        preferences: {
          sabbath_mode: false,
          kids_safe_mode: false,
          default_reading_plan: null,
          default_age_tier: null,
        },
      }, hh);
      // Ensure id and stable created_at
      if (!obj.id) obj.id = genId();
      return write(obj);
    },

    /** Shallow merge a partial update into the existing household. */
    patch: function (partial) {
      const cur = read() || this.create({});
      const next = Object.assign({}, cur, partial);
      // Don't let patch wipe preferences/members structurally
      next.preferences = Object.assign({}, cur.preferences || {}, partial.preferences || {});
      next.members = partial.members || cur.members || [];
      return write(next);
    },

    /** Remove the household entirely. */
    clear: function () {
      try { localStorage.removeItem(KEY); } catch (_) {}
      emit();
    },

    /** Get the household id (creates a fresh blank household if none exists). */
    id: function () {
      const cur = read();
      if (cur && cur.id) return cur.id;
      const made = this.create({});
      return made && made.id;
    },

    /** Members list (always an array). */
    members: function () {
      const cur = read();
      return (cur && cur.members) || [];
    },

    /** Append a member. Doesn't dedupe — call removeMember first if you want to replace. */
    addMember: function (member) {
      const cur = read() || this.create({});
      cur.members = (cur.members || []).slice();
      cur.members.push(Object.assign({ role: 'member' }, member));
      return write(cur);
    },

    /** Remove a member by name (case-insensitive). */
    removeMember: function (name) {
      const cur = read();
      if (!cur) return null;
      const n = (name || '').toLowerCase();
      cur.members = (cur.members || []).filter(function (m) {
        return (m.name || '').toLowerCase() !== n;
      });
      return write(cur);
    },

    /** Get or set a single preference. With one arg, returns the value. With two, sets it. */
    preference: function (key, value) {
      const cur = read() || this.create({});
      cur.preferences = cur.preferences || {};
      if (value === undefined) return cur.preferences[key];
      cur.preferences[key] = value;
      return write(cur);
    },

    /** Subscribe to changes. Returns unsubscribe function. */
    subscribe: function (handler) {
      subs.push(handler);
      return function () {
        const i = subs.indexOf(handler);
        if (i >= 0) subs.splice(i, 1);
      };
    },

    /**
     * Storage helper for tools that want to keep household-scoped data
     * (e.g. Common Book entries, reading-plan progress, calendar events).
     * Returns a small API that reads/writes a separate localStorage key
     * namespaced by the current household id.
     */
    namespace: function (toolKey) {
      const self = this;
      function k() { return 'narrowhighway_' + toolKey + '_' + self.id(); }
      return {
        get: function () {
          try { return JSON.parse(localStorage.getItem(k()) || 'null'); } catch (_) { return null; }
        },
        set: function (obj) {
          try { localStorage.setItem(k(), JSON.stringify(obj)); return true; } catch (_) { return false; }
        },
        update: function (fn) {
          const cur = this.get();
          const next = fn(cur) || cur;
          this.set(next);
          return next;
        },
        clear: function () { try { localStorage.removeItem(k()); } catch (_) {} },
      };
    },
  };

  global.NHHousehold = NHHousehold;
})(typeof window !== 'undefined' ? window : this);
