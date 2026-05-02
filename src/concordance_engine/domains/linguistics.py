"""Linguistics domain validator — RED/FLOOR checks for the LING_VERIFY shape.

Most linguistics checks are *verification* (does the claim match the lexicon?)
rather than *attestation* (did the author affirm a constraint?), so RED here
focuses on packet well-formedness — every Strong's identifier referenced in
the packet must be a syntactically valid 'G####' or 'H####' code. The actual
lexicon-resolution check lives in `verifiers/linguistics.py` and runs at RED
verification time.

FLOOR enforces structural minimums: the packet either declares a LING_VERIFY
block with at least one verifiable claim, or attaches a list of citations
that connect the claim back to a Strong's-tagged source.
"""
from __future__ import annotations
import re
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


_STRONGS_PATTERN = re.compile(r"^[GHgh]\d+$")


def _is_valid_strongs(s: Any) -> bool:
    return bool(s and _STRONGS_PATTERN.match(str(s)))


class LinguisticsValidator:
    domain = "linguistics"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        lv = packet.get("LING_VERIFY") or {}

        if not lv:
            # No artifact — fall back to general-claim shape.
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Linguistics packets must include either LING_VERIFY{} or non-empty claims[]")
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]

        # Validate every Strong's identifier referenced in the block.
        if "strongs" in lv and not _is_valid_strongs(lv["strongs"]):
            errors.append(
                f"strongs={lv['strongs']!r} is not a valid Strong's identifier "
                f"(expected 'G####' Greek NT or 'H####' Hebrew OT)"
            )
        cp = lv.get("cognate_pair")
        if cp is not None:
            if not isinstance(cp, (list, tuple)) or len(cp) != 2:
                errors.append(f"cognate_pair must be a 2-element list, got {cp!r}")
            else:
                for s in cp:
                    if not _is_valid_strongs(s):
                        errors.append(
                            f"cognate_pair member {s!r} is not a valid Strong's identifier"
                        )

        # claimed_count must be a non-negative integer when present.
        cc = lv.get("claimed_count")
        if cc is not None:
            try:
                n = int(cc)
                if n < 0:
                    errors.append(f"claimed_count must be >= 0, got {n}")
            except (TypeError, ValueError):
                errors.append(f"claimed_count must be an integer, got {cc!r}")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        lv = packet.get("LING_VERIFY") or {}

        if lv:
            # Block must contain at least one of the verifiable claim shapes.
            verifiable_keys = (
                "strongs", "claimed_count", "transliteration_claim",
                "gloss_claim", "cognate_pair",
            )
            if not any(k in lv for k in verifiable_keys):
                errors.append(
                    "LING_VERIFY block must contain at least one of: " + ", ".join(verifiable_keys)
                )
            # Paired-field requirement: claimed_count, transliteration_claim,
            # and gloss_claim each need a strongs sibling.
            for paired in ("claimed_count", "transliteration_claim", "gloss_claim"):
                if paired in lv and "strongs" not in lv:
                    errors.append(f"LING_VERIFY.{paired} requires a sibling 'strongs' field")
        else:
            # Without LING_VERIFY, require packet-level artifacts so the claim
            # can be traced back to a Strong's-tagged source.
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Linguistics packets without LING_VERIFY must declare artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
