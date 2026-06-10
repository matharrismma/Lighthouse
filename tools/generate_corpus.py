#!/usr/bin/env python3
"""generate_corpus.py — produce gated responses at scale to build the
training corpus for the standalone model.

Reads a prompt list (JSONL with {prompt} per line, OR plain text one
prompt per line), runs each through the gated pipeline (RED -> Anthropic
-> verifiers -> FLOOR -> BROTHERS -> GOD -> hash), and persists each
result as a /d/<slug> record under data/discernments/.

The existing tools/export_corpus.py then exports those records as
narrowhighway.training_pair/1 JSONL ready for fine-tuning.

Cost-aware:
  - Logs cost-per-prompt as we go (Anthropic Sonnet 4.5: ~$0.003 per prompt)
  - --max-cost halts the run if accumulated cost exceeds the budget
  - Rate-limiting: --sleep <seconds> between calls
  - Skip duplicates by prompt hash

Usage:
    # 100-prompt smoke run, $0.50 budget cap, echo (no API cost):
    python tools/generate_corpus.py --prompts data/eval/prompts_v1.jsonl --base echo --max-cost 0.50

    # 1000-prompt real run with Anthropic, $10 budget cap, 0.5s between calls:
    python tools/generate_corpus.py --prompts data/prompt_sets/v1.jsonl --base anthropic --max-cost 10 --sleep 0.5

    # Then export:
    python tools/export_corpus.py
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import logging.handlers
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT",
    str(Path(__file__).resolve().parent.parent),
)).resolve()
DISCERN_DIR = REPO_ROOT / "data" / "discernments"
LOG_DIR = REPO_ROOT / "logs"

sys.path.insert(0, str(REPO_ROOT))


# Robust .env loader (same as run_benchmark.py)
def _load_env_robust(env_path: Path) -> int:
    if not env_path.exists():
        return 0
    import re as _re
    key_re = _re.compile(r"^[A-Z][A-Z0-9_]*$")
    loaded = 0
    for line in env_path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        k = k.strip()
        if not key_re.match(k):
            continue
        v = v.strip()
        if (v.startswith('"') and v.endswith('"')) or \
           (v.startswith("'") and v.endswith("'")):
            v = v[1:-1]
        if not os.environ.get(k):
            os.environ[k] = v
            loaded += 1
    return loaded


_load_env_robust(REPO_ROOT / ".env")


def _setup_logging() -> logging.Logger:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("nh.generate_corpus")
    logger.setLevel(logging.INFO)
    fh = logging.handlers.RotatingFileHandler(
        LOG_DIR / "generate_corpus.log",
        maxBytes=10 * 1024 * 1024, backupCount=5, encoding="utf-8",
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


def load_prompts(path: Path) -> list[dict]:
    """Load prompts from JSONL ({prompt: str, ...} per line) or plain text."""
    if not path.exists():
        raise FileNotFoundError(f"prompt set missing: {path}")
    out: list[dict] = []
    text = path.read_text(encoding="utf-8")
    # Detect JSONL vs plain text
    first_line = next((l for l in text.splitlines() if l.strip()), "").strip()
    if first_line.startswith("{"):
        for i, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except Exception as e:
                log.warning("line %d not valid JSON: %s", i, e)
                continue
            if "prompt" not in obj:
                continue
            out.append(obj)
    else:
        for line in text.splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            out.append({"prompt": line})
    return out


def prompt_hash(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def load_existing_hashes() -> set[str]:
    """Compute prompt-hash of every existing /d/<slug> record so we skip duplicates."""
    seen: set[str] = set()
    if not DISCERN_DIR.exists():
        return seen
    for jf in DISCERN_DIR.glob("*.json"):
        try:
            d = json.loads(jf.read_text(encoding="utf-8"))
        except Exception:
            continue
        prompt = None
        if isinstance(d.get("prompt"), dict):
            prompt = d["prompt"].get("text")
        elif isinstance(d.get("prompt"), str):
            prompt = d["prompt"]
        elif d.get("teaching"):
            prompt = d["teaching"]
        elif d.get("question"):
            prompt = d["question"]
        if prompt:
            seen.add(prompt_hash(prompt))
    return seen


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Generate gated responses at scale for the training corpus"
    )
    ap.add_argument("--prompts", required=True, help="Path to prompts JSONL or text file")
    ap.add_argument("--base", default="anthropic", choices=["anthropic", "echo"])
    ap.add_argument("--limit", type=int, default=0, help="Max number of prompts (0 = all)")
    ap.add_argument("--max-cost", type=float, default=10.0,
                    help="Halt if accumulated cost exceeds this many USD")
    ap.add_argument("--sleep", type=float, default=0.0,
                    help="Seconds to sleep between API calls (rate-limit)")
    ap.add_argument("--skip-dupes", action="store_true", default=True,
                    help="Skip prompts already in the discernments store")
    ap.add_argument("--dry-run", action="store_true", help="Don't actually call the LLM")
    args = ap.parse_args()

    from api.generate_gated import run_gated, AnthropicAdapter, EchoAdapter

    base = EchoAdapter() if args.base == "echo" else AnthropicAdapter()

    prompts = load_prompts(Path(args.prompts))
    if args.limit:
        prompts = prompts[: args.limit]
    log.info("loaded %d prompts from %s", len(prompts), args.prompts)

    seen = load_existing_hashes() if args.skip_dupes else set()
    if seen:
        log.info("loaded %d existing prompt hashes (will skip dupes)", len(seen))

    DISCERN_DIR.mkdir(parents=True, exist_ok=True)

    run_id = secrets.token_hex(4)
    started = time.time()
    stats = {
        "run_id": run_id,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "prompts_seen": 0,
        "prompts_skipped_dupe": 0,
        "prompts_run": 0,
        "succeeded": 0,
        "failed": 0,
        "final_decisions": {},
        "total_cost_usd": 0.0,
        "total_tokens_in": 0,
        "total_tokens_out": 0,
    }

    try:
        for i, row in enumerate(prompts, 1):
            stats["prompts_seen"] += 1
            prompt = row.get("prompt", "").strip()
            if not prompt or len(prompt) < 3:
                continue

            h = prompt_hash(prompt)
            if args.skip_dupes and h in seen:
                stats["prompts_skipped_dupe"] += 1
                continue

            if stats["total_cost_usd"] >= args.max_cost:
                log.warning("cost cap reached ($%.4f >= $%.2f); halting",
                            stats["total_cost_usd"], args.max_cost)
                break

            log.info("[%d/%d] $%.4f spent · %s",
                     i, len(prompts), stats["total_cost_usd"], prompt[:70])

            if args.dry_run:
                continue

            try:
                resp = run_gated(prompt, base=base)
            except Exception as e:
                log.warning("gated run failed: %s", e)
                stats["failed"] += 1
                continue

            stats["succeeded"] += 1
            stats["prompts_run"] += 1
            seen.add(h)
            cost = (resp.get("metrics") or {}).get("total_cost_usd", 0.0) or 0.0
            stats["total_cost_usd"] += float(cost)
            gen = resp.get("generation") or {}
            stats["total_tokens_in"] += int(gen.get("tokens_in") or 0)
            stats["total_tokens_out"] += int(gen.get("tokens_out") or 0)
            final = resp.get("final_decision") or "unknown"
            stats["final_decisions"][final] = stats["final_decisions"].get(final, 0) + 1

            # Persist as /d/<slug>
            # Same slug pattern as the endpoint
            import re as _re
            slug_seed = _re.sub(r"[^a-z0-9]+", "-", prompt.lower())[:60].strip("-") or "gated"
            slug = "gen-" + slug_seed + "-" + secrets.token_hex(2)
            resp["slug"] = slug
            (DISCERN_DIR / f"{slug}.json").write_text(
                json.dumps(resp, ensure_ascii=False, indent=2), encoding="utf-8"
            )

            if args.sleep > 0:
                time.sleep(args.sleep)
    finally:
        elapsed = round(time.time() - started, 1)
        stats["wall_seconds"] = elapsed
        stats["ended_at"] = datetime.now(timezone.utc).isoformat()
        log.info("=" * 60)
        log.info("RUN COMPLETE (run %s) in %.1fs", run_id, elapsed)
        log.info("  prompts seen:    %d", stats["prompts_seen"])
        log.info("  duplicates:      %d", stats["prompts_skipped_dupe"])
        log.info("  succeeded:       %d", stats["succeeded"])
        log.info("  failed:          %d", stats["failed"])
        log.info("  tokens in/out:   %d / %d",
                 stats["total_tokens_in"], stats["total_tokens_out"])
        log.info("  total cost:      $%.4f", stats["total_cost_usd"])
        log.info("  final decisions: %s", dict(stats["final_decisions"]))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log.warning("interrupted by user")
        sys.exit(130)
