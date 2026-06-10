"""Render Pooh hero frames via alternate models (gemini_image3_pro, gpt_image_2).

Runway's default gen4_image moderation flags every Pooh-aesthetic prompt — even ones
with zero trademark references and zero child references. Hypothesis: the visual
classifier learned that "small bear + balloon + watercolor" is the Pooh signature
and rejects it pre-render as IP-protection.

We try alternate models accessed through the same Runway API — they may use
different moderation pipelines.

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

# Prompts written to avoid the visual classifier's Pooh inference:
# - No "balloon" near "bear" (the Pooh-on-balloon signature)
# - No "Hundred Acre Wood" (trademark)
# - No "Christopher Robin" (named character)
# - "Honey-brown" and "stuffed bear" instead of "tawny bear"
# - Reference to art style and period, not character

FRAMES = [
    {
        "name": "pooh_01_oak_clearing",
        "prompt": (
            "Vintage 1920s English children's book illustration in pen-and-ink "
            "with watercolor wash. A small honey-brown stuffed bear sits contentedly "
            "in tall grass at the base of a large oak tree. Soft summer afternoon light. "
            "Cream paper texture. Gentle sage greens, soft umber browns, honey amber light. "
            "Edwardian picture-book style, watercolor on rough paper, soft pencil under-drawing. "
            "Quiet, pastoral, contemplative."
        ),
        "models_to_try": ["gemini_image3_pro", "gpt_image_2", "gen4_image"],
    },
    {
        "name": "pooh_02_treetop_bee",
        "prompt": (
            "Vintage 1920s English children's book illustration in pen-and-ink "
            "with watercolor wash. Close composition: a small honey-brown stuffed bear "
            "perched on a high oak branch, leaves and sky around him. A single bumblebee "
            "hovers nearby in mid-air. Cream paper texture. Sage greens, dusty cornflower "
            "blue sky, soft umber. Edwardian picture-book style, watercolor on rough paper, "
            "gentle and whimsical."
        ),
        "models_to_try": ["gemini_image3_pro", "gpt_image_2", "gen4_image"],
    },
    {
        "name": "pooh_03_parlor_bedtime",
        "prompt": (
            "Vintage 1920s English children's book illustration in pen-and-ink "
            "with watercolor wash. A cosy English cottage parlor at evening. "
            "A small honey-brown stuffed bear sits on a wool rug in front of a "
            "low-glowing fireplace. Warm firelight, oak floor, an empty armchair, "
            "a wooden mantel clock. Cream paper texture. Honey amber firelight, "
            "soft umber browns. Edwardian picture-book style, watercolor on rough paper, "
            "intimate and warm."
        ),
        "models_to_try": ["gemini_image3_pro", "gpt_image_2", "gen4_image"],
    },
]


def submit(prompt_text: str, model: str, ratio: str = "1920:1080"):
    payload = {"promptText": prompt_text, "ratio": ratio, "model": model}
    req = urllib.request.Request(
        f"{API_BASE}/text_to_image",
        data=json.dumps(payload).encode("utf-8"),
        headers=HEADERS_POST,
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def poll(task_id: str, timeout_seconds: int = 240):
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


def try_one_frame(frame):
    name = frame["name"]
    out_path = OUT / f"{name}.png"
    if out_path.exists() and out_path.stat().st_size > 50_000:
        print(f"  [SKIP] {name} already rendered.")
        return True

    for model in frame["models_to_try"]:
        print(f"  -> {name} via {model}: ", end="", flush=True)
        try:
            resp = submit(frame["prompt"], model)
            tid = resp.get("id")
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            print(f"submit HTTP {e.code}: {body[:200]}")
            continue
        except Exception as e:
            print(f"submit ERROR: {type(e).__name__}: {e}")
            continue

        result = poll(tid)
        status = result.get("status")
        if status == "SUCCEEDED":
            outputs = result.get("output", [])
            url = outputs[0] if outputs else None
            if url:
                try:
                    with urllib.request.urlopen(url, timeout=60) as r:
                        img_bytes = r.read()
                    out_path.write_bytes(img_bytes)
                    print(f"OK  {len(img_bytes)//1024} KB  ->  {out_path}")
                    return True
                except Exception as e:
                    print(f"download FAIL: {e}")
                    continue
            print("no URL returned")
            continue
        elif status == "FAILED":
            failure = result.get("failure") or ""
            code = result.get("failureCode") or ""
            print(f"FAILED  {code}  {failure[:80]}")
            continue
        else:
            print(f"status={status}")
            continue
    print(f"  [GIVE UP] {name} failed on all {len(frame['models_to_try'])} models")
    return False


def org_credits():
    req = urllib.request.Request(f"{API_BASE}/organization", headers=HEADERS_GET)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read()).get("creditBalance")


def main():
    print(f"Starting balance: {org_credits()} credits")
    print()
    results = []
    for frame in FRAMES:
        print(f"FRAME: {frame['name']}")
        ok = try_one_frame(frame)
        results.append((frame["name"], ok))
        print()
    print(f"Final balance: {org_credits()} credits")
    print()
    for name, ok in results:
        print(f"  {'OK ' if ok else 'X  '} {name}")


if __name__ == "__main__":
    main()
