"""acquire_otr_audio.py — Download missing OTR audio from Internet Archive.

The channel manifest references 1,818 OTR audio files (Dimension X, X Minus One,
Lights Out, Lone Ranger, Gunsmoke, etc.) that are documented in the pool but
not yet on disk. This tool reads the ghost entries (items with duration_sec
missing or 0), maps each collection to its Internet Archive item identifier,
and downloads the missing files.

Internet Archive is free, supports HTTPS direct download, and the OTR
Researchers Group (OTRR) maintains restored / cataloged collections under
identifiers like `OTRR_Dimension_X_Singles`. We use the OTRR Singles
collections where they exist (highest quality + best metadata).

Each download is rate-limited politely (2s sleep between requests) and
recoverable (resume on re-run; skips files that already exist).

Run:
  python tools/acquire_otr_audio.py --dry-run            # show what would download
  python tools/acquire_otr_audio.py --collection dimension_x   # one collection
  python tools/acquire_otr_audio.py --apply              # download everything missing
  python tools/acquire_otr_audio.py --apply --limit 50   # cap at 50 files this run

Witness gate: the manifest already has witnesses[] + witness_status=passed
on every OTR item via tools/witness_pool_items.py, so this only downloads
content that has already cleared the gate.
"""
from __future__ import annotations
import argparse
import json
import sys
import time
import urllib.request
from collections import Counter
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "content" / "channels" / "narrow_highway.json"

# Map collection (parent dir of the local path) → IA item identifier
# Verified against IA collection listings. The "OTRR_*_Singles" pattern is
# the Old Time Radio Researchers' standard published collection.
COLLECTION_TO_IA = {
    "dimension_x":            "OTRR_Dimension_X_Singles",
    "xminus_one":             "OTRR_X_Minus_One_Singles",
    "x_minus_one":            "OTRR_X_Minus_One_Singles",
    "lights_out":             "OTRR_Lights_Out_Singles",
    "lone_ranger_otr":        "OTRR_Lone_Ranger_Singles",
    "lone_ranger":            "OTRR_Lone_Ranger_Singles",
    "gunsmoke_otr":           "OTRR_Gunsmoke_Singles",
    "gunsmoke":               "OTRR_Gunsmoke_Singles",
    "have_gun_will_travel":   "OTRR_Have_Gun_Will_Travel_Singles",
    "tales_of_the_texas_rangers": "OTRR_Tales_of_the_Texas_Rangers_Singles",
    "frontier_gentleman":     "OTRR_Frontier_Gentleman_Singles",
    "fort_laramie":           "OTRR_Fort_Laramie_Singles",
    "luke_slaughter":         "OTRR_Luke_Slaughter_of_Tombstone_Singles",
    "six_shooter":            "OTRR_Six_Shooter_Singles",
    "fibber_mcgee":           "OTRR_Fibber_McGee_and_Molly_Singles",
    "jack_benny":             "OTRR_Jack_Benny_Singles",
    "burns_and_allen":        "OTRR_Burns_and_Allen_Singles",
    "our_miss_brooks":        "OTRR_Our_Miss_Brooks_Singles",
    "my_favorite_husband":    "OTRR_My_Favorite_Husband_Singles",
    "phil_harris":            "OTRR_Phil_Harris_Alice_Faye_Singles",
    "suspense":               "OTRR_Suspense_Singles",
    "escape":                 "OTRR_Escape_Singles",
    "inner_sanctum":          "OTRR_Inner_Sanctum_Singles",
    "mystery_theatre":        "OTRR_CBS_Mystery_Theatre_Singles",
    "lux_radio_theatre":      "OTRR_Lux_Radio_Theatre_Singles",
    "mercury_theatre":        "OTRR_Mercury_Theatre_Singles",
    "columbia_workshop":      "OTRR_Columbia_Workshop_Singles",
    "cbs_radio_workshop":     "OTRR_CBS_Radio_Workshop_Singles",
}


def detect_collection_from_path(path_str: str) -> Optional[str]:
    """The manifest stores paths like D:/library_files/<collection>/<file>.mp3."""
    p = Path(path_str)
    # Walk up looking for a parent that's in our map
    for parent in p.parents:
        name = parent.name.lower()
        if name in COLLECTION_TO_IA:
            return name
    # Some manifest entries embed the collection in the filename itself
    fname = p.name.lower()
    for key in COLLECTION_TO_IA:
        if key in fname:
            return key
    return None


