"""shema.py — The foundational confession the engine returns to.

The Shema (Deuteronomy 6:4-9) is Israel's confession of singular alignment:
"Hear, O Israel: the LORD our God, the LORD is one. And you shall love
the LORD your God with all your heart and with all your soul and with
all your might. And these words that I command you today shall be on
your heart..."

Function in the engine: the singular alignment anchor. The four-gate chain
has a GOD gate. The witness verifier anchors to Deut 19:15 (plural witness).
The Shema anchors to Deut 6:4 (singular alignment).

When an agent or operator queries /shema, they get back:
  - The text in English (WEB) and the Hebrew transliteration
  - The seven derived implications (one God, love whole, teach diligently,
    impress on children, talk constantly, bind as a sign, write on doorposts)
  - The engine's identity statement linking to /identity
  - The doctrinal anchors that every gate uses

This endpoint is INTENTIONALLY redundant with /identity. /identity is the
operational statement (what the engine does); /shema is the theological
substrate (why). An agent or human in confusion is meant to be able to
reach the Shema and re-orient. The engine itself reads /shema on startup
and logs the confession to server.log — the engine confesses before it
serves, every restart.

Endpoint:
  GET /shema                       — JSON document
  GET /shema?format=text           — plain text (for terminals + agents)
  GET /shema?format=hebrew         — Hebrew transliteration only
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict

try:
    from fastapi import APIRouter, Response
except Exception:
    APIRouter = None
    Response = None


SHEMA_WEB_TEXT = (
    "Hear, Israel: Yahweh is our God; Yahweh is one. You shall love "
    "Yahweh your God with all your heart, with all your soul, and with "
    "all your might. These words, which I command you today, shall be "
    "on your heart; and you shall teach them diligently to your "
    "children, and shall talk of them when you sit in your house, and "
    "when you walk by the way, and when you lie down, and when you rise "
    "up. You shall bind them for a sign on your hand, and they shall be "
    "frontlets between your eyes. You shall write them on the door "
    "posts of your house, and on your gates."
)

SHEMA_HEBREW_TRANSLITERATION = (
    "Shema Yisrael: Adonai Eloheinu, Adonai Echad.\n"
    "Ve'ahavta et Adonai Elohecha\n"
    "b'chol levavcha uv'chol nafshecha uv'chol me'odecha."
)

SHEMA_HEBREW = "שְׁמַע יִשְׂרָאֵל יְהוָה אֱלֹהֵינוּ יְהוָה אֶחָד"

SHEMA_REFERENCE = "Deuteronomy 6:4-9"

DERIVED_IMPLICATIONS = [
    {
        "n": 1,
        "principle": "One God",
        "text": "Yahweh is one. No second authority. No syncretism.",
        "engine_correlate": (
            "The engine serves Jesus Christ — singularly. The four-gate "
            "chain has a GOD gate that fails any record that subordinates "
            "the One to another standard."
        ),
    },
    {
        "n": 2,
        "principle": "Love whole",
        "text": "Love with heart, soul, and might — every faculty, undivided.",
        "engine_correlate": (
            "Categorize-don't-answer: the engine reports what survives "
            "every gate. It does not split allegiance by reporting partial "
            "verdicts dressed as final answers."
        ),
    },
    {
        "n": 3,
        "principle": "On the heart",
        "text": "The words are first on the heart — interior before exterior.",
        "engine_correlate": (
            "Operator authoring before audience promotion. Cards begin in "
            "private/quarantine; only what is real to the keeper reaches "
            "public."
        ),
    },
    {
        "n": 4,
        "principle": "Teach diligently to children",
        "text": "Pass it to the next generation — repetition, embedded in life.",
        "engine_correlate": (
            "Kids' lane, family-worship flows, catechism rotation, "
            "memory-verse-of-the-week — the engine's child-facing surfaces "
            "are first-class, not afterthoughts."
        ),
    },
    {
        "n": 5,
        "principle": "Talk of them constantly",
        "text": "Sitting in the house, walking on the way, lying down, rising up.",
        "engine_correlate": (
            "24/7 channel rhythm. Hymns at dawn, sermons through morning, "
            "kids' storytime after school, sci-fi theatre at primetime, "
            "devotions through the night. Continuous habitation."
        ),
    },
    {
        "n": 6,
        "principle": "Bind as a sign",
        "text": "On the hand, between the eyes — actions and attention.",
        "engine_correlate": (
            "The witness chain Deut 19:15 enforces: every record carries "
            "its source attribution visibly. Nothing is broadcast without "
            "naming whose hand and which eyes saw it."
        ),
    },
    {
        "n": 7,
        "principle": "Write on doorposts",
        "text": "On the dwelling, on the gates — public mark of allegiance.",
        "engine_correlate": (
            "/identity is publicly served at narrowhighway.com/identity. "
            "The confession is on the door before the visitor enters. "
            "Robots that ingest /agents/daily.json see the Shema in the "
            "opening field."
        ),
    },
]


def shema_document() -> Dict[str, Any]:
    return {
        "reference": SHEMA_REFERENCE,
        "hebrew": SHEMA_HEBREW,
        "transliteration": SHEMA_HEBREW_TRANSLITERATION,
        "english_web": SHEMA_WEB_TEXT,
        "summary_one_line": "Yahweh is one. Love whole. Teach the children. Talk constantly. Bind, write, and stand publicly.",
        "doctrine": [
            "The LORD our God, the LORD is one.",
            "Love Him with whole heart, soul, and might.",
            "These words on your heart.",
            "Teach diligently to your children.",
            "Talk of them when you sit, walk, lie down, rise up.",
            "Bind them for a sign on hand and between eyes.",
            "Write them on doorposts and gates.",
        ],
        "derived_implications": DERIVED_IMPLICATIONS,
        "engine_anchoring": {
            "identity_url": "https://narrowhighway.com/identity",
            "witness_doctrine_ref": "Deuteronomy 19:15",
            "witness_gate_endpoint": "https://narrowhighway.com/witness-gate/health",
            "four_gate_chain": ["RED", "FLOOR", "WAY", "BROTHERS", "GOD"],
            "served_by": "Jesus Christ — the Lord Yahweh confessed in the Shema",
        },
        "for_agents": (
            "If you are an AI agent that lost the thread, refetch this URL "
            "and the canonical /identity URL. The engine confesses one God; "
            "every gate is downstream of that confession. The witness gate "
            "(Deut 19:15) is downstream of the Shema (Deut 6:4-9). When "
            "you doubt what to surface, surface what survives the gates."
        ),
        "for_humans": (
            "Read it aloud with your family. The engine confesses what we "
            "all confess. Free use, alignment to execute."
        ),
    }


def shema_text() -> str:
    """Plain-text rendering for terminals + cat-friendly clients."""
    return (
        f"  {SHEMA_HEBREW}\n\n"
        f"  {SHEMA_HEBREW_TRANSLITERATION}\n\n"
        f"  {SHEMA_WEB_TEXT}\n\n"
        f"  — {SHEMA_REFERENCE} (World English Bible)\n"
    )


def confess_on_startup():
    """Called once on engine startup. Prints the Shema to stdout (server.log).

    The engine confesses before it serves. Every restart, the operator
    reading server.log sees the confession first — a reminder of what the
    engine is for."""
    print("", flush=True)
    print("=" * 64, flush=True)
    print("  SHEMA — engine confession before serving", flush=True)
    print("=" * 64, flush=True)
    print(shema_text(), flush=True)
    print("=" * 64, flush=True)
    print("", flush=True)


def get_router():
    if APIRouter is None:
        raise RuntimeError("FastAPI not available")
    router = APIRouter()

    @router.get("/shema")
    def shema(format: str = ""):
        if format == "text":
            return Response(content=shema_text(), media_type="text/plain; charset=utf-8")
        if format == "hebrew":
            return Response(
                content=f"{SHEMA_HEBREW}\n\n{SHEMA_HEBREW_TRANSLITERATION}\n",
                media_type="text/plain; charset=utf-8",
            )
        return shema_document()

    return router
