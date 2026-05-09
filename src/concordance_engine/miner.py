"""The Miner — corpus → almanac-candidate hummingbird.

Walks a configured corpus directory of EPUBs, extracts passage-shaped
text, scores each passage by axis match + numeric content + engine-
concept keywords, and persists the strongest candidates to a draft
file for curator review. Same posture as the other workers:

  * small, low-power, narrow purpose
  * patient — one tick at a time
  * append-only output, never auto-publishes
  * the engine does the math, the human does the wisdom

Per Matt's deployment philosophy: this miner doesn't compete in
hashrate (the NerdMiner does that, physically and separately). It
mines text — the engine-shaped equivalent — and submits "shares"
in the form of axis-scored candidate Almanac entries.

Output: data/miner/candidates.jsonl
        Append-only. Each line is one candidate Almanac entry shaped
        as a draft. The curator reviews, picks the ones worth keeping,
        edits the wisdom prose, and appends to data/almanac/entries.jsonl
        manually.

Configuration:
  CONCORDANCE_MINER_CORPUS  Directory of EPUBs to mine. If unset,
                             defaults to ~/OneDrive/Desktop on Windows
                             (where the author's books live).
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import time
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Set


# ── Configuration ──────────────────────────────────────────────────────

def _default_corpus_dir() -> Path:
    """Where to look for EPUBs when CONCORDANCE_MINER_CORPUS is unset."""
    cand = Path(os.path.expanduser("~/OneDrive/Desktop"))
    if cand.exists():
        return cand
    return Path(os.path.expanduser("~/Desktop"))


def corpus_dir() -> Path:
    raw = os.environ.get("CONCORDANCE_MINER_CORPUS", "").strip()
    if raw:
        return Path(raw)
    return _default_corpus_dir()


def candidates_path() -> Path:
    p = Path("data") / "miner" / "candidates.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


def seen_path() -> Path:
    """Set of passage hashes already submitted, so re-runs don't dupe."""
    p = Path("data") / "miner" / "seen.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    return p


# ── Passage extraction ─────────────────────────────────────────────────

@dataclass
class Passage:
    text: str
    source_book: str           # title from EPUB metadata
    source_file: str           # internal xhtml path inside the EPUB
    char_count: int = 0
    sentence_count: int = 0
    digest: str = ""           # sha256 of text — used for dedup

    def __post_init__(self):
        self.char_count = len(self.text)
        self.sentence_count = len(re.findall(r"[.!?](?:\s|$)", self.text))
        if not self.digest:
            self.digest = hashlib.sha256(self.text.encode("utf-8")).hexdigest()[:16]


def _epub_metadata(z: zipfile.ZipFile) -> Dict[str, str]:
    """Extract title / creator from the OPF inside an EPUB."""
    out: Dict[str, str] = {}
    for n in z.namelist():
        if n.endswith("content.opf") or n.endswith("package.opf"):
            try:
                opf = z.read(n).decode("utf-8", errors="replace")
            except OSError:
                continue
            for tag in ("dc:title", "dc:creator"):
                m = re.search(rf"<{tag}[^>]*>([^<]+)", opf)
                if m:
                    out[tag] = m.group(1).strip()
            break
    return out


def _strip_html(content: str) -> str:
    """Plain text from XHTML. Preserves paragraph breaks."""
    # Convert <br/>, <p>, <div>, <h*> close tags to newlines
    content = re.sub(r"</?(?:br|p|div|h[1-6])\b[^>]*>", "\n", content, flags=re.IGNORECASE)
    # Strip remaining tags
    content = re.sub(r"<[^>]+>", " ", content)
    # Common entities
    content = content.replace("&#x27;", "'").replace("&apos;", "'")
    content = content.replace("&#8217;", "’").replace("&rsquo;", "’")
    content = content.replace("&#8220;", "“").replace("&ldquo;", "“")
    content = content.replace("&#8221;", "”").replace("&rdquo;", "”")
    content = content.replace("&#8212;", "—").replace("&mdash;", "—")
    content = content.replace("&#8211;", "–").replace("&ndash;", "–")
    content = re.sub(r"&[a-zA-Z]+;", " ", content)
    content = re.sub(r"&#\d+;", " ", content)
    # Collapse whitespace within lines but preserve paragraph breaks
    content = re.sub(r"[ \t\f\v]+", " ", content)
    content = re.sub(r"\n{2,}", "\n\n", content)
    return content.strip()


_FRONT_MATTER_HINTS = (
    "table of contents", "copyright", "isbn", "dedicat", "about the author",
    "also by", "all rights reserved", "first edition", "title page",
    "act i", "act ii", "act iii", "epigraph", "prologue", "epilogue",
)


