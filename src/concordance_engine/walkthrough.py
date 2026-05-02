"""Human-surface renderer for WitnessRecord — Socratic markdown.

Agents read `WitnessRecord.to_dict()`. Humans read this. Same object,
two surfaces. The walkthrough refuses to compress: it surfaces every
gate, every verifier, every anchor's source-hierarchy layer, and the
closest precedent (if any) — then ends with a Socratic question rather
than a verdict.

Doctrinal constraints expressed in the renderer:
  * No `final_answer` line — the engine categorizes, it does not answer.
  * Anchors display their `layer` (jesus_words / bible / apostles /
    recognized_elders) so authority weight is visible at the rendering
    boundary, not buried in metadata.
  * Closest-case section is omitted entirely when no precedent exists,
    rather than fabricated. The doctrine "explicit absence, never
    invented" is honored in the rendering.
  * The walkthrough closes with a question, not a conclusion.

Markdown is the V1 surface because it round-trips through any terminal,
Slack, email, or doc system. Future web/TUI renderers consume the same
WitnessRecord; this module is one of many.
"""
from __future__ import annotations

from typing import List

from .witness_record import WitnessRecord
from . import grid


# ── Helpers ────────────────────────────────────────────────────────────

_GATE_LABELS = {
    "RED":       "RED — refuse the false claim",
    "FLOOR":     "FLOOR — affirmation floor",
    "BROTHERS":  "BROTHERS — plural witness",
    "GOD":       "GOD — wait window",
}

_GATE_STATUS_ICONS = {
    "PASS":       "[PASS]",
    "REJECT":     "[REJECT]",
    "QUARANTINE": "[QUARANTINE]",
}

_VERIFIER_STATUS_ICONS = {
    "CONFIRMED":      "[OK]",
    "MISMATCH":       "[MISMATCH]",
    "NOT_APPLICABLE": "[N/A]",
    "ERROR":          "[ERROR]",
}

_LAYER_LABELS = {
    "jesus_words":       "*jesus_words* (primary)",
    "bible":             "*bible* (secondary)",
    "apostles":          "*apostles*",
    "recognized_elders": "*recognized_elders*",
}


def _h(level: int, text: str) -> str:
    return f"{'#' * level} {text}"


def _hr() -> str:
    return "---"


def _join_sections(sections: List[str]) -> str:
    """Join non-empty sections with a horizontal rule and blank lines."""
    return "\n\n".join(s for s in sections if s)


# ── Section renderers ─────────────────────────────────────────────────

def _render_header(record: WitnessRecord) -> str:
    pid = record.packet_id or "(no packet_id)"
    headline = {
        "PASS":       "PASSED through all four gates",
        "REJECT":     "REJECTED",
        "QUARANTINE": "in QUARANTINE pending resolution",
    }.get(record.overall, record.overall)
    return (
        f"{_h(1, 'Witness Record')}\n\n"
        f"**Packet:** `{pid}`  \n"
        f"**Schema:** `{record.schema_version}` · **Result:** {headline}"
    )


def _render_scaffold(record: WitnessRecord) -> str:
    """Where this packet sits on the dimensional scaffold + adjacency."""
    if record.axis_coords is None:
        return ""
    axis = record.axis_coords.axis
    dims = sorted(record.axis_coords.dimensions)
    if not dims:
        return ""
    lines = [_h(2, "Where this sits on the scaffold")]
    if record.axis_coords.umbrella:
        lines.append(
            f"`{axis}` is a subsystem of the **{record.axis_coords.umbrella}** "
            f"umbrella; it lives at the intersection of:"
        )
    else:
        lines.append(f"`{axis}` lives at the intersection of:")
    lines.append("")
    for d in dims:
        lines.append(f"- **{d}**")

    # Adjacency: top 3 axes that share the most dimensions.
    try:
        neighbors = grid.adjacent(axis)[:3]
    except KeyError:
        neighbors = []
    if neighbors:
        lines.append("")
        parts = [
            f"**{name}** (shares {len(shared)})"
            for name, shared in neighbors
        ]
        lines.append("Closest neighbors on the scaffold: " + ", ".join(parts) + ".")
    return "\n".join(lines)


