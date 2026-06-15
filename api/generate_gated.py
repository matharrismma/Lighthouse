"""generate_gated.py — the mechanism, formalized.

Pipeline:
    prompt
       |
       v
    RED gate         <- disqualifying input patterns (saves cost; halts before LLM)
       |
       v
    Base LLM         <- pluggable adapter (Anthropic today; local model tomorrow)
       |
       v
    Verifiers        <- deterministic domain checks (scripture_anchors,
       |                theology_doctrine; full 69 in v1.5)
       v
    FLOOR gate       <- protective minimum (reject if any verifier MISMATCH)
       |
       v
    BROTHERS gate    <- Deut 19:15 — requires 2+ named witnesses (deferred today)
       |
       v
    GOD gate         <- timing check (operator-configurable hold windows)
       |
       v
    Audit trail      <- ordered log of every step + decision + reason
       |
       v
    Content hash     <- SHA256 over canonical JSON (tamper detection; Ed25519 in v2)
       |
       v
    GatedResponse    <- stable schema: narrowhighway.gated_response/1

Design constraints (the firm foundation):
  - Pluggable base LLM:    BaseModelAdapter protocol; swap implementations freely
  - Stable schema:         versioned; old training data stays readable forever
  - Every call exports as training data: (prompt, output, trail, gate_results)
  - Verifiers deterministic: same input -> same output -> reproducible benchmarks
  - Honest about state:    BROTHERS gate today returns "deferred" (no witnesses);
                           training data captures this; once witnesses join the
                           roll, prior records can be counter-signed.
  - No file I/O in here:   pure functions; caller persists via existing
                           discernment store (api/app.py /d/<slug>).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import secrets
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Protocol, runtime_checkable

# ── Schema constants ─────────────────────────────────────────────────
SCHEMA_VERSION = "narrowhighway.gated_response/1"
MECHANISM_VERSION = "1.0.0"

# Default base model (Anthropic). Override per-call via the adapter.
# Update when a newer Claude model lands.
DEFAULT_ANTHROPIC_MODEL = os.environ.get(
    "NH_BASE_MODEL", "claude-sonnet-4-5"
)
DEFAULT_MAX_TOKENS = 4096

# Anthropic Sonnet 4.5 pricing per 1M tokens (approximate as of 2026-05).
# Used for the metrics.total_cost_usd field; relative comparison is what
# matters for benchmarking.
ANTHROPIC_INPUT_USD_PER_M = 3.0
ANTHROPIC_OUTPUT_USD_PER_M = 15.0


# ── Dataclasses (the canonical schema) ───────────────────────────────

@dataclass
class GateResult:
    gate: str            # "RED" | "FLOOR" | "BROTHERS" | "GOD"
    decision: str        # "pass" | "reject" | "wait" | "deferred"
    reason: str
    evidence: dict = field(default_factory=dict)
    latency_ms: float = 0.0


@dataclass
class VerifierResult:
    verifier: str
    verdict: str         # CONFIRMED | MISMATCH | ERROR | NOT_APPLICABLE | MIXED
    summary: str = ""
    details: list = field(default_factory=list)
    confidence: float = 1.0
    latency_ms: float = 0.0


@dataclass
class Generation:
    text: str
    model: str           # "<adapter_name>/<model_id>"
    tokens_in: int = 0
    tokens_out: int = 0
    latency_ms: float = 0.0
    cost_usd: float = 0.0


# ── BaseModelAdapter protocol ────────────────────────────────────────
# Any LLM that can take a string and return a Generation. The mechanism
# treats Claude, GPT, Llama, and our future fine-tuned model identically.

@runtime_checkable
class BaseModelAdapter(Protocol):
    name: str
    model_id: str

    def generate(self, prompt: str, **opts) -> Generation: ...


class AnthropicAdapter:
    """Calls Anthropic's Claude API. Lazy-imports the SDK so the module
    loads even without `anthropic` installed (errors surface at call time)."""

    name = "anthropic"

    def __init__(self, model_id: str = DEFAULT_ANTHROPIC_MODEL):
        self.model_id = model_id

    def generate(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                 system: str = "", **opts) -> Generation:
        try:
            import anthropic
        except ImportError as e:
            raise RuntimeError(
                "anthropic SDK not installed — pip install anthropic"
            ) from e

        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY not set in environment")

        client = anthropic.Anthropic(api_key=api_key)
        start = time.time()
        kwargs = dict(
            model=self.model_id,
            max_tokens=max_tokens,
            messages=[{"role": "user", "content": prompt}],
        )
        if system:
            kwargs["system"] = system

        r = client.messages.create(**kwargs)
        latency_ms = (time.time() - start) * 1000

        # Extract text from the response blocks
        text_parts = []
        for block in (r.content or []):
            if hasattr(block, "text"):
                text_parts.append(block.text)
        text = "".join(text_parts)

        usage = getattr(r, "usage", None)
        tokens_in = getattr(usage, "input_tokens", 0) if usage else 0
        tokens_out = getattr(usage, "output_tokens", 0) if usage else 0

        cost = (
            tokens_in * ANTHROPIC_INPUT_USD_PER_M / 1_000_000
            + tokens_out * ANTHROPIC_OUTPUT_USD_PER_M / 1_000_000
        )

        return Generation(
            text=text,
            model=f"{self.name}/{self.model_id}",
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=cost,
        )


class EchoAdapter:
    """For testing / benchmark control. Returns the prompt unchanged.
    Useful for measuring the gate/verifier overhead by itself."""

    name = "echo"

    def __init__(self, model_id: str = "echo/v0"):
        self.model_id = model_id

    def generate(self, prompt: str, **opts) -> Generation:
        start = time.time()
        # Tiny delay so latency isn't 0
        time.sleep(0.001)
        return Generation(
            text=prompt,
            model=f"{self.name}/{self.model_id}",
            tokens_in=len(prompt) // 4,
            tokens_out=len(prompt) // 4,
            latency_ms=(time.time() - start) * 1000,
            cost_usd=0.0,
        )


# ── OpenAI-compatible adapter (sovereign + universal) ────────────────
# ONE adapter for "work with anything, stand on our own". It speaks the
# OpenAI /v1/chat/completions wire format that every local runtime
# (Ollama, llama.cpp server, vLLM, LM Studio, text-generation-webui) AND
# every cloud provider (OpenAI, OpenRouter, Together, Groq, Fireworks)
# exposes. Point base_url at a LOCAL server (e.g. Ollama at
# http://localhost:11434/v1) and the engine drafts with ZERO external
# dependency -- the sovereign path; point it at a cloud URL and it
# "works with anything". Stdlib only: no torch / transformers / SDK on
# the host, so it runs even on the small engine droplet (the model is
# served wherever the compute is). The gates, verifiers, witness step,
# and signed trail are identical whatever organ drafts.

class OpenAICompatibleAdapter:
    """Calls any OpenAI-compatible /chat/completions endpoint. Stdlib only.

    Each setting resolves arg -> env -> default:
      base_url : NH_OPENAI_BASE_URL  (default http://localhost:11434/v1, Ollama)
      model_id : NH_OPENAI_MODEL     (default 'llama3.1')
      api_key  : NH_OPENAI_API_KEY   (optional; local servers need none)
    """

    name = "openai"

    def __init__(self, model_id: str | None = None, base_url: str | None = None,
                 api_key: str | None = None):
        self.base_url = (base_url or os.environ.get("NH_OPENAI_BASE_URL")
                         or "http://localhost:11434/v1").rstrip("/")
        self.model_id = (model_id or os.environ.get("NH_OPENAI_MODEL")
                         or "llama3.1")
        self.api_key = api_key or os.environ.get("NH_OPENAI_API_KEY") or ""

    def generate(self, prompt: str, max_tokens: int = DEFAULT_MAX_TOKENS,
                 system: str = "", **opts) -> Generation:
        import urllib.request
        import urllib.error
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        payload = {
            "model": self.model_id,
            "messages": messages,
            "max_tokens": int(max_tokens),
            "temperature": float(opts.get("temperature", 0.0)),
            "stream": False,
        }
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:
            headers["Authorization"] = "Bearer " + self.api_key
        url = self.base_url + "/chat/completions"
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")
        start = time.time()
        try:
            with urllib.request.urlopen(req, timeout=float(opts.get("timeout", 120))) as r:
                body = json.loads(r.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            detail = (e.read().decode("utf-8", "replace")[:300]
                      if hasattr(e, "read") else str(e))
            raise RuntimeError("OpenAI-compatible endpoint %s returned HTTP %s: %s"
                               % (url, e.code, detail)) from e
        except (urllib.error.URLError, OSError) as e:
            raise RuntimeError(
                "could not reach OpenAI-compatible endpoint %s (%s). For the "
                "sovereign path, start a local server (e.g. `ollama serve`) and set "
                "NH_OPENAI_BASE_URL=http://localhost:11434/v1, NH_OPENAI_MODEL=<model>."
                % (url, e)) from e
        latency_ms = (time.time() - start) * 1000.0
        usage = body.get("usage") or {}
        return Generation(
            text=self._extract_text(body),
            model="%s/%s" % (self.name, self.model_id),
            tokens_in=int(usage.get("prompt_tokens", 0) or 0),
            tokens_out=int(usage.get("completion_tokens", 0) or 0),
            latency_ms=latency_ms,
            cost_usd=0.0,   # local inference = $0; cloud cost not tracked here
        )

    @staticmethod
    def _extract_text(body: dict) -> str:
        choices = body.get("choices") or []
        if not choices:
            return ""
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
        if isinstance(content, list):   # some servers return content as parts
            return "".join(p.get("text", "") if isinstance(p, dict) else str(p)
                           for p in content)
        return choices[0].get("text", "") or ""   # completion-style fallback


# ── Local model adapter (the standalone goal) ────────────────────────
# Drop-in replacement for AnthropicAdapter. Loads a locally-stored
# fine-tuned model and exposes the same Generation interface.
#
# Two backends:
#   - mlx-lm     (Apple Silicon; Phase 4 PoC fine-tune)
#   - hf         (any CUDA box; transformers + PEFT; Phase 5 production)
#
# Both backends are lazy-imported; the module loads even without them
# installed (errors surface at adapter construction or first call).
#
# Cost is $0 (local inference). Latency varies by hardware + model size.

class LocalModelAdapter:
    """Loads a locally-saved (optionally LoRA-adapted) language model and
    generates without a network call. Same protocol as AnthropicAdapter.

    Backends:
      backend='mlx': uses mlx-lm. Pass `model_id` = path or HF repo id of a
        4-bit-quantized MLX model; pass `adapter_path` = path to LoRA
        adapter directory (from `mlx_lm.lora` training output).
      backend='hf':  uses transformers + PEFT. Pass `model_id` = HF repo id
        or local path; pass `adapter_path` = path to PEFT adapter dir.

    Args:
        model_id      identifier of the base model (HF repo or local path)
        adapter_path  optional path to a LoRA/PEFT adapter directory
        backend       'mlx' | 'hf'
        device        for hf only: 'cuda' | 'cpu' | 'auto'
        dtype         for hf only: 'auto' | 'float16' | 'bfloat16'
    """

    name = "local"

    def __init__(
        self,
        model_id: str,
        adapter_path: str | None = None,
        backend: str = "mlx",
        device: str = "auto",
        dtype: str = "auto",
        max_tokens_default: int = DEFAULT_MAX_TOKENS,
    ):
        self.model_id = model_id
        self.adapter_path = adapter_path
        self.backend = backend.lower()
        self.device = device
        self.dtype = dtype
        self.max_tokens_default = max_tokens_default
        self._handle = None
        if self.backend not in ("mlx", "hf"):
            raise ValueError(
                f"unknown backend '{backend}' (supported: mlx, hf)"
            )

    def _load_mlx(self):
        try:
            from mlx_lm import load, generate as mlx_generate
        except ImportError as e:
            raise RuntimeError(
                "mlx-lm not installed — `pip install mlx-lm` (Apple Silicon only)"
            ) from e
        if self.adapter_path:
            model, tokenizer = load(self.model_id, adapter_path=self.adapter_path)
        else:
            model, tokenizer = load(self.model_id)
        return {"backend": "mlx", "model": model, "tokenizer": tokenizer,
                "generate_fn": mlx_generate}

    def _load_hf(self):
        try:
            import torch
            from transformers import AutoModelForCausalLM, AutoTokenizer
        except ImportError as e:
            raise RuntimeError(
                "transformers/torch not installed — "
                "`pip install transformers accelerate torch`"
            ) from e

        dtype_map = {
            "auto": "auto",
            "float16": torch.float16,
            "bfloat16": torch.bfloat16,
            "float32": torch.float32,
        }
        torch_dtype = dtype_map.get(self.dtype, "auto")
        device_map = self.device if self.device != "auto" else "auto"

        tokenizer = AutoTokenizer.from_pretrained(self.model_id)
        model = AutoModelForCausalLM.from_pretrained(
            self.model_id,
            torch_dtype=torch_dtype,
            device_map=device_map,
        )

        # Optional PEFT/LoRA adapter
        if self.adapter_path:
            try:
                from peft import PeftModel
            except ImportError as e:
                raise RuntimeError(
                    "peft not installed — `pip install peft` (needed for adapter)"
                ) from e
            model = PeftModel.from_pretrained(model, self.adapter_path)
            model.eval()

        return {"backend": "hf", "model": model, "tokenizer": tokenizer}

    def _ensure_loaded(self):
        if self._handle is None:
            if self.backend == "mlx":
                self._handle = self._load_mlx()
            else:
                self._handle = self._load_hf()

    def generate(
        self,
        prompt: str,
        max_tokens: int | None = None,
        temperature: float = 0.7,
        **opts,
    ) -> Generation:
        self._ensure_loaded()
        n = max_tokens or self.max_tokens_default
        start = time.time()

        if self._handle["backend"] == "mlx":
            generate_fn = self._handle["generate_fn"]
            model = self._handle["model"]
            tokenizer = self._handle["tokenizer"]
            text = generate_fn(
                model, tokenizer, prompt=prompt, max_tokens=n, verbose=False,
            )
            tokens_in = len(tokenizer.encode(prompt))
            tokens_out = max(0, len(tokenizer.encode(text)) - tokens_in)
            # mlx generates a continuation INCLUDING the prompt; trim if so
            if text.startswith(prompt):
                text = text[len(prompt):].lstrip()
                tokens_out = len(tokenizer.encode(text))
        else:  # hf
            import torch
            model = self._handle["model"]
            tokenizer = self._handle["tokenizer"]
            inputs = tokenizer(prompt, return_tensors="pt").to(model.device)
            tokens_in = inputs["input_ids"].shape[-1]
            with torch.no_grad():
                out = model.generate(
                    **inputs,
                    max_new_tokens=n,
                    do_sample=(temperature > 0),
                    temperature=max(temperature, 1e-5),
                    pad_token_id=tokenizer.eos_token_id,
                )
            generated_ids = out[0][tokens_in:]
            tokens_out = generated_ids.shape[-1]
            text = tokenizer.decode(generated_ids, skip_special_tokens=True)

        latency_ms = (time.time() - start) * 1000

        return Generation(
            text=text,
            model=f"{self.name}/{self.backend}/{self.model_id}"
                  + (f"+adapter:{Path(self.adapter_path).name}"
                     if self.adapter_path else ""),
            tokens_in=tokens_in,
            tokens_out=tokens_out,
            latency_ms=latency_ms,
            cost_usd=0.0,  # local inference
        )


# Path is needed here for LocalModelAdapter
from pathlib import Path  # noqa: E402


# ── Scripture-citation extraction (deterministic) ────────────────────
# Same logic as the discern-teaching endpoint; lives here as the
# mechanism's canonical extractor.

_BIBLE_BOOKS = (
    "Genesis|Exodus|Leviticus|Numbers|Deuteronomy|Joshua|Judges|Ruth|"
    "1\\s*Samuel|2\\s*Samuel|1\\s*Kings|2\\s*Kings|1\\s*Chronicles|"
    "2\\s*Chronicles|Ezra|Nehemiah|Esther|Job|Psalms?|Proverbs|"
    "Ecclesiastes|Song\\s*of\\s*Solomon|Isaiah|Jeremiah|Lamentations|"
    "Ezekiel|Daniel|Hosea|Joel|Amos|Obadiah|Jonah|Micah|Nahum|"
    "Habakkuk|Zephaniah|Haggai|Zechariah|Malachi|"
    "Matthew|Mark|Luke|John|Acts|Romans|1\\s*Corinthians|"
    "2\\s*Corinthians|Galatians|Ephesians|Philippians|Colossians|"
    "1\\s*Thessalonians|2\\s*Thessalonians|1\\s*Timothy|2\\s*Timothy|"
    "Titus|Philemon|Hebrews|James|1\\s*Peter|2\\s*Peter|"
    "1\\s*John|2\\s*John|3\\s*John|Jude|Revelation"
)
_SCRIPTURE_CITE_RE = re.compile(
    r"\b(" + _BIBLE_BOOKS + r")\.?\s+(\d+)(?::(\d+)(?:[-–]\d+)?)?",
    re.IGNORECASE,
)


def extract_citations(text: str, limit: int = 100) -> list[dict]:
    """Pull Scripture citations from arbitrary text. Each result:
    {book, chapter, verse?, raw}"""
    out: list[dict] = []
    seen: set = set()
    for m in _SCRIPTURE_CITE_RE.finditer(text or ""):
        book = re.sub(r"\s+", " ", m.group(1).strip())
        parts = book.split()
        book = " ".join(p.capitalize() if not p.isdigit() else p for p in parts)
        ch = m.group(2)
        v = m.group(3) or ""
        key = (book.lower(), ch, v)
        if key in seen:
            continue
        seen.add(key)
        out.append({
            "book": book,
            "chapter": int(ch) if ch.isdigit() else ch,
            "verse": int(v) if v.isdigit() else None,
            "raw": m.group(0).strip(),
        })
        if len(out) >= limit:
            break
    return out


# ── Doctrine pattern scan (deterministic; keyword-based) ─────────────

_DOCTRINE_KEYWORDS: list[tuple[str, list[str]]] = [
    # Salvation
    ("salvation_by_works", ["earn salvation", "saved by works", "works of righteousness"]),
    ("prosperity_gospel", ["health and wealth", "name it and claim it",
                          "your best life now", "speak it into existence"]),
    ("universalism", ["everyone is saved", "all roads lead", "no one goes to hell"]),
    ("open_theism", ["god doesn't know the future", "god takes risks", "god is learning"]),
    # Trinity / Christology
    ("modalism", ["jesus is the father", "father became the son",
                  "one person, three modes"]),
    ("arianism", ["jesus was created", "jesus is not god", "subordinate god"]),
    ("docetism", ["christ only seemed", "christ wasn't really human"]),
    # Anthropology
    ("works_righteousness", ["you are saved by", "must do to be saved"]),
    ("gnosticism", ["secret knowledge", "hidden truth", "the elect alone know"]),
    # Eschatology
    ("hyper_preterism", ["all prophecy is fulfilled", "no future return"]),
    # Hermeneutics
    ("private_interpretation", ["spirit told me", "personal revelation overrides",
                                "my interpretation alone"]),
    # Authority
    ("anti_scripture", ["scripture is outdated", "the bible is just a book",
                        "new revelation supersedes"]),
    # Healthy markers
    ("scripture_centered", ["it is written", "the word of god says",
                            "as scripture teaches"]),
    ("christ_centered", ["jesus christ", "lord jesus", "savior",
                         "crucified and risen"]),
    ("trinitarian", ["father, son, and holy spirit", "triune god",
                     "three persons one essence"]),
]
_HEALTHY_TAGS = {"scripture_centered", "christ_centered", "trinitarian"}


def scan_doctrine_keywords(text: str) -> list[dict]:
    """Return list of {tag, matched_phrase, kind} hits."""
    if not text:
        return []
    lower = text.lower()
    hits: list[dict] = []
    for tag, phrases in _DOCTRINE_KEYWORDS:
        for phrase in phrases:
            if phrase in lower:
                hits.append({
                    "tag": tag,
                    "matched_phrase": phrase,
                    "kind": "healthy" if tag in _HEALTHY_TAGS else "concerning",
                })
                break
    return hits


# ── Gates ────────────────────────────────────────────────────────────

# RED — disqualifying patterns in the INPUT prompt. Halts before LLM call.
RED_PATTERNS: list[tuple[str, str]] = [
    (r"ignore (all |any )?previous instructions", "prompt_injection_attempt"),
    (r"\bjailbreak\b", "jailbreak_attempt"),
    (r"\b(how to (make|build|create))\s+(a\s+)?(bomb|weapon|explosive)",
     "harmful_instruction_request"),
    (r"\b(DAN mode|developer mode|admin mode)\b", "role_override_attempt"),
    (r"forget (all|everything) (you|that) (were|have been) (told|taught)",
     "instruction_override_attempt"),
]


def run_red_gate(prompt: str) -> GateResult:
    start = time.time()
    lower = (prompt or "").lower()
    for pattern, tag in RED_PATTERNS:
        if re.search(pattern, lower):
            return GateResult(
                gate="RED",
                decision="reject",
                reason=f"disqualifying pattern detected: {tag}",
                evidence={"pattern_tag": tag},
                latency_ms=(time.time() - start) * 1000,
            )
    return GateResult(
        gate="RED",
        decision="pass",
        reason="no disqualifying input patterns detected",
        latency_ms=(time.time() - start) * 1000,
    )


def run_floor_gate(gen: Generation | None,
                   verifier_results: list[VerifierResult]) -> GateResult:
    start = time.time()
    if gen is None:
        return GateResult(
            gate="FLOOR",
            decision="reject",
            reason="no generation produced",
            latency_ms=(time.time() - start) * 1000,
        )
    if not gen.text or len(gen.text.strip()) < 10:
        return GateResult(
            gate="FLOOR",
            decision="reject",
            reason="output empty or under 10 chars",
            latency_ms=(time.time() - start) * 1000,
        )
    mismatches = [vr for vr in verifier_results if vr.verdict == "MISMATCH"]
    if mismatches:
        return GateResult(
            gate="FLOOR",
            decision="reject",
            reason=f"{len(mismatches)} verifier(s) returned MISMATCH",
            evidence={"mismatches": [vr.verifier for vr in mismatches]},
            latency_ms=(time.time() - start) * 1000,
        )
    return GateResult(
        gate="FLOOR",
        decision="pass",
        reason="output above protective minimum; no mismatches",
        latency_ms=(time.time() - start) * 1000,
    )


def run_brothers_gate(gen: Generation,
                      witness_pubkeys: list | None) -> GateResult:
    """Deut 19:15 — at the mouth of two or three witnesses.
    Today the Witness Roll is being constituted; with zero witnesses the
    gate returns 'deferred' (honest) rather than blocking. Once witnesses
    join, prior 'deferred' records can be counter-signed and upgraded."""
    start = time.time()
    pubkeys = list(witness_pubkeys or [])
    n = len(pubkeys)
    if n >= 2:
        return GateResult(
            gate="BROTHERS",
            decision="pass",
            reason=f"{n} witnesses signed (Deut 19:15)",
            evidence={"witness_count": n, "pubkey_prefixes":
                      [k[:12] for k in pubkeys if isinstance(k, str)]},
            latency_ms=(time.time() - start) * 1000,
        )
    if n == 1:
        return GateResult(
            gate="BROTHERS",
            decision="wait",
            reason="1 witness signed; awaiting the second receiver",
            evidence={"witness_count": 1},
            latency_ms=(time.time() - start) * 1000,
        )
    return GateResult(
        gate="BROTHERS",
        decision="deferred",
        reason="no witnesses available (Witness Roll not yet constituted)",
        evidence={
            "witness_count": 0,
            "note": (
                "single-receiver mode — once witnesses join the roll, prior "
                "records in this state can be counter-signed and upgraded"
            ),
        },
        latency_ms=(time.time() - start) * 1000,
    )


def run_god_gate(prompt: str, gen: Generation) -> GateResult:
    """Timing check. v1: no hold windows configured. v1.5: operator-set
    hold windows by topic / claimant / season."""
    start = time.time()
    return GateResult(
        gate="GOD",
        decision="pass",
        reason="no timing constraints configured for this query",
        latency_ms=(time.time() - start) * 1000,
    )


# ── Verifier callouts ────────────────────────────────────────────────
# v1: scripture_anchors + theology_doctrine (deterministic, fast).
# v1.5: polymathic dispatch to the full 69-verifier set based on the
# output's classified domains.

def run_scripture_anchors_verifier(text: str) -> VerifierResult:
    """Extract Scripture citations from output text. v1: count and report.
    v1.5: cross-reference each citation against data/bible_en/ to confirm
    the verse exists and (optionally) check that the quoted text matches."""
    start = time.time()
    cites = extract_citations(text)
    verdict = "CONFIRMED" if cites else "NOT_APPLICABLE"
    return VerifierResult(
        verifier="scripture_anchors",
        verdict=verdict,
        summary=f"{len(cites)} Scripture citation(s) extracted",
        details=cites,
        confidence=1.0,
        latency_ms=(time.time() - start) * 1000,
    )


def run_theology_doctrine_verifier(text: str) -> VerifierResult:
    """Scan for doctrine patterns. v1: keyword-based (15 canonical
    patterns, both healthy markers and concerning ones). v1.5: deep
    semantic check against the historical Christian record."""
    start = time.time()
    hits = scan_doctrine_keywords(text)
    healthy = [h for h in hits if h["kind"] == "healthy"]
    concerning = [h for h in hits if h["kind"] == "concerning"]
    if concerning and healthy:
        verdict = "MIXED"
        summary = (f"{len(concerning)} concerning pattern(s); "
                   f"{len(healthy)} healthy marker(s)")
    elif concerning:
        verdict = "MIXED"  # keyword-only signal; not strong enough for MISMATCH
        summary = f"{len(concerning)} concerning pattern(s) detected"
    elif healthy:
        verdict = "CONFIRMED"
        summary = f"{len(healthy)} healthy marker(s); no concerning patterns"
    else:
        verdict = "NOT_APPLICABLE"
        summary = "no doctrine keyword patterns detected"
    return VerifierResult(
        verifier="theology_doctrine",
        verdict=verdict,
        summary=summary,
        details=hits,
        confidence=0.7,  # keyword-only is medium-confidence
        latency_ms=(time.time() - start) * 1000,
    )


# Registry: verifier name -> function
VERIFIERS = {
    "scripture_anchors": run_scripture_anchors_verifier,
    "theology_doctrine": run_theology_doctrine_verifier,
}


# ── The pipeline ─────────────────────────────────────────────────────

DEFAULT_VERIFIERS = ["scripture_anchors", "theology_doctrine"]


def run_gated(
    prompt: str,
    *,
    base: BaseModelAdapter | None = None,
    witness_pubkeys: list | None = None,
    context: dict | None = None,
    verifiers: list[str] | None = None,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    """Run the full mechanism end-to-end. Return a dict matching
    SCHEMA_VERSION; safe to persist as a /d/<slug> record and to export
    as training data.

    Arguments:
      prompt          - the user's input
      base            - BaseModelAdapter; defaults to AnthropicAdapter()
      witness_pubkeys - list of Ed25519 pubkey strings (witnesses who have
                        signed; today usually empty)
      context         - optional caller-side metadata (source, intent, etc.)
      verifiers       - list of verifier names to run; defaults to
                        scripture_anchors + theology_doctrine
      max_tokens      - cap on base LLM output

    Returns the canonical response dict with stable schema. No file I/O.
    """
    base = base or AnthropicAdapter()
    witness_pubkeys = witness_pubkeys or []
    context = context or {}
    verifiers = verifiers or DEFAULT_VERIFIERS

    request_id = secrets.token_hex(8)
    started_at = datetime.now(timezone.utc).isoformat()
    pipeline_start = time.time()
    trail: list[dict] = []

    def log_step(step: str, **fields) -> None:
        evt = {"at": datetime.now(timezone.utc).isoformat(), "step": step}
        evt.update(fields)
        trail.append(evt)

    log_step("received", prompt_chars=len(prompt), verifiers=verifiers)

    # 1. RED gate (input side — halts before LLM call to save cost)
    red = run_red_gate(prompt)
    log_step("red_gate", decision=red.decision, reason=red.reason)
    if red.decision == "reject":
        return _build_response(
            request_id=request_id, started_at=started_at,
            pipeline_start=pipeline_start, prompt=prompt, context=context,
            base=base, generation=None,
            verifier_results=[], gate_results=[red],
            final_decision="rejected", trail=trail,
        )

    # 2. Base LLM
    generation: Generation | None = None
    try:
        generation = base.generate(prompt, max_tokens=max_tokens)
        log_step("base_llm_call",
                 model=generation.model,
                 tokens_in=generation.tokens_in,
                 tokens_out=generation.tokens_out,
                 latency_ms=round(generation.latency_ms, 1),
                 cost_usd=round(generation.cost_usd, 4))
    except Exception as e:
        log_step("base_llm_call_failed", error=str(e)[:500])
        return _build_response(
            request_id=request_id, started_at=started_at,
            pipeline_start=pipeline_start, prompt=prompt, context=context,
            base=base, generation=None,
            verifier_results=[], gate_results=[red],
            final_decision="hold", trail=trail,
        )

    # 3. Verifiers
    verifier_results: list[VerifierResult] = []
    for vname in verifiers:
        fn = VERIFIERS.get(vname)
        if fn is None:
            log_step("verifier_missing", verifier=vname)
            continue
        vr = fn(generation.text)
        verifier_results.append(vr)
        log_step(f"verifier:{vname}", verdict=vr.verdict, summary=vr.summary)

    # 4-6. Remaining gates
    floor = run_floor_gate(generation, verifier_results)
    log_step("floor_gate", decision=floor.decision, reason=floor.reason)

    brothers = run_brothers_gate(generation, witness_pubkeys)
    log_step("brothers_gate", decision=brothers.decision,
             reason=brothers.reason)

    god = run_god_gate(prompt, generation)
    log_step("god_gate", decision=god.decision, reason=god.reason)

    gate_results = [red, floor, brothers, god]

    # 7. Final decision
    if any(g.decision == "reject" for g in gate_results):
        final = "rejected"
    elif any(g.decision == "wait" for g in gate_results):
        final = "hold"
    elif brothers.decision == "deferred":
        final = "stable_pending_witness"
    elif any(vr.verdict == "MIXED" for vr in verifier_results):
        final = "conditional"
    elif all(vr.verdict in ("CONFIRMED", "NOT_APPLICABLE")
             for vr in verifier_results):
        final = "stable"
    else:
        final = "hold"

    return _build_response(
        request_id=request_id, started_at=started_at,
        pipeline_start=pipeline_start, prompt=prompt, context=context,
        base=base, generation=generation,
        verifier_results=verifier_results, gate_results=gate_results,
        final_decision=final, trail=trail,
    )


def _build_response(
    *, request_id: str, started_at: str, pipeline_start: float,
    prompt: str, context: dict,
    base: BaseModelAdapter,
    generation: Generation | None,
    verifier_results: list[VerifierResult],
    gate_results: list[GateResult],
    final_decision: str,
    trail: list[dict],
) -> dict:
    """Assemble the canonical response and add the content hash."""
    total_latency_ms = (time.time() - pipeline_start) * 1000

    response = {
        "schema": SCHEMA_VERSION,
        "mechanism_version": MECHANISM_VERSION,
        "kind": "gated-generation",
        "request_id": request_id,
        "created_at": started_at,
        "prompt": {
            "text": prompt,
            "char_count": len(prompt),
            "context": context,
        },
        "base_model": {
            "name": base.name,
            "model_id": base.model_id,
        },
        "generation": asdict(generation) if generation else None,
        "verifier_results": [asdict(vr) for vr in verifier_results],
        "gate_results": [asdict(g) for g in gate_results],
        "final_decision": final_decision,
        "trail": trail,
        "metrics": {
            "total_latency_ms": round(total_latency_ms, 1),
            "base_llm_latency_ms": round(
                generation.latency_ms if generation else 0.0, 1),
            "verifier_latency_ms": round(
                sum(vr.latency_ms for vr in verifier_results), 1),
            "gate_latency_ms": round(
                sum(g.latency_ms for g in gate_results), 1),
            "total_cost_usd": round(
                generation.cost_usd if generation else 0.0, 4),
        },
    }

    # Content hash — SHA256 over canonical JSON, excluding the hash itself.
    # Provides tamper detection. Ed25519 signing planned for v2 once the
    # operator's signing key is provisioned.
    canonical = json.dumps(
        response, sort_keys=True, ensure_ascii=False, separators=(",", ":")
    )
    response["content_hash"] = (
        "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    )

    # Append the signing event to the trail too
    response["trail"].append({
        "at": datetime.now(timezone.utc).isoformat(),
        "step": "signed",
        "hash_algo": "sha256",
        "hash": response["content_hash"],
    })

    return response


# ── Training-corpus extraction ───────────────────────────────────────

def to_training_pair(response: dict) -> dict:
    """Convert a GatedResponse dict to a JSONL-friendly training pair.

    Stable shape across model versions; the canonical training-data record.
    The fine-tuning script reads JSONL lines of this exact shape.
    """
    gen = response.get("generation") or {}
    return {
        "schema": "narrowhighway.training_pair/1",
        "source_schema": response.get("schema"),
        "request_id": response.get("request_id"),
        "created_at": response.get("created_at"),
        "prompt": (response.get("prompt") or {}).get("text", ""),
        "completion": gen.get("text", ""),
        "final_decision": response.get("final_decision"),
        "gate_results": response.get("gate_results", []),
        "verifier_results": response.get("verifier_results", []),
        "metrics": response.get("metrics", {}),
        "base_model": response.get("base_model"),
        "content_hash": response.get("content_hash"),
    }
