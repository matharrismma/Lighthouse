#!/usr/bin/env python3
"""substrate_backup.py — nightly snapshot of the training corpus.

The substrate IS the training corpus. Every /d/<slug> record, every almanac
entry that passed the gates, every signed receipt is labeled, gated,
aligned training data. Losing it is unrecoverable; OneDrive sync alone is
not a backup (mid-write corruption, sync conflicts, no point-in-time
restore).

This script snapshots the IRREPLACEABLE bits — not the reproducible mp4s,
animation renders, or raw source media — to a timestamped tar.gz outside
OneDrive. Keeps the last NH_BACKUP_RETAIN snapshots; writes a SHA256
manifest alongside each.

What's included (load-bearing for training and audit):
  data/discernments/        - /d/<slug> permanent records
  data/almanac/             - verified almanac entries
  data/almanac_proposals/   - entries awaiting review
  data/keep/                - operator state, receipts, signed trails
  data/seeds/               - seeds (search-misses) + packet snapshots
  data/cards/               - card metadata
  data/library_inventory/   - what we've cataloged
  data/grid_connections.jsonl - the graph
  data/bible_en/            - English Bible (reference; foundational)
  content/                  - channel manifests, bespoke content
  ledger/                   - signed receipts (if present)
  site/sitemap*.xml         - dynamic sitemap state

NOT included (reproducible, would bloat the backup 10x):
  data/publish/             - generated mp4s, can re-render from manifests
  data/serials/             - animation runs, can re-run
  data/raw_sources/         - source media, archived elsewhere
  data/bible_<other_langs>/ - translations, reproducible from sources

Configuration (env vars):
  NH_BACKUP_DIR     default: ~/Backups/narrowhighway  (OUTSIDE OneDrive)
  NH_BACKUP_RETAIN  default: 14   (keep last N snapshots)
  NH_REPO_ROOT      default: <this file>/../
  NH_LOG_DIR        default: <repo>/logs

Output per run:
  <BACKUP_DIR>/substrate-YYYYmmdd-HHMMSS.tar.gz
  <BACKUP_DIR>/substrate-YYYYmmdd-HHMMSS.manifest.json
  <repo>/logs/backup.log
"""

from __future__ import annotations

import hashlib
import json
import logging
import logging.handlers
import os
import sys
import tarfile
import time
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────
REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT",
    str(Path(__file__).resolve().parent.parent)
)).resolve()

BACKUP_DIR = Path(os.environ.get(
    "NH_BACKUP_DIR",
    str(Path.home() / "Backups" / "narrowhighway")
)).resolve()

RETAIN = int(os.environ.get("NH_BACKUP_RETAIN", "14"))

LOG_DIR = Path(os.environ.get("NH_LOG_DIR", str(REPO_ROOT / "logs"))).resolve()

# Paths to include, relative to REPO_ROOT. Missing paths are silently skipped.
INCLUDE_PATHS = [
    "data/discernments",
    "data/almanac",
    "data/almanac_proposals",
    "data/keep",
    "data/seeds",
    "data/cards",
    "data/library_inventory",
    "data/grid_connections.jsonl",
    "data/bible_en",
    "content",
    "ledger",
    "site/sitemap.xml",
    "site/sitemap_index.xml",
    "site/sitemap_cards.xml",
    "site/sitemap_discernments.xml",
]


# ── Logging ────────────────────────────────────────────────────────
def _setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("nh.backup")
    logger.setLevel(logging.INFO)
    fh = logging.handlers.RotatingFileHandler(
        LOG_DIR / "backup.log", maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8"
    )
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    logger.addHandler(fh)
    # stdout: reconfigure to UTF-8 so unicode doesn't crash on Windows cp1252
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    logger.addHandler(sh)
    return logger


log = _setup_logging()


# ── Helpers ────────────────────────────────────────────────────────
def utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")


def sha256_of(path: Path, chunk: int = 1024 * 1024) -> str:
    """Stream a file through SHA256."""
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            buf = f.read(chunk)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def collect_files(repo_root: Path, include: list[str]) -> list[Path]:
    """Resolve every file under the include list. Skip missing entries."""
    files: list[Path] = []
    for rel in include:
        p = (repo_root / rel).resolve()
        if not p.exists():
            log.info("skip (missing): %s", rel)
            continue
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            for f in p.rglob("*"):
                if f.is_file():
                    files.append(f)
    return files


