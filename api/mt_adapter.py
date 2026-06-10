"""Machine translation adapter — provider-agnostic, key-from-env, disk-cached.

Translates engine-authored English content (parable narrations, protocol
step-text, training step-text, almanac wisdom, FieldKit prompts, UI strings,
condition presets) into the reader's language.

Scripture is NOT routed through here — that goes through `scripture_lookup`
which swaps to the parallel public-domain translation already trusted in
the target language. Per `project_parallel_translations_rule.md`.

## Posture (matches `project_network_principle_stripped_seeds.md`)

- **Floor**: zero providers configured → returns input unchanged.
  Engine never crashes for lack of an MT key.
- **Ceiling**: when DeepL / Anthropic / LibreTranslate is configured via
  env var, MT happens on demand and caches to disk forever.
- **Provider-agnostic**: operator picks any one (or none); the adapter
  picks the first configured one in priority order.
- **Cache-first**: every translation hashes (content_sha, target_lang) →
  `data/mt_cache/<lang>.jsonl`. Once translated, no re-spend.

## Provider env vars

- `DEEPL_API_KEY`             — DeepL (best for European langs; free 500K/mo)
- `ANTHROPIC_API_KEY`         — Claude API (every language; flexible)
- `LIBRETRANSLATE_URL`        — LibreTranslate endpoint (self-host or cloud)
- `LIBRETRANSLATE_API_KEY`    — optional LT key

Priority (highest quality first): DEEPL → ANTHROPIC → LIBRETRANSLATE.

## Public surface

- `is_available()` → True if any provider is configured
- `providers_status()` → dict of which providers are reachable
- `translate(text, target_lang, source_lang="en")` → translated text + meta
- `cache_stats()` → counts per language
"""
from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional

_REPO = Path(__file__).parent.parent
_CACHE_DIR = _REPO / "data" / "mt_cache"
_LANG_CORPUS_DIR = _REPO / "data" / "lang_corpus"

# Same English stopword set used during alignment-table construction
# (scripts/build_bible_alignment.py). These tokens were dropped from the
# corpus, so the lookup must also ignore them rather than fail on missing.
_EN_STOPWORDS = frozenset("""
the a an and or but if then so to of in on at by for with from as is are was were be been being
have has had do does did will would shall should may might must can could
this that these those it its his her him my your our their them they we us you i me he she
not no nor yes oh ah lo behold
all any some each every many few much most least less more
who whom whose what which when where why how
into upon onto unto over under above below before after again still also too very just only
""".split())

# Skip MT for text shorter than this — short fragments are usually IDs or
# format-specific tokens that don't make sense to translate.
_MIN_LEN_FOR_MT = 3

# Hard cap to avoid runaway costs on a single oversized field.
_MAX_LEN_FOR_MT = 8000


# ── Cache layer ──────────────────────────────────────────────────────────

def _content_sha(text: str, source_lang: str, target_lang: str) -> str:
    h = hashlib.sha256(
        f"{source_lang}\x00{target_lang}\x00{text}".encode("utf-8")
    ).hexdigest()
    return h[:32]


def _cache_path(target_lang: str) -> Path:
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    return _CACHE_DIR / f"{target_lang}.jsonl"


_CACHE_INDEX: Dict[str, Dict[str, Dict[str, Any]]] = {}
_CACHE_MTIME: Dict[str, float] = {}


def _load_cache(target_lang: str) -> Dict[str, Dict[str, Any]]:
    path = _cache_path(target_lang)
    if not path.exists():
        _CACHE_INDEX[target_lang] = {}
        _CACHE_MTIME[target_lang] = 0.0
        return _CACHE_INDEX[target_lang]
    mtime = path.stat().st_mtime
    if target_lang in _CACHE_INDEX and _CACHE_MTIME.get(target_lang) == mtime:
        return _CACHE_INDEX[target_lang]
    idx: Dict[str, Dict[str, Any]] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            sha = rec.get("sha")
            if sha:
                idx[sha] = rec  # later record overrides earlier
    except OSError:
        pass
    _CACHE_INDEX[target_lang] = idx
    _CACHE_MTIME[target_lang] = mtime
    return idx


