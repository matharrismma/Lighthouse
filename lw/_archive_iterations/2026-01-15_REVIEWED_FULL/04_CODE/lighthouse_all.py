#!/usr/bin/env python3
"""Lighthouse - Current Iteration (All Computation in One File)

Self-contained, deterministic, auditable.

Implements computation that supports the written canon/specs in this repository:
  - LSP (Lighthouse Standard Pages): deterministic chunking + hashing
  - Investment Packet v1.1: canonical JSON + Ed25519 sign/verify
  - Quarantine/Airlock: capture -> normalize -> dedupe -> packet template
  - Minimal simulator scaffold (Setup -> Positioning -> Conversion) for drift testing
  - Manifest generation (SHA-256 of every file) for integrity
  - Scripture Reference Audit: minimal numeric plausibility checker + rotation suggestions
  - PDF and ZIP exports

IMPORTANT
- This code does not interpret Scripture.
- Source hierarchy / RED primacy is enforced in documentation (00_CANON/*), not by this script.

Python: 3.10+
"""

from __future__ import annotations

import argparse
import base64
import dataclasses
import datetime as dt
import hashlib
import json
import os
import re
import sys
import textwrap
import unicodedata
import zipfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

# --- Crypto (Ed25519) ---
try:
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (
        Ed25519PrivateKey,
        Ed25519PublicKey,
    )
    from cryptography.hazmat.primitives import serialization
except Exception as e:  # pragma: no cover
    raise RuntimeError(
        "Missing dependency: cryptography. Install with: pip install cryptography"
    ) from e


# -------------------------
# Utilities
# -------------------------

def utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            b = f.read(chunk_size)
            if not b:
                break
            h.update(b)
    return h.hexdigest()


def b64u_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64u_decode(s: str) -> bytes:
    pad = "=" * ((4 - (len(s) % 4)) % 4)
    return base64.urlsafe_b64decode((s + pad).encode("ascii"))


def read_text(path: Path, encoding: str = "utf-8") -> str:
    return path.read_text(encoding=encoding)


def write_text(path: Path, text: str, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding=encoding)


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def key_from_arg(value: str) -> str:
    """Accept either a b64url key value or a path to a file containing it."""
    v = value.strip()
    p = Path(v)
    if p.exists() and p.is_file():
        return p.read_text(encoding="utf-8", errors="replace").strip()
    return v


# -------------------------
# LSP: Lighthouse Standard Pages
# -------------------------

@dataclasses.dataclass(frozen=True)
class LSPConfig:
    """Deterministic chunking configuration.

    Authoritative spec lives in 02_SPECS/LSP_SPEC.md.
    """

    words_per_page: int = 300
    normalize_form: str = "NFC"  # good default for Greek/Hebrew
    collapse_whitespace: bool = True
    strip_outer_whitespace: bool = True
    keep_punctuation: bool = True


def normalize_text(text: str, cfg: LSPConfig) -> str:
    t = unicodedata.normalize(cfg.normalize_form, text)

    if cfg.strip_outer_whitespace:
        t = t.strip()

    if cfg.collapse_whitespace:
        t = re.sub(r"\s+", " ", t)

    if not cfg.keep_punctuation:
        t = re.sub(r"[^\w\s]", "", t, flags=re.UNICODE)
        t = re.sub(r"\s+", " ", t).strip()

    return t


def lsp_chunk_words(words: List[str], words_per_page: int) -> List[List[str]]:
    if words_per_page <= 0:
        raise ValueError("words_per_page must be > 0")
    return [words[i : i + words_per_page] for i in range(0, len(words), words_per_page)]


def build_lsp(text: str, cfg: LSPConfig, source_id: str = "") -> Dict[str, Any]:
    normalized = normalize_text(text, cfg)
    words = normalized.split(" ") if normalized else []
    pages_words = lsp_chunk_words(words, cfg.words_per_page)

    pages: List[Dict[str, Any]] = []
    for idx, w in enumerate(pages_words, start=1):
        page_text = " ".join(w)
        pages.append(
            {
                "page": idx,
                "word_count": len(w),
                "sha256": sha256_bytes(page_text.encode("utf-8")),
                "text": page_text,
            }
        )

    return {
        "lsp_version": "1.0",
        "source_id": source_id,
        "created_utc": utc_now_iso(),
        "config": dataclasses.asdict(cfg),
        "document_sha256": sha256_bytes(normalized.encode("utf-8")),
        "page_count": len(pages),
        "pages": pages,
    }


