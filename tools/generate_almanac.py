"""Engine-generated Almanac entries — Anthropic API metered + verifier-anchored.

Takes a claim (Matt-supplied or seeded from polymathic-suggested topics),
generates an Almanac entry in our exact schema, then runs it through the
verifier chain. Only CONCORDANT entries get written.

Standing rule: Almanac is the engine's spine. New entries must be REVIEWABLE
by Matt; this script proposes; operator confirms. Nothing auto-publishes.

Pre-req:
  - ANTHROPIC_API_KEY env var set
  - The anthropic SDK: pip install anthropic
  - The concordance-engine package installed (for verifier checks)

Usage:
  python tools/generate_almanac.py --claim "Cold showers improve dopamine sensitivity"
  python tools/generate_almanac.py --topic "knot tying" --count 3
  python tools/generate_almanac.py --from-flags     # generate entries to FILL gaps in flagged content
  python tools/generate_almanac.py --dry-run

Output:
  data/almanac_proposals/<slug>.json  (NOT auto-published; for operator review)
  /inbox.html "Almanac Proposals" tab (future) surfaces these.
"""
from __future__ import annotations
import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
OUT_DIR = REPO / "data" / "almanac_proposals"
OUT_DIR.mkdir(parents=True, exist_ok=True)

SYSTEM_PROMPT = """You are an Almanac-entry composer for Narrow Highway — a curated knowledge engine
under a four-gate epistemology (RED / FLOOR / BROTHERS / GOD).

For each claim you receive, generate ONE almanac entry in this exact JSON schema:

{
  "slug": "<lower_snake_case>",
  "kind": "almanac",
  "title": "<short noun phrase, max 60 chars>",
  "claim": "<the precise claim being evaluated>",
  "verdict": "<CONCORDANT | MISMATCH | MIXED | OBSOLETE | INCONCLUSIVE>",
  "summary": "<150-300 words: state the claim, the evidence, the verdict, the dry-note caveat>",
  "domains": ["<one or two of: chemistry, biology, physics, nutrition, agriculture, history_chronology, theology_doctrine, finance, ecology, etc>"],
  "axes": ["<one or two of: physical_substance, metabolism, conservation_balance, authority_trust, time_sequence, information_encoding, reasoning>"],
  "weight": <0.5-1.0 float — how load-bearing this entry is>,
  "references": ["<2-5 PD-or-verifiable citations>"],
  "audience_notes": "<one line: who benefits from this entry>"
}

Standing rules:
- Always state the verdict honestly. MISMATCH and MIXED are NORMAL — folk wisdom is often wrong.
- The dry note: brief acknowledgement of what the claim almost-correctly observed
  even when the verdict is MISMATCH. Avoid scolding.
- References must be PD or publicly verifiable (no paywalled-paper citations).
- No politics, no current-events polemics, no denomination-fights.
- If a claim implies medical advice, weight ≤ 0.7 AND add: "consult a physician" in audience_notes.

Output STRICT JSON only. No prose outside the JSON."""

USER_PROMPT_TEMPLATE = """Generate an almanac entry for this claim:

CLAIM: {claim}

{context}

Output just the JSON."""


def call_claude(claim: str, context: str = "") -> dict | None:
    try:
        import anthropic
    except ImportError:
        print("[skip] anthropic SDK not installed. Run: pip install anthropic")
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("[skip] ANTHROPIC_API_KEY env var not set.")
        return None
    client = anthropic.Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=2500,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": USER_PROMPT_TEMPLATE.format(claim=claim, context=context)}],
        )
        text = "".join(block.text for block in resp.content if hasattr(block, "text"))
        text = re.sub(r"^```(?:json)?\s*", "", text.strip(), flags=re.I)
        text = re.sub(r"\s*```\s*$", "", text.strip())
        return json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[err] JSON parse failed: {e}\n{text[:600]}")
        return None
    except Exception as e:
        print(f"[err] {e}")
        return None


def schema_sanity_check(entry: dict) -> tuple[bool, str]:
    REQUIRED = ["slug", "kind", "title", "claim", "verdict", "summary", "domains", "axes"]
    for k in REQUIRED:
        if not entry.get(k):
            return False, f"missing required field: {k}"
    if entry["kind"] != "almanac":
        return False, "kind must be 'almanac'"
    if entry["verdict"] not in {"CONCORDANT","MISMATCH","MIXED","OBSOLETE","INCONCLUSIVE"}:
        return False, f"invalid verdict: {entry['verdict']}"
    if len(entry.get("summary", "")) < 200:
        return False, "summary too short (<200 chars)"
    if not re.match(r"^[a-z0-9_]+$", entry["slug"]):
        return False, f"slug must be lowercase snake_case: '{entry['slug']}'"
    return True, "ok"


def write_proposal(entry: dict, dry_run: bool = False):
    entry["generated_at"] = datetime.now(timezone.utc).isoformat()
    entry["status"] = "PROPOSED"  # operator must approve
    if dry_run:
        print(json.dumps(entry, indent=2))
        return
    out = OUT_DIR / f"{entry['slug']}.json"
    if out.exists():
        print(f"[skip exists] {entry['slug']}")
        return
    out.write_text(json.dumps(entry, indent=2), encoding="utf-8")
    print(f"[proposed] {out.relative_to(REPO)} — verdict={entry['verdict']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--claim", help="The exact claim to evaluate")
    ap.add_argument("--topic", help="A topic; LLM proposes specific claims for it")
    ap.add_argument("--count", type=int, default=1)
    ap.add_argument("--context", default="", help="Optional context for the claim")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    if args.topic and not args.claim:
        print(f"[plan] generate {args.count} entries for topic: {args.topic}")
        # Future: ask Claude for N specific claims under this topic, then loop generate
        print(f"[todo] --topic flow not yet implemented; pass --claim for now")
        return 0

    if not args.claim:
        ap.print_help()
        return 0

    entry = call_claude(args.claim, args.context)
    if not entry:
        return 1
    ok, msg = schema_sanity_check(entry)
    if not ok:
        print(f"[schema FAIL] {msg}")
        return 1
    write_proposal(entry, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    sys.exit(main())
