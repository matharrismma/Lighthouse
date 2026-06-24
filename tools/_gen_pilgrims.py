"""Convert the verbatim Pilgrim's Progress excerpt (pilgrims.json, from Project
Gutenberg #131, John Bunyan, 1678, public domain) into the learning-bundle unit
shape. Real found text, recombined — never generated. Re-run to regenerate."""
import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent / "data" / "reading_en_pilgrims"
TRACK = "The Pilgrim's Progress, John Bunyan (public domain)"

src = json.loads((_DIR / "pilgrims.json").read_text("utf-8"))
out = _DIR / "units.jsonl"
with out.open("w", encoding="utf-8") as f:
    for i, e in enumerate(src, 1):
        rec = {"id": f"pilgrims_{i:02d}", "title": e["title"], "unit_seq": i,
               "track": TRACK, "decodable_sentence": (e.get("text", "") or "").strip()}
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
print(f"wrote {len(src)} Pilgrim's Progress units -> {out}")