# -------------------------
# Investment Packet v1.1 (Ed25519)
# -------------------------

PACKET_VERSION = "1.1"


def ed25519_generate_keypair() -> Tuple[str, str]:
    """Return (private_key_b64u, public_key_b64u)."""
    sk = Ed25519PrivateKey.generate()
    pk = sk.public_key()

    sk_bytes = sk.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    pk_bytes = pk.public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return b64u_encode(sk_bytes), b64u_encode(pk_bytes)


def ed25519_sign(private_key_b64u: str, message: bytes) -> str:
    sk_bytes = b64u_decode(private_key_b64u)
    sk = Ed25519PrivateKey.from_private_bytes(sk_bytes)
    return b64u_encode(sk.sign(message))


def ed25519_verify(public_key_b64u: str, message: bytes, signature_b64u: str) -> bool:
    pk_bytes = b64u_decode(public_key_b64u)
    pk = Ed25519PublicKey.from_public_bytes(pk_bytes)
    sig = b64u_decode(signature_b64u)
    try:
        pk.verify(sig, message)
        return True
    except Exception:
        return False


def canonical_json_bytes(obj: Any) -> bytes:
    """Canonical JSON encoding used for signing/verifying."""
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode(
        "utf-8"
    )


def packet_payload_for_signature(packet: Dict[str, Any]) -> Dict[str, Any]:
    """Return packet minus signature fields (sign everything else)."""
    pkt = dict(packet)
    pkt.pop("signature_b64u", None)
    return pkt


def example_investment_packet(
    issuer_pk_b64u: Optional[str] = None,
    subject_pk_b64u: Optional[str] = None,
    days_valid: int = 30,
    # Back-compat / explicit names (preferred)
    issuer_pubkey_b64u: Optional[str] = None,
    subject_pubkey_b64u: Optional[str] = None,
) -> Dict[str, Any]:
    """Create an unsigned Investment Packet v1.1 example.

    Accepts both positional legacy names (issuer_pk_b64u/subject_pk_b64u)
    and explicit keyword names (issuer_pubkey_b64u/subject_pubkey_b64u).
    """
    issuer_pk_b64u = issuer_pubkey_b64u or issuer_pk_b64u or ""
    subject_pk_b64u = subject_pubkey_b64u or subject_pk_b64u or ""
    if not issuer_pk_b64u or not subject_pk_b64u:
        raise ValueError("issuer and subject public keys are required (b64url)")
    now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
    exp = now + dt.timedelta(days=int(days_valid))

    # This is an EXAMPLE structure; authoritative spec is 02_SPECS/INVESTMENT_PACKET_SPEC_v1_1.md
    return {
        "version": PACKET_VERSION,
        "issued_utc": now.isoformat(),
        "expires_utc": exp.isoformat(),
        "issuer_public_key_b64u": issuer_pk_b64u,
        "subject_public_key_b64u": subject_pk_b64u,
        "revocation": {"mode": "revocable", "revocation_uri": ""},
        "bands": {
            "income_band": "B2",
            "debt_to_income_band": "D1",
            "savings_band": "S2",
        },
        "proof_hashes": {"local_agg_state_sha256": ""},
        "constraints": {
            "raw_financial_data_leaves_node": False,
            "derived_only": True,
        },
    }


def packet_sign(packet: Dict[str, Any], issuer_private_key_b64u: str) -> Dict[str, Any]:
    payload = packet_payload_for_signature(packet)
    sig = ed25519_sign(issuer_private_key_b64u, canonical_json_bytes(payload))
    signed = dict(packet)
    signed["signature_b64u"] = sig
    return signed


def packet_verify(signed_packet: Dict[str, Any]) -> Tuple[bool, str]:
    if "signature_b64u" not in signed_packet:
        return False, "missing signature_b64u"
    pk = signed_packet.get("issuer_public_key_b64u", "")
    if not pk:
        return False, "missing issuer_public_key_b64u"

    payload = packet_payload_for_signature(signed_packet)
    ok = ed25519_verify(pk, canonical_json_bytes(payload), signed_packet["signature_b64u"])
    return (ok, "ok" if ok else "signature verification failed")


# -------------------------
# Quarantine / Airlock utility
# -------------------------

