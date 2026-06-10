"""Seed twelve evidence-honest herb monographs for the Apothecary.

Each monograph carries:
  - name + scientific_name + common_names
  - parts_used + preparations (with doses)
  - evidence_verdicts: list of {claim, verdict, note} — engine's CONFIRMED/MIXED/DISCORDANT
  - safety_notes (pregnancy, drug interactions, dose ceiling)
  - growing notes
  - svg_diagram: line-art botanical illustration
  - summary, domains, axes

Verdicts follow the engine's ledger: honesty over advocacy. If the
evidence is mixed, we say so. If a folk claim doesn't hold up, we mark
it DISCORDANT. Same honest verdict the rest of the substrate provides.
"""
from __future__ import annotations
import json
import os

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def leaf(cx, cy, w, h, rot=0):
    return (
        f'<ellipse cx="{cx}" cy="{cy}" rx="{w}" ry="{h}" '
        f'transform="rotate({rot} {cx} {cy})"/>'
        f'<line x1="{cx - w*0.7}" y1="{cy}" x2="{cx + w*0.7}" y2="{cy}" stroke-width="1" '
        f'transform="rotate({rot} {cx} {cy})"/>'
    )


SVG_OPEN = '<svg viewBox="0 0 200 180" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2">'


def label(text, y=170):
    return f'<text x="100" y="{y}" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">{text}</text>'


GINGER_SVG = ''.join([
    SVG_OPEN,
    '<path d="M 30 130 q 10 -15 30 -10 q 15 5 25 -5 q 15 -10 35 0 q 10 8 25 0 q 15 -10 30 -5"/>',
    '<path d="M 30 130 q 10 5 30 5 q 15 0 25 8 q 15 12 35 5 q 10 -3 25 0 q 15 5 30 0"/>',
    '<circle cx="70" cy="125" r="5"/>',
    '<circle cx="115" cy="120" r="5"/>',
    '<circle cx="155" cy="125" r="5"/>',
    '<line x1="60" y1="120" x2="55" y2="30"/>',
    '<line x1="100" y1="115" x2="100" y2="20"/>',
    '<line x1="140" y1="118" x2="148" y2="35"/>',
    leaf(45, 60, 18, 5, -75),
    leaf(70, 50, 22, 5, -65),
    leaf(110, 50, 20, 5, -90),
    leaf(95, 35, 18, 4, -85),
    leaf(140, 65, 20, 5, -85),
    leaf(160, 55, 18, 5, -80),
    label('Ginger — root (rhizome)'),
    '</svg>',
])

PEPPERMINT_SVG = ''.join([
    SVG_OPEN,
    '<line x1="98" y1="160" x2="98" y2="20"/>',
    '<line x1="102" y1="160" x2="102" y2="20"/>',
    leaf(70, 140, 18, 8, -25),
    leaf(130, 140, 18, 8, 25),
    leaf(70, 110, 16, 7, -30),
    leaf(130, 110, 16, 7, 30),
    leaf(75, 80, 14, 6, -35),
    leaf(125, 80, 14, 6, 35),
    leaf(80, 55, 12, 5, -40),
    leaf(120, 55, 12, 5, 40),
    '<line x1="55" y1="138" x2="60" y2="135" stroke-width="1"/>',
    '<line x1="55" y1="142" x2="60" y2="145" stroke-width="1"/>',
    label('Peppermint — leaves (opposite, serrated)', 175),
    '</svg>',
])

CHAMOMILE_SVG = ''.join([
    SVG_OPEN,
    '<line x1="100" y1="160" x2="100" y2="60"/>',
    '<line x1="100" y1="120" x2="80" y2="115" stroke-width="1"/>',
    '<line x1="100" y1="120" x2="85" y2="125" stroke-width="1"/>',
    '<line x1="100" y1="120" x2="120" y2="115" stroke-width="1"/>',
    '<line x1="100" y1="120" x2="115" y2="125" stroke-width="1"/>',
    '<line x1="100" y1="100" x2="82" y2="95" stroke-width="1"/>',
    '<line x1="100" y1="100" x2="118" y2="95" stroke-width="1"/>',
    '<line x1="100" y1="100" x2="85" y2="105" stroke-width="1"/>',
    '<line x1="100" y1="100" x2="115" y2="105" stroke-width="1"/>',
    '<circle cx="100" cy="50" r="8" fill="currentColor"/>',
    '<ellipse cx="100" cy="32" rx="3" ry="9"/>',
    '<ellipse cx="100" cy="68" rx="3" ry="9"/>',
    '<ellipse cx="82" cy="50" rx="9" ry="3"/>',
    '<ellipse cx="118" cy="50" rx="9" ry="3"/>',
    label('Chamomile — flowers (daisy-like)', 175),
    '</svg>',
])

