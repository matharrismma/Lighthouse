"""Expand the unified Narrow Highway channel pool with PD substrate from D:.

Categories added (with per-series caps to keep the manifest sane):
  * Video content (real TV, animation, silent films, sports, vegas, etc.) — all of it
  * OTR audio content — capped per series so the manifest stays under ~2000 items

Strategy:
  Each item gets both an `audio` (or `video`) path AND a `video` field pointing
  at where the encoder will place its uniform MP4 (D:/library_files/_channel_cache/narrow-highway/<id>.mp4).
  The scheduler/muxer prefers the cached video. Once the encoder runs, items
  with audio sources gain still-card-background MP4s ("basic AI background").

Idempotent: re-running picks up new files and skips items already in the pool.
"""
from __future__ import annotations
import json, re
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "content" / "channels" / "narrow_highway.json"
LIB = Path("D:/library_files")
UNIFIED_CACHE_PREFIX = "D:/library_files/_channel_cache/narrow-highway"

# Per-category configuration: pool_key, dir_patterns (regex), cap_per_dir, is_video
# cap_per_dir = None means take everything
CATEGORIES = [
    # === VIDEO content (already broadcast-ready) — take ALL ===
    ("classic_tv_video",        [r"^tv_"],                       None, True),
    ("classic_animation",       [r"^anim_", r"^fleischer_"],     None, True),
    ("silent_films",            [r"^silent_"],                   None, True),
    ("vegas_variety",           [r"^vegas_"],                    None, True),
    ("performance_shorts",      [r"^perf_"],                     None, True),
    ("newsreel_video",          [r"^newsreel_"],                 None, True),
    ("hist_video",              [r"^hist_"],                     None, True),
    ("nasa_video",              [r"^nasa_"],                     None, True),
    ("sports_boxing_video",     [r"^sports_box_"],               None, True),
    ("sports_misc_video",       [r"^sports_(home|you|roller|joe|golden|baseball|football)"], None, True),
    ("educational_video",       [r"^edu_"],                      None, True),
    ("prelinger_video",         [r"^prelinger_"],                None, True),
    ("government_video",        [r"^gov_"],                      None, True),
    ("fishing_film",            [r"^fishing_"],                  None, True),
    ("racing_film",             [r"^racing_"],                   None, True),
    ("rodeo_film",              [r"^rodeo_"],                    None, True),

    # === AUDIO content (still-card + AI background) — capped per series ===
    ("scifi_audio_dramas",      [r"^dimension_x$",
                                 r"^x_minus_one$",
                                 r"^2000_plus$",
                                 r"^quiet_please$",
                                 r"^mercury_theatre$"],          120, False),
    ("otr_mystery_audio",       [r"^suspense$",
                                 r"^yours_truly_johnny_dollar$",
                                 r"^dragnet$",
                                 r"^philip_marlowe$",
                                 r"^whistler$",
                                 r"^escape$",
                                 r"^inner_sanctum$",
                                 r"^crime_classics$",
                                 r"^lights_out$",
                                 r"^sherlock_holmes_rathbone$"], 60, False),
    ("otr_western_audio",       [r"^lone_ranger$",
                                 r"^gunsmoke$",
                                 r"^hopalong_cassidy$",
                                 r"^have_gun$",
                                 r"^wild_bill_hickok$",
                                 r"^melody_ranch$",
                                 r"^roy_rogers_show$",
                                 r"^frontier_gentleman$",
                                 r"^ranger_bill$",
                                 r"^texas_rangers$",
                                 r"^tales_diamond_k$"],          80, False),
    ("otr_anthology_drama",     [r"^cavalcade_of_america$",
                                 r"^family_theater$",
                                 r"^screen_directors_playhouse$",
                                 r"^cbs_radio_workshop$",
                                 r"^you_are_there$",
                                 r"^matinee_theater$",
                                 r"^encore_theater$",
                                 r"^academy_award_theater$",
                                 r"^theatre_royal$"],            60, False),
    ("otr_comedy_audio",        [r"^lum_and_abner$",
                                 r"^father_knows_best$"],        80, False),
]

VIDEO_EXTS = {".mp4", ".mkv", ".avi", ".mov", ".webm"}
AUDIO_EXTS = {".mp3", ".m4a", ".aac"}


def slug(name: str) -> str:
    """Filename → id slug."""
    base = re.sub(r"\.\w+$", "", name)  # drop extension
    base = re.sub(r"[^A-Za-z0-9_-]+", "_", base)
    base = re.sub(r"_+", "_", base).strip("_").lower()
    return base[:90]  # cap length


