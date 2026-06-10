"""Append science_simple_machines unit with inline SVG diagrams for the six classical simple machines."""
import json
import os

# SVG conventions for the engine's curriculum:
#   - viewBox-based (responsive)
#   - stroke="currentColor" so it inherits the page text color (works on dark + light themes)
#   - simple line art, no shading
#   - small enough to render fast and travel over LoRa eventually
#   - self-contained (no external resources)

DIAGRAMS = {
    "lever": '<svg viewBox="0 0 220 120" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><line x1="20" y1="55" x2="200" y2="65"/><polygon points="100,55 110,75 90,75" fill="currentColor"/><rect x="15" y="35" width="18" height="20" fill="currentColor" opacity="0.35"/><circle cx="195" cy="50" r="6" fill="currentColor" opacity="0.35"/><line x1="195" y1="50" x2="195" y2="35" stroke-width="1.5"/><text x="24" y="32" font-size="11" fill="currentColor" stroke="none">load</text><text x="180" y="32" font-size="11" fill="currentColor" stroke="none">effort</text><text x="100" y="100" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">fulcrum</text></svg>',
    "wheel_axle": '<svg viewBox="0 0 220 120" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><circle cx="110" cy="60" r="45"/><circle cx="110" cy="60" r="12"/><line x1="110" y1="15" x2="110" y2="35"/><line x1="110" y1="85" x2="110" y2="105"/><line x1="65" y1="60" x2="98" y2="60"/><line x1="122" y1="60" x2="155" y2="60"/><text x="110" y="20" text-anchor="middle" font-size="10" fill="currentColor" stroke="none">wheel</text><text x="155" y="65" font-size="10" fill="currentColor" stroke="none">axle</text></svg>',
    "pulley": '<svg viewBox="0 0 220 140" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><circle cx="110" cy="40" r="22"/><circle cx="110" cy="40" r="4" fill="currentColor"/><line x1="90" y1="42" x2="90" y2="115"/><line x1="130" y1="42" x2="130" y2="115"/><rect x="78" y="115" width="24" height="14" fill="currentColor" opacity="0.35"/><line x1="130" y1="115" x2="135" y2="125"/><line x1="135" y1="125" x2="145" y2="120"/><polygon points="145,118 152,123 142,128" fill="currentColor"/><text x="110" y="15" text-anchor="middle" font-size="10" fill="currentColor" stroke="none">pulley</text><text x="68" y="135" font-size="10" fill="currentColor" stroke="none">load</text><text x="148" y="115" font-size="10" fill="currentColor" stroke="none">pull</text></svg>',
    "inclined_plane": '<svg viewBox="0 0 220 120" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><polygon points="20,100 200,100 200,30"/><rect x="155" y="50" width="22" height="22" fill="currentColor" opacity="0.35" transform="rotate(-21.8 166 61)"/><line x1="165" y1="50" x2="180" y2="40" stroke-width="1.5"/><polygon points="180,40 184,38 184,46" fill="currentColor"/><text x="100" y="115" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">ramp (inclined plane)</text><text x="185" y="25" font-size="10" fill="currentColor" stroke="none">push up</text></svg>',
    "wedge": '<svg viewBox="0 0 220 120" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><polygon points="110,15 90,95 130,95"/><line x1="60" y1="100" x2="160" y2="100"/><line x1="60" y1="105" x2="160" y2="105"/><line x1="110" y1="15" x2="110" y2="0" stroke-width="1.5"/><polygon points="108,5 112,5 110,-2" fill="currentColor"/><text x="110" y="115" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">wedge (axe head)</text><text x="155" y="25" font-size="10" fill="currentColor" stroke="none">strike →</text></svg>',
    "screw": '<svg viewBox="0 0 220 140" xmlns="http://www.w3.org/2000/svg" stroke="currentColor" fill="none" stroke-width="2"><rect x="90" y="15" width="40" height="12"/><line x1="98" y1="21" x2="122" y2="21" stroke-width="1"/><polygon points="100,30 120,30 110,120" stroke-width="2"/><line x1="102" y1="40" x2="118" y2="46" stroke-width="1.5"/><line x1="103" y1="55" x2="117" y2="61" stroke-width="1.5"/><line x1="104" y1="70" x2="116" y2="76" stroke-width="1.5"/><line x1="105" y1="85" x2="115" y2="91" stroke-width="1.5"/><line x1="107" y1="100" x2="113" y2="106" stroke-width="1.5"/><text x="110" y="135" text-anchor="middle" font-size="11" fill="currentColor" stroke="none">screw (inclined plane wrapped)</text></svg>',
}