def write_tarball(out_path: Path, files: list[Path], repo_root: Path) -> tuple[int, int, list[str]]:
    """Stream files into a tar.gz. Return (count, bytes, skipped[])."""
    count = 0
    total_bytes = 0
    skipped: list[str] = []
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with tarfile.open(out_path, "w:gz", compresslevel=6) as tar:
        for f in files:
            try:
                arcname = str(f.relative_to(repo_root)).replace("\\", "/")
                tar.add(str(f), arcname=arcname, recursive=False)
                count += 1
                total_bytes += f.stat().st_size
            except (OSError, PermissionError) as e:
                skipped.append(f"{f}: {e}")
    return count, total_bytes, skipped


def write_manifest(
    manifest_path: Path,
    tar_path: Path,
    files: list[Path],
    repo_root: Path,
    file_count: int,
    file_bytes: int,
    skipped: list[str],
) -> None:
    """Write a JSON manifest next to the tarball: hash, file list, stats."""
    started = time.time()
    tar_size = tar_path.stat().st_size
    tar_sha = sha256_of(tar_path)
    manifest = {
        "schema": "narrowhighway.substrate.backup/1",
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "tar": {
            "name": tar_path.name,
            "size_bytes": tar_size,
            "sha256": tar_sha,
        },
        "stats": {
            "file_count": file_count,
            "uncompressed_bytes": file_bytes,
            "compression_ratio": (
                round(file_bytes / tar_size, 2) if tar_size > 0 else None
            ),
            "skipped_count": len(skipped),
            "hashing_seconds": round(time.time() - started, 1),
        },
        "include": INCLUDE_PATHS,
        "skipped": skipped[:200],  # cap so the manifest stays small
        "files": sorted(
            str(f.relative_to(repo_root)).replace("\\", "/") for f in files
        )[:50000],  # cap; for very large corpora
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def rotate_old(backup_dir: Path, retain: int) -> int:
    """Delete snapshots older than the most-recent `retain`. Return count removed."""
    snaps = sorted(
        backup_dir.glob("substrate-*.tar.gz"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )
    removed = 0
    for old in snaps[retain:]:
        try:
            old.unlink()
            # Remove the matching manifest if it exists
            manifest = old.with_suffix("").with_suffix(".manifest.json")
            if manifest.exists():
                manifest.unlink()
            log.info("rotated out: %s", old.name)
            removed += 1
        except OSError as e:
            log.warning("could not delete %s: %s", old, e)
    return removed


# ── Main ───────────────────────────────────────────────────────────
def main() -> int:
    log.info(
        "backup start |repo=%s target=%s retain=%d",
        REPO_ROOT,
        BACKUP_DIR,
        RETAIN,
    )

    if not REPO_ROOT.exists():
        log.error("repo root missing: %s", REPO_ROOT)
        return 2

    started = time.time()
    files = collect_files(REPO_ROOT, INCLUDE_PATHS)
    if not files:
        log.error("no files found to back up — check paths/configuration")
        return 3
    log.info("collected %d files for snapshot", len(files))

    stamp = utc_stamp()
    tar_path = BACKUP_DIR / f"substrate-{stamp}.tar.gz"
    manifest_path = BACKUP_DIR / f"substrate-{stamp}.manifest.json"

    log.info("writing tarball -> %s", tar_path)
    try:
        file_count, file_bytes, skipped = write_tarball(tar_path, files, REPO_ROOT)
    except Exception as e:
        log.exception("tarball write failed: %s", e)
        return 4

    tar_size = tar_path.stat().st_size
    log.info(
        "wrote %d files (%.1f MB raw -> %.1f MB compressed, %d skipped)",
        file_count,
        file_bytes / 1024 / 1024,
        tar_size / 1024 / 1024,
        len(skipped),
    )

    log.info("writing manifest -> %s", manifest_path.name)
    try:
        write_manifest(
            manifest_path, tar_path, files, REPO_ROOT, file_count, file_bytes, skipped
        )
    except Exception as e:
        log.exception("manifest write failed: %s", e)
        # tarball is on disk; not a fatal failure of the backup itself
        # continue to rotation

    rotated = rotate_old(BACKUP_DIR, RETAIN)
    if rotated:
        log.info("rotated out %d old snapshot(s)", rotated)

    elapsed = time.time() - started
    log.info(
        "backup done |%s |%.1fs |%.1f MB on disk",
        tar_path.name,
        elapsed,
        tar_size / 1024 / 1024,
    )
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("backup interrupted by user")
        sys.exit(130)
