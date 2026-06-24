"""reticulum_bridge.py — reach the Concordance engine over LoRa, via Reticulum.

The honest architecture (see the long answer in the session): you cannot run the
engine ON a LoRa radio (a Meshtastic/RNode node is a microcontroller). You CAN
put the engine BEHIND the radio — a cheap offline computer (a Pi, an old phone, a
mini-PC; solar-capable) runs the sovereign engine, attaches to an RNode LoRa
radio, and answers the mesh. The mesh carries the question in and a compact,
verifiable answer out. No internet. No provider. For the people who help people
when the grid is gone.

Two integrity layers, both real and honest:
  1. TRANSPORT — Reticulum encrypts end-to-end and cryptographically authenticates
     the answering station's identity. The mesh cannot forge a reply from us.
  2. CONTENT — every answer carries a pull-ref (/c/<id>) and, when the card has
     one, a seal hash, so the content itself can be verified later against the
     keeping. We never claim more integrity than we actually provide.

This module is split so the part that matters is testable with NO hardware and NO
Reticulum installed:
  * compose_reply(query)  — the BRAIN. Sovereign (corpus + the crisis net, no
    oracle/LLM), deterministic, byte-budgeted. Verified now, in simulation.
  * serve(...)            — the RNS wiring. Import-guarded; written to the
    Reticulum API, to be hardware-verified on a real RNode by the operator.

Christ first: the crisis net runs FIRST, before any routing. The tool is the
connector, never the source.

Sovereign: stdlib + the engine (api.cards, api.safety). Reticulum (`rns`) is an
OPTIONAL dependency, needed only to actually transmit.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

DEFAULT_MAX_BYTES = 600  # the link is slow; keep replies small. Tune on real hardware.

# The drafting posture — brief, honest, and Christ-first. Used ONLY by the local
# model (sovereign, offline), only as the last resort below verified content.
_DRAFT_SYS = (
    "You are a brief, honest helper answering over a slow radio link. Reply in 1-2 short, "
    "plain sentences — plain text only, no markdown. Be TRUE; if you are unsure or it is "
    "genuinely debated, say so plainly. You are a tool, not an authority: on ultimate "
    "questions (God, meaning, suffering, death, right and wrong) point toward Christ, "
    "Scripture, and real people (a pastor, a church) as the source — never position "
    "yourself as the final word."
)


def _fit(s: str, max_bytes: int) -> str:
    """Truncate a string to fit a UTF-8 byte budget on a character boundary."""
    b = s.encode("utf-8")
    if len(b) <= max_bytes:
        return s
    cut = b[:max_bytes]
    while cut and (cut[-1] & 0xC0) == 0x80:  # don't split a multibyte char
        cut = cut[:-1]
    return cut.decode("utf-8", "ignore")


def _cap(reply: str, ref: str, max_bytes: int) -> str:
    """Fit reply + a pull-ref tail inside the byte budget, honestly marking a cut."""
    if ref:
        tail = "  …full: " + ref
        if len((reply + tail).encode("utf-8")) > max_bytes:
            reply = _fit(reply, max(0, max_bytes - len(tail.encode("utf-8"))))
            return (reply.rstrip() + tail)
        full = reply if len(reply.encode("utf-8")) <= max_bytes else _fit(reply, max_bytes)
        return full
    return _fit(reply, max_bytes)


def _draft(query: str, max_bytes: int) -> Optional[str]:
    """A SHORT answer from the LOCAL model ONLY (Ollama / qwen2.5:3b) — sovereign,
    offline, never a paid API. Returns None when the local model isn't up. The
    honest last resort, below verified content."""
    try:
        from api import local_llm
        if not local_llm.available():
            return None
        out = local_llm.generate(query, system=_DRAFT_SYS, max_tokens=110,
                                 temperature=0.3)
    except Exception:  # noqa: BLE001
        return None
    if not out or not out.strip():
        return None
    return " ".join(out.split())


def compose_reply(query: str, max_bytes: int = DEFAULT_MAX_BYTES,
                  allow_draft: bool = True) -> Dict[str, Any]:
    """The bridge brain: a question over the mesh → a compact answer. Order:
    crisis-net first → the VERIFIED keeping (preferred) → a checkable claim is
    routed to the verifier → only then, if allowed, a LOCAL-model draft (flagged
    not-verified) → else an honest miss. allow_draft=False = pure-lookup mode."""
    q = (query or "").strip()
    if not q:
        return {"mode": "empty", "reply": "Send a word and I'll search the keeping.",
                "query": q, "bytes": 0}

    # 1) CRISIS — deterministic and FIRST. The only honest reply is real help.
    try:
        from api import safety as _safety
        c = _safety.crisis_check(q)
        if c:
            lines = []
            for r in (c.get("resources") or [])[:2]:
                act, nm = r.get("action", ""), r.get("name", "")
                lines.append((act + " — " + nm).strip(" —"))
            reply = "You matter, and you are not alone. Reach a person now: " + \
                    " | ".join(lines) if lines else \
                    "You matter. Call or text 988 (US) now, or a local crisis line."
            return {"mode": "safety", "reply": _fit(reply, max_bytes),
                    "query": q, "bytes": len(_fit(reply, max_bytes).encode("utf-8"))}
    except Exception:  # noqa: BLE001 — a detector failure must never break the bridge
        pass

    # 2) ANSWER from the keeping — deterministic full-text over the whole corpus.
    hit = None
    try:
        from api.cards import corpus_search
        hits = corpus_search(q, limit=1)
        hit = hits[0] if hits else None
    except Exception:  # noqa: BLE001
        hit = None

    # Relevance floor — never present a weak match as the answer (the same guard
    # the sorter uses). "is 17 prime" must NOT come back as a card about "number".
    if hit:
        try:
            from api.sorter import _relevant
            if not _relevant(q, hit):
                hit = None
        except Exception:  # noqa: BLE001
            pass

    if hit:
        cid = str(hit.get("id") or "")
        title = (hit.get("title") or cid).strip()
        body = " ".join((hit.get("body") or "").split())
        ref = "/c/" + cid
        src = hit.get("source") or {}
        seal = (src.get("seal") if isinstance(src, dict) else None) or hit.get("seal")
        core = (title + " — " + body).strip(" —") if body else title
        reply = _cap(core, ref, max_bytes)
        out: Dict[str, Any] = {"mode": "answer", "reply": reply, "ref": ref,
                               "source": "the keeping", "query": q,
                               "bytes": len(reply.encode("utf-8"))}
        if seal:
            out["seal_ref"] = seal  # content-verifiable later; only when real
        return out

    # 3) No verified card in the keeping. A checkable claim is pointed at the
    # verifier (deterministic, offline) — never drafted, never faked.
    ql = q.lower()
    if any(w in ql for w in ("calculate", "compute", "how many", "how much",
                             "prime", "percent", "equation", "convert", "=",
                             "square root", "probability", " times ")):
        reply = ("Checkable claim — the engine verifies these deterministically. "
                 "Send the structured claim to the verifier.")
        return {"mode": "verify", "reply": _fit(reply, max_bytes), "query": q,
                "bytes": len(_fit(reply, max_bytes).encode("utf-8"))}

    # 3b) DRAFT with the LOCAL model — sovereign, offline, the last resort. Marked
    # "(draft)" on the wire so a recipient is never misled: this is generated, not
    # verified. The deterministic/verified paths above always win.
    if allow_draft:
        d = _draft(q, max_bytes)
        if d:
            prefix = "(draft) "
            room = max(0, max_bytes - len(prefix.encode("utf-8")))
            reply = prefix + _fit(d, room)
            return {"mode": "draft", "reply": reply, "drafted": True,
                    "verified": False,
                    "note": "drafted by a local model — not verified", "query": q,
                    "bytes": len(reply.encode("utf-8"))}

    # 3c) Honest miss — never invented.
    reply = ("No verified card in the keeping matches that yet. Bring it to the "
             "Walk to verify or weigh it.")
    return {"mode": "miss", "reply": _fit(reply, max_bytes), "query": q,
            "bytes": len(_fit(reply, max_bytes).encode("utf-8"))}


# ── Reticulum transport (optional dependency; hardware-verified by the operator) ──
# ── Verified bulletins over the mesh: publish → broadcast the seal-ref → serve
#    the full bundle on request → recipient verifies OFFLINE (api/bulletin.py). ──
_BULLETIN_DIR = Path(__file__).parent.parent / "data" / "bulletins"
_BULLETIN_FILE = _BULLETIN_DIR / "published.jsonl"
_BULLETINS: Dict[str, Dict[str, Any]] = {}  # ref -> {ref, bundle, issued_at}
_BULLETINS_LOADED = False
ANNOUNCE_MAX = 200  # the seal-ref (+short title) must fit a small broadcast


def _load_bulletins() -> None:
    global _BULLETINS_LOADED
    if _BULLETINS_LOADED:
        return
    _BULLETINS_LOADED = True
    try:
        if _BULLETIN_FILE.exists():
            for line in _BULLETIN_FILE.read_text("utf-8", "replace").splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    rec = json.loads(line)
                except Exception:  # noqa: BLE001
                    continue
                if rec.get("ref"):
                    _BULLETINS[rec["ref"]] = rec
    except Exception:  # noqa: BLE001
        pass


def announce_app_data(ref: str, title: str = "") -> bytes:
    """The bytes broadcast on the mesh: the one-packet seal-ref, plus a short
    title after a tab, capped so it fits a small Reticulum announce."""
    title = " ".join((title or "").split())
    blob = ref if not title else (ref + "\t" + title)
    return _fit(blob, ANNOUNCE_MAX).encode("utf-8")


def parse_announce_app_data(data: Any) -> Dict[str, str]:
    """Peer side: recover {ref, title} from a received announce's app_data."""
    try:
        s = data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else str(data or "")
    except Exception:  # noqa: BLE001
        return {"ref": "", "title": ""}
    ref, _, title = s.partition("\t")
    return {"ref": ref.strip(), "title": title.strip()}


