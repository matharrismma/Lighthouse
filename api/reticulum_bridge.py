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
from typing import Any, Dict, Optional

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
    destination.announce()
    RNS.log("Concordance is answering on Reticulum at " + RNS.prettyhexrep(destination.hash))

    import time
    while True:  # keep the stack alive; re-announce periodically so peers find us
        time.sleep(300)
        try:
            destination.announce()
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
    args = ap.parse_args()
    if args.simulate:
        print(json.dumps(simulate(args.simulate, max_bytes=args.max_bytes,
                                  allow_draft=not args.no_draft),
                         ensure_ascii=False, indent=2))
    else:
        serve(max_bytes=args.max_bytes, identity_path=args.identity,
              allow_draft=not args.no_draft)
