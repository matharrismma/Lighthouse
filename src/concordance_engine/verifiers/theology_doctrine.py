"""Theology / Christian doctrine verifier.

Deterministic checks against claims that are directly verifiable from the
literal text of Scripture (KJV / ESV equivalents) and classical orthodox
Christian doctrine. Disputed passages are NOT interpreted here — only
claims that are plainly and repeatedly attested in public-domain biblical text.

Doctrinal hierarchy honoured:
    1. Jesus' words (primary)
    2. Bible / Scripture (secondary)
    3. Apostles + recognized elders (thereafter)

IMPORTANT: This verifier checks structural doctrinal completeness against
public-domain Scripture. It does not render theological opinions on disputed
interpretations or denominational distinctives.

THEOL_VERIFY packet shape (any subset of fields):
    {
      # gospel core facts (1 Cor 15:3-4)
      "claimed_died_for_sins": true, "claimed_was_buried": true,
      "claimed_rose_third_day": true, "claimed_gospel_complete": true,

      # Trinitarian formula (Nicene Creed)
      "persons_named": ["Father", "Son", "Holy Spirit"],
      "claimed_trinitarian_complete": true,

      # salvation mechanism (Eph 2:8-9)
      "claimed_salvation_mechanism": "grace_through_faith",
      "claimed_excludes_works": true,

      # bodily resurrection (Luke 24:39, John 20:27)
      "claimed_resurrection_type": "bodily",
      "claimed_is_bodily": true,

      # creation ex nihilo (Gen 1:1, Heb 11:3)
      "claimed_creation_from_preexisting_matter": false,
      "claimed_ex_nihilo": true,
    }

Grid axes: authority/trust (Scripture as canonical source),
           information/encoding (doctrinal claim encoding).
"""
from __future__ import annotations
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


# ---------------------------------------------------------------------------
# theology_doctrine.gospel_core_facts
# ---------------------------------------------------------------------------

_GOSPEL_CORE_ANCHOR = {
    "ref": "1 Cor 15:3-4",
    "layer": "bible",
    "text_KJV": (
        "'For I delivered unto you first of all that which I also received, "
        "how that Christ died for our sins according to the scriptures; "
        "And that he was buried, and that he rose again the third day "
        "according to the scriptures.' — 1 Corinthians 15:3-4 (KJV)"
    ),
}

_GOSPEL_RULE = (
    "The gospel (1 Cor 15:3-4) requires three facts: (1) Christ died for our sins, "
    "(2) he was buried, (3) he rose on the third day. All three must be present for "
    "the gospel to be complete. Missing any one is an incomplete gospel (Gal 1:8)."
)


def verify_gospel_core_facts(spec: Dict[str, Any]) -> VerifierResult:
    """1 Cor 15:3-4: the gospel requires three facts — died, buried, rose third day."""
    name = "theology_doctrine.gospel_core_facts"
    died      = spec.get("claimed_died_for_sins")
    buried    = spec.get("claimed_was_buried")
    rose      = spec.get("claimed_rose_third_day")
    claimed   = spec.get("claimed_gospel_complete")
    if died is None or buried is None or rose is None or claimed is None:
        return na(name)
    d, b, r = bool(died), bool(buried), bool(rose)
    actual_complete = d and b and r
    missing = []
    if not d: missing.append("died_for_sins")
    if not b: missing.append("was_buried")
    if not r: missing.append("rose_third_day")
    data = {
        "rule": _GOSPEL_RULE,
        "anchor": _GOSPEL_CORE_ANCHOR,
        "claimed_died_for_sins": d,
        "claimed_was_buried": b,
        "claimed_rose_third_day": r,
        "actual_complete": actual_complete,
        "claimed_gospel_complete": bool(claimed),
        "missing_facts": missing,
    }
    if actual_complete == bool(claimed):
        detail = ("all three gospel facts present (1 Cor 15:3-4)"
                  if actual_complete
                  else f"gospel incomplete — missing: {missing}")
        return confirm(name, detail, data)
    if actual_complete and not bool(claimed):
        return mismatch(name,
                        "all three facts present but claimed_gospel_complete=False", data)
    return mismatch(name,
                    f"claimed complete but missing facts: {missing}", data)


# ---------------------------------------------------------------------------
# theology_doctrine.trinitarian_formula
# ---------------------------------------------------------------------------

_TRINITARIAN_ANCHOR = {
    "ref": "Mt 28:19; Nicene Creed (325 AD)",
    "layer": "bible",
    "text_KJV": (
        "'Go ye therefore, and teach all nations, baptizing them in the name "
        "of the Father, and of the Son, and of the Holy Ghost.' — Matthew 28:19 (KJV)"
    ),
}

_TRINITARIAN_RULE = (
    "Classical Trinitarian formula (Nicene, 325 AD): one God in three co-equal, "
    "co-eternal persons — Father, Son, and Holy Spirit (or Holy Ghost). All three "
    "persons must be named. Source: public-domain ecumenical council text and Scripture."
)

