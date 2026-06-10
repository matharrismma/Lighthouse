"""Backfill SVG diagrams onto every unit where graphics carry real load:
   math (operations, place value, money, time, multiplication),
   science (seasons, plants, water cycle, states of matter),
   social studies (compass rose).

   Each unit gets one or more svg_diagrams entries. Existing
   svg_diagrams on units that already have them are NOT overwritten.

   SVG conventions: viewBox-based, stroke='currentColor' so the
   diagram inherits the page text color, simple line art, small
   payload, self-contained.
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Math diagrams ─────────────────────────────────────────────

TENFRAME_3PLUS4 = (
    '<svg viewBox="0 0 280 110" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
    '<rect x="20" y="20" width="240" height="60"/>'
    '<line x1="68" y1="20" x2="68" y2="80"/>'
    '<line x1="116" y1="20" x2="116" y2="80"/>'
    '<line x1="164" y1="20" x2="164" y2="80"/>'
    '<line x1="212" y1="20" x2="212" y2="80"/>'
    '<line x1="20" y1="50" x2="260" y2="50"/>'
    # 3 solid (the first addend)
    '<circle cx="44" cy="35" r="11" fill="currentColor"/>'
    '<circle cx="92" cy="35" r="11" fill="currentColor"/>'
    '<circle cx="140" cy="35" r="11" fill="currentColor"/>'
    # 4 outlined (the second addend, just added)
    '<circle cx="188" cy="35" r="11"/>'
    '<circle cx="236" cy="35" r="11"/>'
    '<circle cx="44" cy="65" r="11"/>'
    '<circle cx="92" cy="65" r="11"/>'
    '<text x="140" y="100" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">3 (filled) + 4 (outline) = 7</text>'
    '</svg>'
)

TENFRAME_SUBTRACT = (
    '<svg viewBox="0 0 280 110" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
    '<rect x="20" y="20" width="240" height="60"/>'
    '<line x1="68" y1="20" x2="68" y2="80"/>'
    '<line x1="116" y1="20" x2="116" y2="80"/>'
    '<line x1="164" y1="20" x2="164" y2="80"/>'
    '<line x1="212" y1="20" x2="212" y2="80"/>'
    '<line x1="20" y1="50" x2="260" y2="50"/>'
    # 7 filled circles
    '<circle cx="44" cy="35" r="11" fill="currentColor"/>'
    '<circle cx="92" cy="35" r="11" fill="currentColor"/>'
    '<circle cx="140" cy="35" r="11" fill="currentColor"/>'
    '<circle cx="188" cy="35" r="11" fill="currentColor"/>'
    '<circle cx="236" cy="35" r="11" fill="currentColor"/>'
    '<circle cx="44" cy="65" r="11" fill="currentColor"/>'
    '<circle cx="92" cy="65" r="11" fill="currentColor"/>'
    # X over the last 3 (subtracting 3)
    '<line x1="156" y1="21" x2="172" y2="49" stroke-width="2.5"/>'
    '<line x1="172" y1="21" x2="156" y2="49" stroke-width="2.5"/>'
    '<line x1="204" y1="21" x2="220" y2="49" stroke-width="2.5"/>'
    '<line x1="220" y1="21" x2="204" y2="49" stroke-width="2.5"/>'
    '<line x1="252" y1="21" x2="268" y2="49" stroke-width="2.5"/>'
    '<line x1="268" y1="21" x2="252" y2="49" stroke-width="2.5"/>'
    '<text x="140" y="100" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">7 − 3 = 4 (cross out 3, count what is left)</text>'
    '</svg>'
)

TENFRAME_PAIR_MAKE_TEN = (
    '<svg viewBox="0 0 360 110" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
    # Left ten-frame (filled to 10)
    '<rect x="10" y="20" width="160" height="60"/>'
    '<line x1="42" y1="20" x2="42" y2="80"/>'
    '<line x1="74" y1="20" x2="74" y2="80"/>'
    '<line x1="106" y1="20" x2="106" y2="80"/>'
    '<line x1="138" y1="20" x2="138" y2="80"/>'
    '<line x1="10" y1="50" x2="170" y2="50"/>'
    # All ten filled — 8 dark + 2 light (the +2 from make-a-ten)
    '<circle cx="26" cy="35" r="9" fill="currentColor"/>'
    '<circle cx="58" cy="35" r="9" fill="currentColor"/>'
    '<circle cx="90" cy="35" r="9" fill="currentColor"/>'
    '<circle cx="122" cy="35" r="9" fill="currentColor"/>'
    '<circle cx="154" cy="35" r="9" fill="currentColor"/>'
    '<circle cx="26" cy="65" r="9" fill="currentColor"/>'
    '<circle cx="58" cy="65" r="9" fill="currentColor"/>'
    '<circle cx="90" cy="65" r="9" fill="currentColor"/>'
    '<circle cx="122" cy="65" r="9"/>'  # outline (the +2)
    '<circle cx="154" cy="65" r="9"/>'  # outline (the +2)
    # Right ten-frame (3 of 5 — remainder of 5 after using 2 to make ten)
    '<rect x="190" y="20" width="160" height="60"/>'
    '<line x1="222" y1="20" x2="222" y2="80"/>'
    '<line x1="254" y1="20" x2="254" y2="80"/>'
    '<line x1="286" y1="20" x2="286" y2="80"/>'
    '<line x1="318" y1="20" x2="318" y2="80"/>'
    '<line x1="190" y1="50" x2="350" y2="50"/>'
    '<circle cx="206" cy="35" r="9"/>'  # outline (the remaining +3)
    '<circle cx="238" cy="35" r="9"/>'
    '<circle cx="270" cy="35" r="9"/>'
    '<text x="180" y="100" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">8 + 5: fill ten (8+2), spill 3 to next frame = 13</text>'
    '</svg>'
)

TENFRAME_PAIR_BACK_THROUGH = (
    '<svg viewBox="0 0 360 110" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
    # Left ten-frame — full ten with last 2 crossed out (8 remain after subtracting 2)
    '<rect x="10" y="20" width="160" height="60"/>'
    '<line x1="42" y1="20" x2="42" y2="80"/>'
    '<line x1="74" y1="20" x2="74" y2="80"/>'
    '<line x1="106" y1="20" x2="106" y2="80"/>'
    '<line x1="138" y1="20" x2="138" y2="80"/>'
    '<line x1="10" y1="50" x2="170" y2="50"/>'
    '<circle cx="26" cy="35" r="9" fill="currentColor"/>'
    '<circle cx="58" cy="35" r="9" fill="currentColor"/>'
    '<circle cx="90" cy="35" r="9" fill="currentColor"/>'
    '<circle cx="122" cy="35" r="9" fill="currentColor"/>'
    '<circle cx="154" cy="35" r="9" fill="currentColor"/>'
    '<circle cx="26" cy="65" r="9" fill="currentColor"/>'
    '<circle cx="58" cy="65" r="9" fill="currentColor"/>'
    '<circle cx="90" cy="65" r="9" fill="currentColor"/>'
    # last two on bottom crossed out
    '<circle cx="122" cy="65" r="9" fill="currentColor"/>'
    '<line x1="114" y1="57" x2="130" y2="73" stroke-width="2"/>'
    '<line x1="130" y1="57" x2="114" y2="73" stroke-width="2"/>'
    '<circle cx="154" cy="65" r="9" fill="currentColor"/>'
    '<line x1="146" y1="57" x2="162" y2="73" stroke-width="2"/>'
    '<line x1="162" y1="57" x2="146" y2="73" stroke-width="2"/>'
    # Right ten-frame: 3 circles all crossed out (the 3 from the 13 we removed first)
    '<rect x="190" y="20" width="160" height="60"/>'
    '<line x1="222" y1="20" x2="222" y2="80"/>'
    '<line x1="254" y1="20" x2="254" y2="80"/>'
    '<line x1="286" y1="20" x2="286" y2="80"/>'
    '<line x1="318" y1="20" x2="318" y2="80"/>'
    '<line x1="190" y1="50" x2="350" y2="50"/>'
    '<circle cx="206" cy="35" r="9" fill="currentColor"/>'
    '<line x1="198" y1="27" x2="214" y2="43" stroke-width="2"/>'
    '<line x1="214" y1="27" x2="198" y2="43" stroke-width="2"/>'
    '<circle cx="238" cy="35" r="9" fill="currentColor"/>'
    '<line x1="230" y1="27" x2="246" y2="43" stroke-width="2"/>'
    '<line x1="246" y1="27" x2="230" y2="43" stroke-width="2"/>'
    '<circle cx="270" cy="35" r="9" fill="currentColor"/>'
    '<line x1="262" y1="27" x2="278" y2="43" stroke-width="2"/>'
    '<line x1="278" y1="27" x2="262" y2="43" stroke-width="2"/>'
    '<text x="180" y="100" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">13 − 5: remove 3 (lands on 10), then 2 more (lands on 8)</text>'
    '</svg>'
)

PLACE_VALUE_47 = (
    '<svg viewBox="0 0 320 130" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
    # 4 rods (tens) — vertical bars
    '<rect x="20" y="20" width="14" height="80"/>'
    '<line x1="20" y1="28" x2="34" y2="28" stroke-width="1"/>'
    '<line x1="20" y1="36" x2="34" y2="36" stroke-width="1"/>'
    '<line x1="20" y1="44" x2="34" y2="44" stroke-width="1"/>'
    '<line x1="20" y1="52" x2="34" y2="52" stroke-width="1"/>'
    '<line x1="20" y1="60" x2="34" y2="60" stroke-width="1"/>'
    '<line x1="20" y1="68" x2="34" y2="68" stroke-width="1"/>'
    '<line x1="20" y1="76" x2="34" y2="76" stroke-width="1"/>'
    '<line x1="20" y1="84" x2="34" y2="84" stroke-width="1"/>'
    '<line x1="20" y1="92" x2="34" y2="92" stroke-width="1"/>'
    '<rect x="44" y="20" width="14" height="80"/>'
    '<rect x="68" y="20" width="14" height="80"/>'
    '<rect x="92" y="20" width="14" height="80"/>'
    '<text x="63" y="115" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">4 tens = 40</text>'
    # 7 unit cubes
    '<rect x="150" y="80" width="14" height="14"/>'
    '<rect x="170" y="80" width="14" height="14"/>'
    '<rect x="190" y="80" width="14" height="14"/>'
    '<rect x="210" y="80" width="14" height="14"/>'
    '<rect x="230" y="80" width="14" height="14"/>'
    '<rect x="250" y="80" width="14" height="14"/>'
    '<rect x="270" y="80" width="14" height="14"/>'
    '<text x="217" y="115" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">7 ones</text>'
    '<text x="160" y="50" text-anchor="middle" font-size="14" font-weight="600" fill="currentColor" stroke="none">+</text>'
    '<text x="300" y="92" text-anchor="middle" font-size="14" font-weight="600" fill="currentColor" stroke="none">= 47</text>'
    '</svg>'
)

CLOCK_3_30 = (
    '<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
    '<circle cx="100" cy="100" r="80"/>'
    # Hour numbers
    '<text x="100" y="35" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">12</text>'
    '<text x="170" y="105" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">3</text>'
    '<text x="100" y="178" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">6</text>'
    '<text x="30" y="105" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">9</text>'
    '<text x="146" y="50" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">1</text>'
    '<text x="164" y="73" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">2</text>'
    '<text x="164" y="138" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">4</text>'
    '<text x="146" y="160" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">5</text>'
    '<text x="54" y="160" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">7</text>'
    '<text x="36" y="138" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">8</text>'
    '<text x="36" y="73" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">10</text>'
    '<text x="54" y="50" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">11</text>'
    # Center
    '<circle cx="100" cy="100" r="4" fill="currentColor"/>'
    # Hour hand — short, between 3 and 4 (halfway, since it is 3:30)
    '<line x1="100" y1="100" x2="138" y2="125" stroke-width="4"/>'
    # Minute hand — long, on 6 (180)
    '<line x1="100" y1="100" x2="100" y2="155" stroke-width="3"/>'
    '<text x="100" y="195" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">half past 3 (3:30)</text>'
    '</svg>'
)

COINS = [
    {"label": "Penny — 1¢", "svg": '<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><circle cx="60" cy="60" r="36"/><text x="60" y="65" text-anchor="middle" font-size="18" fill="currentColor" stroke="none">1¢</text><text x="60" y="110" text-anchor="middle" font-size="10" fill="currentColor" stroke="none">penny (smallest value)</text></svg>'},
    {"label": "Nickel — 5¢", "svg": '<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><circle cx="60" cy="60" r="42"/><text x="60" y="65" text-anchor="middle" font-size="18" fill="currentColor" stroke="none">5¢</text><text x="60" y="115" text-anchor="middle" font-size="10" fill="currentColor" stroke="none">nickel (bigger than penny)</text></svg>'},
    {"label": "Dime — 10¢ (smaller!)", "svg": '<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><circle cx="60" cy="60" r="30"/><text x="60" y="65" text-anchor="middle" font-size="16" fill="currentColor" stroke="none">10¢</text><text x="60" y="105" text-anchor="middle" font-size="10" fill="currentColor" stroke="none">dime — small but worth more!</text></svg>'},
    {"label": "Quarter — 25¢", "svg": '<svg viewBox="0 0 120 120" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><circle cx="60" cy="60" r="48"/><text x="60" y="65" text-anchor="middle" font-size="18" fill="currentColor" stroke="none">25¢</text><text x="60" y="115" text-anchor="middle" font-size="10" fill="currentColor" stroke="none">quarter (largest of the four)</text></svg>'},
]

MULT_ARRAY_3X4 = (
    '<svg viewBox="0 0 260 160" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
    # 3 rows of 4 dots
    + ''.join(
        f'<circle cx="{30 + col*55}" cy="{30 + row*40}" r="14" fill="currentColor"/>'
        for row in range(3)
        for col in range(4)
    )
    + '<text x="130" y="145" text-anchor="middle" font-size="12" fill="currentColor" stroke="none">3 rows × 4 columns = 12 (3 × 4 = 12)</text>'
    + '</svg>'
)

# ── Science diagrams ──────────────────────────────────────────

EARTH_TILT_SEASONS = (
    '<svg viewBox="0 0 360 220" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
    # Sun in middle
    '<circle cx="180" cy="110" r="22" fill="currentColor" opacity="0.5"/>'
    '<text x="180" y="115" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">Sun</text>'
    # Orbit (dashed ellipse)
    '<ellipse cx="180" cy="110" rx="140" ry="70" stroke-dasharray="3,4"/>'
    # Four earth positions
    # Right (summer in N hemisphere)
    '<g transform="translate(310 110)"><circle cx="0" cy="0" r="14"/><line x1="-10" y1="-12" x2="10" y2="12" stroke-width="1.5"/><text x="0" y="-22" text-anchor="middle" font-size="9" fill="currentColor" stroke="none">summer (N)</text></g>'
    # Left (winter in N)
    '<g transform="translate(50 110)"><circle cx="0" cy="0" r="14"/><line x1="-10" y1="-12" x2="10" y2="12" stroke-width="1.5"/><text x="0" y="-22" text-anchor="middle" font-size="9" fill="currentColor" stroke="none">winter (N)</text></g>'
    # Top (spring)
    '<g transform="translate(180 40)"><circle cx="0" cy="0" r="14"/><line x1="-10" y1="-12" x2="10" y2="12" stroke-width="1.5"/><text x="0" y="-18" text-anchor="middle" font-size="9" fill="currentColor" stroke="none">spring (N)</text></g>'
    # Bottom (fall)
    '<g transform="translate(180 180)"><circle cx="0" cy="0" r="14"/><line x1="-10" y1="-12" x2="10" y2="12" stroke-width="1.5"/><text x="0" y="208" text-anchor="middle" font-size="9" fill="currentColor" stroke="none">fall (N)</text></g>'
    '<text x="180" y="216" text-anchor="middle" font-size="10" fill="currentColor" stroke="none">Earth tilt is constant; the hemisphere tilted toward the Sun has summer</text>'
    '</svg>'
)

PLANT_CROSS_SECTION = (
    '<svg viewBox="0 0 220 280" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
    # Ground line
    '<line x1="0" y1="180" x2="220" y2="180" stroke-width="1.5" stroke-dasharray="4,3"/>'
    # Stem
    '<line x1="110" y1="180" x2="110" y2="50" stroke-width="2.5"/>'
    # Roots (branching downward)
    '<line x1="110" y1="180" x2="80" y2="220"/>'
    '<line x1="110" y1="180" x2="140" y2="220"/>'
    '<line x1="110" y1="180" x2="95" y2="250"/>'
    '<line x1="110" y1="180" x2="125" y2="250"/>'
    '<line x1="80" y1="220" x2="65" y2="245"/>'
    '<line x1="140" y1="220" x2="155" y2="245"/>'
    # Leaves (2 pairs)
    '<ellipse cx="80" cy="130" rx="22" ry="8" transform="rotate(-25 80 130)"/>'
    '<ellipse cx="140" cy="130" rx="22" ry="8" transform="rotate(25 140 130)"/>'
    '<ellipse cx="75" cy="90" rx="20" ry="7" transform="rotate(-25 75 90)"/>'
    '<ellipse cx="145" cy="90" rx="20" ry="7" transform="rotate(25 145 90)"/>'
    # Flower at top
    '<circle cx="110" cy="50" r="14"/>'
    '<circle cx="110" cy="50" r="5" fill="currentColor"/>'
    # Labels
    '<text x="55" y="55" text-anchor="end" font-size="11" fill="currentColor" stroke="none">flower</text>'
    '<line x1="60" y1="50" x2="92" y2="50" stroke-width="1"/>'
    '<text x="180" y="110" font-size="11" fill="currentColor" stroke="none">leaves</text>'
    '<line x1="160" y1="105" x2="178" y2="108" stroke-width="1"/>'
    '<text x="180" y="160" font-size="11" fill="currentColor" stroke="none">stem</text>'
    '<line x1="125" y1="155" x2="178" y2="158" stroke-width="1"/>'
    '<text x="180" y="225" font-size="11" fill="currentColor" stroke="none">roots</text>'
    '<line x1="145" y1="225" x2="178" y2="223" stroke-width="1"/>'
    '<text x="10" y="195" font-size="10" fill="currentColor" stroke="none">soil</text>'
    '</svg>'
)

WATER_CYCLE_SVG = (
    '<svg viewBox="0 0 360 220" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
    # Sun (top left)
    '<circle cx="50" cy="40" r="18"/>'
    '<line x1="50" y1="14" x2="50" y2="6" stroke-width="1.5"/>'
    '<line x1="76" y1="40" x2="84" y2="40" stroke-width="1.5"/>'
    '<line x1="24" y1="40" x2="16" y2="40" stroke-width="1.5"/>'
    '<line x1="68" y1="22" x2="74" y2="16" stroke-width="1.5"/>'
    '<line x1="32" y1="22" x2="26" y2="16" stroke-width="1.5"/>'
    '<text x="50" y="45" text-anchor="middle" font-size="9" fill="currentColor" stroke="none">Sun</text>'
    # Cloud (top right)
    '<path d="M 220 50 q -10 -20 10 -20 q 10 -15 30 0 q 25 -5 30 15 q 20 5 0 25 l -70 0 q -20 -10 0 -20 z"/>'
    '<text x="255" y="48" text-anchor="middle" font-size="10" fill="currentColor" stroke="none">cloud</text>'
    # Ocean / pond (bottom)
    '<path d="M 20 175 q 15 -8 30 0 q 15 8 30 0 q 15 -8 30 0 q 15 8 30 0 q 15 -8 30 0 q 15 8 30 0 q 15 -8 30 0 q 15 8 30 0 q 15 -8 30 0 q 15 8 30 0 l 0 35 l -340 0 z" fill="currentColor" opacity="0.15"/>'
    '<text x="120" y="200" font-size="10" fill="currentColor" stroke="none">lake / ocean</text>'
    # Evaporation arrows (up from water to cloud)
    '<line x1="100" y1="160" x2="100" y2="90" stroke-dasharray="3,3"/>'
    '<polygon points="97,93 103,93 100,82" fill="currentColor"/>'
    '<text x="105" y="125" font-size="10" fill="currentColor" stroke="none">evaporation</text>'
    # Precipitation arrows (down from cloud to ground)
    '<line x1="220" y1="78" x2="220" y2="160" stroke-dasharray="3,3"/>'
    '<polygon points="217,158 223,158 220,170" fill="currentColor"/>'
    '<line x1="240" y1="78" x2="240" y2="160" stroke-dasharray="3,3"/>'
    '<polygon points="237,158 243,158 240,170" fill="currentColor"/>'
    '<line x1="260" y1="78" x2="260" y2="160" stroke-dasharray="3,3"/>'
    '<polygon points="257,158 263,158 260,170" fill="currentColor"/>'
    '<text x="280" y="125" font-size="10" fill="currentColor" stroke="none">precipitation</text>'
    # Cycle arrow at bottom (collection back to evaporation start)
    '<text x="180" y="218" text-anchor="middle" font-size="10" fill="currentColor" stroke="none">collection: water gathers, cycle repeats</text>'
    '</svg>'
)

STATES_OF_MATTER_SVG = (
    '<svg viewBox="0 0 360 160" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
    # Solid box — tightly packed grid
    '<rect x="20" y="30" width="90" height="90"/>'
    + ''.join(
        f'<circle cx="{30 + col*16}" cy="{40 + row*16}" r="5" fill="currentColor"/>'
        for row in range(5) for col in range(5)
    )
    + '<text x="65" y="145" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">SOLID (tight)</text>'
    # Liquid — packed at bottom, looser
    '<rect x="135" y="30" width="90" height="90"/>'
    + ''.join(
        f'<circle cx="{145 + (col*18 + row*9) % 80}" cy="{50 + row*16}" r="5" fill="currentColor"/>'
        for row in range(4) for col in range(4)
    )
    + '<text x="180" y="145" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">LIQUID (loose)</text>'
    # Gas — sparse, spread out
    '<rect x="250" y="30" width="90" height="90"/>'
    '<circle cx="262" cy="42" r="5" fill="currentColor"/>'
    '<circle cx="298" cy="55" r="5" fill="currentColor"/>'
    '<circle cx="325" cy="48" r="5" fill="currentColor"/>'
    '<circle cx="275" cy="75" r="5" fill="currentColor"/>'
    '<circle cx="318" cy="85" r="5" fill="currentColor"/>'
    '<circle cx="285" cy="105" r="5" fill="currentColor"/>'
    '<circle cx="265" cy="92" r="5" fill="currentColor"/>'
    '<text x="295" y="145" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">GAS (free)</text>'
    + '</svg>'
)

# ── Social studies ────────────────────────────────────────────

COMPASS_ROSE = (
    '<svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'
    '<circle cx="100" cy="100" r="80"/>'
    # Four cardinal arrows
    '<polygon points="100,30 92,90 108,90" fill="currentColor"/>'
    '<polygon points="100,170 92,110 108,110" fill="currentColor" opacity="0.4"/>'
    '<polygon points="30,100 90,92 90,108" fill="currentColor" opacity="0.4"/>'
    '<polygon points="170,100 110,92 110,108" fill="currentColor" opacity="0.4"/>'
    # Center
    '<circle cx="100" cy="100" r="5" fill="currentColor"/>'
    # Labels
    '<text x="100" y="22" text-anchor="middle" font-size="16" font-weight="600" fill="currentColor" stroke="none">N</text>'
    '<text x="100" y="195" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">S</text>'
    '<text x="18" y="106" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">W</text>'
    '<text x="182" y="106" text-anchor="middle" font-size="14" fill="currentColor" stroke="none">E</text>'
    '<text x="100" y="190" text-anchor="middle" font-size="9" fill="currentColor" stroke="none" opacity="0.6">NEWS reads clockwise: N → E → S → W</text>'
    '</svg>'
)


# ── Backfill table ────────────────────────────────────────────

BACKFILLS = [
    ("data/math/units.jsonl", "math_addition_within_10", [
        {"label": "Ten-frame: 3 + 4 = 7", "svg": TENFRAME_3PLUS4},
    ]),
    ("data/math/units.jsonl", "math_subtraction_within_10", [
        {"label": "Ten-frame: 7 − 3 = 4", "svg": TENFRAME_SUBTRACT},
    ]),
    ("data/math/units.jsonl", "math_addition_within_20", [
        {"label": "Make-a-ten: 8 + 5 = 13", "svg": TENFRAME_PAIR_MAKE_TEN},
    ]),
    ("data/math/units.jsonl", "math_subtraction_within_20", [
        {"label": "Back through ten: 13 − 5 = 8", "svg": TENFRAME_PAIR_BACK_THROUGH},
    ]),
    ("data/math/units.jsonl", "math_place_value_tens", [
        {"label": "Base-ten blocks: 47 = 4 tens + 7 ones", "svg": PLACE_VALUE_47},
    ]),
    ("data/math/units.jsonl", "math_money_coins", COINS),
    ("data/math/units.jsonl", "math_time_oclock", [
        {"label": "Analog clock at 3:30", "svg": CLOCK_3_30},
    ]),
    ("data/math/units.jsonl", "math_multiplication_intro", [
        {"label": "Array: 3 × 4 = 12", "svg": MULT_ARRAY_3X4},
    ]),
    ("data/science/units.jsonl", "science_seasons", [
        {"label": "Earth's orbit + tilt", "svg": EARTH_TILT_SEASONS},
    ]),
    ("data/science/units.jsonl", "science_plant_parts", [
        {"label": "Plant cross-section", "svg": PLANT_CROSS_SECTION},
    ]),
    ("data/science/units.jsonl", "science_water_cycle", [
        {"label": "Water cycle", "svg": WATER_CYCLE_SVG},
    ]),
    ("data/science/units.jsonl", "science_states_matter", [
        {"label": "Particle arrangement by state", "svg": STATES_OF_MATTER_SVG},
    ]),
    ("data/social_studies/units.jsonl", "social_map_skills", [
        {"label": "Compass rose", "svg": COMPASS_ROSE},
    ]),
]


def backfill(file_rel: str, target_id: str, svg_diagrams):
    path = os.path.join(REPO, file_rel)
    out_lines = []
    found = False
    skipped = False
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
                if rec.get("svg_diagrams"):
                    # Already has diagrams — don't overwrite
                    skipped = True
                    out_lines.append(line)
                    continue
                rec["svg_diagrams"] = svg_diagrams
                line = json.dumps(rec, ensure_ascii=False)
                found = True
            out_lines.append(line)
    if not found and not skipped:
        print(f"WARN: {target_id!r} not found in {file_rel}", file=sys.stderr)
        return False
    if skipped:
        print(f"skip (already has diagrams): {target_id}")
        return True
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out_lines) + "\n")
    print(f"backfilled: {target_id}")
    return True


total = 0
ok = 0
for file_rel, target_id, diagrams in BACKFILLS:
    total += 1
    if backfill(file_rel, target_id, diagrams):
        ok += 1
print(f"\n{ok}/{total} backfills completed")
