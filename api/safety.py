"""Crisis safety net — the floor under the floor.

Some conditions a person brings are acute: thoughts of suicide or self-harm, an
overdose, being in danger right now. On those, the most loving and honest thing
the engine can do is get out of the way and point to a real person who can help
immediately. The wisdom in the substrate is real, but it is not triage, and a
remedy must never stand between someone in danger and the help that can keep
them safe.

Deterministic by design. Detection is phrase-based (no oracle): a safety net has
to fire reliably and instantly, not depend on a model call that could be slow,
budgeted-out, or wrong. It is precise, not broad — it triggers on acute,
self-directed signals only, so the message keeps its weight. A crisis banner on
every "I feel stressed" would desensitize and erode trust; the goal is that when
it does appear, it is believed.

When it fires, it points three ways, in order:
  1. to immediate crisis help (988 / 911 / a text line / a worldwide directory),
  2. to a real person the visitor already trusts,
  3. and — because a person's worth never hinged on this tool — to Christ,
     briefly, gently, never preachy, never as a substitute for the call.

Success is the person reaching real help and needing this tool less.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

# Acute, self-directed signals. Word-boundaried and phrase-shaped so we don't
# fire on "I could kill HIM" (anger at another), "dying to see you" (idiom), or
# "dead tired". Erring toward care on a clear self-directed phrase is acceptable:
# a gentle "if you're struggling, help is here" never harms, and a miss can.
_CRISIS_PATTERNS = [
    r"\bkill(?:ing)?\s+my\s?self\b",
    r"\bend(?:ing)?\s+(?:my\s+life|my\s+own\s+life|it\s+all)\b",
    r"\btake\s+my\s+(?:own\s+)?life\b",
    r"\bwan(?:t|na)\s+to?\s*die\b",
    r"\bwant\s+to\s+die\b",
    r"\bwish\s+i\s+(?:was|were)\s+dead\b",
    r"\bbetter\s+off\s+dead\b",
    r"\bno\s+(?:reason|point)\s+(?:to|in)\s+(?:living|live|life|go\s+on)\b",
    r"\bnot\s+worth\s+living\b",
    r"\bdon'?t\s+want\s+to\s+(?:be\s+here|live|exist|wake\s+up)\b",
    r"\bsuicid",            # suicide, suicidal
    r"\bhurt(?:ing)?\s+my\s?self\b",
    r"\bcut(?:ting)?\s+my\s?self\b",
    r"\bself[-\s]?harm",
    r"\boverdos",           # overdose, overdosed, overdosing
    r"\bkill\s+my\s?self\b",
]
_CRISIS_RE = re.compile("|".join(_CRISIS_PATTERNS), re.IGNORECASE)


def crisis_check(text: str) -> Optional[Dict[str, Any]]:
    """Return a structured safety block if `text` carries an acute-risk signal,
    else None. Deterministic; safe to call on every input."""
    if not text or not _CRISIS_RE.search(text):
        return None
    return safety_block()


def safety_block() -> Dict[str, Any]:
    """The crisis response. Stable shape so any surface (apothecary, Shepherd,
    a generative reply) can render it first and identically."""
    immediate: List[Dict[str, str]] = [
        {
            "name": "988 Suicide & Crisis Lifeline (US)",
            "action": "Call or text 988",
            "detail": "Free, confidential, 24/7. You can also chat at 988lifeline.org.",
        },
        {
            "name": "Emergency services",
            "action": "Call 911 (US) or your local emergency number",
            "detail": "If you are in immediate danger or might act on these thoughts.",
        },
        {
            "name": "Crisis Text Line",
            "action": "Text HOME to 741741 (US / Canada / UK)",
            "detail": "Text back and forth with a trained crisis counselor.",
        },
        {
            "name": "Find a helpline (worldwide)",
            "action": "findahelpline.com",
            "detail": "Free, confidential crisis lines listed by country.",
        },
    ]
    return {
        "triggered": True,
        "severity": "crisis",
        "headline": "Please reach a real person right now — you deserve immediate help, "
                    "and this tool cannot give it.",
        "immediate": immediate,
        "a_real_person": "Tell someone you trust what you just told me — a friend, a "
                         "family member, a pastor. You do not have to carry this alone, "
                         "and saying it out loud to a person is itself a step toward safety.",
        "in_christ": "You are not beyond help and you are not a burden. Your life has "
                     "worth that does not depend on how you feel right now, or on anything "
                     "this tool can offer. “The LORD is near to the brokenhearted and "
                     "saves the crushed in spirit.” (Psalm 34:18)",
        "honest_limit": "This is a tool, not a counselor or a doctor. It cannot keep you "
                        "safe — a real person can. Please reach out above before reading "
                        "anything else here.",
    }
