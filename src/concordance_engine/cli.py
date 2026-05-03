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
from .walkthrough import render_walkthrough, render_walkthrough_compact
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
        if args.compact and args.json:
            print("error: --compact and --json are mutually exclusive",
                  file=sys.stderr)
            sys.exit(4)
        packet = _ask_load_packet(args)
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
        if args.json:
            print(_format_record_json(record))
        elif args.compact:
            print(render_walkthrough_compact(record))
        else:
            print(render_walkthrough(record))
        sys.exit(_EXIT.get(record.overall, 1))


if __name__ == "__main__":
    main()
