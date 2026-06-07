# The user layer — one funnel, three shelves

> Matt 2026-06-07: "We need a single funnel for the user to input. We want them
> to use the tools to organize their life. Many cards should remain with the
> user and be for their use. Some may go to a public shelf. Others may end up in
> our knowledge bank."

The engine was built as **our** knowledge bank (the Codex — everything public,
engine/operator-authored). This layer makes it **also the user's tool to organize
their own life**: one place to put things in, the tools to arrange them, and a
clear path for the few that should be shared or verified. The standing test for
every part: *would a Christian mother actually use this Tuesday afternoon?*

## The shape

```
                        ┌─────────────────────────┐
   one input  ───────▶  │   THE FUNNEL (capture)  │   classify + route
   (type / speak /      └────────────┬────────────┘   (uses floor.classify)
    paste / upload)                  │ creates a card
                                     ▼
                         owner = you · visibility = PRIVATE  ◀── default
                                     │
                 organize with the tools (decks: family, recipes,
                 prayer, calendar, journal, verify, walks …)
                                     │
        ┌────────────────────────────┼────────────────────────────┐
        │ stays MINE                  │ you PUBLISH                 │ rises to the BANK
        ▼                             ▼                             ▼
   private shelf                 public shelf                  knowledge bank (Codex)
   (yours only)                  (visibility=public,           (witnessed + promoted;
                                  you control)                  the gate controls, not you)
```

## The three destinations (and who controls each transition)

| Shelf | What it is | Visibility | Who moves it there |
|---|---|---|---|
| **Mine** | the user's own cards — their week, recipes, prayers, notes, questions | `private` | **the funnel** (on create — default) |
| **Public** | what the user chooses to share | `public` | **the user** (a publish toggle) |
| **Bank** | verified, shared knowledge — the Codex/Almanac | `public` + witnessed | **the gate** (witness/four-gate + operator) — never the user alone |

Three rules:
1. **Private by default.** A new card is the user's and stays theirs until they act.
2. **The user controls private↔public.** Publishing is their choice; un-publishing too.
3. **Only the gate admits to the bank.** A card earns the bank by passing the witness
   gate (two or three witnesses + the four gates). Author credited; it becomes shared
   knowledge, not just the user's. This path already exists (`promotion`/`witnesses`).

## Card ownership (the missing foundation)

Today every card is `visibility: public` with no `owner`. We add:
- `owner`: the user's identity (we already have `user_identity` / pubkeys).
- default `visibility: private` for user-created cards (engine/curated bank cards stay public).
- access rule: private cards are served **only to their owner**; never in public
  listings, the public Atlas, search, or the substrate. Owner-gated.

This is the foundation — without an owner, a "single funnel" just makes more public
cards. Ownership first, then the funnel, then the publish/propose transitions.

## The single funnel

One input replaces the six scattered endpoints today (`/capture`, `/submit`,
`/journal/write`, `/notes`, `/scribe`, `/stacks`). The funnel:
1. takes free input (type / speak / paste / upload),
2. **classifies + routes** it (reuse `floor.classify` / the deterministic dispatcher)
   to the right card kind + deck — a recipe to recipes, a prayer to the prayer board,
   a task to the calendar, a claim to verify, a note to notes,
3. creates the card **owned, private**,
4. hands it to the right tool to organize.

The old endpoints become internal sinks behind the one funnel, not separate doors.

## How it maps to what exists

- **Bank = the Almanac/Codex** (the convergence): the witnessed cards are the entries
  the Atlas maps and the original-language rule annotates.
- **Witness gate = the bank door** — already built.
- **Decks/tools = how the user organizes their private shelf** (the existing decks).
- **Card-dev board** gains a second axis: development stage × ownership (mine/public/bank).
- **Feedback loop** (thumbs/flags) applies to public + bank cards, not private ones.

## What to build (in order)

1. **Ownership** — `owner` + default-private + owner-gated access. (foundation)
2. **The single funnel** — one input → classify/route → private card.
3. **Publish toggle** — user flips a card private↔public.
4. **Propose-to-bank** — surfaces a public card to the witness gate (gate decides).

Privacy is load-bearing: a private card is the user's alone. If we ever can't
guarantee that, we don't ship the funnel.
