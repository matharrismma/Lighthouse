"""Cross-reference verifier (Treasury of Scripture Knowledge).

Loads R. A. Torrey's Treasury of Scripture Knowledge (1880) — a public-
domain database of ~500,000 scripture cross-references. Engine ships
with a curated seed (`data/scripture/tsk_seed.jsonl`) of the highest-
weight typological and prophetic links so the verifier works out of
the box. The operator can drop `data/scripture/tsk_full.jsonl` to
expand to the full corpus (see scripts/fetch_tsk.py).

Checks:
  * cross_reference.exists       — is there a known link between two verses?
  * cross_reference.connects_to  — return strongest cross-refs for one verse
  * cross_reference.typology     — confirm or deny a typological claim
                                    (X foreshadows / fulfills / parallels Y)

CROSSREF_VERIFY shape (any subset):
    {
      # exists check
      "from_ref": "Isa 53:5", "to_ref": "1 Peter 2:24",
      "claimed_connected": true,

      # connects_to listing (no verdict — surfaces top references)
      "list_for_ref": "Genesis 22:8",
      "list_limit": 10,

      # typology claim — does the substrate corroborate the connection?
      "claim_a_ref": "Numbers 21:9",
      "claim_b_ref": "John 3:14",
      "claimed_typology": true,
    }

Reference format:
  Accepts "Genesis 22:8", "Gen 22:8", "Gen.22.8", "GEN 22:8" — all
  normalize to canonical "Gen.22.8" internally.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import VerifierResult, na, confirm, mismatch, error


# ── Reference normalization ────────────────────────────────────────────

# SBL-style 3-letter abbreviations (with common variants mapped to canonical).
_BOOK_ABBREV: Dict[str, str] = {}

def _seed_book_abbrevs() -> None:
    table = [
        # Old Testament
        ("Gen", ["Gen", "Genesis"]),
        ("Exo", ["Exo", "Exod", "Exodus"]),
        ("Lev", ["Lev", "Leviticus"]),
        ("Num", ["Num", "Numbers"]),
        ("Deu", ["Deu", "Deut", "Deuteronomy"]),
        ("Jos", ["Jos", "Josh", "Joshua"]),
        ("Jdg", ["Jdg", "Judg", "Judges"]),
        ("Rut", ["Rut", "Ruth"]),
        ("1Sa", ["1Sa", "1Sam", "1 Samuel", "1Samuel", "I Samuel"]),
        ("2Sa", ["2Sa", "2Sam", "2 Samuel", "2Samuel", "II Samuel"]),
        ("1Ki", ["1Ki", "1Kgs", "1 Kings", "1Kings", "I Kings"]),
        ("2Ki", ["2Ki", "2Kgs", "2 Kings", "2Kings", "II Kings"]),
        ("1Ch", ["1Ch", "1Chr", "1 Chronicles", "1Chronicles"]),
        ("2Ch", ["2Ch", "2Chr", "2 Chronicles", "2Chronicles"]),
        ("Ezr", ["Ezr", "Ezra"]),
        ("Neh", ["Neh", "Nehemiah"]),
        ("Est", ["Est", "Esth", "Esther"]),
        ("Job", ["Job"]),
        ("Ps",  ["Ps", "Psa", "Psalm", "Psalms"]),
        ("Pr",  ["Pr", "Prov", "Proverbs"]),
        ("Ecc", ["Ecc", "Eccl", "Ecclesiastes"]),
        ("Song",["Song", "SOS", "Song of Solomon", "Song of Songs", "Cant", "Canticles"]),
        ("Isa", ["Isa", "Isaiah"]),
        ("Jer", ["Jer", "Jeremiah"]),
        ("Lam", ["Lam", "Lamentations"]),
        ("Eze", ["Eze", "Ezek", "Ezekiel"]),
        ("Dan", ["Dan", "Daniel"]),
        ("Hos", ["Hos", "Hosea"]),
        ("Joe", ["Joe", "Joel"]),
        ("Amos",["Amos", "Amo"]),
        ("Oba", ["Oba", "Obad", "Obadiah"]),
        ("Jon", ["Jon", "Jonah"]),
        ("Mic", ["Mic", "Micah"]),
        ("Nah", ["Nah", "Nahum"]),
        ("Hab", ["Hab", "Habakkuk"]),
        ("Zep", ["Zep", "Zeph", "Zephaniah"]),
        ("Hag", ["Hag", "Haggai"]),
        ("Zec", ["Zec", "Zech", "Zechariah"]),
        ("Mal", ["Mal", "Malachi"]),
        # New Testament
        ("Mat", ["Mat", "Matt", "Matthew"]),
        ("Mar", ["Mar", "Mark", "Mk"]),
        ("Luk", ["Luk", "Luke", "Lk"]),
        ("John",["John", "Jn", "Jhn"]),
        ("Acts",["Acts", "Act"]),
        ("Rom", ["Rom", "Romans"]),
        ("1Co", ["1Co", "1Cor", "1 Corinthians", "I Corinthians"]),
        ("2Co", ["2Co", "2Cor", "2 Corinthians", "II Corinthians"]),
        ("Gal", ["Gal", "Galatians"]),
        ("Eph", ["Eph", "Ephesians"]),
        ("Phil",["Phil", "Phi", "Philippians"]),
        ("Col", ["Col", "Colossians"]),
        ("1Th", ["1Th", "1Thes", "1 Thessalonians", "I Thessalonians"]),
        ("2Th", ["2Th", "2Thes", "2 Thessalonians", "II Thessalonians"]),
        ("1Ti", ["1Ti", "1Tim", "1 Timothy", "I Timothy"]),
        ("2Ti", ["2Ti", "2Tim", "2 Timothy", "II Timothy"]),
        ("Tit", ["Tit", "Titus"]),
        ("Phm", ["Phm", "Phlm", "Philemon"]),
        ("Heb", ["Heb", "Hebrews"]),
        ("Jas", ["Jas", "Jam", "James"]),
        ("1Pe", ["1Pe", "1Pet", "1 Peter", "I Peter"]),
        ("2Pe", ["2Pe", "2Pet", "2 Peter", "II Peter"]),
        ("1Jo", ["1Jo", "1Joh", "1 John", "I John"]),
        ("2Jo", ["2Jo", "2Joh", "2 John", "II John"]),
        ("3Jo", ["3Jo", "3Joh", "3 John", "III John"]),
        ("Jude",["Jude", "Jud"]),
        ("Rev", ["Rev", "Revelation", "Apocalypse"]),
    ]
    for canonical, variants in table:
        for v in variants:
            # Register the variant as-typed (lowercased)
            _BOOK_ABBREV[v.lower()] = canonical
            # ALSO register a space-squashed form so "1 peter" → "1peter"
            # matches the same canonical book. Critical because the regex
            # path squashes whitespace before lookup.
            squashed = re.sub(r"\s+", "", v.lower())
            if squashed and squashed not in _BOOK_ABBREV:
                _BOOK_ABBREV[squashed] = canonical

_seed_book_abbrevs()


_REF_RE = re.compile(
    r"^\s*([1-3]?\s*[A-Za-z][A-Za-z]+|[1-3][A-Za-z]+)\s*\.?\s*(\d+)\s*[:\.]\s*(\d+)\s*$"
)


def normalize_ref(s: str) -> Optional[str]:
    """Parse a verse reference. Accepts the common variants and returns
    canonical 'Book.Ch.Verse' form, or None on failure."""
    if not s:
        return None
    raw = s.strip()
    # Tolerate "Gen.22.8" form by replacing dots with spaces, then trying again
    candidates = [raw, raw.replace(".", " "), raw.replace(":", ":")]
    for cand in candidates:
        m = _REF_RE.match(cand.strip())
        if m:
            book, ch, vs = m.group(1).strip().lower(), m.group(2), m.group(3)
            # Squash internal spaces: "1 sam" → "1sam"
            book_key = re.sub(r"\s+", "", book)
            book_key2 = book.replace(" ", "")  # both forms
            canonical_book = _BOOK_ABBREV.get(book_key) or _BOOK_ABBREV.get(book_key2)
            if not canonical_book:
                # Try without numerical prefix attached: "i samuel" → "1 samuel"
                continue
            return f"{canonical_book}.{ch}.{vs}"
    # Try one more pattern: "Book Ch.Vs" with dot
    m = re.match(r"^\s*([1-3]?\s*[A-Za-z][A-Za-z]+)\s+(\d+)\.(\d+)\s*$", raw)
    if m:
        book = re.sub(r"\s+", "", m.group(1).lower())
        canonical_book = _BOOK_ABBREV.get(book)
        if canonical_book:
            return f"{canonical_book}.{m.group(2)}.{m.group(3)}"
    return None


# ── Substrate loading ──────────────────────────────────────────────────

_DATA_DIR = Path(__file__).resolve().parents[2].parent / "data" / "scripture"
_SOURCES = [
    _DATA_DIR / "tsk_full.jsonl",   # operator-fetched full corpus (preferred)
    _DATA_DIR / "tsk_seed.jsonl",   # shipped seed (always present)
]

_CACHE: Dict[str, Any] = {"mtime": 0.0, "from_index": {}, "to_index": {}, "total": 0}


def _latest_mtime() -> float:
    latest = 0.0
    for p in _SOURCES:
        try:
            if p.exists():
                latest = max(latest, p.stat().st_mtime)
        except OSError:
            continue
    return latest


def _load() -> Tuple[Dict[str, List[Dict[str, Any]]], Dict[str, List[Dict[str, Any]]], int]:
    """Load all substrate files into a forward and reverse index."""
    mtime = _latest_mtime()
    if _CACHE["from_index"] and mtime <= _CACHE["mtime"]:
        return _CACHE["from_index"], _CACHE["to_index"], _CACHE["total"]

    from_index: Dict[str, List[Dict[str, Any]]] = {}
    to_index: Dict[str, List[Dict[str, Any]]] = {}
    seen_keys: set = set()
    total = 0

    for path in _SOURCES:
        if not path.exists():
            continue
        try:
            with path.open("r", encoding="utf-8") as fh:
                for line in fh:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    f_raw = rec.get("from") or rec.get("from_ref")
                    t_raw = rec.get("to") or rec.get("to_ref")
                    if not f_raw or not t_raw:
                        continue
                    # Normalize both ends. If unparseable, skip.
                    f = normalize_ref(f_raw) or f_raw.strip()
                    t = normalize_ref(t_raw) or t_raw.strip()
                    key = (f, t)
                    if key in seen_keys:
                        continue
                    seen_keys.add(key)
                    entry = {
                        "from": f, "to": t,
                        "weight": int(rec.get("weight") or 1),
                        "tag": rec.get("tag", ""),
                        "note": rec.get("note", ""),
                    }
                    from_index.setdefault(f, []).append(entry)
                    to_index.setdefault(t, []).append(entry)
                    # Symmetric: a typological link is bidirectional in the
                    # "are these connected?" sense, even though TSK records
                    # it one way. The reverse entry must actually swap from
                    # and to so a query for from_index[t] finds entries
                    # whose `to` field points back to f.
                    reverse_entry = {
                        "from": t, "to": f,
                        "weight": entry["weight"],
                        "tag": entry["tag"],
                        "note": entry["note"],
                        "_reversed": True,
                    }
                    from_index.setdefault(t, []).append(reverse_entry)
                    to_index.setdefault(f, []).append(reverse_entry)
                    total += 1
        except OSError:
            continue

    # Sort each bucket strongest-first
    for buckets in (from_index, to_index):
        for k in buckets:
            buckets[k].sort(key=lambda e: e.get("weight", 0), reverse=True)

    _CACHE["mtime"] = mtime
    _CACHE["from_index"] = from_index
    _CACHE["to_index"] = to_index
    _CACHE["total"] = total
    return from_index, to_index, total


def total_entries() -> int:
    _, _, total = _load()
    return total


def cross_references_for(ref: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Return cross-references that originate from `ref`, strongest first."""
    norm = normalize_ref(ref) or ref.strip()
    from_index, _, _ = _load()
    return from_index.get(norm, [])[:limit]


