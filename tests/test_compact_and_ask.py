"""Tests for render_walkthrough_compact, the `concordance ask`
subcommand, and parse_and_seal end-to-end.

Locks in: the compact render fits on one screen, doesn't fabricate
answers, and ends with a question; the CLI ask subcommand routes
both --packet and --text inputs through validate_and_seal; the
nl_to_packet → seal pipeline produces a valid WitnessRecord.
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
    render_walkthrough, render_walkthrough_compact,
)
from concordance_engine.witness_record import (
    Anchor, ClosestCase, WitnessRecord, axis_coords_for,
)
from concordance_engine.nl_to_packet import parse_and_validate, parse_and_seal


REPO_ROOT = Path(__file__).resolve().parent.parent
SRC = REPO_ROOT / "src"


def _pass_record(**overrides) -> WitnessRecord:
    base = dict(
        overall="PASS",
        gate_results=(
            ok("RED"),
            ok("FLOOR"),
            ok("BROTHERS"),
            ok("GOD"),
        ),
        verifier_results=(
            confirm("math.equality", "matches", {"formula": "a + b = c"}),
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


# ── Compact renderer ───────────────────────────────────────────────────

def test_compact_fits_on_one_screen():
    """The compact render targets ~10 lines max — never grow it past
    20 even for rich records."""
    md = render_walkthrough_compact(_pass_record())
    line_count = len(md.splitlines())
    assert line_count <= 20, f"compact render is {line_count} lines, too verbose"


def test_compact_starts_with_status_headline():
    md = render_walkthrough_compact(_pass_record())
    first_line = md.splitlines()[0]
    assert first_line.startswith("[PASS]")
    assert "mathematics" in first_line
    assert "pkt://test/1" in first_line


def test_compact_contains_no_fabricated_answer():
    md = render_walkthrough_compact(_pass_record())
    forbidden = ("final_answer", "Final Answer", "Engine Answer", "Verdict:",
                 "engine_answer")
    for word in forbidden:
        assert word not in md


def test_compact_ends_with_question():
    md = render_walkthrough_compact(_pass_record())
    assert md.rstrip().endswith("?")


def test_compact_summarizes_anchor_tier():
    """When all anchors are primary-tier, surface that fact in one
    glance instead of forcing the human to inspect each anchor."""
    md = render_walkthrough_compact(_pass_record(anchors=(
        Anchor(ref="Mt 5:37", layer="jesus_words"),
        Anchor(ref="Lk 17:3-4", layer="jesus_words"),
    )))
    assert "all primary-tier" in md


def test_compact_marks_mixed_tier_anchors():
    md = render_walkthrough_compact(_pass_record(anchors=(
        Anchor(ref="Mt 5:37", layer="jesus_words"),
        Anchor(ref="Rom 12:1", layer="apostles"),
    )))
    assert "mixed-tier" in md


def test_compact_lists_failed_verifiers():
    rec = _pass_record(
        overall="REJECT",
        verifier_results=(
            mismatch("math.equality", "claim was 5, actual is 4"),
        ),
        closest_case=None,
    )
    md = render_walkthrough_compact(rec)
    assert "math.equality" in md
    assert "claim was 5" in md


def test_compact_silent_on_failed_when_all_pass():
    md = render_walkthrough_compact(_pass_record())
    assert "failed:" not in md


def test_compact_handles_no_precedent_explicitly():
    rec = _pass_record(closest_case=ClosestCase(precedent_id=None))
    md = render_walkthrough_compact(rec)
    assert "novel claim" in md


def test_compact_omits_precedent_section_when_no_lookup():
    rec = _pass_record(closest_case=None)
    md = render_walkthrough_compact(rec)
    assert "precedent:" not in md


def test_compact_socratic_question_branches_by_status():
    pass_md = render_walkthrough_compact(_pass_record(closest_case=None))
    assert "What is this situation most like?" in pass_md

    pass_with_pre = render_walkthrough_compact(_pass_record())
    assert "Is your situation actually like this precedent?" in pass_with_pre

    reject_md = render_walkthrough_compact(_pass_record(
        overall="REJECT",
        gate_results=(reject("RED", "no claims"),),
        verifier_results=(),
        closest_case=None,
    ))
    assert "What was wrong with the claim?" in reject_md

    quar_md = render_walkthrough_compact(_pass_record(
        overall="QUARANTINE",
        gate_results=(ok("RED"), ok("FLOOR"),
                      quarantine("BROTHERS", "witnesses 1/2")),
        closest_case=None,
    ))
    assert "What is still pending?" in quar_md


# ── parse_and_validate / parse_and_seal ────────────────────────────────

def test_parse_and_validate_no_match_returns_none_pair():
    result, eng = parse_and_validate("how about a nice cup of tea")
    assert result is None
    assert eng is None


def test_parse_and_validate_chemistry_equation_returns_engine_result():
    """Pre-fix this would crash because validate_packet was called
    without config=. This locks in the fix."""
    result, eng = parse_and_validate("is C + O2 -> CO2 balanced?")
    assert result is not None
    assert eng is not None
    assert hasattr(eng, "overall")  # EngineResult shape


def test_parse_and_seal_returns_witness_record():
    rec = parse_and_seal("is C + O2 -> CO2 balanced?")
    assert isinstance(rec, WitnessRecord)
    assert rec.overall in ("PASS", "REJECT", "QUARANTINE")
    # axis_coords should be set for chemistry domain
    assert rec.axis_coords is not None
    assert rec.axis_coords.axis == "chemistry"


def test_parse_and_seal_unparseable_returns_none():
    rec = parse_and_seal("just some prose with no claim shape")
    assert rec is None


def test_parse_and_seal_record_renders_through_walkthrough():
    """End-to-end: NL → parse → seal → render. The full human pipeline
    should produce a non-empty markdown document with no fabricated
    answer."""
    rec = parse_and_seal("merge sort runs in O(n log n)")
    assert rec is not None
    md = render_walkthrough(rec)
    assert "Witness Record" in md
    forbidden = ("final_answer", "Final Answer", "Engine Answer")
    for word in forbidden:
        assert word not in md


# ── `concordance ask` CLI subcommand ───────────────────────────────────

def _run_ask(*args, env_extra=None):
    """Invoke `python -m concordance_engine.cli ask ...` and return
    (returncode, stdout, stderr)."""
    env = os.environ.copy()
    pp = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = (str(SRC) + os.pathsep + pp) if pp else str(SRC)
    # The CLI reconfigures stdout to UTF-8 internally, but the Python
    # interpreter still reads PYTHONIOENCODING for fallback paths. Set
    # it so subprocess.run captures bytes correctly on Windows.
    env.setdefault("PYTHONIOENCODING", "utf-8")
    if env_extra:
        env.update(env_extra)
    proc = subprocess.run(
        [sys.executable, "-m", "concordance_engine.cli", "ask", *args],
        capture_output=True, text=True, env=env, cwd=str(REPO_ROOT),
        encoding="utf-8",
    )
    return proc.returncode, proc.stdout, proc.stderr


def test_ask_with_packet_file_renders_walkthrough(tmp_path):
    packet = {
        "domain": "chemistry",
        "id": "pkt://test/ask/1",
        "claims": ["water is H2O"],
        "scope": "adapter",
        "created_epoch": 1,
        "wait_window_seconds": 0,
        "required_witnesses": 0,
        "witness_count": 0,
    }
    packet_file = tmp_path / "p.json"
    packet_file.write_text(json.dumps(packet), encoding="utf-8")
    rc, stdout, stderr = _run_ask(str(packet_file), "--now-epoch", "10000")
    assert rc == 0, f"non-zero rc: {rc}\nstderr: {stderr}"
    assert "Witness Record" in stdout
    assert "Socratic question" in stdout


def test_ask_compact_flag_emits_compact_render(tmp_path):
    packet = {"domain": "chemistry", "id": "pkt://test/ask/2",
              "claims": ["water is H2O"], "scope": "adapter",
              "created_epoch": 1, "wait_window_seconds": 0,
              "required_witnesses": 0, "witness_count": 0}
    packet_file = tmp_path / "p.json"
    packet_file.write_text(json.dumps(packet), encoding="utf-8")
    rc, stdout, stderr = _run_ask(str(packet_file), "--compact",
                                   "--now-epoch", "10000")
    # Status may be PASS/REJECT/QUARANTINE depending on verifier outcome;
    # what matters is it ran cleanly and emitted the compact format.
    assert rc in (0, 1, 2), f"unexpected rc {rc}\nstderr: {stderr}"
    assert stdout.startswith("["), f"stdout: {stdout!r}"  # [PASS] / [REJECT] / etc
    line_count = len(stdout.strip().splitlines())
    assert line_count <= 20


def test_ask_json_flag_emits_witness_record_json(tmp_path):
    packet = {"domain": "chemistry", "id": "pkt://test/ask/3",
              "claims": ["x"], "scope": "adapter", "created_epoch": 1,
              "wait_window_seconds": 0, "required_witnesses": 0,
              "witness_count": 0}
    packet_file = tmp_path / "p.json"
    packet_file.write_text(json.dumps(packet), encoding="utf-8")
    rc, stdout, _ = _run_ask(str(packet_file), "--json",
                              "--now-epoch", "10000")
    assert rc == 0
    parsed = json.loads(stdout)
    assert parsed["schema_version"]
    assert parsed["overall"] in ("PASS", "REJECT", "QUARANTINE")
    assert "gate_results" in parsed
    # Doctrine: no fabricated answer field in JSON output
    forbidden = {"final_answer", "answer", "engine_answer", "verdict_answer"}
    assert not (forbidden & set(parsed.keys()))


def test_ask_text_flag_routes_through_nl_to_packet():
    rc, stdout, stderr = _run_ask("--text", "merge sort runs in O(n log n)",
                                   "--now-epoch", "9999999999", "--compact")
    assert rc in (0, 1, 2), f"unexpected rc {rc}, stderr: {stderr}"
    assert "computer_science" in stdout


def test_ask_text_unparseable_exits_5():
    rc, _stdout, stderr = _run_ask("--text", "the sky is blue",
                                    "--now-epoch", "9999999999")
    assert rc == 5
    assert "no template matched" in stderr.lower()


def test_ask_no_input_exits_4():
    rc, _stdout, stderr = _run_ask("--now-epoch", "9999999999")
    assert rc == 4
    assert "provide either" in stderr.lower()


def test_ask_both_packet_and_text_exits_4(tmp_path):
    packet_file = tmp_path / "p.json"
    packet_file.write_text("{}", encoding="utf-8")
    rc, _stdout, stderr = _run_ask(str(packet_file), "--text", "x",
                                    "--now-epoch", "9999999999")
    assert rc == 4
    assert "either --text or a packet path" in stderr.lower()


def test_ask_compact_and_json_mutually_exclusive(tmp_path):
    packet_file = tmp_path / "p.json"
    packet_file.write_text('{"domain": "chemistry", "claims": ["x"]}',
                           encoding="utf-8")
    rc, _stdout, stderr = _run_ask(str(packet_file), "--compact", "--json",
                                    "--now-epoch", "9999999999")
    assert rc == 4
    assert "mutually exclusive" in stderr.lower()


def test_ask_packet_not_found_exits_4():
    rc, _stdout, stderr = _run_ask("/nonexistent/path/p.json",
                                    "--now-epoch", "9999999999")
    assert rc == 4
    assert "not found" in stderr.lower()