def humanize_title(item_dir: Path, file_name: str) -> str:
    """Series name + 'Episode N' style title."""
    series = item_dir.name.replace("_", " ").title()
    # Strip dir-name prefix from file if it's there
    stem = re.sub(r"\.\w+$", "", file_name)
    stem = stem.replace("_", " ")
    return f"{series} · {stem}".strip()


def scan_dir(d: Path, want_video: bool, cap: int | None) -> list[Path]:
    """Pick the first N video-or-audio files from a dir, sorted alphabetically."""
    if not d.exists():
        return []
    exts = VIDEO_EXTS if want_video else AUDIO_EXTS
    files = sorted([f for f in d.iterdir() if f.suffix.lower() in exts])
    if cap is not None:
        files = files[:cap]
    return files


def main():
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pool = manifest["content_pool"]
    existing_ids = {it["id"] for items in pool.values() for it in items}

    all_dirs = sorted([d for d in LIB.iterdir() if d.is_dir()])
    added_total = 0

    for pool_key, patterns, cap, is_video in CATEGORIES:
        rxs = [re.compile(p) for p in patterns]
        matched_dirs = [d for d in all_dirs if any(r.match(d.name) for r in rxs)]
        if not matched_dirs:
            continue
        added_here = 0
        pool.setdefault(pool_key, [])
        for d in matched_dirs:
            files = scan_dir(d, want_video=is_video, cap=cap)
            for f in files:
                iid = f"{d.name}__{slug(f.name)}"
                if iid in existing_ids:
                    continue
                if is_video:
                    # Use the original PD video directly — schedulable RIGHT NOW.
                    # The HLS muxer will stream-copy or fall back to re-encode if
                    # the source's codec/spec doesn't match the rest of the day.
                    item = {
                        "id": iid,
                        "title": humanize_title(d, f.name),
                        "source_dir": d.name,
                        "video": str(f).replace("\\", "/"),
                    }
                else:
                    # Audio: video field points at where the encoder will place
                    # the still-card MP4. Until the encoder runs, this item is
                    # skipped by the scheduler (zero duration on missing path).
                    item = {
                        "id": iid,
                        "title": humanize_title(d, f.name),
                        "source_dir": d.name,
                        "video": f"{UNIFIED_CACHE_PREFIX}/{iid}.mp4",
                        "audio": str(f).replace("\\", "/"),
                    }
                pool[pool_key].append(item)
                existing_ids.add(iid)
                added_here += 1
        if added_here:
            print(f"  + {pool_key:30}  {added_here:5}  ({len(matched_dirs)} dirs)")
        added_total += added_here

    # Update _pool_to_block_map to expose the new pool keys via existing block types
    new_mappings = {
        # primetime / variety
        "classic_tv":           "classic_tv_video",
        "classic_animation":    "classic_animation",
        "silent_film":          "silent_films",
        "vegas_variety":        "vegas_variety",
        "performance_short":    "performance_shorts",
        "newsreel":             "newsreel_video",
        "hist_short":           "hist_video",
        "nasa_short":           "nasa_video",
        "sports_boxing":        "sports_boxing_video",
        "sports_misc":          "sports_misc_video",
        "educational_short":    "educational_video",
        "prelinger":            "prelinger_video",
        "western_audio":        "otr_western_audio",
        "mystery_audio":        "otr_mystery_audio",
        "anthology_drama":      "otr_anthology_drama",
        "comedy_audio":         "otr_comedy_audio",
    }
    pmap = manifest.setdefault("_pool_to_block_map", {})
    for k, v in new_mappings.items():
        pmap.setdefault(k, v)

    # Broaden existing block-type pools to draw from richer sources
    # scifi_marquee can now include classic_animation + silent films
    pmap["scifi_marquee"] = ["scifi_animated_pilots", "classic_tv_video", "classic_animation"]
    # movies block can include silent films now (full features)
    pmap["movies"] = ["scifi_animated_pilots", "silent_films"]
    # kids_marquee gets classic animation
    pmap["kids_marquee"] = ["kids_animated_pilots", "classic_animation", "kids_potter_readings"]
    # scifi_audio_drama also pulls from mystery (overlapping vibe)
    pmap["scifi_audio_drama"] = ["scifi_audio_dramas", "otr_mystery_audio"]
    # sports_roller_derby fallback to other sports footage we have
    pmap["sports_roller_derby"] = ["sports_roller_derby", "sports_misc_video", "sports_boxing_video"]

    MANIFEST.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    total_items = sum(len(v) for v in pool.values())
    print(f"\nAdded {added_total} new items. Pool now: {total_items} total items.")
    print(f"_pool_to_block_map now has {len(pmap)} entries.")


if __name__ == "__main__":
    main()
