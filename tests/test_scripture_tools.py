"""Offline tests for the Scripture MCP TOOL layer -- read_passage, concord,
cross_references, commentary, sermon, lexicon, word_study.

Before this file the Scripture tool layer had ZERO coverage -- and it is exactly
where the `def scripture` module-shadowing regression lived (a tool function
shadowing the imported `scripture` verifier module, silently breaking word_study /
resolve / triangulate). These tests guard that class of bug and pin the honesty
contracts (concord is never a verdict; cross_references / commentary / sermon are
ATTRIBUTED).

Follows the repo's graceful-degradation pattern (tests/test_scripture.py): when the
lw/ Layer-0 data is provisioned, assert the real contract; when it is not, accept the
clean source_missing/insufficient status. So these pass in CI without the data AND
catch real breakage where the data exists.

Run: PYTHONPATH=src python -m pytest tests/test_scripture_tools.py
     PYTHONPATH=src python tests/test_scripture_tools.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for _p in (str(_ROOT), str(_ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from concordance_engine.mcp_server import tools as T  # noqa: E402

# statuses that mean "the data simply is not provisioned here" -- acceptable in CI
_GRACEFUL = {"source_missing", "not_found", "insufficient_takes",
             "insufficient_passages"}


def _ok_or_graceful(res):
    """Every Scripture tool must return a dict with a status that is either 'ok' or a
    clean graceful status -- never an unhandled error/crash shape."""
    assert isinstance(res, dict), f"tool did not return a dict: {type(res)}"
    assert "status" in res, f"tool result missing 'status': {list(res)[:6]}"
    assert res["status"] == "ok" or res["status"] in _GRACEFUL, \
        f"unexpected status {res.get('status')!r}: {res.get('detail')}"
    return res["status"] == "ok"


# ── the tools return clean, contract-shaped results ────────────────────────────

def test_read_passage():
    r = T.read_passage("John 3:16")
    if _ok_or_graceful(r):
        assert r.get("verses"), "ok read_passage returned no verses"
        assert r["verses"][0].get("ref")


def test_read_passage_show_concord_integration():
    r = T.read_passage("Romans 8:28", show_concord=True)
    if _ok_or_graceful(r):
        # concord block is attached only when the take sources are present; if attached
        # it must carry the honesty note, never a truth verdict.
        co = r.get("concord")
        if isinstance(co, dict) and co.get("n_sources"):
            assert "NOT a verdict" in (co.get("note") or "")


def test_concord_is_never_a_verdict():
    r = T.concord("John 3:16")
    if _ok_or_graceful(r):
        assert r.get("concord_terms") is not None
        assert "NOT a verdict" in (r.get("note") or ""), "concord lost its honesty disclaimer"
        # concord is an overlap measure, not a judgment -- it must not emit a verdict field
        assert "verdict" not in r


def test_concord_across_xrefs_is_never_a_verdict():
    r = T.concord("John 3:16", across_xrefs=True)
    if _ok_or_graceful(r):
        assert r.get("mode") == "across_xrefs"
        assert "NOT a verdict on meaning" in (r.get("note") or "")
        assert "verdict" not in r


def test_cross_references_attributed():
    r = T.cross_references("Romans 8:28")
    if _ok_or_graceful(r):
        assert r.get("cross_references"), "ok cross_references returned no refs"
        attrib = (r.get("attribution") or "").lower()
        assert "openbible" in attrib or "treasury" in attrib, "cross_references not attributed"


def test_commentary_attributed():
    r = T.commentary("John 3:16")
    if _ok_or_graceful(r):
        assert r.get("notes"), "ok commentary returned no notes"
        assert r.get("attribution"), "commentary not attributed"


def test_sermon_attributed():
    r = T.sermon("Romans 8:28")
    if _ok_or_graceful(r):
        assert r.get("sermons"), "ok sermon returned no sermons"
        assert r.get("attribution"), "sermon not attributed"


def test_lexicon():
    r = T.lexicon("G3056")  # logos
    if _ok_or_graceful(r):
        assert r.get("definition") or r.get("gloss"), "ok lexicon returned no definition"


# ── the scripture module-shadowing regression guard ───────────────────────────

def test_word_study_no_shadowing_regression():
    """word_study depends on the `scripture` VERIFIER module. The shadowing bug made
    it crash / return source_missing even when data was present. It must always return
    a clean dict with a status, never raise."""
    r = T.word_study("G3056")
    assert isinstance(r, dict) and "status" in r
    assert r["status"] == "ok" or r["status"] in _GRACEFUL


def test_scripture_module_not_shadowed():
    """Structural guard for the exact regression: the `scripture` verifier MODULE must
    stay a distinct, usable module (with resolve_ref/word_study), and the `scripture`
    TOOL must be a separate callable. If a `def scripture` ever shadows the import
    again, one of these breaks."""
    from concordance_engine.verifiers import scripture as scr_mod
    assert callable(getattr(scr_mod, "resolve_ref", None)), "scripture verifier module lost resolve_ref"
    assert callable(getattr(scr_mod, "word_study", None)), "scripture verifier module lost word_study"
    # the tool of the same name is a distinct callable in the registry
    assert callable(T.ALL_TOOLS.get("scripture")), "scripture tool missing from ALL_TOOLS"
    assert callable(T.ALL_TOOLS.get("word_study")), "word_study tool missing from ALL_TOOLS"


def test_all_scripture_tools_registered():
    for name in ("read_passage", "concord", "cross_references", "commentary",
                 "sermon", "lexicon", "original_words", "scripture", "word_study"):
        assert callable(T.ALL_TOOLS.get(name)), f"{name} not registered in ALL_TOOLS"


if __name__ == "__main__":
    import traceback
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    failed = 0
    for fn in fns:
        try:
            fn()
            print("PASS", fn.__name__)
        except Exception:  # noqa: BLE001
            failed += 1
            print("FAIL", fn.__name__)
            traceback.print_exc()
    print(f"\n{len(fns) - failed}/{len(fns)} passed")
    sys.exit(1 if failed else 0)
