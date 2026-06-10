/**
 * Narrow Highway Subscription Scheduler v1.
 *
 * Pure-JS schedule generator. Mixes user's subscribed services with our PD
 * library catalog. Outputs a per-daypart array of items, each either:
 *   - kind: 'ours'  — play inline (we have the show)
 *   - kind: 'theirs' — deep-link out to a service the user subscribes to
 *
 * Storage in localStorage:
 *   nh.subscriptions — string[] of service IDs
 *   nh.tastes        — { familyMode, lengthCap, dayparts, genres, pace }
 *   nh.progress      — { [slug]: { episode_idx, position_sec } }
 *   nh.pinned        — { [show_id]: { service, s, e, title } }
 *
 * NEVER auths into any service. Deep-links only.
 */
(function () {
  const SERVICES = [
    { id: 'netflix',      label: 'Netflix',      emoji: '🎬', tier: 'video' },
    { id: 'disney_plus',  label: 'Disney+',      emoji: '✨', tier: 'video' },
    { id: 'hulu',         label: 'Hulu',         emoji: '🟢', tier: 'video' },
    { id: 'max',          label: 'Max',          emoji: '🔵', tier: 'video' },
    { id: 'apple_tv',     label: 'Apple TV+',    emoji: '🍎', tier: 'video' },
    { id: 'paramount',    label: 'Paramount+',   emoji: '🏔', tier: 'video' },
    { id: 'prime',        label: 'Prime Video',  emoji: '📦', tier: 'video' },
    { id: 'peacock',      label: 'Peacock',      emoji: '🦚', tier: 'video' },
    { id: 'amc_plus',     label: 'AMC+',         emoji: '🎭', tier: 'video' },
    { id: 'britbox',      label: 'BritBox',      emoji: '🇬🇧', tier: 'video' },
    { id: 'mubi',         label: 'MUBI',         emoji: '🎞', tier: 'video' },
    { id: 'criterion',    label: 'Criterion',    emoji: '🎯', tier: 'video' },
    { id: 'spotify',      label: 'Spotify',      emoji: '🎵', tier: 'audio' },
    { id: 'apple_music',  label: 'Apple Music',  emoji: '🎶', tier: 'audio' },
    { id: 'amazon_music', label: 'Amazon Music', emoji: '🎼', tier: 'audio' },
    { id: 'pandora',      label: 'Pandora',      emoji: '📻', tier: 'audio' },
    { id: 'audible',      label: 'Audible',      emoji: '📚', tier: 'audiobook' },
    { id: 'libby',        label: 'Libby',        emoji: '🏛', tier: 'audiobook' },
    { id: 'hoopla',       label: 'Hoopla',       emoji: '📖', tier: 'audiobook' },
    { id: 'kanopy',       label: 'Kanopy',       emoji: '🎓', tier: 'video' },
  ];

  const SERVICE_BY_ID = Object.fromEntries(SERVICES.map(s => [s.id, s]));

  const DEFAULT_TASTES = {
    familyMode: true,
    lengthCap: 60,           // max minutes per item
    dayparts: ['evening'],   // which dayparts to schedule
    genres: ['comedy','drama','family','western'],
    pace: 'one_and_done',    // 'one_and_done' | 'few_eps' | 'marathon'
    sabbathMode: false,      // Sunday-morning Scripture-only override
  };

  const DAYPARTS = [
    { id: 'morning',    label: 'Morning',    startHr: 6,  endHr: 11 },
    { id: 'daytime',    label: 'Daytime',    startHr: 11, endHr: 17 },
    { id: 'family',     label: 'Family',     startHr: 17, endHr: 20 },   // dinner & after
    { id: 'evening',    label: 'Evening',    startHr: 20, endHr: 23 },
    { id: 'late_night', label: 'Late Night', startHr: 23, endHr: 26 },   // 26 = 2am next day
  ];

  // Soft-bucket our PD catalog categories into "what's appropriate when"
  const CATEGORY_FIT = {
    // family-block (17-20): kid- and family-safe stuff goes here
    family: {
      bonus: ['children','animation','fishing','western'],
      avoid: ['vegas'], // adult-coded variety
    },
    // evening (20-23): drama, comedy, mystery, action
    evening: {
      bonus: ['pd_tv','western','radio','vegas','sports'],
      avoid: [],
    },
    // late_night (23-26): radio, sermon, contemplative
    late_night: {
      bonus: ['sermon','radio','bible_audio','performances'],
      avoid: ['animation'],
    },
    // morning (6-11): scripture, sermon, devotion
    morning: {
      bonus: ['bible_audio','sermon','radio'],
      avoid: ['vegas','sports'],
    },
    // daytime (11-17): mixed
    daytime: {
      bonus: ['radio','animation','pd_tv'],
      avoid: [],
    },
  };

  // ── Public API ───────────────────────────────────────────
  const NH = window.NH || (window.NH = {});
  const Sched = NH.Sched = {};

  Sched.SERVICES = SERVICES;
  Sched.DAYPARTS = DAYPARTS;
  Sched.DEFAULT_TASTES = DEFAULT_TASTES;

  Sched.getSubscriptions = function () {
    try { return JSON.parse(localStorage.getItem('nh.subscriptions') || '[]'); }
    catch (e) { return []; }
  };
  Sched.setSubscriptions = function (ids) {
    localStorage.setItem('nh.subscriptions', JSON.stringify(ids || []));
  };
  Sched.getTastes = function () {
    try {
      const stored = JSON.parse(localStorage.getItem('nh.tastes') || '{}');
      return Object.assign({}, DEFAULT_TASTES, stored);
    } catch (e) { return Object.assign({}, DEFAULT_TASTES); }
  };
  Sched.setTastes = function (tastes) {
    localStorage.setItem('nh.tastes', JSON.stringify(tastes || {}));
  };
  Sched.getProgress = function (slug) {
    try {
      const p = JSON.parse(localStorage.getItem('nh.progress') || '{}');
      return slug ? (p[slug] || null) : p;
    } catch (e) { return slug ? null : {}; }
  };
  Sched.setProgress = function (slug, idx, posSec) {
    try {
      const p = JSON.parse(localStorage.getItem('nh.progress') || '{}');
      p[slug] = { episode_idx: idx, position_sec: posSec || 0, t: Date.now() };
      localStorage.setItem('nh.progress', JSON.stringify(p));
    } catch (e) {}
  };
  Sched.getPinned = function () {
    try { return JSON.parse(localStorage.getItem('nh.pinned') || '[]'); }
    catch (e) { return []; }
  };
  Sched.setPinned = function (list) {
    localStorage.setItem('nh.pinned', JSON.stringify(list || []));
  };

  // ── Schedule generator ───────────────────────────────────
  /**
   * generateSchedule({ catalog, subscriptions, tastes, pinned, date, dayparts })
   *   catalog       — { shows: [{ slug, title, category, episodes: [...] }, ...] }
   *   subscriptions — string[] of service IDs the user has
   *   tastes        — { familyMode, lengthCap, dayparts, genres, pace }
   *   pinned        — [{ service, title, url, lastSeason, lastEp }, ...]
   *   date          — Date (defaults to now)
   *   dayparts      — string[] (defaults to all from tastes)
   * Returns: ScheduleItem[]
   */
  Sched.generateSchedule = function (opts) {
    opts = opts || {};
    const catalog = opts.catalog || { shows: [] };
    const subs = opts.subscriptions || Sched.getSubscriptions();
    const tastes = Object.assign({}, DEFAULT_TASTES, opts.tastes || Sched.getTastes());
    const pinned = opts.pinned || Sched.getPinned();
    const date = opts.date || new Date();
    const wantedDayparts = opts.dayparts || tastes.dayparts || ['evening'];

    const dayOfWeek = date.getDay(); // 0=Sun
    const isSunday = dayOfWeek === 0;
    const progress = Sched.getProgress();

    const items = [];
    const usedSlugs = new Set();  // don't repeat shows in same schedule
    const usedPins = new Set();

    for (const dpId of wantedDayparts) {
      const dp = DAYPARTS.find(d => d.id === dpId);
      if (!dp) continue;

      // How many half-hour slots in this daypart?
      const totalMin = (dp.endHr - dp.startHr) * 60;
      const slotMin = 30; // default slot length; some items use 60 if length > 30
      let cursorMin = 0;

      // Sabbath override (Sunday morning)
      const sabbathBlock = isSunday && dp.id === 'morning' && tastes.sabbathMode !== false;
      const fit = CATEGORY_FIT[dp.id] || { bonus: [], avoid: [] };
      const bonus = sabbathBlock ? ['bible_audio','sermon','radio'] : fit.bonus;
      const avoid = sabbathBlock ? ['vegas','sports','animation'] : fit.avoid;

      while (cursorMin < totalMin) {
        const slotHr = dp.startHr + Math.floor(cursorMin / 60);
        const slotMinOfHr = cursorMin % 60;
        const timeLabel = formatTime(slotHr % 24, slotMinOfHr);

        // Decide: ours or theirs?
        // Rule: family block prefers OURS; evening alternates; sabbath = OURS only
        let pickOurs;
        if (sabbathBlock) pickOurs = true;
        else if (dp.id === 'family' && tastes.familyMode) pickOurs = Math.random() < 0.7;
        else if (dp.id === 'late_night') pickOurs = Math.random() < 0.85; // mostly our radio at night
        else pickOurs = (subs.length === 0) ? true : Math.random() < 0.55;

        let item;
        if (pickOurs) {
          item = pickOurContent(catalog, usedSlugs, bonus, avoid, tastes, progress);
        } else {
          item = pickTheirContent(pinned, subs, usedPins, tastes);
          // If we couldn't find anything from theirs, fall back to ours
          if (!item) item = pickOurContent(catalog, usedSlugs, bonus, avoid, tastes, progress);
        }
        if (!item) break;

        item.time = timeLabel;
        item.daypart = dp.id;
        items.push(item);

        // Mark used
        if (item.kind === 'ours' && item.slug) usedSlugs.add(item.slug);
        if (item.kind === 'theirs' && item.pinKey) usedPins.add(item.pinKey);

        cursorMin += item.length_min || slotMin;
      }
    }

    return items;
  };

  function pickOurContent(catalog, usedSlugs, bonusCats, avoidCats, tastes, progress) {
    if (!catalog || !catalog.shows) return null;
    // Score each show
    const candidates = catalog.shows
      .filter(s => !usedSlugs.has(s.slug))
      .filter(s => !avoidCats.includes(s.category))
      .map(s => {
        let score = 1;
        if (bonusCats.includes(s.category)) score += 3;
        if (s.episode_count > 1) score += 0.5; // multi-episode shows are good for sequencing
        return { show: s, score };
      })
      .sort((a, b) => b.score - a.score + (Math.random() - 0.5) * 0.6);

    const top = candidates[0];
    if (!top) return null;
    const show = top.show;

    // Determine which episode to play
    const prog = progress[show.slug];
    let epIdx = 0;
    if (prog && prog.episode_idx != null) {
      // play next-after-last-watched
      epIdx = (prog.episode_idx + 1) % show.episodes.length;
    }
    const ep = show.episodes[epIdx];

    return {
      kind: 'ours',
      slug: show.slug,
      title: show.title,
      ep_idx: epIdx,
      ep_title: ep && (ep.title || ep.filename) || '',
      ep_size_mb: ep && ep.size_mb,
      category: show.category,
      length_min: 30, // best guess; real durations not in metadata yet
      deeplink: deeplinkOurs(show.slug, epIdx),
      blurb: `${show.episode_count} eps total · ${show.category.replace(/_/g,' ')}`,
    };
  }

  function pickTheirContent(pinned, subs, usedPins, tastes) {
    // Pinned shows are user-curated; prefer those whose service the user has
    const eligible = (pinned || []).filter(p =>
      p.service && subs.includes(p.service) && !usedPins.has(pinKey(p))
    );
    if (!eligible.length) return null;
    const pick = eligible[Math.floor(Math.random() * eligible.length)];
    const svc = SERVICE_BY_ID[pick.service];

    return {
      kind: 'theirs',
      title: pick.title || (svc?.label + ' show'),
      service_id: pick.service,
      service_label: svc?.label || pick.service,
      service_emoji: svc?.emoji || '📺',
      s: pick.s,
      e: pick.e,
      url: pick.url,
      pinKey: pinKey(pick),
      length_min: 60,
      blurb: pick.s != null ? `S${pick.s} E${pick.e ?? 1}` : 'queued',
    };
  }

  function pinKey(p) {
    return (p.service || '') + ':' + (p.title || p.url || '');
  }

  function deeplinkOurs(slug, epIdx) {
    return '/watch.html?show=' + encodeURIComponent(slug) + (epIdx ? '&ep=' + epIdx : '');
  }

  function formatTime(hr, min) {
    const period = hr >= 12 ? 'PM' : 'AM';
    const h = hr === 0 ? 12 : (hr > 12 ? hr - 12 : hr);
    const m = String(min).padStart(2, '0');
    return `${h}:${m} ${period}`;
  }

  Sched.formatTime = formatTime;
})();
