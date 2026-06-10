"""fix_library_noise.py — Clear the rebalancer's flagged noise.

Three classes of problem this addresses:

1. EMPTY STORYBOARDS — 8 animation storyboard cards from LOOP 26 whose
   body is just "**Scene N: Scene N**" because the script parser couldn't
   extract dialogue / visuals. Archive them (never delete — recoverable).

2. OVERGROWN BOXES — single boxes holding 500-1810 cards make /shelves.html
   unwieldy and trigger rebalancer warnings. Re-box by a meaningful axis:
     - dictionary_cites_scripture (1810) → dictionary_cites_<book>
     - proof_text (876)                  → proof_text_<tradition>
     - easton_concept / person / place   → easton_<cat>_<first_letter_range>
     - patristic_cites_scripture (60)    → consolidated with patristics_cites_scripture (typo fix)
   Sequence_* boxes are left alone — they're glue, not browseable content.

3. TYPO BOX — LOOP 28 used `patristic_cites_scripture`; LOOP 45 used
   `patristics_cites_scripture` (with the trailing 's'). Same concept,
   two boxes. Consolidate by re-boxing the smaller one to match.

Idempotent. Safe to re-run. Operator never silently loses cards.

Usage:
  python tools/fix_library_noise.py             # apply
  python tools/fix_library_noise.py --dry-run   # report only
"""
from __future__ import annotations
import argparse
import json
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

CARDS_DIR = REPO / "data" / "cards"
ARCHIVE_DIR = REPO / "data" / "cards" / "archived"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _alpha_bucket(s: str) -> str:
    """Map a string to a letter-range bucket: a-d, e-h, i-l, m-p, q-t, u-z."""
    s = (s or "").strip().lower()
    if not s:
        return "other"
    ch = s[0]
    if "a" <= ch <= "d": return "a_d"
    if "e" <= ch <= "h": return "e_h"
    if "i" <= ch <= "l": return "i_l"
    if "m" <= ch <= "p": return "m_p"
    if "q" <= ch <= "t": return "q_t"
    if "u" <= ch <= "z": return "u_z"
    return "other"


def _persist(card: dict):
    (CARDS_DIR / f"{card['id']}.json").write_text(json.dumps(card, indent=2), encoding="utf-8")


def fix_storyboards(dry_run: bool) -> dict:
    """Archive storyboards whose body is the empty-parser placeholder."""
    counts = {"scanned": 0, "archived": 0, "kept": 0}
    if not CARDS_DIR.exists():
        return counts
    for f in CARDS_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if c.get("shelf") != "animation":
            continue
        counts["scanned"] += 1
        body = (c.get("body") or "").strip()
        # Empty body or just the scene-header placeholder
        is_empty = not body
        is_placeholder = body.replace("\n", "").startswith("**Scene") and len(body) < 100
        if is_empty or is_placeholder:
            if dry_run:
                counts["archived"] += 1
                continue
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            target = ARCHIVE_DIR / f.name
            c["lifecycle_stage"] = "archived"
            c["archived_at"] = _now()
            c["archived_reason"] = "empty_storyboard_from_LOOP_26_parser_bug"
            target.write_text(json.dumps(c, indent=2), encoding="utf-8")
            f.unlink()
            counts["archived"] += 1
        else:
            counts["kept"] += 1
    return counts


def split_box(target_box: str, splitter, dry_run: bool) -> dict:
    """Walk every card whose box==target_box; reassign via splitter(card) -> new_box."""
    counts = {"scanned": 0, "rebox": 0, "noop": 0}
    for f in CARDS_DIR.glob("*.json"):
        try:
            c = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        if c.get("box") != target_box:
            continue
        counts["scanned"] += 1
        new_box = splitter(c)
        if not new_box or new_box == target_box:
            counts["noop"] += 1
            continue
        if dry_run:
            counts["rebox"] += 1
            continue
        c["box"] = new_box
        c["updated_at"] = _now()
        _persist(c)
        counts["rebox"] += 1
    return counts


def _book_from_bands(c: dict) -> str | None:
    """Return the Bible-book token from a citation card's bands."""
    bands = c.get("bands") or []
    # Bands look like: ["cites", "auto_detected", "dictionary", "romans"]
    # Skip generic ones; return the first that looks like a book.
    SKIP = {"cites", "auto_detected", "dictionary", "patristics", "patristic", "classics", "codex", "hymns", "maker", "recipes",
            "proof_text", "westminster_shorter", "heidelberg", "1689_baptist", "german_reformed", "reformed_baptist", "continental_reformed"}
    for b in bands:
        if not b: continue
        if b in SKIP: continue
        # Could be a book token like "romans" or "1_corinthians" or "1_peter"
        return b
    return None


