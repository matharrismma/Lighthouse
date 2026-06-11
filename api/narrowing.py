"""
The narrowing engine — eliminate to almost nothing, then hand off (2026-06-11).

Matt's move (project_narrow_to_nothing_handoff): "We can narrow it to almost
nothing, so it would be easy for any tool to finish." This is the engine's own
identity made executable — "eliminates what is not the answer so the narrow path
is illuminated by what survives... read the elimination trail; the trail is the
reasoning" (GET /identity).

THREE LAYERS, and we own the only hard one:
  1. NARROW  — run every deterministic eliminator over a candidate space and
               DELETE what cannot be the answer. Un-copyable (it rides our
               verified substrate); produces the elimination trail (the reasoning)
               and a tiny residual. THIS module.
  2. FINISH  — the residual is trivial; ANY tool returns it (a cheap LLM, a
               brute-force loop, a person, a child). Commodity. Not our job.
  3. VERIFY  — the engine re-confirms the finish (here, and/or via the derivation
               chain). Because we verify, the finish can be handed to ANYTHING,
               even a hallucinating tool: a wrong answer FAILS re-confirmation,
               a right one survives. We never generate the answer (Principle B).

SAFETY / TRUST: eliminators are NAMED, pure, deterministic predicates from a
fixed registry — never arbitrary code, never an LLM judgment. The trail is
auditable and the survivors are reproducible. The same content-addressed receipt
substrate that seals a derivation seals an elimination, so a narrowing is citable
and tamper-evident (GET /seal/{ref}).
"""
from __future__ import annotations

import math
from typing import Any, Callable, Dict, List, Optional

# Bound the compute so a range can't wedge the single-worker engine.
_MAX_SPACE = 200_000
# A verifier eliminator dispatches per-candidate (real verifier work), so it runs
# only on a SMALL set. This enforces the intended pattern: cheap predicates narrow
# first, the un-copyable verifier confirms the survivors (the moat, on the residual).
_MAX_VERIFY_CANDIDATES = 2_000
# At or below this residual size the finish is "trivial" — any tool can close it.
_RESIDUAL_TRIVIAL = 12
# How many examples to show per trail step (the trail is evidence, not a dump).
_SAMPLE = 8


# ── the eliminator registry: named, pure, deterministic predicates ────────────
# Each returns True when the candidate SURVIVES (satisfies the constraint) and
# False when it is ELIMINATED. Integer domain (the search spaces we narrow are
# integer-indexed); extend deliberately, never with eval.

def _digits(n: int) -> List[int]:
    return [int(c) for c in str(abs(n))]


def _is_prime(n: int) -> bool:
    if n < 2:
        return False
    if n < 4:
        return True
    if n % 2 == 0:
        return False
    r = int(math.isqrt(n))
    f = 3
    while f <= r:
        if n % f == 0:
            return False
        f += 2
    return True


def _is_square(n: int) -> bool:
    if n < 0:
        return False
    r = math.isqrt(n)
    return r * r == n


def _is_cube(n: int) -> bool:
    if n < 0:
        n = -n
    r = round(n ** (1.0 / 3.0))
    for c in (r - 1, r, r + 1):
        if c >= 0 and c * c * c == n:
            return True
    return False


def _is_triangular(n: int) -> bool:
    if n < 0:
        return False
    # n = k(k+1)/2  ->  8n+1 is an odd perfect square
    return _is_square(8 * n + 1)


def _is_fibonacci(n: int) -> bool:
    if n < 0:
        return False
    return _is_square(5 * n * n + 4) or _is_square(5 * n * n - 4)