def _is_front_matter(text: str) -> bool:
    lower = text[:300].lower()
    return any(k in lower for k in _FRONT_MATTER_HINTS)


def extract_passages(epub_path: Path, min_chars: int = 70, max_chars: int = 480) -> List[Passage]:
    """Read an EPUB and return passage-shaped text chunks.

    Strategy: split each chapter into paragraphs, then yield paragraphs
    (or paragraph runs) that fall within the saying/short-prose range.
    Front-matter and table-of-contents pages are skipped.
    """
    if not epub_path.exists():
        return []
    out: List[Passage] = []
    try:
        with zipfile.ZipFile(epub_path) as z:
            meta = _epub_metadata(z)
            title = meta.get("dc:title", epub_path.stem)
            xhtml_files = sorted(
                n for n in z.namelist()
                if n.lower().endswith((".xhtml", ".html"))
            )
            for n in xhtml_files:
                try:
                    raw = z.read(n).decode("utf-8", errors="replace")
                except (OSError, KeyError):
                    continue
                text = _strip_html(raw)
                if not text or len(text) < 200:
                    continue
                if _is_front_matter(text):
                    continue
                # Split into paragraphs by blank-line boundaries
                paragraphs = [p.strip() for p in re.split(r"\n{2,}", text) if p.strip()]
                for p in paragraphs:
                    p_clean = re.sub(r"\s+", " ", p).strip()
                    if min_chars <= len(p_clean) <= max_chars:
                        # Skip dialogue-only paragraphs (mostly quoted speech)
                        if p_clean.count("“") + p_clean.count('"') >= 2:
                            quote_chars = sum(
                                1 for ch in p_clean
                                if ch in ('"', '“', '”')
                            )
                            if quote_chars / max(1, len(p_clean)) > 0.04:
                                continue
                        out.append(Passage(
                            text=p_clean,
                            source_book=title,
                            source_file=n,
                        ))
    except (zipfile.BadZipFile, OSError):
        return []
    return out


# ── Scoring ────────────────────────────────────────────────────────────

# Axis stem matchers — lifted from the same vocabulary the almanac uses.
AXIS_STEMS: Dict[str, List[str]] = {
    "encoding":              ["encod", "encrypt", "decod", "symbol", "cipher", "letter", "name", "language", "word"],
    "metabolism":            ["metabol", "growth", "decay", "nutri", "energ", "feed", "burn", "live", "die"],
    "reasoning":             ["reason", "logic", "proof", "compute", "calculat", "infer", "argument", "evidence"],
    "physical_substance":    ["physic", "matter", "substanc", "spatial", "geometr", "stone", "wood", "water", "earth", "rope"],
    "authority_trust":       ["author", "trust", "consent", "consensus", "legitim", "sign", "witness", "covenant", "promise"],
    "time_sequence":         ["time", "sequenc", "order", "before", "after", "deadline", "period", "morning", "year", "season"],
    "conservation_balance":  ["balanc", "conserv", "equilibri", "invariant", "preserv", "keep", "remain", "endur"],
}

# Engine-concept keywords — boost any passage that mentions a load-bearing
# concept by name. These are the words the engine and the books share.
ENGINE_CONCEPTS = (
    "the keeping", "the line", "the door", "the way", "alignment",
    "narrow path", "narrow way", "the gate", "the gates",
    "witness", "covenant", "the well",
    "discordant", "concordant", "quarantine",
    "patience", "discipline", "wait",
)

DECLARATIVE_END = re.compile(r"[.!]\s*$|\.[”\"']\s*$")
NUMERIC_RE = re.compile(r"\b\d+(?:[.,]\d+)?\b")


def _predict_axes(text: str) -> List[str]:
    lower = text.lower()
    found: Set[str] = set()
    for axis, stems in AXIS_STEMS.items():
        if any(s in lower for s in stems):
            found.add(axis)
    return sorted(found)


def _engine_concept_hits(text: str) -> List[str]:
    lower = text.lower()
    return [c for c in ENGINE_CONCEPTS if c in lower]


