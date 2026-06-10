"""Aggregate the four source-channel content pools into the unified Narrow Highway channel.

Reads:
  content/channels/nh_scifi_theatre.json
  content/channels/nh_hundred_acre.json
  content/channels/nh_hymns_247.json
  content/channels/nh_sermons_devotions.json

Writes the merged pool back into content/channels/narrow_highway.json, preserving
all other fields (programming_pattern, bumpers, _pool_to_block_map, etc).

Idempotent: re-run anytime a sub-manifest gains items.

Mapping (sub-manifest pool key -> unified pool key):
  nh_scifi_theatre:
    animated_pilots                              -> scifi_animated_pilots
    audio_dramas_dimension_x                     -> scifi_audio_dramas
    audio_dramas_xminus_one                      -> scifi_audio_dramas
    audio_dramas_mercury_theatre                 -> scifi_audio_dramas
  nh_hundred_acre:
    animated_pilots                              -> kids_animated_pilots
    pooh_readings                                -> kids_pooh_readings
    potter_readings                              -> kids_potter_readings
    andersen_readings                            -> kids_andersen_readings
    blue_fairy_readings                          -> kids_blue_fairy_readings
    velveteen                                    -> kids_velveteen
  nh_hymns_247:
    hymns                                        -> hymns
  nh_sermons_devotions:
    spurgeon_morning_evening                     -> spurgeon_morning_evening
    spurgeon_all_of_grace                        -> spurgeon_all_of_grace
    edwards_select_sermons                       -> edwards_select_sermons
    edwards_religious_affections                 -> edwards_religious_affections
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCES_DIR = REPO / "content" / "channels"
UNIFIED = SOURCES_DIR / "narrow_highway.json"

MAPPING = {
    "nh_scifi_theatre.json": ("nh-scifi-theatre", {
        "animated_pilots": "scifi_animated_pilots",
        "audio_dramas_dimension_x": "scifi_audio_dramas",
        "audio_dramas_xminus_one": "scifi_audio_dramas",
        "audio_dramas_mercury_theatre": "scifi_audio_dramas",
    }),
    "nh_hundred_acre.json": ("nh-hundred-acre", {
        "animated_pilots": "kids_animated_pilots",
        "pooh_readings": "kids_pooh_readings",
        "potter_readings": "kids_potter_readings",
        "andersen_readings": "kids_andersen_readings",
        "blue_fairy_readings": "kids_blue_fairy_readings",
        "velveteen": "kids_velveteen",
    }),
    "nh_hymns_247.json": ("nh-hymns-247", {
        "hymns": "hymns",
    }),
    "nh_sermons_devotions.json": ("nh-sermons-devotions", {
        "spurgeon_morning_evening": "spurgeon_morning_evening",
        "spurgeon_all_of_grace": "spurgeon_all_of_grace",
        "edwards_select_sermons": "edwards_select_sermons",
        "edwards_religious_affections": "edwards_religious_affections",
    }),
}


def _decorate(item: dict, source_channel_id: str) -> dict:
    """Attach a cached_video field pointing at the source channel's uniform cache.
    The scheduler/muxer prefers cached_video over the original audio/video field.
    """
    iid = item["id"]
    cached = f"D:/library_files/_channel_cache/{source_channel_id}/{iid}.mp4"
    out = dict(item)
    # Set 'video' to the cached MP4. Keep the original 'audio' (for archival /
    # podcast use) but the scheduler will pick 'video' first.
    out["video"] = cached
    out["source_channel"] = source_channel_id
    return out


def main():
    unified = json.loads(UNIFIED.read_text(encoding="utf-8"))
    pool = {k: [] for k in unified["content_pool"].keys()}
    sources_summary = {}

    for src_name, (source_ch_id, key_map) in MAPPING.items():
        src_path = SOURCES_DIR / src_name
        if not src_path.exists():
            print(f"  [skip] {src_name} missing")
            continue
        src = json.loads(src_path.read_text(encoding="utf-8"))
        src_pool = src.get("content_pool", {})
        src_total = 0
        for src_key, unified_key in key_map.items():
            items = src_pool.get(src_key, [])
            # Decorate each item with a cached_video field pointing at the source
            # channel's uniform-encoded cache. Scheduler picks video first, so the
            # HLS muxer gets MP4s ready for stream-copy.
            for it in items:
                pool.setdefault(unified_key, []).append(_decorate(it, source_ch_id))
                src_total += 1
        sources_summary[src_name] = src_total

    unified["content_pool"] = pool
    UNIFIED.write_text(json.dumps(unified, indent=2), encoding="utf-8")

    total = sum(len(v) for v in pool.values())
    print("Unified pool rebuilt.")
    for src, n in sources_summary.items():
        print(f"  from {src}: {n}")
    print()
    print(f"Per-key counts in narrow_highway.json:")
    for k, v in pool.items():
        print(f"  {k:32} {len(v)}")
    print(f"\n  TOTAL: {total} items")


if __name__ == "__main__":
    main()
