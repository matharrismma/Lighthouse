"""Stable Diffusion local thumbnail/cover-art renderer.

Generates show + episode cover art locally, $0 per image. Replaces paid art
APIs for the long tail. Reserved paid resources for marquee only.

Pre-req (one of):
  A) Automatic1111 WebUI: https://github.com/AUTOMATIC1111/stable-diffusion-webui
     Run with --api flag. Default URL: http://127.0.0.1:7860/sdapi/v1/
  B) ComfyUI: https://github.com/comfyanonymous/ComfyUI
     Run with --listen, default http://127.0.0.1:8188/

This scaffold uses the A1111 API (most popular). For ComfyUI swap the call.

Usage:
  python tools/render_art.py --check
  python tools/render_art.py --slug tv_andy_griffith_discovers_america
  python tools/render_art.py --all-shows
  python tools/render_art.py --prompt "a hymn at evening" --out site/art/hymn.png

Output:
  site/art/<slug>.png  (served at /art/<slug>.png on the channel; cards display)
  Future: D:/library_files/<slug>/cover.png

Standing rule: family-safe prompts only. Negative prompt always includes
inappropriate-content filters. Style prompts emphasize warm, period-appropriate,
storybook / illuminated-manuscript / classic-TV-Guide-cover-art aesthetics.
"""
from __future__ import annotations
import argparse
import base64
import json
import re
import sys
from pathlib import Path
from urllib import error as urlerr, request

REPO = Path(__file__).resolve().parent.parent
ART_DIR = REPO / "site" / "art"
ART_DIR.mkdir(parents=True, exist_ok=True)

A1111_URL = "http://127.0.0.1:7860"

# Style prompts per category — keeps the channel's visual identity consistent.
STYLE_BY_CATEGORY = {
    "pd_tv":     "warm 1960s TV Guide cover art, family-friendly illustration, soft saturated colors, period-appropriate",
    "western":   "warm western frontier illustration, golden hour, dust and pines, period-correct, no horses with riders in violent poses",
    "animation": "vintage 1940s theatrical-short style, cel animation cover plate, friendly characters, bright primary colors",
    "vegas":     "1950s Las Vegas lounge poster, art-deco type, warm neon glow, refined not garish",
    "sports":    "vintage sports magazine cover, mid-century printed-poster aesthetic",
    "fishing":   "Norman Rockwell-adjacent outdoor illustration, river and tree-line, gentle morning light",
    "theatre":   "1940s radio-theatre poster, dramatic typography, warm spotlight",
    "radio":     "vintage radio receiver dial, warm brass and walnut wood, evening lamp glow",
    "sermon":    "open Bible on weathered wood, soft afternoon light through stained glass, contemplative",
    "bible_audio":"illuminated manuscript style, gold leaf accents, calligraphic script, sacred geometry",
    "children":  "storybook cover illustration, warm watercolor, friendly animals, soft sun-dappled scene, child-safe",
    "hymn":      "illuminated hymnal page, calligraphic capital, gold and deep red accents, candle glow",
    "magazines": "vintage Popular Mechanics cover, classic American mid-century design",
    "default":   "warm vintage illustration, period-appropriate American craft aesthetic",
}

NEGATIVE_PROMPT = (
    "explicit, nudity, gore, violence, weapons aimed at people, scary faces, "
    "nightmare imagery, distorted anatomy, modern logos, watermarks, text artifacts, "
    "low quality, jpeg artifacts, deformed, extra limbs, signature"
)


def a1111_available() -> bool:
    try:
        req = request.Request(A1111_URL + "/sdapi/v1/sd-models")
        with request.urlopen(req, timeout=2) as r:
            return r.status == 200
    except Exception:
        return False


