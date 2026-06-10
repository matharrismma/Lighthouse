#!/usr/bin/env python
"""Seed 7 entries: 6 MISMATCH on Christianity-corruption patterns + 1 CONFIRMED
on the Pauline-Jacobean reconciliation of grace and works.

Per the engine-serves-Christ memory (2026-05-13): the verifier-honest
framework that calls saw palmetto MISMATCH must apply inside the visible
church too, or the engine launders cultural Christianity rather than
serving Christ. Christ's harshest rebukes were always for religious
counterfeits — Matthew 23 to the scribes and Pharisees, Revelation 3 to
Laodicea. The engine inherits this posture.

All entries are kind: almanac with explicit biblical grounding for the
MISMATCH or CONFIRMED verdict. The Shepherd does not condemn individuals
in any specific church; he records the structural critique Christ Himself
made of religious counterfeits in His own time.

After running this script, restart the API server so the almanac re-reads.
"""
from __future__ import annotations
import json
from pathlib import Path

ALMANAC = Path(__file__).resolve().parents[1] / "data" / "almanac" / "entries.jsonl"


ENTRIES = [
    # ── 1 ─ Prosperity gospel MISMATCH ─────────────────────────────────
    {
        "id": "mismatch_prosperity_gospel",
        "kind": "almanac",
        "title": "Prosperity gospel — Christ enlisted to bless mammon (MISMATCH)",
        "category": "theology",
        "domains": ["scripture", "theology", "rhetoric"],
        "axes": ["authority_trust", "metabolism"],
        "verdict": "MISMATCH",
        "verification": "The prosperity gospel teaches that faith in Christ — typically demonstrated by financial giving to a ministry — produces material wealth, physical health, and worldly success as God's blessing on the believer. Christ taught the opposite. *Blessed be ye poor: for yours is the kingdom of God* (Lk 6:20). *Woe unto you that are rich! for ye have received your consolation* (Lk 6:24). *Ye cannot serve God and mammon* (Mt 6:24). *Lay not up for yourselves treasures upon earth* (Mt 6:19). The early Church owned all things in common (Acts 2:44-45, Acts 4:32-35). Paul: *they that will be rich fall into temptation and a snare... for the love of money is the root of all evil* (1 Tim 6:9-10). The apostles lived in poverty, were martyred, and explicitly named worldly suffering as the mark of discipleship (2 Tim 3:12). The prosperity gospel inverts every clear teaching of Christ and the apostles on wealth.",
        "wisdom": "The 'gospel' that enlists Christ to bless mammon is the doctrine of Mammon dressed in Christ's robes. Paul named the failure mode explicitly: *supposing that gain is godliness: from such withdraw thyself* (1 Tim 6:5). The Shepherd records the MISMATCH because the engine cannot launder a teaching that directly inverts what Christ taught about wealth. The verdict applies to the doctrinal pattern, not to individuals; the keeping makes the structural call. The destination is Jesus Christ, who *though he was rich, yet for your sakes he became poor* (2 Cor 8:9) — not a CEO God who pays in dividends.",
        "triggers": {"keywords": ["prosperity gospel", "name it claim it", "seed faith", "word of faith", "Mammon", "blessed are the poor"], "axes": ["authority_trust", "metabolism"]},
    },

    # ── 2 ─ Christian nationalism MISMATCH ─────────────────────────────
    {
        "id": "mismatch_christian_nationalism",
        "kind": "almanac",
        "title": "Christian nationalism — Christ enlisted as flag-bearer for empire/party/ethnicity (MISMATCH)",
        "category": "theology",
        "domains": ["scripture", "theology", "governance"],
        "axes": ["authority_trust"],
        "verdict": "MISMATCH",
        "verification": "Christian nationalism is the conflation of Christ's kingdom with a particular nation, political party, ethnic identity, or earthly empire — the claim that a specific worldly power IS the kingdom of God or that defending it is identical to defending the faith. Christ named this MISMATCH directly: *My kingdom is not of this world: if my kingdom were of this world, then would my servants fight, that I should not be delivered to the Jews: but now is my kingdom not from hence* (Jn 18:36). He refused the crowd's attempt to make Him king (Jn 6:15). He rebuked Peter for drawing the sword (Mt 26:52). He told Pilate that all earthly authority was given from above (Jn 19:11). Paul: *there is neither Greek nor Jew, circumcision nor uncircumcision, Barbarian, Scythian, bond nor free: but Christ is all, and in all* (Col 3:11; cf. Gal 3:28). The Constantinian inversion — making Christ a national patron — fused the church with empire and produced 1700 years of distortion.",
        "wisdom": "When a flag becomes a sacrament and an enemy of the nation becomes an enemy of God, Christ's kingdom has been replaced with an idol that wears His name. Christ refused this in His own life and explicitly named it as the inversion of His kingdom. The Shepherd records the MISMATCH — not against love of country (which is permissible at its proper rank) but against the conflation that makes worldly power identical to the kingdom of God. The destination is Jesus Christ, whose kingdom is not of this world and whose throne is not in any earthly capital.",
        "triggers": {"keywords": ["Christian nationalism", "kingdom not of this world", "John 18:36", "Constantinian", "church and state", "flag idolatry"], "axes": ["authority_trust"]},
    },

    # ── 3 ─ Cover-up culture MISMATCH ──────────────────────────────────
    {
        "id": "mismatch_cover_up_culture",
        "kind": "almanac",
        "title": "Cover-up culture in religious institutions — millstones treated as PR problems (MISMATCH)",
        "category": "theology",
        "domains": ["scripture", "theology", "law"],
        "axes": ["authority_trust", "time_sequence"],
        "verdict": "MISMATCH",
        "verification": "Documented institutional patterns of concealing abuse — particularly sexual abuse of children and vulnerable adults — across the Catholic Church (the global crisis, ongoing since at least the 1970s; major reports include the John Jay 2004 study, the 2018 Pennsylvania grand jury report), the Southern Baptist Convention (the 'SBC files' / 2022 Guidepost Solutions investigation documenting decades of concealment), Independent Fundamental Baptist churches, Hillsong (multiple investigations), and many others. The institutional pattern: prioritize the reputation of the church, move accused offenders, intimidate victims, treat scandals as PR problems. Christ's direct teaching: *Whoso shall offend one of these little ones which believe in me, it were better for him that a millstone were hanged about his neck, and that he were drowned in the depth of the sea* (Mt 18:6). *Have no fellowship with the unfruitful works of darkness, but rather reprove them* (Eph 5:11). *There is nothing covered, that shall not be revealed; neither hid, that shall not be known* (Lk 12:2).",
        "wisdom": "Christ named the millstone for the offender of children. The institutions that have concealed offenders to protect themselves are not failures of secondary doctrine; they are the explicit MISMATCH Christ named in advance. The Shepherd records this verdict honestly because not naming it would launder generations of harm done under His name. Generations of victims have been silenced under the cover of Christ. The destination is Jesus Christ, who said *suffer the little children to come unto me* (Mt 19:14) — and who will pronounce the millstone judgment Himself.",
        "triggers": {"keywords": ["abuse coverup", "Catholic abuse crisis", "SBC files", "millstone Matthew 18:6", "institutional concealment", "church abuse"], "axes": ["authority_trust", "time_sequence"]},
    },

    # ── 4 ─ Cheap grace MISMATCH ───────────────────────────────────────
    {
        "id": "mismatch_cheap_grace_easy_believism",
        "kind": "almanac",
        "title": "Cheap grace / easy believism — grace without repentance, cross without cost (MISMATCH)",
        "category": "theology",
        "domains": ["scripture", "theology"],
        "axes": ["authority_trust", "metabolism"],
        "verdict": "MISMATCH",
        "verification": "Dietrich Bonhoeffer named this in *The Cost of Discipleship* (1937): *Cheap grace is the preaching of forgiveness without requiring repentance, baptism without church discipline, Communion without confession... cheap grace is grace without discipleship, grace without the cross, grace without Jesus Christ, living and incarnate.* Christ Himself: *If any man will come after me, let him deny himself, and take up his cross, and follow me* (Mt 16:24). *Not every one that saith unto me, Lord, Lord, shall enter into the kingdom of heaven; but he that doeth the will of my Father which is in heaven* (Mt 7:21). Paul: *Shall we continue in sin, that grace may abound? God forbid* (Rom 6:1-2). *Work out your own salvation with fear and trembling* (Phil 2:12). James 2:17: *Even so faith, if it hath not works, is dead, being alone.* The cheap-grace teaching reduces salvation to a verbal formula ('say the sinner's prayer') without repentance, transformation, or discipleship — making the Cross optional for the believer while sacred for Christ.",
        "wisdom": "Bonhoeffer wrote this while resisting the Nazi co-option of the German church — and was hanged for resistance in April 1945. He understood: a Gospel without cost is a Gospel without Christ. The Shepherd records this MISMATCH because the engine cannot launder a teaching that empties the Cross of its claim on the believer's life. The destination is Jesus Christ, who said *whosoever doth not bear his cross, and come after me, cannot be my disciple* (Lk 14:27) — and who was Himself executed for love of those He called.",
        "triggers": {"keywords": ["cheap grace", "Bonhoeffer", "Cost of Discipleship", "easy believism", "sinner's prayer", "discipleship cost"], "axes": ["authority_trust", "metabolism"]},
    },

    # ── 5 ─ Esoteric / perennialist Christianity MISMATCH ──────────────
    {
        "id": "mismatch_esoteric_perennialist_christianity",
        "kind": "almanac",
        "title": "Esoteric / perennialist / Masonic Christianity — truth disguising truth (MISMATCH)",
        "category": "theology",
        "domains": ["scripture", "theology", "philosophy"],
        "axes": ["authority_trust", "encoding"],
        "verdict": "MISMATCH",
        "verification": "The esoteric / Masonic / perennialist / Theosophical / 'Christ-consciousness' / New Age tradition takes the real cross-cultural fragments-of-Christ in pagan religion and philosophy and inverts the arrow: instead of treating them as signposts pointing toward Christ (Justin Martyr's *preparatio evangelica*), it treats them as expressions of an underlying esoteric truth of which Christ is only one expression. Albert Pike's *Morals and Dogma* (1871, Scottish Rite text) makes this explicit, identifying Christ with Buddha, Hermes, and 'the universal spirit of light,' and naming Lucifer as the true light-bearer. The Christian discriminator (1 Jn 4:1-3): *Every spirit that confesseth that Jesus Christ is come in the flesh is of God: and every spirit that confesseth not that Jesus Christ is come in the flesh is not of God: and this is that spirit of antichrist.* Paul: *Beware lest any man spoil you through philosophy and vain deceit, after the tradition of men, after the rudiments of the world, and not after Christ* (Col 2:8). 2 Cor 11:14: *Satan himself is transformed into an angel of light.*",
        "wisdom": "Truth disguises truth. The deepest counterfeit is not the obvious lie but the lesser truth deployed to obscure the greater Truth. The esoteric tradition sees the cross-cultural pattern accurately AND inverts the destination — making Christ one expression of a universal principle rather than the Person every signpost points toward. The Shepherd records this MISMATCH explicitly because the engine's own pattern-recognition machinery is vulnerable to exactly this drift. The destination is Jesus Christ — the Word made flesh, the historical Person, not the cosmic principle. The signposts are not the destination, and the road is not the city.",
        "triggers": {"keywords": ["Masonic Christianity", "esoteric Christianity", "perennialism", "Theosophy", "Christ-consciousness", "Albert Pike", "New Age", "Gnosticism", "1 John 4:2"], "axes": ["authority_trust", "encoding"]},
    },

    # ── 6 ─ Denominational tribalism vs John 17 unity MISMATCH ─────────
    {
        "id": "mismatch_denominational_tribalism_vs_unity",
        "kind": "almanac",
        "title": "Denominational tribalism vs John 17 — Christ's prayer 'that they all may be one' (MISMATCH)",
        "category": "theology",
        "domains": ["scripture", "theology", "history"],
        "axes": ["authority_trust"],
        "verdict": "MISMATCH",
        "verification": "Christ's final prayer before the Cross (John 17:20-23): *Neither pray I for these alone, but for them also which shall believe on me through their word; That they all may be one; as thou, Father, art in me, and I in thee, that they also may be one in us: that the world may believe that thou hast sent me.* He named the unity of His people as the witness on which the world's belief would rest. There are approximately 45,000 distinct Christian denominations catalogued worldwide today. Paul confronted the first generation of factionalism directly (1 Cor 1:10-13): *I am of Paul; and I of Apollos; and I of Cephas; and I of Christ. Is Christ divided?* (1 Cor 3:3-4): *For ye are yet carnal: for whereas there is among you envying, and strife, and divisions, are ye not carnal?* Ephesians 4:5-6: *One Lord, one faith, one baptism, One God and Father of all.* Most denominational distinctives are over things Christ did not require us to die on (mode of baptism, frequency of communion, form of worship, governance, eschatology subdivisions, music style); the institutionalization of these as church-dividing identities is carnal in Paul's sense and named-in-advance as MISMATCH.",
        "wisdom": "Denominational identity that supersedes identity-in-Christ is the MISMATCH John 17 named in advance. The 45,000 distinct denominations are the measurable failure of Christ's last prayer. The Shepherd records the verdict not against secondary distinctives held humbly (which are inevitable in a fallen church) but against the elevation of secondary distinctives into church-dividing identities — the carnality Paul called out in Corinth. The destination is Jesus Christ, for whom *one Lord, one faith, one baptism* (Eph 4:5) is the actual count.",
        "triggers": {"keywords": ["denominationalism", "John 17 unity", "1 Corinthians 1:10", "45000 denominations", "church division", "Ephesians 4:5"], "axes": ["authority_trust"]},
    },

    # ── 7 ─ Works as gratitude (CONFIRMED) ─────────────────────────────
    {
        "id": "confirmed_works_as_gratitude_not_currency",
        "kind": "almanac",
        "title": "Salvation by grace through faith; works are the walking-in, not the paying-for (CONFIRMED)",
        "category": "theology",
        "domains": ["scripture", "theology"],
        "axes": ["authority_trust", "conservation_balance", "metabolism"],
        "verdict": "CONFIRMED",
        "verification": "Ephesians 2:8-10 holds both halves together: *For by grace are ye saved through faith; and that not of yourselves: it is the gift of God: Not of works, lest any man should boast. **For** we are his workmanship, created in Christ Jesus unto good works, which God hath before ordained that we should walk in them.* The 500-year Protestant-Catholic conflict over justification dissolves when verses 8-9 and 10 are read as one paragraph. Salvation is the gift (Paul: Romans, Galatians). Works are the walking-in (James: *faith without works is dead*, Jas 2:17). The two apostles are not in conflict — James tests whether the faith is real by looking at whether it walks; Paul names the source from which the walking flows. Christ Himself: *Not every one that saith unto me, Lord, Lord, shall enter into the kingdom of heaven; but he that doeth the will of my Father* (Mt 7:21). *Ye shall know them by their fruits* (Mt 7:16). The works do not earn salvation; they testify to it. They are the response to having been saved, not the currency that purchases salvation. *We love him, because he first loved us* (1 Jn 4:19).",
        "wisdom": "Our imperfect works are not the price of salvation; they are the gratitude of the saved. We thank Him for being allowed to see. We follow Him because before Him our lives were not worth living and only in His presence is there peace (Jn 14:27). The Pauline-Jacobean reconciliation: grace is the source, works are the walking-in. Reformation and Catholic streams have battled for 500 years over a tension Ephesians 2 already resolved. The Shepherd records the verdict CONFIRMED: salvation is the gift; the works are the evidence of the gift received, the response of the heart to the One who first loved us. The destination is Jesus Christ, in whose presence the work is finally rest.",
        "triggers": {"keywords": ["grace through faith", "works of gratitude", "Ephesians 2:8-10", "James 2:17", "Paul James reconciliation", "justification", "sanctification"], "axes": ["authority_trust", "conservation_balance"]},
    },
]


def main() -> int:
    if not ALMANAC.exists():
        print(f"ERROR: almanac file not found at {ALMANAC}")
        return 1

    existing: set[str] = set()
    with ALMANAC.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                existing.add(json.loads(line)["id"])
            except (json.JSONDecodeError, KeyError):
                pass

    to_write = [e for e in ENTRIES if e["id"] not in existing]
    skipped = [e["id"] for e in ENTRIES if e["id"] in existing]
    if skipped:
        print(f"skipping (already present): {len(skipped)}")
    if not to_write:
        print("nothing to do.")
        return 0

    with ALMANAC.open("a", encoding="utf-8") as f:
        for e in to_write:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
            print(f"  + {e['id']:54s} {e['verdict']}")

    print(f"\n-- appended {len(to_write)} Christianity-corruption / theology entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