def publish_bulletin(text: str, kind: str = "bulletin") -> Dict[str, Any]:
    """Publish a verified bulletin from this station: sign + content-address it
    (api.bulletin), store it so peers can fetch it by ref, and return the seal-ref
    + the app_data to broadcast. The actual over-the-air announce happens in
    serve()'s loop (hardware-pending)."""
    from api import bulletin as _b
    out = _b.publish(text, kind=kind)
    bundle = out["bundle"]
    rec = {"ref": out["ref"], "bundle": bundle,
           "issued_at": int(bundle.get("issued_at", 0) or 0)}
    _load_bulletins()
    _BULLETINS[rec["ref"]] = rec
    try:
        _BULLETIN_DIR.mkdir(parents=True, exist_ok=True)
        with open(_BULLETIN_FILE, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    except Exception:  # noqa: BLE001
        pass
    app = announce_app_data(out["ref"], bundle.get("text", ""))
    return {"ref": out["ref"], "ref_short": out["ref_short"], "bytes": out["bytes"],
            "app_data": app.decode("utf-8", "replace"),
            "app_data_bytes": len(app), "stored": True}


def get_bulletin(ref: str) -> Optional[Dict[str, Any]]:
    """The full signed bundle for a seal-ref, or None — what serve() returns when
    a peer requests /bulletin with a ref."""
    _load_bulletins()
    rec = _BULLETINS.get((ref or "").strip())
    return rec["bundle"] if rec else None


def list_bulletins(limit: int = 20) -> List[Dict[str, Any]]:
    _load_bulletins()
    items = sorted(_BULLETINS.values(), key=lambda r: r.get("issued_at", 0), reverse=True)
    return [{"ref": r["ref"], "issued_at": r.get("issued_at", 0),
             "text": (r["bundle"].get("text", "") or "")[:80]} for r in items[:limit]]


def simulate_broadcast(text: str, kind: str = "bulletin") -> Dict[str, Any]:
    """Prove the WHOLE distribution round-trip with NO radio: publish → the bytes
    that would be broadcast → a peer recovers the ref → fetches the bundle by ref
    → verifies it OFFLINE. The RNS transport in serve() is the only hardware-
    pending part; this proves everything around it."""
    pub = publish_bulletin(text, kind=kind)
    parsed = parse_announce_app_data(pub["app_data"].encode("utf-8"))
    ref = parsed["ref"]
    bundle = get_bulletin(ref)
    from api import bulletin as _b
    own = bundle.get("_instance_pubkey") if bundle else None
    v = (_b.verify(bundle, ref=ref, pubkey=own) if bundle
         else {"unaltered": False, "authentic": False})
    return {
        "broadcast_app_data": pub["app_data"],
        "app_data_bytes": pub["app_data_bytes"],
        "peer_received_ref": ref,
        "peer_received_title": parsed["title"],
        "bundle_fetched_by_ref": bundle is not None,
        "verify": {"unaltered": v.get("unaltered"), "authentic": v.get("authentic")},
    }


def serve(config_dir: Optional[str] = None, max_bytes: int = DEFAULT_MAX_BYTES,
          identity_path: Optional[str] = None, allow_draft: bool = True) -> None:
    """Stand up the Concordance answering destination on Reticulum and serve the
    mesh. Requires `rns` and (for LoRa) an RNode interface configured in your
    Reticulum config. Run this ON the base station (the computer behind the radio).

    NOTE: written to the Reticulum API; to be verified on a real RNode by the
    operator (no radio is attached where this was authored). The request-handler
    signature is kept tolerant across rns versions."""
    try:
        import RNS  # pip install rns
    except ImportError as e:  # noqa: BLE001
        raise RuntimeError(
            "Reticulum is not installed. On the base station: `pip install rns`, "
            "configure an RNode (LoRa) interface in ~/.reticulum/config, then run "
            "this. The radio carries the mesh; THIS computer runs the engine."
        ) from e

    reticulum = RNS.Reticulum(config_dir)  # noqa: F841 — must stay alive

    if identity_path:
        try:
            identity = RNS.Identity.from_file(identity_path)
        except Exception:  # noqa: BLE001
            identity = RNS.Identity()
            identity.to_file(identity_path)
    else:
        identity = RNS.Identity()

    destination = RNS.Destination(
        identity, RNS.Destination.IN, RNS.Destination.SINGLE,
        "concordance", "answer",
    )
    destination.set_proof_strategy(RNS.Destination.PROVE_ALL)

    def _handler(path, data, request_id, *args):  # tolerant signature across versions
        try:
            q = data.decode("utf-8") if isinstance(data, (bytes, bytearray)) else str(data or "")
        except Exception:  # noqa: BLE001
            q = ""
        rep = compose_reply(q, max_bytes=max_bytes, allow_draft=allow_draft)
        return json.dumps(rep, ensure_ascii=False).encode("utf-8")

    destination.register_request_handler(
        "/ask", response_generator=_handler, allow=RNS.Destination.ALLOW_ALL,
    )

    # A second destination for verified bulletins: peers request /bulletin with a
    # seal-ref and get the full signed bundle back (then verify it OFFLINE). The
    # seal-ref itself is broadcast in the announce app_data below.
    bulletin_dest = RNS.Destination(
        identity, RNS.Destination.IN, RNS.Destination.SINGLE,
        "concordance", "bulletin",
    )
    bulletin_dest.set_proof_strategy(RNS.Destination.PROVE_ALL)

    def _bulletin_handler(path, data, request_id, *args):
        try:
            ref = (data.decode("utf-8") if isinstance(data, (bytes, bytearray))
                   else str(data or "")).strip()
        except Exception:  # noqa: BLE001
            ref = ""
        b = get_bulletin(ref)
        if b is None:
            latest = list_bulletins(limit=1)
            b = get_bulletin(latest[0]["ref"]) if latest else None
        return json.dumps(b or {"error": "no such bulletin"},
                          ensure_ascii=False).encode("utf-8")

    bulletin_dest.register_request_handler(
        "/bulletin", response_generator=_bulletin_handler,
        allow=RNS.Destination.ALLOW_ALL,
    )

    destination.announce()
    bulletin_dest.announce()
    RNS.log("Concordance is answering on Reticulum at " + RNS.prettyhexrep(destination.hash))
    RNS.log("Bulletins announced from " + RNS.prettyhexrep(bulletin_dest.hash))

    import time
    while True:  # keep the stack alive; re-announce so peers find us + the bulletins
        time.sleep(300)
        try:
            destination.announce()
            latest = list_bulletins(limit=1)
            if latest:
                bulletin_dest.announce(
                    app_data=announce_app_data(latest[0]["ref"], latest[0]["text"]))
            else:
                bulletin_dest.announce()
        except Exception:  # noqa: BLE001
            pass


def simulate(query: str, max_bytes: int = DEFAULT_MAX_BYTES,
             allow_draft: bool = True) -> Dict[str, Any]:
    """Prove the round-trip with NO radio and NO Reticulum: query in → the exact
    bytes the mesh peer would receive back."""
    return compose_reply(query, max_bytes=max_bytes, allow_draft=allow_draft)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Concordance over Reticulum/LoRa")
    ap.add_argument("--simulate", metavar="QUERY", help="test the brain with no radio")
    ap.add_argument("--max-bytes", type=int, default=DEFAULT_MAX_BYTES)
    ap.add_argument("--identity", help="path to persist the station identity")
    ap.add_argument("--no-draft", action="store_true",
                    help="pure-lookup mode: never use the local model to draft")
    ap.add_argument("--publish-bulletin", metavar="TEXT",
                    help="publish a verified bulletin + show the seal-ref to broadcast")
    ap.add_argument("--list-bulletins", action="store_true",
                    help="list bulletins this station has published")
    ap.add_argument("--simulate-broadcast", metavar="TEXT",
                    help="prove publish→broadcast→fetch→verify-offline with no radio")
    args = ap.parse_args()
    if args.simulate:
        print(json.dumps(simulate(args.simulate, max_bytes=args.max_bytes,
                                  allow_draft=not args.no_draft),
                         ensure_ascii=False, indent=2))
    elif args.publish_bulletin:
        print(json.dumps(publish_bulletin(args.publish_bulletin),
                         ensure_ascii=False, indent=2))
    elif args.list_bulletins:
        print(json.dumps(list_bulletins(), ensure_ascii=False, indent=2))
    elif args.simulate_broadcast:
        print(json.dumps(simulate_broadcast(args.simulate_broadcast),
                         ensure_ascii=False, indent=2))
    else:
        serve(max_bytes=args.max_bytes, identity_path=args.identity,
              allow_draft=not args.no_draft)