def _tradition_from_bands(c: dict) -> str | None:
    bands = c.get("bands") or []
    TRAD = {"westminster_shorter": "wsc", "heidelberg": "hc", "1689_baptist": "lbcf",
            "german_reformed": "hc", "reformed_baptist": "lbcf"}
    for b in bands:
        if b in TRAD:
            return TRAD[b]
    return None


def _easton_letter_split(c: dict) -> str | None:
    box = c.get("box") or ""
    cat = box.replace("easton_", "")
    name = (c.get("title") or "").replace("Easton: ", "").strip()
    bucket = _alpha_bucket(name)
    return f"easton_{cat}_{bucket}"


def fix_typo_box(dry_run: bool) -> dict:
    """Rename `patristic_cites_scripture` (60) → `patristics_cites_scripture` (canonical)."""
    return split_box(
        "patristic_cites_scripture",
        lambda c: "patristics_cites_scripture",
        dry_run,
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    mode = "DRY RUN" if args.dry_run else "APPLIED"
    print(f"=== Library noise fixer — {mode} ===\n")

    # 1. Storyboards
    print("[1/5] Empty storyboard cards…")
    r = fix_storyboards(args.dry_run)
    for k, v in r.items():
        if v: print(f"  {k}: {v}")

    # 2. Typo: patristic_cites_scripture → patristics_cites_scripture
    print("\n[2/5] Typo consolidation (patristic → patristics)…")
    r = fix_typo_box(args.dry_run)
    for k, v in r.items():
        if v: print(f"  {k}: {v}")

    # 3. Split dictionary_cites_scripture by target book
    print("\n[3/5] Split dictionary_cites_scripture by book…")
    def split_dict_cites(c):
        book = _book_from_bands(c)
        return f"dictionary_cites_{book}" if book else "dictionary_cites_other"
    r = split_box("dictionary_cites_scripture", split_dict_cites, args.dry_run)
    for k, v in r.items():
        if v: print(f"  {k}: {v}")

    # Also handle classics_cites_scripture + patristics_cites_scripture by book
    print("\n[3b/5] Split classics_cites_scripture by book…")
    def split_classics(c): return f"classics_cites_{_book_from_bands(c) or 'other'}"
    r = split_box("classics_cites_scripture", split_classics, args.dry_run)
    for k, v in r.items():
        if v: print(f"  {k}: {v}")

    print("\n[3c/5] Split patristics_cites_scripture by book…")
    def split_patr(c): return f"patristics_cites_{_book_from_bands(c) or 'other'}"
    r = split_box("patristics_cites_scripture", split_patr, args.dry_run)
    for k, v in r.items():
        if v: print(f"  {k}: {v}")

    # 4. Split proof_text by tradition
    print("\n[4/5] Split proof_text by tradition (WSC/HC/LBCF)…")
    def split_proof(c):
        trad = _tradition_from_bands(c)
        return f"proof_text_{trad}" if trad else "proof_text_other"
    r = split_box("proof_text", split_proof, args.dry_run)
    for k, v in r.items():
        if v: print(f"  {k}: {v}")

    # 5. Easton boxes — alphabetical bucket split
    print("\n[5/5] Split easton_concept / person / place by first letter…")
    for cat in ("concept", "person", "place", "object"):
        box = f"easton_{cat}"
        r = split_box(box, _easton_letter_split, args.dry_run)
        if r["scanned"] > 0:
            print(f"  {box}: scanned={r['scanned']} rebox={r['rebox']}")

    print("\n=== Summary ===")
    # Tally final boxes
    if not args.dry_run:
        from collections import Counter
        boxes = Counter()
        for f in CARDS_DIR.glob("*.json"):
            try:
                c = json.loads(f.read_text(encoding="utf-8"))
                boxes[c.get("box") or "(none)"] += 1
            except Exception:
                continue
        big = [(b, n) for b, n in boxes.most_common() if n > 500]
        print(f"  Boxes still >500 cards: {len(big)}")
        for b, n in big[:5]:
            print(f"    {b}: {n}")
        print(f"  Total cards on disk: {sum(1 for _ in CARDS_DIR.glob('*.json'))}")


if __name__ == "__main__":
    main()
