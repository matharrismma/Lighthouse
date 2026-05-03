"""Concordance Engine CLI.

Two entry points for two audiences:

  concordance validate <packet.json>   # legacy/agent — EngineResult, gates only
  concordance ask <packet.json|--text> # human — full WitnessRecord walkthrough

The `ask` subcommand is the human-facing surface. Default output is a
Socratic markdown walkthrough; --compact for one-screen summary; --json
for the canonical sealed WitnessRecord.

Exit codes (both subcommands):
    0  PASS
    1  REJECT
    2  QUARANTINE
    3  schema validation failure (packet not even well-formed)
    4  CLI usage error
    5  natural-language parse failed (--text input only)
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

from .engine import EngineConfig, validate_packet, validate_and_seal
from .packet import EngineResult, GateResult
from .validate import load_schema, validate_against_schema
from .walkthrough import (
    render_walkthrough, render_walkthrough_compact, render_walkthrough_html,
)
from .witness_record import WitnessRecord


_EXIT = {"PASS": 0, "REJECT": 1, "QUARANTINE": 2}
_ICON = {"PASS": "✓", "REJECT": "✗", "QUARANTINE": "⏸"}
_GATE_ORDER = ["RED", "FLOOR", "BROTHERS", "GOD"]


def _load_json(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _format_summary(res: EngineResult, packet_path: Path) -> str:
    icon = _ICON.get(res.overall, "?")
    lines: List[str] = [f"{icon} {res.overall}  ({packet_path})"]

    # Group gate results by gate name; some gates have multiple results (validator + verifier)
    by_gate: Dict[str, List[GateResult]] = {}
    for gr in res.gate_results:
        by_gate.setdefault(gr.gate, []).append(gr)

    for gate in _GATE_ORDER:
        results = by_gate.get(gate, [])
        if not results:
            lines.append(f"    {gate:<9}  (skipped)")
            continue
        # Determine effective status: if any REJECT then REJECT; else if any QUARANTINE then QUARANTINE; else PASS
        has_reject = any(r.status == "REJECT" for r in results)
        has_quarantine = any(r.status == "QUARANTINE" for r in results)
        if has_reject:
            status = "REJECT"
        elif has_quarantine:
            status = "QUARANTINE"
        else:
            status = "PASS"
        gate_icon = _ICON.get(status, "?")
        lines.append(f"    {gate_icon} {gate:<9}  {status}")
        # Add reasons for non-PASS, plus verifier confirmations on PASS
        for r in results:
            if r.status == "REJECT" or r.status == "QUARANTINE":
                for reason in r.reasons:
                    lines.append(f"          • {reason}")
            elif r.status == "PASS" and r.details:
                # Show verifier confirmations
                verified = r.details.get("verified") if isinstance(r.details, dict) else None
                if verified:
                    for v in verified:
                        lines.append(f"          ✓ {v}")
    return "\n".join(lines)


def _format_verbose(res: EngineResult, packet_path: Path) -> str:
    """Verbose format includes all details and metadata."""
    summary = _format_summary(res, packet_path)
    extra: List[str] = ["", "Detail:"]
    for gr in res.gate_results:
        extra.append(f"  [{gr.gate}] status={gr.status}")
        if gr.reasons:
            for reason in gr.reasons:
                extra.append(f"    reason: {reason}")
        if gr.details:
            try:
                rendered = json.dumps(gr.details, indent=2, default=str)
                for line in rendered.splitlines():
                    extra.append(f"    {line}")
            except Exception:
                extra.append(f"    details: {gr.details!r}")
    return summary + "\n" + "\n".join(extra)


def _format_json(res: EngineResult) -> str:
    return json.dumps(
        {
            "overall": res.overall,
            "gate_results": [
                {
                    "gate": gr.gate,
                    "status": gr.status,
                    "reasons": gr.reasons,
                    "details": gr.details,
                }
                for gr in res.gate_results
            ],
        },
        indent=2,
        default=str,
    )


def _ask_load_packet(args: argparse.Namespace) -> Dict[str, Any]:
    """Resolve the input packet for `concordance ask`.

    Either --packet <path> (load JSON) or --text "..." (parse via
    nl_to_packet). Exactly one must be given.
    """
    if args.text and args.packet:
        print("error: pass either --text or a packet path, not both",
              file=sys.stderr)
        sys.exit(4)
    if args.text:
        # Lazy import so the CLI stays light when packets are JSON.
        from .nl_to_packet import parse as nl_parse
        result = nl_parse(args.text)
        if result is None:
            print(
                "error: no template matched the natural-language input.\n"
                "  The deterministic parser handles common claim shapes "
                "(chemistry equations, p-values, dimensional checks, simple\n"
                "  math, big-O complexity). For freeform claims, hand-author\n"
                "  a packet JSON and pass it as a positional argument.",
                file=sys.stderr,
            )
            sys.exit(5)
        if args.verbose:
            print(f"# parsed via template: {result.template} "
                  f"(confidence {result.confidence:.2f})", file=sys.stderr)
        return result.packet
    if not args.packet:
        print("error: provide either a packet path or --text \"...\"",
              file=sys.stderr)
        sys.exit(4)
    packet_path = Path(args.packet)
    try:
        return _load_json(packet_path)
    except FileNotFoundError:
        print(f"error: packet file not found: {packet_path}", file=sys.stderr)
        sys.exit(4)
    except json.JSONDecodeError as e:
        print(f"error: packet is not valid JSON: {e}", file=sys.stderr)
        sys.exit(4)


def _format_record_json(record: WitnessRecord) -> str:
    return json.dumps(record.to_dict(), indent=2, default=str)


def main() -> None:
    # Force UTF-8 on stdout so unicode glyphs in walkthrough/compact
    # renders (and the existing ✓✗⏸ icons in `validate`) don't crash
    # the Windows cp1252 console. Best-effort: skip if stdout doesn't
    # support reconfigure (e.g., in some CI pipes).
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, OSError):
        pass

    p = argparse.ArgumentParser(prog="concordance", description="Concordance Engine CLI")
    sub = p.add_subparsers(dest="cmd", required=True)

    v = sub.add_parser("validate", help="Validate a packet (schema + gates + verifiers)")
    v.add_argument("packet", type=str, help="Path to packet JSON")
    v.add_argument(
        "--schema",
        type=str,
        default=str(Path(__file__).resolve().parents[2] / "schema" / "packet.schema.json"),
    )
    v.add_argument("--now-epoch", type=int, default=None,
                   help="Override 'now' for the GOD gate (Unix epoch seconds). "
                        "Useful for testing without waiting out scope windows.")
    v.add_argument(
        "--format", "-f",
        choices=["summary", "verbose", "json"],
        default="summary",
        help="Output format. summary is human-readable (default); json dumps full result; verbose adds all details.",
    )
    v.add_argument(
        "--no-verifiers",
        action="store_true",
        help="Disable the verifier layer; only run domain attestation validators. Useful for legacy regression.",
    )

    a = sub.add_parser(
        "ask",
        help="Run the engine and produce a sealed WitnessRecord with Socratic walkthrough.",
        description=(
            "Run a packet through the four-gate pipeline and render the "
            "sealed WitnessRecord. Default output is a Socratic markdown "
            "walkthrough designed for human review."
        ),
    )
    a.add_argument(
        "packet",
        type=str,
        nargs="?",
        help="Path to packet JSON (omit when using --text).",
    )
    a.add_argument(
        "--text", "-t",
        type=str,
        default=None,
        help="Natural-language claim. Routed through nl_to_packet's "
             "deterministic templates (chemistry equations, p-values, "
             "dimensional checks, simple math, big-O complexity).",
    )
    a.add_argument("--now-epoch", type=int, default=None)
    a.add_argument(
        "--compact", "-c",
        action="store_true",
        help="One-screen render of the sealed record. Glanceable; trades "
             "the full Socratic walk for a status summary.",
    )
    a.add_argument(
        "--json",
        action="store_true",
        help="Emit the sealed WitnessRecord as JSON. The agent surface; "
             "use this when piping to another tool.",
    )
    a.add_argument(
        "--html",
        action="store_true",
        help="Emit a self-contained HTML document. Same sections as the "
             "markdown walkthrough; embeds CSS so it renders standalone.",
    )
    a.add_argument(
        "--trace",
        action="store_true",
        help="Expand each verifier's data block (formula, rule, claimed "
             "vs actual values) inline. Shows the work behind each gate "
             "verdict.",
    )
    a.add_argument(
        "--auto-precedent",
        action="store_true",
        help="Look up the closest precedent in the Audit Chain and "
             "include it in the sealed record. Honors discovery-not-design: "
             "if no precedent matches, the record explicitly carries "
             "precedent_id=None rather than fabricating one.",
    )
    a.add_argument(
        "--no-verifiers",
        action="store_true",
        help="Disable the verifier layer. Useful for legacy regression.",
    )
    a.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Print template/confidence diagnostic to stderr when --text "
             "is used.",
    )

    # ── ledger subcommand ──────────────────────────────────────────
    led = sub.add_parser(
        "ledger",
        help="Query the Audit Chain of recorded precedents.",
        description=(
            "Read-only access to the ledger of past sealed decisions. "
            "Use `lookup` to find the closest precedent for a packet; "
            "`list` enumerates all known precedents."
        ),
    )
    led_sub = led.add_subparsers(dest="ledger_cmd", required=True)
    led_lookup = led_sub.add_parser(
        "lookup", help="Find the closest precedent for a packet.")
    led_lookup.add_argument("packet", type=str, help="Path to packet JSON")
    led_sub.add_parser("list", help="List all precedents in the ledger.")

    led_seal = led_sub.add_parser(
        "seal",
        help="Append a packet's sealed WitnessRecord to the ledger as "
             "a new precedent.",
        description=(
            "Run a packet through the four gates and, if it passes, "
            "write the resulting record to the Audit Chain as a "
            "new precedent. REJECTED or QUARANTINED packets cannot be "
            "sealed — the ledger is a record of resolved decisions."
        ),
    )
    led_seal.add_argument("packet", type=str, help="Path to packet JSON")
    led_seal.add_argument(
        "--summary", "-s", required=True, type=str,
        help="One-line human description. The ledger's value is the "
             "human framing of what the precedent records — no "
             "auto-generation."
    )
    led_seal.add_argument(
        "--id", dest="precedent_id", type=str, default=None,
        help="Stable precedent_id (URI-style). Auto-generated from axis "
             "and packet_id if omitted."
    )
    led_seal.add_argument(
        "--overwrite", action="store_true",
        help="Allow replacing an existing precedent file. Default is "
             "to refuse."
    )
    led_seal.add_argument("--now-epoch", type=int, default=None)
    led_seal.add_argument("--no-verifiers", action="store_true")

    led_verify = led_sub.add_parser(
        "verify",
        help="Walk the ledger and verify the hash chain is intact.",
        description=(
            "Recompute each precedent's content_hash and confirm the "
            "prev_hash links connect the chain. Tampered files and "
            "broken links are reported. Files written before chain "
            "support was added are reported as 'unsigned'."
        ),
    )

    led_amend = led_sub.add_parser(
        "amend",
        help="Append an amendment to an existing precedent.",
        description=(
            "Amendments are append-only — the prior precedent stays in "
            "the ledger unmodified. The new file carries an `amends` "
            "field linking back to the prior precedent_id, and "
            "`find_closest` automatically prefers the latest version "
            "in an amendment chain. Older versions remain visible to "
            "anyone listing the ledger or auditing how a community "
            "refined its understanding."
        ),
    )
    led_amend.add_argument(
        "prior_id", type=str,
        help="precedent_id of the prior version being refined.",
    )
    led_amend.add_argument(
        "--summary", "-s", required=True, type=str,
        help="One-line description of the new framing.",
    )
    led_amend.add_argument(
        "--id", dest="new_id", type=str, default=None,
        help="Stable precedent_id for the amendment. Auto-generated as "
             "<prior_id>-amended-N if omitted.",
    )

    # ── signing subcommand ─────────────────────────────────────────
    sign = sub.add_parser(
        "sign",
        help="Ed25519 keypair generation, packet signing, signature verification.",
        description=(
            "Cryptographic signing operations per canonical "
            "Investment Packet v1.1 spec. Requires the [signing] "
            "extra: pip install -e \".[signing]\""
        ),
    )
    sign_sub = sign.add_subparsers(dest="sign_cmd", required=True)

    sg_keypair = sign_sub.add_parser(
        "keypair", help="Generate a fresh Ed25519 keypair.",
    )
    sg_keypair.add_argument(
        "--out-private", type=str, default=None,
        help="Write private key b64u to this file (otherwise stdout).",
    )
    sg_keypair.add_argument(
        "--out-public", type=str, default=None,
        help="Write public key b64u to this file (otherwise stdout).",
    )

    sg_sign = sign_sub.add_parser(
        "packet", help="Sign a packet JSON file.",
    )
    sg_sign.add_argument("packet", type=str, help="Path to packet JSON")
    sg_sign.add_argument(
        "--private-key", type=str, required=True,
        help="Path to private key file (b64u-encoded raw 32 bytes)",
    )
    sg_sign.add_argument(
        "--out", type=str, default=None,
        help="Write signed packet to this file (otherwise stdout JSON).",
    )

    sg_verify = sign_sub.add_parser(
        "verify", help="Verify a signed packet's signature.",
    )
    sg_verify.add_argument("packet", type=str, help="Path to signed packet JSON")
    sg_verify.add_argument(
        "--public-key", type=str, default=None,
        help="Path to public key file. If omitted, reads from "
             "packet.issuer_public_key.",
    )

    # ── write subcommand (the calibration tool / coach module) ─────
    wr = sub.add_parser(
        "write",
        help="Capture a stream-of-consciousness journal entry. The engine "
             "categorizes additively without replacing what you wrote.",
        description=(
            "The journal is the calibration surface of the coach module. "
            "Stream of consciousness in; categorization out; nothing replaces "
            "the original text. The engine listens, surfaces what shape it "
            "heard, and shows where this entry sits relative to your recent "
            "writing — drift, recurring anchors, dominant action shapes. "
            "Calibration is descriptive, never prescriptive. The user does "
            "the deciding."
        ),
    )
    wr.add_argument(
        "text", type=str, nargs="?",
        help="The entry text. Omit to read from --from-file or stdin.",
    )
    wr.add_argument(
        "--from-file", "-f", type=str, default=None,
        help="Read entry text from this file.",
    )
    wr.add_argument(
        "--stdin", action="store_true",
        help="Read entry text from stdin (until EOF).",
    )
    wr.add_argument(
        "--tags", type=str, default="",
        help="Comma-separated user tags to attach to the entry.",
    )
    wr.add_argument(
        "--quiet", action="store_true",
        help="Suppress the calibration read-back; just confirm the entry id.",
    )
    wr.add_argument(
        "--no-precedent", action="store_true",
        help="Skip the audit-chain closest-precedent lookup. Faster; useful "
             "when capturing many entries in a row.",
    )

    jr = sub.add_parser(
        "journal",
        help="Read, list, thread, and annotate journal entries.",
        description=(
            "Read-side surface for the journal. The engine has been keeping "
            "your stream-of-consciousness writing alongside its categorizations. "
            "These commands surface what's been kept."
        ),
    )
    jr_sub = jr.add_subparsers(dest="jr_cmd", required=True)

    jr_list = jr_sub.add_parser(
        "list", help="List recent entries (newest first).",
    )
    jr_list.add_argument(
        "--since", type=float, default=None,
        help="Unix epoch seconds; only entries written after this time.",
    )
    jr_list.add_argument(
        "--tag", type=str, default=None,
        help="Filter to a specific user tag.",
    )

    jr_show = jr_sub.add_parser(
        "show", help="Show a single entry by id.",
    )
    jr_show.add_argument("entry_id", type=str)

    jr_thread = jr_sub.add_parser(
        "thread",
        help="Find entries that share categorizations with the given one "
             "(thread of return).",
    )
    jr_thread.add_argument("entry_id", type=str)

    jr_annotate = jr_sub.add_parser(
        "annotate",
        help="Add a later annotation to an entry. Original text is preserved.",
    )
    jr_annotate.add_argument("entry_id", type=str)
    jr_annotate.add_argument("--note", required=True, type=str)
    jr_annotate.add_argument("--author", type=str, default="")

    # ── keep subcommand (the liturgical layer) ─────────────────────
    kp = sub.add_parser(
        "keep",
        help="Keeping — the liturgical layer. Continuous body-practice that "
             "runs whether or not packets are submitted.",
        description=(
            "Per KoA Trilogy (The Keeping, Book Three): the engine's "
            "validation is liturgical, not climactic. Four canonical "
            "practices keep the four gates alive between firings: "
            "SignalHum (GOD/heartbeat), PerimeterWalk (FLOOR/audit chain "
            "boundary), ForgeLighting (RED/verifier readiness), "
            "RollKeeping (BROTHERS/precedent index). Each practice keeps "
            "something; none returns a decision."
        ),
    )
    kp_sub = kp.add_subparsers(dest="kp_cmd", required=True)

    kp_walk = kp_sub.add_parser(
        "walk",
        help="Run one tick of the keeping. Each due practice fires; the log "
             "is appended; observations print to stdout.",
    )
    kp_walk.add_argument(
        "--practice", "-p", type=str, default=None,
        choices=["signal_hum", "perimeter_walk", "forge_lighting", "roll_keeping"],
        help="Run only this practice. Default: run any practice whose "
             "cadence has elapsed.",
    )
    kp_walk.add_argument(
        "--force", action="store_true",
        help="Force-run the practice(s) regardless of cadence. Useful for "
             "scripted invocations.",
    )

    kp_status = kp_sub.add_parser(
        "status",
        help="Show what's been kept while you were away. Reads the keeping "
             "log; surfaces per-practice run-count + latest observation.",
    )
    kp_status.add_argument(
        "--since", type=float, default=None,
        help="Unix epoch seconds; only show observations after this time. "
             "Default: last 24 hours.",
    )
    kp_status.add_argument(
        "--practice", "-p", type=str, default=None,
        help="Filter to a single practice.",
    )

    kp_run = kp_sub.add_parser(
        "run",
        help="Run the keeper as a daemon. Ticks at the configured interval "
             "until interrupted (Ctrl-C).",
    )
    kp_run.add_argument(
        "--tick-interval", type=float, default=30.0,
        help="Seconds between tick checks (default: 30).",
    )
    kp_run.add_argument(
        "--quiet", action="store_true",
        help="Don't print observations as they fire. Log still fills.",
    )

    # ── lsp subcommand ─────────────────────────────────────────────
    lsp_p = sub.add_parser(
        "lsp",
        help="Lighthouse Standard Pages — deterministic chunking + hashing.",
        description=(
            "Build / verify LSP records per canonical 02_SPECS/LSP_SPEC.md. "
            "NFKC normalize, 200-word chunks (default), SHA-256 per chunk. "
            "Caller provides text; no LXX/MorphGNT corpus is bundled in "
            "MVP."
        ),
    )
    lsp_sub = lsp_p.add_subparsers(dest="lsp_cmd", required=True)

    lsp_build = lsp_sub.add_parser(
        "build", help="Build an LSP record from a text file.")
    lsp_build.add_argument("input", type=str, help="Path to input text file")
    lsp_build.add_argument(
        "--out", type=str, default=None,
        help="Write LSP JSON to this file (otherwise stdout).",
    )
    lsp_build.add_argument(
        "--words-per-page", type=int, default=200,
        help="Chunk size in words (default: 200, per LSP_SPEC v0).",
    )
    lsp_build.add_argument(
        "--source-id", type=str, default="",
        help="Opaque identifier for the source text (e.g. 'LXX-Mt').",
    )
    lsp_build.add_argument(
        "--no-nfkc", action="store_true",
        help="Skip Unicode NFKC normalization. Default is to apply.",
    )

    lsp_verify_cmd = lsp_sub.add_parser(
        "verify", help="Recompute and verify chunk hashes in an LSP file.")
    lsp_verify_cmd.add_argument("lsp", type=str, help="Path to LSP JSON")

    lsp_ingest = lsp_sub.add_parser(
        "ingest",
        help="Ingest a JSONL corpus of {ref, text} into an LSPCorpus.",
        description=(
            "Build an LSPCorpus from a JSONL file. Each line must be a "
            "JSON object with `ref` and `text` keys. The corpus carries "
            "the LSP record + a ref→word-range index so anchors like "
            "'Mt 5:37' resolve to the chunk(s) covering them. The result "
            "is what makes a ref-shaped anchor verifiable end-to-end."
        ),
    )
    lsp_ingest.add_argument("input", type=str, help="Path to JSONL input")
    lsp_ingest.add_argument(
        "--out", type=str, required=True,
        help="Write LSPCorpus JSON to this file.",
    )
    lsp_ingest.add_argument(
        "--source-id", type=str, default="",
        help="Opaque identifier for the source corpus (e.g. 'WEB-66').",
    )
    lsp_ingest.add_argument(
        "--words-per-page", type=int, default=200,
        help="Chunk size in words (default: 200, per LSP_SPEC v0).",
    )

    lsp_lookup = lsp_sub.add_parser(
        "lookup",
        help="Look up a reference in an LSPCorpus and verify chunk integrity.",
    )
    lsp_lookup.add_argument("corpus", type=str, help="Path to LSPCorpus JSON")
    lsp_lookup.add_argument("ref", type=str, help="Reference to look up (e.g. 'Mt 5:37')")

    # ── quarantine subcommand ──────────────────────────────────────
    qn = sub.add_parser(
        "quarantine",
        help="Quarantine Airlock — capture, decontaminate, admit ideas.",
        description=(
            "Per canonical 03_ARCH/QUARANTINE_AIRLOCK.md: ideas are "
            "quarantined by default. Three zones (Holding / "
            "Decontamination / Core), three roles (Q / Scribe / Guide), "
            "structured admission format (hypothesis / backlog / "
            "decision). File-backed under lw/quarantine/ parallel to the "
            "Audit Chain."
        ),
    )
    qn_sub = qn.add_subparsers(dest="qn_cmd", required=True)

    qn_capture = qn_sub.add_parser(
        "capture",
        help="Scribe captures a raw input. Lands in HOLDING.",
    )
    qn_capture.add_argument(
        "text", type=str, nargs="?",
        help="Raw text of the captured idea. Omit to read from --from-file.",
    )
    qn_capture.add_argument(
        "--from-file", type=str, default=None,
        help="Read raw text from this file instead of the text argument.",
    )
    qn_capture.add_argument(
        "--tags", type=str, default="",
        help="Comma-separated tags to attach to the packet.",
    )
    qn_capture.add_argument(
        "--note", type=str, default="",
        help="Optional human-readable note for the capture history entry.",
    )

    qn_list = qn_sub.add_parser(
        "list",
        help="List quarantine packets, optionally filtered by zone.",
    )
    qn_list.add_argument(
        "--zone", type=str, default=None,
        choices=["holding", "decontamination", "core"],
        help="Filter to one zone. Default lists all zones.",
    )

    qn_show = qn_sub.add_parser(
        "show",
        help="Print the full JSON of one quarantine packet.",
    )
    qn_show.add_argument("packet_id", type=str, help="Quarantine packet id (q-…)")

    qn_decon = qn_sub.add_parser(
        "decontaminate",
        help="Q moves a packet HOLDING → DECONTAMINATION with a hypothesis.",
    )
    qn_decon.add_argument("packet_id", type=str, help="Quarantine packet id")
    qn_decon.add_argument(
        "--hypothesis", "-H", type=str, required=True,
        help="The structured hypothesis the captured idea is being tested as.",
    )
    qn_decon.add_argument(
        "--backlog", type=str, default="",
        help="Pipe-separated backlog items: 'check ref|compare to canon'.",
    )
    qn_decon.add_argument("--note", type=str, default="")

    qn_admit = qn_sub.add_parser(
        "admit",
        help="Guide issues a decision: accept / reject / defer.",
    )
    qn_admit.add_argument("packet_id", type=str, help="Quarantine packet id")
    qn_admit.add_argument(
        "--decision", "-d", type=str, required=True,
        choices=["accept", "reject", "defer"],
        help="The Guide's decision. ACCEPT → CORE; REJECT → HOLDING with "
             "rejection reason; DEFER → stays in DECONTAMINATION.",
    )
    qn_admit.add_argument(
        "--rationale", "-r", type=str, default="",
        help="Why the Guide chose this decision. Required for REJECT — "
             "the rejection record's value is the captured 'why'.",
    )
    qn_admit.add_argument("--note", type=str, default="")

    qn_delete = qn_sub.add_parser(
        "delete",
        help="Delete a quarantine packet from the store. Use with care.",
    )
    qn_delete.add_argument("packet_id", type=str, help="Quarantine packet id")

    # ── investment-packet subcommand ───────────────────────────────
    inv = sub.add_parser(
        "investment-packet",
        help="Build / verify Investment Packet v1.1 credentials.",
        description=(
            "Per canonical 02_SPECS/INVESTMENT_PACKET_SPEC_v1_1.md: "
            "signed, time-bound, revocable, privacy-preserving "
            "eligibility credential. Raw financial data stays local; "
            "only derived bands + proof hashes leave Node."
        ),
    )
    inv_sub = inv.add_subparsers(dest="inv_cmd", required=True)
    inv_verify = inv_sub.add_parser(
        "verify",
        help="Verify an Investment Packet (signature, expiry, revocation).",
    )
    inv_verify.add_argument("packet", type=str, help="Path to signed Investment Packet JSON")
    inv_verify.add_argument(
        "--revoked", type=str, default=None,
        help="Path to a JSON file with a list of revoked revocation_key_id values.",
    )

    args = p.parse_args()

    if args.cmd == "validate":
        packet_path = Path(args.packet)
        schema_path = Path(args.schema)
        try:
            packet = _load_json(packet_path)
        except FileNotFoundError:
            print(f"error: packet file not found: {packet_path}", file=sys.stderr)
            sys.exit(4)
        except json.JSONDecodeError as e:
            print(f"error: packet is not valid JSON: {e}", file=sys.stderr)
            sys.exit(4)

        try:
            schema = load_schema(schema_path)
            validate_against_schema(packet, schema)
        except Exception as e:
            print(f"✗ SCHEMA INVALID  ({packet_path})", file=sys.stderr)
            print(f"    {e}", file=sys.stderr)
            sys.exit(3)

        cfg = EngineConfig(
            schema_path=str(schema_path),
            run_verifiers=not args.no_verifiers,
        )
        res = validate_packet(packet, now_epoch=args.now_epoch, config=cfg)

        if args.format == "json":
            print(_format_json(res))
        elif args.format == "verbose":
            print(_format_verbose(res, packet_path))
        else:
            print(_format_summary(res, packet_path))

        sys.exit(_EXIT.get(res.overall, 1))

    if args.cmd == "ask":
        # Output formats are mutually exclusive: at most one of
        # --compact / --json / --html.
        chosen_formats = sum(bool(x) for x in (args.compact, args.json, args.html))
        if chosen_formats > 1:
            print("error: --compact, --json, and --html are mutually exclusive",
                  file=sys.stderr)
            sys.exit(4)
        packet = _ask_load_packet(args)
        cfg = EngineConfig(
            schema_path="",
            run_verifiers=not args.no_verifiers,
        )

        # Optional ledger lookup before sealing.
        closest_case = None
        if args.auto_precedent:
            from .ledger import find_closest
            closest_case = find_closest(packet)

        record = validate_and_seal(
            packet,
            now_epoch=args.now_epoch,
            config=cfg,
            packet_id=packet.get("id"),
            closest_case=closest_case,
        )
        if args.json:
            print(_format_record_json(record))
        elif args.compact:
            print(render_walkthrough_compact(record))
        elif args.html:
            print(render_walkthrough_html(record, expand_traces=args.trace))
        else:
            print(render_walkthrough(record, expand_traces=args.trace))
        sys.exit(_EXIT.get(record.overall, 1))

    if args.cmd == "ledger":
        from .ledger import (
            find_closest, list_precedents, seal_to_ledger, verify_chain,
            amend_precedent,
        )
        if args.ledger_cmd == "verify":
            report = verify_chain()
            print(f"ledger: {report['total']} precedents")
            print(f"  verified: {report['verified']}")
            if report["unsigned"]:
                print(f"  unsigned (no content_hash): {len(report['unsigned'])}")
                for name in report["unsigned"]:
                    print(f"    {name}")
            if report["tampered"]:
                print(f"  TAMPERED: {len(report['tampered'])}")
                for entry in report["tampered"]:
                    print(f"    {entry['file']}: {entry['error']}")
            if report["broken_links"]:
                print(f"  BROKEN LINKS: {len(report['broken_links'])}")
                for entry in report["broken_links"]:
                    print(
                        f"    {entry['file']}: expected prev "
                        f"{entry['expected_prev']}, got {entry['got_prev']}"
                    )
            if report["ok"]:
                print("chain ok")
                sys.exit(0)
            print("chain INVALID — see report above", file=sys.stderr)
            sys.exit(1)
        if args.ledger_cmd == "list":
            precedents = list_precedents()
            if not precedents:
                print("(no precedents in ledger)")
            else:
                for p in precedents:
                    axis = p.get("axis", "?")
                    pid = p.get("precedent_id", "?")
                    summary = p.get("summary", "")
                    print(f"  {axis:<20}  {pid}")
                    if summary:
                        print(f"    {summary}")
            sys.exit(0)
        if args.ledger_cmd == "lookup":
            packet_path = Path(args.packet)
            try:
                packet = _load_json(packet_path)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"error: could not read packet: {e}", file=sys.stderr)
                sys.exit(4)
            cc = find_closest(packet)
            if cc is None or cc.precedent_id is None:
                print("(no comparable precedent in the ledger — claim is novel)")
                sys.exit(0)
            print(f"precedent: {cc.precedent_id}")
            print(f"  shared dimensions: {sorted(cc.shared_dimensions)}")
            if cc.shared_anchors:
                print(f"  shared anchors: {list(cc.shared_anchors)}")
            if cc.distance is not None:
                print(f"  distance: {cc.distance}")
            if cc.reasoning_overlay:
                print("  reasoning overlay:")
                for k, v in (cc.reasoning_overlay or {}).items():
                    print(f"    {k}: {v}")
            sys.exit(0)
        if args.ledger_cmd == "amend":
            try:
                target = amend_precedent(
                    args.prior_id,
                    summary=args.summary,
                    new_precedent_id=args.new_id,
                )
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                sys.exit(4)
            except FileExistsError as e:
                print(f"error: {e}", file=sys.stderr)
                sys.exit(4)
            print(f"amended precedent → {target}")
            sys.exit(0)
        if args.ledger_cmd == "seal":
            packet_path = Path(args.packet)
            try:
                packet = _load_json(packet_path)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"error: could not read packet: {e}", file=sys.stderr)
                sys.exit(4)
            cfg = EngineConfig(
                schema_path="",
                run_verifiers=not args.no_verifiers,
            )
            record = validate_and_seal(
                packet,
                now_epoch=args.now_epoch,
                config=cfg,
                packet_id=packet.get("id"),
            )
            if record.overall != "PASS":
                print(
                    f"error: packet did not PASS (overall={record.overall}). "
                    "Only PASS records can be sealed to the ledger.",
                    file=sys.stderr,
                )
                sys.exit(_EXIT.get(record.overall, 1))
            try:
                target = seal_to_ledger(
                    record,
                    summary=args.summary,
                    precedent_id=args.precedent_id,
                    overwrite=args.overwrite,
                )
            except FileExistsError as e:
                print(f"error: {e}", file=sys.stderr)
                sys.exit(4)
            except ValueError as e:
                print(f"error: {e}", file=sys.stderr)
                sys.exit(4)
            print(f"sealed precedent → {target}")
            sys.exit(0)
        print("error: unknown ledger subcommand", file=sys.stderr)
        sys.exit(4)

    if args.cmd == "sign":
        from . import signing
        if args.sign_cmd == "keypair":
            try:
                priv, pub = signing.generate_keypair()
            except ImportError as e:
                print(f"error: {e}", file=sys.stderr)
                sys.exit(4)
            if args.out_private:
                Path(args.out_private).write_text(priv, encoding="utf-8")
                print(f"private key → {args.out_private}", file=sys.stderr)
            else:
                print(f"private: {priv}")
            if args.out_public:
                Path(args.out_public).write_text(pub, encoding="utf-8")
                print(f"public key → {args.out_public}", file=sys.stderr)
            else:
                print(f"public:  {pub}")
            sys.exit(0)
        if args.sign_cmd == "packet":
            try:
                packet = _load_json(Path(args.packet))
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"error: could not read packet: {e}", file=sys.stderr)
                sys.exit(4)
            try:
                priv = Path(args.private_key).read_text(encoding="utf-8").strip()
            except OSError as e:
                print(f"error: could not read private key: {e}", file=sys.stderr)
                sys.exit(4)
            try:
                signed = signing.sign_packet(packet, priv)
            except ImportError as e:
                print(f"error: {e}", file=sys.stderr)
                sys.exit(4)
            out = json.dumps(signed, indent=2, default=str)
            if args.out:
                Path(args.out).write_text(out, encoding="utf-8")
                print(f"signed packet → {args.out}", file=sys.stderr)
            else:
                print(out)
            sys.exit(0)
        if args.sign_cmd == "verify":
            try:
                packet = _load_json(Path(args.packet))
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"error: could not read packet: {e}", file=sys.stderr)
                sys.exit(4)
            pub = None
            if args.public_key:
                try:
                    pub = Path(args.public_key).read_text(encoding="utf-8").strip()
                except OSError as e:
                    print(f"error: could not read public key: {e}", file=sys.stderr)
                    sys.exit(4)
            try:
                ok, detail = signing.verify_packet(packet, pub)
            except ImportError as e:
                print(f"error: {e}", file=sys.stderr)
                sys.exit(4)
            if ok:
                print(f"signature ok ({detail})")
                sys.exit(0)
            print(f"signature INVALID: {detail}", file=sys.stderr)
            sys.exit(1)

    if args.cmd == "write":
        from . import journal as jr_mod

        # Resolve entry text from positional / --from-file / --stdin.
        text = args.text
        sources_chosen = sum(bool(s) for s in (text, args.from_file, args.stdin))
        if sources_chosen > 1:
            print("error: pass at most one of: positional text, --from-file, --stdin",
                  file=sys.stderr)
            sys.exit(4)
        if args.from_file:
            try:
                text = Path(args.from_file).read_text(encoding="utf-8")
            except OSError as e:
                print(f"error: could not read input: {e}", file=sys.stderr)
                sys.exit(4)
        if args.stdin:
            text = sys.stdin.read()
        if not text or not text.strip():
            print(
                "error: provide entry text (positional, --from-file, or --stdin)",
                file=sys.stderr,
            )
            sys.exit(4)

        tag_list = [t.strip() for t in args.tags.split(",") if t.strip()]
        try:
            entry = jr_mod.capture(
                text,
                tags=tag_list,
                look_up_precedent=not args.no_precedent,
            )
        except ValueError as e:
            print(f"error: {e}", file=sys.stderr)
            sys.exit(4)

        if args.quiet:
            print(entry.id)
            sys.exit(0)

        # Default: print id + calibration read-back.
        print(f"# Captured `{entry.id}`")
        print()
        cal = jr_mod.calibrate(entry)
        print(jr_mod.render_calibration(entry, cal))
        sys.exit(0)

    if args.cmd == "journal":
        from . import journal as jr_mod
        store = jr_mod.JournalStore()

        if args.jr_cmd == "list":
            entries = store.list_all(since=args.since, tag=args.tag)
            if not entries:
                print("(no entries match)")
                sys.exit(0)
            for e in entries:
                ts = time.strftime(
                    "%Y-%m-%d %H:%M:%S",
                    time.gmtime(e.written_at),
                ) if e.written_at else "(no timestamp)"
                preview = e.text.replace("\n", " ")[:80]
                tags = (
                    "  [" + ", ".join(e.user_tags) + "]"
                    if e.user_tags else ""
                )
                print(f"{e.id}  {ts}  {preview}{tags}")
            sys.exit(0)

        if args.jr_cmd == "show":
            e = store.load(args.entry_id)
            if e is None:
                print(f"error: no entry found with id {args.entry_id}",
                      file=sys.stderr)
                sys.exit(4)
            print(json.dumps(e.to_dict(), indent=2, ensure_ascii=False))
            sys.exit(0)

        if args.jr_cmd == "thread":
            entries = jr_mod.thread(args.entry_id)
            source = store.load(args.entry_id)
            if source is None:
                print(f"error: no entry found with id {args.entry_id}",
                      file=sys.stderr)
                sys.exit(4)
            if not entries:
                print(f"(no entries thread with {args.entry_id})")
                sys.exit(0)
            print(f"# Entries threading with `{args.entry_id}`:")
            for e in entries:
                preview = e.text.replace("\n", " ")[:80]
                shared: List[str] = []
                src_anchors = set(source.categorization.detected_anchors)
                cand_anchors = set(e.categorization.detected_anchors)
                if src_anchors & cand_anchors:
                    shared.append(
                        "anchors: " + ", ".join(src_anchors & cand_anchors)
                    )
                src_actions = set(source.categorization.detected_action_shapes)
                cand_actions = set(e.categorization.detected_action_shapes)
                if src_actions & cand_actions:
                    shared.append(
                        "actions: " + ", ".join(src_actions & cand_actions)
                    )
                if (e.categorization.detected_scope
                        and e.categorization.detected_scope
                            == source.categorization.detected_scope):
                    shared.append(f"scope: {e.categorization.detected_scope}")
                shared_str = " | ".join(shared) if shared else "(via persistence)"
                print(f"  {e.id}  {preview}")
                print(f"      shared → {shared_str}")
            sys.exit(0)

        if args.jr_cmd == "annotate":
            updated = jr_mod.annotate(
                args.entry_id, args.note, author=args.author,
            )
            if updated is None:
                print(f"error: no entry found with id {args.entry_id}",
                      file=sys.stderr)
                sys.exit(4)
            print(f"annotated {updated.id}; "
                  f"{len(updated.annotations)} annotation(s) total")
            sys.exit(0)

    if args.cmd == "keep":
        from . import keeping as kp_mod
        import time as _time

        if args.kp_cmd == "walk":
            keeper = kp_mod.default_keeper()
            if args.practice:
                # Run a single practice (force or due-only).
                target = next(
                    (p for p in keeper.practices if p.name == args.practice),
                    None,
                )
                if target is None:
                    print(f"error: unknown practice {args.practice!r}",
                          file=sys.stderr)
                    sys.exit(4)
                if not args.force and not target.due():
                    print(f"{target.name} not due yet (cadence "
                          f"{target.cadence_seconds:.0f}s); use --force to override")
                    sys.exit(0)
                obs = target.run()
                keeper.log.append(obs)
                print(json.dumps(obs.to_dict(), indent=2, default=str))
                sys.exit(0)
            # Default: tick the keeper, print whatever fired.
            observations = keeper.tick()
            if not observations:
                print("(nothing due this tick)")
                sys.exit(0)
            for obs in observations:
                print(json.dumps(obs.to_dict(), indent=2, default=str))
            sys.exit(0)

        if args.kp_cmd == "status":
            since = args.since if args.since is not None else (_time.time() - 86400)
            log = kp_mod.KeepingLog()
            if args.practice:
                obs_list = log.read(since=since, practice=args.practice)
                summary = {
                    "since": since,
                    "practice": args.practice,
                    "runs": len(obs_list),
                    "latest_kept": obs_list[-1].kept if obs_list else None,
                    "latest_at": obs_list[-1].started_at if obs_list else None,
                }
            else:
                summary = kp_mod.while_you_were_away(since=since)
            print(json.dumps(summary, indent=2, default=str))
            sys.exit(0)

        if args.kp_cmd == "run":
            import threading as _threading
            keeper = kp_mod.default_keeper(
                tick_interval_seconds=args.tick_interval,
            )
            stop = _threading.Event()
            print(f"keeper running (tick interval {args.tick_interval:.0f}s); "
                  f"Ctrl-C to stop", file=sys.stderr)

            def _on_tick(observations):
                if args.quiet:
                    return
                for obs in observations:
                    print(f"[{obs.practice}] {obs.kept}")

            try:
                keeper.run_forever(stop_event=stop, on_tick=_on_tick)
            except KeyboardInterrupt:
                stop.set()
                print("keeper stopped", file=sys.stderr)
            sys.exit(0)

    if args.cmd == "lsp":
        from . import lsp as lsp_mod
        if args.lsp_cmd == "build":
            try:
                text = Path(args.input).read_text(encoding="utf-8")
            except OSError as e:
                print(f"error: could not read input: {e}", file=sys.stderr)
                sys.exit(4)
            cfg = lsp_mod.LSPConfig(
                words_per_page=args.words_per_page,
                nfkc=not args.no_nfkc,
            )
            record = lsp_mod.build_lsp(
                text, source_id=args.source_id, cfg=cfg,
            )
            out_json = json.dumps(record, indent=2, ensure_ascii=False)
            if args.out:
                Path(args.out).write_text(out_json, encoding="utf-8")
                print(
                    f"LSP built → {args.out} "
                    f"({record['chunk_count']} chunks, "
                    f"{record['total_words']} words)",
                    file=sys.stderr,
                )
            else:
                print(out_json)
            sys.exit(0)
        if args.lsp_cmd == "verify":
            try:
                lsp_record = _load_json(Path(args.lsp))
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"error: could not read LSP: {e}", file=sys.stderr)
                sys.exit(4)
            report = lsp_mod.verify_lsp(lsp_record)
            print(f"LSP: {report['total']} chunks, "
                  f"{report['verified']} verified")
            if report["tampered"]:
                print(f"  TAMPERED: {len(report['tampered'])}")
                for entry in report["tampered"]:
                    print(
                        f"    chunk {entry['index']}: "
                        f"expected {entry['expected']} got {entry['recomputed']}"
                    )
                sys.exit(1)
            print("ok")
            sys.exit(0)
        if args.lsp_cmd == "ingest":
            cfg = lsp_mod.LSPConfig(words_per_page=args.words_per_page)
            try:
                corpus = lsp_mod.load_corpus_from_jsonl(
                    Path(args.input), source_id=args.source_id, cfg=cfg,
                )
            except OSError as e:
                print(f"error: could not read input: {e}", file=sys.stderr)
                sys.exit(4)
            target = corpus.save(Path(args.out))
            print(
                f"LSPCorpus → {target}  "
                f"({len(corpus.ref_index)} refs, "
                f"{corpus.lsp.get('chunk_count', 0)} chunks, "
                f"{corpus.lsp.get('total_words', 0)} words)",
                file=sys.stderr,
            )
            sys.exit(0)
        if args.lsp_cmd == "lookup":
            try:
                corpus = lsp_mod.LSPCorpus.load(Path(args.corpus))
            except (FileNotFoundError, json.JSONDecodeError, KeyError) as e:
                print(f"error: could not read corpus: {e}", file=sys.stderr)
                sys.exit(4)
            result = corpus.verify_anchor(args.ref)
            print(json.dumps(result, indent=2, ensure_ascii=False))
            if result["status"] == "ok":
                sys.exit(0)
            if result["status"] == "not_indexed":
                sys.exit(2)
            sys.exit(1)  # tampered

    if args.cmd == "quarantine":
        from . import quarantine as qn_mod
        store = qn_mod.QuarantineStore()

        if args.qn_cmd == "capture":
            text = args.text
            if args.from_file:
                if text:
                    print(
                        "error: pass either text or --from-file, not both",
                        file=sys.stderr,
                    )
                    sys.exit(4)
                try:
                    text = Path(args.from_file).read_text(encoding="utf-8")
                except OSError as e:
                    print(f"error: could not read input: {e}", file=sys.stderr)
                    sys.exit(4)
            if not text:
                print(
                    "error: provide raw text as a positional arg or --from-file",
                    file=sys.stderr,
                )
                sys.exit(4)
            tag_list = [t.strip() for t in args.tags.split(",") if t.strip()]
            try:
                pkt = qn_mod.capture(text, tags=tag_list, note=args.note)
            except qn_mod.QuarantineError as e:
                print(f"error: {e}", file=sys.stderr)
                sys.exit(4)
            store.save(pkt)
            print(f"captured {pkt.id} → HOLDING ({len(pkt.raw)} chars)")
            sys.exit(0)

        if args.qn_cmd == "list":
            zone = qn_mod.Zone(args.zone) if args.zone else None
            pkts = store.list_all(zone=zone)
            if not pkts:
                label = f"zone={args.zone}" if args.zone else "all zones"
                print(f"(no quarantine packets in {label})")
                sys.exit(0)
            for pkt in pkts:
                summary = pkt.hypothesis or pkt.normalized[:60]
                print(f"  {pkt.zone:<16} {pkt.id}  {summary}")
                if pkt.decision:
                    print(f"    decision: {pkt.decision}")
                if pkt.rejection_reason:
                    print(f"    rejected: {pkt.rejection_reason}")
            sys.exit(0)

        if args.qn_cmd == "show":
            pkt = store.load(args.packet_id)
            if pkt is None:
                print(f"error: no packet found with id {args.packet_id}",
                      file=sys.stderr)
                sys.exit(4)
            print(json.dumps(pkt.to_dict(), indent=2, ensure_ascii=False))
            sys.exit(0)

        if args.qn_cmd == "decontaminate":
            pkt = store.load(args.packet_id)
            if pkt is None:
                print(f"error: no packet found with id {args.packet_id}",
                      file=sys.stderr)
                sys.exit(4)
            backlog = [b.strip() for b in args.backlog.split("|") if b.strip()] \
                if args.backlog else None
            try:
                qn_mod.decontaminate(
                    pkt,
                    hypothesis=args.hypothesis,
                    backlog_items=backlog,
                    note=args.note,
                )
            except qn_mod.QuarantineError as e:
                print(f"error: {e}", file=sys.stderr)
                sys.exit(4)
            store.save(pkt)
            print(f"decontaminated {pkt.id} → DECONTAMINATION")
            sys.exit(0)

        if args.qn_cmd == "admit":
            pkt = store.load(args.packet_id)
            if pkt is None:
                print(f"error: no packet found with id {args.packet_id}",
                      file=sys.stderr)
                sys.exit(4)
            try:
                decision = qn_mod.Decision(args.decision)
            except ValueError:
                print(f"error: invalid decision {args.decision!r}",
                      file=sys.stderr)
                sys.exit(4)
            try:
                qn_mod.admit(
                    pkt,
                    decision=decision,
                    rationale=args.rationale,
                    note=args.note,
                )
            except qn_mod.QuarantineError as e:
                print(f"error: {e}", file=sys.stderr)
                sys.exit(4)
            store.save(pkt)
            print(f"admitted {pkt.id} → {pkt.zone.upper()} "
                  f"(decision={pkt.decision})")
            sys.exit(0)

        if args.qn_cmd == "delete":
            ok = store.delete(args.packet_id)
            if not ok:
                print(f"error: no packet found with id {args.packet_id}",
                      file=sys.stderr)
                sys.exit(4)
            print(f"deleted {args.packet_id}")
            sys.exit(0)

    if args.cmd == "investment-packet":
        from . import investment_packet as ip
        if args.inv_cmd == "verify":
            try:
                packet = _load_json(Path(args.packet))
            except (FileNotFoundError, json.JSONDecodeError) as e:
                print(f"error: could not read packet: {e}", file=sys.stderr)
                sys.exit(4)
            revoked = None
            if args.revoked:
                try:
                    revoked = json.loads(
                        Path(args.revoked).read_text(encoding="utf-8")
                    )
                except (OSError, json.JSONDecodeError) as e:
                    print(f"error: could not read revoked list: {e}", file=sys.stderr)
                    sys.exit(4)
            try:
                ok, detail, report = ip.verify_investment_packet(
                    packet, revoked_keys=revoked,
                )
            except ImportError as e:
                print(f"error: {e}", file=sys.stderr)
                sys.exit(4)
            print(f"{'OK' if ok else 'INVALID'}: {detail}")
            for check, result in report.get("checks", {}).items():
                print(f"  {check}: {result}")
            sys.exit(0 if ok else 1)


if __name__ == "__main__":
    main()
