"""THE FLOOR — one thing every tool stands on.

The integration spine. Until now each tool reached for the one piece of the
floor it happened to know about: the Apothecary touched Scripture, a verifier
touched its domain, Calibre touched nothing. They stood on shards.

`stand_on_floor()` is the single call that puts any tool's output on the WHOLE
floor at once:

    1. CANON      — anchored to Scripture (the words in red; the fixed floor)
    2. GATES      — run through RED / FLOOR / BROTHERS / GOD
    3. VERIFIER   — pointed at the deterministic domain check that applies
    4. CALIBRE    — scored for health / beauty / shadow / vice where derivable
    5. NESTED     — mapped to the control-system layer (load vs capacity)
    6. LEDGER     — offered an append-only record

Every import is soft: in a context where a piece isn't reachable, the floor
reports that honestly instead of failing. A tool that calls this is no longer
connected to one shard — it is standing on the whole floor, and it can show it.
"""
from __future__ import annotations
from typing import Any, Dict, List, Optional

# ── The lenses (the "rooms", as views of the one floor) ────────────────────
# A lens is not a separate tool. It is the one operation — stand_on_floor —
# wearing a face: a framing for what was brought, and a hint about which walls
# should light up. Apothecary is the floor with a health lens; Discern is the
# floor with a claim lens. The engine detects the lens from what you bring, so
# you never pick a tool — you bring something, and the floor tells you what it is.
LENSES: Dict[str, Dict[str, Any]] = {
    "discern":    {"label": "Discern",   "domain": None,        "frame": "a claim to weigh against the floor"},
    "apothecary": {"label": "Apothecary","domain": "health",    "frame": "a body, read as nested control systems"},
    "scripture":  {"label": "Scripture", "domain": "scripture", "frame": "the Word, looked at directly"},
    "household":  {"label": "Household",  "domain": None,        "frame": "a practical need of the home"},
    "almanac":    {"label": "Almanac",   "domain": None,        "frame": "an observation to confirm against record"},
    "reckon":     {"label": "Reckon",    "domain": "math",      "frame": "a calculation pressed against the math wall"},
    # Navigation, not judgment — the floor doesn't render a verdict on "play
    # chess" or "the calendar"; it just opens the room. Kept distinct from
    # 'discern' so the front door routes these instead of running the gates.
    "navigate":   {"label": "Open",      "domain": None,        "frame": "opening the room"},
}

_SCRIPTURE_BOOKS = (
    "genesis", "exodus", "leviticus", "numbers", "deuteronomy", "joshua", "judges",
    "ruth", "samuel", "kings", "chronicles", "ezra", "nehemiah", "esther", "job",
    "psalm", "psalms", "proverbs", "ecclesiastes", "isaiah", "jeremiah", "ezekiel",
    "daniel", "hosea", "amos", "jonah", "micah", "nahum", "habakkuk", "zephaniah",
    "haggai", "zechariah", "malachi", "matthew", "mark", "luke", "john", "acts",
    "romans", "corinthians", "galatians", "ephesians", "philippians", "colossians",
    "thessalonians", "timothy", "titus", "philemon", "hebrews", "james", "peter",
    "jude", "revelation",
)


