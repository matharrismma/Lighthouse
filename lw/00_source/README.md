# Layer 0 — WORD (Authority Reference)

> *"In the beginning was the Word."* — John 1:1 (WEB)

## What this is

This is the root source layer of the Lighthouse / Concordance Engine.

All domain canons (biology, chemistry, mathematics, governance, etc.) are downstream
calibrations of what is declared here. The Bible is not one input among many — it is
the README. It is the primary source from which all pattern recognition in the engine
was derived.

## The three-layer source architecture

```
┌─────────────────────────────────────────────────────────────┐
│  Layer 0a — ORIGINAL LANGUAGES  (immutable root)            │
│    Hebrew (OT) · Greek (NT) · Aramaic (embedded in Hebrew)  │
│    → openscriptures/morphhb  · morphgnt/sblgnt             │
├─────────────────────────────────────────────────────────────┤
│  Layer 0b — WEB  (locked English translation)               │
│    World English Bible — public domain, no living drift     │
│    → scrollmapper/bible_databases  → web/web.db             │
├─────────────────────────────────────────────────────────────┤
│  BRIDGE — Strong's Concordance  (triangulation key)         │
│    Maps English words → Strong's numbers → original words   │
│    → openscriptures/strongs → original/lexicon/             │
└─────────────────────────────────────────────────────────────┘
```

**Why three layers?** Drift prevention through triangulation.

A claim about scripture must survive alignment at all three layers:
1. Does the WEB (locked English) actually say what the claim asserts?
2. Do the original language words — checked across their full corpus usage — support that reading?
3. Does the interpretation require a meaning the original word's attested range does not support?

If any layer diverges from the claim → drift flagged.

## Folder structure

    00_source/
      source.yaml              ← authority declaration (machine-readable)
      fetch_sources.py         ← one script to download WEB + Strong's
      README.md                ← this file
      web/
        README.md
        web.db                 ← WEB SQLite (downloaded by fetch_sources.py)
      original/
        README.md
        hebrew/                ← morphhb (git clone manually — see original/README.md)
        greek/                 ← MorphGNT (git clone manually — see original/README.md)
        lexicon/
          strongs_hebrew.json  ← H1–H8674 (downloaded by fetch_sources.py)
          strongs_greek.json   ← G1–G5624 (downloaded by fetch_sources.py)
      triangulation/
        __init__.py
        lookup.py              ← ref resolver + Strong's lookup
        drift_check.py         ← interpretation drift detector

## Quick start

**Step 1 — Download WEB and Strong's lexicons (one command):**

    cd lw/00_source
    python fetch_sources.py

**Step 2 — Verify:**

    python -m triangulation.lookup --status
    python -m triangulation.lookup --ref Jn3:16
    python -m triangulation.lookup --ref Gen1:1
    python -m triangulation.lookup --word G26     # agape — love
    python -m triangulation.lookup --word H430    # Elohim — God
    python -m triangulation.lookup --word H2617   # chesed — lovingkindness

**Step 3 — Triangulate a claim:**

    python -m triangulation.drift_check \
      --ref Jn15:2 \
      --claim "branches that don't bear fruit are destroyed" \
      --strongs G142

**Step 4 (optional) — Clone original language texts:**

    git clone https://github.com/openscriptures/morphhb original/hebrew
    git clone https://github.com/morphgnt/sblgnt original/greek

## How this connects to the kernel

The kernel (`03_kernel/the_way_kernel_min.py`) stores scripture refs in entry
records:

    Entry(
        refs=["Jn15:2", "Pr4:23"],
        ...
    )

These ref strings resolve against this layer. The triangulation tools here
are the mechanism by which those refs are verified — not just cited.

## Relationship to domain canons

The domain canons in `02_canons/` (biology, chemistry, mathematics, etc.) are
not parallel to this layer. They are downstream of it. The canons describe how
scriptural patterns manifest in specific domains. When a canon claim is checked,
it traces back to scripture — which traces back here.

```
00_source/  ←  root authority
02_canons/  ←  derived calibrations (downstream)
01_engine/  ←  verification layer (checks claims against both)
```

## License

All source texts here are public domain:
- World English Bible: public domain (ebible.org)
- Strong's concordance: public domain (openscriptures)
- Open Scriptures Hebrew Bible (morphhb): public domain (openscriptures)
- MorphGNT / SBLGNT: public domain (morphgnt.org / sblgnt.com)

No API keys. No subscriptions. Offline-first. Append-only.