# ── Verifier checks ────────────────────────────────────────────────────

def verify_exists(spec: Dict[str, Any]) -> VerifierResult:
    name = "cross_reference.exists"
    a_raw = spec.get("from_ref")
    b_raw = spec.get("to_ref")
    claimed = spec.get("claimed_connected")
    if not a_raw or not b_raw or claimed is None:
        return na(name)
    a = normalize_ref(a_raw) or a_raw.strip()
    b = normalize_ref(b_raw) or b_raw.strip()
    from_index, _, _ = _load()
    hits = [e for e in from_index.get(a, []) if e.get("to") == b]
    actual = bool(hits)
    cl = bool(claimed)
    data = {
        "from_ref": a, "to_ref": b,
        "actual_connected": actual,
        "claimed_connected": cl,
        "match": hits[0] if hits else None,
        "source": "Treasury of Scripture Knowledge (R.A. Torrey, 1880; public domain)",
    }
    if actual == cl:
        if actual:
            tag = hits[0].get("tag") or ""
            note = hits[0].get("note") or ""
            return confirm(
                name,
                f"{a} ↔ {b} connected (weight {hits[0].get('weight')}; {tag}: {note[:80]})",
                data,
            )
        return confirm(name, f"{a} and {b} not connected in TSK seed (matches claim)", data)
    return mismatch(
        name,
        f"{a} ↔ {b} actually connected={actual}, claimed {cl}",
        data,
    )


