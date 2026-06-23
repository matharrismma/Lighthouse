"""bulletin.py — a verified bulletin any node can confirm OFFLINE.

The integrity gift for an untrusted mesh (LoRa / Meshtastic / Reticulum): publish
a short, signed, content-addressed bulletin, and let ANY recipient confirm — with
no server and no internet — that it is (1) UNALTERED and (2) AUTHENTIC. For the
people who help people when the grid is down, "is this message real?" is
life-and-death; a mesh relays through nodes nobody vetted, so the answer can't
depend on trusting the relay.

Reuses what we already have, no parallel crypto:
  - signing: concordance_engine.instance_identity.sign_dict / verify_dict (Ed25519
    over canonical JSON; the bundle self-carries _instance_pubkey, so it verifies
    offline).
  - content-addressing: sha256 of the canonical bundle (the seals' model — the
    hash IS the identity).

How it travels: the full bundle goes by Reticulum Resource / SD card / sneakernet;
the ONE-PACKET seal-ref (nh1:<sha256-hex>, ~68 bytes) fits a single LoRa message,
so a peer can confirm over the air that the bundle they hold is the one referenced.

Two honest layers — we never claim more integrity than we provide:
  - UNALTERED: recompute sha256(canonical(bundle)) == ref. NO key needed. Detects
    any tampering across untrusted relays.
  - AUTHENTIC: the Ed25519 signature is valid AND _instance_pubkey equals the
    issuer key you trust (pin it out-of-band; GET /pubkey). A bundle carrying its
    own pubkey only proves internal consistency — trust comes from the pinned key.
"""
from __future__ import annotations

import hashlib
import json
import time
from typing import Any, Dict, Optional

_REF_PREFIX = "nh1:"  # Narrow Highway bulletin, scheme v1


def _canon(d: Dict[str, Any]) -> bytes:
    """The same canonical bytes the signature covers, so the hash and the sig
    agree. Falls back to a stable sort if the engine canonicalizer is absent."""
    try:
        from concordance_engine.validate import canonical_json_bytes
        return canonical_json_bytes(d)
    except Exception:  # noqa: BLE001
        return json.dumps(d, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False).encode("utf-8")


def seal_ref(bundle: Dict[str, Any]) -> str:
    """The one-packet content reference: nh1:<sha256-hex of the canonical bundle>."""
    return _REF_PREFIX + hashlib.sha256(_canon(bundle)).hexdigest()


def publish(text: str, kind: str = "bulletin",
            extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Mint a signed, content-addressed bulletin.

    Returns {bundle, ref, ref_short, bytes}. `bundle` is the self-contained signed
    record (carry it on the mesh/SD); `ref` is the one-packet seal-ref."""
    text = (text or "").strip()
    if not text:
        raise ValueError("a bulletin needs text")
    now = int(time.time())
    payload: Dict[str, Any] = {
        "bulletin_version": 1,
        "kind": kind,
        "text": text[:4000],
        "issued_at": now,
        "issued_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now)),
    }
    if extra:
        for k, v in extra.items():
            if k not in payload and not str(k).startswith("_"):
                payload[k] = v
    try:
        from concordance_engine.instance_identity import sign_dict
        bundle = sign_dict(payload)
    except Exception as exc:  # noqa: BLE001
        raise RuntimeError(f"signing unavailable: {exc}") from exc
    ref = seal_ref(bundle)
    return {"bundle": bundle, "ref": ref,
            "ref_short": ref[:len(_REF_PREFIX) + 16],
            "bytes": len(_canon(bundle))}


def verify(bundle: Dict[str, Any], ref: Optional[str] = None,
           pubkey: Optional[str] = None) -> Dict[str, Any]:
    """Verify a bulletin OFFLINE. Returns
    {unaltered, authentic, issuer_pubkey, issuer_id, ref, detail}.

    `ref`    — the one-packet seal-ref; checks the bundle wasn't tampered with.
    `pubkey` — the issuer's PINNED key; checks authenticity. If omitted, the
               signature is checked against the bundle's OWN embedded key, which
               proves internal consistency, NOT who issued it (said plainly in
               `detail`)."""
    computed = seal_ref(bundle)
    unaltered = True if ref is None else (ref.strip() == computed)
    detail = []
    if ref is not None and not unaltered:
        detail.append("REF MISMATCH — bundle does not match the seal-ref "
                      "(altered in transit, or the wrong bundle)")

    authentic = False
    issuer_pubkey = bundle.get("_instance_pubkey")
    issuer_id = bundle.get("_instance_id")
    try:
        from concordance_engine.instance_identity import verify_dict
        ok, vdetail = verify_dict(bundle, pubkey)
        authentic = bool(ok)
        detail.append(("signature ok" if ok else "signature INVALID")
                      + (f" ({vdetail})" if vdetail else ""))
        if ok and pubkey is None:
            detail.append("verified against the bundle's OWN key — pin the issuer "
                          "key (GET /pubkey) to prove WHO signed it")
        elif ok and pubkey is not None:
            detail.append("verified against the pinned issuer key")
    except Exception as exc:  # noqa: BLE001
        detail.append(f"verify unavailable: {exc}")

    return {"unaltered": unaltered, "authentic": authentic,
            "issuer_pubkey": issuer_pubkey, "issuer_id": issuer_id,
            "ref": computed, "detail": "; ".join(detail)}


if __name__ == "__main__":
    import argparse
    import sys
    ap = argparse.ArgumentParser(
        description="Verified bulletins for an untrusted mesh — publish + verify OFFLINE.")
    ap.add_argument("--publish", metavar="TEXT", help="mint a signed bulletin")
    ap.add_argument("--verify", metavar="FILE", help="verify a bundle JSON file")
    ap.add_argument("--ref", help="the one-packet seal-ref to check against")
    ap.add_argument("--pubkey", help="the issuer's pinned public key (authenticity)")
    args = ap.parse_args()
    if args.publish:
        out = publish(args.publish)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    elif args.verify:
        with open(args.verify, "r", encoding="utf-8") as fh:
            b = json.load(fh)
        res = verify(b, ref=args.ref, pubkey=args.pubkey)
        print(json.dumps(res, ensure_ascii=False, indent=2))
        sys.exit(0 if (res["unaltered"] and res["authentic"]) else 1)
    else:
        ap.print_help()
