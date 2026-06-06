"""The Didache — the Church's oldest discernment, brought into the floor.

The Didache ("The Teaching of the Twelve Apostles," c. 50-120 AD) is the
earliest Christian church-manual: the Two Ways, the prayers, the breaking of
bread, and — what we draw on here — the protocol for testing teachers and
prophets. It is not Canon; Scripture is the fixed floor. The Didache is the
first and best of the wisdom sewn through history — the BROTHERS layer, a
second witness standing WITH Scripture, never over it.

This module ties each of the four gates to BOTH:
  • its Scripture anchor (the floor, primary), and
  • its Didache witness (the Church's oldest application of the same test).

So the engine's testing stands openly in the company of the testing the
Church has done since the beginning. Texts are public domain (KJV; the
Roberts–Donaldson rendering of the Didache).
"""
from __future__ import annotations
from typing import Any, Dict

# ── The four gates, each grounded in Scripture and witnessed by the Didache ──
GATE_ANCHORS: Dict[str, Dict[str, Any]] = {
    "RED": {
        "asks": "Aligned with the words of Jesus? Known by fruit, not by claim.",
        "scripture": {
            "ref": "Matthew 7:16",
            "text": "Ye shall know them by their fruits.",
            "also": ["1 John 4:1", "Matthew 7:15-20"],
        },
        "didache": {
            "ref": "Didache 11:8",
            "text": "Not everyone who speaks in the Spirit is a prophet, but only "
                    "if he holds the ways of the Lord. From their ways the false "
                    "prophet and the true prophet shall be known.",
            "also": "Didache 11:12 — whoever says in the Spirit, 'Give me money,' "
                    "you shall not listen to him.",
        },
    },
    "FLOOR": {
        "asks": "Does it keep the Way of Life, and not the way of death?",
        "scripture": {
            "ref": "Deuteronomy 30:19",
            "text": "I have set before you life and death... therefore choose life.",
            "also": ["Matthew 7:13-14"],
        },
        "didache": {
            "ref": "Didache 1:1",
            "text": "There are two ways, one of life and one of death, and there is "
                    "a great difference between the two ways.",
        },
    },
    "BROTHERS": {
        "asks": "Do at least two witnesses affirm it?",
        "scripture": {
            "ref": "Deuteronomy 19:15",
            "text": "At the mouth of two or three witnesses shall the matter be established.",
            "also": ["Matthew 18:16", "2 Corinthians 13:1"],
        },
        "didache": {
            "ref": "Didache 12:1",
            "text": "Let everyone who comes in the name of the Lord be received; "
                    "but afterward prove and know him.",
        },
    },
    "GOD": {
        "asks": "Has it endured the waiting? Time is the witness; nothing is rushed.",
        "scripture": {
            "ref": "Matthew 24:13",
            "text": "He that shall endure unto the end, the same shall be saved.",
            "also": ["Matthew 24:42", "James 5:7"],
        },
        "didache": {
            "ref": "Didache 16:1",
            "text": "Watch over your life; let your lamps not be quenched... be ready, "
                    "for you know not the hour in which our Lord comes.",
            "also": "Didache 11:5 — a prophet who stays three days is a false prophet "
                    "(time tries the spirit).",
        },
    },
}

# ── The founding passages — the witness text itself (public domain) ──────────
FOUNDING_PASSAGES = [
    {"ref": "Didache 1:1", "title": "The Two Ways",
     "text": "There are two ways, one of life and one of death, and there is a "
             "great difference between the two ways."},
    {"ref": "Didache 1:2", "title": "The Way of Life",
     "text": "The way of life is this: first, you shall love God who made you; "
             "second, your neighbor as yourself; and whatever you would not have "
             "done to you, do not do to another."},
    {"ref": "Didache 11:8", "title": "Testing the teacher",
     "text": "Not everyone who speaks in the Spirit is a prophet, but only if he "
             "holds the ways of the Lord. From their ways the false prophet and the "
             "true prophet shall be known."},
    {"ref": "Didache 16:1", "title": "Watch",
     "text": "Watch over your life; let your lamps not be quenched, nor your loins "
             "unloosed; but be ready, for you know not the hour in which our Lord comes."},
]


def gate_anchor(gate: str) -> Dict[str, Any]:
    """Return the Scripture + Didache grounding for a gate (RED/FLOOR/BROTHERS/GOD)."""
    return GATE_ANCHORS.get((gate or "").upper(), {})


def witness() -> Dict[str, Any]:
    """The founding-witness payload: the Didache's standing under the floor."""
    return {
        "name": "The Didache (Teaching of the Twelve Apostles)",
        "dated": "c. 50-120 AD",
        "standing": "Not Canon. The earliest application of the Lord's words — "
                    "the BROTHERS layer, a second witness beneath Scripture, never over it.",
        "passages": FOUNDING_PASSAGES,
        "gates": GATE_ANCHORS,
    }
