#!/usr/bin/env python
"""Extract Easton's Bible Dictionary into structured JSONL.

Source: neuu-org/bible-dictionary-dataset (CC-BY 4.0). Original
Easton's Bible Dictionary (Matthew George Easton, 1897) is public domain;
the neuu-org parse is CC-BY which requires attribution.

Outputs:
  data/easton/entries.jsonl   — every term (3,962 entries)
  data/places/entries.jsonl   — geographic subset (~600 places)

Each output entry shape:
  {
    "id":          "easton_<slug>",
    "name":        "Antioch",
    "kind":        "easton" (or "place" in places file),
    "category":    "place" | "person" | "concept" | "object" | "other",
    "text":        full definition text,
    "scripture_refs": ["Acts 11:19", ...],
    "axes":        ["..."],   # derived heuristically
    "source":      "Easton's Bible Dictionary (1897, PD)",
    "license":     "CC-BY 4.0 (parse) / Public Domain (text)",
    "attribution": "Parse from neuu-org/bible-dictionary-dataset"
  }
"""
from __future__ import annotations
import io
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
except (AttributeError, ValueError):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

REPO = Path(__file__).resolve().parents[1]
SRC_DIR = REPO / "data" / "raw_sources" / "easton"
OUT_DIR_FULL   = REPO / "data" / "easton"
OUT_DIR_PLACES = REPO / "data" / "places"

# Geographic-classifier heuristics. These cues, when they appear early in the
# definition text, strongly indicate the entry is a place. Order matters —
# more specific markers first to avoid mis-classification.
_PLACE_HINTS_STRONG = [
    "a city", "the city", "city of", "a town", "the town", "a village",
    "a country", "the country", "a kingdom", "the land of", "the region",
    "a region", "a province", "the province", "a district", "the district",
    "a river", "the river", "a brook", "the brook", "a stream", "the stream",
    "a mountain", "the mountain", "a hill", "the hill", "a peak",
    "a plain", "the plain", "a valley", "the valley", "a wilderness",
    "the wilderness", "the desert", "a desert", "an island", "the island",
    "a sea ", "the sea ", "a lake", "the lake", "a well", "the well",
    "a fountain", "the fountain", "a pool", "the pool",
    "a fortress", "the fortress", "a stronghold",
    "ancient city", "ruined city", "capital of",
    "a place", "place where", "place on", "place in",
]
# Weaker markers — only count when paired with another indicator
_PLACE_HINTS_WEAK = [
    "situated", "located", "lying", "north of", "south of", "east of",
    "west of", "near to", "on the border", "on the coast", "promontory",
    "tribe of", "tribal territory", "territory of",
]
# Person markers — fast-exit if these appear (so we don't falsely classify
# people whose definitions mention places).
_PERSON_HINTS = [
    "son of", "daughter of", "father of", "mother of", "wife of", "husband of",
    "king of israel", "king of judah", "the prophet", "high priest",
    "an israelite", "an apostle", "a disciple", "a levite", "a priest",
    "the son", "the daughter", "the father", "the wife",
]


def classify(text: str, name: str) -> str:
    """Return one of: place, person, concept, object, other."""
    if not text:
        return "other"
    t = text.lower()
    head = t[:400]  # heuristics look at first 400 chars where the genus is usually stated

    # Person check first — many people-entries also mention places
    if any(h in head for h in _PERSON_HINTS):
        return "person"
    # Strong place markers
    if any(h in head for h in _PLACE_HINTS_STRONG):
        return "place"
    # Weak markers, only if no person hint already
    if sum(1 for h in _PLACE_HINTS_WEAK if h in head) >= 2:
        return "place"
    # Object hints
    if any(h in head for h in (
        "a vessel", "a garment", "an instrument", "a coin", "a measure",
        "a unit", "a precious stone", "a tree", "a plant", "a beast",
        "an animal", "a bird", "a fish", "a metal",
    )):
        return "object"
    return "concept"


def normalize_text(s: str) -> str:
    """Strip ThML/HTML residue, collapse whitespace."""
    if not s:
        return ""
    # Strip XML/HTML tags
    s = re.sub(r"<[^>]+>", " ", s)
    # Collapse whitespace
    s = re.sub(r"\s+", " ", s).strip()
    return s


