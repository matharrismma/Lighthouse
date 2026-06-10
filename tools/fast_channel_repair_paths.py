"""Repair broken source paths in content/channels/narrow_highway.json.

The unified channel manifest is the problem behind the 23-minute loop: ~2,300
of its 3,127 content_pool items point their `video` field at a non-existent
D:/library_files/_channel_cache/.../<id>.mp4 — that's the encode OUTPUT path,
not a real SOURCE. With no real source, fast_channel_encode.py can't encode
them, so they never reach the channel cache, so the HLS day stays tiny.

This tool fixes what it honestly can:
  - Items whose `source_channel` is another channel (hymn_*, sermon renders,
    etc.) are LEFT ALONE — those are produced by encoding that sub-channel.
  - Items native to narrow-highway are matched, by normalized id, against the
    real media still sitting in their D:/library_files/<collection>/ directory.
    When a real file is found, the item is rewritten to point at it — as
    `audio` for mp3-family sources, `video` otherwise.

Dry-run by default; pass --apply to write (a .bak is made first).

  python tools/fast_channel_repair_paths.py            # dry run, just report
  python tools/fast_channel_repair_paths.py --apply    # write the repair
"""
from __future__ import annotations
import json, os, re, shutil, sys
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
LIB = Path("D:/library_files")
MANIFEST = REPO / "content" / "channels" / "narrow_highway.json"

AUDIO_EXT = {".mp3", ".m4a", ".aac", ".ogg", ".flac", ".wav", ".opus"}
VIDEO_EXT = {".mp4", ".mkv", ".avi", ".mpeg", ".mpg", ".webm", ".mov", ".m4v"}


def norm(s: str) -> str:
    """Normalize a filename stem the way the manifest ids were built:
    lowercase; keep alphanumerics and hyphens; collapse everything else to _."""
    return re.sub(r"[^a-z0-9-]+", "_", s.lower()).strip("_")


def build_index() -> dict[str, Path]:
    """Map '<collection>__<norm(stem)>' -> real media file, for every file
    under a real (non-cache) D:/library_files collection directory."""
    idx: dict[str, Path] = {}
    if not LIB.is_dir():
        return idx
    for d in sorted(LIB.iterdir()):
        if not d.is_dir() or d.name.startswith("_"):
            continue
        try:
            entries = list(d.iterdir())
        except OSError:
            continue
        for f in entries:
            if not f.is_file():
                continue
            ext = f.suffix.lower()
            if ext not in AUDIO_EXT and ext not in VIDEO_EXT:
                continue
            idx.setdefault(f"{d.name}__{norm(f.stem)}", f)
    return idx


def main() -> None:
    apply = "--apply" in sys.argv
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    idx = build_index()
    print(f"Indexed {len(idx):,} real media files under {LIB}")

    broken = repaired = skipped_cross = unmatched = 0
    rep_audio = rep_video = 0
    sample_fixed, sample_unmatched = [], []

    for _cat, items in manifest.get("content_pool", {}).items():
        for it in items:
            cur = (it.get("video") or it.get("audio") or "")
            if cur and "_channel_cache" not in cur and os.path.exists(cur):
                continue  # already valid
            if "_channel_cache" not in cur:
                continue  # not the failure mode we fix here
            broken += 1

            sc = it.get("source_channel", "")
            if sc and sc != "narrow-highway":
                skipped_cross += 1   # belongs to a sub-channel encode
                continue

            real = idx.get(it.get("id", ""))
            if not real:
                unmatched += 1
                if len(sample_unmatched) < 8:
                    sample_unmatched.append(it.get("id", ""))
                continue

            p = str(real).replace("\\", "/")
            if real.suffix.lower() in AUDIO_EXT:
                it["audio"] = p
                it.pop("video", None)
                rep_audio += 1
            else:
                it["video"] = p
                it.pop("audio", None)
                rep_video += 1
            repaired += 1
            if len(sample_fixed) < 8:
                sample_fixed.append(f"{it.get('id','')[:40]} -> {real.name[:46]}")

    print(f"\nBroken (_channel_cache) items: {broken:,}")
    print(f"  repaired to real source:        {repaired:,}  (audio={rep_audio}, video={rep_video})")
    print(f"  left for sub-channel encode:    {skipped_cross:,}")
    print(f"  unmatched (no real source):     {unmatched:,}")
    if sample_fixed:
        print("\n  sample repairs:")
        for s in sample_fixed:
            print(f"    {s}")
    if sample_unmatched:
        print("\n  sample unmatched ids:")
        for s in sample_unmatched:
            print(f"    {s}")

    if apply and repaired:
        bak = MANIFEST.with_name(MANIFEST.name + ".bak")
        if not bak.exists():
            shutil.copy2(MANIFEST, bak)
            print(f"\nBackup written: {bak}")
        MANIFEST.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"WROTE {MANIFEST}")
    elif repaired:
        print("\nDRY RUN — re-run with --apply to write the repair.")
    else:
        print("\nNothing to repair.")


if __name__ == "__main__":
    main()
