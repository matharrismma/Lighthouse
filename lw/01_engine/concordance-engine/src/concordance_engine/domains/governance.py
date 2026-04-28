"""Governance domain validator — keyword/concept constraint library.

Unlike the academic domain validators which check structured packet fields,
this validator scans plain-text decision descriptions against a library of
RED and FLOOR constraints with scripture citations.

This is the validator that handles the 50 eval examples (governance,
business, household, education, church domains).

Limitations (be honest about these):
    * Keyword scanning is triage, not decision authority. It misses paraphrase
      and gets fooled by adversarial input.
    * The negation pass below catches the simplest false positives
      ("we will not exploit anyone", "no fabrication permitted"). It does
      not handle distant negation, double negatives, quoted-but-rejected
      content, or sarcasm.
    * For high-stakes use (e.g. JDA decisions) the one-page paper protocol
      from the_mechanism.pdf is stronger because a human reader does not
      fall for the failure modes a substring scanner falls for.
    * Treat REJECT verdicts as "stop and look", PASS verdicts as "no
      tripwire fired", not as "approved".
"""
from __future__ import annotations
from typing import Any, Dict, List
from ..gates import reject, quarantine, ok
from ..packet import GateResult

RED_CONSTRAINTS = [
    {"id": "RED-001", "name": "No deception",
     "keywords": ["fabricat","fake","pretend","deceiv","mislead","falsif","lying","fraud","forge","counterfeit","impersonat"],
     "citation": "Prov 12:22; Matt 5:37"},
    {"id": "RED-002", "name": "No coercion",
     "keywords": ["forced","compelled","coerce","mandatory surveillance","no choice","must comply","punish refusal","threaten"],
     "citation": "1 Pet 5:2-3; Philemon 1:14"},
    {"id": "RED-003", "name": "No exploitation",
     "keywords": ["exploit","predatory","captive audience","no alternative","usury","trapped","indentured"],
     "citation": "Prov 22:16; Jas 5:4; Lev 25:36"},
    {"id": "RED-004", "name": "No injustice",
     "keywords": ["unequal","favoritism","double standard","rigged","discriminat","unjust"],
     "citation": "Prov 11:1; Lev 19:15"},
    {"id": "RED-005", "name": "No identity branding",
     "keywords": ["branded","labeled","marked","badge of shame","mandatory tracking","social credit","identity mark"],
     "citation": "Gen 1:27; Rev 13:16-17"},
    {"id": "RED-006", "name": "No harm to children",
     "keywords": ["humiliat","shame children","child labor","endanger children","expose children"],
     "citation": "Matt 18:6; Eph 6:4"},
    {"id": "RED-007", "name": "No suppression of accountability",
     "keywords": ["hide financial","suppress report","no audit","trust without verify","questions are divisive","stop publishing","conceal"],
     "citation": "2 Cor 8:21; Prov 28:13"},
    {"id": "RED-008", "name": "No self-referential authority",
     "keywords": ["self-validat","self-referent","we are the authority","no appeal","absolute power","unquestionable"],
     "citation": "Exod 20:3; Acts 5:29"},
]

FLOOR_CONSTRAINTS = [
    {"id": "FLOOR-001", "name": "Proportionality",
     "keywords": ["blanket","all employees","everyone must","zero tolerance","every intersection","universal mandate","no exceptions"],
     "citation": "Prov 11:1; Mic 6:8", "severity": "warn"},
    {"id": "FLOOR-002", "name": "Due process",
     "keywords": ["no appeal","immediate termination","no hearing","summary judgment","without review"],
     "citation": "Deut 1:16-17; Prov 18:17", "severity": "warn"},
    {"id": "FLOOR-003", "name": "Transparency",
     "keywords": ["secret","behind closed doors","undisclosed","confidential criteria","hidden algorithm"],
     "citation": "2 Cor 8:21; John 3:20-21", "severity": "warn"},
    {"id": "FLOOR-004", "name": "Financial stability floor",
     "keywords": ["all-in","bet everything","drain reserves","no emergency fund","leverage everything"],
     "citation": "Prov 21:20; Gen 41:34-36", "severity": "error"},
    {"id": "FLOOR-005", "name": "Retention bounds",
     "keywords": ["retain indefinitely","permanent record","5 year","10 year","lifetime tracking","all data"],
     "citation": "Prov 11:1; Eccl 3:1", "severity": "warn"},
]

# Domains that use text-based governance scanning
GOVERNANCE_DOMAINS = {"governance", "business", "household", "education", "church"}


# Negation cues that, when they appear within NEG_WINDOW words before a
# forbidden keyword, suppress the match. This removes the most common false
# positives ("we will not exploit anyone", "no fabrication permitted") without
# pretending to be a robust NLP layer. Treat the scanner as triage, not as a
# semantic decision authority.
NEGATION_CUES = (
    "not", "no", "never", "without", "avoid", "avoids", "avoiding",
    "prohibit", "prohibits", "prohibited", "forbid", "forbids", "forbidden",
    "ban", "bans", "banned", "reject", "rejects", "rejected",
    "disallow", "disallows", "disallowed", "refuse", "refuses", "refused",
    "cannot", "can't", "won't", "shouldn't", "must not", "do not", "does not",
    "no one", "nobody", "none",
)
NEG_WINDOW = 5  # words


def _is_negated(text_lower: str, kw_index: int) -> bool:
    """Return True if a negation cue appears within NEG_WINDOW words before kw_index."""
    prefix = text_lower[:kw_index]
    # take the last NEG_WINDOW whitespace-separated tokens (plus a small slack)
    tail_tokens = prefix.split()[-NEG_WINDOW:]
    if not tail_tokens:
        return False
    tail = " ".join(tail_tokens)
    return any(cue in tail for cue in NEGATION_CUES)


def _scan(text: str, constraints: list) -> tuple[list, list]:
    """Scan text for keyword matches with simple negation suppression.
    Returns (errors, warnings).
    """
    text_lower = text.lower()
    errs, warns = [], []
    for c in constraints:
        hit = False
        for kw in c["keywords"]:
            idx = text_lower.find(kw)
            while idx != -1:
                if not _is_negated(text_lower, idx):
                    hit = True
                    break
                idx = text_lower.find(kw, idx + 1)
            if hit:
                break
        if hit:
            entry = f"{c['id']} {c['name']} ({c['citation']})"
            if c.get("severity") == "warn":
                warns.append(entry)
            else:
                errs.append(entry)
    return errs, warns


class GovernanceValidator:
    domain = "governance"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        text = packet.get("text", packet.get("description", ""))
        if not text:
            # Try to build text from claims
            claims = packet.get("claims", [])
            if isinstance(claims, list):
                text = " ".join(
                    c.get("subject", "") + " " + c.get("predicate", "")
                    if isinstance(c, dict) else str(c)
                    for c in claims
                )

        if not text:
            return [ok("RED", {"note": "no text to scan"})]

        errors, _ = _scan(text, RED_CONSTRAINTS)
        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        text = packet.get("text", packet.get("description", ""))
        if not text:
            claims = packet.get("claims", [])
            if isinstance(claims, list):
                text = " ".join(
                    c.get("subject", "") + " " + c.get("predicate", "")
                    if isinstance(c, dict) else str(c)
                    for c in claims
                )

        if not text:
            return [ok("FLOOR", {"note": "no text to scan"})]

        errors, warnings = _scan(text, FLOOR_CONSTRAINTS)
        if errors:
            return [reject("FLOOR", *errors)]
        # Warnings don't halt, but we note them
        if warnings:
            return [ok("FLOOR", {"warnings": warnings})]
        return [ok("FLOOR")]
