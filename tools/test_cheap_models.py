"""Test cheap models with character-action prompts vs veo3.1_fast.

We already have veo3.1_fast (40 cr/sec) result for pooh_02_treetop_bee. Now test:
  - kling2.5_turbo_pro (~8 cr/sec, 5x cheaper) — different API schema, no `ratio`
  - seedance2 (~? cr/sec, ByteDance) — different API schema
  - gen4_turbo with maximally aggressive prompt

Goal: find a model where character motion is comparable but cost is dramatically lower.
"""
from __future__ import annotations
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import os, urllib.request, urllib.error, json, time, base64, io
from PIL import Image

KEY = os.environ["RUNWAY_API_KEY"]
SOURCE = Path("D:/library_files/_hero_frames/pooh_02_treetop_bee.png")
OUT = Path("D:/library_files/_motion_tests/cheap_models")
OUT.mkdir(parents=True, exist_ok=True)

API_BASE = "https://api.dev.runwayml.com/v1"
H_POST = {"Authorization": f"Bearer {KEY}", "X-Runway-Version": "2024-11-06",
          "Content-Type": "application/json"}
H_GET = {"Authorization": f"Bearer {KEY}", "X-Runway-Version": "2024-11-06"}

PROMPT = (
    "Hanna-Barbera style limited animation. The honey-brown teddy bear on the oak branch "
    "turns his head slowly to look at the bee, blinks twice, his paws shift on the branch. "
    "The bumblebee flies in figure-eight patterns around his nose, wings beating visibly. "
    "Oak leaves rustle in the wind. The bear's mouth opens slightly. Vintage 1920s English "
    "picture-book aesthetic preserved."
)


def encode_image() -> str:
    raw = SOURCE.read_bytes()
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    if max(img.size) > 1920:
        scale = 1920 / max(img.size)
        img = img.resize((int(img.size[0]*scale), int(img.size[1]*scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"


def submit_payload(payload: dict) -> dict:
    req = urllib.request.Request(f"{API_BASE}/image_to_video",
                                  data=json.dumps(payload).encode("utf-8"),
                                  headers=H_POST, method="POST")
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def poll(tid: str, timeout: int = 360) -> dict:
    req = urllib.request.Request(f"{API_BASE}/tasks/{tid}", headers=H_GET)
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            return {"status": "ERROR", "error": e.read().decode("utf-8", errors="replace")[:400]}
        if data.get("status") in ("SUCCEEDED", "FAILED", "CANCELLED"):
            return data
        time.sleep(5)
    return {"status": "TIMEOUT"}


def try_test(name: str, payload_variants: list[dict]):
    """Try several payload shapes for the same model until one is accepted."""
    out = OUT / f"{name}.mp4"
    if out.exists() and out.stat().st_size > 50_000:
        print(f"  [SKIP] {name} already done")
        return
    for i, payload in enumerate(payload_variants):
        try:
            resp = submit_payload(payload)
            tid = resp.get("id")
            print(f"  [SUBMIT-OK] {name} variant {i+1}/{len(payload_variants)}  task={tid}")
            result = poll(tid)
            s = result.get("status")
            if s == "SUCCEEDED":
                url = (result.get("output") or [None])[0]
                if url:
                    with urllib.request.urlopen(url, timeout=120) as r:
                        out.write_bytes(r.read())
                    print(f"  [OK] {name}: {out.stat().st_size//1024} KB")
                    return
                print(f"  [NO-URL] {name}")
                return
            elif s == "FAILED":
                print(f"  [FAILED] {name}: {result.get('failure')!r} code={result.get('failureCode')!r}")
                return
            elif s == "ERROR":
                print(f"  [ERROR] {name}: {result.get('error')}")
                return
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:400]
            print(f"  [REJECT v{i+1}] {name}: HTTP {e.code}: {body[:200]}")
            continue
        except Exception as e:
            print(f"  [ERR] {name}: {type(e).__name__}: {e}")
            return
    print(f"  [GIVE UP] {name} after {len(payload_variants)} variants")


def credits():
    req = urllib.request.Request(f"{API_BASE}/organization", headers=H_GET)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read()).get("creditBalance")


def main():
    print(f"Starting balance: {credits()}")
    img = encode_image()
    print(f"Source: {SOURCE.name}")
    print()

    # 1. kling — try with and without ratio
    try_test("kling25_aggressive", [
        {"model": "kling2.5_turbo_pro", "promptImage": img, "promptText": PROMPT, "duration": 5},
        {"model": "kling2.5_turbo_pro", "promptImage": img, "promptText": PROMPT, "duration": 10},
        {"model": "kling2.5_turbo_pro", "promptImage": img, "promptText": PROMPT,
         "duration": 5, "aspectRatio": "16:9"},
    ])

    # 2. seedance2
    try_test("seedance2_aggressive", [
        {"model": "seedance2", "promptImage": img, "promptText": PROMPT, "duration": 5},
        {"model": "seedance2", "promptImage": img, "promptText": PROMPT, "duration": 5, "ratio": "1280:720"},
        {"model": "seedance2", "promptImage": img, "promptText": PROMPT, "duration": 5, "aspectRatio": "16:9"},
    ])

    # 3. gen4_turbo with MUCH more aggressive prompt (Hanna-Barbera style explicitly)
    try_test("gen4turbo_max_aggressive", [
        {"model": "gen4_turbo", "promptImage": img, "promptText":
            "Hanna-Barbera 1970s Saturday morning cartoon style. The teddy bear's HEAD TURNS LEFT THEN RIGHT. "
            "His eyes BLINK CLOSED AND OPEN. His MOUTH OPENS WIDE then closes. His RIGHT PAW LIFTS and waves at the bee. "
            "The BEE FLIES IN A LARGE CIRCLE around the bear's head. The OAK LEAVES SHAKE in the wind. "
            "Limited animation cel style. Watercolor aesthetic preserved.",
         "duration": 10, "ratio": "1280:720"},
    ])

    print()
    print(f"Final balance: {credits()}")


if __name__ == "__main__":
    main()
