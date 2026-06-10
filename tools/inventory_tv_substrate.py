"""Inventory D: drive for TV-eligible content not yet in any channel manifest.

Reports per-category:
  - dir count, file count
  - total estimated runtime (rough: average MP3 ~30 min, MP4 ~25 min — adjust by actual probe later)
  - sample filenames

This is read-only. It does NOT touch any manifest. Use the output to decide
which categories to ingest into channel pools.
"""
from __future__ import annotations
import re
from pathlib import Path

LIB = Path("D:/library_files")

# Categories with prefix pattern + a human label + whether it has video
CATEGORIES = [
    # Real TV (already video)
    ("tv_video",            r"^tv_",                    "Classic TV (real video)",       True),
    ("animation_video",     r"^anim_|^fleischer_",      "Animation (real video)",        True),
    ("silent_films",        r"^silent_",                "Silent films",                  True),
    ("vegas_variety",       r"^vegas_",                 "Vegas variety shows",           True),
    ("performance_shorts",  r"^perf_",                  "Performance shorts",            True),
    ("newsreel",            r"^newsreel_",              "Newsreels",                     True),
    ("nasa_video",          r"^nasa_",                  "NASA archive",                  True),
    ("hist_video",          r"^hist_",                  "Historical footage",            True),
    ("fishing_film",        r"^fishing_",               "Fishing films",                 True),
    ("racing_film",         r"^racing_",                "Racing films",                  True),
    ("rodeo_film",          r"^rodeo_",                 "Rodeo films",                   True),
    ("prelinger",           r"^prelinger_",             "Prelinger archive",             True),
    ("educational",         r"^edu_",                   "Educational films",             True),
    ("government",          r"^gov_",                   "Government films",              True),
    # OTR (audio with basic AI background card)
    ("otr_sci_fi",          r"^(dimension_x|x_minus_one|2000_plus|quiet_please)$", "OTR Sci-Fi", False),
    ("otr_mystery",         r"^(dragnet|sherlock_holmes_rathbone|philip_marlowe|whistler|yours_truly_johnny_dollar|crime_classics|inner_sanctum|lights_out|escape|suspense)$", "OTR Mystery / Suspense", False),
    ("otr_western",         r"^(gunsmoke|lone_ranger|hopalong_cassidy|frontier_gentleman|have_gun|melody_ranch|roy_rogers_show|ranger_bill|wild_bill_hickok)$", "OTR Westerns", False),
    ("otr_drama",           r"^(mercury_theatre|academy_award_theater|cavalcade_of_america|cbs_radio_workshop|encore_theater|family_theater|screen_directors_playhouse|matinee_theater|you_are_there)$", "OTR Anthology Drama", False),
    ("otr_comedy",          r"^(lum_and_abner|jack_benny|burns_and_allen|fibber_mcgee_and_molly|amos_andy)$", "OTR Comedy", False),
    ("otr_religious",       r"^(old_fashioned_revival_hour|father_knows_best)$", "OTR Religious / Family", False),
]


def inventory_dir(d: Path) -> dict:
    """Count audio + video files; return summary."""
    if not d.exists():
        return {"audio": 0, "video": 0, "sample": []}
    audio = sum(1 for f in d.iterdir() if f.suffix.lower() in (".mp3", ".m4a", ".aac"))
    video = sum(1 for f in d.iterdir() if f.suffix.lower() in (".mp4", ".mkv", ".avi", ".mov", ".webm"))
    sample = []
    for f in d.iterdir():
        if f.suffix.lower() in (".mp3", ".mp4", ".m4a", ".mkv", ".avi"):
            sample.append(f.name)
            if len(sample) >= 3:
                break
    return {"audio": audio, "video": video, "sample": sample}


def main():
    all_dirs = [d for d in LIB.iterdir() if d.is_dir()]
    classified = set()

    grand_audio = 0
    grand_video = 0

    print("=" * 78)
    print("D: DRIVE TV-ELIGIBLE INVENTORY")
    print("=" * 78)

    for cat_id, pattern, label, has_video in CATEGORIES:
        rx = re.compile(pattern)
        matching = [d for d in all_dirs if rx.match(d.name)]
        if not matching:
            continue
        cat_audio = 0
        cat_video = 0
        print(f"\n[{label}]  ({len(matching)} dirs)")
        for d in matching[:10]:  # show first 10
            info = inventory_dir(d)
            cat_audio += info["audio"]
            cat_video += info["video"]
            tag = "VIDEO" if info["video"] > 0 else "audio"
            print(f"   {d.name:50}  {tag:5}  {info['audio']:4} mp3 / {info['video']:4} mp4")
            classified.add(d.name)
        for d in matching[10:]:
            info = inventory_dir(d)
            cat_audio += info["audio"]
            cat_video += info["video"]
            classified.add(d.name)
        if len(matching) > 10:
            print(f"   ... ({len(matching) - 10} more dirs)")
        print(f"   SUBTOTAL: {cat_audio} audio + {cat_video} video items")
        grand_audio += cat_audio
        grand_video += cat_video

    print(f"\n{'='*78}")
    print(f"GRAND TOTAL: {grand_audio} audio items + {grand_video} video items")
    print(f"At ~25 min average: ~{(grand_audio + grand_video) * 25 / 60:.0f} hours of substrate")

    # Show unclassified dirs (might be content we missed)
    unclassified = [d for d in all_dirs if d.name not in classified and not d.name.startswith("_")]
    relevant_unclassified = [d for d in unclassified
                             if any(d.name.startswith(p) for p in
                                    ("bible_", "kids_", "sermon_", "lv_", "mag_",
                                     "comic_", "bg_", "pulp_", "annie_", "father_",
                                     "78_", "podcast", "racing_", "rodeo_", "fishing_"))]
    other_unclassified = [d for d in unclassified
                          if d not in relevant_unclassified]
    if other_unclassified:
        print(f"\n[OTHER dirs not classified above] ({len(other_unclassified)})")
        for d in other_unclassified[:25]:
            info = inventory_dir(d)
            tag = "VIDEO" if info["video"] > 0 else "audio"
            print(f"   {d.name:50}  {tag:5}  {info['audio']:4} mp3 / {info['video']:4} mp4")
        if len(other_unclassified) > 25:
            print(f"   ... ({len(other_unclassified) - 25} more)")


if __name__ == "__main__":
    main()
