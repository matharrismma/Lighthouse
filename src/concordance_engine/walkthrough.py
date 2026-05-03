"""Human-surface renderer for WitnessRecord — Socratic markdown.

**Canonical naming.** This module IS *Atlas* per canonical naming
(00_CANON, 03_ARCH/NAMING_AND_STRUCTURE.md): Lighthouse is the
project, Concordance is the ingestion engine, Atlas is the output
side. The thin `atlas.py` module re-exports these functions under
the canonical names (`render_atlas` / `render_atlas_compact` /
`render_atlas_html`); both are valid public APIs.

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

from typing import Any, Dict, List, Optional, Tuple

from .witness_record import WitnessRecord
from . import grid


# ── Helpers ────────────────────────────────────────────────────────────

_GATE_LABELS = {
    "RED":       "RED — refuse the false claim (Authority check)",
    "FLOOR":     "FLOOR — affirmation floor (Law check)",
    "WAY":       "WAY — path without coercion (Way check)",
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


# ── Shared data-prep helpers ──────────────────────────────────────────
# Both renderers (markdown and HTML) consume these — the data lookups
# are the part that was duplicated across formats; the per-format
# emission stays separate.

_STATUS_PRIORITY = {"PASS": 0, "QUARANTINE": 1, "REJECT": 2}


def _group_gate_results(record: WitnessRecord) -> List[Dict[str, Any]]:
    """Collapse consecutive same-gate verdicts into one group with
    worst-status-wins for the headline. Each group exposes the gate
    name, headline status, all reasons, all confirmed-verifier strings,
    and any notes."""
    groups: List[List] = []
    for gr in record.gate_results:
        if groups and groups[-1][0].gate == gr.gate:
            groups[-1].append(gr)
        else:
            groups.append([gr])
    out: List[Dict[str, Any]] = []
    for group in groups:
        headline = max(
            (gr.status for gr in group),
            key=lambda s: _STATUS_PRIORITY.get(s, -1),
        )
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
        out.append({
            "gate": group[0].gate,
            "title": _GATE_LABELS.get(group[0].gate, group[0].gate),
            "status": headline,
            "reasons": merged_reasons,
            "verified": merged_verified,
            "notes": merged_notes,
        })
    return out


def _scaffold_neighbors(axis: str, top: int = 3) -> List[Tuple[str, frozenset]]:
    """Top N axes that share the most dimensions with `axis`."""
    try:
        return grid.adjacent(axis)[:top]
    except KeyError:
        return []


def _anchor_tier_summary(record: WitnessRecord) -> Optional[str]:
    """Return a one-line summary of the anchor-tier composition, or
    None if there's nothing to highlight (mixed tier or no anchors)."""
    if not record.anchors:
        return None
    layers = {a.layer for a in record.anchors}
    if layers == {"jesus_words"}:
        return ("All citations carry primary-tier authority. No appeal "
                "to apostolic letters or recognized elders was needed.")
    return None