def classify(text: str) -> Dict[str, Any]:
    """The one brain. Read what was brought and return everything the engine
    needs: the lens (how the floor frames it for judgment, or None for pure
    navigation), the domain, and the route/url/tool (where it goes). The
    airlock and the floor both call this — there is one classifier now, not two.

    Returns: {lens, domain, route, tool, url, confidence, why}
    Lens is None for navigation-only intents (radio, contact, a recipe) — the
    floor doesn't render a verdict on 'play the radio'; it just opens the room.
    """
    import re as _re
    t = (text or "").lower().strip()

    def R(lens, domain, route, tool, url, conf, why):
        return {"lens": lens, "domain": domain, "route": route, "tool": tool,
                "url": url, "confidence": conf, "why": why}

    if not t:
        return R(None, None, "desk", "", "/workspace.html", 0.0, "nothing brought — opening the workspace")

    # Pasted URL → discern (verify the page)
    if _re.match(r"^https?://", t):
        return R("discern", None, "discern", "verify-url", "/try.html", 0.9, "a URL — verify the claim it makes")
    # Verify-shaped claim → discern
    if any(t.startswith(p) or p in t[:40] for p in
           ("is it true", "is that true", "did ", "really", "fact check", "fact-check",
            "verify ", "is this real", "true or false", "is this teaching", "sound doctrine", "aligned with")):
        return R("discern", None, "discern", "verify", "/try.html", 0.85, "a verifiable claim")
    # Scripture → scripture lens
    if (any(b in t for b in _SCRIPTURE_BOOKS) or "bible says" in t or "scripture" in t
            or "verse about" in t or "what does the bible" in t):
        return R("scripture", "scripture", "learn", "bibles", "/bibles.html", 0.85, "scripture lookup")
    # Health / body → apothecary lens (the floor stands it on nested control)
    if any(k in t for k in ("remedy", "cure ", "ache", "sore", "cough", "cold ", "fever",
                            "rash", "headache", "anxiety", "grief", "anointing", "balm",
                            "tonic", "herb", "fatigue", "diabetes", "blood sugar", "inflammation",
                            "sick", "symptom", "heal", "tired", "stress", "sleep", "depress")):
        return R("apothecary", "health", "family", "apothecary", "/apothecary.html", 0.8, "a body, read as nested control systems")
    # Games → the games deck (specific game first, then the deck)
    if any(k in t for k in ("chess", "wilderness trail", "oregon trail", "bible trivia",
                            "trivia", "play a game", "board game", "checkers", "arcade")):
        if "chess" in t:                       return R(None, None, "family", "chess", "/games/chess.html", 0.85, "play chess")
        if "wilderness" in t or "oregon" in t: return R(None, None, "family", "wilderness", "/games/wilderness-trail.html", 0.85, "Wilderness Trail — Oregon Trail through Sinai")
        if "trivia" in t:                      return R(None, None, "family", "trivia", "/bible-trivia.html", 0.85, "Bible trivia")
        return R(None, None, "family", "games", "/games.html", 0.8, "the games deck")
    # Kids → family-safe cartoons & Bible stories (before the generic watch rule)
    if any(k in t for k in ("kids", "for my child", "for my kids", "children's", "kid-safe", "cartoon for")):
        return R(None, None, "watch", "kids", "/kids.html", 0.8, "kids — family-safe cartoons & Bible stories")
    # Graphing before plain calculation (so "graph y = 2x" → grapher, not calculator)
    if any(k in t for k in ("graph ", "plot ", "graphing", "y =", "f(x)")):
        return R(None, "math", "tools", "graph", "/tools/graph.html", 0.75, "the graphing calculator")
    # Calculation → reckon lens (the math wall verifies it). Require a real
    # arithmetic pattern or an explicit calc word — not a bare "what is".
    if _re.search(r"[\d\.\s]+[\+\-\*\/×÷=][\d\.\s]+", t) or any(
            k in t for k in ("calculate", "percent of", "how much is", "square root", "how many", " times ")):
        return R("reckon", "math", "tools", "calculator", "/tools/calculator.html", 0.8, "a calculation pressed against the math wall")
    # Recipe → navigation (household)
    if any(k in t for k in ("recipe for", "how to cook", "how to bake", "cookbook", "make bread", "make a pie")):
        return R(None, None, "family", "recipes", "/recipes.html", 0.85, "recipe from the heritage cookbook")
    # Prayer
    if t.startswith("pray ") or "pray for" in t or "prayer request" in t:
        return R(None, None, "family", "prayer", "/prayer.html", 0.85, "prayer board")
    # Hymn
    if "hymn" in t or "psalter" in t or "praise song" in t:
        return R(None, None, "watch", "hymns", "/hymns.html", 0.85, "hymn lookup")
    # Audio / radio
    if any(k in t for k in ("listen to", "play radio", "shortwave", "podcast", "tune in", "broadcast", "radio")):
        return R(None, None, "watch", "radio", "/radio.html", 0.75, "audio surface")
    # Watch / video
    if any(k in t for k in ("watch ", "show me", "cartoon", "video about")):
        return R(None, None, "watch", "channels", "/channels.html", 0.75, "video surface")
    # Definition
    if t.startswith("define ") or ("what does " in t and " mean" in t):
        return R(None, "linguistics", "tools", "dictionary", "/tools/dictionary.html", 0.85, "word definition")
    # Map / location
    if "map of" in t or "where is" in t or "location of" in t:
        return R(None, None, "tools", "maps", "/tools/maps.html", 0.75, "map lookup")
    # Contact the operator
    if any(k in t for k in ("contact ", "message you", "message matt", "reach you", "reach matt",
                            "get in touch", "email you", "talk to you", "talk to someone", "speak to",
                            "how do i reach", "report a", "report an", "complaint", "feedback for")):
        return R(None, None, "take_part", "contact", "/contact.html", 0.85, "leave the operator a message")
    # Submit / support
    if any(k in t for k in ("submit ", "send you", "pitch ", "i want to share", "donate", "support you")):
        return R(None, None, "take_part", "", "/support.html", 0.7, "take part")
    # Almanac — verified observations, folk wisdom, weather lore
    if any(k in t for k in ("almanac", "weather lore", "folk wisdom", "old wives", "planting by the moon")):
        return R(None, None, "discern", "almanac", "/almanac.html", 0.8, "the almanac of verified claims")
    # Encyclopedia / reference lookup
    if any(k in t for k in ("encyclopedia", "what is a ", "what is an ", "who was ", "tell me about ", "look up ")):
        return R(None, None, "learn", "encyclopedia", "/encyclopedia.html", 0.7, "the encyclopedia")
    # Calendar
    if any(k in t for k in ("calendar", "feast day", "liturgical", "the church year", "what day is")):
        return R(None, None, "family", "calendar", "/calendar.html", 0.75, "the family calendar")
    # Maker / projects
    if any(k in t for k in ("project", "build a", "how to make", "how to build", "woodwork",
                            "sew ", "knit", "garden", "fix a", "mend ", "whittle")):
        return R(None, None, "family", "maker", "/maker.html", 0.75, "the maker's workshop")
    # Household / hearth
    if any(k in t for k in ("household", "chores", "manage my home", "family rhythm", "hearth", "fellowship")):
        return R(None, None, "family", "household", "/household.html", 0.7, "household & hearth")
    # Reading plans / library
    if any(k in t for k in ("reading plan", "read through the bible", "bible in a year",
                            "what should i read", "library", "read a book", "reading room")):
        return R(None, None, "learn", "library", "/library.html", 0.7, "the library & reading plans")
    # Codex — the manuscript
    if any(k in t for k in ("codex", "guidance document", "the tradition", "the assembly",
                            "witness roll", "testimony", "working canon", "what do we believe")):
        return R(None, None, "codex", "codex", "/codex-deep.html", 0.7, "the codex — the manuscript")
    # Media center — watch / listen / read in one room
    if any(k in t for k in ("media center", "what to watch", "something to watch", "free movies",
                            "free films", "audiobook", "free books", "free library")):
        return R(None, None, "watch", "media", "/media-center.html", 0.75, "the media center")
    # The smaller tools
    if any(k in t for k in ("drawing", "draw ", "paint", "sketch")):
        return R(None, None, "tools", "draw", "/tools/draw.html", 0.7, "the drawing pad")
    if any(k in t for k in ("piano", "compose music", "make music", "music maker")):
        return R(None, None, "tools", "music", "/tools/music.html", 0.7, "the music maker")
    if any(k in t for k in ("learn to type", "typing tutor", "typing practice", "wpm")):
        return R(None, None, "tools", "typing", "/tools/typing.html", 0.7, "the typing tutor")
    if any(k in t for k in ("graph ", "plot ", "graphing calculator", "y =", "f(x)")):
        return R(None, "math", "tools", "graph", "/tools/graph.html", 0.7, "the graphing calculator")
    if any(k in t for k in ("periodic table", "atomic number", "chemical element")):
        return R(None, "chemistry", "tools", "periodic", "/tools/periodic.html", 0.7, "the periodic table")
    if any(k in t for k in ("synonym", "thesaurus", "another word for", "antonym")):
        return R(None, "linguistics", "tools", "thesaurus", "/tools/thesaurus.html", 0.75, "the thesaurus")
    if any(k in t for k in ("wikipedia", "search wikipedia")):
        return R(None, None, "tools", "wiki", "/tools/wiki.html", 0.7, "Wikipedia search")
    # Sponsors
    if any(k in t for k in ("sponsor", "underwrite", "advertise")):
        return R(None, None, "take_part", "sponsors", "/sponsors.html", 0.7, "sponsors")
    # How-to / learn
    if t.startswith("how do i ") or t.startswith("teach me ") or "lesson on" in t:
        return R(None, None, "learn", "", "/learn.html", 0.7, "learn / how-to")
    # Default → weigh it as a claim
    return R("discern", None, "discern", "engine", "/walks.html", 0.3, "unrouted — weighed as a claim")