@dataclasses.dataclass
class QuarantinePacket:
    created_utc: str
    source_sha256: str
    normalized_sha256: str
    tags: List[str]
    dedupe_key: str
    raw_text: str
    normalized_text: str


def quarantine_normalize(text: str) -> str:
    t = unicodedata.normalize("NFC", text)
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{3,}", "\n\n", t)
    return t.strip()


def quarantine_packetize(text: str, tags: Optional[List[str]] = None) -> QuarantinePacket:
    tags = tags or []
    raw = text
    norm = quarantine_normalize(text)
    src_h = sha256_bytes(raw.encode("utf-8"))
    norm_h = sha256_bytes(norm.encode("utf-8"))
    dedupe_key = norm_h
    return QuarantinePacket(
        created_utc=utc_now_iso(),
        source_sha256=src_h,
        normalized_sha256=norm_h,
        tags=tags,
        dedupe_key=dedupe_key,
        raw_text=raw,
        normalized_text=norm,
    )


# -------------------------
# Minimal phase simulation (Setup -> Positioning -> Conversion)
# -------------------------

@dataclasses.dataclass
class SimState:
    day: int
    phase: str
    drift_score: float


def simulate(days: int = 365, seed: int = 7) -> Dict[str, Any]:
    # Deterministic pseudo-sim (no RNG needed for this placeholder): drift increases
    # until a phase boundary resets it. This is a *scaffold*.
    phases = [(1, "Setup"), (int(days * 0.4), "Positioning"), (int(days * 0.8), "Conversion")]
    phase = "Setup"
    drift = 0.0
    timeline: List[Dict[str, Any]] = []

    for d in range(1, days + 1):
        for start_day, ph in reversed(phases):
            if d >= start_day:
                phase = ph
                break

        # simple deterministic drift curve
        drift = min(1.0, drift + 0.002)
        if d in {phases[1][0], phases[2][0]}:
            drift = max(0.0, drift - 0.25)

        timeline.append({"day": d, "phase": phase, "drift_score": round(drift, 6)})

    return {
        "created_utc": utc_now_iso(),
        "days": days,
        "seed": seed,
        "timeline": timeline,
    }


# -------------------------
# Manifest
# -------------------------


def build_manifest(root: Path, out: Path) -> Dict[str, Any]:
    root = root.resolve()
    files: List[Dict[str, str]] = []
    for p in sorted(root.rglob("*")):
        if p.is_dir():
            continue
        rel = p.relative_to(root)
        # Skip volatile caches and compiled artifacts
        if any(part in {"__pycache__", ".pytest_cache"} for part in rel.parts):
            continue
        files.append({"path": str(rel), "sha256": sha256_file(p)})

    man = {"created_utc": utc_now_iso(), "root": str(root), "files": files}
    write_json(out, man)
    return man


# -------------------------
# Scripture Reference Audit (minimal)
# -------------------------

# Goal: catch obvious input errors (e.g., impossible verse numbers) and apply the
# Reference Alignment / Rotation Rule by suggesting nearby anchors.

_BOOK_ALIASES = {
    "gen": "Genesis",
    "genesis": "Genesis",
    "isa": "Isaiah",
    "isaiah": "Isaiah",
    "ps": "Psalms",
    "psalm": "Psalms",
    "psalms": "Psalms",
    "prov": "Proverbs",
    "proverbs": "Proverbs",
    "matt": "Matthew",
    "mat": "Matthew",
    "matthew": "Matthew",
    "mark": "Mark",
    "luke": "Luke",
    "john": "John",
    "acts": "Acts",
    "rom": "Romans",
    "romans": "Romans",
    "1 thess": "1 Thessalonians",
    "1thess": "1 Thessalonians",
    "1 thessalonians": "1 Thessalonians",
    "2 thess": "2 Thessalonians",
    "2thess": "2 Thessalonians",
    "2 thessalonians": "2 Thessalonians",
}

# Minimal verse maxima for chapters that appear in current ledger/specs.
# Not a full Bible database.
_VERSE_MAX: Dict[Tuple[str, int], int] = {
    ("Matthew", 6): 34,
    ("Matthew", 7): 29,
    ("John", 6): 71,
    ("John", 15): 27,
    ("Genesis", 3): 24,
    ("Isaiah", 55): 13,
    ("Psalms", 127): 5,
    ("Proverbs", 10): 32,
    ("1 Thessalonians", 4): 18,
    ("Mark", 7): 37,
    ("Luke", 6): 49,
    ("Acts", 7): 60,
}

