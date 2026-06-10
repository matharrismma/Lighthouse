#!/usr/bin/env python3
"""export_corpus.py — turn /d/<slug> records into a training corpus.

Reads every JSON record under data/discernments/, filters by kind and quality,
and writes JSONL training pairs to data/training_corpus/.

The output schema is stable: narrowhighway.training_pair/1. The fine-tuning
script reads JSONL lines of this shape. As long as the schema doesn't change,
training data accumulated today remains usable forever.

Default behavior:
    - Includes kind=teaching and kind=gated-generation
    - Skips records where final_decision in {rejected, hold}
    - Hash-deduplicates by content_hash
    - Filters by minimum prompt + completion length (signal-to-noise)
    - Outputs one JSONL file per kind, plus a manifest

Configuration (env vars):
    NH_REPO_ROOT       default: <this file>/../
    NH_CORPUS_DIR      default: <repo>/data/training_corpus
    NH_MIN_PROMPT_CHARS    default: 30
    NH_MIN_COMPLETION_CHARS default: 30
    NH_INCLUDE_KINDS   default: "teaching,gated-generation"
    NH_EXCLUDE_DECISIONS default: "rejected,hold"

Usage:
    python tools/export_corpus.py
    python tools/export_corpus.py --dry-run        # just count
    python tools/export_corpus.py --include-all    # include rejected/hold too
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import logging.handlers
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

# ── Configuration ──────────────────────────────────────────────────
REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT",
    str(Path(__file__).resolve().parent.parent),
)).resolve()

DISCERN_DIR = REPO_ROOT / "data" / "discernments"
CORPUS_DIR = Path(os.environ.get(
    "NH_CORPUS_DIR",
    str(REPO_ROOT / "data" / "training_corpus"),
)).resolve()
LOG_DIR = REPO_ROOT / "logs"

MIN_PROMPT_CHARS = int(os.environ.get("NH_MIN_PROMPT_CHARS", "30"))
MIN_COMPLETION_CHARS = int(os.environ.get("NH_MIN_COMPLETION_CHARS", "30"))
DEFAULT_INCLUDE_KINDS = os.environ.get(
    "NH_INCLUDE_KINDS", "teaching,gated-generation"
).split(",")
DEFAULT_EXCLUDE_DECISIONS = set(os.environ.get(
    "NH_EXCLUDE_DECISIONS", "rejected,hold"
).split(","))


# ── Logging ────────────────────────────────────────────────────────
def _setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("nh.export_corpus")
    logger.setLevel(logging.INFO)
    fh = logging.handlers.RotatingFileHandler(
        LOG_DIR / "export_corpus.log",
        maxBytes=5 * 1024 * 1024, backupCount=3, encoding="utf-8",
    )
    fh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    logger.addHandler(fh)
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    sh = logging.StreamHandler(sys.stdout)
    sh.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    logger.addHandler(sh)
    return logger


log = _setup_logging()


# ── Record-to-training-pair conversion ─────────────────────────────

def teaching_to_pair(d: dict) -> dict | None:
    """A kind=teaching record becomes a labeled training pair:
    (prompt=teaching text, completion=engine's structured discernment).

    Since teaching records have buckets that fill over time, today the
    "completion" is the citation-and-keyword first-pass output. As the
    buckets fill (operator + witnesses weighing in), the pair gets richer.
    Versioning of the source record (schema) lets us trace this.
    """
    teaching = d.get("teaching") or ""
    if len(teaching) < MIN_PROMPT_CHARS:
        return None

    citations = d.get("citations") or []
    keywords = d.get("keyword_hits") or []
    buckets = d.get("buckets") or {}

    # Construct the "completion" — a structured summary the model should learn
    parts = []
    if citations:
        parts.append("Citations: " + ", ".join(
            c.get("raw", "") for c in citations
        ))
    if keywords:
        healthy = [k for k in keywords if k.get("kind") == "healthy"]
        concerning = [k for k in keywords if k.get("kind") == "concerning"]
        if healthy:
            parts.append("Healthy markers: " + ", ".join(
                h.get("tag", "") for h in healthy
            ))
        if concerning:
            parts.append("Concerning patterns: " + ", ".join(
                c.get("tag", "") for c in concerning
            ))
    for bucket_name in ("stable", "conditional", "hold"):
        items = buckets.get(bucket_name) or []
        if items:
            parts.append(f"{bucket_name.capitalize()}: " + "; ".join(
                (it.get("claim", "") if isinstance(it, dict) else str(it))
                for it in items
            ))

    completion = "\n".join(parts).strip()
    if len(completion) < MIN_COMPLETION_CHARS:
        return None

    return {
        "schema": "narrowhighway.training_pair/1",
        "source_kind": "teaching",
        "source_schema": d.get("schema", ""),
        "source_slug": d.get("slug", ""),
        "created_at": d.get("created_at", ""),
        "prompt": teaching,
        "completion": completion,
        "metadata": {
            "citations": citations,
            "keyword_hits": keywords,
            "bucket_filled": sum(
                len(buckets.get(b, [])) for b in ("stable", "conditional", "hold")
            ),
            "status": d.get("status", ""),
        },
    }


def gated_to_pair(d: dict) -> dict | None:
    """A kind=gated-generation record is the canonical training pair —
    (prompt, gated_completion) with full provenance.

    Note: this returns the simple training-pair/1 shape. For richer
    training data that preserves the FULL distributed trail (so the LLM
    organ learns to produce drafts the rest of the body can quickly
    evaluate), use gated_to_organ_pair() — schema training_pair_organ/1.
    See organic-design.html: the model is one organ. The training data
    that respects that distinction is the organ-pair, not the simple pair.
    """
    prompt_obj = d.get("prompt") or {}
    if isinstance(prompt_obj, dict):
        prompt = prompt_obj.get("text", "")
    else:
        prompt = str(prompt_obj)
    if len(prompt) < MIN_PROMPT_CHARS:
        return None

    gen = d.get("generation") or {}
    completion = gen.get("text", "") if isinstance(gen, dict) else ""
    if len(completion) < MIN_COMPLETION_CHARS:
        return None

    return {
        "schema": "narrowhighway.training_pair/1",
        "source_kind": "gated-generation",
        "source_schema": d.get("schema", ""),
        "source_slug": d.get("slug", ""),
        "created_at": d.get("created_at", ""),
        "prompt": prompt,
        "completion": completion,
        "metadata": {
            "final_decision": d.get("final_decision"),
            "base_model": d.get("base_model"),
            "verifier_results": [
                {"verifier": vr.get("verifier"),
                 "verdict": vr.get("verdict"),
                 "summary": vr.get("summary")}
                for vr in (d.get("verifier_results") or [])
            ],
            "gate_results": [
                {"gate": g.get("gate"), "decision": g.get("decision")}
                for g in (d.get("gate_results") or [])
            ],
            "content_hash": d.get("content_hash"),
            "metrics": d.get("metrics"),
        },
    }


def gated_to_organ_pair(d: dict) -> dict | None:
    """The OI-respecting training-pair shape: schema training_pair_organ/1.

    Preserves the FULL distributed trail (every gate decision, every
    verifier verdict, the witness state, the audit hash) so a fine-tune
    teaches the LLM organ to produce drafts that:

      - cite Scripture cleanly (so scripture_anchors passes fast),
      - mark uncertain claims explicitly (so theology_doctrine doesn't
        have to guess),
      - structure output in ways the verifiers can read deterministically,
      - never claim to be the verdict (the body decides, not the organ).

    A fine-tune on training_pair/1 risks producing a model that mimics
    gated outputs without internalizing 'I am one organ.' A fine-tune on
    training_pair_organ/1 includes the surrounding body's response in the
    target, so the model learns to produce drafts the body can quickly
    judge — the correct optimization for OI.
    """
    prompt_obj = d.get("prompt") or {}
    if isinstance(prompt_obj, dict):
        prompt = prompt_obj.get("text", "")
    else:
        prompt = str(prompt_obj)
    if len(prompt) < MIN_PROMPT_CHARS:
        return None

    gen = d.get("generation") or {}
    completion = gen.get("text", "") if isinstance(gen, dict) else ""
    if len(completion) < MIN_COMPLETION_CHARS:
        return None

    return {
        "schema": "narrowhighway.training_pair_organ/1",
        "source_kind": "gated-generation",
        "source_schema": d.get("schema", ""),
        "source_slug": d.get("slug", ""),
        "created_at": d.get("created_at", ""),
        # The triple the model learns: prompt + completion + how the body
        # received it. The completion is what the LLM organ produced; the
        # body_response is how the rest of the engine read that draft.
        "prompt": prompt,
        "completion": completion,
        "body_response": {
            "final_decision": d.get("final_decision"),
            "gates": [
                {"gate": g.get("gate"),
                 "decision": g.get("decision"),
                 "reason": g.get("reason", "")}
                for g in (d.get("gate_results") or [])
            ],
            "verifiers": [
                {"verifier": vr.get("verifier"),
                 "verdict": vr.get("verdict"),
                 "summary": vr.get("summary", ""),
                 "details_count": len(vr.get("details") or [])}
                for vr in (d.get("verifier_results") or [])
            ],
            "witness_state": next(
                (g.get("evidence", {}).get("witness_count")
                 for g in (d.get("gate_results") or [])
                 if g.get("gate") == "BROTHERS"),
                0,
            ),
        },
        "provenance": {
            "base_model": d.get("base_model"),
            "content_hash": d.get("content_hash"),
            "metrics": d.get("metrics"),
        },
    }


# Two converter sets — pick via --schema cli flag.
#   training_pair/1        — simple (prompt, completion). Fast, lossy.
#   training_pair_organ/1  — preserves the full distributed trail. Slower,
#                            larger files, but trains the LLM organ
#                            correctly (per /organic-design.html).
CONVERTERS_V1 = {
    "teaching": teaching_to_pair,
    "gated-generation": gated_to_pair,
}
CONVERTERS_ORGAN = {
    "teaching": teaching_to_pair,            # teaching v1 is fine; no body_response yet
    "gated-generation": gated_to_organ_pair, # gated v_organ preserves the body
}
CONVERTERS = CONVERTERS_V1  # default; may be replaced at runtime


def pair_hash(pair: dict) -> str:
    """Stable hash over prompt + completion for dedupe."""
    key = (pair.get("prompt", "") + "\n---\n" + pair.get("completion", ""))
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


# ── Main ───────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(description="Export /d/<slug> records as training corpus")
    parser.add_argument("--dry-run", action="store_true",
                        help="Count and report; don't write JSONL")
    parser.add_argument("--include-all", action="store_true",
                        help="Include rejected/hold records too")
    parser.add_argument("--include-kinds", default=",".join(DEFAULT_INCLUDE_KINDS),
                        help="Comma-separated list of kinds to include")
    parser.add_argument(
        "--schema", default="organ",
        choices=["organ", "v1"],
        help=(
            "Training-pair schema. 'organ' (default) preserves the full "
            "distributed trail — gate decisions, verifier verdicts, witness "
            "state — so the LLM organ learns to produce drafts the body can "
            "quickly judge (the OI-respecting shape). 'v1' is the simple "
            "(prompt, completion) shape — faster, lossier, and risks "
            "collapsing distributed sophistication into one model."
        ),
    )
    args = parser.parse_args()

    # Pick the converter set based on --schema
    global CONVERTERS
    CONVERTERS = CONVERTERS_ORGAN if args.schema == "organ" else CONVERTERS_V1
    schema_name = ("narrowhighway.training_pair_organ/1"
                   if args.schema == "organ"
                   else "narrowhighway.training_pair/1")

    include_kinds = [k.strip() for k in args.include_kinds.split(",") if k.strip()]
    exclude_decisions = set() if args.include_all else DEFAULT_EXCLUDE_DECISIONS

    log.info(
        "export start | repo=%s discernments=%s out=%s kinds=%s exclude_decisions=%s",
        REPO_ROOT, DISCERN_DIR, CORPUS_DIR, include_kinds,
        sorted(exclude_decisions) or "(none)",
    )

    if not DISCERN_DIR.exists():
        log.error("discernments dir missing: %s", DISCERN_DIR)
        return 2

    if not args.dry_run:
        CORPUS_DIR.mkdir(parents=True, exist_ok=True)

    stats = {
        "total_records": 0,
        "by_kind": {},
        "by_decision": {},
        "skipped_unknown_kind": 0,
        "skipped_excluded_decision": 0,
        "skipped_too_short": 0,
        "skipped_dedupe": 0,
        "written": {},
    }
    seen_hashes: dict[str, set[str]] = {}
    out_files: dict[str, object] = {}
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")

    try:
        for jf in sorted(DISCERN_DIR.glob("*.json"), key=lambda p: p.stat().st_mtime):
            stats["total_records"] += 1
            try:
                d = json.loads(jf.read_text(encoding="utf-8"))
            except Exception as e:
                log.warning("could not parse %s: %s", jf.name, e)
                continue

            kind = d.get("kind") or "legacy"
            stats["by_kind"][kind] = stats["by_kind"].get(kind, 0) + 1
            decision = d.get("final_decision") or d.get("status") or "n/a"
            stats["by_decision"][decision] = stats["by_decision"].get(decision, 0) + 1

            if kind not in include_kinds:
                stats["skipped_unknown_kind"] += 1
                continue
            if decision in exclude_decisions:
                stats["skipped_excluded_decision"] += 1
                continue

            converter = CONVERTERS.get(kind)
            if not converter:
                stats["skipped_unknown_kind"] += 1
                continue

            pair = converter(d)
            if not pair:
                stats["skipped_too_short"] += 1
                continue

            h = pair_hash(pair)
            kind_seen = seen_hashes.setdefault(kind, set())
            if h in kind_seen:
                stats["skipped_dedupe"] += 1
                continue
            kind_seen.add(h)

            stats["written"][kind] = stats["written"].get(kind, 0) + 1

            if not args.dry_run:
                if kind not in out_files:
                    out_path = CORPUS_DIR / f"corpus-{kind}-{stamp}.jsonl"
                    out_files[kind] = (out_path, out_path.open("w", encoding="utf-8"))
                    log.info("opening %s", out_path.name)
                _, fh = out_files[kind]
                fh.write(json.dumps(pair, ensure_ascii=False) + "\n")
    finally:
        for _, (_, fh) in out_files.items():
            fh.close()

    # Manifest
    if not args.dry_run and out_files:
        manifest = {
            "schema": "narrowhighway.corpus_manifest/1",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "training_pair_schema": schema_name,
            "include_kinds": include_kinds,
            "exclude_decisions": sorted(exclude_decisions),
            "stats": stats,
            "files": [
                {"kind": kind, "path": str(p.relative_to(REPO_ROOT)).replace("\\", "/")}
                for kind, (p, _) in out_files.items()
            ],
        }
        manifest_path = CORPUS_DIR / f"manifest-{stamp}.json"
        manifest_path.write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        log.info("wrote manifest: %s", manifest_path.name)

    log.info("=" * 60)
    log.info("DONE")
    log.info("  total records scanned: %d", stats["total_records"])
    log.info("  by kind: %s", dict(stats["by_kind"]))
    log.info("  by decision: %s", dict(stats["by_decision"]))
    log.info("  skipped (unknown kind): %d", stats["skipped_unknown_kind"])
    log.info("  skipped (excluded decision): %d", stats["skipped_excluded_decision"])
    log.info("  skipped (too short): %d", stats["skipped_too_short"])
    log.info("  skipped (dedupe): %d", stats["skipped_dedupe"])
    log.info("  written: %s", dict(stats["written"]))
    if args.dry_run:
        log.info("  (DRY RUN — no files written)")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("export interrupted")
        sys.exit(130)