def verify_typology(spec: Dict[str, Any]) -> VerifierResult:
    """For 'X is a type/foreshadowing/parallel of Y' style claims.

    The TSK substrate contains tagged typological links; if either direction
    is present, the claim is corroborated. Otherwise return MISMATCH (no
    substrate support — engine doesn't confirm what it can't show).
    """
    name = "cross_reference.typology"
    a_raw = spec.get("claim_a_ref")
    b_raw = spec.get("claim_b_ref")
    claimed = spec.get("claimed_typology")
    if not a_raw or not b_raw or claimed is None:
        return na(name)
    a = normalize_ref(a_raw) or a_raw.strip()
    b = normalize_ref(b_raw) or b_raw.strip()
    from_index, _, _ = _load()
    hits = [e for e in from_index.get(a, []) if e.get("to") == b]
    actual = bool(hits)
    cl = bool(claimed)
    tag = (hits[0].get("tag") if hits else "") or ""
    note = (hits[0].get("note") if hits else "") or ""
    data = {
        "claim_a_ref": a, "claim_b_ref": b,
        "actual_corroborated": actual,
        "claimed_typology": cl,
        "tsk_tag": tag,
        "tsk_note": note,
        "source": "Treasury of Scripture Knowledge (R.A. Torrey, 1880; public domain)",
    }
    if actual == cl:
        if actual:
            return confirm(
                name,
                f"{a} ↔ {b} corroborated in TSK ({tag}; {note[:80]})",
                data,
            )
        return confirm(
            name,
            f"{a} ↔ {b}: claim denies link, and none is present in TSK seed",
            data,
        )
    return mismatch(
        name,
        f"{a} ↔ {b}: TSK link present={actual}, claim said {cl}",
        data,
    )


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    cv = packet.get("CROSSREF_VERIFY") or {}
    if cv.get("from_ref") and cv.get("to_ref") and cv.get("claimed_connected") is not None:
        results.append(verify_exists(cv))
    if cv.get("claim_a_ref") and cv.get("claim_b_ref") and cv.get("claimed_typology") is not None:
        results.append(verify_typology(cv))
    # list_for_ref is informational, surfaces top references with no verdict.
    list_ref = cv.get("list_for_ref")
    if list_ref and not results:
        limit = int(cv.get("list_limit") or 10)
        items = cross_references_for(list_ref, limit=limit)
        if items:
            from .base import VerifierResult as _VR
            results.append(_VR(
                name="cross_reference.connects_to",
                status="NOT_APPLICABLE",
                detail=f"{len(items)} cross-references for {list_ref} (informational, no claim to verify)",
            ))
    if not results:
        results.append(na("cross_references"))
    return results
