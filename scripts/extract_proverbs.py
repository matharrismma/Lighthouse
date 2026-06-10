"""Extract WEB Bible Proverbs verses into structured packet substrate.

Source: lw/00_source/web/web.db (table t_web, public domain WEB text).
Output: data/proverbs/verses.jsonl — one packet per verse.

Each packet auto-derives theme tags by keyword pattern matching against
the verse text. The 7-axis scaffold (authority_trust, reasoning,
information_encoding, physical_substance, metabolism, conservation_balance,
time_sequence) is also assigned by keyword pattern.

This is one-shot. Rerun if the source DB changes.
"""
from __future__ import annotations
import json
import re
import sqlite3
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent
WEB_DB = REPO / "lw" / "00_source" / "web" / "web.db"
OUT_FILE = REPO / "data" / "proverbs" / "verses.jsonl"

# Book 20 in standard Protestant order = Proverbs
PROVERBS_BOOK = 20

# ── Axis derivation by keyword (light-touch; verses can carry 0-3 axes) ──
_AXIS_PATTERNS: dict[str, list[str]] = {
    "authority_trust": [
        r"\bLORD\b", r"\bGod\b", r"\bfear\b", r"\btrust\b", r"\bobey\b",
        r"\bcommand", r"\bauthority\b", r"\brighteous", r"\bwicked\b",
        r"\bking\b", r"\bfather\b", r"\bmother\b", r"\bson\b", r"\binstruct",
        r"\bcounsel\b", r"\bdiscipline\b",
    ],
    "reasoning": [
        r"\bwisdom\b", r"\bwise\b", r"\bfool\b", r"\bfolly\b",
        r"\bunderstand", r"\bdiscern", r"\bknowledge\b", r"\bprudent",
        r"\binsight\b", r"\binstruction\b", r"\bcounsel\b", r"\bplan\b",
        r"\bdevise\b", r"\bsimple\b",
    ],
    "information_encoding": [
        r"\btongue\b", r"\blip\b", r"\bword\b", r"\bspeech\b",
        r"\bspeak", r"\bsaid\b", r"\bsay\b", r"\bsilent\b", r"\bsilence\b",
        r"\bwhisper", r"\bgossip", r"\bslander", r"\blie\b", r"\blying\b",
        r"\btruth", r"\bdeceit", r"\brebuke\b", r"\bteach", r"\bansw",
    ],
    "physical_substance": [
        r"\bhand\b", r"\bfoot\b", r"\beye\b", r"\bear\b", r"\bbody\b",
        r"\bbones\b", r"\bblood\b", r"\bsword\b", r"\brod\b",
        r"\bhouse\b", r"\bbuilt\b", r"\bbuild\b", r"\bstone\b",
        r"\bpath\b", r"\bway\b", r"\bjourney\b", r"\bdoor\b",
    ],
    "metabolism": [
        r"\beat\b", r"\bdrink\b", r"\bhungry\b", r"\bfull\b",
        r"\bsleep\b", r"\brest\b", r"\bweary\b", r"\bstrong\b",
        r"\bharvest\b", r"\bsow\b", r"\breap\b", r"\bgrow\b",
        r"\blife\b", r"\bdeath\b", r"\blive\b", r"\bdie\b",
    ],
    "conservation_balance": [
        r"\briches\b", r"\bwealth\b", r"\bpoor\b", r"\brich\b", r"\bpoverty\b",
        r"\bmoney\b", r"\bsilver\b", r"\bgold\b", r"\bsurety\b", r"\bdebt\b",
        r"\bloan\b", r"\bgive\b", r"\bgiveth\b", r"\bgenerous\b",
        r"\bjust\b", r"\bjustice\b", r"\bequity\b", r"\bbalance\b",
        r"\bweight\b", r"\bmeasure\b", r"\bportion\b",
    ],
    "time_sequence": [
        r"\bwait\b", r"\bpatient\b", r"\bpatience\b", r"\bdiligent\b",
        r"\bslothful\b", r"\bsluggard\b", r"\bdelay", r"\btomorrow\b",
        r"\bmorning\b", r"\bnight\b", r"\bseason\b", r"\bage\b",
        r"\bold\b", r"\byouth\b", r"\bbefore\b", r"\bafter\b",
    ],
}

