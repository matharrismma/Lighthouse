"""Scan D: sermon directories and fill the Sermons & Devotions channel manifest.

Reads content/channels/nh_sermons_devotions.json, walks the four sermon source
folders on D:, and populates the empty content_pool arrays with one item per
audio file. Writes the manifest back in-place (preserves all other fields).

Idempotent: re-running picks up new files added to D: and refreshes the pool.

Title heuristics:
  - spurgeon_morning_evening: "Morning & Evening · Day NN"
  - spurgeon_all_of_grace: "All of Grace · Chapter NN"
  - edwards_select_sermons: "Edwards Select Sermons · NN"
  - edwards_religious_affections: "Religious Affections · Part NN"
"""
from __future__ import annotations
import json, re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "content" / "channels" / "nh_sermons_devotions.json"

SOURCES = [
    ("spurgeon_morning_evening", Path("D:/library_files/sermon_spurgeon_morning_evening"),
     "Morning & Evening · {n}", "morningevening", "spurgeon"),
    ("spurgeon_all_of_grace", Path("D:/library_files/sermon_spurgeon_all_of_grace"),
     "All of Grace · Chapter {n}", "allgrace", "spurgeon"),
    ("edwards_select_sermons", Path("D:/library_files/sermon_edwards_select"),
     "Edwards Select Sermons · {n}", "selectsermons", "edwards"),
    ("edwards_religious_affections", Path("D:/library_files/sermon_edwards_religious_affections"),
     "Religious Affections · Part {n}", "religiousaffections", "edwards"),
]


def part_num(name: str) -> str | None:
    m = re.search(r"_(\d{2,3})_", name)
    return m.group(1) if m else None


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pool = {}

    for pool_key, src_dir, title_fmt, id_prefix, author in SOURCES:
        items = []
        if not src_dir.exists():
            print(f"  [SKIP {pool_key}] source dir missing: {src_dir}")
            pool[pool_key] = []
            continue
        for mp3 in sorted(src_dir.glob("*.mp3")):
            n = part_num(mp3.name) or mp3.stem
            iid = f"{id_prefix}_{n}"
            items.append({
                "id": iid,
                "title": title_fmt.format(n=n.lstrip("0") or "0"),
                "author": author,
                "audio": str(mp3).replace("\\", "/"),
            })
        pool[pool_key] = items
        print(f"  [OK {pool_key}] {len(items)} items")

    manifest["content_pool"] = pool
    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    total = sum(len(v) for v in pool.values())
    print(f"\nWrote {MANIFEST} ({total} items)")


if __name__ == "__main__":
    main()
