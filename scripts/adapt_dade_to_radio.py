"""Adapt one Dade episode from TV screenplay to radio drama.

Usage:
    python scripts/adapt_dade_to_radio.py [ep_num] [--dry-run]

Writes:
    data/serials/dade/episodes/{nnn}.radio.json    — adapted segments
    data/serials/dade/episodes/{nnn}.radio.diff.md  — side-by-side
                                                       before/after preview

The TV master (.json) is never touched.
"""
import json
import os
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

# Load .env into os.environ
env_path = REPO / ".env"
if env_path.exists():
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        k = k.strip()
        # Overwrite if shell has it empty (common on Windows)
        if not os.environ.get(k):
            os.environ[k] = v

from api.radio_adapter import adapt_episode  # noqa: E402

EP_DIR = REPO / "data" / "serials" / "dade" / "episodes"

ep_num = 1
dry = False
for a in sys.argv[1:]:
    if a == "--dry-run":
        dry = True
    elif a.isdigit():
        ep_num = int(a)

src = EP_DIR / f"{ep_num:03d}.json"
if not src.exists():
    print(f"missing: {src}", file=sys.stderr)
    sys.exit(1)

rec = json.loads(src.read_text(encoding="utf-8"))
segments = rec.get("segments") or []
print(f"Loaded ep{ep_num:02d} '{rec.get('title')}' — {len(segments)} TV segments")
print()

if dry:
    # Just show what would happen for the first 2 scenes
    from api.radio_adapter import _segments_to_scenes  # type: ignore
    scenes = _segments_to_scenes(segments)
    print(f"Would adapt {len(scenes)} scenes via Claude")
    for i, sc in enumerate(scenes[:2], 1):
        action_n = sum(1 for s in sc if s.get("kind") == "action")
        dia_n    = sum(1 for s in sc if s.get("kind") == "dialogue")
        hd       = next((s for s in sc if s.get("kind") == "scene_heading"), {})
        print(f"  Scene {i}: {hd.get('text','(no heading)')[:60]} — {action_n} action / {dia_n} dialogue")
    print()
    print("--dry-run: no API calls made.")
    sys.exit(0)

# Real run
print("Sending scenes to Claude for radio adaptation...")
print(f"  (using ANTHROPIC_API_KEY of length {len(os.environ.get('ANTHROPIC_API_KEY',''))})")
print()

t0 = time.time()
scenes_done = [0]
def progress(i, total, result):
    scenes_done[0] = i
    print(f"  scene {i}/{total} -> {len(result)} radio segments")

result = adapt_episode(segments, on_progress=progress)
elapsed = time.time() - t0

adapted = result["adapted_segments"]
stats = result["stats"]

print()
print(f"DONE in {elapsed:.1f}s")
print(f"  Scenes adapted: {result['scene_count']}")
print(f"  Model: {result['model']}")
print(f"  TV  segments: {stats['tv_segments']:4d}  (action {stats['tv_action']:3d}  dialogue {stats['tv_dialogue']:3d}  headings {stats['tv_scene_heading']:3d}  transitions {stats['tv_transition']:3d})")
print(f"  RAD segments: {stats['radio_segments']:4d}  (narrator {stats['radio_narrator']:3d}  sfx {stats['radio_sfx']:3d}  dialogue {stats['radio_dialogue']:3d}  headings {stats['radio_scene_heading']:3d})")

# Write the adapted segments
out_json = EP_DIR / f"{ep_num:03d}.radio.json"
radio_rec = dict(rec)
radio_rec["segments"] = adapted
radio_rec["adapted_from_tv"] = True
radio_rec["adapter_model"]   = result["model"]
radio_rec["adapter_stats"]   = stats
out_json.write_text(json.dumps(radio_rec, ensure_ascii=False, indent=2), encoding="utf-8")
print()
print(f"Wrote {out_json}")

# Write a side-by-side diff for human review (first 3 scenes)
diff_path = EP_DIR / f"{ep_num:03d}.radio.diff.md"
lines = [f"# ep{ep_num:02d} '{rec.get('title')}' — TV vs Radio preview", "",
         f"Stats: {json.dumps(stats)}", "", "---", ""]

# Group both by scene heading so we can show before/after
def scene_groups(segs, kinds_action):
    groups = []; cur = []
    for s in segs:
        if s.get("kind") == "scene_heading":
            if cur: groups.append(cur)
            cur = [s]
        else:
            cur.append(s)
    if cur: groups.append(cur)
    return groups

tv_scenes = scene_groups(segments, {"action"})
rad_scenes = scene_groups(adapted, {"narrator","sfx"})

for i in range(min(3, len(tv_scenes), len(rad_scenes))):
    tv = tv_scenes[i]
    rd = rad_scenes[i]
    hd = next((s for s in tv if s.get("kind")=="scene_heading"), {}).get("text","")
    lines.append(f"## Scene {i+1} — {hd}")
    lines.append("")
    lines.append("### TV (original)")
    lines.append("")
    for s in tv:
        k = s.get("kind"); t = s.get("text","")
        if k == "action":
            lines.append(f"_{t}_")
            lines.append("")
        elif k == "dialogue":
            lines.append(f"**{s.get('speaker','')}**: {t}")
            lines.append("")
        elif k == "scene_heading":
            lines.append(f"**[{t}]**")
            lines.append("")
        elif k == "transition":
            lines.append(f"`>> {t}`")
            lines.append("")
    lines.append("### Radio (adapted)")
    lines.append("")
    for s in rd:
        k = s.get("kind"); t = s.get("text","")
        if k == "narrator":
            lines.append(f"_{t}_  ← narrator")
            lines.append("")
        elif k == "sfx":
            lines.append(f"`[SFX: {t}]`")
            lines.append("")
        elif k == "dialogue":
            lines.append(f"**{s.get('speaker','')}**: {t}")
            lines.append("")
        elif k == "scene_heading":
            lines.append(f"**[{t}]**")
            lines.append("")
    lines.append("---")
    lines.append("")

diff_path.write_text("\n".join(lines), encoding="utf-8")
print(f"Wrote {diff_path}")
