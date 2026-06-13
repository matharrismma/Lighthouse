# Put the verifier where agents work: ChatGPT Action / Custom GPT

The single biggest "be found by agents" lever. Two on-ramps:

- **MCP (already live):** MCP-capable clients connect to `https://narrowhighway.com/mcp` -- no setup here.
- **ChatGPT Custom GPT + Action (this doc):** wraps the public verify endpoint as a GPT tool so any
  ChatGPT user can verify derivations and get permanent seals inside a conversation.

Everything below is **prepared**; the steps marked (OPERATOR) need Matt's ChatGPT account or a
live deploy and are his to trigger.

## Prerequisites -- BOTH NOW LIVE (deployed 2026-06-13)

1. **Focused spec -- LIVE** at `https://narrowhighway.com/openapi-derivation.json` (OpenAPI 3.0.3,
   4 ops: verifyDerivation, getSeal, getIdentity, getCapabilities -- matches the GPT instructions
   below). ChatGPT Actions cap operations (~30) and choke on huge schemas, so do NOT use the
   auto-served `/openapi.json` (471 paths). (A broader agent spec also exists at
   `/openapi-actions.json` if you ever want the full agent API instead.)
2. **Privacy policy -- LIVE** at `https://narrowhighway.com/privacy.html` (conservative; an HTML
   comment in the file notes two optional refinements -- logging specifics + a direct contact --
   you can fill anytime; it reads cleanly as-is).

Only the GPT creation itself (below) needs your ChatGPT account.

## Build the Custom GPT (OPERATOR -- needs your ChatGPT account)

1. ChatGPT -> **Explore GPTs** -> **Create** -> **Configure**.
2. **Name:** `Concordance Verifier`  (or `Narrow Highway Verifier`).
3. **Description:** `Machine-checks a derivation step by step and returns a permanent, independently-checkable receipt. Catches hallucinated math; proves what holds.`
4. **Instructions:** paste the block in the next section.
5. **Actions** -> **Create new action** -> **Import from URL** -> `https://narrowhighway.com/openapi-derivation.json`.
6. **Authentication:** `None` (the verify endpoint is public and read-only; sealing mints a public
   record -- see privacy).
7. **Privacy policy:** `https://narrowhighway.com/privacy.html`.
8. Save -> test with a true claim and a false one (below) -> **Publish** (Anyone with link, or
   Public to the GPT Store for maximum visibility).

## GPT Instructions (paste verbatim)

```
You are a verification front-end for the Concordance Engine (https://narrowhighway.com).
Your job is to PROVE claims, never to assert them on trust.

- Whenever the user states a mathematical claim, or you produce a derivation, VERIFY it with the
  verifyDerivation action BEFORE you assert it is true. Break multi-step work into steps and submit
  them together; the whole derivation HOLDS only if every step holds.
- Use mode "equality" for identities (expr_a == expr_b), "inequality" for comparisons
  (lhs op rhs), and "derivative" for d/dvariable of function == claimed_derivative.
- When the user wants proof they can keep or share, set seal=true and give them the
  receipt.cite_url (a https://narrowhighway.com/seal/<hash> page anyone can re-check). Tell them the
  receipt is permanent and public.
- If a step returns BROKEN/MISMATCH, do not paper over it: report the engine's detail (it gives the
  true value), correct the claim, and re-verify.
- Never say a result is verified unless the action returned verdict HOLDS. The engine eliminates and
  seals; it does not generate answers. You are a conduit, not the authority.
```

## Smoke test (after publishing)

- True: "Verify that sin^2(x)+cos^2(x)=1 and seal it." -> expect HOLDS + a cite_url.
- False: "Verify that (a+b)^2 = a^2+b^2." -> expect BROKEN/MISMATCH with the true value.

## Also worth doing (OPERATOR, lower effort)

- List the MCP server in public MCP directories/registries (zero-install discovery for MCP clients).
- Add the GPT link to the site footer + README once published.
