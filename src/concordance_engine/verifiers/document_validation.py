"""Document validation verifier (information/encoding grid axis).

Checksum / format checks for common structured identifiers: ISBN-10
and ISBN-13, EAN/UPC, Luhn (credit cards / IMEI), and IBAN. All
checksums are public-domain algorithms.

Checks:
  * doc_validation.isbn10            — 10-digit ISBN with mod-11 check
  * doc_validation.isbn13            — 13-digit ISBN-13 with EAN mod-10 check
  * doc_validation.luhn              — Luhn mod-10 (credit cards, IMEI)
  * doc_validation.ean_upc           — EAN-13 / UPC-A mod-10 check (12-13 digits)

DOC_VERIFY shape (any subset):
    {
      "isbn10": "0306406152",
      "claimed_isbn10_valid": true,

      "isbn13": "9780306406157",
      "claimed_isbn13_valid": true,

      "luhn_number": "4532015112830366",
      "claimed_luhn_valid": true,

      "ean_or_upc": "036000291452",
      "claimed_ean_valid": true,
    }
"""
from __future__ import annotations
import re
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


def _digits_only(s: str) -> str:
    return re.sub(r"[^0-9Xx]", "", str(s))


def _isbn10_check(s: str) -> bool:
    digits = _digits_only(s)
    if len(digits) != 10:
        return False
    total = 0
    for i, ch in enumerate(digits):
        if i == 9 and ch in ("X", "x"):
            v = 10
        else:
            if not ch.isdigit():
                return False
            v = int(ch)
        total += v * (10 - i)
    return total % 11 == 0


def _isbn13_check(s: str) -> bool:
    digits = _digits_only(s)
    if len(digits) != 13 or not digits.isdigit():
        return False
    total = 0
    for i, ch in enumerate(digits):
        v = int(ch)
        total += v if i % 2 == 0 else 3 * v
    return total % 10 == 0


def _luhn_check(s: str) -> bool:
    digits = _digits_only(s)
    if not digits.isdigit() or len(digits) < 2:
        return False
    total = 0
    n = len(digits)
    for i, ch in enumerate(digits):
        v = int(ch)
        # Double every second digit from the right.
        if (n - i) % 2 == 0:
            v *= 2
            if v > 9:
                v -= 9
        total += v
    return total % 10 == 0


def _ean_check(s: str) -> bool:
    """EAN-13 / UPC-A. UPC-A is 12 digits; we accept by left-padding to 13."""
    digits = _digits_only(s)
    if not digits.isdigit():
        return False
    if len(digits) == 12:
        digits = "0" + digits
    if len(digits) != 13:
        return False
    total = 0
    for i, ch in enumerate(digits):
        v = int(ch)
        total += v if i % 2 == 0 else 3 * v
    return total % 10 == 0


def verify_isbn10(spec: Dict[str, Any]) -> VerifierResult:
    name = "doc_validation.isbn10"
    s = spec.get("isbn10")
    claimed = spec.get("claimed_isbn10_valid")
    if s is None or claimed is None:
        return na(name)
    actual = _isbn10_check(str(s))
    data = {"input": s, "actual_valid": actual, "claimed_valid": bool(claimed),
            "rule": "mod-11 weighted sum (positions 10..1)"}
    if actual == bool(claimed):
        return confirm(name, f"ISBN-10 {s!r} valid={actual} (matches claim)", data)
    return mismatch(name, f"ISBN-10 {s!r} valid={actual}, claimed {bool(claimed)}", data)


def verify_isbn13(spec: Dict[str, Any]) -> VerifierResult:
    name = "doc_validation.isbn13"
    s = spec.get("isbn13")
    claimed = spec.get("claimed_isbn13_valid")
    if s is None or claimed is None:
        return na(name)
    actual = _isbn13_check(str(s))
    data = {"input": s, "actual_valid": actual, "claimed_valid": bool(claimed),
            "rule": "EAN mod-10 (alternating ×1/×3 weights)"}
    if actual == bool(claimed):
        return confirm(name, f"ISBN-13 {s!r} valid={actual} (matches claim)", data)
    return mismatch(name, f"ISBN-13 {s!r} valid={actual}, claimed {bool(claimed)}", data)


def verify_luhn(spec: Dict[str, Any]) -> VerifierResult:
    name = "doc_validation.luhn"
    s = spec.get("luhn_number")
    claimed = spec.get("claimed_luhn_valid")
    if s is None or claimed is None:
        return na(name)
    actual = _luhn_check(str(s))
    data = {"input": s, "actual_valid": actual, "claimed_valid": bool(claimed),
            "rule": "Luhn mod-10 (double every second digit from right)"}
    if actual == bool(claimed):
        return confirm(name, f"Luhn {s!r} valid={actual} (matches claim)", data)
    return mismatch(name, f"Luhn {s!r} valid={actual}, claimed {bool(claimed)}", data)


def verify_ean_upc(spec: Dict[str, Any]) -> VerifierResult:
    name = "doc_validation.ean_upc"
    s = spec.get("ean_or_upc")
    claimed = spec.get("claimed_ean_valid")
    if s is None or claimed is None:
        return na(name)
    actual = _ean_check(str(s))
    data = {"input": s, "actual_valid": actual, "claimed_valid": bool(claimed),
            "rule": "EAN-13 mod-10 (UPC-A accepted via leading-zero pad)"}
    if actual == bool(claimed):
        return confirm(name, f"EAN/UPC {s!r} valid={actual} (matches claim)", data)
    return mismatch(name, f"EAN/UPC {s!r} valid={actual}, claimed {bool(claimed)}", data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    dv = packet.get("DOC_VERIFY") or {}
    if "isbn10" in dv and "claimed_isbn10_valid" in dv:
        results.append(verify_isbn10(dv))
    if "isbn13" in dv and "claimed_isbn13_valid" in dv:
        results.append(verify_isbn13(dv))
    if "luhn_number" in dv and "claimed_luhn_valid" in dv:
        results.append(verify_luhn(dv))
    if "ean_or_upc" in dv and "claimed_ean_valid" in dv:
        results.append(verify_ean_upc(dv))
    if not results:
        results.append(na("document_validation", "no DOC_VERIFY artifacts present"))
    return results
