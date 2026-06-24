"""Convert the verbatim Aesop source (aesop.json, from Project Gutenberg #19994,
"The Aesop for Children", 1919, public domain) into the learning-bundle unit
shape. Real found text, recombined — never generated. The only transform is
stripping the markdown italic markers (_..._) the source uses around the moral.
Re-run to regenerate units.jsonl."""
import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent / "data" / "reading_en_aesop"
TRACK = "The Aesop for Children (1919, public domain)"

src = json.loads((_DIR / "aesop.json").read_text("utf-8"))
out = _DIR / "units.jsonl"
with out.open("w", encoding="utf-8") as f:
    for i, e in enumerate(src, 1):
        text = (e.get("text", "") or "").replace("_", "").strip()  # drop italic markers
        unit = {
            "id": f"aesop_{i:02d}",
            "title": e["title"],
            "unit_seq": i,
            "track": TRACK,
            "decodable_sentence": text,
        }
        f.write(json.dumps(unit, ensure_ascii=False) + "\n")
print(f"wrote {len(src)} Aesop units -> {out}")