def _render_submission(record: WitnessRecord) -> str:
    """A short 'what you submitted' echo. The record carries axis_coords
    and packet_id but not the original packet body, so this stays
    minimal — humans who need the full submission can look it up by
    packet_id."""
    if record.axis_coords is None:
        return ""
    return (
        f"{_h(2, 'What you submitted')}\n\n"
        f"**Domain:** `{record.axis_coords.axis}`"
    )


_STATUS_PRIORITY = {"PASS": 0, "QUARANTINE": 1, "REJECT": 2}


def _render_gates(record: WitnessRecord) -> str:
    """One H3 section per gate, in firing order.

    The gate runner can append multiple verdicts for the same gate (e.g.
    RED gets one verdict from the domain validator, then a second from
    the verifier-dispatch step). Collapse consecutive same-gate verdicts
    into one section: take the worst status (REJECT > QUARANTINE > PASS)
    as the headline, merge reasons and confirmed-verifier lists across
    all verdicts.
    """
    if not record.gate_results:
        return ""
    # Group adjacent verdicts on the same gate.
    groups: List[List] = []
    for gr in record.gate_results:
        if groups and groups[-1][0].gate == gr.gate:
            groups[-1].append(gr)
        else:
            groups.append([gr])

    lines = [_h(2, "The four gates")]
    for i, group in enumerate(groups, start=1):
        # Worst-status wins for the headline.
        headline_status = max(
            (gr.status for gr in group),
            key=lambda s: _STATUS_PRIORITY.get(s, -1),
        )
        gate = group[0].gate
        gate_title = _GATE_LABELS.get(gate, gate)
        status_icon = _GATE_STATUS_ICONS.get(headline_status, f"[{headline_status}]")
        lines.append("")
        lines.append(_h(3, f"{i}. {gate_title} · {status_icon}"))

        merged_reasons: List[str] = []
        merged_verified: List[str] = []
        merged_notes: List[str] = []
        for gr in group:
            merged_reasons.extend(gr.reasons or [])
            if gr.details and isinstance(gr.details, dict):
                v = gr.details.get("verified")
                if v:
                    merged_verified.extend(v)
                note = gr.details.get("note")
                if note:
                    merged_notes.append(note)

        if merged_reasons:
            lines.append("")
            for r in merged_reasons:
                lines.append(f"- {r}")
        if merged_verified:
            lines.append("")
            lines.append("Verifier checks confirmed:")
            for v in merged_verified:
                lines.append(f"- `{v}`")
        for note in merged_notes:
            lines.append("")
            lines.append(f"_{note}_")
    return "\n".join(lines)


def _render_verifier_table(record: WitnessRecord) -> str:
    """Glanceable per-verifier table. Excluded when no verifiers ran."""
    if not record.verifier_results:
        return ""
    lines = [_h(2, "What the verifiers actually checked"), ""]
    lines.append("| verifier | status | rule |")
    lines.append("|---|---|---|")
    for v in record.verifier_results:
        icon = _VERIFIER_STATUS_ICONS.get(v.status, f"[{v.status}]")
        rule = ""
        if isinstance(v.data, dict):
            rule = v.data.get("rule") or v.data.get("formula") or ""
        # Markdown-table-safe: replace pipes and newlines.
        rule = str(rule).replace("|", "\\|").replace("\n", " ")
        if len(rule) > 80:
            rule = rule[:77] + "..."
        detail = (v.detail or "").replace("|", "\\|").replace("\n", " ")
        if not rule and detail:
            rule = detail[:80]
        lines.append(f"| `{v.name}` | {icon} | {rule} |")
    return "\n".join(lines)


def _render_anchors(record: WitnessRecord) -> str:
    """Citations with their source-hierarchy layer made visible."""
    if not record.anchors:
        return ""
    lines = [_h(2, "Citations and their authority layer"), ""]
    for a in record.anchors:
        layer_label = _LAYER_LABELS.get(a.layer, f"*{a.layer}*")
        line = f"- **{a.ref}** · {layer_label}"
        if a.text:
            line += f"  \n  > \"{a.text}\""
        lines.append(line)

    # Quiet-confidence note: if every anchor is primary-tier, surface that.
    layers_present = {a.layer for a in record.anchors}
    if layers_present == {"jesus_words"}:
        lines.append("")
        lines.append(
            "All citations carry primary-tier authority. No appeal to "
            "apostolic letters or recognized elders was needed."
        )
    return "\n".join(lines)


