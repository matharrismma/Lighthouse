# Pre-traffic security gate -- /derivation/verify

The load-bearing gate before driving agent traffic to the public, sympy-backed verification
endpoint. This is a **review checklist for the operator** -- the live web server is not in this
repo's `src/` (it runs on the deploy host), and the standing rule is to not probe or alter the live
endpoint. Confirm each item against the actual server code/config; do not load-test or attack the
live service to "check."

## 1. Safe expression parsing (highest priority)

A public endpoint that turns user strings into math is the classic injection surface.

- Confirm expressions are parsed with **`sympy.parsing.sympy_parser.parse_expr`** (or an equivalent
  restricted parser), **never** `eval`, `exec`, or a bare `sympify` on attacker-controlled input
  with default settings. `sympify`/`eval=True` paths can be coerced into evaluating arbitrary Python.
- Pass a **restricted local namespace** (only the symbols/functions you intend: the math you support)
  and reject inputs containing `__`, attribute access (`.`), `lambda`, or import-like tokens.
- Treat `variables` (the JSON object in equality/inequality params) the same way -- it is
  attacker-controlled.

## 2. Input size limits (DoS guard)

- Cap **expression length** (e.g. a few thousand chars) and reject longer.
- Cap **steps per request** (e.g. <= 64) and total request body size.
- Reject deeply nested / pathological expressions before handing them to sympy.

## 3. Compute / time limits (DoS guard)

- sympy can hang or blow up memory on hostile inputs (huge `factorial`, deep symbolic
  integrals/limits, enormous integer powers like `9**9**9`). Enforce a **per-step wall-clock
  timeout** and a memory cap, in a worker that can be killed. (The README already notes a per-claim
  wall-clock budget for the CS verifier -- confirm the math/derivation path has the same.)
- Disallow or bound extreme integer/`**` operations that are not timed out by simplification.

## 4. Rate limiting

- Per-IP and/or per-token rate limit on `POST /derivation/verify`. Without it, one client can
  saturate the sympy workers.
- **Separate, stricter limit on `seal: true`** -- sealing mints a permanent public record, so it is
  an amplification/storage-abuse vector. Rate-limit seal minting harder than plain verification.

## 5. CORS (scoped, read-only intent)

- Agents need cross-origin access, so CORS must allow the verify/seal/identity/capabilities reads.
  Keep it **scoped to those endpoints**; the engine should not expose a broad cross-origin *write*
  surface beyond the intended verify+seal.

## 6. Seal-registry integrity

- The value of a seal is that it cannot be forged. Confirm seals are **signed** (the `/seal/<hash>`
  record already returns `issuer_public_key` and `integrity_verified` -- good) and that the public
  key + verification method are documented so third parties can check a seal without trusting the
  service. This is also the foundation of the `.org` notary layer (see ORG_NOTARY_REGISTRY.md).

## 7. Observability

- Log rejected/oversized/timed-out requests (counts, not payloads) so abuse is visible. Alert on
  sustained rate-limit hits.

## Bottom line

Items 1-3 are the must-haves before any public promotion (they prevent code execution and
denial-of-service). 4-5 prevent saturation and scope creep. 6-7 protect the trust asset and give
visibility. None of this changes the verifier's correctness (the 52/52 adversarial benchmark stands)
-- it protects the service that hosts it.
