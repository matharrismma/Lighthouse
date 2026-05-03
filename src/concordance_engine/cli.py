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
