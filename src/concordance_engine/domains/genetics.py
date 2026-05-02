"""Genetics domain validator — RED/FLOOR checks for the GENETICS_VERIFY shape.

RED: every sequence in the packet must be a valid DNA or RNA string
(only ACGT or ACGU letters). FLOOR: the packet either declares a
GENETICS_VERIFY block with at least one verifiable claim, or attaches
artifacts that connect the claim back to a public-domain reference
(NCBI RefSeq, UCSC, etc.).
"""
from __future__ import annotations
from typing import Any, Dict, List

from ..gates import reject, ok
from ..packet import GateResult


_DNA_BASES = set("ACGTacgt")
_RNA_BASES = set("ACGUacgu")


def _seq_chars_valid(s: Any, rna: bool) -> bool:
    if not s:
        return False
    valid = _RNA_BASES if rna else _DNA_BASES
    return all(c in valid for c in str(s))


class GeneticsValidator:
    domain = "genetics"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        gv = packet.get("GENETICS_VERIFY") or {}

        if not gv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Genetics packets must include either GENETICS_VERIFY{} or non-empty claims[]")
            if errors:
                return [reject("RED", *errors)]
            return [ok("RED")]

        rna = bool(gv.get("rna"))
        # All sequence-bearing fields must be valid DNA (or RNA when rna=True).
        for fld in ("sequence", "claimed_complement", "claimed_reverse_complement", "claimed_protein"):
            val = gv.get(fld)
            if val and not _seq_chars_valid(val, rna=rna and fld != "claimed_protein"):
                # claimed_protein uses single-letter amino acid codes, not bases — skip alphabet check
                if fld == "claimed_protein":
                    if not all(c.upper().isalpha() or c == "*" for c in str(val)):
                        errors.append(f"claimed_protein has invalid characters: {val!r}")
                else:
                    expected = "RNA (ACGU)" if rna else "DNA (ACGT)"
                    errors.append(f"{fld} contains non-{expected} characters: {val!r}")

        if "codon" in gv:
            codon = str(gv["codon"]).upper().strip()
            if len(codon) != 3:
                errors.append(f"codon must be exactly 3 bases, got {codon!r} (len {len(codon)})")
            elif not all(c in _DNA_BASES.union(_RNA_BASES) for c in codon):
                errors.append(f"codon has non-DNA/RNA characters: {codon!r}")

        if "claimed_orf" in gv:
            orf = gv["claimed_orf"]
            if not isinstance(orf, dict) or "start" not in orf or "end" not in orf:
                errors.append(f"claimed_orf must be a dict with start/end, got {orf!r}")
            else:
                try:
                    s = int(orf["start"])
                    e = int(orf["end"])
                    if s < 0 or e <= s:
                        errors.append(f"claimed_orf start/end invalid: start={s}, end={e}")
                except (TypeError, ValueError):
                    errors.append(f"claimed_orf start/end must be integers, got {orf!r}")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        gv = packet.get("GENETICS_VERIFY") or {}

        if gv:
            verifiable_keys = (
                "claimed_complement", "claimed_reverse_complement",
                "claimed_gc_fraction", "claimed_protein",
                "claimed_amino_acid", "claimed_orf",
            )
            if not any(k in gv for k in verifiable_keys):
                errors.append(
                    "GENETICS_VERIFY block must contain at least one of: " + ", ".join(verifiable_keys)
                )
            # Most checks need a sequence sibling.
            sequence_required = ("claimed_complement", "claimed_reverse_complement",
                                 "claimed_gc_fraction", "claimed_protein", "claimed_orf")
            for k in sequence_required:
                if k in gv and "sequence" not in gv:
                    errors.append(f"GENETICS_VERIFY.{k} requires a sibling 'sequence' field")
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                errors.append("Genetics packets without GENETICS_VERIFY must declare artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