def derive_axes(category: str, text: str) -> List[str]:
    """Quick axis-tagging so the Places lens crosses cleanly into the existing
    axis substrate. Place-category entries lean on physical_substance +
    time_sequence (history of the place); persons lean on authority_trust."""
    if category == "place":
        return ["physical_substance", "time_sequence", "information_encoding"]
    if category == "person":
        return ["authority_trust", "time_sequence"]
    if category == "object":
        return ["physical_substance"]
    if category == "concept":
        return ["information_encoding", "reasoning"]
    return []


def main() -> int:
    if not SRC_DIR.exists():
        print(f"missing source dir: {SRC_DIR}", file=sys.stderr)
        return 1
    OUT_DIR_FULL.mkdir(parents=True, exist_ok=True)
    OUT_DIR_PLACES.mkdir(parents=True, exist_ok=True)

    full_path = OUT_DIR_FULL / "entries.jsonl"
    places_path = OUT_DIR_PLACES / "entries.jsonl"

    counts: Dict[str, int] = {"place": 0, "person": 0, "object": 0, "concept": 0, "other": 0}
    total = 0

    with full_path.open("w", encoding="utf-8") as out_full, \
         places_path.open("w", encoding="utf-8") as out_places:

        for letter_file in sorted(SRC_DIR.glob("*.json")):
            try:
                data = json.loads(letter_file.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as e:
                print(f"  skip {letter_file.name}: {e}", file=sys.stderr)
                continue

            if not isinstance(data, dict):
                continue

            for term, entry in data.items():
                if not isinstance(entry, dict):
                    continue
                name = entry.get("name") or term
                slug = entry.get("slug") or name.lower()
                defs = entry.get("definitions") or []
                # Concat definition texts from Easton specifically; fall back to all
                texts = []
                for d in defs:
                    if isinstance(d, dict):
                        src = (d.get("source") or "").upper()
                        if src in ("EAS", ""):  # Easton (the 'EAS' tag is what neuu uses)
                            t = normalize_text(d.get("text") or "")
                            if t:
                                texts.append(t)
                if not texts:
                    continue
                text = " ".join(texts)
                scripture_refs = entry.get("scripture_refs") or []
                # scripture_refs may be a list of strings or a list of objects
                # The neuu format uses {reference, original} where reference is
                # the normalized form (e.g. "Genesis 35:16") and original is
                # the citation as it appeared in Easton's text (e.g. "Gen. 35:16").
                refs_clean: List[str] = []
                for r in scripture_refs:
                    if isinstance(r, str):
                        refs_clean.append(r.strip())
                    elif isinstance(r, dict):
                        v = r.get("reference") or r.get("ref") or r.get("text") or r.get("original") or ""
                        if v:
                            refs_clean.append(str(v).strip())
                # Dedupe + cap
                seen = set()
                refs_unique = []
                for r in refs_clean:
                    if r and r not in seen:
                        seen.add(r)
                        refs_unique.append(r)
                refs_unique = refs_unique[:50]

                category = classify(text, name)
                rec = {
                    "id":          f"easton_{slug}",
                    "name":        name,
                    "kind":        "easton",
                    "category":    category,
                    "text":        text[:6000],   # cap entry size
                    "scripture_refs": refs_unique,
                    "axes":        derive_axes(category, text),
                    "source":      "Easton's Bible Dictionary (1897, PD)",
                    "license":     "CC-BY 4.0 (parse) / Public Domain (original text)",
                    "attribution": "Parse from neuu-org/bible-dictionary-dataset",
                }
                out_full.write(json.dumps(rec, ensure_ascii=False) + "\n")
                counts[category] += 1
                total += 1

                # Places file: same record with kind=place
                if category == "place":
                    place_rec = dict(rec)
                    place_rec["kind"] = "place"
                    place_rec["id"] = f"place_{slug}"
                    out_places.write(json.dumps(place_rec, ensure_ascii=False) + "\n")

    print(f"wrote {total:,} Easton entries to {full_path}")
    for cat, n in counts.items():
        print(f"  {cat}: {n:,}")
    print(f"wrote {counts['place']:,} place entries to {places_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
