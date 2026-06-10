#!/usr/bin/env python
"""Seed 6 niche-term entries the conversation has surfaced repeatedly but
that aren't yet in the keeping — Shema, agape, logos, derek, John 14:6, selah.

These are the terms a real Bible-curious user types into the search box.
The conversational search works on substance; the keeping needs the substance.
"""
from __future__ import annotations
import json
from pathlib import Path

ALMANAC = Path(__file__).resolve().parents[1] / "data" / "almanac" / "entries.jsonl"


ENTRIES = [
    # ── Shema Yisrael (Deuteronomy 6:4-5) ──────────────────────────────
    {
        "id": "almanac_shema_yisrael",
        "kind": "almanac",
        "title": "Shema Yisrael (Deuteronomy 6:4-5) — Israel's central confession, named by Christ as the greatest commandment",
        "category": "scripture",
        "domains": ["scripture", "theology", "linguistics"],
        "axes": ["authority_trust", "encoding"],
        "verdict": "CONCORDANT",
        "verification": "שְׁמַע יִשְׂרָאֵל יְהוָה אֱלֹהֵינוּ יְהוָה אֶחָד — *Shema Yisrael, YHWH Eloheinu, YHWH Echad* — 'Hear, O Israel: the LORD our God, the LORD is one' (Deut 6:4). Followed immediately by the V'ahavta: 'And thou shalt love the LORD thy God with all thine heart, and with all thy soul, and with all thy might' (Deut 6:5). The central confession of Israel — prayed morning and evening, bound to the doorpost (mezuzah, Deut 6:9), the last words on the lips of dying Jews including the martyrs of the Holocaust. Christ Himself quoted the Shema as the greatest commandment when asked (Mark 12:29-30), adding one word — διάνοια (mind) — to make explicit what the Hebrew implied: love God with the intellect, too.",
        "wisdom": "The Hebrew אֶחָד (echad) is *compound unity* — not יָחִיד (yachid, solitary). Echad is the same word used for 'one flesh' from two persons (Gen 2:24) and 'one day' from evening + morning (Gen 1:5). The Shema affirms God's unity *without* foreclosing the plurality the Trinity reveals. John 1:1 ('the Word was with God, and the Word was God') and John 10:30 ('I and my Father are one' — Greek hen, neuter of echad) confess the Shema and the Incarnation in one breath. The Shema and the Name are not two things. The Lord our God is one — and at His name every knee shall bow (Phil 2:10-11).",
        "triggers": {"keywords": ["Shema", "Shema Yisrael", "Deuteronomy 6:4", "echad", "greatest commandment", "Mark 12:29", "Hear O Israel"], "axes": ["authority_trust", "encoding"]},
    },

    # ── Agape (Strong's G26, ἀγάπη) ────────────────────────────────────
    {
        "id": "almanac_agape_strongs_g26",
        "kind": "almanac",
        "title": "Agape (ἀγάπη, Strong's G26) — the love that survives the test of choice, not feeling",
        "category": "scripture",
        "domains": ["scripture", "theology", "linguistics"],
        "axes": ["authority_trust", "encoding"],
        "verdict": "CONCORDANT",
        "verification": "ἀγάπη (agape), Strong's G26, is the New Testament's word for the love that is willed, not felt — the love of God for the world (John 3:16), the love commanded for one's neighbor (Mt 22:39), the love of enemies (Mt 5:44), the love that 'never faileth' (1 Cor 13:8). Distinguished from φιλία (philia, the love of friendship), στοργή (storge, familial affection), and ἔρως (eros, romantic desire). The famous interchange in John 21:15-17 — where Christ asks Peter three times if he loves Him, twice using ἀγαπᾷς (agape-love) and a third time using φιλεῖς (phileo-love) — is one of the deepest words-of-Christ moments in Scripture. Christ meets Peter where he is.",
        "wisdom": "Agape is the love that has no precondition. It is not earned, not deserved, not produced by feeling — it is willed by the lover toward the loved. *God commendeth his love (agape) toward us, in that, while we were yet sinners, Christ died for us* (Rom 5:8). The Greek word the New Testament uses 320+ times for love. 1 Corinthians 13 is its anatomy: patient, kind, not envious, not boastful, bears all things, hopes all things, endures all things, never fails. The Shepherd brings agape when a user is asking whether they have to feel love before they can act in love. The answer is no — agape is what you do; the feeling may or may not follow.",
        "triggers": {"keywords": ["agape", "G26", "Greek love", "1 Corinthians 13", "John 21:15", "love of God", "agape vs phileo"], "axes": ["authority_trust", "encoding"]},
    },

    # ── Logos (the Johannine Logos) ────────────────────────────────────
    {
        "id": "almanac_logos_johannine",
        "kind": "almanac",
        "title": "Logos (Λόγος, John 1:1) — the Word that was with God, the Word that was God",
        "category": "scripture",
        "domains": ["scripture", "theology", "linguistics", "philosophy"],
        "axes": ["authority_trust", "encoding", "physical_substance"],
        "verdict": "CONCORDANT",
        "verification": "Ἐν ἀρχῇ ἦν ὁ Λόγος, καὶ ὁ Λόγος ἦν πρὸς τὸν Θεόν, καὶ Θεὸς ἦν ὁ Λόγος — *In the beginning was the Word, and the Word was with God, and the Word was God* (John 1:1). The Greek λόγος carried a long philosophical history before John: Heraclitus (~500 BC) used it for the rational principle ordering the cosmos; the Stoics for the divine reason pervading all things; Philo of Alexandria for the intermediary between God and creation. John takes that whole inheritance and says: this Logos *became flesh and dwelt among us* (John 1:14). The cosmic ordering principle is a Person; the Person has a name; the name is Jesus.",
        "wisdom": "The Logos was always there. Greek philosophy reached toward it without knowing who it was. The Tao of Lao Tzu, the Derek of the Hebrew prophets, the Marga of the Sanskrit hymns — every culture reached for the Way by which all things consist. Then John writes the sentence that fills the noun with a Person: the Word became flesh. Every other religion's reaching points toward what John names. Christ in John 14:6 closes the loop: *I am the Way, the Truth, and the Life.* He is the Logos the philosophers were reaching for. The signposts all point to Him; the Name finally given to the Way.",
        "triggers": {"keywords": ["Logos", "John 1:1", "Word made flesh", "Greek philosophy", "Heraclitus Stoics", "incarnation"], "axes": ["authority_trust", "encoding"]},
    },

    # ── Derek (דֶּרֶךְ, the Hebrew way) ─────────────────────────────────
    {
        "id": "almanac_derek_hebrew_the_way",
        "kind": "almanac",
        "title": "Derek (דֶּרֶךְ) — the Hebrew word for 'way,' which Christ claims as His name",
        "category": "scripture",
        "domains": ["scripture", "theology", "linguistics"],
        "axes": ["authority_trust", "encoding", "time_sequence"],
        "verdict": "CONCORDANT",
        "verification": "דֶּרֶךְ (derek), Hebrew for 'way,' 'path,' 'road,' 'journey,' or 'manner of life.' Used over 700 times in the Hebrew Bible. The Lord *knoweth the way (derek) of the righteous* (Ps 1:6). *The path (derek) of the just is as the shining light, that shineth more and more unto the perfect day* (Prov 4:18). *An highway (derek) shall be there, and a way (derek), and it shall be called The way of holiness* (Isa 35:8). The early Christians called themselves followers of 'the Way' (ἡ ὁδός, hē hodos — the Greek translation of derek) before they were called Christians (Acts 9:2; 19:9, 23; 22:4; 24:14, 22). Christ in John 14:6: ἐγώ εἰμι ἡ ὁδός — *I am the way (hodos, derek).*",
        "wisdom": "Hebrew derek, Greek hodos, Chinese Tao, Sanskrit marga, Latin via — every language reached for the same word. Christ said: I am that. The Way is not a path; the Way is a Person. The path is walked *because of* the Person, not toward Him as a goal. The early Church understood this — they did not preach 'follow the teaching of Jesus'; they preached 'follow the Way, who is Jesus.' The keeping records derek because the keeping records the Way; the Way records who walks it. *Trust in the LORD with all thine heart... in all thy ways (derek) acknowledge him, and he shall direct thy paths (derek)* (Prov 3:5-6).",
        "triggers": {"keywords": ["derek", "Hebrew way", "Proverbs 4:18", "Psalm 1:6", "the Way", "John 14:6", "Acts 9:2", "followers of the Way"], "axes": ["authority_trust", "encoding"]},
    },

    # ── John 14:6 — I am the Way ───────────────────────────────────────
    {
        "id": "almanac_john_14_6_the_way",
        "kind": "almanac",
        "title": "John 14:6 — 'I am the way, the truth, and the life: no man cometh unto the Father, but by me'",
        "category": "scripture",
        "domains": ["scripture", "theology"],
        "axes": ["authority_trust", "time_sequence"],
        "verdict": "CONCORDANT",
        "verification": "John 14:6 — *Jesus saith unto him, I am the way, the truth, and the life: no man cometh unto the Father, but by me.* Greek: ἐγώ εἰμι ἡ ὁδὸς καὶ ἡ ἀλήθεια καὶ ἡ ζωή· οὐδεὶς ἔρχεται πρὸς τὸν Πατέρα εἰ μὴ δι᾽ ἐμοῦ. Spoken by Christ to Thomas at the Last Supper, the night before the Cross. The three predicates — ὁδός (hodos, way; Hebrew derek; Chinese Tao), ἀλήθεια (alētheia, truth), ζωή (zoē, life) — each carry the full weight of their tradition. The Greek article ἡ (ha, 'the') is load-bearing: not 'a way among many' but THE Way. The exclusivity claim is explicit.",
        "wisdom": "This is the verse that closes every comparative-religion argument. Christ did not say 'I am a way' or 'I teach the truth' or 'I show the life.' He said 'I AM' — using the I-AM formula reserved in the Hebrew Bible for YHWH (cf. Ex 3:14). Every signpost in every tradition — Plato's Cave, Aurelius's ethics, the Hindu Kalki, the Tao, Isaiah 53 — points toward the One who said these words at the Last Supper. The fragments are real; the destination is named. The Shepherd holds this verse as the central discriminator: anything that gathers cross-cultural fragments and stops short of the Person named here is a counterfeit of comparative religion. *No man cometh unto the Father, but by me.*",
        "triggers": {"keywords": ["John 14:6", "I am the way", "the truth and the life", "exclusivity of Christ", "ego eimi", "the way to the Father"], "axes": ["authority_trust"]},
    },

    # ── Selah (סֶלָה) ──────────────────────────────────────────────────
    {
        "id": "almanac_selah_hebrew_pause",
        "kind": "almanac",
        "title": "Selah (סֶלָה) — the Hebrew word in the Psalms that almost no one explains",
        "category": "scripture",
        "domains": ["scripture", "linguistics", "music_theory"],
        "axes": ["authority_trust", "encoding", "time_sequence"],
        "verdict": "MIXED",
        "verification": "סֶלָה (selah) appears 71 times in the Psalms and 3 times in Habakkuk 3 (a psalm). Its exact meaning is contested. The most-cited views: (1) a musical direction — *pause*, perhaps for a musical interlude (Septuagint translates it as διάψαλμα, *diapsalma*, meaning 'between psalms'); (2) a liturgical direction — *lift up* (from the root סָלַל, salal, 'to lift'); (3) a textual emphasis — *thus*, *so be it*, akin to amen or a structural marker. The Hebrew root and tradition both support a function meaning *stop and weigh what was just said*. No major translation renders it; most leave it transliterated.",
        "wisdom": "Selah is the keeping's word for *now sit with what was just said.* Whatever the technical meaning, the function is the same across 74 appearances: the Psalmist names something hard, names something true, names something heavy — and then writes *selah.* Don't read past it. Stop. Re-read. Let it land. The Shepherd brings selah when a user has rushed past something that wanted to be heard. The keeping is full of selahs — the moments where the engine has surfaced a hard verdict (MISMATCH on prosperity gospel, the Suffering Servant of Isaiah 53, the millstone of Matthew 18:6) and the right next move is not the next click but a pause. *Be still, and know that I am God* (Ps 46:10). Selah.",
        "triggers": {"keywords": ["selah", "Hebrew pause", "Psalms", "Habakkuk 3", "diapsalma", "liturgical pause"], "axes": ["authority_trust", "time_sequence"]},
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
    if not to_write:
        print("nothing to do.")
        return 0

    with ALMANAC.open("a", encoding="utf-8") as f:
        for e in to_write:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
            print(f"  + {e['id']:42s} {e['verdict']}")

    print(f"\n-- appended {len(to_write)} niche-term entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