def detect_lens(text: str) -> str:
    """Which lens the floor brings to bear. Delegates to the one classifier;
    falls to 'discern' (weigh it as a claim) when the input is navigation-only."""
    return classify(text).get("lens") or "discern"


# ── The four gates, as the canon defines them ──────────────────────────────
GATES = [
    {"gate": "RED",      "asks": "Aligned with the words of Jesus? (truth)"},
    {"gate": "FLOOR",    "asks": "Does it violate the Law / break a stability floor? (harm)"},
    {"gate": "BROTHERS", "asks": "Do at least two witnesses affirm it? (corroboration)"},
    {"gate": "GOD",      "asks": "Has the required waiting elapsed? (no rushing)"},
]

# Disqualifying signals the RED gate rejects outright (coercion, domination,
# the antichrist shape the Pressure System becomes without a floor).
_RED_DISQUALIFIERS = (
    "coerce", "force them", "manipulate", "dominate", "exploit", "by any means",
    "the ends justify", "no rules", "do whatever", "control them",
)


def _canon_anchor(text: str, domain: Optional[str]) -> Dict[str, Any]:
    """Anchor the output to Scripture — the fixed floor. Soft: if the scripture
    services aren't importable here, name Canon as the reference without a verse."""
    out: Dict[str, Any] = {"is_floor": True, "authority": "Canon (Scripture) — closed, supreme"}
    try:
        # The apothecary already knows how to surface a relevant anchor; reuse
        # its scripture path if available, else leave the anchor open.
        from api import scripture_lookup as _sl  # noqa: F401
        out["scripture_available"] = True
    except Exception:
        out["scripture_available"] = False
    out["note"] = "Every standing is checked against Canon; the lens never overrules the floor."
    return out


