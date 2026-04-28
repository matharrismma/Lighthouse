# Release Checklist — Concordance v1.0.4 Alpha

Everything below has either been done for you or is the kind of thing only you can do. The "Done" section is the work that's already complete; the "Your moves" section is what's left.

## Done — staged for release

- [x] **Four engine bugs fixed** (statistics tail aliasing, CS test_cases unpacking, governance schema mismatch, wait_window override semantics).
- [x] **Test suite extended and passing** — 64 verifier tests + ~60 engine tests + 4 new regression tests for today's fixes. All pass.
- [x] **Version bumped** — `pyproject.toml` `1.0.3 → 1.0.4`.
- [x] **CHANGELOG entry written** for v1.0.4.
- [x] **Interface pack written** at `outputs/concordance/`: quickstart, glossary, schemas reference, 19-example training set, known issues, decision packet template, worked example.
- [x] **Tester brief, email template, feedback form** written at `outputs/concordance/release/`.
- [x] **Release packet validated through Concordance itself** — RED/FLOOR/BROTHERS passed; GOD held the 24-hour wait, as designed.

## Your moves — only you can do these

**Today (≤30 minutes):**
- [ ] Read `outputs/concordance/release/TESTER_BRIEF.md`. Edit the "How to reach me" line at the bottom — pick one channel (email, Signal, phone) and commit to checking it daily for two weeks.
- [ ] Pick 3–5 testers. Criteria: trusted, candid, will actually return the form, ideally one of them is technical enough to install and run the MCP server. Write their names somewhere.
- [ ] Bundle the package. From the repo root: `tar -czf concordance-v1.0.4-alpha.tar.gz --exclude='__pycache__' --exclude='.git' .` then add `outputs/concordance/` (or use a fresh zip — whichever you prefer).

**Tomorrow (after the GOD wait elapses — ≥24h after you composed the release packet):**
- [ ] Re-run `validate_packet` with the same release packet and `now_epoch` set to current time. Confirm overall PASS. *That PASS is your "approved to ship" stamp.*
- [ ] Send the email template (`TESTER_EMAIL.md`) to each tester, customizing the bracketed line per recipient.

**Optional but strongly recommended:**
- [ ] `git init` the repo. Right now there's no version control — if a tester finds a critical bug, you have no rollback target. `git init && git add -A && git commit -m "v1.0.4 alpha"` takes 30 seconds.
- [ ] Schedule the one-week check-in and two-week feedback review *now* on your calendar. Otherwise they slip.

## Decisions I made on your behalf

You said "figure out the best way; I don't care," so I picked these. Override any of them if you want:

- **Cohort, not public.** A small invited cohort (3–5) returns better feedback than a public alpha. You can go public later; you can't unsend a public release.
- **Two-week window with a one-week check-in.** Long enough for testers to actually use it, short enough that they don't forget.
- **Tarball, not GitHub push.** No git history exists, so the cleanest artifact is a versioned tarball. If you want to put this on GitHub later, that's a separate decision (and `git init` first).
- **No promotional language.** The brief says "alpha" four times. Better to under-promise.

## What the engine is telling you about this release

The release packet you composed earlier today returned QUARANTINE on the GOD gate — "wait 60/86400 seconds." That's a 24-hour cooling-off period before you should enact a mesh-scope decision. The packet itself is sound (RED/FLOOR/BROTHERS all PASS). Sleep on it. Re-run tomorrow. If anything changes in your gut between now and then, that's exactly what the wait is for.
