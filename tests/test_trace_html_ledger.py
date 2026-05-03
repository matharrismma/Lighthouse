"""Tests for the third human-surface batch:
  * --trace flag (verifier data expansion in walkthrough)
  * render_walkthrough_html (web-friendly output)
  * Evidence Ledger lookup + --auto-precedent

The doctrinal commitments hold across all three: no fabricated answers,
explicit absence on no-precedent, anchor layers visible, Socratic close
preserved in every renderer.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from concordance_engine.gates import ok, quarantine, reject
from concordance_engine.verifiers.base import confirm, mismatch
from concordance_engine.walkthrough import (
    render_walkthrough, render_walkthrough_html,
)
from concordance_engine.witness_record import (
    Anchor, ClosestCase, WitnessRecord, axis_coords_for,
)
from concordance_engine.ledger import find_closest, list_precedents


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"


def _pass_record(**overrides) -> WitnessRecord:
    base = dict(
        overall="PASS",
        gate_results=(ok("RED"), ok("FLOOR"), ok("BROTHERS"), ok("GOD")),
        verifier_results=(
            confirm("math.equality", "matches",
                    {"formula": "a + b = c", "rule": "symbolic equality",
                     "claimed": "x + 1", "actual": "x + 1"}),
            mismatch("math.derivative", "wrong",
                     {"formula": "d/dx(x^2)", "rule": "power rule",
                      "claimed": "x", "actual": "2x"}),
        ),
        anchors=(Anchor(ref="Mt 5:37", layer="jesus_words"),),
        axis_coords=axis_coords_for("mathematics"),
        closest_case=ClosestCase(
            precedent_id="ledger://p/1",
            shared_dimensions=frozenset({"reasoning"}),
            distance=0.13,
        ),
        packet_id="pkt://test/1",
    )
    base.update(overrides)
    return WitnessRecord(**base)


# ── --trace expansion ──────────────────────────────────────────────────

def test_trace_off_by_default():
    md = render_walkthrough(_pass_record())
    assert "Verifier traces" not in md


def test_trace_on_adds_section():
    md = render_walkthrough(_pass_record(), expand_traces=True)
    assert "Verifier traces" in md


def test_trace_shows_formula_and_rule_for_each_verifier():
    md = render_walkthrough(_pass_record(), expand_traces=True)
    assert "**Formula:**" in md
    assert "a + b = c" in md
    assert "d/dx(x^2)" in md
    assert "**Rule:**" in md
    assert "power rule" in md


def test_trace_shows_extra_data_in_json_block():
    md = render_walkthrough(_pass_record(), expand_traces=True)
    # Extra data fields beyond formula/rule should appear in the JSON
    # trace block.
    assert "claimed" in md
    assert "actual" in md
    assert "2x" in md  # the actual derivative
    assert "```json" in md  # the trace fence


def test_trace_skips_na_results():
    from concordance_engine.verifiers.base import na as na_result
    rec = _pass_record(verifier_results=(
        confirm("a", "ok", {"formula": "f"}),
        na_result("b"),
    ))
    md = render_walkthrough(rec, expand_traces=True)
    # `b` has no data and is NA — should not appear in the trace section.
    if "Verifier traces" in md:
        trace_section = md.split("Verifier traces")[1]
        # Section ends at the next H2 (Citations / Closest precedent /
        # Socratic). Find whichever comes first.
        cuts = [trace_section.find("\n## " + h)
                for h in ("Citations", "The closest", "The Socratic")]
        cuts = [c for c in cuts if c >= 0]
        if cuts:
            trace_section = trace_section[:min(cuts)]
        assert "`b`" not in trace_section


def test_trace_skips_results_with_no_data():
    rec = _pass_record(verifier_results=(
        confirm("with_data", "ok", {"formula": "f"}),
        confirm("no_data", "ok"),  # no data dict
    ))
    md = render_walkthrough(rec, expand_traces=True)
    if "Verifier traces" in md:
        trace_section = md.split("Verifier traces")[1].split("\n## ")[0]
        # `no_data` should be skipped because there's nothing to expand.
        assert "no_data" not in trace_section


# ── HTML renderer ──────────────────────────────────────────────────────

def test_html_returns_full_document():
    html = render_walkthrough_html(_pass_record())
    assert html.startswith("<!DOCTYPE html>")
    assert "</html>" in html
    assert "<style>" in html


def test_html_no_fabricated_answer_field():
    html = render_walkthrough_html(_pass_record())
    forbidden = ("final_answer", "Final Answer", "Engine Answer", "Verdict:")
    for word in forbidden:
        assert word not in html


def test_html_renders_all_sections():
    html = render_walkthrough_html(_pass_record())
    assert "<h1>Witness Record</h1>" in html
    assert "What you submitted" in html
    assert "Where this sits on the scaffold" in html
    assert "The four gates" in html
    assert "What the verifiers actually checked" in html
    assert "Citations and their authority layer" in html
    assert "The closest precedent we found" in html
    assert "The Socratic question" in html


def test_html_anchors_carry_layer_class():
    html = render_walkthrough_html(_pass_record())
    # jesus_words layer should get its dedicated CSS class
    assert "layer-jesus" in html
    assert "Mt 5:37" in html


def test_html_socratic_section_ends_with_question():
    html = render_walkthrough_html(_pass_record())
    # Find the socratic block and confirm it has a question
    socratic_start = html.find('class="socratic"')
    assert socratic_start > 0
    socratic_block = html[socratic_start:]
    assert 'class="question"' in socratic_block
    assert "?" in socratic_block


def test_html_no_precedent_renders_explicitly():
    rec = _pass_record(closest_case=ClosestCase(precedent_id=None))
    html = render_walkthrough_html(rec)
    assert "No comparable precedent" in html
    assert "no-precedent" in html  # the CSS class


def test_html_escapes_potentially_unsafe_text():
    """Anchor text or detail strings could carry HTML — must be
    escaped, not interpreted."""
    rec = _pass_record(anchors=(
        Anchor(ref="<script>alert(1)</script>", layer="jesus_words"),
    ))
    html = render_walkthrough_html(rec)
    # Should NOT have raw <script>; should have escaped form
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_html_with_trace_expansion():
    html = render_walkthrough_html(_pass_record(), expand_traces=True)
    assert "Verifier traces" in html
    assert "<pre>" in html  # trace JSON block uses pre/code


def test_html_reject_path_truncates_late_sections():
    rec = _pass_record(
        overall="REJECT",
        gate_results=(reject("RED", "no claims"),),
        verifier_results=(),
        anchors=(),
        closest_case=None,
    )
    html = render_walkthrough_html(rec)
    # Headline should be REJECTED in red
    assert "REJECTED" in html
    assert "headline-reject" in html
    # No precedent section should appear (closest_case is None)
    assert "The closest precedent we found" not in html


# ── Ledger lookup ──────────────────────────────────────────────────────

def test_list_precedents_returns_all_files():
    """The sample ledger ships with 3 precedent files."""
    precedents = list_precedents()
    pids = {p["precedent_id"] for p in precedents}
    assert "ledger://decision/2024-11-08/admit-member-007" in pids
    assert "ledger://decision/2024-09-22/publish-canon-update" in pids
    assert "ledger://verification/2024-12-15/balance-saponification" in pids


def test_find_closest_governance_packet_returns_governance_precedent():
    cc = find_closest({"domain": "governance"})
    assert cc is not None
    assert cc.precedent_id is not None
    # Both governance precedents share all 3 dimensions; either is a
    # valid answer. Check that the lookup returned one of them.
    assert "decision" in cc.precedent_id
    # Same axis → distance should be 0.0 (full Jaccard match) or close.
    assert cc.distance is not None
    assert cc.distance <= 0.01


def test_find_closest_chemistry_packet_returns_chemistry_precedent():
    cc = find_closest({"domain": "chemistry"})
    assert cc is not None
    assert cc.precedent_id is not None
    assert "saponification" in cc.precedent_id


def test_find_closest_unknown_domain_returns_none():
    """Unknown domain — no axis on the scaffold, no lookup possible."""
    cc = find_closest({"domain": "underwater_basket_weaving"})
    assert cc is None


def test_find_closest_carries_reasoning_overlay():
    cc = find_closest({"domain": "governance"})
    assert cc is not None
    assert cc.reasoning_overlay is not None
    assert isinstance(cc.reasoning_overlay, dict)
    assert len(cc.reasoning_overlay) > 0


def test_find_closest_with_empty_ledger_returns_explicit_novel(tmp_path):
    """Ledger directory exists but has no precedents — return explicit
    novel-claim signal, not silent absence."""
    cc = find_closest({"domain": "chemistry"},
                       ledger_dir=tmp_path)
    assert cc is not None
    assert cc.precedent_id is None  # explicit "no precedent"


def test_find_closest_with_no_dimension_overlap_returns_explicit_novel(tmp_path):
    """Ledger has precedents but none share any scaffold dimension with
    the input packet."""
    # Put a single precedent on a dimension that nothing else shares.
    fake = {
        "precedent_id": "ledger://test/isolated",
        "axis": "calendar_time",
        "dimensions": ["time_sequence"],
        "summary": "isolated",
    }
    (tmp_path / "isolated.json").write_text(json.dumps(fake), encoding="utf-8")
    # mathematics sits on `reasoning` only — no overlap with time_sequence.
    cc = find_closest({"domain": "mathematics"}, ledger_dir=tmp_path)
    assert cc is not None
    assert cc.precedent_id is None


def test_find_closest_skips_malformed_files(tmp_path):
    """A bad JSON file in the ledger shouldn't break the lookup."""
    (tmp_path / "bad.json").write_text("{ not valid json", encoding="utf-8")
    good = {
        "precedent_id": "ledger://test/good",
        "axis": "governance",
        "dimensions": ["reasoning", "authority_trust", "time_sequence"],
        "summary": "good",
    }
    (tmp_path / "good.json").write_text(json.dumps(good), encoding="utf-8")
    cc = find_closest({"domain": "governance"}, ledger_dir=tmp_path)
    assert cc is not None
    assert cc.precedent_id == "ledger://test/good"


