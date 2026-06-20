"""
canon.py — Tradition-aware biblical canon as a SEPARATE LAYER.

The operator's directive (literal):
  "Treat canon as a separate layer. We don't judge, but we don't include
   disputed books with the 66 books that are not disputed. We show it
   honestly and historically framed. Let the user discern."

So this module models canon as concentric LAYERS, with disputed books kept
strictly SEPARATE from the undisputed core:

  * UNDISPUTED_66       — the Protestant 66, the core all major traditions
                          share. Derived from verifiers/scripture._CANON_BOOKS
                          so there is ONE source of truth for the 66.
  * TRADITION_ADDITIONS — books each tradition adds BEYOND the 66, each with
                          an honest one-line historical frame. The disputed
                          books are never merged into the 66; they are reported
                          on their own layer.

The engine SHOWS who holds what plus the history. It does NOT rule which canon
is "correct" — conduit, not source; it points to Christ, not to itself as an
arbiter (it is not an idol). The map never launders: the historical frames here
are kept factual and the genuine uncertainty in some enumerations (especially
the Ethiopian Tewahedo canon) is flagged honestly rather than overstated.

Sovereign: stdlib-only. No external dependencies.

Usage:
    from concordance_engine import canon
    canon.canon_status("John")     # → in_undisputed_66=True, held_by=["all"]
    canon.canon_status("Tobit")    # → in_undisputed_66=False, held_by=[catholic, ...]
    canon.canon_status("Enoch")    # → in_undisputed_66=False, held_by=[ethiopian_orthodox]
    canon.canon_status("Znope")    # → in_undisputed_66=False, held_by=[]  (likely typo)
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# UNDISPUTED 66 — the shared core.
# ---------------------------------------------------------------------------
# We do NOT re-type the 66 here; we derive the name/abbreviation set from the
# verifier's existing _CANON_BOOKS so there is a single source of truth. If the
# import ever fails (e.g. the canon module is used in isolation), we fall back
# to a minimal mirror so canon_status still functions — but the primary path is
# the import, keeping the two in lockstep.
try:  # pragma: no cover - import wiring
    from .verifiers.scripture import _CANON_BOOKS as _UNDISPUTED_66_FORMS
except Exception:  # pragma: no cover - defensive fallback only
    # Minimal fallback mirror (full names only). The verifier's set is the
    # authoritative one; this exists solely so the module never hard-crashes
    # if imported before/without the verifier package.
    _UNDISPUTED_66_FORMS = {
        "genesis", "exodus", "leviticus", "numbers", "deuteronomy",
        "joshua", "judges", "ruth", "1 samuel", "2 samuel",
        "1 kings", "2 kings", "1 chronicles", "2 chronicles", "ezra",
        "nehemiah", "esther", "job", "psalms", "proverbs", "ecclesiastes",
        "song of solomon", "isaiah", "jeremiah", "lamentations", "ezekiel",
        "daniel", "hosea", "joel", "amos", "obadiah", "jonah", "micah",
        "nahum", "habakkuk", "zephaniah", "haggai", "zechariah", "malachi",
        "matthew", "mark", "luke", "john", "acts", "romans",
        "1 corinthians", "2 corinthians", "galatians", "ephesians",
        "philippians", "colossians", "1 thessalonians", "2 thessalonians",
        "1 timothy", "2 timothy", "titus", "philemon", "hebrews", "james",
        "1 peter", "2 peter", "1 john", "2 john", "3 john", "jude",
        "revelation",
    }

# A frozenset of all accepted name/abbreviation forms for the 66, lower-cased.
# This includes the abbreviations the verifier already accepts ("gen", "jn",
# "1cor", ...), so canon_status agrees with the verifier on what is "in the 66".
UNDISPUTED_66: frozenset = frozenset(b.lower() for b in _UNDISPUTED_66_FORMS)


# ---------------------------------------------------------------------------
# TRADITION_ADDITIONS — books held BEYOND the 66, kept on their own layer.
# ---------------------------------------------------------------------------
# Each entry: tradition key -> {
#     "label":  human-readable tradition name,
#     "frame":  one-line honest historical frame for these additions,
#     "books":  { canonical_lower_name: [accepted forms / aliases, lower] },
# }
#
# HONESTY NOTE ON ENUMERATION: the exact contents and counts of these expanded
# canons vary by source, edition, and how one counts composite books and the
# Greek additions. We name the standard lists below and flag the uncertainty
# explicitly — most acutely for the Ethiopian Tewahedo canon, whose "81" and
# "88" book counts are themselves debated. The frames below describe history,
# not a verdict on which canon is true.

TRADITION_ADDITIONS: Dict[str, Dict[str, Any]] = {
    # ── Roman Catholic deuterocanon ──────────────────────────────────────
    # Fixed dogmatically at the Council of Trent (4th session, 1546). These
    # books stood in the Septuagint (the Greek OT the early church largely
    # used); Jerome, translating the Vulgate, doubted them and called them
    # "apocrypha" (worth reading, not for establishing doctrine). Trent
    # affirmed them as canonical, partly in response to the Reformation.
    "catholic": {
        "label": "Roman Catholic (deuterocanon, Council of Trent, 1546)",
        "frame": (
            "Present in the Septuagint (the Greek Old Testament used by much "
            "of the early church); Jerome doubted them and labeled them "
            '"apocrypha"; affirmed as canonical by the Council of Trent in '
            "1546, in response to the Reformation."
        ),
        "books": {
            "tobit": ["tobit", "tob", "tb"],
            "judith": ["judith", "jdt", "jth"],
            # "Wisdom of Solomon" — distinct from canonical Proverbs/Ecclesiastes.
            "wisdom of solomon": ["wisdom of solomon", "wisdom", "wis", "ws"],
            # Sirach = Ecclesiasticus (NOT Ecclesiastes, which is in the 66).
            "sirach": ["sirach", "ecclesiasticus", "sir", "ecclus"],
            "baruch": ["baruch", "bar"],
            "1 maccabees": ["1 maccabees", "1maccabees", "1 macc", "1macc", "1 mac", "1mac"],
            "2 maccabees": ["2 maccabees", "2maccabees", "2 macc", "2macc", "2 mac", "2mac"],
            # Greek additions to Esther (extra chapters in the LXX Esther).
            "additions to esther": [
                "additions to esther", "greek esther", "esther (greek)",
                "rest of esther", "additions of esther",
            ],
            # Greek additions to Daniel: in Catholic Bibles these are folded
            # INTO the book of Daniel, but the underlying texts are the
            # disputed material, so we enumerate them on this layer.
            "prayer of azariah": [
                "prayer of azariah", "song of the three young men",
                "song of the three holy children", "azariah",
            ],
            "susanna": ["susanna", "sus"],
            "bel and the dragon": ["bel and the dragon", "bel", "bel and dragon"],
            # The Letter of Jeremiah is, in Catholic Bibles, Baruch chapter 6;
            # in some traditions it is counted separately. Listed for clarity.
            "letter of jeremiah": ["letter of jeremiah", "epistle of jeremiah", "ep jer"],
        },
    },

    # ── Eastern Orthodox (anagignoskomena) ───────────────────────────────
    # The Orthodox receive the Catholic deuterocanon PLUS several more books,
    # through the Septuagint / Byzantine tradition. The Synod of Jerusalem
    # (1672) is the usual reference point for their formal reception. They are
    # called "anagignoskomena" — "things that are read" / "worthy to be read."
    # NOTE: only the books BEYOND the Catholic set are listed here; the
    # Catholic deuterocanon is held by Orthodoxy too (reflected in held_by via
    # the lookup below). 4 Maccabees often appears as an appendix rather than
    # as fully canonical — flagged accordingly.
    "eastern_orthodox": {
        "label": "Eastern Orthodox (anagignoskomena; Synod of Jerusalem, 1672)",
        "frame": (
            "Received through the Septuagint / Byzantine tradition and called "
            'anagignoskomena ("worthy to be read"); the Synod of Jerusalem '
            "(1672) is a common reference point for their formal reception. "
            "These are held in ADDITION to the Catholic deuterocanon. "
            "(4 Maccabees commonly appears as an appendix rather than as fully "
            "canonical — counts vary by jurisdiction and edition.)"
        ),
        "books": {
            # 1 Esdras (LXX) — NOT the same numbering as Ezra/Nehemiah; the
            # naming of Esdras books is notoriously tangled across traditions.
            "1 esdras": ["1 esdras", "1esdras", "1 esd", "1esd", "3 ezra", "3 esdras"],
            "3 maccabees": ["3 maccabees", "3maccabees", "3 macc", "3macc", "3 mac", "3mac"],
            "psalm 151": ["psalm 151", "ps 151", "psalm151"],
            "prayer of manasseh": ["prayer of manasseh", "manasseh", "pr man", "pr of man"],
            # Appendix in many Orthodox Bibles; canonical status varies.
            "4 maccabees": ["4 maccabees", "4maccabees", "4 macc", "4macc", "4 mac", "4mac"],
        },
    },

    # ── Ethiopian Orthodox Tewahedo (the broadest received canon) ─────────
    # The Ethiopian Tewahedo Church has the LARGEST canon of any church.
    # HONESTY: the exact enumeration is genuinely DEBATED and varies by
    # source. A "narrower" canon is often cited as ~81 books and a "broader"
    # canon as ~88; even those numbers are contested because books are counted
    # and combined differently, and some lists circulate that scholars dispute.
    # Treat the count as approximate. Distinctive additional books include
    # 1 Enoch (Henok) — quoted in Jude 1:14-15 — Jubilees (Kufale), and the
    # three books of Meqabyan (which are NOT the Greek Maccabees, despite the
    # similar name). Listed below are the DISTINCTIVE additions most sources
    # agree on; this is not presented as a complete or settled enumeration.
    "ethiopian_orthodox": {
        "label": "Ethiopian Orthodox Tewahedo (broadest received canon; ~81 narrower / ~88 broader — counts debated)",
        "frame": (
            "The largest canon received by any church. The exact enumeration "
            "is debated and varies by source: a narrower sense is often cited "
            "as about 81 books and a broader sense as about 88, but those "
            "counts are themselves contested (books are combined and counted "
            "differently). Distinctive additions include 1 Enoch (Henok) — "
            "which Jude 1:14-15 quotes — Jubilees (Kufale), the three books of "
            "Meqabyan (NOT the Greek Maccabees), and others. The list here is "
            "the distinctive core, not a settled, complete enumeration."
        ),
        "books": {
            "1 enoch": ["1 enoch", "enoch", "henok", "1enoch", "i enoch", "book of enoch"],
            "jubilees": ["jubilees", "kufale", "book of jubilees", "jub"],
            # Meqabyan 1-3 — Ethiopian books, distinct from 1-4 Maccabees.
            "1 meqabyan": ["1 meqabyan", "1meqabyan", "meqabyan 1", "1 mekabyan"],
            "2 meqabyan": ["2 meqabyan", "2meqabyan", "meqabyan 2", "2 mekabyan"],
            "3 meqabyan": ["3 meqabyan", "3meqabyan", "meqabyan 3", "3 mekabyan"],
            # 4 Baruch = Paralipomena of Jeremiah (Rest of the Words of Baruch).
            "4 baruch": [
                "4 baruch", "4baruch", "paralipomena of jeremiah",
                "rest of the words of baruch", "remainder of the words of baruch",
            ],
        },
    },
}


# ---------------------------------------------------------------------------
# Lookup index: alias -> (tradition_key, canonical_book_name)
# ---------------------------------------------------------------------------
# A single book can be held by more than one tradition (e.g. Tobit is held by
# both Catholic and Eastern Orthodox). We therefore map each alias to a list of
# (tradition_key, canonical_name) so canon_status can report ALL holders.
#
# Holding rule:
#   - A book listed under "catholic" is also held by Eastern Orthodox (the
#     Orthodox receive the full Catholic deuterocanon).
#   - Books listed under "eastern_orthodox" are the Orthodox-only additions.
#   - Ethiopian additions are listed on their own (the Ethiopian canon also
#     overlaps the deuterocanon, but here we only assert holders we can state
#     with confidence per book; see _holders_for_canonical).

def _build_alias_index() -> Dict[str, str]:
    """alias(lower) -> canonical lower book name. Across all traditions."""
    idx: Dict[str, str] = {}
    for trad in TRADITION_ADDITIONS.values():
        for canonical, aliases in trad["books"].items():
            for a in aliases:
                idx[a.lower()] = canonical
            idx[canonical.lower()] = canonical
    return idx


_ALIAS_INDEX: Dict[str, str] = _build_alias_index()


def _holders_for_canonical(canonical: str) -> List[str]:
    """Return the list of tradition keys that hold `canonical` (a disputed
    book), applying the nesting rule (Orthodox holds the Catholic set too)."""
    holders: List[str] = []
    in_catholic = canonical in TRADITION_ADDITIONS["catholic"]["books"]
    in_orthodox_only = canonical in TRADITION_ADDITIONS["eastern_orthodox"]["books"]
    in_ethiopian = canonical in TRADITION_ADDITIONS["ethiopian_orthodox"]["books"]

    if in_catholic:
        holders.append("catholic")
        # Eastern Orthodox AND Ethiopian Tewahedo (the broadest canon) both
        # receive the full Catholic deuterocanon.
        holders.append("eastern_orthodox")
        holders.append("ethiopian_orthodox")
    if in_orthodox_only and "eastern_orthodox" not in holders:
        holders.append("eastern_orthodox")
        # NOTE: some Orthodox-only Greek books (e.g. 3 Maccabees) are genuinely
        # debated for the Ethiopian canon, so Ethiopian is NOT auto-asserted here
        # — only for the Catholic deuterocanon (above) and its own distinctives.
    if in_ethiopian and "ethiopian_orthodox" not in holders:
        holders.append("ethiopian_orthodox")
    return holders


def _historical_note_for(holders: List[str], canonical: str) -> str:
    """Compose an honest historical frame from the holders' frames."""
    if not holders:
        return (
            "not found in any known canon (likely a typo or non-scriptural "
            "reference)"
        )
    parts: List[str] = []
    for key in holders:
        trad = TRADITION_ADDITIONS.get(key)
        if trad:
            parts.append(f"{trad['label']}: {trad['frame']}")
    # Special, accurate cross-note: 1 Enoch is quoted in Jude (canonical 66).
    if canonical == "1 enoch":
        parts.append(
            "Note: 1 Enoch is directly quoted in Jude 1:14-15, a book in the "
            "undisputed 66 — quotation is not the same as canonization, but it "
            "is part of why the Ethiopian church received it."
        )
    return " | ".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def is_in_undisputed_66(book_name: str) -> bool:
    """True iff `book_name` (full name or accepted abbreviation) is one of the
    undisputed 66. Case-insensitive; whitespace-normalized."""
    if not book_name:
        return False
    key = " ".join(str(book_name).strip().lower().split())
    if key in UNDISPUTED_66:
        return True
    # Also try without a trailing period (e.g. "matt." -> "matt").
    return key.rstrip(".") in UNDISPUTED_66


