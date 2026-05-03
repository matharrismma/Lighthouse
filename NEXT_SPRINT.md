# Concordance / Lighthouse — Next Sprint Punch List
**As of:** 2026-05-02 (afternoon)
**Handoff to:** Claude Code

This picks up where the Cowork session left off. The engine is live at narrowhighway.com. Today we added Claude narration, ElevenLabs TTS (Matt's cloned voice), general Q&A with confidence percentage, and wired up the .env. The server is running with all keys loaded.

---

## P0 — Do first (blockers)

**1. Push today's changes to GitHub**
These files changed today and are NOT yet on the repo:
- `api/app.py` — added `/narrate`, `/speak`, `_claude_answer()`, confidence_pct
- `site/index.html` — ANSWERED verdict, confidence badge, audio auto-play
- `.env.example` — new file (safe to push; `.env` itself is gitignored)

GitHub PAT is in memory. Use it to push. DNS blocks `gh auth` on this machine — push via HTTPS with the token embedded in the remote URL.

```bash
git remote set-url origin https://<token>@github.com/matharrismma/Lighthouse.git
git config user.email "mharris.wcs@icloud.com"
git config user.name "matharrismma"
git add api/app.py site/index.html .env.example
git commit -m "Add Claude narration, ElevenLabs TTS, general Q&A with confidence"
git push origin main
```

**2. Apply the README benchmark addition**
Exact markdown is at `C:\Users\hdven\OneDrive\Desktop\README_BENCHMARK_ADDITION.md`. Adds the "Verified at scale" table (91% overall, per-domain numbers) to the repo README. Either paste it via the GitHub web editor or push it through git.

**3. Delete the duplicate `lw/` engine tree (P0 per BIBLE)**
Two engine source trees have diverged and caused real pain:
- `src/concordance_engine/` — newer, canonical
- `lw/01_engine/concordance-engine/src/concordance_engine/` — Apr-27 snapshot, stale

Consolidate to `src/`. The server imports from the installed package, not from `lw/`, so deleting `lw/01_engine/` should be safe — but verify first with a `grep -r "lw/01_engine"` to catch any hard-coded paths before deleting.

---

## P1 — Engine quality (from benchmark)

**4. Fix statistics 32.3% false-positive rate**
This is the highest-leverage engine fix. Pull the 20 false-positive rows from `lw/09_evaluation/benchmark_results.jsonl`, find the common signature, tighten the tolerance or recomputation path in `src/concordance_engine/verifiers/statistics.py`.

**5. Fix mathematics 20% ERROR rate**
SymPy parse failures are crashing instead of returning NOT_APPLICABLE. In `src/concordance_engine/verifiers/mathematics.py` (or wherever the derivative/equality verifier lives), wrap the SymPy calls in try/except and downgrade parse errors to NOT_APPLICABLE so the gate doesn't blow up.

**6. Fix broken test: `tests/test_mcp_tools.py`**
Tries to import `ALL_TOOLS` from `tools.py` but that export doesn't exist — the module exports `TOOLS` (list) and `TOOL_BY_NAME` (dict). Two fixes:
- Quick: add `ALL_TOOLS = {fn.__name__: fn for fn in [...]}` to `tools.py`
- Clean: rewrite the test to dispatch via `call_tool(name, args)`

**7. Fix broken test: `tests/test_canon_validators.py`**
Resolves canon path via `Path(__file__).resolve().parents[3] / "02_canons"` which only works from inside `lw/`. Either parameterize the canon-root or move the test.

---

## P2 — Feature expansion

**8. Ground biblical answers in Layer 0**
Currently `_claude_answer()` relies on Claude's training knowledge for scripture. The server already has `/scripture/{ref}` and `/triangulate` endpoints backed by the WEB Bible + Strong's. Improve biblical Q&A by:
- Detecting when a question is scripture-related
- Looking up relevant verse(s) via the existing verifiers
- Including the verified WEB text in the Claude prompt
This raises confidence from "Claude thinks it knows" to "Layer 0 verified."

**9. Expand nl_to_packet to more claim shapes**
Currently handles: chemistry equations, one-sample t-test, math derivative/equality, dimensional physics, Big-O complexity. Everything else falls to Claude. Add templates for:
- Stoichiometry ratios
- Statistical distributions (chi-square, ANOVA)
- Logic / boolean claims
- Governance/decision claims via natural language (currently requires a JSON packet)

**10. Install server as a Windows Service**
Right now the server dies if the PowerShell window closes or the PC reboots. Fix:
```powershell
# Use NSSM (Non-Sucking Service Manager) or sc.exe
nssm install ConcordanceEngine "C:\Users\hdven\AppData\Local\Python\pythoncore-3.14-64\python.exe" "-m uvicorn api.app:app --host 0.0.0.0 --port 8000"
nssm set ConcordanceEngine AppDirectory "C:\Users\hdven\OneDrive\Documents\Claude\Projects\Lighthouse"
nssm start ConcordanceEngine
```

---

## P3 — Polish

**11. Governance false-negative rate (27.5%)**
The deterministic structural checks are too permissive. Two options:
- Build a separate LLM-judge "rationale alignment" verifier (clearly labeled as LLM-backed)
- Explicitly scope governance to structural-only and surface LLM judgment through the new `_claude_answer()` path

**12. Streaming responses**
Currently the `/discern` endpoint blocks until both the engine AND the Claude narration call complete (~1-3s). Consider:
- Return the gate verdict immediately via streaming or a two-phase response
- Let the explanation arrive as a second chunk
This would make the UI feel much faster on general questions.

**13. Confidence calibration**
The confidence percentage from `_claude_answer()` is self-reported by Claude Haiku. Consider a calibration pass: run 50 known-answer questions, compare reported confidence to actual accuracy, add a correction factor or few-shot examples to the prompt.

---

## Files of interest

- `api/app.py` — main server; all endpoints including `/discern`, `/speak`, `_claude_answer()`
- `site/index.html` — frontend form; handles ANSWERED, PASS/REJECT, confidence badge, audio
- `.env` — API keys (gitignored); has ANTHROPIC_API_KEY, ELEVENLABS_API_KEY, ELEVENLABS_VOICE_ID
- `lw/09_evaluation/RESULTS.md` — full benchmark results + per-domain failure analysis
- `lw/09_evaluation/benchmark_results.jsonl` — raw benchmark rows (pull false-positives from here)
- `Desktop/README_BENCHMARK_ADDITION.md` — exact markdown to add to repo README
- `Desktop/Restart_Concordance_Server.ps1` — restart helper
- `src/concordance_engine/nl_to_packet.py` — the NL parser (add templates here)
- `src/concordance_engine/verifiers/statistics.py` — fix false-positive rate here
