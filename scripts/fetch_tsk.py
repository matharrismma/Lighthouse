"""Fetch the full Treasury of Scripture Knowledge (TSK) cross-references.

The TSK is R. A. Torrey's 1880 cross-reference database — fully public
domain. openbible.info hosts a CSV version derived from TSK + votes
data; we transform it into our JSONL substrate format and drop it at
data/scripture/tsk_full.jsonl.

The engine's cross_references verifier auto-loads tsk_full.jsonl when
present, in preference to the shipped tsk_seed.jsonl. The seed remains
as a fallback so the engine works offline.

Usage:
    python scripts/fetch_tsk.py            # downloads ~3 MB, ~340k entries
    python scripts/fetch_tsk.py --min-vote 5   # filter to higher-weight refs

License: TSK itself is PD. The openbible.info dataset is CC-BY 4.0;
attribution to OpenBible.info is included in the generated file's
header (a `# source:` line at the top of the JSONL).
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request
from pathlib import Path
from typing import Optional

# Public-domain CSV: from_verse,to_verse,votes
# https://www.openbible.info/labs/cross-references/
URL = "https://a.openbible.info/data/cross-references.zip"

OUT = Path(__file__).resolve().parent.parent / "data" / "scripture" / "tsk_full.jsonl"


# OpenBible.info uses OSIS-ish abbreviations; we use SBL-style.
# Translation between the two systems.
_OSIS_TO_SBL = {
    "Gen": "Gen", "Exod": "Exo", "Lev": "Lev", "Num": "Num", "Deut": "Deu",
    "Josh": "Jos", "Judg": "Jdg", "Ruth": "Rut",
    "1Sam": "1Sa", "2Sam": "2Sa", "1Kgs": "1Ki", "2Kgs": "2Ki",
    "1Chr": "1Ch", "2Chr": "2Ch", "Ezra": "Ezr", "Neh": "Neh", "Esth": "Est",
    "Job": "Job", "Ps": "Ps", "Prov": "Pr", "Eccl": "Ecc", "Song": "Song",
    "Isa": "Isa", "Jer": "Jer", "Lam": "Lam", "Ezek": "Eze", "Dan": "Dan",
    "Hos": "Hos", "Joel": "Joe", "Amos": "Amos", "Obad": "Oba", "Jonah": "Jon",
    "Mic": "Mic", "Nah": "Nah", "Hab": "Hab", "Zeph": "Zep", "Hag": "Hag",
    "Zech": "Zec", "Mal": "Mal",
    "Matt": "Mat", "Mark": "Mar", "Luke": "Luk", "John": "John", "Acts": "Acts",
    "Rom": "Rom", "1Cor": "1Co", "2Cor": "2Co", "Gal": "Gal", "Eph": "Eph",
    "Phil": "Phil", "Col": "Col", "1Thess": "1Th", "2Thess": "2Th",
    "1Tim": "1Ti", "2Tim": "2Ti", "Titus": "Tit", "Phlm": "Phm",
    "Heb": "Heb", "Jas": "Jas", "1Pet": "1Pe", "2Pet": "2Pe",
    "1John": "1Jo", "2John": "2Jo", "3John": "3Jo", "Jude": "Jude", "Rev": "Rev",
}

_OSIS_REF_RE = re.compile(r"^([1-3]?[A-Za-z]+)\.(\d+)\.(\d+)(?:-(\d+)\.(\d+))?$")


def normalize_osis(ref: str) -> Optional[str]:
    """Convert 'Gen.1.1' (OSIS) → 'Gen.1.1' (SBL). Range refs collapse to
    the start verse (TSK records ranges occasionally)."""
    m = _OSIS_REF_RE.match(ref.strip())
    if not m:
        return None
    book = m.group(1)
    sbl = _OSIS_TO_SBL.get(book)
    if not sbl:
        return None
    return f"{sbl}.{m.group(2)}.{m.group(3)}"


def fetch_zip(url: str) -> bytes:
    print(f"fetching {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "concordance-engine/1.0"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return r.read()


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch the full TSK cross-reference corpus.")
    p.add_argument("--min-vote", type=int, default=0,
                   help="filter to entries with votes ≥ this (default 0 = keep all)")
    p.add_argument("--max-rows", type=int, default=0,
                   help="cap total rows written (0 = no cap)")
    args = p.parse_args()

    try:
        import zipfile
        import io
        zip_bytes = fetch_zip(URL)
        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
            # The archive contains one .txt (TSV) file
            names = [n for n in zf.namelist() if n.endswith(".txt") or n.endswith(".tsv")]
            if not names:
                print("zip did not contain a .txt/.tsv file", file=sys.stderr)
                return 2
            with zf.open(names[0]) as fh:
                lines = fh.read().decode("utf-8", errors="replace").splitlines()
    except Exception as exc:
        print(f"fetch failed: {exc}", file=sys.stderr)
        print("falling back: leave tsk_full.jsonl untouched; engine uses seed", file=sys.stderr)
        return 1

    OUT.parent.mkdir(parents=True, exist_ok=True)
    n_in = n_out = 0
    with OUT.open("w", encoding="utf-8") as out:
        out.write('# source: OpenBible.info cross-references (CC-BY 4.0)\n')
        out.write('# data: Treasury of Scripture Knowledge (R.A. Torrey, 1880; public domain)\n')
        for line in lines:
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("From"):
                continue
            n_in += 1
            parts = line.split("\t")
            if len(parts) < 2:
                continue
            from_raw, to_raw = parts[0], parts[1]
            votes = 1
            if len(parts) >= 3:
                try:
                    votes = int(parts[2])
                except ValueError:
                    votes = 1
            if votes < args.min_vote:
                continue
            f = normalize_osis(from_raw)
            t = normalize_osis(to_raw)
            if not f or not t:
                continue
            # Map votes to a 1-5 weight scale roughly comparable to the seed
            if votes >= 10:
                weight = 5
            elif votes >= 5:
                weight = 4
            elif votes >= 2:
                weight = 3
            else:
                weight = 2
            entry = {"from": f, "to": t, "weight": weight, "tag": "tsk", "note": ""}
            out.write(json.dumps(entry, ensure_ascii=False) + "\n")
            n_out += 1
            if args.max_rows and n_out >= args.max_rows:
                break
    print(f"read {n_in} rows, wrote {n_out} to {OUT}", file=sys.stderr)
    print(f"the engine will now use this corpus alongside the shipped seed.", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
