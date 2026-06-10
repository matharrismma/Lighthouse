"""Build static JSON catalogs of acquired content from the inventory manifests.

Emits to site/:
  - shows.json     — video shows (pd_tv, vegas, sports, fishing, western, theatre, animation)
  - stations.json  — audio (radio, sermon, performances, bible_audio, music_78rpm)
  - kids.json      — children audiobooks + family animation
  - library.json   — everything together (for the Library deck)

Re-run after every download wave finishes. Idempotent.
"""
from __future__ import annotations
import json
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
ACQ = REPO / "data" / "library_inventory" / "acquired"
OUT = REPO / "site"

VIDEO_EXTS = (".mp4", ".avi", ".mkv", ".mpeg4", ".m4v", ".webm", ".ogv", ".mov")
AUDIO_EXTS = (".mp3", ".ogg", ".m4a", ".wav", ".flac")
PDF_EXTS = (".pdf",)

VIDEO_CATS = {"pd_tv", "vegas", "sports", "fishing", "western", "theatre", "animation",
              "feature_film", "newsreel", "history", "documentary", "prelinger",
              "education", "observatory"}
AUDIO_CATS = {"radio", "sermon", "performances", "bible_audio", "music_78rpm"}
KIDS_CATS  = {"children"}
MAG_CATS   = {"magazines", "pulp", "board_games_reference"}


def load_manifests() -> list[dict]:
    out = []
    if not ACQ.exists():
        return out
    for m in sorted(ACQ.glob("*.json")):
        try:
            data = json.loads(m.read_text(encoding="utf-8"))
            out.append(data)
        except Exception:
            pass
    return out


def shape_show(data: dict, exts: tuple[str, ...]) -> dict | None:
    items = data.get("items", [])
    filtered = [
        it for it in items
        if any((it.get("filename") or "").lower().endswith(e) for e in exts)
    ]
    if not filtered:
        return None
    # Case-insensitive sort by filename so S01e21 doesn't jump ahead of s01e01
    filtered.sort(key=lambda it: (it.get("filename") or "").lower())
    slug = data.get("slug") or ""
    eps = []
    for it in filtered:
        fn = it.get("filename") or ""
        # Prefer the transcoded .web.mp4 sibling if present (browser-playable)
        local_path = it.get("local_path") or ""
        playable_filename = fn
        if local_path:
            from pathlib import Path as _P
            web_sibling = _P(local_path).with_suffix(".web.mp4")
            if web_sibling.exists():
                playable_filename = web_sibling.name
        # Same-origin URL for in-browser playback (served by /media/{slug}/{file})
        local_url = f"/media/{slug}/{playable_filename}" if slug and playable_filename else None
        eps.append({
            "filename": fn,
            "playable_filename": playable_filename,
            "title": it.get("title") or fn,
            "size_mb": round((it.get("size_bytes") or 0) / 1024 / 1024, 1),
            "ia_url": it.get("download_url"),
            "local_url": local_url,
            "is_web_optimized": playable_filename.lower().endswith(".web.mp4"),
        })
    return {
        "slug": slug,
        "title": data.get("title"),
        "category": data.get("category"),
        "claimed_status": data.get("claimed_status"),
        "notes": data.get("notes"),
        "episode_count": len(filtered),
        "total_mb": round(data.get("total_mb", 0), 1),
        "episodes": eps,
    }


def build():
    manifests = load_manifests()
    shows = []      # video
    stations = []   # audio (non-kids)
    kids = []       # children-category audio + any kids animation
    everything = [] # combined for Library deck

    for m in manifests:
        cat = m.get("category", "")
        # Video catalog
        if cat in VIDEO_CATS:
            s = shape_show(m, VIDEO_EXTS)
            if s:
                shows.append(s)
                everything.append(s)
        # Audio catalog (non-kids)
        if cat in AUDIO_CATS:
            s = shape_show(m, AUDIO_EXTS)
            if s:
                stations.append(s)
                everything.append(s)
        # Kids catalog
        if cat in KIDS_CATS:
            # children category is audiobook-heavy; some have ogg/mp3
            s = shape_show(m, AUDIO_EXTS + VIDEO_EXTS)
            if s:
                kids.append(s)
                everything.append(s)

    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "shows.json").write_text(
        json.dumps({"shows": shows, "total_shows": len(shows),
                    "total_episodes": sum(s["episode_count"] for s in shows)}, indent=2),
        encoding="utf-8")
    (OUT / "stations.json").write_text(
        json.dumps({"stations": stations, "total_stations": len(stations),
                    "total_episodes": sum(s["episode_count"] for s in stations)}, indent=2),
        encoding="utf-8")
    (OUT / "kids.json").write_text(
        json.dumps({"shows": kids, "total_shows": len(kids),
                    "total_episodes": sum(s["episode_count"] for s in kids)}, indent=2),
        encoding="utf-8")
    (OUT / "library.json").write_text(
        json.dumps({"items": everything, "total_items": len(everything),
                    "total_episodes": sum(s["episode_count"] for s in everything)}, indent=2),
        encoding="utf-8")

    print(f"shows.json:    {len(shows):>4} shows  / {sum(s['episode_count'] for s in shows):>5} episodes")
    print(f"stations.json: {len(stations):>4} stations / {sum(s['episode_count'] for s in stations):>5} episodes")
    print(f"kids.json:     {len(kids):>4} shows  / {sum(s['episode_count'] for s in kids):>5} episodes")
    print(f"library.json:  {len(everything):>4} items  / {sum(s['episode_count'] for s in everything):>5} episodes")


if __name__ == "__main__":
    build()