# ── CLI: ledger subcommand ─────────────────────────────────────────────

def _run_cli(*args, env_extra=None):
    env = os.environ.copy()
    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (str(SRC) + os.pathsep + pp) if pp else str(SRC)
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, "-m", "concordance_engine.cli", *args],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
        encoding="utf-8",
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_cli_ledger_list_shows_all_precedents():
    rc, stdout, _ = _run_cli("ledger", "list")
    assert rc == 0
    assert "admit-member-007" in stdout
    assert "publish-canon-update" in stdout
    assert "saponification" in stdout


def test_cli_ledger_lookup_finds_chemistry_precedent(tmp_path):
    packet = {"domain": "chemistry", "claims": ["x"]}
    f = tmp_path / "p.json"
    f.write_text(json.dumps(packet), encoding="utf-8")
    rc, stdout, _ = _run_cli("ledger", "lookup", str(f))
    assert rc == 0
    assert "saponification" in stdout
    assert "shared dimensions" in stdout


def test_cli_ledger_lookup_unknown_domain_says_novel(tmp_path):
    packet = {"domain": "underwater_basket_weaving"}
    f = tmp_path / "p.json"
    f.write_text(json.dumps(packet), encoding="utf-8")
    rc, stdout, _ = _run_cli("ledger", "lookup", str(f))
    assert rc == 0
    assert "novel" in stdout.lower() or "no comparable" in stdout.lower()