def _split_verifier_data(data: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Split a verifier's `data` payload into the parts the renderer
    surfaces prominently (formula, rule, anchor) and the leftover
    trace fields. Both renderers want this exact split."""
    if not isinstance(data, dict):
        return {"formula": None, "rule": None, "anchor": None, "rest": {}}
    rest = dict(data)
    formula = rest.pop("formula", None)
    rule = rest.pop("rule", None)
    anchor = rest.pop("anchor", None)
    return {"formula": formula, "rule": rule, "anchor": anchor, "rest": rest}


def _expandable_verifier_results(record: WitnessRecord):
    """The subset of verifier_results worth rendering in a trace
    expansion: not NA, has data."""
    return [
        v for v in record.verifier_results
        if v.status != "NOT_APPLICABLE" and v.data
    ]


def _has_fabricated_answer(packet_dict: Dict[str, Any]) -> List[str]:
    """For witness-style introspection — list any forbidden answer
    fields present. Currently unused by the renderer but kept here so
    the doctrinal commitment lives in one shared place."""
    forbidden = ("final_answer", "answer", "engine_answer", "verdict_answer")
    return [f for f in forbidden if packet_dict.get(f) not in (None, "", [], {})]


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
    neighbors = _scaffold_neighbors(axis)
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


def _render_gates(record: WitnessRecord) -> str:
    """One H3 section per gate, in firing order. Consecutive same-gate
    verdicts collapse via shared `_group_gate_results` helper."""
    if not record.gate_results:
        return ""
    groups = _group_gate_results(record)
    lines = [_h(2, "The four gates")]
    for i, g in enumerate(groups, start=1):
        status_icon = _GATE_STATUS_ICONS.get(g["status"], f"[{g['status']}]")
        lines.append("")
        lines.append(_h(3, f"{i}. {g['title']} · {status_icon}"))
        if g["reasons"]:
            lines.append("")
            for r in g["reasons"]:
                lines.append(f"- {r}")
        if g["verified"]:
            lines.append("")
            lines.append("Verifier checks confirmed:")
            for v in g["verified"]:
                lines.append(f"- `{v}`")
        for note in g["notes"]:
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


def _format_data_value(v) -> str:
    """Render an arbitrary `data` value for the trace expansion. Lists
    and dicts get JSON-formatted; scalars print as-is."""
    import json as _json
    if isinstance(v, (dict, list)):
        try:
            return _json.dumps(v, indent=2, default=str)
        except Exception:
            return repr(v)
    return str(v)


def _render_verifier_traces(record: WitnessRecord) -> str:
    """Per-verifier expanded trace — the formula, rule, claimed vs
    actual values, residuals, anything the verifier surfaced in its
    `data` block. Off by default; opt-in via `expand_traces=True`.

    Skips NOT_APPLICABLE results (no work was done) and also skips any
    verifier with no `data` payload (nothing to expand). The detail
    string is shown as a short headline; the data dict follows."""
    expandable = _expandable_verifier_results(record)
    if not expandable:
        return ""
    lines = [_h(2, "Verifier traces — the work shown")]
    for v in expandable:
        icon = _VERIFIER_STATUS_ICONS.get(v.status, f"[{v.status}]")
        lines.append("")
        lines.append(_h(3, f"`{v.name}` · {icon}"))
        if v.detail:
            lines.append("")
            lines.append(f"_{v.detail}_")
        lines.append("")
        parts = _split_verifier_data(v.data)
        if parts["formula"]:
            lines.append(f"**Formula:** `{parts['formula']}`")
        if parts["rule"]:
            lines.append(f"**Rule:** {parts['rule']}")
        anchor = parts["anchor"]
        if isinstance(anchor, dict) and anchor.get("ref"):
            layer = anchor.get("layer", "?")
            layer_label = _LAYER_LABELS.get(layer, f"*{layer}*")
            lines.append(
                f"**Derives from:** `{anchor['ref']}` · {layer_label}"
            )
            derivation = anchor.get("derivation")
            if derivation:
                lines.append(f"  > {derivation}")
        if parts["rest"]:
            lines.append("")
            lines.append("**Trace:**")
            lines.append("")
            lines.append("```json")
            lines.append(_format_data_value(parts["rest"]))
            lines.append("```")
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
    summary = _anchor_tier_summary(record)
    if summary:
        lines.append("")
        lines.append(summary)
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
    if cc.shared_anchors:
        refs = ", ".join(f"`{r}`" for r in cc.shared_anchors)
        lines.append(f"Shared citations: {refs}.  ")
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

def render_walkthrough(record: WitnessRecord, *, expand_traces: bool = False) -> str:
    """Render a sealed WitnessRecord as a Socratic markdown walkthrough.

    The output is designed to be readable in any terminal, pasted into
    Slack/email/docs, and round-tripped through human review without
    losing structure. It refuses to compress to a verdict; the closing
    section is always a question.

    With `expand_traces=True`, an additional "Verifier traces" section
    appears between the verifier table and the anchors section, showing
    each verifier's formula, rule, and full `data` payload. Useful when
    the human needs to inspect *how* the engine arrived at each
    verdict — the show-your-work mode.
    """
    sections = [
        _render_header(record),
        _render_submission(record),
        _render_scaffold(record),
        _render_gates(record),
        _render_verifier_table(record),
    ]
    if expand_traces:
        sections.append(_render_verifier_traces(record))
    sections.extend([
        _render_anchors(record),
        _render_closest_case(record),
        _render_socratic_close(record),
    ])
    body = _join_sections(sections)
    # A blank line + horizontal rule between header and first section
    # would be redundant; rely on _join_sections' double-newlines.
    return body


_HTML_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
       max-width: 800px; margin: 2rem auto; padding: 0 1rem; line-height: 1.5;
       color: #222; }
h1 { border-bottom: 2px solid #888; padding-bottom: 0.3rem; }
h2 { margin-top: 2rem; color: #444; border-bottom: 1px solid #ddd;
     padding-bottom: 0.2rem; }
h3 { margin-top: 1.5rem; color: #555; }
.headline-pass    { color: #1a7f37; font-weight: bold; }
.headline-reject  { color: #cf222e; font-weight: bold; }
.headline-quar    { color: #9a6700; font-weight: bold; }
.gate-pass        { color: #1a7f37; }
.gate-reject      { color: #cf222e; }
.gate-quar        { color: #9a6700; }
.layer-jesus      { color: #cf222e; font-weight: bold; }
.layer-bible      { color: #0969da; }
.layer-apostles   { color: #553a90; }
.layer-elders     { color: #6e7781; }
table { border-collapse: collapse; width: 100%; margin: 1rem 0; }
th, td { border: 1px solid #ddd; padding: 0.4rem 0.6rem; text-align: left; }
th { background: #f6f8fa; }
code { background: #f6f8fa; padding: 0.1rem 0.3rem; border-radius: 3px;
       font-family: ui-monospace, "SF Mono", Menlo, monospace; font-size: 0.9em; }
blockquote { border-left: 3px solid #ddd; margin: 0.5rem 0;
             padding: 0.3rem 1rem; color: #555; font-style: italic; }
.socratic { background: #fffbe6; border-left: 4px solid #d4a72c;
            padding: 1rem; margin-top: 2rem; }
.socratic .question { font-style: italic; font-size: 1.1em; }
.no-precedent { color: #6e7781; font-style: italic; }
""".strip()


def _html_escape(text: str) -> str:
    return (text
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def _layer_html_class(layer: str) -> str:
    return {
        "jesus_words":       "layer-jesus",
        "bible":             "layer-bible",
        "apostles":          "layer-apostles",
        "recognized_elders": "layer-elders",
    }.get(layer, "")


def _gate_html_class(status: str) -> str:
    return {
        "PASS":       "gate-pass",
        "REJECT":     "gate-reject",
        "QUARANTINE": "gate-quar",
    }.get(status, "")


def render_walkthrough_html(record: WitnessRecord, *,
                             expand_traces: bool = False,
                             embedded: bool = False) -> str:
    """Render a sealed WitnessRecord as HTML.

    Same sections, same doctrinal commitments as the markdown
    walkthrough — the HTML renderer is just a different surface, not a
    different reading.

    embedded=False (default): full standalone HTML document with
    embedded CSS. Savable to disk, emailable, served from any static
    host. Use this when the output is the page.

    embedded=True: inner content only — no DOCTYPE, no <html>/<head>/
    <body>, no embedded <style>. Use this when injecting the
    walkthrough into a host page that already has its own styling.
    The host page should provide CSS for `.headline-pass`,
    `.headline-reject`, `.headline-quar`, `.gate-pass`, `.gate-reject`,
    `.gate-quar`, `.layer-jesus`, `.layer-bible`, `.layer-apostles`,
    `.layer-elders`, `.socratic`, `.no-precedent`, or accept browser
    defaults.
    """
    pid = _html_escape(record.packet_id or "(no packet_id)")
    headline_class = {
        "PASS":       "headline-pass",
        "REJECT":     "headline-reject",
        "QUARANTINE": "headline-quar",
    }.get(record.overall, "")
    headline_text = {
        "PASS":       "PASSED through all four gates",
        "REJECT":     "REJECTED",
        "QUARANTINE": "in QUARANTINE pending resolution",
    }.get(record.overall, _html_escape(record.overall))

    parts: List[str] = []
    if not embedded:
        parts.append("<!DOCTYPE html>")
        parts.append("<html lang=\"en\">")
        parts.append("<head>")
        parts.append("<meta charset=\"utf-8\">")
        parts.append(f"<title>Witness Record · {pid}</title>")
        parts.append(f"<style>{_HTML_CSS}</style>")
        parts.append("</head>")
        parts.append("<body>")
    else:
        parts.append('<div class="witness-record">')

    # Header
    parts.append("<h1>Witness Record</h1>")
    parts.append(
        f"<p><strong>Packet:</strong> <code>{pid}</code><br>"
        f"<strong>Schema:</strong> <code>{_html_escape(record.schema_version)}</code> · "
        f"<strong>Result:</strong> <span class=\"{headline_class}\">{headline_text}</span></p>"
    )

    # Submission
    if record.axis_coords is not None:
        parts.append("<h2>What you submitted</h2>")
        parts.append(
            f"<p><strong>Domain:</strong> <code>{_html_escape(record.axis_coords.axis)}</code></p>"
        )

    # Scaffold
    if record.axis_coords is not None and record.axis_coords.dimensions:
        parts.append("<h2>Where this sits on the scaffold</h2>")
        if record.axis_coords.umbrella:
            parts.append(
                f"<p><code>{_html_escape(record.axis_coords.axis)}</code> is a "
                f"subsystem of the <strong>{_html_escape(record.axis_coords.umbrella)}</strong> "
                f"umbrella; it lives at the intersection of:</p>"
            )
        else:
            parts.append(
                f"<p><code>{_html_escape(record.axis_coords.axis)}</code> "
                f"lives at the intersection of:</p>"
            )
        parts.append("<ul>")
        for d in sorted(record.axis_coords.dimensions):
            parts.append(f"<li><strong>{_html_escape(d)}</strong></li>")
        parts.append("</ul>")
        neighbors = _scaffold_neighbors(record.axis_coords.axis)
        if neighbors:
            n_parts = [
                f"<strong>{_html_escape(name)}</strong> (shares {len(shared)})"
                for name, shared in neighbors
            ]
            parts.append(
                f"<p>Closest neighbors on the scaffold: {', '.join(n_parts)}.</p>"
            )

    # Gates — shares group logic with the markdown renderer.
    if record.gate_results:
        parts.append("<h2>The four gates</h2>")
        for i, g in enumerate(_group_gate_results(record), start=1):
            cls = _gate_html_class(g["status"])
            parts.append(
                f"<h3>{i}. {_html_escape(g['title'])} · "
                f"<span class=\"{cls}\">[{_html_escape(g['status'])}]</span></h3>"
            )
            if g["reasons"]:
                parts.append("<ul>")
                for r in g["reasons"]:
                    parts.append(f"<li>{_html_escape(r)}</li>")
                parts.append("</ul>")
            if g["verified"]:
                parts.append("<p>Verifier checks confirmed:</p><ul>")
                for v in g["verified"]:
                    parts.append(f"<li><code>{_html_escape(v)}</code></li>")
                parts.append("</ul>")
            for note in g["notes"]:
                parts.append(f"<p><em>{_html_escape(note)}</em></p>")

    # Verifier table
    if record.verifier_results:
        parts.append("<h2>What the verifiers actually checked</h2>")
        parts.append("<table>")
        parts.append("<tr><th>verifier</th><th>status</th><th>rule</th></tr>")
        for v in record.verifier_results:
            cls = _gate_html_class(v.status if v.status in ("PASS", "REJECT", "QUARANTINE") else "")
            rule = ""
            if isinstance(v.data, dict):
                rule = v.data.get("rule") or v.data.get("formula") or ""
            if not rule:
                rule = v.detail or ""
            parts.append(
                f"<tr><td><code>{_html_escape(v.name)}</code></td>"
                f"<td>[{_html_escape(v.status)}]</td>"
                f"<td>{_html_escape(str(rule)[:200])}</td></tr>"
            )
        parts.append("</table>")

    # Verifier traces (opt-in) — shares data-split with the markdown
    # renderer via _split_verifier_data.
    if expand_traces:
        expandable = _expandable_verifier_results(record)
        if expandable:
            parts.append("<h2>Verifier traces — the work shown</h2>")
            for v in expandable:
                parts.append(
                    f"<h3><code>{_html_escape(v.name)}</code> · "
                    f"[{_html_escape(v.status)}]</h3>"
                )
                if v.detail:
                    parts.append(f"<p><em>{_html_escape(v.detail)}</em></p>")
                d = _split_verifier_data(v.data)
                if d["formula"]:
                    parts.append(
                        f"<p><strong>Formula:</strong> <code>{_html_escape(str(d['formula']))}</code></p>"
                    )
                if d["rule"]:
                    parts.append(
                        f"<p><strong>Rule:</strong> {_html_escape(str(d['rule']))}</p>"
                    )
                anchor = d["anchor"]
                if isinstance(anchor, dict) and anchor.get("ref"):
                    cls = _layer_html_class(anchor.get("layer", ""))
                    parts.append(
                        f"<p><strong>Derives from:</strong> "
                        f"<code>{_html_escape(anchor['ref'])}</code> · "
                        f"<span class=\"{cls}\">{_html_escape(anchor.get('layer', '?'))}</span></p>"
                    )
                    derivation = anchor.get("derivation")
                    if derivation:
                        parts.append(
                            f"<blockquote>{_html_escape(derivation)}</blockquote>"
                        )
                if d["rest"]:
                    parts.append("<p><strong>Trace:</strong></p>")
                    parts.append(
                        f"<pre><code>{_html_escape(_format_data_value(d['rest']))}</code></pre>"
                    )

    # Anchors
    if record.anchors:
        parts.append("<h2>Citations and their authority layer</h2>")
        parts.append("<ul>")
        for a in record.anchors:
            cls = _layer_html_class(a.layer)
            line = (
                f"<li><strong>{_html_escape(a.ref)}</strong> · "
                f"<span class=\"{cls}\">{_html_escape(a.layer)}</span>"
            )
            if a.text:
                line += f"<blockquote>{_html_escape(a.text)}</blockquote>"
            line += "</li>"
            parts.append(line)
        parts.append("</ul>")
        summary = _anchor_tier_summary(record)
        if summary:
            parts.append(f"<p><em>{_html_escape(summary)}</em></p>")

    # Closest case
    cc = record.closest_case
    if cc is not None:
        parts.append("<h2>The closest precedent we found</h2>")
        if cc.precedent_id is None:
            parts.append(
                "<p class=\"no-precedent\">No comparable precedent was found "
                "in the ledger. This claim is novel relative to the recorded "
                "record.</p>"
            )
        else:
            parts.append(f"<p><strong><code>{_html_escape(cc.precedent_id)}</code></strong></p>")
            if cc.shared_dimensions:
                dims = ", ".join(
                    f"<code>{_html_escape(d)}</code>"
                    for d in sorted(cc.shared_dimensions)
                )
                parts.append(f"<p>Shared scaffold dimensions: {dims}.</p>")
            if cc.shared_anchors:
                refs = ", ".join(
                    f"<code>{_html_escape(r)}</code>"
                    for r in cc.shared_anchors
                )
                parts.append(f"<p>Shared citations: {refs}.</p>")
            if cc.distance is not None:
                parts.append(f"<p>Distance: <strong>{cc.distance}</strong>.</p>")
            if cc.reasoning_overlay:
                parts.append("<p><strong>Reasoning trace from the precedent:</strong></p>")
                parts.append("<ul>")
                if isinstance(cc.reasoning_overlay, dict):
                    for k, v in cc.reasoning_overlay.items():
                        parts.append(
                            f"<li><strong>{_html_escape(str(k))}</strong> — "
                            f"{_html_escape(str(v))}</li>"
                        )
                parts.append("</ul>")

    # Socratic close
    parts.append("<div class=\"socratic\">")
    parts.append("<h2 style=\"border:none; margin-top:0;\">The Socratic question</h2>")
    if record.overall == "REJECT":
        parts.append("<p class=\"question\">What was wrong with the claim itself?</p>")
        parts.append(
            "<p>The engine refused this packet at one of the hard gates. "
            "The reasons are listed above. The next move belongs to you.</p>"
        )
    elif record.overall == "QUARANTINE":
        parts.append("<p class=\"question\">What is still pending?</p>")
        parts.append(
            "<p>This isn't a verdict yet. One of the gates has held the "
            "packet — usually a wait window or missing witnesses.</p>"
        )
    elif cc is not None and cc.precedent_id is not None:
        parts.append("<p class=\"question\">Is your situation actually like the precedent above?</p>")
        parts.append(
            "<p>The engine has refused to give you a verdict on the question "
            "itself. That's load-bearing: this verdict belongs to the community "
            "of witnesses, not to a machine.</p>"
        )
    else:
        parts.append("<p class=\"question\">What is this situation most like?</p>")
        parts.append(
            "<p>All four gates passed and the verifiers confirmed every "
            "claim that was checkable. No comparable precedent was supplied "
            "for overlay; that doesn't make the decision wrong, only novel.</p>"
        )
    parts.append("</div>")

    if not embedded:
        parts.append("</body>")
        parts.append("</html>")
    else:
        parts.append("</div>")
    return "\n".join(parts)


def render_walkthrough_compact(record: WitnessRecord) -> str:
    """Single-screen render of the same record. ~10 lines max.

    Trades the Socratic walkthrough for a glanceable status. Used when
    piping the engine through CLI (`concordance ask --compact`) or when
    a human is checking many records quickly. Same doctrinal commitments
    apply: no fabricated answer, anchors carry their layer, no-precedent
    renders explicitly, closing line is a question.
    """
    lines: List[str] = []

    # Headline
    pid = record.packet_id or "(no packet_id)"
    domain = record.axis_coords.axis if record.axis_coords else "(unknown domain)"
    lines.append(f"[{record.overall}] {domain} · {pid}")

    # Gates: collapsed to a single status-icon line
    if record.gate_results:
        # Group consecutive same-gate verdicts (worst-status-wins).
        groups: List[List] = []
        for gr in record.gate_results:
            if groups and groups[-1][0].gate == gr.gate:
                groups[-1].append(gr)
            else:
                groups.append([gr])
        gate_segments = []
        for group in groups:
            status = max(
                (gr.status for gr in group),
                key=lambda s: _STATUS_PRIORITY.get(s, -1),
            )
            icon = {"PASS": "✓", "REJECT": "✗", "QUARANTINE": "⏸"}.get(status, "?")
            gate_segments.append(f"{icon} {group[0].gate}")
        lines.append("  gates: " + "  ".join(gate_segments))

    # Failed verifiers, if any (silent on PASS)
    failed = record.failed_verifiers()
    if failed:
        lines.append("  failed:")
        for v in failed:
            detail = (v.detail or "").splitlines()[0][:80]
            lines.append(f"    [{v.status}] {v.name}: {detail}")

    # Anchors — count + tier summary
    if record.anchors:
        layers = {a.layer for a in record.anchors}
        if layers == {"jesus_words"}:
            tier_note = "all primary-tier"
        elif len(layers) == 1:
            tier_note = f"all {next(iter(layers))}"
        else:
            tier_note = "mixed-tier: " + ", ".join(sorted(layers))
        refs = ", ".join(a.ref for a in record.anchors[:3])
        more = "" if len(record.anchors) <= 3 else f", +{len(record.anchors) - 3} more"
        lines.append(f"  anchors: {len(record.anchors)} ({tier_note}) — {refs}{more}")

    # Closest case
    cc = record.closest_case
    if cc is not None:
        if cc.precedent_id is None:
            lines.append("  precedent: none in ledger (novel claim)")
        else:
            shared = len(cc.shared_dimensions)
            dist = f", distance {cc.distance}" if cc.distance is not None else ""
            lines.append(
                f"  precedent: {cc.precedent_id} (shares {shared} dim{dist})"
            )

    # Closing question — branched, single line
    if record.overall == "REJECT":
        lines.append("  → What was wrong with the claim?")
    elif record.overall == "QUARANTINE":
        lines.append("  → What is still pending?")
    elif cc is not None and cc.precedent_id is not None:
        lines.append("  → Is your situation actually like this precedent?")
    else:
        lines.append("  → What is this situation most like?")

    return "\n".join(lines)