# Regex: BookName Chapter:Verse(-Verse)
_REF_RE = re.compile(
    r"\b(?P<book>(?:[1-3]\s*)?[A-Za-z]+(?:\s+[A-Za-z]+)*)\s+"
    r"(?P<ch>\d{1,3}):(?P<v1>\d{1,3})(?:-(?P<v2>\d{1,3}))?\b"
)


def _canon_book(book_raw: str) -> Optional[str]:
    b = re.sub(r"\s+", " ", book_raw.strip()).lower()
    return _BOOK_ALIASES.get(b)


def parse_scripture_refs(text: str) -> List[str]:
    return [m.group(0) for m in _REF_RE.finditer(text)]


def _split_ref(ref: str) -> Optional[Tuple[str, int, int, int]]:
    m = _REF_RE.search(ref)
    if not m:
        return None
    book = _canon_book(m.group("book"))
    if not book:
        return None
    ch = int(m.group("ch"))
    v1 = int(m.group("v1"))
    v2 = int(m.group("v2")) if m.group("v2") else v1
    return book, ch, v1, v2


def rotation_suggestions(ref: str, radius: int = 3) -> List[str]:
    parsed = _split_ref(ref)
    if not parsed:
        return []
    book, ch, v1, _ = parsed
    maxv = _VERSE_MAX.get((book, ch))
    if not maxv:
        return []
    out: List[str] = []
    for dv in range(-radius, radius + 1):
        cand = v1 + dv
        if 1 <= cand <= maxv:
            out.append(f"{book} {ch}:{cand}")
    if f"{book} {ch}:{maxv}" not in out:
        out.append(f"{book} {ch}:{maxv}")
    return out


def validate_ref(ref: str) -> Dict[str, Any]:
    parsed = _split_ref(ref)
    if not parsed:
        return {"raw": ref, "status": "unparsed", "detail": "regex did not match"}
    book, ch, v1, v2 = parsed
    maxv = _VERSE_MAX.get((book, ch))
    if maxv is None:
        return {
            "raw": ref,
            "book": book,
            "chapter": ch,
            "v1": v1,
            "v2": v2,
            "status": "unverified",
            "detail": "chapter not in minimal verse-max map",
        }
    if not (1 <= v1 <= maxv and 1 <= v2 <= maxv and v1 <= v2):
        return {
            "raw": ref,
            "book": book,
            "chapter": ch,
            "v1": v1,
            "v2": v2,
            "maxv": maxv,
            "status": "invalid",
            "detail": f"verse out of bounds for {book} {ch} (max {maxv})",
        }
    return {
        "raw": ref,
        "book": book,
        "chapter": ch,
        "v1": v1,
        "v2": v2,
        "maxv": maxv,
        "status": "ok",
        "detail": "ok",
    }


def audit_repo_scripture_refs(root: Path) -> Dict[str, Any]:
    root = root.resolve()
    findings: List[Dict[str, Any]] = []
    scanned_files: List[str] = []

    def consider_file(p: Path) -> bool:
        if p.suffix.lower() not in {".md", ".json", ".txt", ".py"}:
            return False
        # Avoid self-referential audits (audit outputs include refs and will
        # create false positives / loops).
        if "07_AUDITS" in p.parts:
            return False
        if "06_EXPORTS" in p.parts and p.suffix.lower() in {".pdf", ".zip"}:
            return False
        if any(part in {"__pycache__", ".pytest_cache"} for part in p.parts):
            return False
        return True

    for p in sorted(root.rglob("*")):
        if p.is_dir() or not consider_file(p):
            continue
        try:
            t = p.read_text(encoding="utf-8", errors="replace")
        except Exception:
            continue
        refs = parse_scripture_refs(t)
        if not refs:
            continue
        scanned_files.append(str(p.relative_to(root)))
        for r in refs:
            vr = validate_ref(r)
            vr["file"] = str(p.relative_to(root))
            if vr.get("status") == "invalid":
                vr["rotation_suggestions"] = rotation_suggestions(r, radius=3)
            findings.append(vr)

    summary = {
        "ok": sum(1 for f in findings if f.get("status") == "ok"),
        "invalid": sum(1 for f in findings if f.get("status") == "invalid"),
        "unverified": sum(1 for f in findings if f.get("status") == "unverified"),
        "unparsed": sum(1 for f in findings if f.get("status") == "unparsed"),
        "total": len(findings),
        "files_with_refs": len(set(f["file"] for f in findings)) if findings else 0,
    }

    return {
        "created_utc": utc_now_iso(),
        "root": str(root),
        "summary": summary,
        "files_scanned_with_refs": sorted(set(scanned_files)),
        "findings": findings,
        "verse_max_map": {f"{k[0]} {k[1]}": v for k, v in _VERSE_MAX.items()},
    }