def _render_closest_case(record: WitnessRecord) -> str:
    """The precedent overlay, or an explicit no-precedent note."""
    cc = record.closest_case
    # Section is omitted entirely when the field is None — no precedent
    # was looked up for this packet. Different from cc.precedent_id is
    # None, which means a lookup *was* done and found nothing.
    if cc is None:
        return ""

    lines = [_h(2, "The closest precedent we found"), ""]
    if cc.precedent_id is None:
        lines.append(
            "_No comparable precedent was found in the ledger. This claim "
            "is novel relative to the recorded record._"
        )
        return "\n".join(lines)

    lines.append(f"**`{cc.precedent_id}`**  ")
    if cc.shared_dimensions:
        dims = ", ".join(f"`{d}`" for d in sorted(cc.shared_dimensions))
        lines.append(f"Shared scaffold dimensions: {dims}.  ")
    if cc.distance is not None:
        lines.append(f"Distance: **{cc.distance}**.")
    if cc.reasoning_overlay:
        lines.append("")
        lines.append("**Reasoning trace from the precedent:**")
        lines.append("")
        if isinstance(cc.reasoning_overlay, dict):
            for k, v in cc.reasoning_overlay.items():
                lines.append(f"- **{k}** — {v}")
        else:
            lines.append(str(cc.reasoning_overlay))
    return "\n".join(lines)


def _render_socratic_close(record: WitnessRecord) -> str:
    """The walkthrough ends on a question, not a conclusion."""
    lines = [_h(2, "The Socratic question"), ""]
    cc = record.closest_case
    if record.overall == "REJECT":
        lines.append(
            "*What was wrong with the claim itself?*"
            "\n\n"
            "The engine refused this packet at one of the hard gates. "
            "The reasons are listed above. The next move belongs to you: "
            "fix the underlying claim and resubmit, or reconsider whether "
            "the claim should be made at all."
        )
    elif record.overall == "QUARANTINE":
        lines.append(
            "*What is still pending?*"
            "\n\n"
            "This isn't a verdict yet. One of the gates has held the "
            "packet — usually a wait window or missing witnesses. The "
            "gate verdict above tells you what's blocking. The packet "
            "will close once the gate's condition is met; the engine "
            "is not the right authority to override it."
        )
    elif cc is not None and cc.precedent_id is not None:
        lines.append(
            "*Is your situation actually like the precedent above?*"
            "\n\n"
            "If yes — the precedent's reasoning trace overlays cleanly, "
            "and the gaps you have to close are the differences listed "
            "above. If no — what's different? Surface the difference and "
            "re-run."
        )
        lines.append("")
        lines.append(
            "The engine has refused to give you a verdict on the question "
            "itself. That's load-bearing: this verdict belongs to the "
            "community of witnesses, not to a machine."
        )
    else:
        lines.append(
            "*What is this situation most like?*"
            "\n\n"
            "All four gates passed and the verifiers confirmed every "
            "claim that was checkable. No comparable precedent was "
            "supplied for overlay; that doesn't make the decision wrong, "
            "only novel. The next move is yours."
        )
    return "\n".join(lines)


# ── Public API ─────────────────────────────────────────────────────────

def render_walkthrough(record: WitnessRecord) -> str:
    """Render a sealed WitnessRecord as a Socratic markdown walkthrough.

    The output is designed to be readable in any terminal, pasted into
    Slack/email/docs, and round-tripped through human review without
    losing structure. It refuses to compress to a verdict; the closing
    section is always a question.
    """
    sections = [
        _render_header(record),
        _render_submission(record),
        _render_scaffold(record),
        _render_gates(record),
        _render_verifier_table(record),
        _render_anchors(record),
        _render_closest_case(record),
        _render_socratic_close(record),
    ]
    body = _join_sections(sections)
    # A blank line + horizontal rule between header and first section
    # would be redundant; rely on _join_sections' double-newlines.
    return body
