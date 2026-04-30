"""
triangulation/drift_check.py — Interpretation drift detector

Triangulation: a claim about a scripture verse must survive alignment
at all three layers:
  1. WEB text    — what the locked English says
  2. Strong's    — what the original language word means
  3. Claim       — what is being asserted

If a claim is consistent with (1) and (2), it passes.
If a claim requires reading the verse in a way the original word's
semantic range does not support, it is flagged as DRIFT.

Usage:
    python -m triangulation.drift_check --ref Jn3:16 --claim "God loves the world"
    python -m triangulation.drift_check --ref Jn15:2 --claim "branches that don't bear fruit are destroyed"

    # Or from Python:
    from triangulation.drift_check import DriftChecker
    dc = DriftChecker()
    result = dc.check("Jn15:2", "branches that don't bear fruit are destroyed")
"""

from __future__ import annotations

import argparse
import json
from typing import Optional

from .lookup import SourceLayer, _parse_ref, BOOK_NAMES, BOOK_MAP


class DriftChecker:
    """
    Checks whether an interpretation claim about a scripture verse
    is consistent with the original language text.

    The triangulation principle:
        A claim survives if it does not require the key original-language
        words to mean something outside their attested semantic range.

    Current implementation:
        - Fetches the WEB text for the verse
        - Fetches Strong's definitions for any Strong's numbers mentioned
          in the claim OR in an explicit strongs_keys parameter
        - Returns a structured report the caller can inspect

    Note: Full automated drift detection requires the morphologically-tagged
    original language texts (morphhb / MorphGNT) to map verse → word → Strong's.
    Until those are fetched, the caller supplies strongs_keys manually or
    the check reports as NEEDS_MANUAL_VERIFICATION with the source texts
    available for human review.
    """

    def __init__(self):
        self.src = SourceLayer()

    def check(
        self,
        ref: str,
        claim: str,
        strongs_keys: Optional[list[str]] = None,
    ) -> dict:
        """
        Check whether `claim` about verse `ref` is consistent with the
        original language meaning.

        Args:
            ref:          Scripture ref string, e.g. "Jn15:2"
            claim:        The interpretation being checked
            strongs_keys: Optional list of Strong's numbers for key terms,
                          e.g. ["G142"] for the word airo (take away / lift up)
                          If not supplied, returns WEB text + prompts manual review.

        Returns a dict with:
            status:   "PASS" | "DRIFT_FLAGGED" | "NEEDS_MANUAL_VERIFICATION"
            ref:      canonical ref string
            web_text: WEB text for the verse
            claim:    the claim being checked
            analysis: per-word analysis if strongs_keys were supplied
            verdict:  human-readable summary
        """
        verse = self.src.lookup(ref)

        if verse["status"] != "ok":
            return {
                "status": "ERROR",
                "ref": ref,
                "claim": claim,
                "detail": verse.get("detail", verse.get("status")),
            }

        result = {
            "ref": ref,
            "book": verse["book"],
            "chapter": verse["chapter"],
            "verse_num": verse["verse"],
            "testament": verse["testament"],
            "web_text": verse["web_text"],
            "claim": claim,
            "layer": "triangulation",
        }

        if not strongs_keys:
            result["status"] = "NEEDS_MANUAL_VERIFICATION"
            result["verdict"] = (
                f"WEB text retrieved. To complete triangulation, supply the "
                f"Strong's numbers for the key terms in this verse via strongs_keys=[]. "
                f"Example: dc.check('{ref}', claim, strongs_keys=['G142']). "
                f"Use lookup.py --word G### to find and study specific words."
            )
            result["next_step"] = (
                f"1. Read the WEB text above.\n"
                f"2. Identify the key word(s) in dispute.\n"
                f"3. Look up their Strong's numbers in a concordance.\n"
                f"4. Run: python -m triangulation.lookup --word G### (or H###)\n"
                f"5. Re-run this check with strongs_keys=['G###'] to complete triangulation."
            )
            return result

        # Analyze each supplied Strong's key
        analysis = []
        drift_detected = False
        for skey in strongs_keys:
            word_data = self.src.lookup_strongs(skey)
            if word_data.get("status") != "ok":
                analysis.append({
                    "strongs": skey,
                    "status": "lookup_failed",
                    "detail": word_data.get("detail", "not found"),
                })
                continue

            analysis.append({
                "strongs": skey,
                "word": word_data.get("word", ""),
                "transliteration": word_data.get("transliteration", ""),
                "definition": word_data.get("definition", ""),
                "derivation": word_data.get("derivation", ""),
                "status": "ok",
                "instruction": (
                    f"Verify: does the claim ('{claim}') require {skey} "
                    f"({word_data.get('word', '')}) to mean something outside "
                    f"its attested definition above? If yes → DRIFT."
                ),
            })

        result["strongs_analysis"] = analysis

        # Automated verdict is only possible when morphological tagging is present.
        # Until then, return the assembled data for human review.
        result["status"] = "NEEDS_HUMAN_REVIEW"
        result["verdict"] = (
            f"Strong's data retrieved for {strongs_keys}. "
            f"Human review required: compare the claim against the word definitions above. "
            f"If the claim requires a meaning outside the attested definition, flag as DRIFT."
        )
        result["automated_drift_detection"] = {
            "available": False,
            "requires": "Morphologically-tagged original language texts (morphhb / MorphGNT). "
                        "Run: git clone https://github.com/openscriptures/morphhb original/hebrew "
                        "and git clone https://github.com/morphgnt/sblgnt original/greek "
                        "to enable automated verse → word → Strong's mapping.",
        }

        return result

    def batch_check(self, checks: list[dict]) -> list[dict]:
        """
        Run multiple checks at once.

        Each check is a dict: {ref, claim, strongs_keys (optional)}
        """
        return [
            self.check(
                c["ref"],
                c["claim"],
                c.get("strongs_keys"),
            )
            for c in checks
        ]


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Triangulation drift checker — verify interpretation against original language"
    )
    parser.add_argument("--ref", required=True, help="Scripture reference, e.g. Jn15:2")
    parser.add_argument("--claim", required=True, help="The interpretation claim to check")
    parser.add_argument(
        "--strongs", nargs="*",
        help="Strong's numbers for key terms, e.g. --strongs G142 G4160"
    )
    args = parser.parse_args()

    dc = DriftChecker()
    result = dc.check(args.ref, args.claim, strongs_keys=args.strongs)
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
