"""Lock in the tutor-shape fix and the standing surface guard.

On 2026-06-16 the tutor rendered blank because /curriculum returns
{tracks:{phonics:[...]}} but read.html indexed flat d[key]. The runtime guard is
tools/check_surfaces.py; these are the offline, deterministic source-level guards so the
fix can't be quietly removed. No network, no engine -- just reads the shipped files.
See [[feedback_verify_runtime_not_just_http200_2026-06-16]] in operator memory.
"""
import os

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _read(*parts):
    with open(os.path.join(ROOT, *parts), encoding="utf-8") as f:
        return f.read()


def test_tutor_tolerates_curriculum_shape():
    """The consumer must be shape-tolerant: d.tracks||d before indexing subjects."""
    html = _read("site", "read.html")
    assert "d.tracks||d" in html, "read.html must normalize the /curriculum shape (d.tracks||d)"
    # and it must NOT go back to indexing the raw response flat for subjects
    assert "(C[m.key]||[])" in html, "subjects should be read off the normalized object C"


def test_surface_check_exists_and_covers_the_doors():
    """The standing health check must guard the JS surfaces and their data paths."""
    src = _read("tools", "check_surfaces.py")
    for needed in ("/read.html", "/curriculum", "/brain-graph.json", "/", "/identity"):
        assert '"%s"' % needed in src, "check_surfaces.py must guard %s" % needed
    # it must verify data, not just status, for the JSON dependencies
    assert "total_units" in src, "curriculum check must assert real units, not just 200"
    assert "no graph nodes" in src, "brain-graph check must assert real nodes, not just 200"


def test_curriculum_check_is_a_content_fingerprint_not_just_200():
    """A 200 on a JS shell is not proof of life; the check must look past the status."""
    src = _read("tools", "check_surfaces.py")
    # fingerprints prove the right rendered content came back
    assert "must_contain" in src or "needle" in src, "check must fingerprint content"
    assert "SOME SURFACES DOWN" in src and "ALL UP" in src, "check must give a clear verdict"
