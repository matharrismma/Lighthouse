"""Convert the verbatim Founding-documents source (founding.json — Declaration of
Independence from Project Gutenberg #1, U.S. Constitution Preamble from #5, Bill
of Rights from #2; all public domain) into the learning-bundle unit shape. Real
found primary-source text, recombined — never generated. Re-run to regenerate."""
import json
from pathlib import Path

_DIR = Path(__file__).resolve().parent.parent / "data" / "reading_en_founding"
TRACK = "Founding Documents (United States, public domain)"
_ROMAN = {1: "I", 2: "II", 3: "III", 4: "IV", 5: "V",
          6: "VI", 7: "VII", 8: "VIII", 9: "IX", 10: "X"}

src = json.loads((_DIR / "founding.json").read_text("utf-8"))
units = []
units.append({"title": "The Declaration of Independence — Opening (excerpt)",
              "text": src["declaration_opening"]})
units.append({"title": "The Declaration of Independence — Conclusion",
              "text": src["declaration_conclusion"]})
units.append({"title": "The Constitution of the United States — Preamble",
              "text": src["constitution_preamble"]})
for a in src["bill_of_rights"]:
    units.append({"title": f"The Bill of Rights — Amendment {_ROMAN[a['n']]}",
                  "text": a["text"]})

out = _DIR / "units.jsonl"
with out.open("w", encoding="utf-8") as f:
    for i, u in enumerate(units, 1):
        rec = {"id": f"founding_{i:02d}", "title": u["title"], "unit_seq": i,
               "track": TRACK, "decodable_sentence": u["text"].strip()}
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
print(f"wrote {len(units)} founding-document units -> {out}")