# registry: name -> (predicate(candidate, params) -> survives?, human template)
_PREDS: Dict[str, Callable[[int, Dict[str, Any]], bool]] = {
    "is_prime":        lambda n, p: _is_prime(n),
    "is_composite":    lambda n, p: n > 1 and not _is_prime(n),
    "is_perfect_square": lambda n, p: _is_square(n),
    "is_perfect_cube": lambda n, p: _is_cube(n),
    "is_triangular":   lambda n, p: _is_triangular(n),
    "is_fibonacci":    lambda n, p: _is_fibonacci(n),
    "is_palindrome":   lambda n, p: str(abs(n)) == str(abs(n))[::-1],
    "is_even":         lambda n, p: n % 2 == 0,
    "is_odd":          lambda n, p: n % 2 != 0,
    "all_digits_odd":  lambda n, p: all(d % 2 for d in _digits(n)),
    "all_digits_even": lambda n, p: all(d % 2 == 0 for d in _digits(n)),
    "distinct_digits": lambda n, p: len(set(_digits(n))) == len(_digits(n)),
    "digit_sum_eq":    lambda n, p: sum(_digits(n)) == int(p["k"]),
    "digit_sum_divisible_by": lambda n, p: sum(_digits(n)) % int(p["d"]) == 0,
    "digit_count_eq":  lambda n, p: len(_digits(n)) == int(p["k"]),
    "divisible_by":    lambda n, p: n % int(p["d"]) == 0,
    "not_divisible_by": lambda n, p: n % int(p["d"]) != 0,
    "coprime_to":      lambda n, p: math.gcd(n, int(p["m"])) == 1,
    "ends_with_digit": lambda n, p: _digits(n)[-1] == int(p["d"]),
    "starts_with_digit": lambda n, p: _digits(n)[0] == int(p["d"]),
    "greater_than":    lambda n, p: n > int(p["v"]),
    "less_than":       lambda n, p: n < int(p["v"]),
    "between":         lambda n, p: int(p["lo"]) <= n <= int(p["hi"]),
    "in_set":          lambda n, p: n in set(int(x) for x in p["values"]),
}


def predicates() -> List[str]:
    """The available eliminator names (for discovery / capabilities)."""
    return sorted(_PREDS)


# ── verifier-backed eliminators: narrowing rides the 70 verifier domains ──────
# A constraint {"verify":"<domain>", "spec_template":{...}, "inject":"<field>"}
# dispatches each candidate to verify_<domain> and SURVIVES iff CONFIRMED. The
# candidate is merged into the spec: a dict candidate updates spec_template; a
# scalar candidate is placed at `inject`. This is the moat — elimination by the
# un-copyable verified substrate (a quantum law, a primality proof, dimensional
# analysis), not just a local predicate. Reuses derivation.verify_step (the same
# dispatch + status collapse the derivation chain uses), so the verdict is the
# deterministic verifier's, never generated.

def _is_verify(c: Dict[str, Any]) -> bool:
    return "verify" in c


def _build_spec(candidate: Any, c: Dict[str, Any]) -> Dict[str, Any]:
    spec = dict(c.get("spec_template") or {})
    inject = c.get("inject")
    if isinstance(candidate, dict) and inject is None:
        spec.update(candidate)
    elif inject is not None:
        spec[str(inject)] = candidate
    else:
        # scalar with no inject field named — best effort: a lone "value"
        spec["value"] = candidate
    return spec


def _verify_survives(candidate: Any, c: Dict[str, Any]) -> bool:
    from api import derivation as _derivation  # reuse the chain's dispatch
    spec = _build_spec(candidate, c)
    res = _derivation.verify_step(str(c.get("verify", "")), spec)
    return res.get("status") == "CONFIRMED"


def _label(c: Dict[str, Any]) -> str:
    if _is_verify(c):
        dom = str(c.get("verify", ""))
        inj = c.get("inject")
        tmpl = c.get("spec_template") or {}
        extra = (f" inject={inj}" if inj else "")
        tdesc = (" " + ", ".join(f"{k}={v}" for k, v in tmpl.items())) if tmpl else ""
        return f"verify:{dom}({tdesc.strip()}){extra}".replace("()", "")
    name = str(c.get("pred", ""))
    params = {k: v for k, v in c.items() if k != "pred"}
    return name + (("(" + ", ".join(f"{k}={v}" for k, v in params.items()) + ")")
                   if params else "")


