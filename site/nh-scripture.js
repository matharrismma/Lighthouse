/* nh-scripture.js — Auto-link scripture references to the Codex.
 *
 * Walks the DOM (text nodes inside .nh-auto-scripture containers OR all <p>/<li>
 * by default) and replaces matched references like "John 3:16", "Psa 23",
 * "Genesis 1:1-3", "1 Cor 13:1-13" with clickable links.
 *
 * Link target: /canon.html?ref=<encoded reference>
 *   (Codex page can read the ?ref param and jump to that passage.)
 *
 * Opt-out:
 *   <p class="nh-no-scripture-link">...</p>
 * Opt-in narrowly:
 *   <section class="nh-auto-scripture">...</section>   (limits scanning to this section)
 *
 * The matcher is conservative — only canonical book abbreviations + a
 * "X:Y" or "X:Y-Z" pattern. Won't false-positive on phone numbers / dates.
 */
(function (global) {
  // Canonical book name patterns. Order matters — longer first so "1 Cor" doesn't get
  // half-matched as "Cor" later.
  const BOOKS = [
    // Pentateuch
    'Gen(?:esis)?', 'Ex(?:od|odus)?', 'Lev(?:iticus)?', 'Num(?:bers)?', 'Deut(?:eronomy)?',
    // Historical
    'Josh(?:ua)?', 'Judg(?:es)?', 'Ruth',
    '1\\s?Sam(?:uel)?', '2\\s?Sam(?:uel)?', '1\\s?Kgs|1\\s?Kings', '2\\s?Kgs|2\\s?Kings',
    '1\\s?Chr(?:on|onicles)?', '2\\s?Chr(?:on|onicles)?',
    'Ezra', 'Neh(?:emiah)?', 'Esth(?:er)?',
    // Wisdom + Poetry
    'Job', 'Ps(?:a|alm|alms)?', 'Pro(?:v|verbs)?', 'Eccl(?:es|esiastes)?', 'Song(?:\\s?of\\s?Sol(?:omon)?)?', 'SoS',
    // Prophets
    'Isa(?:iah)?', 'Jer(?:emiah)?', 'Lam(?:entations)?', 'Ezek(?:iel)?', 'Dan(?:iel)?',
    'Hos(?:ea)?', 'Joel', 'Amos', 'Obad(?:iah)?', 'Jon(?:ah)?', 'Mic(?:ah)?', 'Nah(?:um)?',
    'Hab(?:akkuk)?', 'Zeph(?:aniah)?', 'Hag(?:gai)?', 'Zech(?:ariah)?', 'Mal(?:achi)?',
    // Gospels + Acts
    'Matt(?:hew)?', 'Mark', 'Luke', 'John', 'Acts',
    // Pauline epistles
    'Rom(?:ans)?', '1\\s?Cor(?:inthians)?', '2\\s?Cor(?:inthians)?', 'Gal(?:atians)?', 'Eph(?:esians)?',
    'Phil(?:ippians)?', 'Col(?:ossians)?', '1\\s?Thess(?:alonians)?', '2\\s?Thess(?:alonians)?',
    '1\\s?Tim(?:othy)?', '2\\s?Tim(?:othy)?', 'Tit(?:us)?', 'Phlm|Philemon',
    // General + Revelation
    'Heb(?:rews)?', 'Jas|James', '1\\s?Pet(?:er)?', '2\\s?Pet(?:er)?',
    '1\\s?John', '2\\s?John', '3\\s?John', 'Jude', 'Rev(?:elation)?',
  ];

  // Build the master regex once: (\b BOOK \s+ CHAPTER (?: : VERSE (?: - VERSE )? )? \b)
  const bookPattern = BOOKS.join('|');
  const RE = new RegExp(
    '\\b(' + bookPattern + ')\\s+(\\d{1,3})(?::(\\d{1,3})(?:[-–](\\d{1,3}))?)?',
    'g'
  );

  function linkify(text) {
    return text.replace(RE, function (match, book, ch, v1, v2) {
      const ref = book.replace(/\s+/g, ' ').trim() + ' ' + ch + (v1 ? ':' + v1 + (v2 ? '-' + v2 : '') : '');
      const url = '/canon.html?ref=' + encodeURIComponent(ref);
      return '<a class="nh-scripture-link" href="' + url + '" data-ref="' +
        ref.replace(/"/g, '&quot;') + '">' + match + '</a>';
    });
  }

  function isOptedOut(node) {
    let p = node;
    while (p && p !== document.body) {
      if (p.classList && p.classList.contains('nh-no-scripture-link')) return true;
      if (p.tagName === 'A' || p.tagName === 'CODE' || p.tagName === 'PRE') return true;
      if (p.tagName === 'SCRIPT' || p.tagName === 'STYLE') return true;
      p = p.parentNode;
    }
    return false;
  }

  function walkAndReplace(root) {
    const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        if (!n.nodeValue || !n.nodeValue.trim()) return NodeFilter.FILTER_REJECT;
        if (isOptedOut(n.parentNode)) return NodeFilter.FILTER_REJECT;
        if (!RE.test(n.nodeValue)) return NodeFilter.FILTER_REJECT;
        RE.lastIndex = 0;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    const to_replace = [];
    while (walker.nextNode()) to_replace.push(walker.currentNode);
    to_replace.forEach(function (n) {
      const linked = linkify(n.nodeValue);
      if (linked !== n.nodeValue) {
        const span = document.createElement('span');
        span.innerHTML = linked;
        n.parentNode.replaceChild(span, n);
      }
    });
  }

  function injectStyles() {
    if (document.getElementById('nh-scripture-styles')) return;
    const s = document.createElement('style');
    s.id = 'nh-scripture-styles';
    s.textContent = (
      '.nh-scripture-link {' +
      '  color: inherit;' +
      '  border-bottom: 1px dotted rgba(26, 58, 82, 0.5);' +
      '  text-decoration: none;' +
      '  cursor: help;' +
      '}' +
      '.nh-scripture-link:hover {' +
      '  background: #fff5d4;' +
      '  color: #1a3a52;' +
      '  border-bottom-style: solid;' +
      '}'
    );
    document.head.appendChild(s);
  }

  function run() {
    injectStyles();
    // If page explicitly scopes scanning, honor it; otherwise scan main content.
    const scoped = document.querySelectorAll('.nh-auto-scripture');
    if (scoped.length > 0) {
      scoped.forEach(walkAndReplace);
    } else {
      // Default scope: <article>, <main>, .intro, .card body — common content containers
      ['article', 'main', '.intro', '.card', '.entry', '.recipe-view', '.project-view',
       '.what-this-unlocks', '.principles', '.feast-card'].forEach(function (sel) {
        document.querySelectorAll(sel).forEach(walkAndReplace);
      });
    }
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', run);
  } else {
    run();
  }

  global.NHScripture = { run: run, linkify: linkify };
})(typeof window !== 'undefined' ? window : this);
