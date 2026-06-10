"""Render the remaining sci-fi hero frames for the 'There Will Come Soft Rains' pilot.

Sci-fi style is LOCKED — the recipe that lands is:
'1950s pulp magazine cover painted in gouache + halftone screentone + inked outlines'

The Soft Rains pilot has 22 scenes; 3 hero frames already exist:
  scifi_01_automated_house_dawn (scene ~1)
  scifi_02_robotic_mice          (scene ~6)
  scifi_03_house_aflame          (scenes ~18-20)

This script renders 9 more frames covering the remaining beats so the full pilot
has visual coverage. Total cost: ~9 frames * 8 credits = ~72 credits.

Output: D:/library_files/_hero_frames/<name>.png
"""
from __future__ import annotations
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import os, urllib.request, urllib.error, json, time

KEY = os.environ["RUNWAY_API_KEY"]
OUT = Path("D:/library_files/_hero_frames")
OUT.mkdir(parents=True, exist_ok=True)

API_BASE = "https://api.dev.runwayml.com/v1"
HEADERS_POST = {
    "Authorization": f"Bearer {KEY}",
    "X-Runway-Version": "2024-11-06",
    "Content-Type": "application/json",
}
HEADERS_GET = {
    "Authorization": f"Bearer {KEY}",
    "X-Runway-Version": "2024-11-06",
}

# Locked sci-fi style suffix — the recipe that lands (per Visual Style Bible)
SCIFI_STYLE = (
    "1950s pulp science-fiction magazine cover painted in gouache, "
    "halftone screentone pattern visible, inked outlines, saturated cyan "
    "and cadmium red palette, slight color-registration offset, "
    "vintage pulp paper texture, strong horizontal composition. "
    "Avoid photorealism, 3D render, modern technology, glossy plastic, "
    "cinematic photography, neon, anime, text artifacts."
)

# Scene mapping — covers the remaining beats of Soft Rains pilot
FRAMES = [
    {
        "name": "scifi_softrains_04_family_shadows",
        "scene": (
            "Side of a streamlined 1950s atomic-age suburban house, painted as a 1950 pulp "
            "science-fiction magazine illustration. On the white exterior wall are five "
            "silhouetted human shadows burned into the paint — a father raising a hand to "
            "throw a ball, a mother bending in mid-motion, a boy mid-jump, a girl reaching up, "
            "a small dog stretched mid-leap. The shadows are crisp, white outlines on charred "
            "wall. Foreground grass is dead and grey. Saturated cyan sky. Halftone screentone."
        ),
    },
    {
        "name": "scifi_softrains_05_dog_at_door",
        "scene": (
            "A thin, scarred dog stands at the front door of a 1950s atomic-age suburban house, "
            "painted as a 1950 pulp science-fiction magazine illustration. The dog is gaunt, "
            "fur falling out in patches, head lowered. The door is closed; warm interior light "
            "glows through a small porthole window. Dusk light. Saturated cyan-and-amber sky. "
            "Halftone screentone visible. Inked outlines. Pathos in composition."
        ),
    },
    {
        "name": "scifi_softrains_07_breakfast_table",
        "scene": (
            "Interior of an automated 1950s atomic-age suburban kitchen, painted as a 1950 pulp "
            "science-fiction magazine illustration. A formica breakfast table is set with toast, "
            "bacon, and a glass of orange juice — but every chair is empty. A robotic mechanical "
            "arm extends from the wall holding a coffee pot, paused mid-pour. Warm morning sun "
            "through chrome window blinds. Saturated cyan and warm amber. Halftone screentone. "
            "Eerie domestic emptiness."
        ),
    },
    {
        "name": "scifi_softrains_08_backyard_sprinkler",
        "scene": (
            "Suburban backyard of a 1950s atomic-age home, painted as a 1950 pulp science-fiction "
            "magazine illustration. An automated lawn sprinkler arcs water gently over yellowed "
            "dead grass. A child's tricycle lies on its side in the foreground, faded and rusted. "
            "A wooden swing-set in the back, swings hanging still. Cyan sky with cumulus clouds. "
            "Halftone screentone. Inked outlines. Quiet apocalyptic atmosphere."
        ),
    },
    {
        "name": "scifi_softrains_09_nursery_animals",
        "scene": (
            "A child's nursery interior, painted as a 1950 pulp science-fiction magazine "
            "illustration. The walls are murals that have come alive: a yellow giraffe walks "
            "across one wall, blue elephants graze along another, parrots flock through painted "
            "trees. The nursery is otherwise empty — a small bed, a rocking horse, building "
            "blocks scattered on the rug. Warm afternoon light. Saturated colors. Halftone "
            "screentone. Inked outlines. Sweet and uncanny."
        ),
    },
    {
        "name": "scifi_softrains_12_teasdale_poem_card",
        "scene": (
            "A 1950s atomic-age suburban living room at twilight, painted as a 1950 pulp "
            "science-fiction magazine illustration. A vintage hi-fi cabinet plays itself, "
            "warm light spilling from its speaker grilles. An empty leather armchair faces the "
            "hi-fi. A book of poetry lies open on the side table — pages curled. Warm amber "
            "lamp-light against deep cyan shadows. Halftone screentone. Inked outlines. "
            "Solitude and elegy."
        ),
    },
    {
        "name": "scifi_softrains_13_storm_winds",
        "scene": (
            "The 1950s atomic-age suburban house at the start of a violent storm, painted as a "
            "1950 pulp science-fiction magazine illustration. Dramatic dark cyan-black storm "
            "clouds boil overhead. Wind bends grass and shakes shutters. A single trash can "
            "rolls across the foreground. Cadmium-orange lightning flashes in the distance. "
            "Halftone screentone visible. Inked outlines. Building dread."
        ),
    },
    {
        "name": "scifi_softrains_14_falling_oak",
        "scene": (
            "A massive oak tree falls toward a 1950s atomic-age suburban house in a violent storm, "
            "painted as a 1950 pulp science-fiction magazine illustration. The tree is mid-fall, "
            "branches splayed, mass aimed at the house's left wing. Rain sheets across the scene. "
            "Saturated cyan-black storm sky. Cadmium lightning. Halftone screentone. Inked "
            "outlines. Dramatic catastrophic energy."
        ),
    },
    {
        "name": "scifi_softrains_21_dawn_ashes",
        "scene": (
            "Pre-dawn light over a 1950s atomic-age suburban neighborhood, painted as a 1950 pulp "
            "science-fiction magazine illustration. Where the house stood, only smoldering ashes "
            "remain. A single brick chimney still stands, soot-stained. Thin smoke rises straight "
            "up into a soft pinkish-cyan dawn sky. Charred tree silhouettes around. Halftone "
            "screentone. Inked outlines. Aftermath. Quiet. Sara Teasdale poem made visible."
        ),
    },
]


