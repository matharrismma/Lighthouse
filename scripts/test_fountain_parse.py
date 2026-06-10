"""Parse all 13 Dade episodes and report cast + stats."""
import sys
from pathlib import Path
sys.path.insert(0, '.')
from api import fountain

SRC = Path("data/serials/_source/dade")
all_chars = {}
all_stats = []
for f in sorted(SRC.glob("FINAL_E*.fountain")):
    text = f.read_text(encoding='utf-8')
    parsed = fountain.parse(text)
    all_stats.append({"file": f.name, **parsed["stats"]})
    for c in parsed["characters"]:
        all_chars[c] = all_chars.get(c, 0) + parsed["stats"]["dialogue_segments"]

print("Per-episode stats:")
for s in all_stats:
    print(f"  {s['file']:40s} segments={s['segments']:4d} dialogue={s['dialogue_segments']:4d} unique_speakers={s['unique_speakers']:3d}")

print(f"\nTotal unique speakers across all 13 episodes: {len(all_chars)}")
print("\nTop 30 speakers (rough — counted by ep-occurrence):")
for c, n in sorted(all_chars.items(), key=lambda x: -x[1])[:30]:
    print(f"  {c:40s} (in ~{n} dialogue-segments)")
