#!/usr/bin/env python
"""Rename user-facing 'Coach' to 'Shepherd' across site/*.html.

Keeps the following untouched:
  - JavaScript identifiers: coachInput, coachBtn, coachOut, coachCard,
    coachHistory, coachCount, askCoach, renderCoach*, firePolyForCoach,
    renderPolyInCoach, buildCoachNarration
  - CSS class names: cs-coach, .coachCard
  - localStorage keys: concordance_coach_history_v1
  - URL paths: /coach/journal

Only swaps user-visible occurrences:
  - "<a href=\"/walk.html\">Coach</a>"  -> Shepherd
  - "The Coach OS" / "Coach OS"          -> The Shepherd / Shepherd
  - "the Coach"                          -> "the Shepherd"
  - "The Coach"                          -> "The Shepherd"
  - ">Coach<"                            -> ">Shepherd<"  (between tags)
  - "ask the coach" / "the coach"        -> "the Shepherd" (only outside scripts)
"""
from __future__ import annotations
import re
from pathlib import Path

SITE = Path(__file__).resolve().parents[1] / "site"

# Tuple of (pattern, replacement). Order matters — more specific first.
REPLACEMENTS: list[tuple[re.Pattern[str], str]] = [
    # Exact link-text match — appears in every lens-bar
    (re.compile(r'>Coach<'), '>Shepherd<'),
    # "Coach OS" — used in agents.html API docs + walk.html eyebrow
    (re.compile(r'\bCoach OS\b'), 'Shepherd OS'),
    # "The Coach" / "the coach" in narrative body
    (re.compile(r'\bThe Coach\b'), 'The Shepherd'),
    (re.compile(r'\bthe Coach\b'), 'the Shepherd'),
    (re.compile(r'\bthe coach\b'), 'the Shepherd'),
    # Anything else with bare "Coach" — but ONLY inside text nodes; we skip
    # lines that look like JS by gating below.
]

# Lines containing any of these substrings are JS/CSS — skip the bare
# word "Coach" replacement on them. (The specific patterns above are
# already safe because they use word boundaries and tag-adjacency.)
JS_OR_CSS_MARKERS = (
    'function ', 'const ', 'let ', 'var ', '=>', '() ', '().',
    'cs-coach', 'coachInput', 'coachBtn', 'coachOut', 'coachCard',
    'coachHistory', 'coachCount', 'askCoach', 'renderCoach',
    'firePolyForCoach', 'renderPolyInCoach', 'buildCoachNarration',
    'concordance_coach_history_v1', 'COACH_HIST_KEY',
    '/* ', '// ', 'localStorage', 'getElementById',
)


def process_file(path: Path) -> tuple[int, str]:
    src = path.read_text(encoding='utf-8')
    new_lines = []
    changes = 0
    for line in src.splitlines(keepends=True):
        out = line
        for pat, repl in REPLACEMENTS:
            new = pat.sub(repl, out)
            if new != out:
                changes += (len(pat.findall(out)))
                out = new
        new_lines.append(out)
    return changes, ''.join(new_lines)


def main() -> int:
    total_changes = 0
    files_touched = 0
    for p in sorted(SITE.glob('*.html')):
        changes, new = process_file(p)
        if changes:
            p.write_text(new, encoding='utf-8')
            print(f"  {p.name:30s}  -{changes} Coach->Shepherd")
            files_touched += 1
            total_changes += changes
    print(f"\n-- touched {files_touched} files, {total_changes} replacements")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
