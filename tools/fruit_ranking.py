#!/usr/bin/env python3
# The fruit test, turned inward (Matt 2026-06-12: "look at the ideas that have
# produced the most fruit"). A STANDING MEASURE: which ideas in the corpus bear
# the most fruit -- measured by how many other cards bond TO them (in-degree),
# which form-families generate the most cards, and which work-programs produced
# the most. Re-run as the corpus grows to watch which ideas keep bearing.
#
#   python tools/fruit_ranking.py
# Writes the current snapshot to data/codex/fruit_ranking.json and appends a
# compact line to data/codex/fruit_ranking_history.jsonl (the watch-over-time log).
import json, collections, datetime, os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ENT  = os.path.join(ROOT, "data/almanac/entries.jsonl")
SNAP = os.path.join(ROOT, "data/codex/fruit_ranking.json")
HIST = os.path.join(ROOT, "data/codex/fruit_ranking_history.jsonl")

# fold id aliases so a single idea isn't split across spellings
NORM = {
    "som_01": "som_01_the_beatitudes", "teaching_som_01": "som_01_the_beatitudes",
    "teaching_beatitude_1": "teaching_beatitude_1_poor_in_spirit",
    "teaching_beatitude_5": "teaching_beatitude_5_merciful",
    "teaching_beatitude_9": "teaching_beatitude_9_rejoice_reward",
    "reality_is_mappable": "connection_reality_is_mappable",
}

rows = [json.loads(l) for l in open(ENT, encoding="utf-8") if l.strip()]
byid = {r.get("id"): r for r in rows}

indeg = collections.Counter()
for r in rows:
    for b in (r.get("bonds") or []):
        indeg[NORM.get(b, b)] += 1

top    = indeg.most_common(30)
fam    = collections.Counter((r.get("coord") or {}).get("family") for r in rows if (r.get("coord") or {}).get("family"))
origin = collections.Counter(r.get("origin") for r in rows if r.get("origin"))
date   = datetime.date.today().isoformat()

print("FRUIT RANKING  %s  (%d rows)" % (date, len(rows)))
print("--- most fruit (cards bonded to it) ---")
for cid, c in top[:20]:
    r = byid.get(cid)
    t = (r.get("title") if r else "(not a card in corpus)") or ""
    try: t = t.encode("ascii", "replace").decode()
    except Exception: t = ""
    print("  %3d  %-46s %s" % (c, cid, t[:40]))
print("--- most generative forms (coord.family) ---")
print("  " + ", ".join("%s=%d" % (f, c) for f, c in fam.most_common(12)))
print("--- by work-program (origin) ---")
print("  " + ", ".join("%s=%d" % (o, c) for o, c in origin.most_common(8)))

snap = {"date": date, "rows": len(rows),
        "top_ideas": [{"id": i, "fruit": c} for i, c in top],
        "top_forms": dict(fam.most_common(25)),
        "by_origin": dict(origin.most_common())}
json.dump(snap, open(SNAP, "w", encoding="utf-8"), indent=1)
with open(HIST, "a", encoding="utf-8", newline="\n") as f:
    f.write(json.dumps({"date": date, "rows": len(rows),
                        "top5": [i for i, _ in top[:5]],
                        "top5_fruit": [c for _, c in top[:5]]}) + "\n")
print("wrote %s  +  appended %s" % (os.path.relpath(SNAP, ROOT), os.path.relpath(HIST, ROOT)))