# -------------------------
# PDF + ZIP export helpers
# -------------------------


def build_pdf(out_path: Path, md_files: List[Path], title: str = "Lighthouse - Current Iteration") -> None:
    """Create one PDF containing provided markdown files in order.

    Minimal markdown renderer: headings detected; everything else wrapped as text.
    """

    try:
        from reportlab.lib.pagesizes import LETTER
        from reportlab.pdfbase import pdfmetrics
        from reportlab.pdfbase.ttfonts import TTFont
        from reportlab.pdfgen import canvas
    except Exception as e:
        raise SystemExit("Missing dependency 'reportlab'. Install: pip install reportlab") from e

    # Optional font; falls back to Helvetica
    try:
        pdfmetrics.registerFont(
            TTFont("DejaVuSans", "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf")
        )
        base_font = "DejaVuSans"
    except Exception:
        base_font = "Helvetica"

    c = canvas.Canvas(str(out_path), pagesize=LETTER)
    width, height = LETTER
    left, right = 54, width - 54
    top, bottom = height - 54, 54

    def new_page() -> None:
        c.showPage()
        c.setFont(base_font, 11)

    y = top
    c.setTitle(title)
    c.setFont(base_font, 16)
    c.drawString(left, y, title)
    y -= 24
    c.setFont(base_font, 10)
    c.drawString(left, y, f"Generated (UTC): {utc_now_iso()}")
    y -= 18

    def draw_wrapped(line: str, font_size: int = 11, leading: int = 14) -> None:
        nonlocal y
        c.setFont(base_font, font_size)
        max_width = right - left
        words = line.split()
        if not words:
            y -= leading
            return
        cur = ""
        for w in words:
            trial = (cur + " " + w).strip()
            if c.stringWidth(trial, base_font, font_size) <= max_width:
                cur = trial
            else:
                if y <= bottom:
                    new_page()
                    y = top
                c.drawString(left, y, cur)
                y -= leading
                cur = w
        if cur:
            if y <= bottom:
                new_page()
                y = top
            c.drawString(left, y, cur)
            y -= leading

    for md in md_files:
        if not md.exists():
            continue
        if y <= bottom + 40:
            new_page()
            y = top
        c.setFont(base_font, 12)
        c.drawString(left, y, f"FILE: {md.as_posix()}")
        y -= 18

        for raw in md.read_text(encoding="utf-8", errors="replace").splitlines():
            line = raw.rstrip("\n")
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                txt = line.lstrip("#").strip()
                size = max(14 - (level - 1), 11)
                if y <= bottom + 30:
                    new_page()
                    y = top
                c.setFont(base_font, size)
                c.drawString(left, y, txt)
                y -= 18
            elif line.strip().startswith("```"):
                if y <= bottom + 20:
                    new_page()
                    y = top
                c.setFont(base_font, 10)
                c.drawString(left, y, line.strip())
                y -= 14
            else:
                draw_wrapped(line, font_size=11, leading=14)
        y -= 12

    c.save()


