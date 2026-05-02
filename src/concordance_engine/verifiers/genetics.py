"""Genetics verifier.

Deterministic checks against the standard genetic code, base-pairing rules,
and sequence-level invariants. Distinct from the biology verifier (which
covers organism-level phenomena like replicates, dose-response, control
systems): genetics handles molecular-level claims about DNA/RNA/protein
sequences. The standard genetic code is public-domain (NCBI translation
table 1) — fits the public-domain-only ingestion ethic cleanly.

Checks performed:
  * complementarity      — claimed complement matches DNA-base pairing
  * reverse_complement   — claimed reverse complement matches the canonical
  * gc_content           — claimed GC fraction matches the count
  * codon_translation    — claimed amino-acid sequence matches the standard
                           genetic code applied to the supplied DNA/RNA
  * codon_amino_acid     — single codon → claimed amino-acid letter match
  * orf_bounds           — claimed ORF (open reading frame) starts with ATG
                           and ends with a stop codon (TAA/TAG/TGA)

GENETICS_VERIFY packet shape (any subset of fields, all optional):
    {
      "sequence": "ATGGCC...",                          # used by several checks
      "claimed_complement": "...",                      # complementarity
      "claimed_reverse_complement": "...",              # reverse_complement
      "claimed_gc_fraction": 0.55,                      # gc_content
      "claimed_protein": "MAA*",                        # codon_translation
      "rna": false,                                     # if true, treat sequence as RNA
      "codon": "ATG",                                   # codon_amino_acid
      "claimed_amino_acid": "M",                        # codon_amino_acid
      "claimed_orf": {"start": 0, "end": 12},           # orf_bounds (end exclusive)
    }
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional, Tuple

from .base import VerifierResult, na, confirm, mismatch, error


# ── Standard genetic code (NCBI translation table 1) ──────────────────────
# Public domain. Stop codons map to '*'.
_GENETIC_CODE: Dict[str, str] = {
    "TTT": "F", "TTC": "F", "TTA": "L", "TTG": "L",
    "CTT": "L", "CTC": "L", "CTA": "L", "CTG": "L",
    "ATT": "I", "ATC": "I", "ATA": "I", "ATG": "M",
    "GTT": "V", "GTC": "V", "GTA": "V", "GTG": "V",
    "TCT": "S", "TCC": "S", "TCA": "S", "TCG": "S",
    "CCT": "P", "CCC": "P", "CCA": "P", "CCG": "P",
    "ACT": "T", "ACC": "T", "ACA": "T", "ACG": "T",
    "GCT": "A", "GCC": "A", "GCA": "A", "GCG": "A",
    "TAT": "Y", "TAC": "Y", "TAA": "*", "TAG": "*",
    "CAT": "H", "CAC": "H", "CAA": "Q", "CAG": "Q",
    "AAT": "N", "AAC": "N", "AAA": "K", "AAG": "K",
    "GAT": "D", "GAC": "D", "GAA": "E", "GAG": "E",
    "TGT": "C", "TGC": "C", "TGA": "*", "TGG": "W",
    "CGT": "R", "CGC": "R", "CGA": "R", "CGG": "R",
    "AGT": "S", "AGC": "S", "AGA": "R", "AGG": "R",
    "GGT": "G", "GGC": "G", "GGA": "G", "GGG": "G",
}

_DNA_COMPLEMENT = str.maketrans("ACGTacgt", "TGCAtgca")
_RNA_COMPLEMENT = str.maketrans("ACGUacgu", "UGCAugca")
_STOP_CODONS = {"TAA", "TAG", "TGA"}
_DNA_BASES = set("ACGT")
_RNA_BASES = set("ACGU")


def _normalize_seq(s: Any, rna: bool = False) -> str:
    """Uppercase + strip whitespace. If rna=True, also accepts U as a base.
    Caller is expected to validate alphabet via _is_valid_seq."""
    if not s:
        return ""
    return "".join(str(s).upper().split())


def _is_valid_seq(s: str, rna: bool = False) -> bool:
    if not s:
        return False
    valid = _RNA_BASES if rna else _DNA_BASES
    return all(c in valid for c in s)


def _to_dna(s: str) -> str:
    """Convert RNA to DNA (U → T) for codon-table lookup."""
    return s.replace("U", "T").replace("u", "T")


def verify_complementarity(spec: Dict[str, Any]) -> VerifierResult:
    """Claimed complement must be the base-pair complement (NOT reversed).

    ATCG → TAGC. RNA mode swaps U/T pairing. The reverse complement is
    a separate check (verify_reverse_complement).
    """
    name = "genetics.complementarity"
    seq = _normalize_seq(spec.get("sequence"))
    claimed = _normalize_seq(spec.get("claimed_complement"))
    if not seq or not claimed:
        return na(name)
    rna = bool(spec.get("rna"))
    if not _is_valid_seq(seq, rna=rna):
        return error(name, f"sequence has non-{'RNA' if rna else 'DNA'} characters")
    if not _is_valid_seq(claimed, rna=rna):
        return error(name, f"claimed_complement has non-{'RNA' if rna else 'DNA'} characters")
    if len(claimed) != len(seq):
        return mismatch(name,
                        f"length mismatch: sequence={len(seq)}, claimed_complement={len(claimed)}",
                        {"sequence_len": len(seq), "claimed_len": len(claimed)})
    actual = seq.translate(_RNA_COMPLEMENT if rna else _DNA_COMPLEMENT)
    if actual == claimed:
        return confirm(name,
                       f"complement of {seq[:20]}{'…' if len(seq) > 20 else ''} matches claim",
                       {"sequence": seq, "actual": actual})
    return mismatch(name,
                    f"complement mismatch: actual={actual[:60]}, claimed={claimed[:60]}",
                    {"sequence": seq, "actual": actual, "claimed": claimed})


def verify_reverse_complement(spec: Dict[str, Any]) -> VerifierResult:
    """Claimed reverse complement: complement, then reverse. Standard
    operation for finding the antisense strand."""
    name = "genetics.reverse_complement"
    seq = _normalize_seq(spec.get("sequence"))
    claimed = _normalize_seq(spec.get("claimed_reverse_complement"))
    if not seq or not claimed:
        return na(name)
    rna = bool(spec.get("rna"))
    if not _is_valid_seq(seq, rna=rna):
        return error(name, f"sequence has non-{'RNA' if rna else 'DNA'} characters")
    if not _is_valid_seq(claimed, rna=rna):
        return error(name, "claimed_reverse_complement has invalid characters")
    if len(claimed) != len(seq):
        return mismatch(name,
                        f"length mismatch: sequence={len(seq)}, claim={len(claimed)}",
                        {"sequence_len": len(seq), "claimed_len": len(claimed)})
    table = _RNA_COMPLEMENT if rna else _DNA_COMPLEMENT
    actual = seq.translate(table)[::-1]
    if actual == claimed:
        return confirm(name, "reverse complement matches claim",
                       {"sequence": seq, "actual": actual})
    return mismatch(name,
                    f"reverse complement mismatch: actual={actual[:60]}, claimed={claimed[:60]}",
                    {"sequence": seq, "actual": actual, "claimed": claimed})


def verify_gc_content(spec: Dict[str, Any]) -> VerifierResult:
    """Claimed GC fraction within tolerance of the count."""
    name = "genetics.gc_content"
    seq = _normalize_seq(spec.get("sequence"))
    claimed = spec.get("claimed_gc_fraction")
    if not seq or claimed is None:
        return na(name)
    rna = bool(spec.get("rna"))
    if not _is_valid_seq(seq, rna=rna):
        return error(name, f"sequence has non-{'RNA' if rna else 'DNA'} characters")
    try:
        claimed_f = float(claimed)
    except (TypeError, ValueError):
        return error(name, f"claimed_gc_fraction must be numeric, got {claimed!r}")
    if not (0.0 <= claimed_f <= 1.0):
        return mismatch(name, f"claimed_gc_fraction must be in [0, 1], got {claimed_f}",
                        {"claimed": claimed_f})
    gc = sum(1 for c in seq if c in "GCgc")
    actual = gc / len(seq)
    tol = float(spec.get("tolerance", 1e-3))
    if abs(actual - claimed_f) <= tol:
        return confirm(name,
                       f"GC fraction {actual:.4f} matches claim {claimed_f:.4f} (tol {tol})",
                       {"actual": actual, "claimed": claimed_f, "gc_count": gc, "length": len(seq)})
    return mismatch(name,
                    f"GC fraction {actual:.4f} != claim {claimed_f:.4f} (diff {abs(actual-claimed_f):.4f} > tol {tol})",
                    {"actual": actual, "claimed": claimed_f, "gc_count": gc, "length": len(seq)})


def _translate_dna(seq_dna: str) -> str:
    """Translate a DNA sequence to protein using the standard code.
    Reads in-frame from position 0; trailing partial codons are dropped.
    Stop codons emit '*'."""
    out = []
    for i in range(0, len(seq_dna) - 2, 3):
        codon = seq_dna[i:i + 3]
        out.append(_GENETIC_CODE.get(codon, "X"))
    return "".join(out)


def verify_codon_translation(spec: Dict[str, Any]) -> VerifierResult:
    """Claimed protein matches standard-code translation of the sequence."""
    name = "genetics.codon_translation"
    seq = _normalize_seq(spec.get("sequence"))
    claimed = _normalize_seq(spec.get("claimed_protein"))
    if not seq or not claimed:
        return na(name)
    rna = bool(spec.get("rna"))
    if not _is_valid_seq(seq, rna=rna):
        return error(name, f"sequence has non-{'RNA' if rna else 'DNA'} characters")
    seq_dna = _to_dna(seq) if rna else seq
    if len(seq_dna) % 3 != 0:
        return error(name, f"sequence length {len(seq_dna)} is not a multiple of 3")
    actual = _translate_dna(seq_dna)
    if actual.upper() == claimed.upper():
        return confirm(name,
                       f"translation matches: {actual!r}",
                       {"sequence": seq, "actual": actual, "claimed": claimed})
    return mismatch(name,
                    f"translation mismatch: actual={actual!r}, claimed={claimed!r}",
                    {"sequence": seq, "actual": actual, "claimed": claimed})


def verify_codon_amino_acid(spec: Dict[str, Any]) -> VerifierResult:
    """A single codon translates to the claimed amino acid (standard code)."""
    name = "genetics.codon_amino_acid"
    codon_raw = spec.get("codon")
    claimed = spec.get("claimed_amino_acid")
    if not codon_raw or not claimed:
        return na(name)
    codon = _normalize_seq(codon_raw)
    rna = bool(spec.get("rna"))
    if rna:
        codon = _to_dna(codon)
    if len(codon) != 3:
        return error(name, f"codon must be exactly 3 bases, got {codon!r} (len {len(codon)})")
    if not _is_valid_seq(codon, rna=False):
        return error(name, f"codon has non-DNA characters: {codon!r}")
    actual = _GENETIC_CODE.get(codon)
    if actual is None:
        return error(name, f"codon {codon!r} not in standard genetic code (shouldn't happen)")
    claimed_str = str(claimed).upper().strip()
    # Accept both single-letter ('M') and "stop"/'*' for stop codons.
    if claimed_str in ("STOP", "TER"):
        claimed_str = "*"
    if claimed_str == actual:
        return confirm(name,
                       f"codon {codon} translates to {actual!r} (matches claim)",
                       {"codon": codon, "actual": actual, "claimed": claimed_str})
    return mismatch(name,
                    f"codon {codon} translates to {actual!r}, claimed {claimed_str!r}",
                    {"codon": codon, "actual": actual, "claimed": claimed_str})


def verify_orf_bounds(spec: Dict[str, Any]) -> VerifierResult:
    """Claimed open reading frame starts with ATG and ends with a stop codon."""
    name = "genetics.orf_bounds"
    seq = _normalize_seq(spec.get("sequence"))
    orf = spec.get("claimed_orf")
    if not seq or not orf:
        return na(name)
    rna = bool(spec.get("rna"))
    if not _is_valid_seq(seq, rna=rna):
        return error(name, f"sequence has non-{'RNA' if rna else 'DNA'} characters")
    seq_dna = _to_dna(seq) if rna else seq
    try:
        start = int(orf.get("start"))
        end = int(orf.get("end"))
    except (TypeError, ValueError, AttributeError):
        return error(name, f"claimed_orf must have integer start/end, got {orf!r}")
    if start < 0 or end > len(seq_dna):
        return mismatch(name,
                        f"ORF [{start},{end}) out of bounds for sequence length {len(seq_dna)}",
                        {"start": start, "end": end, "seq_len": len(seq_dna)})
    if (end - start) % 3 != 0:
        return mismatch(name,
                        f"ORF length {end-start} is not a multiple of 3",
                        {"start": start, "end": end, "length": end - start})
    if end - start < 6:
        return mismatch(name,
                        f"ORF too short ({end-start} bases) — must include start + at least one stop codon",
                        {"start": start, "end": end})
    start_codon = seq_dna[start:start + 3]
    stop_codon = seq_dna[end - 3:end]
    issues = []
    if start_codon != "ATG":
        issues.append(f"start codon {start_codon!r} != ATG")
    if stop_codon not in _STOP_CODONS:
        issues.append(f"end codon {stop_codon!r} is not a stop codon ({sorted(_STOP_CODONS)})")
    if issues:
        return mismatch(name, "; ".join(issues),
                        {"start": start, "end": end, "start_codon": start_codon,
                         "stop_codon": stop_codon})
    return confirm(name,
                   f"ORF [{start},{end}) starts with {start_codon}, ends with {stop_codon}",
                   {"start": start, "end": end, "start_codon": start_codon,
                    "stop_codon": stop_codon})


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    """Dispatch every applicable genetics check for the GENETICS_VERIFY block."""
    results: List[VerifierResult] = []
    gv = packet.get("GENETICS_VERIFY") or {}

    if "claimed_complement" in gv:
        results.append(verify_complementarity(gv))
    if "claimed_reverse_complement" in gv:
        results.append(verify_reverse_complement(gv))
    if "claimed_gc_fraction" in gv:
        results.append(verify_gc_content(gv))
    if "claimed_protein" in gv:
        results.append(verify_codon_translation(gv))
    if "codon" in gv and "claimed_amino_acid" in gv:
        results.append(verify_codon_amino_acid(gv))
    if "claimed_orf" in gv:
        results.append(verify_orf_bounds(gv))

    if not results:
        results.append(na("genetics", "no GENETICS_VERIFY artifacts present"))
    return results