def submit(prompt_text: str):
    payload = {"promptText": prompt_text, "ratio": "1920:1080", "model": "gen4_image"}
    req = urllib.request.Request(
        f"{API_BASE}/text_to_image",
        data=json.dumps(payload).encode("utf-8"),
        headers=HEADERS_POST, method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def poll(task_id: str, timeout_seconds: int = 300):
    url = f"{API_BASE}/tasks/{task_id}"
    req = urllib.request.Request(url, headers=HEADERS_GET)
    start = time.time()
    while time.time() - start < timeout_seconds:
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            return {"status": "ERROR", "error": e.read().decode("utf-8", errors="replace")[:400]}
        status = data.get("status")
        if status in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return data
        time.sleep(4)
    return {"status": "TIMEOUT"}


def org_credits():
    req = urllib.request.Request(f"{API_BASE}/organization", headers=HEADERS_GET)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read()).get("creditBalance")


def main():
    print(f"Starting balance: {org_credits()} credits")
    print()

    # Length sanity check
    print("Prompt length check (must be <=1000 chars):")
    for f in FRAMES:
        full = f["scene"] + " " + SCIFI_STYLE
        ln = len(full)
        print(f"  [{ 'OK ' if ln<=1000 else 'OVER'}] {f['name']:<45} {ln} chars")
    print()

    # Skip already-rendered
    to_render = []
    for f in FRAMES:
        target = OUT / f"{f['name']}.png"
        if target.exists() and target.stat().st_size > 50_000:
            print(f"  [SKIP] {f['name']}")
        else:
            to_render.append(f)
    if not to_render:
        print("All frames already exist.")
        return
    print()
    print(f"Submitting {len(to_render)} frames (gen4_image, 1920:1080)...")

    submitted = []
    for f in to_render:
        prompt = f["scene"] + " " + SCIFI_STYLE
        try:
            resp = submit(prompt)
            tid = resp.get("id")
            print(f"  [SUBMITTED] {f['name']:<45} task={tid}")
            submitted.append((f, tid))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:200]
            print(f"  [FAIL]      {f['name']:<45} HTTP {e.code}: {body}")
        except Exception as e:
            print(f"  [FAIL]      {f['name']:<45} {type(e).__name__}: {e}")
        time.sleep(0.5)

    print()
    print("Polling...")
    for f, tid in submitted:
        if not tid: continue
        result = poll(tid)
        status = result.get("status")
        if status == "SUCCEEDED":
            outputs = result.get("output", [])
            url = outputs[0] if outputs else None
            if url:
                try:
                    with urllib.request.urlopen(url, timeout=60) as r:
                        img_bytes = r.read()
                    out_path = OUT / f"{f['name']}.png"
                    out_path.write_bytes(img_bytes)
                    print(f"  [OK]      {f['name']:<45} {len(img_bytes)//1024} KB")
                except Exception as e:
                    print(f"  [DL-FAIL] {f['name']:<45} {e}")
            else:
                print(f"  [NO-URL]  {f['name']:<45}")
        elif status == "FAILED":
            print(f"  [FAILED]  {f['name']:<45} {result.get('failure')!r}")
        elif status == "ERROR":
            print(f"  [ERROR]   {f['name']:<45} {result.get('error')}")
        else:
            print(f"  [TIMEOUT] {f['name']:<45}")

    print()
    print(f"Final balance: {org_credits()} credits")
    print(f"Frames at: {OUT}")


if __name__ == "__main__":
    main()