GARLIC_SVG = ''.join([
    SVG_OPEN,
    '<ellipse cx="100" cy="120" rx="38" ry="34"/>',
    '<path d="M 100 86 L 100 154" stroke-width="1"/>',
    '<path d="M 70 105 Q 100 88 130 105" stroke-width="1"/>',
    '<path d="M 70 135 Q 100 152 130 135" stroke-width="1"/>',
    '<path d="M 78 88 L 78 152" stroke-width="1"/>',
    '<path d="M 122 88 L 122 152" stroke-width="1"/>',
    '<line x1="100" y1="86" x2="100" y2="25"/>',
    '<line x1="100" y1="40" x2="75" y2="20"/>',
    '<line x1="100" y1="35" x2="125" y2="15"/>',
    '<line x1="100" y1="45" x2="70" y2="50"/>',
    label('Garlic — bulb (cloves)', 175),
    '</svg>',
])

TURMERIC_SVG = ''.join([
    SVG_OPEN,
    '<path d="M 25 135 q 12 -12 30 -8 q 18 4 35 -4 q 18 -10 40 0 q 12 6 30 -2 q 12 -8 25 -3"/>',
    '<path d="M 25 135 q 12 8 30 8 q 18 0 35 10 q 18 12 40 5 q 12 -3 30 5 q 12 5 25 0"/>',
    '<line x1="60" y1="135" x2="60" y2="155" stroke-width="1"/>',
    '<line x1="105" y1="138" x2="105" y2="158" stroke-width="1"/>',
    '<path d="M 100 122 Q 70 80 50 30 Q 80 80 100 122"/>',
    '<path d="M 100 122 Q 130 75 150 25 Q 120 80 100 122"/>',
    '<path d="M 100 122 Q 100 70 100 18"/>',
    label('Turmeric — root (yellow-orange)', 175),
    '</svg>',
])

ALOE_SVG = ''.join([
    SVG_OPEN,
    '<polygon points="65,160 135,160 130,135 70,135"/>',
    '<line x1="68" y1="135" x2="132" y2="135" stroke-width="1.5"/>',
    '<path d="M 100 135 Q 85 90 75 30"/>',
    '<path d="M 100 135 Q 100 80 100 20"/>',
    '<path d="M 100 135 Q 115 90 125 30"/>',
    '<line x1="78" y1="65" x2="82" y2="63" stroke-width="1"/>',
    '<line x1="78" y1="80" x2="82" y2="78" stroke-width="1"/>',
    '<line x1="118" y1="65" x2="122" y2="63" stroke-width="1"/>',
    '<line x1="118" y1="80" x2="122" y2="78" stroke-width="1"/>',
    label('Aloe vera — leaves (gel inside)', 175),
    '</svg>',
])

WILLOW_SVG = ''.join([
    SVG_OPEN,
    '<rect x="92" y="40" width="16" height="100"/>',
    '<line x1="95" y1="50" x2="105" y2="55" stroke-width="1"/>',
    '<line x1="94" y1="75" x2="106" y2="72" stroke-width="1"/>',
    '<line x1="95" y1="100" x2="104" y2="105" stroke-width="1"/>',
    '<line x1="94" y1="125" x2="106" y2="122" stroke-width="1"/>',
    leaf(75, 30, 18, 4, -30),
    leaf(125, 30, 18, 4, 30),
    leaf(60, 50, 16, 4, -50),
    leaf(140, 50, 16, 4, 50),
    label('Willow — bark (salicin source)'),
    '</svg>',
])

LAVENDER_SVG = ''.join([
    SVG_OPEN,
    '<line x1="100" y1="160" x2="100" y2="60"/>',
    '<line x1="80" y1="155" x2="80" y2="70"/>',
    '<line x1="120" y1="155" x2="120" y2="70"/>',
    '<ellipse cx="100" cy="55" rx="4" ry="4"/>',
    '<ellipse cx="100" cy="45" rx="4" ry="4"/>',
    '<ellipse cx="100" cy="35" rx="4" ry="4"/>',
    '<ellipse cx="100" cy="25" rx="4" ry="4"/>',
    '<ellipse cx="80" cy="65" rx="4" ry="4"/>',
    '<ellipse cx="80" cy="55" rx="4" ry="4"/>',
    '<ellipse cx="80" cy="45" rx="4" ry="4"/>',
    '<ellipse cx="120" cy="65" rx="4" ry="4"/>',
    '<ellipse cx="120" cy="55" rx="4" ry="4"/>',
    '<ellipse cx="120" cy="45" rx="4" ry="4"/>',
    label('Lavender — flowers + essential oil', 175),
    '</svg>',
])