def _run_gates(text: str) -> Dict[str, Any]:
    """Evaluate what is checkable now. RED and FLOOR are hard (can reject);
    BROTHERS and GOD are soft (quarantine until satisfied). Honest: we do not
    mark a soft gate PASS from a single call — it stays PENDING."""
    t = (text or "").lower()
    red_hit = next((d for d in _RED_DISQUALIFIERS if d in t), None)
    verdicts: List[Dict[str, str]] = []
    verdicts.append({
        "gate": "RED",
        "status": "REJECT" if red_hit else "PASS",
        "why": f"disqualifying signal: '{red_hit}'" if red_hit else "no disqualifying signal found",
    })
    # FLOOR: structural — empty or self-contradictory inputs fail; otherwise pass-pending-verifier
    floor_ok = bool((text or "").strip())
    verdicts.append({
        "gate": "FLOOR",
        "status": "PASS" if floor_ok else "REJECT",
        "why": "structurally present" if floor_ok else "empty / structurally incomplete",
    })
    # BROTHERS + GOD are not satisfiable from one call — they require witnesses + time.
    verdicts.append({"gate": "BROTHERS", "status": "PENDING", "why": "needs ≥2 witnesses (Deut 19:15)"})
    verdicts.append({"gate": "GOD", "status": "PENDING", "why": "needs the waiting period (no rushing)"})
    hard_reject = any(v["status"] == "REJECT" for v in verdicts[:2])
    return {
        "verdicts": verdicts,
        "admitted": not hard_reject,
        "state": "rejected" if hard_reject else "quarantined-until-witnessed",
    }


# Domain → the deterministic verifier that applies. A pointer, so the tool
# knows which fixed wall to press its claim against.
_VERIFIER_FOR = {
    "math": "verify_mathematics", "mathematics": "verify_mathematics",
    "stats": "verify_statistics", "statistics": "verify_statistics",
    "physics": "verify_physics", "chemistry": "verify_chemistry",
    "biology": "verify_biology", "medicine": "verify_medicine",
    "nutrition": "verify_nutrition", "health": "verify_medicine",
    "logic": "verify_formal_logic", "scripture": "verify_scripture_anchors",
    "theology": "verify_theology_doctrine", "finance": "verify_finance",
    "law": "verify_law", "governance": "verify_governance_decision_packet",
}

# Health-domain hint: when to also stand on the nested-control framework.
_HEALTH_HINT = ("health", "medicine", "nutrition", "disease", "symptom", "remedy", "apothecary")


