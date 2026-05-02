"""Regression test for lazy verifier imports.

Importing `concordance_engine.verifiers` must NOT pull scipy or sympy
unless a packet actually exercises a domain that needs them. These
libraries together cost ~1.5s at import time; loading them on demand
keeps cold-start fast (37× faster as of the lazy-loading refactor).

If this test fails, somebody re-introduced an eager import in a
verifier module's top-level statements. Push the import inside the
function that actually uses it (or import it at module-top with a
local-only side effect) — see chemistry / formal_logic for examples
of modules that *can* import sympy at top-level because they're loaded
on demand.
"""
from __future__ import annotations

import importlib
import subprocess
import sys


def _import_in_subprocess(stmt: str) -> set:
    """Run `stmt` in a fresh Python and return the set of modules
    loaded afterward. Subprocess isolation matters: pytest itself may
    have already imported scipy/sympy via earlier tests, so checking
    sys.modules in-process gives a false positive."""
    code = (
        "import sys\n"
        f"{stmt}\n"
        "print('|'.join(sorted(sys.modules.keys())))"
    )
    result = subprocess.run(
        [sys.executable, "-c", code],
        capture_output=True, text=True, check=True,
        env={"PYTHONPATH": "src", **__import_environ()},
    )
    return set(result.stdout.strip().split("|"))


def __import_environ():
    import os
    return dict(os.environ)


def test_importing_verifiers_does_not_load_scipy():
    loaded = _import_in_subprocess("from concordance_engine import verifiers")
    scipy_modules = {m for m in loaded if m == "scipy" or m.startswith("scipy.")}
    assert not scipy_modules, (
        f"scipy was eagerly loaded by `from concordance_engine import verifiers` "
        f"({len(scipy_modules)} scipy modules). Push scipy imports inside the "
        f"verifier modules' top level only — they will be loaded lazily on first "
        f"use via _get_module()."
    )


def test_importing_verifiers_does_not_load_sympy():
    loaded = _import_in_subprocess("from concordance_engine import verifiers")
    sympy_modules = {m for m in loaded if m == "sympy" or m.startswith("sympy.")}
    assert not sympy_modules, (
        f"sympy was eagerly loaded by `from concordance_engine import verifiers` "
        f"({len(sympy_modules)} sympy modules). Push sympy imports inside the "
        f"verifier modules' top level only — they will be loaded lazily on first "
        f"use via _get_module()."
    )


def test_running_a_lightweight_domain_does_not_load_scipy():
    """A packet for a domain that doesn't need scipy (e.g. witness)
    should not trigger scipy load. This catches the case where a
    cross-cutting verifier or a refactor pulled scipy into a hot path."""
    loaded = _import_in_subprocess(
        "from concordance_engine import verifiers\n"
        "verifiers.run_for_domain('witness', {})"
    )
    scipy_modules = {m for m in loaded if m == "scipy" or m.startswith("scipy.")}
    assert not scipy_modules, (
        "scipy was loaded by running a witness packet — the witness "
        "verifier shouldn't need it."
    )


def test_running_statistics_does_load_scipy():
    """Sanity check: when statistics IS exercised, scipy *should* load.
    This locks in the contract that scipy is reachable, just lazily."""
    loaded = _import_in_subprocess(
        "from concordance_engine import verifiers\n"
        "verifiers.run_for_domain('statistics', {})"
    )
    scipy_modules = {m for m in loaded if m == "scipy" or m.startswith("scipy.")}
    assert scipy_modules, (
        "statistics ran without loading scipy — either the lazy loader "
        "broke or statistics no longer uses scipy."
    )


def test_lazy_module_caching():
    """Successive calls to _get_module for the same domain return the
    same cached object — we don't re-import on every call."""
    from concordance_engine import verifiers
    a = verifiers._get_module("witness")
    b = verifiers._get_module("witness")
    assert a is b
    # Aliases pointing at the same canonical module also resolve to the
    # same loaded object.
    c = verifiers._get_module("testimony")
    assert a is c


def test_lazy_module_unknown_domain_returns_none():
    from concordance_engine import verifiers
    assert verifiers._get_module("not_a_real_domain") is None
