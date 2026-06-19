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


# ── Lock in the discovery/indexability + Acts-2 work shipped 2026-06-19 ──────

def test_surface_check_covers_the_crawlable_record_and_missions():
    """The health gate must guard the new doors with REAL-DATA fingerprints."""
    src = _read("tools", "check_surfaces.py")
    for door in ("/almanac/book", "/curriculum/book", "/verified", "/grid/scaffold",
                 "/missions", "/seal/{hash}"):
        assert door in src, "check_surfaces.py must guard %s" % door
    for proof in ("proven claims", "dimensions", "missions", "without trusting us"):
        assert proof in src, "check must assert real content (%r), not just 200" % proof


def test_seals_are_server_rendered_not_redirected():
    """The proof moat must server-render crawlable HTML for browsers/crawlers --
    NOT redirect them back to the client-rendered /seal.html (the old bug that
    left every proof invisible to search and AI retrieval)."""
    src = _read("api", "app.py")
    assert "def _seal_html(" in src, "the SSR proof renderer must exist"
    assert "ClaimReview" in src, "the seal proof must carry ClaimReview JSON-LD"
    assert 'RedirectResponse(url=f"/seal.html' not in src, \
        "seal HTML must NOT redirect crawlers to the JS viewer"


def test_verified_index_content_negotiates_to_crawlable_html():
    """/verified must serve a crawlable hub to browsers and JSON to agents."""
    assert "def _verified_html(" in _read("api", "app.py"), \
        "the verified hub renderer must exist"


def test_missions_guardrails_are_baked_in():
    """The Acts-2 primitive must carry its honest guardrails in the module itself."""
    low = _read("api", "missions.py").lower()
    assert "never feed" in low or "feeds, houses, or heals" in low, \
        "missions must say the software seeds/facilitates, never feeds/houses/heals"
    assert "christ" in low, "a mission must point to Christ, not be an idol"
    assert "locally sovereign" in low, "each mission is locally sovereign"


def test_robots_does_not_block_the_seal_proofs():
    """robots.txt must NOT carry a blanket `Disallow: /seal` -- that blocked the
    now-crawlable proof pages. Only the POST paths may be disallowed."""
    lines = [ln.strip() for ln in _read("site", "robots.txt").splitlines()]
    assert "Disallow: /seal" not in lines, \
        "a bare `Disallow: /seal` blocks the crawlable proof pages"
