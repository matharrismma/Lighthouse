"""wallet.py — Wallet endpoints (Phase 1 + LOOP 8 polish).

The site never holds keys or funds. These endpoints:
- Publish the operator's address
- Log txids users + operator tell us about (transparency ledger)
- Return that ledger publicly
- Provide onboarding help JSON
- Verify claimed txids against Base RPC (mark `verified_on_chain: true`)
- Read live operator balance + recent incoming tx via Base RPC
- Record privacy-respecting analytics (counters only, no PII)
"""
from __future__ import annotations
import json
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# ---------- Lightweight Base RPC client ----------

# Public Base mainnet RPC. Free for low-volume read calls. Operator can
# override via env var or by editing this constant if rate-limited.
BASE_RPC_URL = "https://mainnet.base.org"
USDC_BASE_CONTRACT = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

def _rpc(method: str, params: list, timeout: float = 6.0) -> dict | None:
    """Single JSON-RPC call to Base. Returns the 'result' field or None on error."""
    payload = json.dumps({"jsonrpc": "2.0", "method": method, "params": params, "id": 1}).encode()
    req = urllib.request.Request(
        BASE_RPC_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = json.loads(r.read().decode())
            return body.get("result")
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, json.JSONDecodeError):
        return None


def _verify_tx(txid: str) -> dict:
    """Check if a tx exists on Base + whether it succeeded. Returns
    {found, success, block_number, from, to, value_wei}."""
    if not txid or not txid.startswith("0x") or len(txid) != 66:
        return {"found": False, "success": False, "reason": "invalid_txid"}
    tx = _rpc("eth_getTransactionByHash", [txid])
    if not tx:
        return {"found": False, "success": False, "reason": "rpc_or_not_found"}
    receipt = _rpc("eth_getTransactionReceipt", [txid])
    if not receipt:
        # Tx exists but not yet mined
        return {
            "found": True, "success": False, "reason": "pending",
            "from": tx.get("from"), "to": tx.get("to"),
            "value_wei": int(tx.get("value", "0x0"), 16) if tx.get("value") else 0,
        }
    success = receipt.get("status") == "0x1"
    return {
        "found": True,
        "success": success,
        "block_number": int(receipt.get("blockNumber", "0x0"), 16) if receipt.get("blockNumber") else None,
        "from": tx.get("from"),
        "to": tx.get("to"),
        "value_wei": int(tx.get("value", "0x0"), 16) if tx.get("value") else 0,
    }


def _eth_balance_wei(address: str) -> int:
    res = _rpc("eth_getBalance", [address, "latest"])
    if not res:
        return 0
    try:
        return int(res, 16)
    except ValueError:
        return 0


def _usdc_balance_units(address: str) -> int:
    """Returns USDC balance in 6-decimal base units. USDC.balanceOf(address)
    selector: 0x70a08231 (balanceOf)."""
    if not address or not address.startswith("0x") or len(address) != 42:
        return 0
    selector = "0x70a08231"
    padded = address[2:].lower().rjust(64, "0")
    data = selector + padded
    res = _rpc("eth_call", [{"to": USDC_BASE_CONTRACT, "data": data}, "latest"])
    if not res or res == "0x":
        return 0
    try:
        return int(res, 16)
    except ValueError:
        return 0

try:
    from fastapi import APIRouter, HTTPException, Body
    from pydantic import BaseModel
except Exception:
    BaseModel = object  # type: ignore
    APIRouter = None

REPO = Path(__file__).resolve().parent.parent
WALLET_DIR = REPO / "data" / "wallet"
OPERATOR_PATH = WALLET_DIR / "operator.json"
LOG_PATH = WALLET_DIR / "transparency_log.json"


# Module-scope Pydantic model — FastAPI's OpenAPI schema generator can't
# introspect models defined inside get_router(), so /openapi.json 500s.
if APIRouter is not None:
    class TipRecord(BaseModel):
        txid: str
        chain: str  # 'base' | 'optimism' | 'ethereum'
        amount_usd: Optional[float] = None
        token: Optional[str] = "USDC"
        from_redacted: Optional[str] = None
        intent: str  # 'patron' | 'tip-creator' | 'sponsor-invoice' | 'other'
        creator_id: Optional[str] = None
        message: Optional[str] = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_operator() -> dict:
    if not OPERATOR_PATH.exists():
        return {}
    return json.loads(OPERATOR_PATH.read_text(encoding="utf-8"))


def _load_log() -> dict:
    if not LOG_PATH.exists():
        return {"entries": [], "schema_version": 1}
    return json.loads(LOG_PATH.read_text(encoding="utf-8"))


def _save_log(log: dict):
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps(log, indent=2), encoding="utf-8")


def _valid_txid(txid: str) -> bool:
    """Light validation only — EVM tx hash is 0x + 64 hex chars."""
    if not isinstance(txid, str):
        return False
    txid = txid.strip()
    if not txid.startswith("0x"):
        return False
    body = txid[2:]
    if len(body) != 64:
        return False
    try:
        int(body, 16)
        return True
    except ValueError:
        return False


