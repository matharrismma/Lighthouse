# Security Policy

The Concordance Engine runs publicly at `https://narrowhighway.com` and as a Python library / MCP server inside other people's environments. Both surfaces have meaningful security implications, and we want to hear about problems early.

---

## Reporting a vulnerability

**Do not open a public GitHub issue for security reports.** Instead:

- Email **mharris.wcs@icloud.com** with subject prefix `[SECURITY]`.
- Or use GitHub's private vulnerability reporting at https://github.com/matharrismma/Lighthouse/security/advisories/new

Please include:

- A clear description of the vulnerability and its impact
- Steps to reproduce (the smallest packet, request, or code snippet that demonstrates it)
- Your assessment of severity
- Whether you want public credit when the fix lands

We will acknowledge within 5 business days, agree on a coordinated-disclosure timeline, and credit you in the release notes when the fix ships (unless you prefer otherwise).

---

## What we treat as in-scope

### Engine layer (`src/concordance_engine/`)

- The CS verifier executes user-supplied Python in a restricted namespace. **Sandbox-escape vulnerabilities are in-scope.** It is not designed for adversarial input, but it should not let a packet reach `__import__`, `open`, `exec`, `eval`, `compile`, or arbitrary file I/O.
- Hash-chain breaks, packet-hash collisions, or any way to make `/ledger/verify` return `valid: true` after tampering.
- Crashes in any verifier from packet content (the engine should never raise to the API; verifiers should always return structured `{status, detail, data}` even for malformed input).
- MCP tool dispatcher accepting unintended arguments or escaping the tool boundary.

### API layer (`api/app.py`, live at `narrowhighway.com`)

- Authentication bypass on `/validate` (the X-Api-Key header should not be skippable).
- Server-side request forgery, path traversal, or any way to reach the host filesystem outside the served directories.
- Cross-tenant data leaks (this currently runs single-tenant, but future multi-tenant modes must isolate ledgers).
- Resource-exhaustion vectors (large packets, deep recursion, slow loris) that take down the public endpoint.
- Information disclosure via error messages or schema responses.

### Layer 0 / Scripture (`lw/00_source/`, `verifiers/scripture.py`)

- Path traversal through scripture-reference resolution (e.g. specially-crafted `ref` arguments).
- Cache-poisoning of the WEB or Strong's lookup tables.
- Memory-exhaustion attacks via word-study queries that match too many verses.

### Tunnel and deployment (`local/`)

- Anything that allows the Cloudflare Tunnel token to be exfiltrated.
- Privilege-escalation paths in the PowerShell scripts (the user runs them as Administrator — they should not write outside `C:\Concordance\` or the repo working folder).

---

## What we treat as out-of-scope

- Reports of "this gate verdict is wrong" — those are protocol disagreements, not security issues. File a normal issue describing the case.
- Theological objections to the gate predicates (RED, FLOOR, BROTHERS, GOD) — these are architectural commitments, not bugs. See `docs/CANON.md`.
- Reports that downloaded models trained on the kit produce poor verdicts — that's a training quality issue. See `training/BASELINE.md`.
- DDoS testing without prior coordination. The public endpoint is one person's desktop. Do not stress-test it without a heads-up.
- Issues in third-party dependencies (sympy, scipy, fastapi, etc.). Report those upstream; we'll pick up the fix when we update.

---

## Sensitive data handling

The engine is offline-first by design. Specifically:

- **No packet content leaves the host process.** Verifiers run locally; no network calls in core validation.
- **The ledger is local.** It is append-only and SHA-256-chained. Anyone with read access to the file has read access to every recorded packet.
- **Scripture references are public.** Looking up `Jn3:16` is not a privacy event.
- **The MCP server is trusted-environment.** It should be exposed only to AI assistants the operator trusts; it executes Python from the CS verifier.

If you find a packet that contains material the operator would not want indexed (PII, secrets, etc.) committed to the public ledger at `narrowhighway.com`, report it to mharris.wcs@icloud.com — we will flag it for review and follow the canon-scope process for ledger handling.

---

## Disclosure timeline

- **Day 0** — vulnerability reported; we acknowledge within 5 business days.
- **Day 1-30** — we work on a fix and a release plan with you.
- **Release day** — fix ships, advisory published, credit (if desired) given.
- **Day 30+** — if a fix isn't possible in 30 days, we publish a workaround and continue working.

For high-severity issues affecting the live endpoint, we may take the public deployment offline temporarily while the fix is staged.

---

## Hall of fame

When the project has security reporters, they are credited here.

*(empty as of 2026-05-01 — be the first.)*