HONEY_SVG = ''.join([
    SVG_OPEN,
    '<rect x="65" y="55" width="70" height="100" rx="4"/>',
    '<rect x="60" y="45" width="80" height="15" rx="2"/>',
    '<line x1="75" y1="75" x2="125" y2="75" stroke-width="1"/>',
    '<path d="M 70 90 Q 85 85 100 90 Q 115 95 130 90" stroke-width="1"/>',
    '<path d="M 70 105 Q 85 100 100 105 Q 115 110 130 105" stroke-width="1"/>',
    '<path d="M 70 120 Q 85 115 100 120 Q 115 125 130 120" stroke-width="1"/>',
    '<path d="M 70 135 Q 85 130 100 135 Q 115 140 130 135" stroke-width="1"/>',
    '<polygon points="155,30 165,25 175,30 175,40 165,45 155,40"/>',
    '<polygon points="155,50 165,45 175,50 175,60 165,65 155,60"/>',
    label('Honey — raw, local', 175),
    '</svg>',
])

ELDERBERRY_SVG = ''.join([
    SVG_OPEN,
    '<line x1="100" y1="160" x2="100" y2="60"/>',
    '<line x1="100" y1="120" x2="70" y2="100"/>',
    '<line x1="100" y1="100" x2="130" y2="80"/>',
    leaf(60, 100, 12, 5, -20),
    leaf(75, 90, 12, 5, -20),
    leaf(135, 80, 12, 5, 20),
    leaf(120, 70, 12, 5, 20),
    '<circle cx="92" cy="50" r="3" fill="currentColor"/>',
    '<circle cx="100" cy="48" r="3" fill="currentColor"/>',
    '<circle cx="108" cy="50" r="3" fill="currentColor"/>',
    '<circle cx="96" cy="42" r="3" fill="currentColor"/>',
    '<circle cx="104" cy="42" r="3" fill="currentColor"/>',
    '<circle cx="88" cy="44" r="3" fill="currentColor"/>',
    '<circle cx="112" cy="44" r="3" fill="currentColor"/>',
    '<circle cx="100" cy="35" r="3" fill="currentColor"/>',
    label('Elderberry — ripe berries only (raw = toxic)', 175),
    '</svg>',
])

THYME_SVG = ''.join([
    SVG_OPEN,
    '<line x1="100" y1="160" x2="100" y2="30"/>',
    '<line x1="100" y1="130" x2="70" y2="110"/>',
    '<line x1="100" y1="130" x2="130" y2="110"/>',
    '<line x1="100" y1="90" x2="65" y2="80"/>',
    '<line x1="100" y1="90" x2="135" y2="80"/>',
    '<line x1="100" y1="60" x2="80" y2="50"/>',
    '<line x1="100" y1="60" x2="120" y2="50"/>',
    ''.join(f'<ellipse cx="{x}" cy="{y}" rx="3" ry="1.5" transform="rotate({r} {x} {y})"/>'
            for x, y, r in [(75, 115, -30), (80, 110, -30), (85, 105, -30),
                            (125, 115, 30), (120, 110, 30), (115, 105, 30),
                            (70, 85, -20), (75, 80, -20), (80, 75, -20),
                            (130, 85, 20), (125, 80, 20), (120, 75, 20)]),
    label('Thyme — leaves + sprigs', 175),
    '</svg>',
])

LEMON_BALM_SVG = ''.join([
    SVG_OPEN,
    '<line x1="98" y1="160" x2="98" y2="30"/>',
    '<line x1="102" y1="160" x2="102" y2="30"/>',
    leaf(70, 135, 14, 7, -10),
    leaf(130, 135, 14, 7, 10),
    leaf(70, 95, 14, 7, -10),
    leaf(130, 95, 14, 7, 10),
    leaf(75, 55, 12, 6, -10),
    leaf(125, 55, 12, 6, 10),
    label('Lemon balm — leaves (lemon-scented mint)', 175),
    '</svg>',
])


