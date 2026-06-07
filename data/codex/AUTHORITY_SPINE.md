# The Codex Authority Spine

**Settled doctrine.** Per Matt 2026-05-15 sharpening of the source hierarchy memorialized 2026-05-02.

## The four tiers, in descending authority

### Tier 1 — Words in Red (primary)

The direct words of Jesus Christ in the Gospels. Red-letter content.

- **Always wins on conflict.** Every other tier is interpreted *through* this one.
- The center of the codex. Every chapter that has Words in Red applicable cites them first.
- Source: WEB Bible Layer 0 (canonical text) + 22 PD translations available for parallel reading.

### Tier 2 — The Bible

The canonical 66 books of Scripture (Old and New Testaments together), other than Words in Red.

- Source: WEB Bible Layer 0 + 22 PD translations.
- Hebrew Masoretic substrate via Westminster Leningrad Codex (morphhb).
- Greek New Testament substrate via MorphGNT.
- Latin Vulgate available where relevant.

### Tier 3 — The Disciples + Didache + Church Fathers

Apostolic and post-apostolic writings.

**Composition:**
- **The Disciples themselves** — Paul, Peter, John, Mark, Luke, James, Jude (epistles + Acts narrative)
- **The Didache** — *The Teaching of the Twelve Apostles*, ~1st-2nd century. Named explicitly by Matt 2026-05-15.
- **Direct students of apostles** — Polycarp (John's disciple), Clement of Rome, Ignatius of Antioch, Papias, Barnabas
- **Recognized church fathers** — Augustine, Athanasius, Boethius, Aquinas, others within historic creedal tradition
- **Reformers** when they recover apostolic teaching: Luther, Calvin, Wesley, Edwards (no separate tier; same Tier 3 weight as Augustine)

Already in the substrate as text: Augustine *Confessions* (Pusey), *Imitation of Christ* (Benham), Boethius *Consolation* (James), Ignatius's seven letters, *Martyrdom of Polycarp*, Epistle of Barnabas.

### Tier 4 — Matt's writing (lens, not authority)

M.R. Harris's body of work — the KOA trilogy, Apokalypsis script, Molasses, Root Access (in progress), Tell Me You Got That, Participant-Initiated Risk, sermons, devotionals.

**Explicitly subordinated.** Per Matt 2026-05-15: "My writing is just there to fill in the gaps and show the lens."

- The fiction *illustrates* how Matt reads the canonical material — it does not establish doctrine.
- If the KOA trilogy reads against Words in Red on any matter, the Words in Red win.
- KOA passages appear in the codex as **lens** entries with explicit framing:
  > "M.R. Harris's *The Line* illustrates this teaching when..."
  Never as authority statements.

## Citation grading conventions

Every claim in the codex is graded by tier. The format:

```
**Tier 1 anchor:** [scripture reference] [exact text in WEB] [link to /codex/scripture/<ref>]
**Tier 2 supports:** [list of scripture passages with refs]
**Tier 3 supports:** [Augustine X.Y; Didache ch. N; Polycarp's letter to the Philippians §N; etc.]
**Tier 4 lens:** [M.R. Harris's <work>, ch. N — direct quote where load-bearing]
```

Tier 4 may be omitted from a chapter where no KOA/Apokalypsis/Molasses material illuminates it. Tier 1-3 should always have entries (or the chapter is underbuilt and should be flagged in the gap analysis).

## The codex must NEVER

- Let Tier 4 (Matt's prose) override Tier 1 (Words in Red)
- Silently elevate a denominational confession to Tier 1-3
- Silently elevate a modern theologian above Tier 3
- Cite a Tier 4 passage as if it were authority (always frame as lens)
- Invent a fifth tier ("modern Christian commentary", "contemporary apologetics")

The four tiers are the structure. Matt's selectivity is deliberate and load-bearing.

## How the verifier engine enforces this

The Concordance engine already grades by tier in `verify_scripture_anchors`. Tier 4 (Matt's writing) is excluded from doctrinal verification entirely. When the codex compiler walks the chapter sources, it confirms each citation is correctly tier-tagged before including it.

## Why Words in Red are primary

Matt's framing 2026-05-02 and 2026-05-15: "Jesus's words are the ceiling; everything else is interpreted through that filter."

This isn't an arbitrary choice. It reflects:
- The Gospel-witness primacy in historic Christianity
- The recurring scriptural pattern of God speaking *finally* in His Son (Hebrews 1:1-2)
- Matt's stated theological discernment (he's the operator; this is his project)
- The discipline that prevents pattern-recognition syncretism (see memorialized: "The engine serves Christ, not pattern recognition")

The Words in Red are the ceiling. The codex's structure organizes everything beneath them.