def canon_status(book_name: str) -> Dict[str, Any]:
    """Report which canon layer a book belongs to, with an honest history.

    Returns:
        {
            "book": str,                # the input, trimmed
            "in_undisputed_66": bool,
            "held_by": List[str],       # ["all"] for the 66; tradition keys
                                        # for disputed books; [] for unknown
            "historical_note": str,
        }

    - In the 66:        in_undisputed_66=True,  held_by=["all"]
    - Disputed book:    in_undisputed_66=False, held_by=[traditions], note=frame
    - Unknown string:   in_undisputed_66=False, held_by=[],
                        note="not found in any known canon (likely a typo or
                        non-scriptural reference)"

    This function REPORTS who holds what plus the history. It does not judge
    which canon is correct.
    """
    raw = "" if book_name is None else str(book_name).strip()
    key = " ".join(raw.lower().split())

    # 1) Undisputed 66 — the shared core.
    if is_in_undisputed_66(key):
        return {
            "book": raw,
            "in_undisputed_66": True,
            "held_by": ["all"],
            "historical_note": (
                "In the undisputed 66-book canon shared by all major Christian "
                "traditions (the validated core of this engine)."
            ),
        }

    # 2) Disputed / deuterocanonical — held by some traditions.
    canonical = _ALIAS_INDEX.get(key) or _ALIAS_INDEX.get(key.rstrip("."))
    if canonical:
        holders = _holders_for_canonical(canonical)
        return {
            "book": raw,
            "in_undisputed_66": False,
            "held_by": holders,
            "historical_note": _historical_note_for(holders, canonical),
            # canonical name surfaced so callers can dedupe aliases.
            "canonical_name": canonical,
        }

    # 3) Unknown — not in any known canon (likely a typo / non-scriptural).
    return {
        "book": raw,
        "in_undisputed_66": False,
        "held_by": [],
        "historical_note": (
            "not found in any known canon (likely a typo or non-scriptural "
            "reference)"
        ),
    }


def tradition_label(key: str) -> str:
    """Human-readable label for a tradition key (or the key itself if unknown)."""
    trad = TRADITION_ADDITIONS.get(key)
    return trad["label"] if trad else key


def all_disputed_books() -> Dict[str, List[str]]:
    """canonical book name -> list of tradition keys that hold it. Useful for
    enumerating the separate layer (e.g. for a UI or audit)."""
    seen: Dict[str, List[str]] = {}
    for trad in TRADITION_ADDITIONS.values():
        for canonical in trad["books"]:
            if canonical not in seen:
                seen[canonical] = _holders_for_canonical(canonical)
    return seen
