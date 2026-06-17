# The Companion — one tool, made of reusable chunks

Not a pile of subsystems. One companion that answers to whatever you bring — tutor,
assistant, sounding board, advisor — assembled from a small set of chunks used in many
instances. This is the architecture that emerged, written down so we build *with* it
instead of adding a new tool each time.

## The one principle

> You don't build a new subsystem for each thing. You have chunks of useful code used in
> various instances. We find them and compose them.

Fractals repeat: the same forms recur across every domain, so the same chunks serve every
feature. Below is the chunk inventory and how the surfaces compose them.

## The chunks (found, reused)

| Chunk | What it is | Used in |
|---|---|---|
| **Intake router** | one classifier reads what you bring -> an intent + the artifact (`/workspace/intake`; the rule-based `floor.classify` is the offline fallback) | the work area; routes verify/list/draft/note/ask/open |
| **The engine** | 64 deterministic verifiers + the four gates + the content-addressed seal | every claim that can be checked; the proof; the seal viewer |
| **Curriculum schema** | one shape — `rule / examples / modes / wedges / check / track` | all 7 subjects (phonics, reading, writing, math, science, social studies, bible) |
| **Teaching moves (wedges)** | a leveled catalog of scaffolds — Repeat, Echo, Chunk, Phonics, Context, Skip, Meaning, Praise (+ math: Count-on, Ten-frame, Doubles) | every lesson, every subject (`data/wedges/catalog.jsonl`) |
| **Gradual release (modes)** | model -> together -> you do | every lesson |
| **Interaction chunks** | the per-domain practice: segment->sound->blend for reading words; the ten-frame for math; tap-to-hear cards for other facts | the tutor, keyed by subject |
| **Graph renderer** | draws any node/edge set as a glowing network | the brain (the engine's real structure); reusable for any map |

## The surfaces (composed from the chunks)

- **The work area** (`/`) — the front door. Bring anything; the intake router routes it; the
  engine verifies what's verifiable; the assistant drafts the rest; it's kept on-device. Asking
  to learn something hands off to the tutor.
- **The tutor** (`/read`) — the curriculum schema + interaction chunks + the wedges/modes,
  over all 7 subjects from `/curriculum`. Plus **learn anything** (`/tutor/lesson`): the
  assistant drafts a lesson on any topic in the same schema. Deep-linkable —
  `/read.html?topic=...` drafts that lesson on arrival, so the work area can route you straight in.
- **The brain** (`/brain`) — the graph renderer over the real 1,684-node map.
- **The story** (`/enter`) — what this is, once.

Tutor, assistant, advisor, sounding board are not separate surfaces — they are the work
area answering to what you bring.

## The laws (non-negotiable)

1. **The engine VERIFIES; the assistant only DRAFTS.** Deterministic verdict + seal for
   the checkable; honest "drafted, not verified" for the rest. Never blur the two.
2. **Conduit, not source.** The tool surfaces, attributes, points — it does not author truth.
3. **Curate, not filter.** Pull the world *in* (the assistant drafts from outside; the engine
   vouches where it can) rather than walling it off. A window, not a wall.
4. **Point to Christ; never be an idol.** Genuinely useful and *not* preachy on ordinary
   questions; but on matters of ultimate weight, point to Christ, Scripture, prayer, and real
   people (pastor, church, crisis help) — say plainly the wisdom is in Him, not the tool;
   never pose as God, savior, or final authority. (`api/app.py` `_INTAKE_SYS`/`_LESSON_SYS`;
   guarded by `tests/test_companion_guardrail.py`.) See
   [[feedback_companion_points_to_christ_not_idol_2026-06-16]] in operator memory.
5. **Decrease.** Success = the person freer, nearer to Christ and real community, needing the
   tool *less* — not more (John 3:30). The opposite of the engagement metric.

## Honest state (build vs seed)

- **Real now:** the work area routes + does the everyday things; the tutor teaches 7 subjects
  + drafts a lesson on anything; the engine verifies + seals; the anti-idol guardrail is live
  and tested; everything kept on-device (private, nothing tracked).
- **Seed / next:** content is thin (~69 curriculum units); "curate" is labelled-honest but the
  engine doesn't yet *seal* a lesson's checkable claims; the gated organ (`run_gated`) still
  needs the same anti-idol guardrail; the shared work-area isn't yet embedded on *every* page.
  (Done since first writing: the ten-frame math chunk; the browsable kept shelf at `/kept`;
  the work-area -> tutor learn hand-off.)

The next honest moves are composition, not new subsystems: seal a lesson's checkable claims
through the engine; carry the same anti-idol guardrail into the gated organ; embed the work
area on every page.