def export_zip(root: Path, out_zip: Path, exclude_dirs: Optional[set[str]] = None) -> None:
    exclude_dirs = exclude_dirs or set()
    with zipfile.ZipFile(out_zip, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for p in sorted(root.rglob("*")):
            if p.is_dir():
                continue
            rel = p.relative_to(root)
            if rel.parts and rel.parts[0] in exclude_dirs:
                continue
            if any(part in {"__pycache__", ".pytest_cache"} for part in rel.parts):
                continue
            z.write(p, arcname=str(rel))


# -------------------------
# CLI commands
# -------------------------


def cmd_build_lsp(args: argparse.Namespace) -> int:
    text = read_text(Path(args.input))
    cfg = LSPConfig(
        words_per_page=args.words_per_page,
        normalize_form=args.normalize_form,
        collapse_whitespace=not args.keep_whitespace,
        keep_punctuation=not args.drop_punctuation,
    )
    out = build_lsp(text, cfg, source_id=args.source_id)
    write_json(Path(args.out), out)
    return 0


def cmd_gen_keypair(args: argparse.Namespace) -> int:
    sk, pk = ed25519_generate_keypair()
    out = {
        "version": "1",
        "created_utc": utc_now_iso(),
        "ed25519_private_key_b64u": sk,
        "ed25519_public_key_b64u": pk,
    }
    write_json(Path(args.out), out)
    return 0


def cmd_make_example_packet(args: argparse.Namespace) -> int:
    issuer_pk = key_from_arg(args.issuer_pubkey)
    subject_pk = key_from_arg(args.subject_pubkey)
    pkt = example_investment_packet(issuer_pk, subject_pk, days_valid=args.days_valid)
    write_json(Path(args.out), pkt)
    return 0


def cmd_sign_packet(args: argparse.Namespace) -> int:
    pkt = load_json(Path(args.packet))
    signed = packet_sign(pkt, key_from_arg(args.issuer_private_key))
    write_json(Path(args.out), signed)
    return 0


def cmd_verify_packet(args: argparse.Namespace) -> int:
    pkt = load_json(Path(args.signed))
    ok, msg = packet_verify(pkt)
    print(json.dumps({"ok": ok, "message": msg}, indent=2))
    return 0 if ok else 2


def cmd_quarantine(args: argparse.Namespace) -> int:
    text = read_text(Path(args.input))
    qp = quarantine_packetize(text, tags=args.tags or [])
    write_json(Path(args.out), dataclasses.asdict(qp))
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    rep = simulate(days=args.days, seed=args.seed)
    write_json(Path(args.out), rep)
    return 0


def cmd_manifest(args: argparse.Namespace) -> int:
    build_manifest(Path(args.root), Path(args.out))
    return 0


def cmd_audit_refs(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    rep = audit_repo_scripture_refs(root)
    out_json = Path(args.out_json)
    write_json(out_json, rep)

    if args.out_md:
        out_md = Path(args.out_md)
        s = rep["summary"]
        lines: List[str] = []
        lines.append("# Scripture Reference Audit")
        lines.append("")
        lines.append(f"Generated (UTC): {rep['created_utc']}")
        lines.append("")
        lines.append("## Summary")
        lines.append(f"- Total refs found: **{s['total']}**")
        lines.append(f"- OK: **{s['ok']}**")
        lines.append(f"- Invalid: **{s['invalid']}**")
        lines.append(f"- Unverified: **{s['unverified']}**")
        lines.append(f"- Unparsed: **{s['unparsed']}**")
        lines.append("")

        invalid = [f for f in rep["findings"] if f.get("status") == "invalid"]
        if invalid:
            lines.append("## Invalid references (input error candidates)")
            for f in invalid:
                lines.append(f"- **{f['raw']}** in `{f['file']}` - {f['detail']}")
                if f.get("rotation_suggestions"):
                    sug = ", ".join(f["rotation_suggestions"][:8])
                    lines.append(f"  - Rotation suggestions: {sug}")
        else:
            lines.append("## Invalid references")
            lines.append("- None found.")

        lines.append("")
        unv = [f for f in rep["findings"] if f.get("status") == "unverified"]
        lines.append("## Unverified references")
        if unv:
            for f in unv:
                lines.append(f"- **{f['raw']}** in `{f['file']}` ({f['detail']})")
        else:
            lines.append("- None.")

        write_text(out_md, "\n".join(lines) + "\n")

    print(json.dumps(rep["summary"], indent=2))
    return 0


def cmd_build_pdf(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    md_files: List[Path] = [root / "README_START_HERE.md"]
    for folder in ["00_CANON", "01_SEEDS", "02_SPECS", "03_ARCH", "07_AUDITS", "seed"]:
        d = root / folder
        if not d.exists():
            continue
        md_files.extend(sorted(d.glob("*.md")))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    build_pdf(out, md_files, title=args.title)
    print(f"Wrote PDF: {out}")
    return 0


def cmd_export_zip(args: argparse.Namespace) -> int:
    root = Path(args.root).resolve()
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    exclude = set(args.exclude_dirs or [])
    export_zip(root, out, exclude_dirs=exclude)
    print(f"Wrote ZIP: {out}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="lighthouse_all.py",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """\
            Lighthouse - All computation in one file.

            Examples:
              python3 04_CODE/lighthouse_all.py build-lsp --input my.txt --out 06_EXPORTS/lsp.json
              python3 04_CODE/lighthouse_all.py gen-keypair --out 06_EXPORTS/keys.json
              python3 04_CODE/lighthouse_all.py make-example-packet --issuer-pubkey <pk> --subject-pubkey <pk> --out 06_EXPORTS/packet.json
              python3 04_CODE/lighthouse_all.py sign-packet --packet 06_EXPORTS/packet.json --issuer-private-key <sk> --out 06_EXPORTS/signed.json
              python3 04_CODE/lighthouse_all.py verify-packet --signed 06_EXPORTS/signed.json
              python3 04_CODE/lighthouse_all.py audit-refs --root . --out-json 07_AUDITS/scripture_audit.json --out-md 07_AUDITS/scripture_audit.md
              python3 04_CODE/lighthouse_all.py manifest --root . --out 06_EXPORTS/MANIFEST.json
              python3 04_CODE/lighthouse_all.py build-pdf --root . --out 06_EXPORTS/Lighthouse_Current_Iteration.pdf
              python3 04_CODE/lighthouse_all.py export-zip --root . --out 06_EXPORTS/Lighthouse_Current_Iteration.zip
            """
        ),
    )

    sp = p.add_subparsers(dest="cmd", required=True)

    s = sp.add_parser("build-lsp", help="Build Lighthouse Standard Pages JSON")
    s.add_argument("--input", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--source-id", default="")
    s.add_argument("--words-per-page", type=int, default=300)
    s.add_argument("--normalize-form", default="NFC", choices=["NFC", "NFD", "NFKC", "NFKD"])
    s.add_argument("--keep-whitespace", action="store_true", help="Do not collapse whitespace")
    s.add_argument("--drop-punctuation", action="store_true")
    s.set_defaults(func=cmd_build_lsp)

    s = sp.add_parser("gen-keypair", help="Generate Ed25519 keypair (b64url raw)")
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_gen_keypair)

    s = sp.add_parser("make-example-packet", help="Create an unsigned Investment Packet v1.1 example")
    s.add_argument("--issuer-pubkey", required=True)
    s.add_argument("--subject-pubkey", required=True)
    s.add_argument("--days-valid", type=int, default=30)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_make_example_packet)

    s = sp.add_parser("sign-packet", help="Sign an Investment Packet v1.1 (Ed25519)")
    s.add_argument("--packet", required=True)
    s.add_argument("--issuer-private-key", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_sign_packet)

    s = sp.add_parser("verify-packet", help="Verify a signed Investment Packet v1.1")
    s.add_argument("--signed", required=True)
    s.set_defaults(func=cmd_verify_packet)

    s = sp.add_parser("quarantine", help="Packetize raw input into a quarantine packet template")
    s.add_argument("--input", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--tags", nargs="*", default=[])
    s.set_defaults(func=cmd_quarantine)

    s = sp.add_parser("simulate", help="Run minimal phase/drift simulation")
    s.add_argument("--days", type=int, default=365)
    s.add_argument("--seed", type=int, default=7)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_simulate)

    s = sp.add_parser("manifest", help="Generate SHA-256 manifest for a folder")
    s.add_argument("--root", required=True)
    s.add_argument("--out", required=True)
    s.set_defaults(func=cmd_manifest)

    s = sp.add_parser("audit-refs", help="Audit Scripture references (minimal plausibility check)")
    s.add_argument("--root", required=True)
    s.add_argument("--out-json", required=True)
    s.add_argument("--out-md", required=False)
    s.set_defaults(func=cmd_audit_refs)

    s = sp.add_parser("build-pdf", help="Build a single PDF of all markdown docs")
    s.add_argument("--root", required=True, help="Root folder of the iteration")
    s.add_argument("--out", required=True, help="Output PDF path")
    s.add_argument("--title", default="Lighthouse - Current Iteration")
    s.set_defaults(func=cmd_build_pdf)

    s = sp.add_parser("export-zip", help="Export a zip of the iteration folder")
    s.add_argument("--root", required=True)
    s.add_argument("--out", required=True)
    s.add_argument("--exclude-dirs", nargs="*", default=["06_EXPORTS"], help="Top-level dirs to exclude")
    s.set_defaults(func=cmd_export_zip)

    return p


def main(argv: Optional[List[str]] = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    parser = build_parser()
    args = parser.parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