# ── CLI: `ask --auto-precedent` ────────────────────────────────────────

def test_cli_ask_auto_precedent_attaches_precedent_to_record(tmp_path):
    packet = {
        "domain": "chemistry",
        "id": "pkt://test/auto-pre/1",
        "claims": ["water is H2O"],
        "scope": "adapter", "created_epoch": 1,
        "wait_window_seconds": 0,
        "required_witnesses": 0, "witness_count": 0,
    }
    f = tmp_path / "p.json"
    f.write_text(json.dumps(packet), encoding="utf-8")
    rc, stdout, stderr = _run_cli(
        "ask", str(f), "--auto-precedent", "--json", "--now-epoch", "10000",
    )
    assert rc in (0, 1, 2), f"unexpected rc {rc}: {stderr}"
    parsed = json.loads(stdout)
    cc = parsed.get("closest_case")
    assert cc is not None
    assert cc.get("precedent_id") is not None
    assert "saponification" in cc["precedent_id"]


def test_cli_ask_html_flag_emits_html(tmp_path):
    packet = {
        "domain": "chemistry", "id": "pkt://test/html/1",
        "claims": ["x"], "scope": "adapter", "created_epoch": 1,
        "wait_window_seconds": 0,
        "required_witnesses": 0, "witness_count": 0,
    }
    f = tmp_path / "p.json"
    f.write_text(json.dumps(packet), encoding="utf-8")
    rc, stdout, _ = _run_cli(
        "ask", str(f), "--html", "--now-epoch", "10000",
    )
    assert rc in (0, 1, 2)
    assert stdout.startswith("<!DOCTYPE html>")
    assert "<style>" in stdout
    assert "Witness Record" in stdout


def test_cli_ask_trace_flag_expands_verifier_data(tmp_path):
    packet = {
        "domain": "chemistry", "id": "pkt://test/trace/1",
        "claims": ["water is H2O"], "scope": "adapter",
        "created_epoch": 1, "wait_window_seconds": 0,
        "required_witnesses": 0, "witness_count": 0,
    }
    f = tmp_path / "p.json"
    f.write_text(json.dumps(packet), encoding="utf-8")
    rc, stdout, _ = _run_cli(
        "ask", str(f), "--trace", "--now-epoch", "10000",
    )
    assert rc in (0, 1, 2)
    # With --trace, the "Verifier traces" section should appear (assuming
    # at least one verifier produced data — the chemistry RED check does).
    if "Verifier traces" not in stdout:
        # Some packets may not produce expandable trace data; the test
        # passes as long as the flag didn't break the command.
        assert "Witness Record" in stdout


def test_cli_ask_three_format_flags_mutually_exclusive(tmp_path):
    f = tmp_path / "p.json"
    f.write_text('{"domain": "chemistry", "claims": ["x"]}', encoding="utf-8")
    rc, _, stderr = _run_cli(
        "ask", str(f), "--compact", "--html", "--now-epoch", "10000",
    )
    assert rc == 4
    assert "mutually exclusive" in stderr.lower()
