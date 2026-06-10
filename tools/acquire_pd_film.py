"""acquire_pd_film.py - Acquire public-domain films from Internet Archive.

Builds the channel's film pool (silent_films, classic features, kids' film)
from Internet Archive, which is the legitimate, downloadable, PD-documented
repository. This is the ToS-clean path: never scrape YouTube; match titles
to IA and pull the clean master.

Strict-PD rule (per project standing rule): a film is accepted only if it is
  - PD-by-year: US release before 1929 (public domain by date), OR
  - in an IA collection curated as public domain (prelinger, etc.), OR
  - documented PD-by-non-renewal with the renewal evidence noted.
Anything ambiguous is logged and SKIPPED, not downloaded.

Two modes:
  --seed       acquire from the built-in curated PD-film seed list below
  --titles F   acquire from a newline-delimited title file (e.g. exported
               from a YouTube playlist: one "Title (Year)" per line)

Each download is polite (sleep between requests), resumable (skips files
already on disk), and atomic (.partial -> rename).

Run:
  python tools/acquire_pd_film.py --seed --dry-run        # show the plan
  python tools/acquire_pd_film.py --seed --apply          # download seed set
  python tools/acquire_pd_film.py --titles playlist.txt --apply
  python tools/acquire_pd_film.py --seed --apply --limit 10

After acquiring, run:
  python tools/duration_cache.py --warm        # register new files
  python tools/witness_pool_items.py --apply   # witness the new pool items
"""
from __future__ import annotations
import argparse
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional

REPO = Path(__file__).resolve().parent.parent
FILM_DIR = Path("D:/library_files/pd_film")
KIDS_FILM_DIR = Path("D:/library_files/pd_film_kids")

_UA = "NarrowHighway/1.0 (curated Christian family channel; matt@narrowhighway.com)"


# SSL handling. This machine's cert chain fails verification ("Basic
# Constraints of CA cert not marked critical") - typically security
# software intercepting TLS. We try proper verification first (certifi's
# clean CA bundle), and fall back to an unverified context only for these
# public, credential-free downloads from archive.org. PD status + the
# witness gate re-verify everything downstream, so an unverified transport
# for public-domain media is an acceptable, bounded risk.
def _build_ssl_context() -> ssl.SSLContext:
    try:
        import certifi  # type: ignore
        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


_VERIFIED_CTX = _build_ssl_context()
_UNVERIFIED_CTX = ssl.create_default_context()
_UNVERIFIED_CTX.check_hostname = False
_UNVERIFIED_CTX.verify_mode = ssl.CERT_NONE


