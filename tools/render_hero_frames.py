"""Render the 6 pilot hero frames via Runway gen4_image (high quality, not turbo).

Per Visual Style Bible (content/style/visual_style_bible.md): three frames per series.
Pooh frames use Shepard-1926 prompt; Sci-Fi frames use 1950-magazine-illustration prompt.

Output: D:/library_files/_hero_frames/<name>.png
"""
from __future__ import annotations
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import os
import urllib.request
import urllib.error
import json
import time

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

POOH_STYLE = (
    "E.H. Shepard 1926 pen-and-ink line drawing with light watercolor wash, "
    "English picture-book illustration, gentle tawny browns and sage greens "
    "on cream paper, visible watercolor paper texture, soft pencil under-lines. "
    "Avoid Disney, photorealism, 3D, anime, plush toys, neon, glossy."
)

SCIFI_STYLE = (
    "1950s pulp science-fiction magazine cover painted in gouache, "
    "halftone screentone pattern visible, inked outlines, saturated cyan "
    "and cadmium red palette, slight color-registration offset, "
    "vintage pulp paper texture, strong horizontal composition. "
    "Avoid photorealism, 3D render, modern technology, glossy plastic, "
    "cinematic photography, neon, anime, text artifacts."
)

FRAMES = [
    {
        "name": "pooh_01_oak_clearing",
        "scene": (
            "Hundred Acre Wood clearing in summer. A small stout tawny bear sits on the grass "
            "at the base of a tall oak tree, looking up thoughtfully. Sun-shafts through leaves. "
            "Faint bees in the canopy. Gentle pen-and-ink with watercolor wash."
        ),
        "style": POOH_STYLE,
    },
    {
        "name": "pooh_02_balloon_bee",
        "scene": (
            "A small tawny bear floats at the top of an oak tree holding a pale blue balloon string. "
            "A single bumblebee hovers near the bear's nose. Green oak leaves around. "
            "Comic-gentle picture-book scene, pen-and-ink with watercolor wash."
        ),
        "style": POOH_STYLE,
    },
    {
        "name": "pooh_03_parlor_bedtime",
        "scene": (
            "Cosy English cottage parlor at evening, 1926. A young boy of about five sits on the rug "
            "by a fireplace, holding a small tawny teddy bear in his lap. An old armchair is just visible. "
            "Warm firelight, oak floor, mantel clock. Picture-book pen-and-ink with watercolor wash."
        ),
        "style": POOH_STYLE,
    },
    {
        "name": "scifi_01_automated_house_dawn",
        "scene": (
            "A streamlined mid-century atomic-age suburban house at dawn, painted as a 1950 pulp "
            "science-fiction magazine cover. The house glows softly with interior light. Surrounding "
            "lawn is empty and grey. Charred tree silhouettes in the background. Saturated cyan sky "
            "with a band of cadmium-orange at the horizon. Halftone screentone visible across the sky. "
            "Inked black outlines. Vintage paper grain. Pulp magazine illustration style."
        ),
        "style": SCIFI_STYLE,
    },
    {
        "name": "scifi_02_robotic_mice",
        "scene": (
            "Five small chrome wind-up mechanical mice in a row on a wood parlor floor, painted as a "
            "1950 pulp science-fiction magazine illustration. Each mouse has riveted metal panels, "
            "antenna whiskers, and brush feet. Long warm-amber sun-shafts cross the floor from a window "
            "above frame. Halftone screentone pattern visible. Inked black outlines. Saturated cyan "
            "wallpaper at edges. Pulp magazine cover style, gouache on board."
        ),
        "style": SCIFI_STYLE,
    },
    {
        "name": "scifi_03_house_aflame",
        "scene": (
            "A 1950s-future atomic-age streamlined suburban house engulfed in flames at night, painted "
            "as a 1950 pulp science-fiction magazine cover. Orange-red flames erupt through every window. "
            "Deep cyan-black sky. Empty street. Charred tree silhouettes. Halftone screentone pattern. "
            "Inked black outlines. Saturated pulp colors. Apocalyptic but beautiful."
        ),
        "style": SCIFI_STYLE,
    },
]


def char_count_check():
    for f in FRAMES:
        full = f["scene"] + " " + f["style"]
        ln = len(full)
        flag = "OK " if ln <= 1000 else "OVER"
        print(f"  [{flag}] {f['name']:<30} {ln} chars")


def filter_existing(frames):
    """Skip frames whose output PNG already exists."""
    out = []
    skipped = []
    for f in frames:
        target = OUT / f"{f['name']}.png"
        if target.exists() and target.stat().st_size > 50_000:
            skipped.append(f['name'])
        else:
            out.append(f)
    if skipped:
        print(f"  Skipping (already rendered): {', '.join(skipped)}")
    return out


def submit(prompt_text: str, ratio: str = "1920:1080", model: str = "gen4_image"):
    payload = {
        "promptText": prompt_text,
        "ratio": ratio,
        "model": model,
    }
    req = urllib.request.Request(
        f"{API_BASE}/text_to_image",
        data=json.dumps(payload).encode("utf-8"),
        headers=HEADERS_POST,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def submit_with_model(frame, model):
    prompt = frame["scene"] + " " + frame["style"]
    return submit(prompt, ratio="1920:1080", model=model)


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
    print("Prompt length check:")
    char_count_check()
    print()
    frames_to_render = filter_existing(FRAMES)
    if not frames_to_render:
        print("All frames already exist; nothing to render.")
        return
    print()
    print(f"Submitting {len(frames_to_render)} hero frame jobs (gen4_image, 1920:1080)...")
    print()

    submitted = []
    for f in frames_to_render:
        prompt = f["scene"] + " " + f["style"]
        try:
            resp = submit(prompt, ratio="1920:1080", model="gen4_image")
            tid = resp.get("id")
            print(f"  [SUBMITTED] {f['name']:<32}  task_id={tid}")
            submitted.append((f, tid))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            print(f"  [FAIL] {f['name']:<32}  HTTP {e.code}: {body}")
        except Exception as e:
            print(f"  [FAIL] {f['name']:<32}  {type(e).__name__}: {e}")
        time.sleep(0.5)

    print()
    print(f"Polling for completion (each ~30-90s)...")
    for f, tid in submitted:
        if not tid:
            continue
        result = poll(tid, timeout_seconds=300)
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
                    print(f"  [OK]      {f['name']:<32}  {len(img_bytes)//1024} KB  ->  {out_path}")
                except Exception as e:
                    print(f"  [DL-FAIL] {f['name']:<32}  {e}")
            else:
                print(f"  [NO-URL]  {f['name']:<32}  output={result.get('output')}")
        elif status == "FAILED":
            print(f"  [FAILED]  {f['name']:<32}  failure={result.get('failure')!r}  failureCode={result.get('failureCode')!r}")
        elif status == "ERROR":
            print(f"  [ERROR]   {f['name']:<32}  {result.get('error')}")
        else:
            print(f"  [TIMEOUT] {f['name']:<32}  status={status}")

    print()
    print(f"Final balance: {org_credits()} credits")
    print(f"All frames saved to: {OUT}")


if __name__ == "__main__":
    main()