# Each set is a group of acceptable case-insensitive strings for that person.
_TRINITARIAN_PERSONS = [
    {"father"},
    {"son"},
    {"holy spirit", "holy ghost"},
]
_PERSON_LABELS = ["Father", "Son", "Holy Spirit/Ghost"]


def _persons_present(persons_named: List[str]) -> List[bool]:
    normalised = [p.lower().strip() for p in persons_named]
    return [any(alias in normalised for alias in aliases)
            for aliases in _TRINITARIAN_PERSONS]


def verify_trinitarian_formula(spec: Dict[str, Any]) -> VerifierResult:
    """All three persons (Father, Son, Holy Spirit) must be named."""
    name = "theology_doctrine.trinitarian_formula"
    persons_raw = spec.get("persons_named")
    claimed     = spec.get("claimed_trinitarian_complete")
    if persons_raw is None or claimed is None:
        return na(name)
    if not isinstance(persons_raw, list):
        return error(name, "persons_named must be a list of strings")
    persons: List[str] = [str(p) for p in persons_raw]
    presence = _persons_present(persons)
    missing  = [label for label, found in zip(_PERSON_LABELS, presence) if not found]
    actual_complete = all(presence)
    data = {
        "rule": _TRINITARIAN_RULE,
        "anchor": _TRINITARIAN_ANCHOR,
        "persons_named": persons,
        "person_presence": dict(zip(_PERSON_LABELS, presence)),
        "missing_persons": missing,
        "actual_complete": actual_complete,
        "claimed_trinitarian_complete": bool(claimed),
    }
    if actual_complete == bool(claimed):
        detail = ("all three Trinitarian persons present"
                  if actual_complete
                  else f"Trinitarian formula incomplete — missing: {missing}")
        return confirm(name, detail, data)
    if actual_complete and not bool(claimed):
        return mismatch(name,
                        "all three persons present but claimed_trinitarian_complete=False", data)
    return mismatch(name,
                    f"claimed complete but missing persons: {missing}", data)


# ---------------------------------------------------------------------------
# theology_doctrine.salvation_by_grace
# ---------------------------------------------------------------------------

_SALVATION_ANCHOR = {
    "ref": "Eph 2:8-9",
    "layer": "bible",
    "text_KJV": (
        "'For by grace are ye saved through faith; and that not of yourselves: "
        "it is the gift of God: Not of works, lest any man should boast.' "
        "— Ephesians 2:8-9 (KJV)"
    ),
}

_SALVATION_RULE = (
    "Eph 2:8-9: salvation is by grace through faith, not works. Mechanisms that "
    "exclude works: 'grace', 'faith', 'grace_through_faith'. Mechanisms that include "
    "works are discordant with the plain text of Ephesians 2:8-9."
)

_GRACE_MECHANISMS = frozenset(["grace", "faith", "grace_through_faith"])


def verify_salvation_by_grace(spec: Dict[str, Any]) -> VerifierResult:
    """Eph 2:8-9: salvation mechanism must be grace-based, not works-based."""
    name = "theology_doctrine.salvation_by_grace"
    mechanism   = spec.get("claimed_salvation_mechanism")
    excl_works  = spec.get("claimed_excludes_works")
    if mechanism is None or excl_works is None:
        return na(name)
    mech_str = str(mechanism).lower().strip()
    actual_excludes_works = mech_str in _GRACE_MECHANISMS
    data = {
        "rule": _SALVATION_RULE,
        "anchor": _SALVATION_ANCHOR,
        "claimed_salvation_mechanism": mech_str,
        "grace_mechanisms": sorted(_GRACE_MECHANISMS),
        "actual_excludes_works": actual_excludes_works,
        "claimed_excludes_works": bool(excl_works),
    }
    if actual_excludes_works == bool(excl_works):
        detail = (f"mechanism={mech_str!r} is grace-based (Eph 2:8-9)"
                  if actual_excludes_works
                  else f"mechanism={mech_str!r} includes works — discordant with Eph 2:8-9")
        return confirm(name, detail, data)
    if actual_excludes_works and not bool(excl_works):
        return mismatch(name,
                        f"mechanism={mech_str!r} excludes works but claimed_excludes_works=False",
                        data)
    return mismatch(name,
                    f"mechanism={mech_str!r} does not exclude works, "
                    f"but claimed_excludes_works=True",
                    data)


# ---------------------------------------------------------------------------
# theology_doctrine.bodily_resurrection
# ---------------------------------------------------------------------------

_RESURRECTION_ANCHOR = {
    "ref": "Luke 24:39; John 20:27",
    "layer": "jesus_words",
    "text_KJV": (
        "'Behold my hands and my feet, that it is I myself: handle me, and see; "
        "for a spirit hath not flesh and bones, as ye see me have.' — Luke 24:39 (KJV)"
    ),
}

