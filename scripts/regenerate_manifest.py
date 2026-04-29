#!/usr/bin/env python3
"""Regenerate packet_manifest.yaml with current SHA-256 hashes.

The manifest tracks stable text artifacts in the public-facing surface of the
repo. Run this from the repo root before cutting a release; the RELEASING.md
checklist asks for it.

Excludes: byte-compiled files, build artifacts, the lw/ private subtree, the
frozen 1.0.4 snapshot, eval data (the 706-line JSON would dominate the diff),
canon scaffolds, .github metadata, and Claude Code / pytest local caches.

Usage:
    python scripts/regenerate_manifest.py
    python scripts/regenerate_manifest.py --check    # exit nonzero if drift detected

Convenient as a CI step (e.g. in .github/workflows/ci.yml):
    python scripts/regenerate_manifest.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import os
import sys
from pathlib import Path

INCLUDE_DIRS = ["docs", "examples", "schema", "src", "tests", "scripts"]
INCLUDE_TOP = [
    ".gitignore",
    "AGENTS.md",
    "AUTHORITY.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "KNOWN_ISSUES.md",
    "LICENSE",
    "README.md",
    "RELEASING.md",
    "concordance_mcp_server.py",
    "llms.txt",
    "pyproject.toml",
]
EXCLUDE_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".git",
    ".github",
    ".claude",
    "concordance_engine-1.0.4",
    "lw",
    "eval",
    "canons",
    "dist",
    "build",
}
EXCLUDE_FILE_SUFFIXES = (".pyc", ".pyo")
MANIFEST_PATH = "packet_manifest.yaml"


def collect_files(repo_root: Path):
    files = []
    for f in INCLUDE_TOP:
        p = repo_root / f
        if p.exists():
            files.append(p)
    for d in INCLUDE_DIRS:
        base = repo_root / d
        if not base.exists():
            continue
        for root, dirs, fnames in os.walk(base):
            dirs[:] = [
                x for x in dirs
                if x not in EXCLUDE_DIR_NAMES and not x.startswith(".")
            ]
            for fn in fnames:
                if fn.endswith(EXCLUDE_FILE_SUFFIXES) or fn.startswith("."):
                    continue
                files.append(Path(root) / fn)
    return sorted(set(files))


def render_manifest(repo_root: Path) -> str:
    lines = ["packet_manifest:"]
    for p in collect_files(repo_root):
        h = hashlib.sha256(p.read_bytes()).hexdigest()
        rel = p.relative_to(repo_root).as_posix()
        lines.append(f"  {rel}: {h}")
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true",
                    help="Compare against the on-disk manifest; exit 1 if they differ.")
    ap.add_argument("--repo-root", default=".",
                    help="Repository root (default: cwd)")
    args = ap.parse_args()

    repo_root = Path(args.repo_root).resolve()
    new = render_manifest(repo_root)
    target = repo_root / MANIFEST_PATH

    if args.check:
        if not target.exists():
            print(f"ERROR: {MANIFEST_PATH} does not exist", file=sys.stderr)
            return 1
        existing = target.read_text()
        if existing == new:
            print("OK: manifest is up to date")
            return 0
        print("DRIFT: manifest does not match current files. Run "
              "`python scripts/regenerate_manifest.py` to refresh.",
              file=sys.stderr)
        return 1

    target.write_text(new)
    print(f"Wrote {target} ({new.count(chr(10))} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
