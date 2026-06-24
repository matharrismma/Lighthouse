"""Convert the verbatim McGuffey Primer source (primer.json, from Project
Gutenberg #14642, public domain) into the learning-bundle unit shape. Real found
text, recombined — never generated. Re-run to regenerate units.jsonl."""
import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent / "data" / "reading_en_mcguffey"
TRACK = "McGuffey's Eclectic Primer (1879)"

src = json.loads((_DIR / "primer.json").read_text("utf-8"))
out = _DIR / "units.jsonl"
with out.open("w", encoding="utf-8") as f:
    for e in src:
        n = int(e["n"])
        unit = {
            "id": f"mcguffey_primer_{n:02d}",
            "title": f"Lesson {n}",
            "unit_seq": n,
            "track": TRACK,
            "examples": e.get("words", []),
            "decodable_sentence": (e.get("text", "") or "").strip(),
        }
        f.write(json.dumps(unit, ensure_ascii=False) + "\n")
print(f"wrote {len(src)} McGuffey units -> {out}")
