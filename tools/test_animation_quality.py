"""Test premium animation on a single Pooh frame to verify the path to Hanna-Barbera quality.

The pooh_02_treetop_bee frame goes through 4 different motion prompts via 3 different models:
  - veo3.1_fast at 8 sec (premium character motion, ~320 credits)
  - gen4.5 at 8 sec (Runway's newer high-quality, ~120 credits)
  - gen4_turbo with AGGRESSIVE prompt (vs. the timid version we shipped)
  - kling2.5_turbo_pro at 8 sec (Kling is known for character motion)

This is ~600-700 credits of testing to pick the right model + prompt style
before re-rendering the full Pooh pilot.

Output: D:/library_files/_motion_tests/quality_test/<test_name>.mp4
"""
from __future__ import annotations
from dotenv import load_dotenv
from pathlib import Path
load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import os, urllib.request, urllib.error, json, time, base64
import io
from PIL import Image

KEY = os.environ["RUNWAY_API_KEY"]
SOURCE = Path("D:/library_files/_hero_frames/pooh_02_treetop_bee.png")
OUT = Path("D:/library_files/_motion_tests/quality_test")
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


def encode_image() -> str:
    """Resize + JPEG-encode the source for Runway's data-URI cap."""
    raw = SOURCE.read_bytes()
    img = Image.open(io.BytesIO(raw)).convert("RGB")
    w, h = img.size
    if max(w, h) > 1920:
        scale = 1920 / max(w, h)
        img = img.resize((int(w*scale), int(h*scale)), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=88, optimize=True)
    return f"data:image/jpeg;base64,{base64.b64encode(buf.getvalue()).decode()}"


TESTS = [
    {
        "name": "test1_gen4turbo_aggressive",
        "model": "gen4_turbo",
        "duration": 10,
        "ratio": "1280:720",
        "prompt": (
            "The teddy bear sitting on the oak branch turns his head slowly to look at the bee. "
            "He blinks twice. His paws shift on the branch. The bee flies in a small circle around his nose, "
            "wings beating visibly. Oak leaves around them rustle in the wind. The bear's fur ruffles slightly. "
            "A second bee enters the frame from the right and joins the first."
        ),
    },
    {
        "name": "test2_gen4_5_aggressive",
        "model": "gen4.5",
        "duration": 10,
        "ratio": "1280:720",
        "prompt": (
            "The teddy bear sitting on the oak branch turns his head slowly to look at the bee. "
            "He blinks twice. His paws shift on the branch. The bee flies in a small circle around his nose, "
            "wings beating visibly. Oak leaves around them rustle in the wind. The bear's fur ruffles slightly. "
            "A second bee enters the frame from the right and joins the first."
        ),
    },
    {
        "name": "test3_veo3fast_aggressive",
        "model": "veo3.1_fast",
        "duration": 8,
        "ratio": "1280:720",
        "prompt": (
            "Hanna-Barbera style limited animation. The honey-brown teddy bear on the oak branch "
            "looks at the bumblebee with comic concern, tilts his head, blinks slowly. The bee buzzes "
            "around his nose in distinct loops. Oak leaves sway in the breeze. The bear waves a paw gently "
            "to shoo the bee, expression playful. Vintage 1920s English picture-book aesthetic preserved."
        ),
    },
    {
        "name": "test4_kling25_aggressive",
        "model": "kling2.5_turbo_pro",
        "duration": 10,
        "ratio": "1280:720",
        "prompt": (
            "Limited cel animation. The teddy bear on the oak branch slowly turns his head to look at the bee. "
            "He blinks twice. His arm rises slowly and gestures gently. The bumblebee flies in figure-eight "
            "patterns around his nose. Wings beat visibly. Leaves move in the wind. Pen-and-ink watercolor style preserved."
        ),
    },
]


def submit_i2v(test, data_uri):
    payload = {
        "promptImage": data_uri,
        "promptText": test["prompt"],
        "model": test["model"],
        "duration": test["duration"],
        "ratio": test["ratio"],
    }
    req = urllib.request.Request(
        f"{API_BASE}/image_to_video",
        data=json.dumps(payload).encode("utf-8"),
        headers=HEADERS_POST, method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def poll(tid, timeout=360):
    url = f"{API_BASE}/tasks/{tid}"
    req = urllib.request.Request(url, headers=HEADERS_GET)
    start = time.time()
    while time.time() - start < timeout:
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                data = json.loads(r.read())
        except urllib.error.HTTPError as e:
            return {"status":"ERROR","error":e.read().decode("utf-8",errors="replace")[:400]}
        s = data.get("status")
        if s in ("SUCCEEDED","FAILED","CANCELLED"):
            return data
        time.sleep(5)
    return {"status":"TIMEOUT"}


def credits():
    req = urllib.request.Request(f"{API_BASE}/organization", headers=HEADERS_GET)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read()).get("creditBalance")


def main():
    print(f"Starting balance: {credits()} credits")
    data_uri = encode_image()
    print(f"Source: {SOURCE.name} ({len(data_uri)//1024} KB data-uri)")
    print()

    submitted = []
    for t in TESTS:
        out = OUT / f"{t['name']}.mp4"
        if out.exists() and out.stat().st_size > 50_000:
            print(f"  [SKIP] {t['name']} already done")
            continue
        print(f"  [SUBMIT] {t['name']:<40} model={t['model']} dur={t['duration']}s")
        try:
            resp = submit_i2v(t, data_uri)
            tid = resp.get("id")
            print(f"           task_id={tid}")
            submitted.append((t, tid, out))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8",errors="replace")[:300]
            print(f"  [FAIL]   HTTP {e.code}: {body}")
        except Exception as e:
            print(f"  [FAIL]   {type(e).__name__}: {e}")
        time.sleep(1)

    print()
    print("Polling (each ~30-90s)...")
    for t, tid, out in submitted:
        if not tid: continue
        result = poll(tid)
        s = result.get("status")
        if s == "SUCCEEDED":
            url = (result.get("output") or [None])[0]
            if url:
                with urllib.request.urlopen(url, timeout=120) as r:
                    out.write_bytes(r.read())
                kb = out.stat().st_size // 1024
                print(f"  [OK]      {t['name']:<40} {kb} KB")
            else:
                print(f"  [NO-URL]  {t['name']}")
        elif s == "FAILED":
            print(f"  [FAILED]  {t['name']}  {result.get('failure')!r}  code={result.get('failureCode')!r}")
        elif s == "ERROR":
            print(f"  [ERROR]   {t['name']}  {result.get('error')}")
        else:
            print(f"  [TIMEOUT] {t['name']}")
    print()
    print(f"Final balance: {credits()} credits")
    print(f"Output: {OUT}")


if __name__ == "__main__":
    main()
