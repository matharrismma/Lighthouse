"""Test the Runway image-to-video pipeline.

Take an already-rendered hero frame, animate it into a 5-second clip via gen3a_turbo
(cost-efficient: 5 credits/sec * 5 sec = 25 credits).

The animation prompt encodes the 'New' part of Classic/Nostalgic/New — subtle motion
that wasn't possible in the 1950 source era (smoke curling, light shifting, etc.).

Output: D:/library_files/_motion_tests/<name>.mp4
"""
from __future__ import annotations
from dotenv import load_dotenv
from pathlib import Path

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

import os, urllib.request, urllib.error, json, time, base64

KEY = os.environ["RUNWAY_API_KEY"]
OUT = Path("D:/library_files/_motion_tests")
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

# Test set — animate one frame from each series (and one of the strongest of each)
TESTS = [
    {
        "name": "scifi_03_house_aflame_motion",
        "source_image": Path("D:/library_files/_hero_frames/scifi_03_house_aflame.png"),
        "prompt": (
            "Flames flicker and curl upward through the windows. "
            "Thick black smoke rises and drifts. "
            "Distant horizon shimmers with heat. "
            "Subtle camera push-in toward the burning house. "
            "Painterly 1950 pulp magazine illustration aesthetic preserved."
        ),
    },
    {
        "name": "pooh_02_treetop_bee_motion",
        "source_image": Path("D:/library_files/_hero_frames/pooh_02_treetop_bee.png"),
        "prompt": (
            "Oak leaves stir gently in a soft breeze. "
            "The bumblebee hovers in place, wings beating fast. "
            "The small bear blinks slowly and tilts his head. "
            "Subtle parallax — slight camera drift to the right. "
            "Watercolor picture-book aesthetic preserved."
        ),
    },
]


def encode_image_data_uri(path: Path) -> str:
    """Encode a local PNG as a data URI for Runway image-to-video."""
    img_bytes = path.read_bytes()
    b64 = base64.b64encode(img_bytes).decode("ascii")
    return f"data:image/png;base64,{b64}"


def submit_i2v(image_data_uri: str, prompt_text: str, duration: int = 5):
    payload = {
        "promptImage": image_data_uri,
        "promptText": prompt_text,
        "model": "gen3a_turbo",
        "duration": duration,           # 5 or 10 seconds
        "ratio": "1280:768",            # gen3a_turbo supports 1280:768 / 768:1280
    }
    req = urllib.request.Request(
        f"{API_BASE}/image_to_video",
        data=json.dumps(payload).encode("utf-8"),
        headers=HEADERS_POST, method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def poll(task_id: str, timeout_seconds: int = 360):
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
        time.sleep(5)
    return {"status": "TIMEOUT"}


def org_credits():
    req = urllib.request.Request(f"{API_BASE}/organization", headers=HEADERS_GET)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read()).get("creditBalance")


def main():
    print(f"Starting balance: {org_credits()} credits")
    print()

    submitted = []
    for t in TESTS:
        img = t["source_image"]
        if not img.exists():
            print(f"  [SKIP] {t['name']}  missing source: {img}")
            continue
        size_kb = img.stat().st_size // 1024
        print(f"  [SUBMIT] {t['name']}  source={img.name} ({size_kb} KB)")
        try:
            data_uri = encode_image_data_uri(img)
            resp = submit_i2v(data_uri, t["prompt"], duration=5)
            tid = resp.get("id")
            print(f"           task_id={tid}")
            submitted.append((t, tid))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")[:300]
            print(f"  [FAIL]   HTTP {e.code}: {body}")
        except Exception as e:
            print(f"  [FAIL]   {type(e).__name__}: {e}")
        time.sleep(0.5)

    print()
    print("Polling (each 5-sec clip ~30-90s render time)...")
    for t, tid in submitted:
        if not tid: continue
        result = poll(tid, timeout_seconds=360)
        status = result.get("status")
        if status == "SUCCEEDED":
            outputs = result.get("output", [])
            url = outputs[0] if outputs else None
            if url:
                try:
                    with urllib.request.urlopen(url, timeout=120) as r:
                        mp4_bytes = r.read()
                    out_path = OUT / f"{t['name']}.mp4"
                    out_path.write_bytes(mp4_bytes)
                    print(f"  [OK]      {t['name']}  {len(mp4_bytes)//1024} KB  ->  {out_path}")
                except Exception as e:
                    print(f"  [DL-FAIL] {t['name']}  {e}")
            else:
                print(f"  [NO-URL]  {t['name']}")
        elif status == "FAILED":
            print(f"  [FAILED]  {t['name']}  {result.get('failure')!r}  code={result.get('failureCode')!r}")
        elif status == "ERROR":
            print(f"  [ERROR]   {t['name']}  {result.get('error')}")
        else:
            print(f"  [TIMEOUT] {t['name']}  status={status}")

    print()
    print(f"Final balance: {org_credits()} credits")


if __name__ == "__main__":
    main()
