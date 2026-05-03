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
        help="Look up the closest precedent in the Evidence Ledger and "
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
        help="Query the Evidence Ledger of recorded precedents.",
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
            "write the resulting record to the Evidence Ledger as a "
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


if __name__ == "__main__":
    main()
