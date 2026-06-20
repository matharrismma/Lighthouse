#!/usr/bin/env python3
"""One-shot: capture the 2026-06-20 harmonics/dimensions/canon session as engine
teachings (operator's directives + the principle + what the assay actually said).
Run ONCE against the authoritative store (the droplet). Sovereign; uses
api.teachings.record. Each teaching keeps its HONEST status — including the
refutations, because the method (intuition proposes, the assay disposes) is the
lesson, not any single claim.
"""
import sys
sys.path.insert(0, ".")
from api import teachings  # noqa: E402

TEACHINGS = [
    dict(
        tid="two_axis_systems_measure_meaning_bridge",
        directive="Scale and time are not dimensions. There are more of those. We need to find them. Forces?",
        principle=("The map has two KINDS of axis, not one. MEANING axes (how meaning "
                   "structures) and MEASURE axes (how reality is quantified) are different "
                   "categories; scale/time are measures, not conceptual dimensions. FORCES are "
                   "a third list (interactions) — dimensionally derived, not base measures. The "
                   "BRIDGE (the math both trees share) is the harmony of science and math itself."),
        realization=("The 11 conceptual dimensions split 4 meaning / 4 measure / 3 bridge. The "
                     "physical base quantities (length/scale, time, mass, charge, temperature, "
                     "+ conventional amount/luminous_intensity) and the four fundamental forces "
                     "are their own lists, kept OUT of the conceptual set."),
        result=("Built into grid.py: DIMENSION_KIND, MEASURE_AXES, FORCES. The measure-count is "
                "a unit convention, not a deep fact (natural units collapse it); the deep things "
                "are the quantities, not their number."),
        status="confirmed",
        refs=["src/concordance_engine/grid.py"],
    ),
    dict(
        tid="missing_one_intuition_proposes_assay_disposes",
        directive="I still think we are missing 1.",
        principle=("A persistent intuition of a gap is generative and worth chasing — but it "
                   "must be TESTED against a null, never assumed. A dual is NOT a new dimension "
                   "(its negation is already implied by the original). Refutation is a real, "
                   "valuable outcome; the fruit can be the cleanup the hunt forces, not the "
                   "claim it started from."),
        realization=("Three candidate 12th dimensions — continuity, abstract_spirit, proportion — "
                     "all failed the same way (at or below chance; duals redundant). The 'missing 1' "
                     "was finally a DATA BUG: biology lacked discreteness though its child genetics "
                     "carries it. Fixing that coherence-mandated bug closed the phantom 'missing "
                     "domain' gap; no 12th dimension and no new domain were warranted."),
        result=("11 dimensions held robust; 72 domains intact. The real fruit was a cleaner, more "
                "honest map: subdomains/branches, measure/meaning/bridge, the canon layer, biology "
                "coherence fixed. The intuition was right that something was off — wrong about what."),
        status="discipline",
        refs=["src/concordance_engine/grid.py"],
    ),
    dict(
        tid="canon_separate_layer_show_dont_crown",
        directive=("On Canon, we treat it as a separate layer. We don't judge, but we don't "
                   "include it with the 66 books that are not disputed. We show it honestly and "
                   "historically framed. Let the user discern."),
        principle=("The engine SHOWS the canon landscape — which tradition holds which books, and "
                   "the history — but never CROWNS a canon. Which books are Scripture is the "
                   "church's discernment under the Spirit, not a verdict a verifier renders. "
                   "Conduit not source; points to Christ, not an idol."),
        realization=("The undisputed 66 stay the validated core; disputed books (Catholic "
                     "deuterocanon, Eastern Orthodox additions, Ethiopian Tewahedo distinctives) "
                     "live on a SEPARATE layer, historically framed, never merged into the 66 and "
                     "never falsely rejected. The canons nest concentrically: 66 core inside "
                     "Catholic inside Orthodox inside Ethiopian."),
        result=("Built canon.py + a canon-aware scripture verifier (live). Enumerations flagged "
                "where genuinely debated (Ethiopian ~81/~88); Ethiopian credited for the "
                "deuterocanon, not over-claimed for debated Orthodox-only Greek books."),
        status="confirmed",
        refs=["src/concordance_engine/canon.py", "src/concordance_engine/verifiers/scripture.py"],
    ),
    dict(
        tid="branches_and_complementary_pairing",
        directive="branches  /  72 most likely interact in 36 pairs ... like complimentary colors. Not same/similar.",
        principle=("The map is fractal: domains nest into subdomains (branches) along scale. And "
                   "domains pair by COMPLEMENTARITY — opposite, completing each other toward the "
                   "whole — not by similarity. Relation (ratio) binds distinct parts; sameness "
                   "does not."),
        realization=("Nesting the over-split facets as branches dropped domain collisions 10->6 "
                     "groups. Complementary pairing of the 72 (coverage toward all 11 dims) beat a "
                     "random matching by z=7.2 (avg 7.25/11); a similarity pairing found only 13 "
                     "weak pairs. The complement gaps named real thinness, not a missing axis."),
        result=("UMBRELLAS extended; the shape is one shared core + branches, related by ratio, "
                "from one Source — the same shape as the canon (core + traditions)."),
        status="tested",
        refs=["src/concordance_engine/grid.py"],
    ),
]


def main():
    before = len(teachings.listing().get("teachings", []))
    for t in TEACHINGS:
        rec = teachings.record(**t)
        print("recorded:", rec.get("id"), "status:", rec.get("status"))
    after = len(teachings.listing().get("teachings", []))
    print(f"teachings store: {before} -> {after}")


if __name__ == "__main__":
    main()