def _valid_evm(addr: str) -> bool:
    if not isinstance(addr, str):
        return False
    addr = addr.strip()
    if not addr.startswith("0x") or len(addr) != 42:
        return False
    try:
        int(addr[2:], 16)
        return True
    except ValueError:
        return False


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/wallet/operator-address")
    def get_operator_address():
        op = _load_operator()
        addr = op.get("evm_address", "")
        basename = op.get("evm_basename", "")
        return {
            "evm_basename": basename,
            "evm_address": addr,
            "btc_address": op.get("btc_address", ""),
            "default_chain": op.get("default_chain", "base"),
            "chains_accepted": op.get("chains_accepted", ["base"]),
            "default_token": op.get("default_token", "USDC"),
            "tokens_accepted": op.get("tokens_accepted", ["USDC"]),
            "patron_suggested_amounts_usd": op.get("patron_suggested_amounts_usd", [5, 10, 25, 50, 100]),
            "patron_circle_cadence_options": op.get("patron_circle_cadence_options", ["one-time", "monthly"]),
            "published": bool(addr or basename),
            "send_ready": bool(addr),  # need raw 0x for the actual transfer call
            "explorer_urls": op.get("explorer_urls", {}),
            "basename_lookup_url": "https://www.base.org/name/" + basename.replace(".base.eth", "") if basename.endswith(".base.eth") else None,
            "allocation": op.get("allocation", {}),
        }

    @router.post("/wallet/record-tip")
    def record_tip(rec: TipRecord):
        if not _valid_txid(rec.txid):
            raise HTTPException(400, "Invalid txid format. Expected 0x + 64 hex chars.")
        if rec.intent not in ("patron", "tip-creator", "sponsor-invoice", "other"):
            raise HTTPException(400, "Invalid intent.")
        if rec.amount_usd is not None and (rec.amount_usd <= 0 or rec.amount_usd > 1_000_000):
            raise HTTPException(400, "Amount out of range.")
        log = _load_log()
        entries = log.get("entries", [])
        # Dedupe: if a txid is already logged, refuse silently
        if any(e.get("txid") == rec.txid for e in entries):
            return {"status": "already_logged", "txid": rec.txid}
        entry = {
            "id": f"tip_{len(entries) + 1:06d}",
            "direction": "in",
            "txid": rec.txid,
            "chain": rec.chain,
            "amount_usd": rec.amount_usd,
            "token": rec.token,
            "from_redacted": rec.from_redacted,
            "intent": rec.intent,
            "creator_id": rec.creator_id,
            "message": (rec.message or "")[:200],
            "recorded_at": _now(),
            "verified_on_chain": False,  # Phase 2: set True after RPC check
        }
        entries.append(entry)
        log["entries"] = entries
        _save_log(log)
        return {"status": "recorded", "id": entry["id"], "txid": rec.txid}

    @router.post("/wallet/record-payout")
    def record_payout(body: dict = Body(...)):
        """Operator-only (in Phase 2, gate this with auth). Logs an outgoing payout for transparency."""
        txid = body.get("txid")
        creator_id = body.get("creator_id")
        amount_usd = body.get("amount_usd")
        note = body.get("note", "")
        if not _valid_txid(txid):
            raise HTTPException(400, "Invalid txid.")
        log = _load_log()
        entries = log.get("entries", [])
        if any(e.get("txid") == txid for e in entries):
            return {"status": "already_logged"}
        entry = {
            "id": f"out_{len(entries) + 1:06d}",
            "direction": "out",
            "txid": txid,
            "chain": body.get("chain", "base"),
            "amount_usd": amount_usd,
            "creator_id": creator_id,
            "note": str(note)[:200],
            "recorded_at": _now(),
            "verified_on_chain": False,
        }
        entries.append(entry)
        log["entries"] = entries
        _save_log(log)
        return {"status": "recorded", "id": entry["id"]}

    @router.get("/wallet/transparency")
    def transparency():
        log = _load_log()
        entries = log.get("entries", [])
        in_total = sum((e.get("amount_usd") or 0) for e in entries if e.get("direction") == "in")
        out_total = sum((e.get("amount_usd") or 0) for e in entries if e.get("direction") == "out")
        return {
            "schema_version": log.get("schema_version", 1),
            "entries": entries,
            "totals": {
                "in_count": sum(1 for e in entries if e.get("direction") == "in"),
                "out_count": sum(1 for e in entries if e.get("direction") == "out"),
                "in_usd": round(in_total, 2),
                "out_usd": round(out_total, 2),
                "balance_logged_usd": round(in_total - out_total, 2),
            },
            "_note": "Phase 1: amounts are self-reported by senders + operator. Phase 2 verifies via RPC. Anyone can audit on-chain at the operator's address.",
        }

    @router.post("/wallet/verify-pending")
    def verify_pending():
        """Sweep transparency_log for unverified entries; check each against Base RPC; mark verified."""
        log = _load_log()
        entries = log.get("entries", [])
        checked = 0
        verified = 0
        failed = 0
        for e in entries:
            if e.get("verified_on_chain"):
                continue
            if e.get("chain") not in (None, "base"):
                # Phase 1 only verifies on Base
                continue
            checked += 1
            txid = e.get("txid", "")
            r = _verify_tx(txid)
            if r.get("found") and r.get("success"):
                e["verified_on_chain"] = True
                e["verified_at"] = _now()
                e["verified_block"] = r.get("block_number")
                verified += 1
            elif r.get("found") and not r.get("success") and r.get("reason") != "pending":
                e["verified_on_chain"] = False
                e["verification_failed"] = True
                e["verification_reason"] = r.get("reason", "tx_failed")
                failed += 1
        log["entries"] = entries
        _save_log(log)
        return {"checked": checked, "verified": verified, "failed": failed}

    @router.get("/wallet/onchain")
    def onchain_snapshot():
        """Read live balance from Base RPC. No keys involved — RPC is read-only public."""
        op = _load_operator()
        addr = op.get("evm_address", "")
        if not addr:
            return {"available": False, "reason": "no_address_published"}
        eth_wei = _eth_balance_wei(addr)
        usdc_units = _usdc_balance_units(addr)
        return {
            "available": True,
            "address": addr,
            "basename": op.get("evm_basename", ""),
            "eth_balance": eth_wei / 1e18,
            "usdc_balance": usdc_units / 1e6,
            "as_of": _now(),
            "chain": "base",
            "_note": "Live read from Base RPC. No keys used; this is read-only public chain state.",
        }

    # --- Privacy-respecting analytics (counters only) ---
    ANALYTICS_PATH = WALLET_DIR / "analytics.json"

    def _load_analytics():
        if not ANALYTICS_PATH.exists():
            return {"counts_by_event": {}, "started": _now()}
        try:
            return json.loads(ANALYTICS_PATH.read_text(encoding="utf-8"))
        except Exception:
            return {"counts_by_event": {}, "started": _now()}

    def _save_analytics(d):
        ANALYTICS_PATH.write_text(json.dumps(d, indent=2), encoding="utf-8")

    @router.post("/wallet/analytics")
    def record_analytics(body: dict = Body(...)):
        """Counter-only. No PII, no IP, no session id stored. Caller dedupes per session client-side."""
        ev = body.get("event")
        VALID_EVENTS = {"page_view", "amount_picked", "send_clicked", "send_confirmed", "reminder_downloaded"}
        if ev not in VALID_EVENTS:
            raise HTTPException(400, f"Invalid event. One of: {sorted(VALID_EVENTS)}")
        a = _load_analytics()
        a.setdefault("counts_by_event", {})
        a["counts_by_event"][ev] = a["counts_by_event"].get(ev, 0) + 1
        a["last_at"] = _now()
        _save_analytics(a)
        return {"ok": True, "event": ev, "count": a["counts_by_event"][ev]}

    @router.get("/wallet/analytics")
    def analytics_summary():
        a = _load_analytics()
        c = a.get("counts_by_event", {})
        # Compute conversion funnel
        page = c.get("page_view", 0)
        picked = c.get("amount_picked", 0)
        clicked = c.get("send_clicked", 0)
        confirmed = c.get("send_confirmed", 0)
        def pct(num, den):
            return round((num / den) * 100, 1) if den else 0.0
        return {
            "counts_by_event": c,
            "funnel": {
                "page_view": page,
                "amount_picked": picked,
                "send_clicked": clicked,
                "send_confirmed": confirmed,
                "picked_pct": pct(picked, page),
                "click_pct": pct(clicked, page),
                "conversion_pct": pct(confirmed, page),
            },
            "started": a.get("started"),
            "last_at": a.get("last_at"),
        }

    @router.get("/wallet/help")
    def help_content():
        return {
            "no_wallet_steps": [
                {
                    "step": 1,
                    "title": "Install a self-custodial wallet",
                    "body": "Coinbase Wallet (mobile, self-custodial — NOT the exchange app) is the easiest first wallet. MetaMask, Rainbow, and Frame also work.",
                    "link": "https://www.coinbase.com/wallet",
                },
                {
                    "step": 2,
                    "title": "Get a small amount of USDC on Base",
                    "body": "Coinbase Wallet has a built-in onramp — fund the wallet with a small amount of USDC on the Base network. Other wallets work too; just choose 'Base' as the chain.",
                    "link": "https://www.coinbase.com/wallet",
                },
                {
                    "step": 3,
                    "title": "Send a one-time test",
                    "body": "Try sending $1 first to verify the address. Once it lands, send your real amount. Done.",
                    "link": None,
                },
            ],
            "supported_wallets": [
                "Coinbase Wallet (self-custodial mobile app)",
                "MetaMask",
                "Rainbow",
                "Frame",
                "Rabby",
                "Trust Wallet",
                "Brave Wallet",
            ],
            "standing_principles": [
                "We never see your keys or seed phrase.",
                "We never custody your funds.",
                "We do not process credit cards — on principle.",
                "Every contribution is voluntary; you can stop the flow anytime by not signing the next transaction.",
                "Every transaction is verifiable on-chain at the operator's published address.",
            ],
            "contact": "partnerships@narrowhighway.com",
        }

    return router