def _cache_write(target_lang: str, rec: Dict[str, Any]) -> None:
    path = _cache_path(target_lang)
    try:
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        # Invalidate in-memory cache so next read picks up the new record
        _CACHE_MTIME[target_lang] = 0.0
    except OSError:
        pass


def cache_stats() -> Dict[str, Any]:
    """Per-language cache size and oldest/newest record timestamps."""
    out: Dict[str, Any] = {}
    if not _CACHE_DIR.exists():
        return out
    for path in sorted(_CACHE_DIR.glob("*.jsonl")):
        lang = path.stem
        idx = _load_cache(lang)
        if not idx:
            continue
        timestamps = [r.get("translated_at", 0) for r in idx.values()]
        out[lang] = {
            "count": len(idx),
            "oldest": min(timestamps) if timestamps else 0,
            "newest": max(timestamps) if timestamps else 0,
        }
    return out


# ── Provider stubs ───────────────────────────────────────────────────────

# ── Provider: Bible-corpus alignment (free, offline, Scripture-vocabulary) ──

_CORPUS_CACHE: Dict[str, Dict[str, Dict[str, Any]]] = {}
_CORPUS_MTIME: Dict[str, float] = {}

# Minimum Dice score to accept a Bible-corpus candidate as a translation.
# Below this, the alignment is too uncertain to use without a human check.
_CORPUS_MIN_SCORE = 0.30

# Bible-corpus is good for single tokens and short phrases. Beyond this
# many tokens, fall through to a real MT provider — concatenating word-by-
# word translations of long English text into target produces nonsense.
_CORPUS_MAX_TOKENS = 4


def _load_corpus(corpus_key: str) -> Dict[str, Dict[str, Any]]:
    """Load src→{candidates: [...]} index, mtime-cached.

    `corpus_key` is the JSONL stem in data/lang_corpus/. Forward direction
    is `<target_lang>` (e.g. "es" means EN→ES). Reverse direction is
    `<source_lang>_to_en` (e.g. "es_to_en" means ES→EN).
    """
    path = _LANG_CORPUS_DIR / f"{corpus_key}.jsonl"
    if not path.exists():
        return {}
    mtime = path.stat().st_mtime
    if corpus_key in _CORPUS_CACHE and _CORPUS_MTIME.get(corpus_key) == mtime:
        return _CORPUS_CACHE[corpus_key]
    idx: Dict[str, Dict[str, Any]] = {}
    try:
        for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue
            src = rec.get("src")
            if src:
                idx[src] = rec
    except OSError:
        return _CORPUS_CACHE.get(corpus_key, {})
    _CORPUS_CACHE[corpus_key] = idx
    _CORPUS_MTIME[corpus_key] = mtime
    return idx


def _tokenize_target_for_lookup(lang: str, text: str) -> List[str]:
    """Tokenize a target-language string the same way the reverse-alignment
    build did, so reverse lookups can match. CJK languages need character/
    syllable segmentation; Latin-script languages use simple word splits."""
    import re as _re
    if lang in ("zh", "ja", "ko"):
        # Mirror cjk_tokens in scripts/build_bible_alignment.py
        out: List[str] = []
        n = len(text)
        i = 0
        while i < n:
            ch = text[i]
            if "一" <= ch <= "鿿":  # Han
                out.append(ch); i += 1
            elif "가" <= ch <= "힯":  # Hangul syllable run
                j = i
                while j < n and "가" <= text[j] <= "힯":
                    j += 1
                out.append(text[i:j]); i = j
            elif ("぀" <= ch <= "ヿ") or ("ㇰ" <= ch <= "ㇿ"):  # Kana
                j = i
                while j < n and (("぀" <= text[j] <= "ヿ") or ("ㇰ" <= text[j] <= "ㇿ")):
                    j += 1
                out.append(text[i:j]); i = j
            else:
                i += 1
        return out
    # Latin-script: simple word match, ≥3 chars
    return [m.group(0).lower() for m in _re.finditer(r"[A-Za-zÀ-ÿĀ-ž]+", text) if len(m.group(0)) >= 3]


