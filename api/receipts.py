"""Promotion receipts — Ed25519-signed proofs of contribution.

When the operator promotes a Scribe submission to the almanac, this
module mints a soulbound receipt: a JSON record signed by the
engine's instance keypair, tying the intake_id + handle to the
almanac entry it produced.

The receipt is the credential primitive for the kingdom-economy
substrate: a contributor's submission record cannot be forged
without the engine's private key, and the receipt is verifiable
offline (LoRa mesh, USB transfer, future Arweave anchor) by anyone
holding the engine's public key.

Storage: data/receipts/promotions.jsonl (append-only)
Public lookup: GET /receipts/{intake_id}
"""
from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Dict, List, Optional


_DATA_DIR = Path(__file__).parent.parent / "data" / "receipts"
_RECEIPTS_FILE = _DATA_DIR / "promotions.jsonl"


def _ensure_dir() -> None:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)


def mint_promotion_receipt(
    *,
    intake_id: str,
    almanac_entry_id: str,
    almanac_entry_title: str = "",
    contributor_handle: str = "",
    operator_note: str = "",
) -> Dict[str, Any]:
    """Sign a promotion receipt and persist it.

    Returns the full signed receipt dict, including signature fields.
    Idempotent: minting twice for the same intake_id replaces the
    prior receipt in the visible feed (the JSONL keeps both for audit;
    look-ups use the latest).
    """
    iid = (intake_id or "").strip()
    aid = (almanac_entry_id or "").strip()
    if not iid:
        raise ValueError("intake_id is required")
    if not aid:
        raise ValueError("almanac_entry_id is required")

    now = int(time.time())
    payload: Dict[str, Any] = {
        "receipt_version": 1,
        "kind": "almanac_promotion_receipt",
        "intake_id": iid,
        "almanac_entry_id": aid,
        "almanac_entry_title": (almanac_entry_title or "")[:240],
        "contributor_handle": (contributor_handle or "").strip().lower()[:40],
        "promoted_at": now,
        "promoted_at_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
        "operator_note": (operator_note or "").strip()[:500],
    }

    # Sign — instance_identity.sign_dict adds _sig, _instance_pubkey, _instance_id
    try:
        from concordance_engine.instance_identity import sign_dict
        signed = sign_dict(payload)
    except Exception as exc:
        # If signing fails, persist an unsigned record so the audit trail
        # exists, but flag it so the operator knows to investigate.
        signed = dict(payload)
        signed["_sig_error"] = f"{type(exc).__name__}: {str(exc)[:200]}"

    _ensure_dir()
    with _RECEIPTS_FILE.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(signed, ensure_ascii=False) + "\n")
    return signed


def find_receipt(intake_id: str) -> Optional[Dict[str, Any]]:
    """Return the most recent receipt for an intake_id, or None.

    Scans the JSONL; for receipt volumes < ~10k this is fast and
    simple. If volume grows, add a JSON index.
    """
    iid = (intake_id or "").strip()
    if not iid or not _RECEIPTS_FILE.exists():
        return None
    latest: Optional[Dict[str, Any]] = None
    try:
        for line in _RECEIPTS_FILE.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if rec.get("intake_id") == iid:
                latest = rec  # last wins
    except OSError:
        return None
    return latest


def list_receipts(
    *, handle: Optional[str] = None, limit: int = 200
) -> List[Dict[str, Any]]:
    """List receipts, optionally filtered by contributor handle."""
    if not _RECEIPTS_FILE.exists():
        return []
    out: List[Dict[str, Any]] = []
    target = (handle or "").strip().lower() or None
    try:
        for line in _RECEIPTS_FILE.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            if target and rec.get("contributor_handle", "") != target:
                continue
            out.append(rec)
    except OSError:
        return []
    out.sort(key=lambda r: r.get("promoted_at", 0), reverse=True)
    return out[:limit]


def verify_receipt(receipt: Dict[str, Any]) -> Dict[str, Any]:
    """Verify the Ed25519 signature on a receipt.

    Returns {ok, detail, signer_pubkey, signer_instance_id}.
    """
    try:
        from concordance_engine.instance_identity import verify_dict
    except Exception as exc:
        return {"ok": False, "detail": f"verify unavailable: {exc}"}
    ok, detail = verify_dict(receipt)
    return {
        "ok": bool(ok),
        "detail": detail,
        "signer_pubkey": receipt.get("_instance_pubkey"),
        "signer_instance_id": receipt.get("_instance_id"),
    }
