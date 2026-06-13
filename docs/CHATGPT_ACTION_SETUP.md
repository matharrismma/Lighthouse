# Put the verifier where agents work: ChatGPT Action / Custom GPT

The single biggest "be found by agents" lever. Two on-ramps:

- **MCP (already live):** MCP-capable clients connect to `https://narrowhighway.com/mcp` -- no setup here.
- **ChatGPT Custom GPT + Action (this doc):** wraps the public verify endpoint as a GPT tool so any
  ChatGPT user can verify derivations and get permanent seals inside a conversation.

Everything below is **prepared**; the steps marked (OPERATOR) need Matt's ChatGPT account or a
live deploy and are his to trigger.

## Prerequisites (two gated items)

1. **(OPERATOR) Serve the focused spec.** ChatGPT Actions cap the number of operations (~30) and
   choke on huge schemas, so the engine's auto-served `/openapi.json` (471 paths) will NOT import.
   Serve the focused 4-path spec instead -- the repo's `openapi.json` -- at a stable public URL,
   e.g. `https://narrowhighway.com/openapi-actions.json`. (It validates as OpenAPI 3.0.3, 4 paths:
   verifyDerivation, getSeal, getIdentity, getCapabilities.)
2. **(OPERATOR) Privacy policy URL.** Public GPTs with Actions require one. A draft is built at
   `site/privacy.html` -> serve it at `https://narrowhighway.com/privacy` and verify its
   data-handling claims before publishing (see that file's header).

## Build the Custom GPT (OPERATOR -- needs your ChatGPT account)

1. ChatGPT -> **Explore GPTs** -> **Create** -> **Configure**.
2. **Name:** `Concordance Verifier`  (or `Narrow Highway Verifier`).
3. **Description:** `Machine-checks a derivation step by step and returns a permanent, independently-checkable receipt. Catches hallucinated math; proves what holds.`
4. **Instructions:** paste the block in the next section.
5. **Actions** -> **Create new action** -> **Import from URL** -> the served spec URL from
   Prerequisite 1 (or paste the contents of `openapi.json`).
6. **Authentication:** `None` (the verify endpoint is public and read-only; sealing mints a public
   record -- see privacy).
7. **Privacy policy:** the URL from Prerequisite 2.
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