_RESURRECTION_RULE = (
    "The resurrection of Christ was bodily, not merely spiritual or symbolic. "
    "Jesus invited Thomas to touch his physical wounds (John 20:27) and declared "
    "his flesh and bones to the disciples (Luke 24:39). "
    "claimed_resurrection_type must equal 'bodily' for claimed_is_bodily to confirm."
)


def verify_bodily_resurrection(spec: Dict[str, Any]) -> VerifierResult:
    """The resurrection must be claimed as bodily (Luke 24:39, John 20:27)."""
    name = "theology_doctrine.bodily_resurrection"
    res_type = spec.get("claimed_resurrection_type")
    claimed  = spec.get("claimed_is_bodily")
    if res_type is None or claimed is None:
        return na(name)
    rt = str(res_type).lower().strip()
    actual_is_bodily = (rt == "bodily")
    data = {
        "rule": _RESURRECTION_RULE,
        "anchor": _RESURRECTION_ANCHOR,
        "claimed_resurrection_type": rt,
        "actual_is_bodily": actual_is_bodily,
        "claimed_is_bodily": bool(claimed),
    }
    if actual_is_bodily == bool(claimed):
        detail = (f"resurrection type={rt!r} is bodily (Luke 24:39, John 20:27)"
                  if actual_is_bodily
                  else f"resurrection type={rt!r} is not bodily")
        return confirm(name, detail, data)
    if actual_is_bodily and not bool(claimed):
        return mismatch(name,
                        f"type={rt!r} is 'bodily' but claimed_is_bodily=False", data)
    return mismatch(name,
                    f"claimed bodily but type={rt!r} is not 'bodily'", data)


# ---------------------------------------------------------------------------
# theology_doctrine.creation_ex_nihilo
# ---------------------------------------------------------------------------

_EX_NIHILO_ANCHOR = {
    "ref": "Gen 1:1; Heb 11:3",
    "layer": "bible",
    "text_KJV": (
        "'Through faith we understand that the worlds were framed by the word "
        "of God, so that things which are seen were not made of things which do "
        "appear.' — Hebrews 11:3 (KJV)"
    ),
}

_EX_NIHILO_RULE = (
    "Gen 1:1 and Heb 11:3 attest that God created the universe from nothing "
    "(ex nihilo), not from pre-existing matter. "
    "actual_ex_nihilo = not claimed_creation_from_preexisting_matter. "
    "claimed_ex_nihilo must agree with that derivation."
)


def verify_creation_ex_nihilo(spec: Dict[str, Any]) -> VerifierResult:
    """Gen 1:1 / Heb 11:3: creation was from nothing, not pre-existing matter."""
    name = "theology_doctrine.creation_ex_nihilo"
    from_preexisting = spec.get("claimed_creation_from_preexisting_matter")
    claimed_nihilo   = spec.get("claimed_ex_nihilo")
    if from_preexisting is None or claimed_nihilo is None:
        return na(name)
    fp = bool(from_preexisting)
    cn = bool(claimed_nihilo)
    actual_ex_nihilo = not fp
    data = {
        "rule": _EX_NIHILO_RULE,
        "anchor": _EX_NIHILO_ANCHOR,
        "claimed_creation_from_preexisting_matter": fp,
        "actual_ex_nihilo": actual_ex_nihilo,
        "claimed_ex_nihilo": cn,
    }
    if actual_ex_nihilo == cn:
        detail = ("creation ex nihilo confirmed (Gen 1:1, Heb 11:3)"
                  if actual_ex_nihilo
                  else "claimed creation from pre-existing matter (not ex nihilo)")
        return confirm(name, detail, data)
    if actual_ex_nihilo and not cn:
        return mismatch(name,
                        "no pre-existing matter claimed, so creation is ex nihilo, "
                        "but claimed_ex_nihilo=False",
                        data)
    return mismatch(name,
                    "claimed ex nihilo but claimed_creation_from_preexisting_matter=True — "
                    "contradictory inputs",
                    data)


# ---------------------------------------------------------------------------
# run()
# ---------------------------------------------------------------------------

def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    tv = packet.get("THEOL_VERIFY") or {}

    gospel_fields = ("claimed_died_for_sins", "claimed_was_buried",
                     "claimed_rose_third_day", "claimed_gospel_complete")
    if all(f in tv for f in gospel_fields):
        results.append(verify_gospel_core_facts(tv))

    if "persons_named" in tv and "claimed_trinitarian_complete" in tv:
        results.append(verify_trinitarian_formula(tv))

    if "claimed_salvation_mechanism" in tv and "claimed_excludes_works" in tv:
        results.append(verify_salvation_by_grace(tv))

    if "claimed_resurrection_type" in tv and "claimed_is_bodily" in tv:
        results.append(verify_bodily_resurrection(tv))

    if ("claimed_creation_from_preexisting_matter" in tv
            and "claimed_ex_nihilo" in tv):
        results.append(verify_creation_ex_nihilo(tv))

    if not results:
        results.append(na("theology_doctrine", "no THEOL_VERIFY artifacts present"))
    return results