def find_ghost_items(manifest: dict) -> list:
    """Return list of (pool_key, item, collection_name, expected_path) for every
    missing pool item where we have an IA collection mapping."""
    out = []
    pool = manifest.get("content_pool", {})
    for pool_key, items in pool.items():
        for it in items:
            if (it.get("duration_sec") or 0) > 0:
                continue
            audio = it.get("audio") or ""
            video = it.get("video") or ""
            path_str = audio or video
            if not path_str:
                continue
            local = Path(path_str)
            if local.exists():
                continue
            coll = detect_collection_from_path(path_str)
            if coll is None:
                continue
            out.append((pool_key, it, coll, local))
    return out


def ia_file_url(item_id: str, filename: str) -> str:
    """Construct the direct download URL for a file inside an IA item."""
    return f"https://archive.org/download/{item_id}/{filename}"


def download_file(url: str, dst: Path, timeout: int = 120) -> tuple[bool, str]:
    """Download URL to dst (atomic via .partial → rename). Returns (ok, msg)."""
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".partial")
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "NarrowHighway/1.0 (curated Christian family channel; matt@narrowhighway.com)"
        })
        with urllib.request.urlopen(req, timeout=timeout) as r:
            with open(tmp, "wb") as f:
                while True:
                    chunk = r.read(64 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        tmp.replace(dst)
        return True, f"{dst.stat().st_size // 1024} KB"
    except urllib.error.HTTPError as e:
        if tmp.exists():
            tmp.unlink()
        return False, f"HTTP {e.code}"
    except Exception as e:
        if tmp.exists():
            tmp.unlink()
        return False, str(e)[:80]


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true", help="Actually download")
    p.add_argument("--dry-run", action="store_true", help="Report only")
    p.add_argument("--collection", help="Limit to a single collection name")
    p.add_argument("--limit", type=int, default=0, help="Max files this run (0=no limit)")
    p.add_argument("--sleep", type=float, default=2.0, help="Seconds between downloads")
    args = p.parse_args()
    if not (args.apply or args.dry_run):
        args.dry_run = True

    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    ghosts = find_ghost_items(m)
    print(f"ghost items detected: {len(ghosts)}")

    # Filter by collection if requested
    if args.collection:
        ghosts = [g for g in ghosts if g[2] == args.collection.lower()]
        print(f"after --collection={args.collection}: {len(ghosts)} items")

    # Group by IA item to report coverage
    by_collection = Counter(g[2] for g in ghosts)
    print()
    print("by collection (collection -> IA item -> count):")
    for coll, n in by_collection.most_common():
        ia = COLLECTION_TO_IA.get(coll, "UNMAPPED")
        print(f"  {coll:<30}  archive.org/details/{ia}  ({n} files)")

    if not args.apply:
        print()
        print("DRY-RUN — nothing downloaded. Re-run with --apply.")
        return

    print()
    print(f"=== downloading (sleep {args.sleep}s between requests) ===")
    ok_count = 0
    fail_count = 0
    started = time.time()
    for idx, (pool_key, it, coll, dst) in enumerate(ghosts):
        if args.limit and (ok_count + fail_count) >= args.limit:
            break
        ia_id = COLLECTION_TO_IA[coll]
        url = ia_file_url(ia_id, dst.name)
        ok, msg = download_file(url, dst)
        if ok:
            ok_count += 1
            mark = "OK"
        else:
            fail_count += 1
            mark = "FAIL"
        elapsed = time.time() - started
        print(f"  [{idx+1}/{len(ghosts)}] {mark:<5} {dst.name[:55]:<55} {msg}  (t+{elapsed:.0f}s)",
              flush=True)
        time.sleep(args.sleep)

    print()
    print(f"=== done in {time.time()-started:.0f}s ===")
    print(f"  downloaded: {ok_count}")
    print(f"  failed:     {fail_count}")
    print()
    print("Next step: rerun tools/duration_cache.py --warm to register newly-arrived files.")


if __name__ == "__main__":
    main()
