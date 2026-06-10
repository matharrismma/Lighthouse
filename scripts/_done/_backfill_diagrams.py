"""Backfill SVG diagrams onto three high-value existing units:
  - math_counting_to_20  → ten-frame
  - math_shapes_2d       → the four basic shapes
  - science_magnets      → attract / repel diagram with N/S poles

Rewrites the JSONL file in-place, leaving every other unit untouched
and adding only the new `svg_diagrams` field on the targeted unit.
"""
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

TEN_FRAME_SVG = (
    '<svg viewBox="0 0 280 100" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
    '<rect x="20" y="20" width="240" height="60"/>'
    '<line x1="68" y1="20" x2="68" y2="80"/>'
    '<line x1="116" y1="20" x2="116" y2="80"/>'
    '<line x1="164" y1="20" x2="164" y2="80"/>'
    '<line x1="212" y1="20" x2="212" y2="80"/>'
    '<line x1="20" y1="50" x2="260" y2="50"/>'
    # Fill 7 of 10 cells to show counting to 7
    '<circle cx="44" cy="35" r="11" fill="currentColor"/>'
    '<circle cx="92" cy="35" r="11" fill="currentColor"/>'
    '<circle cx="140" cy="35" r="11" fill="currentColor"/>'
    '<circle cx="188" cy="35" r="11" fill="currentColor"/>'
    '<circle cx="236" cy="35" r="11" fill="currentColor"/>'
    '<circle cx="44" cy="65" r="11" fill="currentColor"/>'
    '<circle cx="92" cy="65" r="11" fill="currentColor"/>'
    '<text x="140" y="98" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">ten-frame showing 7 (5 + 2)</text>'
    '</svg>'
)

SHAPES_SVG = [
    {"label": "Circle", "svg": '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><circle cx="50" cy="50" r="36"/></svg>'},
    {"label": "Square (4 equal sides)", "svg": '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><rect x="20" y="20" width="60" height="60"/></svg>'},
    {"label": "Triangle (3 sides)", "svg": '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><polygon points="50,18 18,82 82,82"/></svg>'},
    {"label": "Rectangle (2 long, 2 short)", "svg": '<svg viewBox="0 0 100 100" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><rect x="10" y="30" width="80" height="40"/></svg>'},
]

MAGNETS_SVG = [
    {"label": "Opposite poles ATTRACT (pull together)", "svg": (
        '<svg viewBox="0 0 240 80" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
        '<rect x="30" y="25" width="60" height="30"/>'
        '<line x1="60" y1="25" x2="60" y2="55" stroke-width="1.5"/>'
        '<text x="45" y="45" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">N</text>'
        '<text x="75" y="45" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">S</text>'
        '<rect x="150" y="25" width="60" height="30"/>'
        '<line x1="180" y1="25" x2="180" y2="55" stroke-width="1.5"/>'
        '<text x="165" y="45" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">N</text>'
        '<text x="195" y="45" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">S</text>'
        '<line x1="95" y1="40" x2="145" y2="40" stroke-dasharray="3,3"/>'
        '<polygon points="100,37 100,43 95,40" fill="currentColor"/>'
        '<polygon points="140,37 140,43 145,40" fill="currentColor"/>'
        '<text x="120" y="20" text-anchor="middle" font-size="10" fill="currentColor" stroke="none">attract</text>'
        '</svg>'
    )},
    {"label": "Same poles REPEL (push apart)", "svg": (
        '<svg viewBox="0 0 240 80" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
        '<rect x="30" y="25" width="60" height="30"/>'
        '<line x1="60" y1="25" x2="60" y2="55" stroke-width="1.5"/>'
        '<text x="45" y="45" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">S</text>'
        '<text x="75" y="45" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">N</text>'
        '<rect x="150" y="25" width="60" height="30"/>'
        '<line x1="180" y1="25" x2="180" y2="55" stroke-width="1.5"/>'
        '<text x="165" y="45" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">N</text>'
        '<text x="195" y="45" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">S</text>'
        '<line x1="115" y1="40" x2="100" y2="40" stroke-dasharray="3,3"/>'
        '<polygon points="100,37 100,43 95,40" fill="currentColor"/>'
        '<line x1="125" y1="40" x2="140" y2="40" stroke-dasharray="3,3"/>'
        '<polygon points="140,37 140,43 145,40" fill="currentColor"/>'
        '<text x="120" y="20" text-anchor="middle" font-size="10" fill="currentColor" stroke="none">repel</text>'
        '</svg>'
    )},
]


def backfill(file_rel: str, target_id: str, svg_diagrams):
    path = os.path.join(REPO, file_rel)
    out_lines = []
    found = False
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.rstrip("\n")
            if not line.strip():
                out_lines.append(line)
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                out_lines.append(line)
                continue
            if rec.get("id") == target_id:
                rec["svg_diagrams"] = svg_diagrams
                line = json.dumps(rec, ensure_ascii=False)
                found = True
            out_lines.append(line)
    if not found:
        raise RuntimeError(f"unit {target_id!r} not found in {file_rel}")
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    print(f"backfilled {target_id} in {file_rel}")


# math_counting_to_20 — single diagram, use svg_diagrams with one entry
# for consistency with the multi-diagram pattern
backfill(
    "data/math/units.jsonl",
    "math_counting_to_20",
    [{"label": "Ten-frame", "svg": TEN_FRAME_SVG}],
)

backfill(
    "data/math/units.jsonl",
    "math_shapes_2d",
    SHAPES_SVG,
)

backfill(
    "data/science/units.jsonl",
    "science_magnets",
    MAGNETS_SVG,
)
print("done")
