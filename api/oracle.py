"""oracle.py — the ONE pluggable entry every generative edge calls.

Stage 1 of standing on our own: every remaining cloud-LLM call in the engine
routes through this single seam. Flip one env var (NH_ORACLE_PROVIDER) and the
whole system drafts on a LOCAL model (Ollama / llama.cpp / vLLM) with ZERO
external provider — while DEFAULTING to today's exact Anthropic behavior, so
nothing changes unless configured.

The three edges that draft (NEVER judge — the deterministic verifiers/seal are
untouched):
  - api/app.py :: _intake_route   (the work-area router)
  - api/app.py :: _tutor_lesson   (the learn-anything tutor)
  - api/derivation.py :: structure_prose  (the prose->steps formalizer)

All three now call complete(...) here instead of constructing
anthropic.Anthropic(...) directly.

Provider selection (env NH_ORACLE_PROVIDER, default "anthropic") reuses the
EXACT grammar /api/generate-gated already accepts via its base_model param:

    anthropic                 -> AnthropicAdapter  (DEFAULT; NH_BASE_MODEL,
                                 default "claude-sonnet-4-5")
    echo                      -> EchoAdapter       (test/benchmark control)
    openai[:<model>]          -> OpenAICompatibleAdapter (any OpenAI /v1
    ollama[:<model>]             /chat/completions endpoint; LOCAL = sovereign,
    compat[:<model>]             $0; cloud URL = "works with anything").
                                 base_url from NH_OPENAI_BASE_URL
                                 (default http://localhost:11434/v1, Ollama);
                                 model from NH_OPENAI_MODEL (default 'llama3.1')
                                 unless overridden after the colon;
                                 NH_OPENAI_API_KEY optional.
    local[:<model_id>]        -> LocalModelAdapter (on-host weights; from
                                 data/models/registry.json)

Defensive by design: complete() NEVER raises. On any failure (SDK missing, no
key, endpoint unreachable, bad provider string) it returns ok=False with an
error string — exactly the shape each edge already handles to fall back to its
rule-based floor. The deterministic engine never crashes because the oracle is
down.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

# The adapters and the canonical Anthropic pricing constants live in
# generate_gated; reuse them so there is ONE definition of each, not a copy.
from api.generate_gated import (
    AnthropicAdapter,
    EchoAdapter,
    OpenAICompatibleAdapter,
    DEFAULT_ANTHROPIC_MODEL,
    DEFAULT_MAX_TOKENS,
    Generation,
)


# Env that selects the provider for the generative edges. Empty/unset ->
# "anthropic" == today's exact behavior. This is the SAME grammar the rest of
# the engine uses (the /api/generate-gated base_model param), so a single
# convention drives the whole system.
ORACLE_PROVIDER_ENV = "NH_ORACLE_PROVIDER"


@dataclass
class OracleResult:
    """What every edge needs back: the drafted text plus token counts for the
    edge's own ledger accounting, or ok=False + error for the fallback path.

    Mirrors the relevant fields of generate_gated.Generation; tokens_in/out let
    each edge keep its existing `ledger_record(source, ti*3e-6 + to*15e-6)`
    accounting byte-for-byte.
    """
    ok: bool
    text: str = ""
    tokens_in: int = 0
    tokens_out: int = 0
    model: str = ""
    cost_usd: float = 0.0
    error: str = ""


def _build_adapter(provider: str, model: str | None = None):
    """Resolve a provider string to a BaseModelAdapter, using the SAME grammar
    /api/generate-gated accepts. Raises on an unknown/unbuildable provider;
    complete() catches and converts to a graceful OracleResult.

    `model` is an OPTIONAL per-call override for the Anthropic default path only:
    one edge (/agent's _call_oracle) passes a per-request model (e.g. haiku). It
    is applied ONLY when the provider resolves to anthropic, so that edge keeps
    its exact default model; the local/openai/compat paths take their model from
    their own grammar (after the colon) or env, as before."""
    name = (provider or "anthropic").strip()
    low = name.lower()

    if low in ("", "anthropic"):
        # DEFAULT: model from NH_BASE_MODEL (default claude-sonnet-4-5), exactly
        # as the edges did before — unless an edge supplies a per-call override
        # (e.g. the /agent oracle's haiku), which only affects this default path.
        if model:
            return AnthropicAdapter(model_id=model)
        return AnthropicAdapter()
    if low == "echo":
        return EchoAdapter()
    if low.startswith("openai") or low.startswith("ollama") or low.startswith("compat"):
        # openai[:model] | ollama[:model] | compat[:model] -> OpenAI-compatible
        # endpoint. A LOCAL server (NH_OPENAI_BASE_URL=http://localhost:11434/v1)
        # is the sovereign $0 path; a cloud URL "works with anything".
        model_id = name.split(":", 1)[1].strip() if ":" in name else ""
        return OpenAICompatibleAdapter(model_id=model_id or None)
    if low.startswith("local"):
        # local[:model_id] -> on-host weights from data/models/registry.json.
        from api.generate_gated import LocalModelAdapter
        from pathlib import Path
        import json as _json
        model_id = name.split(":", 1)[1].strip() if ":" in name else ""
        registry_path = (Path(__file__).resolve().parents[1]
                         / "data" / "models" / "registry.json")
        if not registry_path.exists():
            raise RuntimeError("local provider selected but model registry is empty")
        reg = _json.loads(registry_path.read_text(encoding="utf-8"))
        models = reg.get("models", [])
        if not models:
            raise RuntimeError("local provider selected but no models registered")
        chosen = None
        if model_id:
            for m in models:
                if m.get("id") == model_id:
                    chosen = m
                    break
            if not chosen:
                raise RuntimeError(f"local model not found: {model_id}")
        else:
            chosen = sorted(models, key=lambda m: m.get("registered_at", ""),
                            reverse=True)[0]
        adapter_path_rel = chosen.get("adapter_path", "")
        adapter_path = (Path(__file__).resolve().parents[1] / adapter_path_rel
                        ) if adapter_path_rel else None
        return LocalModelAdapter(
            model_id=chosen["base_model"],
            adapter_path=str(adapter_path) if adapter_path else None,
            backend=chosen.get("backend", "hf"),
        )
    raise RuntimeError(
        f"unknown {ORACLE_PROVIDER_ENV} provider: {name} "
        f"(supported: anthropic, echo, openai[:model], ollama[:model], "
        f"compat[:model], local[:model_id])"
    )


def select_adapter(provider: str | None = None, model: str | None = None):
    """Build the configured adapter (arg overrides env overrides default).
    Exposed for callers/tests that want the adapter object directly.

    `model` is the optional per-call Anthropic-default override (see _build_adapter)."""
    prov = provider if provider is not None else os.environ.get(ORACLE_PROVIDER_ENV, "")
    return _build_adapter(prov, model)


def complete(
    system: str,
    user: str,
    *,
    max_tokens: int = DEFAULT_MAX_TOKENS,
    provider: str | None = None,
    model: str | None = None,
    messages: list | None = None,
    timeout: float | None = None,
    max_retries: int | None = None,
    temperature: float = 0.0,
) -> OracleResult:
    """The single seam. Take a (system, user) pair and return completion text
    plus token counts, via the configured provider.

    DEFAULT path == today's exact Anthropic behavior:
      - provider resolves to "anthropic" (NH_ORACLE_PROVIDER unset/empty)
      - model = NH_BASE_MODEL (default "claude-sonnet-4-5"), unless `model` is
        given (the /agent oracle passes its per-request model, e.g. haiku) —
        the override applies ONLY on the anthropic default path.
      - messages = [{"role":"user","content":user}], system=system
      - timeout / max_retries passed through to the Anthropic client when given
        (the edges set 22-25s, 1 retry); ignored by non-Anthropic adapters.

    `messages`: an OPTIONAL full conversation ([{role,content},...]) used in
    place of the single `user` turn. The Shepherd discernment edge sends the
    whole history; passing it through here keeps the default Anthropic request
    byte-for-byte identical (same multi-turn messages array) while still routing
    through this one seam, so the env flip governs it too. When omitted, `user`
    is sent as the lone user turn exactly as before.

    LOCAL path: set NH_ORACLE_PROVIDER=ollama (or openai/compat) and point
    NH_OPENAI_BASE_URL at a local server — same call, zero external provider.

    NEVER raises. On any failure returns OracleResult(ok=False, error=...), which
    each edge already knows how to handle (fall back to its rule-based floor /
    return its error shape). This keeps the endpoints graceful exactly as before.
    """
    try:
        adapter = select_adapter(provider, model)
    except Exception as exc:  # noqa: BLE001 — never crash the endpoint
        return OracleResult(ok=False, error=f"{type(exc).__name__}: {exc}"[:300])

    # Pass the edge's timeout to WHICHEVER adapter honors it: the Anthropic client
    # (default path, unchanged) AND the OpenAI-compatible adapter (the LOCAL path),
    # so a hung local model fails fast (the edge's 22-25s) instead of blocking the
    # endpoint on the 120s adapter default. max_retries stays Anthropic-only.
    # Adapters ignore opts they don't use.
    opts: dict = {"system": system, "max_tokens": max_tokens, "temperature": temperature}
    if messages is not None:
        opts["messages"] = messages
    if timeout is not None:
        opts["timeout"] = timeout
    if max_retries is not None and getattr(adapter, "name", "") == "anthropic":
        opts["max_retries"] = max_retries

    try:
        gen: Generation = adapter.generate(user, **opts)
    except Exception as exc:  # noqa: BLE001 — graceful, like the edges today
        return OracleResult(ok=False, error=f"{type(exc).__name__}: {exc}"[:300])

    return OracleResult(
        ok=True,
        text=(gen.text or "").strip(),
        tokens_in=gen.tokens_in,
        tokens_out=gen.tokens_out,
        model=gen.model,
        cost_usd=gen.cost_usd,
    )