HERB_MONOGRAPHS = [
    {
        "id": "herb_ginger",
        "name": "Ginger",
        "scientific_name": "Zingiber officinale",
        "common_names": ["ginger root", "fresh ginger", "ginger rhizome"],
        "parts_used": ["rhizome (underground stem)"],
        "traditional_uses": [
            "Nausea (motion sickness, morning sickness, post-operative, chemotherapy)",
            "Digestion (mild dyspepsia, gas, bloating)",
            "Mild anti-inflammatory (joint discomfort)",
        ],
        "evidence_verdicts": [
            {"claim": "Ginger reduces nausea (motion, pregnancy, chemo, post-op)", "verdict": "CONFIRMED", "note": "Cochrane reviews and meta-analyses support 1-1.5g/day in divided doses for several nausea contexts."},
            {"claim": "Ginger reduces arthritis or muscle pain", "verdict": "MIXED", "note": "Small RCTs show modest effects on osteoarthritis pain; quality limited."},
            {"claim": "Ginger 'detoxes' the body", "verdict": "DISCORDANT", "note": "No medical definition of 'detox' that ginger meets. The body detoxes via liver and kidneys."},
        ],
        "preparations": [
            "Fresh root: peel and slice 1-inch (~5g); chew, add to food, or steep in hot water 10 min for tea",
            "Dried powder: 250-1000 mg per dose, up to 4x per day (max ~4g/day for adults)",
            "Capsules: follow label; typical 500-1000 mg twice daily",
        ],
        "safety_notes": [
            "Generally safe at culinary doses (<5g/day)",
            "May increase bleeding risk — caution with warfarin, aspirin, anticoagulants",
            "Pregnancy: 1g/day or less considered safe in most guidelines",
            "Stop 2 weeks before surgery",
        ],
        "growing": "Tropical to subtropical. Plant rhizome pieces (each with an 'eye') 1-2 inches deep in pots indoors (warm, indirect light). Harvest after 8-10 months. Easy from grocery-store ginger.",
        "summary": "Ginger root for nausea is one of the best-evidenced botanical remedies — Cochrane-confirmed across multiple contexts at 1-1.5g/day. Safe at culinary doses; meaningful interaction risk with blood thinners.",
        "svg_diagram": GINGER_SVG,
        "domains": ["medicine", "nutrition", "agriculture", "biology"],
        "axes": ["physical_substance", "metabolism", "authority_trust"],
    },
    {
        "id": "herb_peppermint",
        "name": "Peppermint",
        "scientific_name": "Mentha × piperita",
        "common_names": ["mint", "peppermint leaf", "peppermint oil"],
        "parts_used": ["leaves (fresh or dried)", "essential oil"],
        "traditional_uses": ["Indigestion, gas, bloating", "Irritable bowel syndrome (IBS)", "Tension headache (topical oil)"],
        "evidence_verdicts": [
            {"claim": "Enteric-coated peppermint oil reduces IBS symptoms", "verdict": "CONFIRMED", "note": "Multiple RCTs and meta-analyses; recommended by some GI guidelines."},
            {"claim": "Topical peppermint oil eases tension headaches", "verdict": "MIXED", "note": "Small studies positive; comparable to acetaminophen for some users."},
            {"claim": "Peppermint heals stomach ulcers", "verdict": "DISCORDANT", "note": "May actually worsen reflux/GERD by relaxing the lower esophageal sphincter."},
        ],
        "preparations": [
            "Tea: 1 tsp dried leaf or a few fresh leaves steeped 10 min in hot water; up to 3x daily",
            "Enteric-coated capsules: 180-225 mg of peppermint oil, 2-3x daily before meals (for IBS)",
            "Topical: dilute 2-3 drops in a teaspoon of carrier oil; rub on temples for headache",
        ],
        "safety_notes": [
            "Avoid in active GERD/reflux — peppermint relaxes the lower esophageal sphincter",
            "Essential oil is concentrated — never apply undiluted or take internally without proper formulation",
            "Avoid menthol-heavy preparations near infant faces (apnea risk)",
        ],
        "growing": "Vigorous perennial. Plant in a CONTAINED pot — spreads aggressively. Partial sun, moist soil. Harvest before flowering for strongest flavor.",
        "summary": "Peppermint is best-evidenced for IBS symptoms (enteric-coated oil capsules) and tension headache (diluted topical oil). Don't use if you have reflux — it can make GERD worse.",
        "svg_diagram": PEPPERMINT_SVG,
        "domains": ["medicine", "nutrition", "agriculture", "biology"],
        "axes": ["physical_substance", "metabolism", "authority_trust"],
    },
    {
        "id": "herb_chamomile",
        "name": "Chamomile",
        "scientific_name": "Matricaria chamomilla (German) or Chamaemelum nobile (Roman)",
        "common_names": ["German chamomile", "Roman chamomile", "manzanilla"],
        "parts_used": ["flower heads"],
        "traditional_uses": ["Mild anxiety and restlessness", "Mild sleep difficulties", "Digestive upset (especially in children)"],
        "evidence_verdicts": [
            {"claim": "Chamomile mildly reduces generalized anxiety", "verdict": "MIXED", "note": "A few small RCTs (200-1500 mg/day extract) show benefit; effects modest."},
            {"claim": "Chamomile is safe as a daily calming tea", "verdict": "CONFIRMED", "note": "Long history of safe culinary use; main caution is ragweed allergy cross-reactivity."},
        ],
        "preparations": [
            "Tea: 2-3 tsp dried flowers steeped 10 min in hot water, 1-4 cups daily",
            "Standardized capsules: 200-400 mg of standardized extract, 1-3x daily",
        ],
        "safety_notes": [
            "Possible allergy in people sensitive to ragweed, daisies, or marigolds",
            "Generally safe in pregnancy at tea doses; concentrated extracts less studied",
        ],
        "growing": "Cool-season annual or perennial. Direct-sow in spring; full sun, well-drained soil. Self-seeds reliably. Harvest flowers when fully open; dry on a screen.",
        "summary": "Chamomile tea is a gentle, well-tolerated calming and sleep aid with mild evidence support. Watch for ragweed allergy.",
        "svg_diagram": CHAMOMILE_SVG,
        "domains": ["medicine", "agriculture", "biology"],
        "axes": ["physical_substance", "metabolism", "authority_trust"],
    },
    {
        "id": "herb_garlic",
        "name": "Garlic",
        "scientific_name": "Allium sativum",
        "common_names": ["garlic", "allium"],
        "parts_used": ["bulb (cloves), fresh or aged"],
        "traditional_uses": ["Cardiovascular support (blood pressure, cholesterol)", "Mild antimicrobial (folk use for colds)"],
        "evidence_verdicts": [
            {"claim": "Garlic produces a small reduction in blood pressure", "verdict": "MIXED", "note": "Meta-analyses suggest ~4-8 mmHg systolic drop at 600-1500 mg/day of aged garlic extract; modest."},
            {"claim": "Garlic reduces total cholesterol", "verdict": "MIXED", "note": "Small effect (~5%); not enough to replace statins for high-risk patients."},
        ],
        "preparations": [
            "Fresh: 1-2 cloves daily, crushed and rested 10 min before cooking (allicin forms)",
            "Aged garlic extract: 600-1200 mg/day for cardiovascular support",
        ],
        "safety_notes": [
            "Significant blood-thinning effect — caution with warfarin, aspirin, before surgery",
            "Heartburn possible at high doses",
        ],
        "growing": "Plant individual cloves (pointed end up) in fall in temperate climates; harvest mid-summer when half the leaves yellow. One of the easiest crops.",
        "summary": "Garlic has real but modest cardiovascular effects (BP, cholesterol). Easy to grow. Watch the bleeding-risk interaction with blood thinners.",
        "svg_diagram": GARLIC_SVG,
        "domains": ["medicine", "nutrition", "agriculture", "biology"],
        "axes": ["physical_substance", "metabolism", "authority_trust"],
    },
    {
        "id": "herb_turmeric",
        "name": "Turmeric",
        "scientific_name": "Curcuma longa",
        "common_names": ["turmeric", "curcumin (active compound)"],
        "parts_used": ["rhizome (root)"],
        "traditional_uses": ["Anti-inflammatory (joint pain, arthritis)", "Digestive support", "Cooking spice"],
        "evidence_verdicts": [
            {"claim": "Turmeric/curcumin reduces osteoarthritis pain", "verdict": "MIXED", "note": "Several RCTs show modest pain reduction comparable to ibuprofen for OA; quality varies."},
            {"claim": "Curcumin alone is poorly absorbed", "verdict": "CONFIRMED", "note": "Bioavailability is very low without black pepper (piperine) or liposomal formulations."},
            {"claim": "Turmeric prevents Alzheimer's or cures cancer", "verdict": "DISCORDANT", "note": "Strong cell-culture effects; no convincing human evidence for prevention/cure."},
        ],
        "preparations": [
            "Culinary: 1-2 tsp daily in cooking (piperine in black pepper helps absorption)",
            "Supplement: 500 mg curcumin extract with piperine 2x daily for inflammation",
            "Golden milk: 1 tsp turmeric + warm milk + pinch black pepper + honey",
        ],
        "safety_notes": [
            "Mild blood-thinning — caution with anticoagulants and surgery",
            "May worsen gallbladder issues (stimulates bile)",
            "Stains yellow",
        ],
        "growing": "Tropical. Plant rhizomes in pots indoors. Slow grower — 8-10 months.",
        "summary": "Turmeric/curcumin has modest evidence for osteoarthritis pain — comparable to ibuprofen in some studies. Critical: curcumin is barely absorbed without piperine.",
        "svg_diagram": TURMERIC_SVG,
        "domains": ["medicine", "nutrition", "agriculture", "biology"],
        "axes": ["physical_substance", "metabolism", "authority_trust"],
    },
    {
        "id": "herb_aloe_vera",
        "name": "Aloe vera",
        "scientific_name": "Aloe barbadensis miller",
        "common_names": ["aloe", "true aloe"],
        "parts_used": ["leaf gel (inner clear flesh)"],
        "traditional_uses": ["Sunburn and minor burns (topical)", "Skin irritation, cuts (topical)"],
        "evidence_verdicts": [
            {"claim": "Topical aloe vera gel speeds first- and second-degree burn healing", "verdict": "CONFIRMED", "note": "Multiple clinical studies show modest acceleration of healing for minor/superficial burns."},
            {"claim": "Aloe juice (internal) cures digestive disease", "verdict": "DISCORDANT", "note": "Aloe latex is a strong laxative; chronic use is hard on the colon. Not recommended."},
        ],
        "preparations": [
            "Topical gel from fresh leaf: split a leaf, scoop the clear inner gel, apply directly",
            "Store-bought aloe gel: 99%+ pure aloe; check ingredients",
            "DO NOT consume aloe latex (yellow layer just under skin)",
        ],
        "safety_notes": [
            "Topical: very safe; patch-test for allergy first",
            "DO NOT take internally (especially aloe latex)",
            "Pregnancy: avoid internal use",
        ],
        "growing": "Easiest succulent. Indoor pot, bright indirect light. Water only when soil is fully dry. Propagates by pups. One plant supplies a family.",
        "summary": "Aloe vera gel topically for minor burns and skin irritation is well-evidenced and safe. Do NOT take aloe internally. Easy houseplant — 'fresh medicine on the windowsill'.",
        "svg_diagram": ALOE_SVG,
        "domains": ["medicine", "agriculture", "biology"],
        "axes": ["physical_substance", "metabolism", "authority_trust"],
    },
    {
        "id": "herb_willow_bark",
        "name": "Willow bark",
        "scientific_name": "Salix alba (white willow)",
        "common_names": ["white willow", "willow bark"],
        "parts_used": ["inner bark of branches"],
        "traditional_uses": ["Pain (headache, lower back, muscle)", "Mild fever", "Joint inflammation"],
        "evidence_verdicts": [
            {"claim": "Willow bark eases lower back pain", "verdict": "CONFIRMED", "note": "RCTs of standardized extract (120-240 mg salicin/day) show comparable effect to NSAIDs for chronic LBP."},
            {"claim": "Willow bark is the natural source of aspirin", "verdict": "CONFIRMED", "note": "Salicin is converted in the body to salicylic acid — what aspirin is based on."},
        ],
        "preparations": [
            "Standardized extract capsules: 120-240 mg salicin daily for pain",
            "Tea (bitter): 1-2 tsp dried bark simmered 15 min in water",
        ],
        "safety_notes": [
            "Same cautions as aspirin: avoid in children with viral illness (Reye's syndrome risk)",
            "Bleeding risk — caution with anticoagulants and before surgery",
            "Avoid in salicylate allergy",
            "Avoid in late pregnancy",
        ],
        "growing": "White willow grows well near water in temperate climates. Harvest inner bark from 2-3-year-old branches in spring. Wild-craft responsibly.",
        "summary": "Willow bark is the historical and biochemical ancestor of aspirin. Standardized extract is well-evidenced for chronic low back pain. Same safety profile as aspirin.",
        "svg_diagram": WILLOW_SVG,
        "domains": ["medicine", "biology", "agriculture"],
        "axes": ["physical_substance", "metabolism", "authority_trust"],
    },
    {
        "id": "herb_lavender",
        "name": "Lavender",
        "scientific_name": "Lavandula angustifolia",
        "common_names": ["English lavender", "true lavender"],
        "parts_used": ["flowers", "essential oil"],
        "traditional_uses": ["Mild anxiety", "Mild sleep difficulties", "Aromatherapy"],
        "evidence_verdicts": [
            {"claim": "Oral lavender oil (Silexan, 80 mg/day) reduces generalized anxiety", "verdict": "CONFIRMED", "note": "Multiple RCTs of standardized lavender oil show effect comparable to low-dose benzodiazepines with fewer side effects."},
            {"claim": "Lavender essential oil applied undiluted is safe", "verdict": "DISCORDANT", "note": "Skin irritation common; possible endocrine effects in prepubescent boys with chronic undiluted topical use."},
        ],
        "preparations": [
            "Standardized oral capsule (Silexan): 80 mg once daily for anxiety",
            "Tea: 1-2 tsp dried flowers steeped 10 min",
            "Aromatherapy: 2-4 drops oil in diffuser",
            "Topical: 2-3 drops oil per tsp carrier oil — never undiluted",
        ],
        "safety_notes": [
            "Avoid undiluted topical application",
            "Avoid chronic undiluted topical use in prepubescent children (endocrine concern)",
        ],
        "growing": "Hardy perennial zones 5-9. Full sun, well-drained alkaline soil. Drought-tolerant.",
        "summary": "Lavender oil (Silexan, 80 mg/day) is the best-evidenced botanical for generalized anxiety — comparable to low-dose benzodiazepines without dependence.",
        "svg_diagram": LAVENDER_SVG,
        "domains": ["medicine", "agriculture", "biology"],
        "axes": ["physical_substance", "metabolism", "authority_trust"],
    },
    {
        "id": "herb_honey",
        "name": "Honey",
        "scientific_name": "Apis mellifera (honey bee product)",
        "common_names": ["raw honey", "manuka honey", "local honey"],
        "parts_used": ["honey (the substance itself)"],
        "traditional_uses": ["Cough suppression (nighttime, in children >1 yr)", "Sore throat", "Wound healing (medical-grade)"],
        "evidence_verdicts": [
            {"claim": "Honey suppresses nighttime cough in children over 1 yr", "verdict": "CONFIRMED", "note": "Multiple RCTs; WHO recommends for cough in children >1 (NOT under 1)."},
            {"claim": "Medical-grade honey speeds wound healing", "verdict": "CONFIRMED", "note": "Used in hospitals (Medihoney) for chronic wounds, burns, ulcers."},
            {"claim": "Honey is safe for infants under 1 year", "verdict": "DISCORDANT", "note": "HARD RULE: never give honey to a baby under 12 months — infant botulism risk."},
        ],
        "preparations": [
            "Cough: 1-2 tsp raw honey 30 min before bed (over age 1)",
            "Sore throat: stir into warm water with lemon",
            "Wound: medical-grade honey (Medihoney) directly on minor wound; cover",
        ],
        "safety_notes": [
            "ABSOLUTE RULE: never give honey to infants under 12 months (botulism risk)",
            "Diabetics: still sugar — counts toward carb totals",
            "Manuka honey has highest antimicrobial activity",
        ],
        "growing": "Keep honeybees. Backyard hives legal in most US locations. Start with a mentor and a single nuc colony.",
        "summary": "Honey is well-evidenced for nighttime cough in children >1 and wound healing (medical-grade). The hard rule: NEVER for infants under 1.",
        "svg_diagram": HONEY_SVG,
        "domains": ["medicine", "nutrition", "agriculture", "biology"],
        "axes": ["physical_substance", "metabolism", "authority_trust"],
    },
    {
        "id": "herb_elderberry",
        "name": "Elderberry",
        "scientific_name": "Sambucus nigra",
        "common_names": ["black elder", "elderberry", "sambucus"],
        "parts_used": ["ripe black berries (cooked)", "flowers"],
        "traditional_uses": ["Influenza / cold support", "Antioxidant-rich syrup"],
        "evidence_verdicts": [
            {"claim": "Elderberry syrup shortens duration of flu", "verdict": "MIXED", "note": "Several small RCTs show ~3-4 days shorter symptoms; quality moderate; replication needed."},
            {"claim": "Raw elderberries are safe to eat", "verdict": "DISCORDANT", "note": "Raw berries, leaves, bark contain cyanogenic glycosides. ALWAYS cook before consuming."},
            {"claim": "Elderberry is a substitute for flu vaccination", "verdict": "DISCORDANT", "note": "No. Vaccines have far more evidence and prevent severe disease."},
        ],
        "preparations": [
            "Syrup: simmer 1 cup dried berries with 3 cups water 30-45 min; strain; add honey",
            "Dose (cold/flu, adult): 1 tbsp syrup 3-4x daily at onset of symptoms",
        ],
        "safety_notes": [
            "NEVER consume raw berries, leaves, or bark — cyanogenic compounds",
            "Cooking 30+ min destroys the toxins",
            "Use as supportive care, not as flu vaccine replacement",
        ],
        "growing": "Hardy shrub zones 3-9. Grows wild in much of North America and Europe. Harvest umbels when fully black/purple.",
        "summary": "Elderberry has mixed evidence for shortening flu duration when used at symptom onset. CRITICAL: raw berries are toxic — always cook. Not a flu-vaccine substitute.",
        "svg_diagram": ELDERBERRY_SVG,
        "domains": ["medicine", "nutrition", "agriculture", "biology"],
        "axes": ["physical_substance", "metabolism", "authority_trust"],
    },
    {
        "id": "herb_thyme",
        "name": "Thyme",
        "scientific_name": "Thymus vulgaris",
        "common_names": ["common thyme", "garden thyme"],
        "parts_used": ["leaves and flowering tops"],
        "traditional_uses": ["Cough (especially bronchitis)", "Sore throat (gargle)", "Cooking"],
        "evidence_verdicts": [
            {"claim": "Thyme syrup reduces acute bronchitis cough", "verdict": "MIXED", "note": "Several RCTs (thyme + ivy, thyme + primrose) show modest cough reduction."},
            {"claim": "Thymol (active compound) is antimicrobial", "verdict": "CONFIRMED", "note": "Demonstrated in vitro against many bacteria and fungi; used in some commercial mouthwashes."},
            {"claim": "Thyme tea cures pneumonia or strep throat", "verdict": "DISCORDANT", "note": "Serious infections need evaluation and often antibiotics. Thyme is supportive, not curative."},
        ],
        "preparations": [
            "Tea: 1 tsp dried (or 2-3 sprigs fresh) steeped 10 min, 1-3x daily",
            "Gargle: strong tea (cooled) for sore throat",
            "Cough syrup (folk): tea + honey + lemon",
        ],
        "safety_notes": [
            "Culinary use very safe",
            "Concentrated thyme essential oil is irritating — never undiluted",
        ],
        "growing": "Hardy perennial zones 5-9. Full sun, dry, well-drained soil. Drought-tolerant. Easy from cuttings.",
        "summary": "Thyme has mixed evidence for cough/bronchitis support. Thymol is genuinely antimicrobial in vitro. Don't substitute for medical care in serious infections.",
        "svg_diagram": THYME_SVG,
        "domains": ["medicine", "nutrition", "agriculture", "biology"],
        "axes": ["physical_substance", "metabolism", "authority_trust"],
    },
    {
        "id": "herb_lemon_balm",
        "name": "Lemon balm",
        "scientific_name": "Melissa officinalis",
        "common_names": ["balm", "melissa", "lemon mint"],
        "parts_used": ["leaves"],
        "traditional_uses": ["Mild anxiety", "Mild sleep difficulties", "Cold sores (topical)"],
        "evidence_verdicts": [
            {"claim": "Lemon balm reduces mild anxiety", "verdict": "MIXED", "note": "Small studies (300-600 mg extract) show modest calming effects."},
            {"claim": "Topical lemon balm cream speeds cold sore (HSV-1) healing", "verdict": "MIXED", "note": "A few RCTs of 1% extract cream show reduced healing time when applied early."},
        ],
        "preparations": [
            "Tea: 1-2 tsp dried leaf steeped 10 min, 1-3x daily",
            "Extract capsules: 300-600 mg for anxiety/sleep",
            "Topical: 1% extract cream for cold sores, applied 2-4x daily at first tingling",
        ],
        "safety_notes": [
            "Well-tolerated; main caution is excessive sedation with sleep medications",
            "Possible interaction with thyroid medications (theoretical)",
        ],
        "growing": "Vigorous mint-family perennial zones 4-9. Part shade, moist soil. Self-seeds.",
        "summary": "Lemon balm is a gentle, well-tolerated calming herb with mild evidence for anxiety and sleep. Topical cream for cold sores has the best support.",
        "svg_diagram": LEMON_BALM_SVG,
        "domains": ["medicine", "agriculture", "biology"],
        "axes": ["physical_substance", "metabolism", "authority_trust"],
    },
]


def main():
    out_dir = os.path.join(REPO, "data", "herbs")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "monographs.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for m in HERB_MONOGRAPHS:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    print(f"wrote {len(HERB_MONOGRAPHS)} herb monographs to {out_path}")


if __name__ == "__main__":
    main()
