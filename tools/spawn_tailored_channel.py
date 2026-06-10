"""Spawn a tailored channel from a slice of the unified Narrow Highway pool.

Inputs: a new channel id + name + which pool keys to include + a few cosmetics.
Output: a new channel manifest at content/channels/<id>.json that the existing
scheduler / HLS muxer / MRSS / index pipeline can build for.

Discipline: this does NOT mark the new channel as live. It writes the manifest
and prints next-step build commands. Operator runs them when ready (and only
if the slice has enough content to actually fill 24h).

Usage:
  python tools/spawn_tailored_channel.py \
      --id narrow-kids \
      --name "Narrow Highway · Kids" \
      --pools kids_pooh_readings,kids_potter_readings,kids_andersen_readings,kids_blue_fairy_readings,kids_velveteen,kids_animated_pilots,classic_animation \
      --color-primary "#5c432c" \
      --color-accent  "#c9b48a" \
      --tagline "Stories for the whole family"
"""
from __future__ import annotations
import argparse, json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
UNIFIED = REPO / "content" / "channels" / "narrow_highway.json"
OUT_DIR = REPO / "content" / "channels"


def default_weekly_pattern(block_type_default: str) -> list:
    """Produce a sensible 7-day pattern that mostly maps every block to one default type.
    Operator should edit to insert variety. The shape matches the unified channel's grid.
    """
    days = ["sunday", "monday", "tuesday", "wednesday", "thursday", "friday", "saturday"]
    hours = ["00:05", "02:05", "04:05", "06:05", "08:05", "10:05", "12:05",
             "14:05", "16:05", "18:05", "20:05", "22:05"]
    pattern = []
    for d in days:
        for h in hours:
            pattern.append({
                "day": d, "hour": h,
                "block_name": f"{d.capitalize()} {h}",
                "type": block_type_default,
                "tone": "standard",
            })
    return pattern


def build_manifest(args) -> dict:
    unified = json.loads(UNIFIED.read_text(encoding="utf-8"))

    # Slice the pool
    pool_keys = [k.strip() for k in args.pools.split(",") if k.strip()]
    sliced_pool = {}
    for k in pool_keys:
        items = unified.get("content_pool", {}).get(k, [])
        sliced_pool[k] = list(items)  # shallow copy
        print(f"  + {k}: {len(items)} items")

    # Default pool->block map: a single "primary" block type drawing from ALL sliced pools
    pool_map = {"primary": pool_keys}

    # Bumpers — start from unified bumpers but rebrand the text
    name = args.name
    bumpers = [
        {"id": "station_id_1", "type": "station_id", "duration_sec": 6,
         "text": f"You're watching {name}", "subtitle": args.tagline or ""},
        {"id": "station_id_2", "type": "station_id", "duration_sec": 8,
         "text": name, "subtitle": "narrowhighway.com — a curated internet for Christian families"},
        {"id": "now_playing", "type": "now_playing", "duration_sec": 6,
         "text_template": "Now Playing · {current_title}"},
        {"id": "scripture_card_1", "type": "pastoral", "duration_sec": 10,
         "text": "Enter ye in at the strait gate... narrow is the way, which leadeth unto life. Matthew 7:13-14.",
         "subtitle": "Narrow Highway"},
    ]

    manifest = {
        "channel_id": args.id,
        "name": name,
        "tagline": args.tagline or "A tailored slice of Narrow Highway",
        "description": args.description or
            f"A tailored channel of Narrow Highway, focused on {', '.join(pool_keys[:3])}{'...' if len(pool_keys) > 3 else ''}.",
        "category": args.category or "Christian Family · Tailored",
        "audience": args.audience or "All ages",
        "color_primary": args.color_primary or "#1a3a52",
        "color_accent":  args.color_accent  or "#c9b48a",
        "logo": f"/img/channel-{args.id}.png",
        "_doc": (
            f"Spawned by tools/spawn_tailored_channel.py from the unified Narrow Highway pool. "
            f"This channel shares the upstream pool — when items are added to the unified manifest "
            f"with one of these pool keys ({', '.join(pool_keys)}), they automatically become available here. "
            f"Operator must edit weekly_programming_pattern below to add variety; the default puts all "
            f"blocks on type 'primary' which draws from every sliced pool randomly."
        ),
        "weekly_programming_pattern": default_weekly_pattern("primary"),
        "_pool_to_block_map": pool_map,
        "content_pool": sliced_pool,
        "bumpers": bumpers,
        "bumper_cadence_minutes": 30,
        "block_transition_bumper": "station_id_1",
        "distribution_targets": [
            {"platform": "YouTube Live (24/7 stream)", "status": "planned"},
            {"platform": "Plex Live TV", "status": "planned"},
            {"platform": "Roku Direct Publisher", "status": "planned",
             "mrss_url": f"https://narrowhighway.com/channels/{args.id}/mrss.xml"},
        ],
    }
    return manifest


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--id", required=True, help="channel id (e.g. narrow-kids)")
    ap.add_argument("--name", required=True, help='display name (e.g. "Narrow Highway · Kids")')
    ap.add_argument("--pools", required=True,
                    help="comma-separated list of pool keys from the unified manifest to include")
    ap.add_argument("--tagline", default=None)
    ap.add_argument("--description", default=None)
    ap.add_argument("--category", default=None)
    ap.add_argument("--audience", default=None)
    ap.add_argument("--color-primary", default=None)
    ap.add_argument("--color-accent", default=None)
    ap.add_argument("--force", action="store_true", help="overwrite existing manifest if any")
    args = ap.parse_args()

    out_path = OUT_DIR / f"{args.id.replace('-', '_')}.json"
    if out_path.exists() and not args.force:
        print(f"[ABORT] {out_path} already exists. Pass --force to overwrite.")
        return

    print(f"Spawning channel '{args.id}' from {args.pools.count(',') + 1} pool keys...\n")
    manifest = build_manifest(args)
    total = sum(len(v) for v in manifest["content_pool"].values())

    out_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"\nWrote {out_path}")
    print(f"  Pool total: {total} items")
    print(f"  Bumpers:    {len(manifest['bumpers'])}")
    print(f"  Pattern:    {len(manifest['weekly_programming_pattern'])} blocks across 7 days")
    print()
    print("Next steps (operator runs when ready):")
    print(f"  1. Edit {out_path} to add daypart variety to weekly_programming_pattern.")
    print(f"  2. python tools/fast_channel_bumpers.py --channel {out_path}")
    print(f"  3. python tools/fast_channel_schedule.py --channel {out_path}")
    print(f"  4. python tools/fast_channel_hls.py --channel {out_path} --date $(date -u +%Y-%m-%d)")
    print(f"  5. python tools/fast_channel_mrss.py --channel {out_path}")
    print(f"  6. python tools/fast_channel_index.py    # refresh the channels index")
    print()
    print("Don't ship publicly until the schedule rebuild reports ≥23.5h of runtime.")


if __name__ == "__main__":
    main()