unit = {
    "id": "science_simple_machines",
    "title": "Simple machines — six ways to make work easier",
    "unit_seq": 7,
    "track": "science_physics",
    "rule": "A SIMPLE MACHINE is a tool that makes work easier by changing how much force you need or the direction you apply it. There are SIX classical simple machines: (1) LEVER — a bar that pivots on a fulcrum. (2) WHEEL AND AXLE — a wheel attached to a rod. (3) PULLEY — a wheel with a rope that changes the direction of pull. (4) INCLINED PLANE — a ramp. (5) WEDGE — a thin slanted piece that splits things. (6) SCREW — an inclined plane wrapped around a rod. Every machine, no matter how complex, is built from these six. A bicycle uses wheel-and-axle + lever + screw. A car uses all six.",
    "examples": [
        "Lever: seesaw, crowbar, scissors, your forearm",
        "Wheel and axle: bicycle, car, doorknob, screwdriver",
        "Pulley: flagpole, blinds, crane, well bucket",
        "Inclined plane: ramp, slide, mountain road, wheelchair access",
        "Wedge: knife, axe, doorstop, your front teeth",
        "Screw: jar lid, drill bit, light bulb, lightbulb socket",
        "Simple machines trade FORCE for DISTANCE. A ramp lets you push with less force, but you push for longer.",
        "Work = Force x Distance. Simple machines don't reduce work — they let you do it with less force at a time.",
        "The lever has three classes based on where the fulcrum sits relative to load and effort.",
        "A pulley with one wheel changes direction (pull down → load goes up). A pulley with multiple wheels reduces force.",
    ],
    "manipulative": "A small physics kit, OR everyday objects: a ruler + small block (lever), a roll of tape on a pencil (wheel and axle), a string over a pencil with a bag of marbles hanging (improvised pulley), a piece of wood at an angle (ramp), a knife or doorstop (wedge), a jar lid (screw). Trying each one with your hands — feel the difference between lifting a bag straight up vs sliding it up a ramp — is what makes the lesson stick.",
    "svg_diagrams": [
        {"label": "Lever", "svg": DIAGRAMS["lever"]},
        {"label": "Wheel and axle", "svg": DIAGRAMS["wheel_axle"]},
        {"label": "Pulley", "svg": DIAGRAMS["pulley"]},
        {"label": "Inclined plane", "svg": DIAGRAMS["inclined_plane"]},
        {"label": "Wedge", "svg": DIAGRAMS["wedge"]},
        {"label": "Screw", "svg": DIAGRAMS["screw"]},
    ],
    "modes": [
        {
            "id": "coach_models",
            "label": "Coach demonstrates",
            "instruction": "Engine names each machine, points to the diagram, gives one everyday example, and (if you have the manipulative) shows it working.",
            "script": "This is a lever. (Point to diagram.) See the bar across the fulcrum? Push down on one side and the other side goes up. A seesaw is a lever. Now a ramp — inclined plane. (Point.) It's easier to push a heavy box UP the ramp than to lift it straight up. Less force, longer distance. Same work.",
        },
        {
            "id": "take_turns",
            "label": "Spot the machine",
            "instruction": "Engine names an everyday object; learner says which simple machine (or machines) it uses. Some objects use more than one — name them all.",
            "script": "I say 'bicycle'. What simple machines? (Wheel and axle for the wheels and gears, lever for the handlebars and brakes, screw for the bolts.) I say 'scissors'. (Two levers connected at a fulcrum, with wedge edges.)",
        },
        {
            "id": "i_find",
            "label": "I find",
            "instruction": "Learner walks around the house finding examples of each of the six machines. Stuck → Context (look at what twists, pivots, rolls, ramps, splits), then Echo (engine names one in the room), then Repeat.",
            "script": "Walk around. Find one example of each of the six simple machines.",
        },
    ],
    "check": {
        "prompt": "A ramp lets you push a heavy box up with LESS force than lifting it straight up. Does the ramp reduce the WORK? Why or why not?",
        "answer": "No — the ramp doesn't reduce the work. Work = Force x Distance. The ramp lets you push with LESS force, but you push for a LONGER distance. The total work (force times distance) stays the same. What the ramp gives you is the ability to do hard work without lifting all at once. That's why simple machines are so useful — they don't cheat physics; they change which kind of effort you spend.",
        "teaching_note": "This is the load-bearing insight about simple machines. Children think machines 'reduce' work; physics says they don't. The trade is force-for-distance. The same total energy moves the box; the machine just spreads the effort. Connect to the lever: push the long end down a lot, the short end goes up a little (with more force) — same work, different distribution.",
    },
    "wedges": ["wedge_repeat", "wedge_context", "wedge_echo", "wedge_chunk", "wedge_meaning", "wedge_praise"],
    "prerequisites": ["science_magnets"],
    "next": "science_forces_motion",
    "summary": "The six classical simple machines (lever, wheel-and-axle, pulley, inclined plane, wedge, screw) with inline SVG diagrams for each. Examples grounded in everyday objects. Check teaches the load-bearing 'work = force × distance, machines trade force for distance' insight — the foundation of mechanics.",
    "domains": ["physics", "pedagogy"],
    "axes": ["physical_substance", "conservation_balance", "information_encoding"],
}

repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
path = os.path.join(repo, "data", "science", "units.jsonl")
with open(path, "a", encoding="utf-8") as f:
    f.write(json.dumps(unit, ensure_ascii=False) + "\n")
print("appended:", path)
