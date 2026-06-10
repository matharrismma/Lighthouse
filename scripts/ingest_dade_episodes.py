"""Parse all 13 Dade fountain episodes and write structured JSON files
into data/serials/dade/episodes/NNN.json — ready for the multi-voice
producer.
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, '.')
from api import fountain

SRC = Path("data/serials/_source/dade")
OUT = Path("data/serials/dade/episodes")
OUT.mkdir(parents=True, exist_ok=True)

EP_RE = re.compile(r"FINAL_E(\d+)_(.+)\.fountain$")

# Episode title overrides for nicer display (from filename → reader-friendly)
TITLES = {
    "TheCreek":      "The Creek",
    "TheNumber":     "The Number",
    "ThePew":        "The Pew",
    "TheWindow":     "The Window",
    "TheClay":       "The Clay",
    "TheHead":       "The Head",
    "TheKiln":       "The Kiln",
    "TheWages":      "The Wages",
    "TheCompanyMan": "The Company Man",
    "TheHandshake":  "The Handshake",
    "TheRoad":       "The Road",
    "TheFloor":      "The Floor",
    "TheCollision":  "The Collision",
}

now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

count = 0
total_dialogue = 0
total_action = 0
total_speakers = set()

for f in sorted(SRC.glob("FINAL_E*.fountain")):
    m = EP_RE.match(f.name)
    if not m:
        continue
    ep_num = int(m.group(1))
    title_slug = m.group(2)
    title = TITLES.get(title_slug, title_slug)

    text = f.read_text(encoding="utf-8")
    parsed = fountain.parse(text)

    # Render to a plain script for read-along on the page
    plain = fountain.segments_to_plain_script(parsed["segments"])

    # Summary from the synopsis lines, if any
    synopses = parsed.get("synopses", [])
    summary = " — ".join(synopses[:4]) if synopses else ""

    out_rec = {
        "serial":            "dade",
        "ep_num":            ep_num,
        "title":             title,
        "metadata":          parsed.get("metadata", {}),
        "synopses":          synopses,
        "summary":           summary,
        "script":            plain,
        "segments":          parsed["segments"],
        "characters":        parsed["characters"],
        "stats":             parsed["stats"],
        "fountain_source":   str(f.relative_to(Path("."))),
        "ingested_at_iso":   now_iso,
        "produced":          False,
    }
    json_path = OUT / f"{ep_num:03d}.json"
    json_path.write_text(json.dumps(out_rec, ensure_ascii=False, indent=2), encoding="utf-8")
    count += 1
    total_dialogue += parsed["stats"]["dialogue_segments"]
    total_action   += parsed["stats"]["action_segments"]
    for c in parsed["characters"]:
        total_speakers.add(c)
    print(f"  E{ep_num:02d} {title:25s} segments={parsed['stats']['segments']:4d}  dialogue={parsed['stats']['dialogue_segments']:4d}  speakers={parsed['stats']['unique_speakers']:3d}")

print(f"\nWrote {count} episodes → {OUT}")
print(f"Totals: dialogue={total_dialogue}, action={total_action}, unique speakers={len(total_speakers)}")