def score_passage(p: Passage) -> Dict[str, object]:
    """Score a passage. Higher = better candidate. No oracle calls."""
    axes = _predict_axes(p.text)
    concepts = _engine_concept_hits(p.text)
    has_numbers = bool(NUMERIC_RE.search(p.text))
    is_declarative = bool(DECLARATIVE_END.search(p.text))
    is_one_breath = p.sentence_count <= 6

    # Components
    axis_pts     = min(len(axes), 4)        # up to 4
    concept_pts  = 2 * len(concepts)         # 2 per engine-concept hit
    numeric_pts  = 1 if has_numbers else 0
    decl_pts     = 1 if is_declarative else 0
    breath_pts   = 1 if is_one_breath else 0

    total = axis_pts + concept_pts + numeric_pts + decl_pts + breath_pts

    return {
        "axes": axes,
        "engine_concepts": concepts,
        "has_numbers": has_numbers,
        "is_declarative": is_declarative,
        "is_one_breath": is_one_breath,
        "score": total,
        "score_breakdown": {
            "axis_pts": axis_pts,
            "concept_pts": concept_pts,
            "numeric_pts": numeric_pts,
            "decl_pts": decl_pts,
            "breath_pts": breath_pts,
        },
    }


# ── Draft entry shaping ────────────────────────────────────────────────

def _slug(text: str) -> str:
    seed = text.lower()[:80]
    s = re.sub(r"[^a-z0-9]+", "_", seed).strip("_")
    return s[:48] or "passage"


def candidate_from(passage: Passage, scoring: Dict[str, object]) -> Dict[str, object]:
    """Shape a passage + score into a draft Almanac entry for curation."""
    return {
        "id": f"miner-{_slug(passage.text)}-{passage.digest[:8]}",
        "kind": "passage",
        "title": passage.text if len(passage.text) <= 240 else passage.text[:240].rsplit(" ", 1)[0] + "...",
        "category": "uncategorized",
        "source": {
            "book": passage.source_book,
            "file": passage.source_file,
            "char_count": passage.char_count,
            "passage_digest": passage.digest,
        },
        "domains": [],
        "axes": scoring.get("axes", []),
        "verdict": "DRAFT",
        "wisdom": "(curator: write the dry note here — what does this passage teach?)",
        "verification": passage.text,
        "score": scoring.get("score", 0),
        "score_breakdown": scoring.get("score_breakdown", {}),
        "engine_concepts": scoring.get("engine_concepts", []),
        "extracted_at": int(time.time()),
        "triggers": {
            "keywords": [
                w for w in re.findall(r"[a-zA-Z]{4,}", passage.text.lower())
                if w not in {
                    "that","this","with","from","into","when","than","what","were",
                    "they","then","have","been","does","there","which","while",
                    "could","would","should","about","because","through","across",
                }
            ][:10],
            "axes": scoring.get("axes", []),
        },
    }


# ── Persistence helpers ────────────────────────────────────────────────

def load_seen_digests() -> Set[str]:
    p = seen_path()
    if not p.exists():
        return set()
    out: Set[str] = set()
    try:
        for line in p.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if line:
                out.add(line)
    except OSError:
        pass
    return out


def append_seen(digest: str) -> None:
    try:
        with open(seen_path(), "a", encoding="utf-8") as fh:
            fh.write(digest + "\n")
    except OSError:
        pass


def append_candidate(candidate: Dict[str, object]) -> None:
    try:
        with open(candidates_path(), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(candidate, ensure_ascii=False) + "\n")
    except OSError:
        pass


def list_candidates(limit: int = 50) -> List[Dict[str, object]]:
    p = candidates_path()
    if not p.exists():
        return []
    out: List[Dict[str, object]] = []
    try:
        for line in p.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    except OSError:
        pass
    out.sort(key=lambda c: int(c.get("score", 0)), reverse=True)
    return out[:limit]


# ── Tick — one mining pass over one book ───────────────────────────────

def list_corpus_books() -> List[Path]:
    d = corpus_dir()
    if not d.exists():
        return []
    return sorted(d.glob("*.epub"))


def mine_one_book(epub_path: Path, min_score: int = 4, max_per_book: int = 30) -> Dict[str, object]:
    """Process one book end-to-end. Returns a small summary."""
    seen = load_seen_digests()
    passages = extract_passages(epub_path)
    proposed = 0
    skipped_seen = 0
    skipped_low = 0
    top_score = 0

    for p in passages:
        if p.digest in seen:
            skipped_seen += 1
            continue
        scoring = score_passage(p)
        s = int(scoring["score"])  # type: ignore[index]
        top_score = max(top_score, s)
        if s < min_score:
            skipped_low += 1
            append_seen(p.digest)  # mark as seen-but-too-low
            continue
        cand = candidate_from(p, scoring)
        append_candidate(cand)
        append_seen(p.digest)
        proposed += 1
        if proposed >= max_per_book:
            break

    return {
        "book": epub_path.name,
        "passages_seen": len(passages),
        "candidates_proposed": proposed,
        "skipped_already_seen": skipped_seen,
        "skipped_low_score": skipped_low,
        "top_score_in_book": top_score,
    }