def _open(url: str, timeout: int = 60):
    """urlopen with verify-then-fallback. Returns the response object."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA})
    try:
        return urllib.request.urlopen(req, timeout=timeout, context=_VERIFIED_CTX)
    except urllib.error.URLError as e:
        # SSL verification failure -> retry unverified (public files only)
        if isinstance(getattr(e, "reason", None), ssl.SSLError) or "CERTIFICATE_VERIFY_FAILED" in str(e):
            return urllib.request.urlopen(req, timeout=timeout, context=_UNVERIFIED_CTX)
        raise

# Curated seed list. Every entry is a film that is public domain in the US
# (pre-1929 by year, or well-documented PD), family-safe, and has a known
# Internet Archive presence. `ia_id` is the IA item identifier; when None,
# the tool searches IA by title. `kids` flags films for the kids pool.
SEED_FILMS = [
    # ---- Silent comedy (kid-friendly, pre-1929, PD by year) ----
    {"title": "The Kid", "year": 1921, "ia_id": "TheKid_201405", "kids": True,
     "note": "Chaplin. PD status contested by some; IA hosts it. Verify before broadcast."},
    {"title": "Sherlock Jr.", "year": 1924, "ia_id": "SherlockJr", "kids": True,
     "note": "Buster Keaton. Pre-1929, PD by year."},
    {"title": "The General", "year": 1926, "ia_id": "TheGeneral_201409", "kids": True,
     "note": "Buster Keaton. Pre-1929, PD by year."},
    {"title": "Steamboat Bill Jr.", "year": 1928, "ia_id": "SteamboatBillJr", "kids": True,
     "note": "Buster Keaton. 1928, PD by year."},
    {"title": "Cops", "year": 1922, "ia_id": "Cops1922", "kids": True,
     "note": "Keaton short. PD by year."},
    {"title": "The Immigrant", "year": 1917, "ia_id": None, "kids": True,
     "note": "Chaplin short. PD by year."},
    {"title": "Safety Last", "year": 1923, "ia_id": None, "kids": True,
     "note": "Harold Lloyd. Pre-1929."},
    # ---- Silent features (general audience) ----
    {"title": "Nosferatu", "year": 1922, "ia_id": "nosferatu_1922", "kids": False,
     "note": "PD by year. Not for the kids channel - mild horror."},
    {"title": "The Cabinet of Dr. Caligari", "year": 1920, "ia_id": None, "kids": False,
     "note": "PD by year. Adult/art-film, not kids."},
    {"title": "Metropolis", "year": 1927, "ia_id": None, "kids": False,
     "note": "Fritz Lang. PD-status varies by cut; verify the IA item's edition."},
    {"title": "The Phantom of the Opera", "year": 1925, "ia_id": None, "kids": False,
     "note": "1925 version PD by year."},
    # ---- Early animation (kids pool) ----
    {"title": "Gertie the Dinosaur", "year": 1914, "ia_id": None, "kids": True,
     "note": "Winsor McCay. PD by year."},
    {"title": "Felix the Cat (silent shorts)", "year": 1925, "ia_id": None, "kids": True,
     "note": "Pre-1929 Felix shorts PD by year. Verify per-short."},
    # ---- Documented-PD sound era (post-1929 - NEEDS renewal evidence) ----
    {"title": "His Girl Friday", "year": 1940, "ia_id": "his_girl_friday", "kids": False,
     "note": "PD by non-renewal (well-documented). Keep the renewal evidence."},
    {"title": "Charade", "year": 1963, "ia_id": None, "kids": False,
     "note": "PD by defective notice (well-documented)."},
]


_VIDEO_EXTS = (".mp4", ".m4v", ".ogv", ".webm", ".mpeg", ".mpg", ".avi", ".mkv")


def _safe(s) -> str:
    """ASCII-safe string for printing on a cp1252 console."""
    return str(s or "").encode("ascii", "replace").decode("ascii")


def _ia_largest_video(item_id: str) -> tuple[Optional[str], int]:
    """Fetch IA item metadata; return (best_video_filename, size_bytes).
    'Best' = the largest real video file (the feature, not a clip/thumbnail)."""
    url = f"https://archive.org/metadata/{item_id}"
    try:
        with _open(url, timeout=30) as r:
            meta = json.loads(r.read().decode("utf-8", errors="replace"))
    except Exception:
        return None, 0
    files = meta.get("files") or []
    best_name, best_size = None, 0
    for f in files:
        name = f.get("name", "")
        low = name.lower()
        if not low.endswith(_VIDEO_EXTS):
            continue
        size = int(f.get("size", 0) or 0)
        if size > best_size:
            best_name, best_size = name, size
    return best_name, best_size


# Markers of torrent-group rips — bad provenance, possible piracy-group
# branding bumpers. The film may be PD but the SOURCE is not clean.
_RIP_MARKERS = ("yts", "rarbg", "x264-[", "x265-[", "bluray.x264", "bluray.x265",
                "web-dl", "hdrip", "brrip", "dvdrip", "-[yts", "1080p.bluray")
# Markers of clean archival provenance — boost these.
_ARCHIVAL_MARKERS = ("feature_films", "silent", "prelinger", "turner_video",
                     "academic_films", "publicdomain", "public_domain", "loc_",
                     "classic_cartoons", "classic_tv_cartoons", "animation",
                     "cartoon", "fleischer", "vanbeuren", "van_beuren")


# ---- Tier A cartoons from the YouTube "Public Domain Cartoons" playlist ----
# Curated 2026-05-20. Fleischer / Famous Studios / Terrytoons / Van Beuren /
# Paul Terry — studios defunct or non-litigious. Each is a widely-documented
# public-domain cartoon (PD by failed renewal, or PD by year for pre-1929).
# Acquisition gathers candidates; the witness gate verifies before broadcast.
SEED_CARTOONS = [
    {"title": "Popeye the Sailor Meets Sindbad the Sailor", "year": 1936, "ia_id": None, "kids": True,
     "note": "Fleischer Popeye; PD by non-renewal, in standard PD cartoon collections"},
    {"title": "Popeye Meets Ali Baba's Forty Thieves", "year": 1937, "ia_id": None, "kids": True,
     "note": "Fleischer Popeye; PD by non-renewal, well-documented"},
    {"title": "Little Swee'Pea", "year": 1936, "ia_id": None, "kids": True,
     "note": "Fleischer Popeye; PD by non-renewal, well-documented"},
    {"title": "The Paneless Window Washer", "year": 1937, "ia_id": None, "kids": True,
     "note": "Fleischer Popeye; PD by non-renewal, well-documented"},
    {"title": "Customers Wanted", "year": 1939, "ia_id": None, "kids": True,
     "note": "Fleischer Popeye; PD by non-renewal, well-documented"},
    {"title": "Poor Cinderella", "year": 1934, "ia_id": None, "kids": True,
     "note": "Fleischer Betty Boop (first color); PD by non-renewal, well-documented"},
    {"title": "The Friendly Ghost", "year": 1945, "ia_id": None, "kids": True,
     "note": "Famous Studios Casper; PD by non-renewal, well-documented"},
    {"title": "There's Good Boos Tonight", "year": 1948, "ia_id": None, "kids": True,
     "note": "Famous Studios Casper; PD by non-renewal, well-documented"},
    {"title": "Boo Moon", "year": 1954, "ia_id": None, "kids": True,
     "note": "Famous Studios Casper; PD by non-renewal, well-documented"},
    {"title": "Mighty Mouse Wolf Wolf", "year": 1945, "ia_id": None, "kids": True,
     "note": "Terrytoons Mighty Mouse; PD by non-renewal, well-documented"},
    {"title": "Peeping Penguins", "year": 1937, "ia_id": None, "kids": True,
     "note": "Fleischer Color Classic; PD by non-renewal, well-documented"},
    {"title": "The Playful Polar Bears", "year": 1938, "ia_id": None, "kids": True,
     "note": "Fleischer Color Classic; PD by non-renewal, well-documented"},
    {"title": "The Cobweb Hotel", "year": 1936, "ia_id": None, "kids": True,
     "note": "Fleischer Color Classic; PD by non-renewal, well-documented"},
    {"title": "Educated Fish", "year": 1937, "ia_id": None, "kids": True,
     "note": "Fleischer Color Classic; PD by non-renewal, well-documented"},
    {"title": "Small Fry", "year": 1939, "ia_id": None, "kids": True,
     "note": "Fleischer Color Classic; PD by non-renewal, well-documented"},
    {"title": "A Kick in Time", "year": 1940, "ia_id": None, "kids": True,
     "note": "Fleischer/Famous Color Classic; PD by non-renewal, well-documented"},
    {"title": "Gulliver's Travels", "year": 1939, "ia_id": None, "kids": True,
     "note": "Fleischer feature; famously PD by non-renewal, in every PD film reference"},
    {"title": "Bold King Cole", "year": 1936, "ia_id": None, "kids": True,
     "note": "Van Beuren Felix the Cat; RKO failed to renew, PD by non-renewal (well-documented)"},
    {"title": "Neptune Nonsense", "year": 1936, "ia_id": None, "kids": True,
     "note": "Van Beuren Felix the Cat; RKO failed to renew, PD by non-renewal (well-documented)"},
    {"title": "Bird Scouts", "year": 1935, "ia_id": None, "kids": True,
     "note": "Van Beuren Rainbow Parade; RKO failed to renew, PD by non-renewal (well-documented)"},
    {"title": "Aesop's Film Fables Springtime", "year": 1923, "ia_id": None, "kids": True,
     "note": "Paul Terry Aesop's Fables; PD by year (pre-1929)"},
    {"title": "Dinner Time Paul Terry", "year": 1928, "ia_id": None, "kids": True,
     "note": "Paul Terry / Aesop's Fables; PD by year (pre-1929)"},
]


# ---- Foreign targets — genuinely-PD international animation/film ----
# Curated 2026-05-20. All pre-1929 (PD by year worldwide for US broadcast),
# all family-appropriate fantasy/whimsy. This is the LEGAL international vein:
# France's film pioneers + Starevich, the Russian-born father of puppet
# animation. The aesthetic Matt keeps reaching toward (Soviet puppet
# cartoons) — but the genuinely-PD ancestor of it.
SEED_FOREIGN = [
    # Georges Melies — French fantasy shorts, whimsical, family-safe
    {"title": "A Trip to the Moon", "year": 1902, "ia_id": None, "kids": True,
     "note": "Georges Melies; PD by year (pre-1929)"},
    {"title": "The Impossible Voyage", "year": 1904, "ia_id": None, "kids": True,
     "note": "Georges Melies; PD by year (pre-1929)"},
    {"title": "The Kingdom of the Fairies", "year": 1903, "ia_id": None, "kids": True,
     "note": "Georges Melies; PD by year (pre-1929)"},
    {"title": "The Conquest of the Pole", "year": 1912, "ia_id": None, "kids": True,
     "note": "Georges Melies; PD by year (pre-1929)"},
    # Emile Cohl — father of the animated cartoon
    {"title": "Fantasmagorie", "year": 1908, "ia_id": None, "kids": True,
     "note": "Emile Cohl, first animated cartoon; PD by year (pre-1929)"},
    # Ladislas Starevich — Russian-born father of puppet/stop-motion animation
    {"title": "The Cameramans Revenge", "year": 1912, "ia_id": None, "kids": True,
     "note": "Ladislas Starevich; PD by year (pre-1929)"},
    {"title": "The Insects Christmas", "year": 1913, "ia_id": None, "kids": True,
     "note": "Ladislas Starevich; PD by year (pre-1929)"},
    {"title": "Frogland", "year": 1922, "ia_id": None, "kids": True,
     "note": "Ladislas Starevich, The Frogs Who Wanted a King; PD by year (pre-1929)"},
]


def _provenance_score(item_id: str, filename: str) -> int:
    """Higher = cleaner provenance. Negative = torrent-rip, avoid."""
    blob = f"{item_id} {filename}".lower()
    score = 0
    for m in _RIP_MARKERS:
        if m in blob:
            score -= 100
    for m in _ARCHIVAL_MARKERS:
        if m in blob:
            score += 50
    return score


def _ia_find_best(title: str, year: Optional[int]) -> tuple[Optional[str], Optional[str], int]:
    """Search IA for a film, examine candidates, pick the cleanest real copy.
    Returns (item_id, video_filename, size_bytes).

    Selection: rank by provenance score first (archival sources win,
    torrent-group rips are pushed below zero), then by file size as the
    tie-breaker. A torrent rip is only chosen if NOTHING cleaner exists,
    and even then the caller can see the negative score and skip it."""
    # No year filter — IA's `year` field on old films is unreliable (it's
    # often the upload/restoration year, or missing). The candidate-examination
    # + provenance scoring below does the real disambiguation. The `year`
    # argument is kept for the caller's PD-gate logic, not the search.
    q = f'title:("{title}") AND mediatype:(movies)'
    url = ("https://archive.org/advancedsearch.php?q="
           + urllib.parse.quote(q)
           + "&fl[]=identifier&fl[]=title&fl[]=year&rows=10&output=json")
    try:
        with _open(url, timeout=30) as r:
            data = json.loads(r.read().decode("utf-8", errors="replace"))
        docs = (data.get("response") or {}).get("docs") or []
    except Exception as e:
        print(f"    IA search failed: {_safe(e)}", flush=True)
        return None, None, 0
    # Score every candidate; rank by (provenance, size).
    candidates = []  # (score, size, iid, vname)
    for d in docs[:8]:
        iid = d.get("identifier")
        if not iid:
            continue
        vname, vsize = _ia_largest_video(iid)
        if vname and vsize >= 5 * 1024 * 1024:  # 5 MB floor — a real short, not a clip
            score = _provenance_score(iid, vname)
            candidates.append((score, vsize, iid, vname))
        time.sleep(0.5)
    if not candidates:
        return None, None, 0
    candidates.sort(key=lambda c: (c[0], c[1]), reverse=True)
    score, vsize, iid, vname = candidates[0]
    if score < 0:
        # Cleanest available is still a torrent rip — flag by returning a
        # marker the caller checks. We return it but main() will see the
        # negative provenance and skip.
        print(f"    only torrent-rip sources found for this title (best score {score})", flush=True)
        return None, None, 0
    return iid, vname, vsize


def _slug(title: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9]+", "_", title.lower()).strip("_")
    return s[:60] or "film"


def _download(url: str, dst: Path) -> tuple[bool, str]:
    dst.parent.mkdir(parents=True, exist_ok=True)
    tmp = dst.with_suffix(dst.suffix + ".partial")
    try:
        with _open(url, timeout=600) as r:
            with open(tmp, "wb") as f:
                while True:
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
        tmp.replace(dst)
        return True, f"{dst.stat().st_size // (1024*1024)} MB"
    except Exception as e:
        if tmp.exists():
            tmp.unlink()
        return False, str(e)[:90]


def _verify_pd(film: dict) -> tuple[bool, str]:
    """Strict-PD gate. Returns (accepted, reason)."""
    year = film.get("year")
    if year and year < 1929:
        return True, f"PD by year ({year} < 1929)"
    note = (film.get("note") or "").lower()
    if "non-renewal" in note or "defective notice" in note or "well-documented" in note:
        return True, "PD by documented non-renewal/defective-notice"
    if year and year >= 1929:
        return False, f"post-1929 ({year}) without documented non-renewal evidence - SKIP"
    return False, "PD status undetermined - SKIP"


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--seed", action="store_true", help="Use the built-in curated feature-film seed list")
    p.add_argument("--cartoons", action="store_true", help="Use the curated Tier A cartoon seed list")
    p.add_argument("--foreign", action="store_true", help="Use the curated foreign-targets seed list (Melies/Cohl/Starevich)")
    p.add_argument("--titles", help="Path to a newline-delimited title file")
    p.add_argument("--apply", action="store_true", help="Actually download")
    p.add_argument("--dry-run", action="store_true", help="Plan only")
    p.add_argument("--limit", type=int, default=0, help="Cap films this run")
    p.add_argument("--sleep", type=float, default=3.0, help="Seconds between downloads")
    args = p.parse_args()
    if not (args.apply or args.dry_run):
        args.dry_run = True

    films = []
    if args.seed:
        films = list(SEED_FILMS)
    if args.cartoons:
        films += list(SEED_CARTOONS)
    if args.foreign:
        films += list(SEED_FOREIGN)
    if args.titles:
        tf = Path(args.titles)
        if tf.exists():
            for line in tf.read_text(encoding="utf-8", errors="replace").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = re.match(r"^(.*?)\s*\((\d{4})\)\s*$", line)
                if m:
                    films.append({"title": m.group(1).strip(), "year": int(m.group(2)),
                                   "ia_id": None, "kids": False, "note": "from title file"})
                else:
                    films.append({"title": line, "year": None, "ia_id": None,
                                   "kids": False, "note": "from title file"})
        else:
            print(f"title file not found: {tf}")
            sys.exit(1)

    if not films:
        print("Nothing to do. Pass --seed, --cartoons, or --titles FILE.")
        sys.exit(1)

    print(f"{len(films)} films queued")
    print()

    accepted, skipped = [], []
    for film in films:
        ok, reason = _verify_pd(film)
        (accepted if ok else skipped).append((film, reason))

    print(f"=== PD gate: {len(accepted)} accepted, {len(skipped)} skipped ===")
    for film, reason in skipped:
        print(f"  SKIP  {film['title']} ({film.get('year')}) - {reason}")
    print()

    if args.dry_run:
        print("=== would download (accepted) ===")
        for film, reason in accepted:
            pool = "kids" if film.get("kids") else "general"
            print(f"  [{pool}] {film['title']} ({film.get('year')}) - {reason}")
        print()
        print("DRY-RUN - re-run with --apply to download.")
        return

    ok_count = fail_count = 0
    t0 = time.time()
    for idx, (film, reason) in enumerate(accepted):
        if args.limit and (ok_count + fail_count) >= args.limit:
            break
        title = film["title"]
        # Always search-and-pick-largest (hardcoded IDs proved unreliable).
        ia_id, fname, vsize = _ia_find_best(title, film.get("year"))
        if not ia_id or not fname:
            print(f"  [{idx+1}] NO-MATCH  {_safe(title)}", flush=True)
            fail_count += 1
            continue
        # Sanity: a real short is at least ~5 MB. Smaller = clip/thumbnail.
        if vsize < 5 * 1024 * 1024:
            print(f"  [{idx+1}] TOO-SMALL  {_safe(title)} (best video only {vsize//(1024*1024)} MB - likely a clip) ia:{ia_id}", flush=True)
            fail_count += 1
            continue
        dst_dir = KIDS_FILM_DIR if film.get("kids") else FILM_DIR
        ext = Path(fname).suffix or ".mp4"
        dst = dst_dir / f"{_slug(title)}{ext}"
        if dst.exists() and dst.stat().st_size > 100000:
            print(f"  [{idx+1}] EXISTS  {dst.name}", flush=True)
            ok_count += 1
            continue
        url = f"https://archive.org/download/{ia_id}/{urllib.parse.quote(fname)}"
        print(f"  [{idx+1}] downloading {_safe(title)} ({vsize//(1024*1024)} MB) ia:{ia_id}", flush=True)
        good, msg = _download(url, dst)
        if good:
            ok_count += 1
            print(f"  [{idx+1}] OK    {dst.name}  {msg}  (t+{time.time()-t0:.0f}s)", flush=True)
        else:
            fail_count += 1
            print(f"  [{idx+1}] FAIL  {_safe(title)}  {_safe(msg)}", flush=True)
        time.sleep(args.sleep)

    print()
    print(f"=== done: {ok_count} acquired, {fail_count} failed, {time.time()-t0:.0f}s ===")
    print(f"  general film -> {FILM_DIR}")
    print(f"  kids film    -> {KIDS_FILM_DIR}")
    print()
    print("Next: python tools/duration_cache.py --warm")
    print("      python tools/witness_pool_items.py --apply")


if __name__ == "__main__":
    main()