def render_image(prompt: str, out_path: Path, width: int = 768, height: int = 432, steps: int = 28) -> bool:
    """POST to A1111 /sdapi/v1/txt2img. Returns True on success."""
    if not a1111_available():
        print(f"[skip] Stable Diffusion WebUI not running on {A1111_URL}")
        print(f"       Start it with --api flag and retry.")
        return False
    payload = {
        "prompt": prompt,
        "negative_prompt": NEGATIVE_PROMPT,
        "width": width,
        "height": height,
        "steps": steps,
        "sampler_name": "DPM++ 2M Karras",
        "cfg_scale": 6.5,
        "seed": -1,
    }
    try:
        data = json.dumps(payload).encode("utf-8")
        req = request.Request(
            A1111_URL + "/sdapi/v1/txt2img",
            data=data,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with request.urlopen(req, timeout=300) as r:
            blob = json.loads(r.read().decode("utf-8"))
        img_b64 = (blob.get("images") or [None])[0]
        if not img_b64:
            print("[err] no image in response")
            return False
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(base64.b64decode(img_b64.split(",", 1)[-1]))
        return True
    except urlerr.URLError as e:
        print(f"[err] {e}")
        return False
    except Exception as e:
        print(f"[err] {e}")
        return False


def render_for_show(slug: str, title: str, category: str = "default") -> Path | None:
    style = STYLE_BY_CATEGORY.get(category, STYLE_BY_CATEGORY["default"])
    # Sanitize title for prompt
    clean = re.sub(r"[^a-zA-Z0-9 ,.\-:']", "", title)[:80]
    prompt = f"{clean} — {style}, cover art, no text, no letters"
    out = ART_DIR / f"{slug}.png"
    print(f"[render] {slug} → {out}")
    print(f"  prompt: {prompt}")
    if out.exists():
        print(f"  [skip exists]")
        return out
    if render_image(prompt, out):
        return out
    return None


def render_all_shows() -> int:
    # Walk the build_catalog output
    library_json = REPO / "site" / "library.json"
    if not library_json.exists():
        print(f"[err] {library_json} not found. Run tools/build_catalog.py first.")
        return 1
    blob = json.loads(library_json.read_text(encoding="utf-8"))
    n = 0
    for s in blob.get("items", []):
        out = render_for_show(s.get("slug"), s.get("title", ""), s.get("category", "default"))
        if out:
            n += 1
    print(f"\nRendered {n} cover art image(s) to {ART_DIR}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--slug", help="Render one show by slug")
    ap.add_argument("--prompt", help="Render an arbitrary prompt")
    ap.add_argument("--out", help="Output path (with --prompt)")
    ap.add_argument("--all-shows", action="store_true")
    ap.add_argument("--width", type=int, default=768)
    ap.add_argument("--height", type=int, default=432)
    args = ap.parse_args()

    if args.check:
        status = "✓ RUNNING" if a1111_available() else f"✗ NOT REACHABLE at {A1111_URL}"
        print(f"Stable Diffusion WebUI: {status}")
        if not a1111_available():
            print(f"\nInstall + run instructions:")
            print(f"  1. git clone https://github.com/AUTOMATIC1111/stable-diffusion-webui")
            print(f"  2. cd stable-diffusion-webui && bash webui.sh --api  (or webui-user.bat with --api in COMMANDLINE_ARGS)")
            print(f"  3. Download a model (e.g. SD 1.5, SDXL Base) to models/Stable-diffusion/")
            print(f"  4. Server defaults to {A1111_URL}")
        return 0

    if args.all_shows:
        return render_all_shows()
    if args.prompt:
        out = Path(args.out or (ART_DIR / "ad_hoc.png"))
        ok = render_image(args.prompt, out, width=args.width, height=args.height)
        return 0 if ok else 1
    if args.slug:
        # Look up slug in library.json
        library_json = REPO / "site" / "library.json"
        if not library_json.exists():
            print(f"[err] {library_json} not found. Run tools/build_catalog.py first.")
            return 1
        blob = json.loads(library_json.read_text(encoding="utf-8"))
        match = next((s for s in blob.get("items", []) if s.get("slug") == args.slug), None)
        if not match:
            print(f"[err] slug {args.slug} not in library.json")
            return 1
        render_for_show(match.get("slug"), match.get("title", ""), match.get("category", "default"))
        return 0
    ap.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