def _provider_bible_corpus(text: str, source_lang: str, target_lang: str) -> Optional[str]:
    """Look up source phrase in the Bible-corpus alignment table.

    Supports both directions:
      - EN → target  (uses `<target>.jsonl` forward alignment)
      - target → EN  (uses `<source>_to_en.jsonl` reverse alignment)

    Stopwords + sub-3-char tokens are dropped. Content words below the
    confidence threshold pass through untranslated. Decline (return None)
    when fewer than half the content words matched, or when too many
    content words to be a reliable phrase lookup — those cases fall
    through to a real MT provider.
    """
    if source_lang == target_lang:
        return None

    # Direction A: EN → target
    if source_lang == "en":
        corpus = _load_corpus(target_lang)
        if not corpus:
            return None
        import re as _re
        word_re = _re.compile(r"\b[A-Za-z']+\b")
        tokens = [t.lower().strip("'") for t in word_re.findall(text)]
        content = [t for t in tokens if len(t) >= 3 and t not in _EN_STOPWORDS]
        if not content or len(content) > _CORPUS_MAX_TOKENS:
            return None
        pieces: List[str] = []
        matched = 0
        for t in content:
            rec = corpus.get(t)
            if rec and rec.get("candidates"):
                top = rec["candidates"][0]
                if top.get("score", 0) >= _CORPUS_MIN_SCORE:
                    pieces.append(top["text"])
                    matched += 1
                    continue
            pieces.append(t)
        if matched < max(1, (len(content) + 1) // 2):
            return None
        return " ".join(pieces)

    # Direction B: target → EN
    if target_lang == "en":
        corpus = _load_corpus(f"{source_lang}_to_en")
        if not corpus:
            return None
        content = _tokenize_target_for_lookup(source_lang, text)
        if not content:
            return None
        # CJK languages produce many single-char tokens; allow more of them.
        max_tokens = 12 if source_lang in ("zh", "ja", "ko") else _CORPUS_MAX_TOKENS
        if len(content) > max_tokens:
            return None
        pieces: List[str] = []
        matched = 0
        for t in content:
            rec = corpus.get(t)
            if rec and rec.get("candidates"):
                top = rec["candidates"][0]
                if top.get("score", 0) >= _CORPUS_MIN_SCORE:
                    pieces.append(top["text"])
                    matched += 1
                    continue
            pieces.append(t)
        if matched < max(1, (len(content) + 1) // 2):
            return None
        return " ".join(pieces)

    # target → other target: skip (no direct alignment table)
    return None


def bible_corpus_stats() -> Dict[str, Any]:
    """Per-language entry counts in the alignment table."""
    out: Dict[str, Any] = {}
    if not _LANG_CORPUS_DIR.exists():
        return out
    for path in sorted(_LANG_CORPUS_DIR.glob("*.jsonl")):
        lang = path.stem
        try:
            n = sum(1 for line in path.read_text(encoding="utf-8", errors="replace").splitlines() if line.strip())
        except OSError:
            n = 0
        out[lang] = n
    return out


def _provider_deepl(text: str, source_lang: str, target_lang: str) -> Optional[str]:
    key = os.environ.get("DEEPL_API_KEY")
    if not key:
        return None
    # DeepL endpoint differs for free vs paid keys. Free keys end in ":fx".
    base = "https://api-free.deepl.com" if key.endswith(":fx") else "https://api.deepl.com"
    # DeepL uses upper-case ISO codes (EN, ES, ZH, FR, PT-BR, etc.). Map.
    deepl_target = {
        "es": "ES",  "fr": "FR",  "pt": "PT-BR", "zh": "ZH",  "ru": "RU",
        "ja": "JA",  "ko": "KO",  "de": "DE",    "it": "IT",  "nl": "NL",
        "ar": "AR",  "hi": "HI",
    }.get(target_lang.lower(), target_lang.upper())
    deepl_source = (source_lang or "en").upper()
    data = urllib.parse.urlencode({
        "auth_key": key,
        "text": text,
        "source_lang": deepl_source,
        "target_lang": deepl_target,
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{base}/v2/translate",
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        tr = (body.get("translations") or [{}])[0].get("text")
        return tr or None
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
        return None


def _provider_anthropic(text: str, source_lang: str, target_lang: str) -> Optional[str]:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return None
    # Map language code → human name for clearer prompt
    lang_names = {
        "es": "Spanish (Castellano)", "fr": "French",   "pt": "Brazilian Portuguese",
        "zh": "Chinese (Mandarin, simplified)", "ru": "Russian", "ja": "Japanese",
        "ko": "Korean",   "de": "German", "it": "Italian", "nl": "Dutch",
        "ar": "Arabic",   "hi": "Hindi",  "sw": "Swahili",
    }
    src_name = lang_names.get(source_lang, source_lang)
    tgt_name = lang_names.get(target_lang, target_lang)
    prompt = (
        f"Translate the following text from {src_name} to {tgt_name}. "
        f"Preserve tone, meaning, and any Scripture quotations word-for-word "
        f"if they appear in the target language's standard public-domain "
        f"translation. Return only the translation, no commentary.\n\n"
        f"{text}"
    )
    body = json.dumps({
        "model": "claude-opus-4-5",
        "max_tokens": 4096,
        "messages": [{"role": "user", "content": prompt}],
    }).encode("utf-8")
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=body,
        headers={
            "x-api-key": key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            r = json.loads(resp.read().decode("utf-8"))
        # Claude API response: {content: [{type: "text", text: "..."}]}
        content = r.get("content") or []
        for blk in content:
            if blk.get("type") == "text":
                return blk.get("text", "").strip() or None
        return None
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
        return None


def _provider_libretranslate(text: str, source_lang: str, target_lang: str) -> Optional[str]:
    url = os.environ.get("LIBRETRANSLATE_URL")
    if not url:
        return None
    url = url.rstrip("/") + "/translate"
    payload = {
        "q":      text,
        "source": source_lang,
        "target": target_lang,
        "format": "text",
    }
    api_key = os.environ.get("LIBRETRANSLATE_API_KEY")
    if api_key:
        payload["api_key"] = api_key
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=20) as resp:
            r = json.loads(resp.read().decode("utf-8"))
        return r.get("translatedText") or None
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, OSError):
        return None


# Priority order. bible_corpus FIRST — it's free, offline, and produces
# Scripture-vocabulary diction that matches the engine's idiom. Falls through
# to a real MT provider for anything corpus can't confidently handle.
# Env-var sentinel "BIBLE_CORPUS" is always considered "configured" — the
# provider is available whenever the alignment table is built.
_PROVIDERS = [
    ("bible_corpus",   _provider_bible_corpus,   "__BUILTIN__"),
    ("deepl",          _provider_deepl,          "DEEPL_API_KEY"),
    ("anthropic",      _provider_anthropic,      "ANTHROPIC_API_KEY"),
    ("libretranslate", _provider_libretranslate, "LIBRETRANSLATE_URL"),
]


def providers_status() -> Dict[str, bool]:
    """Which providers are usable. bible_corpus is usable whenever the
    alignment table is built; others require an env-var key/URL."""
    out: Dict[str, bool] = {}
    for name, _, env_var in _PROVIDERS:
        if env_var == "__BUILTIN__":
            # bible_corpus available when at least one language's
            # alignment file exists.
            out[name] = any(
                (_LANG_CORPUS_DIR / f"{lang}.jsonl").exists()
                for lang in (
                    "es", "fr", "pt", "de", "it", "nl", "ro", "vi", "ht", "la", "sw",
                    "ru", "uk", "ar", "fa", "he", "my", "hi", "zh", "ko", "ja",
                )
            )
        else:
            out[name] = bool(os.environ.get(env_var))
    return out


def is_available() -> bool:
    """True if any MT provider is usable."""
    return any(providers_status().values())


# ── Main public API ──────────────────────────────────────────────────────

def translate(text: str, target_lang: str, source_lang: str = "en") -> Dict[str, Any]:
    """Translate `text` from `source_lang` to `target_lang`. Cached on disk.

    Returns:
        {
            "text":      the translated text (or input unchanged on fallback),
            "lang":      target_lang,
            "provider":  name of provider that did the work (or None),
            "cached":    True if served from cache,
            "fallback":  True if no provider available (text is unchanged),
        }
    """
    if not text or not isinstance(text, str):
        return {"text": text, "lang": target_lang, "provider": None, "cached": False, "fallback": True}
    if not target_lang or target_lang == source_lang:
        return {"text": text, "lang": target_lang, "provider": None, "cached": False, "fallback": True}
    if len(text) < _MIN_LEN_FOR_MT or len(text) > _MAX_LEN_FOR_MT:
        return {"text": text, "lang": target_lang, "provider": None, "cached": False, "fallback": True}

    sha = _content_sha(text, source_lang, target_lang)
    cache = _load_cache(target_lang)
    hit = cache.get(sha)
    if hit and hit.get("translated"):
        return {
            "text":     hit["translated"],
            "lang":     target_lang,
            "provider": hit.get("provider"),
            "cached":   True,
            "fallback": False,
        }

    # Cache miss — try providers in priority order.
    for name, fn, env_var in _PROVIDERS:
        if env_var != "__BUILTIN__" and not os.environ.get(env_var):
            continue
        try:
            translated = fn(text, source_lang, target_lang)
        except Exception:
            translated = None
        if translated and isinstance(translated, str) and translated.strip():
            rec = {
                "sha":            sha,
                "source_lang":    source_lang,
                "target_lang":    target_lang,
                "provider":       name,
                "original":       text,
                "translated":     translated.strip(),
                "translated_at":  int(time.time()),
            }
            _cache_write(target_lang, rec)
            return {
                "text":     translated.strip(),
                "lang":     target_lang,
                "provider": name,
                "cached":   False,
                "fallback": False,
            }

    # All providers failed or none configured — graceful English fallback.
    return {
        "text":     text,
        "lang":     target_lang,
        "provider": None,
        "cached":   False,
        "fallback": True,
    }


def translate_many(texts: List[str], target_lang: str,
                   source_lang: str = "en") -> List[Dict[str, Any]]:
    """Translate multiple strings; preserves order. Cache hits are free."""
    return [translate(t, target_lang, source_lang) for t in texts]


def translate_packet_view(view: Optional[Dict[str, Any]], target_lang: str,
                          source_lang: str = "en",
                          fields: Optional[List[str]] = None,
                          deadline: float = 0) -> Optional[Dict[str, Any]]:
    """Translate the engine-authored prose fields of a packet view in place.

    Default fields: text, question, practice, falsifiable_check, common_failure,
    prompt, practice_7day, common_drift, summary. Each is translated only when
    present and non-empty. Existing fields are overwritten; an `_en_fields`
    map is added preserving the original English so the UI can show both.

    If `deadline` (epoch seconds) is non-zero, skip remaining fields once
    the clock exceeds it. This prevents the MT pass from blocking the entire
    compound response.
    """
    if not view or not isinstance(view, dict):
        return view
    if not target_lang or target_lang == source_lang:
        return view
    fields = fields or [
        "text", "question", "practice", "falsifiable_check", "common_failure",
        "prompt", "practice_7day", "common_drift", "summary", "title",
    ]
    en_originals: Dict[str, str] = {}
    for k in fields:
        if deadline and time.time() > deadline:
            break  # Time budget exceeded — keep remaining fields in English
        v = view.get(k)
        if isinstance(v, str) and v.strip():
            result = translate(v, target_lang, source_lang)
            if not result.get("fallback"):
                en_originals[k] = v
                view[k] = result["text"]
    if en_originals:
        view["_en"] = en_originals
        view["_mt_lang"] = target_lang
    return view