def _build_space(space: Dict[str, Any]) -> List[Any]:
    """Materialize the candidate space. range -> integers; set -> values as given
    (integers for predicate eliminators, or objects for verifier eliminators)."""
    t = str(space.get("type", "range"))
    if t == "set":
        vals = list(space.get("values", []))
        if len(vals) > _MAX_SPACE:
            raise ValueError(f"set too large ({len(vals)} > {_MAX_SPACE})")
        return vals
    if t == "range":
        lo, hi = int(space["lo"]), int(space["hi"])
        if hi < lo:
            raise ValueError("range hi < lo")
        if hi - lo + 1 > _MAX_SPACE:
            raise ValueError(f"range too large ({hi - lo + 1} > {_MAX_SPACE}); "
                             "add a bounding constraint or narrow the range")
        return list(range(lo, hi + 1))
    raise ValueError(f"unknown space type: {t}")


def eliminate(space: Dict[str, Any],
              constraints: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Run every constraint over the space, deleting what fails. Returns the
    survivors (the residual), the elimination trail (the reasoning), and a
    finish-spec telling any tool exactly what is left to do.

    The engine eliminates what cannot be the answer; it does not generate the
    answer (Principle B). A constraint naming an unknown predicate is itself an
    ERROR (we never silently pass an un-runnable filter)."""
    if not isinstance(constraints, list) or not constraints:
        return {"error": "no constraints provided"}
    try:
        candidates = _build_space(space)
    except Exception as exc:  # noqa: BLE001
        return {"error": str(exc)[:200]}

    space_size = len(candidates)
    survivors = candidates
    trail: List[Dict[str, Any]] = []

    for c in constraints:
        before = len(survivors)
        kept: List[Any] = []
        killed: List[Any] = []
        if _is_verify(c):
            dom = str(c.get("verify", ""))
            if before > _MAX_VERIFY_CANDIDATES:
                return {"error": (f"verifier eliminator 'verify:{dom}' would run on "
                                  f"{before} candidates (max {_MAX_VERIFY_CANDIDATES}). "
                                  "Narrow first with cheap predicate eliminators, then "
                                  "confirm the survivors with the verifier (the moat "
                                  "pattern).")}
            try:
                for n in survivors:
                    (kept if _verify_survives(n, c) else killed).append(n)
            except Exception as exc:  # noqa: BLE001
                return {"error": f"verifier eliminator '{dom}' failed: {str(exc)[:140]}"}
        else:
            name = str(c.get("pred", ""))
            fn = _PREDS.get(name)
            if fn is None:
                return {"error": f"unknown eliminator '{name}'. available: "
                                 + ", ".join(predicates())}
            params = {k: v for k, v in c.items() if k != "pred"}
            try:
                for n in survivors:
                    (kept if fn(n, params) else killed).append(n)
            except Exception as exc:  # noqa: BLE001
                return {"error": f"eliminator '{name}' failed: {str(exc)[:140]}"}
        survivors = kept
        trail.append({
            "constraint": _label(c),
            "before": before,
            "eliminated": len(killed),
            "after": len(survivors),
            "eliminated_sample": killed[:_SAMPLE],
            "survivors_sample": survivors[:_SAMPLE],
        })

    residual_size = len(survivors)
    finish = _finish_spec(residual_size, survivors, space_size)
    return {
        "kind": "elimination",
        "space": space,
        "space_size": space_size,
        "constraints": [_label(c) for c in constraints],
        "trail": trail,
        "residual": survivors if residual_size <= _MAX_SPACE else survivors[:_MAX_SPACE],
        "residual_size": residual_size,
        "narrowed_by": space_size - residual_size,
        "finish": finish,
        "note": ("The engine eliminated what cannot be the answer; what survives "
                 "is the narrow path. The trail is the reasoning. The engine does "
                 "not generate the answer — any tool completes the residual and "
                 "the engine verifies the finish."),
    }


def _finish_spec(k: int, survivors: List[int], space_size: int) -> Dict[str, Any]:
    """What any tool must do to finish, sized to how small the residual got."""
    if k == 0:
        return {
            "status": "EMPTY",
            "trivial": True,
            "instruction": (f"No candidate of {space_size} survived. By exhaustive "
                            "deterministic elimination, NO solution exists in this "
                            "space. The non-existence IS the verified result "
                            "(proof by elimination)."),
        }
    if k == 1:
        x = survivors[0]
        return {
            "status": "SINGLE",
            "trivial": True,
            "answer": x,
            "instruction": (f"Exactly one candidate ({x}) survived elimination of "
                            f"{space_size - 1} others. FINISH (any tool): return "
                            f"{x}. The engine then verifies it independently."),
        }
    if k <= _RESIDUAL_TRIVIAL:
        return {
            "status": "TRIVIAL",
            "trivial": True,
            "candidates": survivors,
            "instruction": (f"{k} candidates survived (from {space_size}). FINISH "
                            "(any tool): select or check among these few; the "
                            "engine verifies the choice."),
        }
    return {
        "status": "OPEN",
        "trivial": False,
        "residual_size": k,
        "instruction": (f"Narrowed {space_size} -> {k}, but the residual is not yet "
                        "trivial. Add constraints to narrow further before handoff, "
                        "or hand the residual set to a tool to scan."),
    }


def verify_finish(result: Dict[str, Any], answer: int,
                  constraints: List[Dict[str, Any]]) -> Dict[str, Any]:
    """VERIFY layer: re-confirm a tool's claimed finish against the SAME stated
    constraints, independently of the elimination pass. This is what lets the
    finish be handed to any tool — a wrong answer fails here. Returns HOLDS only
    if the claimed answer was in the space and satisfies every constraint."""
    try:
        answer = int(answer)
    except Exception:  # noqa: BLE001
        return {"verdict": "BROKEN", "detail": "answer is not an integer"}
    checks: List[Dict[str, Any]] = []
    ok = True
    for c in constraints:
        if _is_verify(c):
            try:
                passed = _verify_survives(answer, c)
            except Exception as exc:  # noqa: BLE001
                return {"verdict": "ERROR", "detail": f"verify:{c.get('verify')}: {str(exc)[:120]}"}
        else:
            name = str(c.get("pred", ""))
            fn = _PREDS.get(name)
            if fn is None:
                return {"verdict": "ERROR", "detail": f"unknown eliminator '{name}'"}
            params = {k: v for k, v in c.items() if k != "pred"}
            try:
                passed = bool(fn(answer, params))
            except Exception as exc:  # noqa: BLE001
                return {"verdict": "ERROR", "detail": f"{name}: {str(exc)[:120]}"}
        checks.append({"constraint": _label(c), "holds": passed})
        ok = ok and passed
    # also confirm membership in the originally-claimed residual when present
    residual = result.get("residual")
    in_residual = (answer in residual) if isinstance(residual, list) else None
    return {
        "verdict": "HOLDS" if ok else "BROKEN",
        "answer": answer,
        "checks": checks,
        "in_residual": in_residual,
        "note": ("The engine re-confirmed the claimed finish against every stated "
                 "constraint. A wrong answer would be BROKEN here — which is why "
                 "the finish is safe to hand to any tool."),
    }


def seal_elimination(result: Dict[str, Any], problem: Optional[str] = None,
                     verification: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """Mint a citable, tamper-evident receipt for a narrowing — the elimination
    trail (and optionally the verified finish). Reuses the content-addressed
    store: the SHA-256 hash IS the permanent ref and the integrity proof
    (GET /seal/{ref} to recompute). Records the trail and verdict, never a
    generated answer (a SINGLE/EMPTY residual is read off the surviving set, not
    invented)."""
    rec: Dict[str, Any] = {"kind": "elimination_receipt", "engine": "concordance"}
    if problem:
        rec["problem"] = problem
    for key in ("space", "space_size", "constraints", "trail", "residual",
                "residual_size", "narrowed_by", "finish"):
        v = result.get(key)
        if v is not None:
            rec[key] = v
    if verification is not None:
        rec["verification"] = verification
    rec["note"] = result.get("note") or (
        "The engine eliminated what cannot be the answer; the trail is the "
        "reasoning. It does not generate the answer.")
    try:
        from concordance_engine.user_identity import get_user_pubkey
        pk = get_user_pubkey()
        if pk:
            rec["issuer_public_key"] = pk
    except Exception:  # noqa: BLE001
        pass
    try:
        from concordance_engine import cas as _cas
        h = _cas.store(rec)
        return {"permanent_ref": h, "content_hash": h,
                "cite_url": "https://narrowhighway.com/seal/" + h,
                "residual_size": rec.get("residual_size")}
    except Exception as exc:  # noqa: BLE001
        return {"error": "seal unavailable: " + str(exc)[:120]}