# Theme tags — broader categories that overlap with almanac domains
_THEME_PATTERNS: dict[str, list[str]] = {
    "wisdom_folly":      [r"\bwise\b", r"\bwisdom\b", r"\bfool\b", r"\bfolly\b", r"\bunderstand"],
    "speech_tongue":     [r"\btongue\b", r"\blip\b", r"\bword\b", r"\bspeak", r"\bgossip"],
    "diligence_laziness":[r"\bdiligent\b", r"\bsluggard\b", r"\bslothful\b", r"\bidle\b", r"\blazy\b"],
    "fear_of_the_lord":  [r"\bfear of (the )?LORD\b", r"\bfear of (the )?God\b"],
    "wealth_poverty":    [r"\bpoor\b", r"\brich\b", r"\bwealth\b", r"\briches\b", r"\bmoney\b", r"\bsilver\b", r"\bgold\b"],
    "justice":           [r"\bjust\b", r"\bjustice\b", r"\brighteous", r"\bequity\b", r"\bbribe\b"],
    "discipline":        [r"\brod\b", r"\bdiscipline\b", r"\bcorrect", r"\brebuke\b", r"\binstruct"],
    "honesty_deceit":    [r"\blie\b", r"\blying\b", r"\bdeceit", r"\btruth", r"\bfalse\b", r"\bhonest"],
    "anger_temper":      [r"\banger\b", r"\bwrath\b", r"\bquick to\b", r"\bslow to anger\b", r"\bfury\b"],
    "pride_humility":    [r"\bpride\b", r"\bproud\b", r"\bhumble\b", r"\bhumility\b", r"\barrog"],
    "friendship":        [r"\bfriend", r"\bcompanion\b", r"\bneighbor\b"],
    "family":            [r"\bson\b", r"\bdaughter\b", r"\bfather\b", r"\bmother\b", r"\bchildren\b", r"\bhousehold\b", r"\bhouse\b"],
    "adultery":          [r"\badulter", r"\bharlot\b", r"\bstrange woman\b", r"\bforeign woman\b", r"\bseduc"],
    "king_authority":    [r"\bking\b", r"\bruler\b", r"\bauthority\b", r"\bthrone\b"],
    "path_way":          [r"\bpath\b", r"\bway\b", r"\bjourney\b", r"\bstep\b", r"\bwalk\b", r"\bstraight\b", r"\bcrooked\b"],
    "fear_of_man":       [r"\bsnare\b", r"\bfear of man\b", r"\bafraid\b"],
}


def derive_axes(text: str) -> list[str]:
    """Return axes whose patterns match the verse text."""
    out: list[str] = []
    for axis, patterns in _AXIS_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                out.append(axis)
                break
    return out


def derive_themes(text: str) -> list[str]:
    out: list[str] = []
    for theme, patterns in _THEME_PATTERNS.items():
        for pat in patterns:
            if re.search(pat, text, re.IGNORECASE):
                out.append(theme)
                break
    return out


def main():
    if not WEB_DB.exists():
        print(f"WEB DB not found: {WEB_DB}", file=sys.stderr)
        sys.exit(1)

    OUT_FILE.parent.mkdir(parents=True, exist_ok=True)

    con = sqlite3.connect(str(WEB_DB))
    cur = con.cursor()
    rows = list(cur.execute(
        "select c, v, t from t_web where b = ? order by c, v",
        (PROVERBS_BOOK,)
    ))
    con.close()

    written = 0
    with OUT_FILE.open("w", encoding="utf-8") as fh:
        for c, v, t in rows:
            text = (t or "").strip()
            if not text:
                continue
            ref = f"Proverbs {c}:{v}"
            packet = {
                "id": f"prov_{c:02d}_{v:02d}",
                "kind": "proverb",
                "reference": ref,
                "book": "Proverbs",
                "chapter": c,
                "verse": v,
                "text": text,
                "axes": derive_axes(text),
                "themes": derive_themes(text),
                "source": "World English Bible",
                "license": "Public Domain",
            }
            fh.write(json.dumps(packet, ensure_ascii=False) + "\n")
            written += 1
    print(f"wrote {written} proverb packets to {OUT_FILE.relative_to(REPO)}")


if __name__ == "__main__":
    main()
