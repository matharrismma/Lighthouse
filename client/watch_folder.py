"""watch_folder — drop a file, plant a seed.

Watches a directory; when a `.txt` or `.md` file appears, the file's
contents are POST'd to a Concordance instance as a journal seed,
tagged `source:watch_folder`. The original file is then either
deleted, moved to a `_processed/` subdirectory, or left in place
(configurable).

Zero external dependencies — uses stdlib only. Polls the directory
on an interval; no inotify / FSEvents requirement, so it works
identically on Linux, macOS, Windows.

Per the kingdom-economy substrate: the user's existing cloud
folders (iCloud, Dropbox, GDrive) become feeders by pointing this
script at them. No new app required, no payment processor in the
path. The only thing the user adds is one config: where to watch.

Per "wise as serpents, innocent as doves": this script is fully
transparent. It logs every file it processes. It never touches
files older than its start time without `--include-existing`. It
will never silently overwrite or delete user data.

Usage:
    python watch_folder.py --dir ~/concordance-inbox
    python watch_folder.py --dir ~/concordance-inbox --api https://narrowhighway.com
    python watch_folder.py --dir ~/concordance-inbox --on-success move
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Iterable, List, Set


DEFAULT_API = "https://narrowhighway.com"
DEFAULT_INTERVAL_SECONDS = 5.0
DEFAULT_EXTENSIONS = {".txt", ".md"}
DEFAULT_ON_SUCCESS = "move"  # "delete" | "move" | "leave"


def post_capture(
    api: str,
    text: str,
    *,
    source_meta: dict | None = None,
    timeout: float = 30.0,
) -> dict:
    """POST text to /capture. Returns the parsed JSON response."""
    url = api.rstrip("/") + "/capture"
    body = json.dumps({
        "text": text,
        "source": "watch_folder",
        "source_meta": source_meta or {},
        "identity_acknowledged": True,
    }).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def find_files(
    folder: Path,
    extensions: Set[str],
    seen: Set[Path],
    min_mtime: float | None,
) -> List[Path]:
    """Return new files in `folder` matching extensions and post-mtime."""
    out: List[Path] = []
    if not folder.exists():
        return out
    for entry in folder.iterdir():
        if not entry.is_file():
            continue
        if entry.suffix.lower() not in extensions:
            continue
        if entry in seen:
            continue
        if min_mtime is not None:
            try:
                if entry.stat().st_mtime < min_mtime:
                    continue
            except OSError:
                continue
        out.append(entry)
    return out


def process_file(
    path: Path,
    api: str,
    on_success: str,
    processed_dir: Path,
) -> bool:
    """Read, POST, dispose. Returns True on success, False on failure."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        print(f"[error] could not read {path.name}: {exc}", file=sys.stderr)
        return False
    text = text.strip()
    if not text:
        print(f"[skip ] {path.name} is empty")
        return True  # nothing to do, but not an error

    try:
        result = post_capture(
            api,
            text,
            source_meta={
                "filename": path.name,
                "size_bytes": len(text.encode("utf-8")),
                "captured_at_epoch": time.time(),
            },
        )
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"[error] POST failed for {path.name}: {exc}", file=sys.stderr)
        return False
    except Exception as exc:  # noqa: BLE001 — surface any unexpected error
        print(f"[error] unexpected: {exc}", file=sys.stderr)
        return False

    seed_id = (result.get("entry") or {}).get("id", "?")
    print(f"[ok   ] {path.name} -> {seed_id}")

    # Dispose of the source file according to policy.
    try:
        if on_success == "delete":
            path.unlink()
        elif on_success == "move":
            processed_dir.mkdir(parents=True, exist_ok=True)
            target = processed_dir / path.name
            # If target exists, suffix with timestamp to avoid clobber.
            if target.exists():
                stem = target.stem
                suffix = target.suffix
                target = processed_dir / f"{stem}-{int(time.time())}{suffix}"
            shutil.move(str(path), str(target))
    except OSError as exc:
        print(f"[warn ] {path.name} captured but file disposal failed: {exc}",
              file=sys.stderr)
    return True


def watch(
    folder: Path,
    api: str,
    interval: float,
    extensions: Set[str],
    on_success: str,
    include_existing: bool,
) -> None:
    """Loop forever, processing new files as they arrive."""
    folder = folder.expanduser().resolve()
    folder.mkdir(parents=True, exist_ok=True)
    processed_dir = folder / "_processed"

    print(f"[watch] folder: {folder}")
    print(f"[watch] api:    {api}")
    print(f"[watch] every:  {interval}s")
    print(f"[watch] ext:    {sorted(extensions)}")
    print(f"[watch] on success: {on_success}")
    if not include_existing:
        print("[watch] ignoring files older than now (use --include-existing to override)")

    seen: Set[Path] = set()
    min_mtime = None if include_existing else time.time()

    try:
        while True:
            new_files = find_files(folder, extensions, seen, min_mtime)
            for path in sorted(new_files):
                ok = process_file(path, api, on_success, processed_dir)
                # Mark as seen so we don't reprocess if it lingers
                # (e.g. when on_success == "leave").
                seen.add(path)
                if not ok:
                    # On failure, drop from `seen` so a later attempt
                    # can pick it up after the network recovers.
                    seen.discard(path)
            time.sleep(interval)
    except KeyboardInterrupt:
        print("\n[watch] stopped", file=sys.stderr)


def main() -> None:
    p = argparse.ArgumentParser(
        description="Watch a folder and capture text files as journal seeds."
    )
    p.add_argument("--dir", "-d", default="~/concordance-inbox",
                   help="Folder to watch (default: ~/concordance-inbox)")
    p.add_argument("--api", default=DEFAULT_API,
                   help=f"Concordance API base URL (default: {DEFAULT_API})")
    p.add_argument("--interval", type=float, default=DEFAULT_INTERVAL_SECONDS,
                   help="Seconds between scans (default: 5)")
    p.add_argument("--ext", default=",".join(sorted(DEFAULT_EXTENSIONS)),
                   help="Comma-separated file extensions to watch "
                        f"(default: {','.join(sorted(DEFAULT_EXTENSIONS))})")
    p.add_argument("--on-success", choices=["delete", "move", "leave"],
                   default=DEFAULT_ON_SUCCESS,
                   help="What to do with a file after successful capture "
                        "(default: move to ./_processed/)")
    p.add_argument("--include-existing", action="store_true",
                   help="Also process files already in the folder at startup. "
                        "By default only files newer than start time are picked up.")
    args = p.parse_args()

    extensions = {e.strip().lower() for e in args.ext.split(",") if e.strip()}
    extensions = {e if e.startswith(".") else "." + e for e in extensions}

    watch(
        folder=Path(args.dir),
        api=args.api,
        interval=args.interval,
        extensions=extensions,
        on_success=args.on_success,
        include_existing=args.include_existing,
    )


if __name__ == "__main__":
    main()