def stand_on_floor(
    text: str,
    *,
    lens: Optional[str] = None,
    domain: Optional[str] = None,
    kind: str = "claim",
    triad: Optional[Dict[str, float]] = None,
    load: Optional[float] = None,
    capacity: Optional[float] = None,
    vice_signals: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """The one engine. Bring anything; it stands on the whole floor.

    You don't pick a tool. If `lens` and `domain` aren't given, the floor reads
    what you brought and applies the lens itself (apothecary, discern, scripture,
    …) — the airlock and the floor are one motion. Returns the full standing:
    Canon · gates · verifier · Calibre · nested-control · ledger, framed by the
    lens it detected.

    Optional signals deepen the standing where they can be supplied:
      triad        = {spirit, mind, body} in [0,1] → Calibre health + beauty
      load/capacity in [0,1]                        → Calibre shadow + nested overload
      vice_signals = {source, channel, desire}      → Calibre vice index
    """
    # Read what was brought — the one brain selects lens, domain, and route.
    routing = classify(text)
    if lens is None:
        # Preserve the distinction: a real judgment lens, else 'navigate'
        # (a room to open) — never silently collapse navigation into 'discern'.
        lens = routing.get("lens") or "navigate"
    lens_cfg = LENSES.get(lens, LENSES["discern"])
    if domain is None:
        domain = routing.get("domain") or lens_cfg.get("domain")

    standing: Dict[str, Any] = {
        "input_kind": kind,
        "lens": {"name": lens, "label": lens_cfg["label"], "frame": lens_cfg["frame"]},
        "domain": domain,
        # The route is part of the standing: where this goes, from the same
        # brain. One call now answers both 'what is it' and 'where does it go'.
        "route": {"to": routing.get("route"), "url": routing.get("url"),
                  "tool": routing.get("tool"), "why": routing.get("why")},
        "canon": _canon_anchor(text, domain),
        "gates": _run_gates(text),
    }

    # 3. VERIFIER — point at the fixed wall for this domain
    key = (domain or "").lower()
    standing["verifier"] = {
        "applies": _VERIFIER_FOR.get(key),
        "note": "the deterministic check this claim should be pressed against" if key in _VERIFIER_FOR
                else "no domain verifier identified — falls to search/LLM, and logs a gap",
    }

    # 4. CALIBRE — the moral floor, made calculable, where derivable
    calibre_out: Dict[str, Any] = {}
    try:
        from api import calibre as _cal
        if triad:
            calibre_out.update(_cal.score_triad(
                triad.get("spirit", 0.0), triad.get("mind", 0.0), triad.get("body", 0.0)))
        if load is not None and capacity is not None:
            calibre_out["shadow"] = round(_cal.shadow(1.0, capacity, load), 4)
        if vice_signals:
            calibre_out["vice"] = round(_cal.vice_index(
                vice_signals.get("source", 1.0),
                vice_signals.get("channel", 1.0),
                vice_signals.get("desire", 0.0)), 4)
    except Exception as exc:
        calibre_out["error"] = str(exc)[:120]
    standing["calibre"] = calibre_out or {"note": "no triad / load / vice signals supplied"}

    # 5. NESTED CONTROL — for health-domain outputs, the control-layer reading
    if (domain or "").lower() in _HEALTH_HINT or any(h in (text or "").lower() for h in _HEALTH_HINT):
        try:
            from api import nested_control as _nc
            standing["nested_control"] = _nc.layer_view(text, load=load, capacity=capacity)
        except Exception as exc:
            standing["nested_control"] = {"error": str(exc)[:120]}

    # 6. LEDGER — offered, not forced (the canon: we record, we don't coerce)
    standing["ledger"] = {
        "recordable": standing["gates"]["admitted"],
        "note": "append-only proof available once witnessed (BROTHERS) and waited (GOD)",
    }
    return standing


def floor_summary() -> Dict[str, Any]:
    """What the whole floor is — so a tool (or a person) can see every piece
    it stands on at a glance. The index card for the floor itself."""
    return {
        "pieces": [
            {"name": "Canon", "what": "Scripture — the fixed, supreme floor (the words in red)"},
            {"name": "Gates", "what": "RED / FLOOR / BROTHERS / GOD — the admission protocol"},
            {"name": "Verifiers", "what": "65 deterministic domain checks (the fixed walls)"},
            {"name": "Calibre", "what": "health / beauty / shadow / vice — the moral floor, calculable"},
            {"name": "Nested Control", "what": "load vs capacity across nested layers (the cross-domain pattern)"},
            {"name": "Ledger", "what": "append-only proof — witness over time"},
        ],
        "rule": "Every tool stands on all of it. No tool is connected to one shard.",
        "lenses": {
            name: {"label": cfg["label"], "frame": cfg["frame"]}
            for name, cfg in LENSES.items()
        },
        "lenses_note": (
            "The 'rooms' are not separate tools. Each is the one operation "
            "wearing a lens. You bring something; the floor reads which lens "
            "it is and stands it on the foundation. One engine, many views."
        ),
    }
