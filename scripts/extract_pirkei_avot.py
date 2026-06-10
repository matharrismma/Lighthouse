"""Parse Pirkei Avot from Sefaria API responses into packet substrate.

Source: Mishnah Yomit translation by Dr. Joshua Kulp (CC-BY via Sefaria).
Output: data/pirkei_avot/sayings.jsonl — one packet per mishnah (saying).

Sefaria's chapter JSON structure: { text: ["v1 text", "v2 text", ...], ... }
"""
from __future__ import annotations
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
RAW = REPO / "data" / "raw_sources"
OUT = REPO / "data" / "pirkei_avot" / "sayings.jsonl"

sys.path.insert(0, str(REPO / "scripts"))
from extract_proverbs import derive_axes, derive_themes


def main():
    OUT.parent.mkdir(parents=True, exist_ok=True)
    written = 0
    with OUT.open("w", encoding="utf-8") as fh:
        for ch in range(1, 7):
            f = RAW / f"pirkei_avot_ch{ch}.json"
            if not f.exists():
                print(f"  missing: {f.name}")
                continue
            d = json.loads(f.read_text(encoding="utf-8"))
            verses = d.get("text") or []
            version = d.get("versionTitle") or "Mishnah Yomit by Dr. Joshua Kulp"
            license_str = d.get("license") or "CC-BY"
            for i, v in enumerate(verses, start=1):
                if not v or not v.strip():
                    continue
                # Sefaria sometimes returns HTML — strip basic tags
                text = re.sub(r"<[^>]+>", "", v)
                text = re.sub(r"\s+", " ", text).strip()
                if len(text) < 20:
                    continue
                packet = {
                    "id": f"avot_{ch:02d}_{i:02d}",
                    "kind": "pirkei_avot",
                    "reference": f"Pirkei Avot {ch}:{i}",
                    "chapter": ch,
                    "mishnah": i,
                    "text": text,
                    "source": f"Pirkei Avot — Sefaria, trans. {version}",
                    "license": license_str,
                    "attribution_required": True,
                    "axes": derive_axes(text),
                    "themes": derive_themes(text),
                }
                fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
                written += 1
    print(f"Pirkei Avot: {written} mishnayot")


if __name__ == "__main__":
    main()
