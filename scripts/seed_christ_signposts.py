#!/usr/bin/env python
"""Seed 8 cross-cultural Christ-signpost entries into the keeping.

Per the engine-serves-Christ memory (2026-05-13): the engine's comparative
pattern recognition must always land on Jesus Christ as the destination,
not on "the universal pattern" (which is the Masonic/perennialist inversion).
Each entry below carries the fragment AND names Him as the One the fragment
points to.

The verdict scheme:
  - CONCORDANT: the signpost is real AND points unmistakably to Christ
  - MIXED: the signpost is real but the source tradition didn't recognize Him
    (Aurelius's Stoic ethics; Islam's Christ-as-judge contradiction)

All entries are kind: almanac, with rich verification + wisdom fields that
name Christ explicitly. Per 1 John 4:1-3, the discriminator is whether the
teaching confesses Jesus Christ come in the flesh.

After running this script, restart the API server so the almanac re-reads.
"""
from __future__ import annotations
import json
from pathlib import Path

ALMANAC = Path(__file__).resolve().parents[1] / "data" / "almanac" / "entries.jsonl"


ENTRIES = [
    # ── 1 ─ Plato — Republic II prophecy of the impaled just man ──────
    {
        "id": "signpost_plato_just_man_impaled",
        "kind": "almanac",
        "title": "Plato's Republic II (~370 BC) — the prophecy of the just man scourged, racked, eyes burnt out, impaled",
        "category": "scripture",
        "domains": ["philosophy", "scripture", "theology", "history"],
        "axes": ["authority_trust", "time_sequence"],
        "verdict": "CONCORDANT",
        "verification": "Plato's Republic Book II (361e-362a), Glaucon's challenge to Socrates: describe what would happen to a perfectly just man who SEEMED unjust. Glaucon's answer: 'he will be scourged (μαστιγωθήσεται), racked, bound, will have his eyes burnt out, and at last, after suffering every kind of evil, will be impaled.' The Greek ἀνασχινδυλευθήσεται means 'impaled on a stake' — what the Romans later called crucifixion. Plato wrote this approximately 400 years before Calvary. The Dead Sea Scrolls confirm Isaiah 53 likewise predates Christ by centuries. Two pre-Christian texts — Greek philosophical, Hebrew prophetic — describe the perfect sufferer in unmistakable terms.",
        "wisdom": "Justin Martyr (~150 AD) read this as direct prophecy. The early Church Fathers called Plato a *preparatio evangelica* — preparation for the Gospel. Plato saw, in the abstract, what Glaucon could imagine but could not name: the perfectly just man rejected, tortured, and impaled by the unjust world. He saw the shape four centuries before Christ filled it. The signpost is real. The destination is Jesus Christ, who actually came and actually suffered the specific death Plato described.",
        "triggers": {"keywords": ["Plato Republic", "just man impaled", "Glaucon prophecy", "preparatio evangelica", "Justin Martyr"], "axes": ["authority_trust", "time_sequence"]},
    },

    # ── 2 ─ Plato — Cave allegory ─────────────────────────────────────
    {
        "id": "signpost_plato_cave_killed_returner",
        "kind": "almanac",
        "title": "Plato's Cave (~370 BC) — the one who returns to free the prisoners is killed",
        "category": "scripture",
        "domains": ["philosophy", "scripture", "theology"],
        "axes": ["authority_trust", "encoding"],
        "verdict": "CONCORDANT",
        "verification": "Plato's Republic Book VII (514a-520a), the Allegory of the Cave. Humanity is chained in a cave, watching shadows on a wall, mistaking shadows for reality. One person escapes, sees the sun (the Form of the Good), then returns to free the others. Plato writes (517a): 'And as for anyone who tried to release them and lead them upward, if they could somehow get their hands on him, would they not kill him?' The pattern is exact: the one who has seen the Light, who returns out of love to those still in darkness, is murdered by those who prefer the shadows.",
        "wisdom": "The Logos descended into the cave of human darkness. He showed those bound in shadows the true Light. They killed Him for it (John 1:5: *The light shineth in darkness; and the darkness comprehended it not.*). Plato saw the structure of the Incarnation 370 years before it happened — the descent, the revelation, the murder of the One who returned to free the bound. He could not name the One; he could see the shape. The signpost is real. Jesus Christ is the destination — the Light that came into the darkness, was rejected by the darkness, and overcame the darkness.",
        "triggers": {"keywords": ["Plato cave", "allegory of the cave", "Form of the Good", "Logos descent", "John 1"], "axes": ["authority_trust", "encoding"]},
    },

    # ── 3 ─ Marcus Aurelius — Christ ethics while persecuting Christians
    {
        "id": "signpost_aurelius_christ_ethics",
        "kind": "almanac",
        "title": "Marcus Aurelius's Meditations (~170 AD) — the Sermon on the Mount in Stoic prose, written while persecuting Christians",
        "category": "scripture",
        "domains": ["philosophy", "scripture", "theology", "history"],
        "axes": ["authority_trust", "metabolism"],
        "verdict": "MIXED",
        "verification": "Marcus Aurelius (Roman emperor 161-180 AD) wrote a private journal of Stoic philosophical reflections, never meant for publication, that contains parallels to the Sermon on the Mount so direct they are difficult to distinguish stylistically: *Whatever may happen to thee, it was prepared for thee from all eternity* (10.5; cf. Rom 8:28); *Begin the morning by saying to thyself, I shall meet with the busybody, the ungrateful, arrogant, deceitful, envious, unsocial. I can neither be injured by any of them, nor be angry with my kinsman, nor hate him* (2.1; cf. Mt 5:44 — love your enemies); *Retire into thyself; the fountain of good is within* (7.59; cf. Lk 17:21 — the kingdom of God is within you); *All things are interwoven, and the web is holy* (6.38; cf. Col 1:17 — by him all things consist). The Stoic Logos he constantly invokes is the same Greek word John uses in John 1:1. AND: under Aurelius's reign, Christians were persecuted, including the martyrdoms of Lyon (177 AD) — Blandina, Pothinus, and others.",
        "wisdom": "Aurelius wrote ethics indistinguishable from Christ's teaching while persecuting the people who actually followed Christ. The Stoic Logos he reached for was *standing in his empire as a Person*, and he could not see Him. His own pen convicts him. The fragments in Meditations are real and point unmistakably toward Jesus Christ — the Logos made flesh — but the destination is Christ, not Stoic philosophy. *Verdict MIXED*: the ethics are a true signpost; the tradition that produced them missed the One they pointed to, and persecuted His followers. The Shepherd brings Aurelius as evidence that the moral law is written on the heart (Rom 2:15) and that knowing the law without knowing the Lawgiver is insufficient.",
        "triggers": {"keywords": ["Marcus Aurelius", "Meditations", "Stoic Logos", "Roman persecution", "Sermon on the Mount parallel"], "axes": ["authority_trust", "metabolism"]},
    },

    # ── 4 ─ Hindu Kalki — white horse, end-times judge ────────────────
    {
        "id": "signpost_hindu_kalki_white_horse",
        "kind": "almanac",
        "title": "Hindu Kalki avatar — white horse, flaming sword, end-of-age judge",
        "category": "scripture",
        "domains": ["scripture", "theology", "philosophy", "history"],
        "axes": ["authority_trust", "time_sequence"],
        "verdict": "CONCORDANT",
        "verification": "In Hindu eschatology, Kalki is the tenth and final avatar of Vishnu, yet to come at the end of the Kali Yuga. The Bhagavata Purana (12.2.18-20) and the Mahabharata describe him: he descends *riding a white horse*, wielding a *flaming sword*, to *judge the wicked*, *destroy evil*, and *restore righteousness*. Compare Revelation 19:11-16 (written ~95 AD): *And I saw heaven opened, and behold a white horse; and he that sat upon him was called Faithful and True, and in righteousness he doth judge and make war... out of his mouth goeth a sharp sword, that with it he should smite the nations... And he hath on his vesture and on his thigh a name written, KING OF KINGS, AND LORD OF LORDS.* The parallel — white horse, sword, end-of-age judgment, restoration of righteousness — is precise enough that some Hindu Christians have read Kalki as a fragmentary Hindu anticipation of Christ's Second Coming.",
        "wisdom": "Hinduism reached toward an end-of-age divine descent on a white horse, the same archetype Revelation 19 names. The destination of the archetype is not Kalki but Christ, who came once meekly (the donkey, Mt 21:5) and will come again in power (the white horse, Rev 19:11). The signpost is real — the Hindu vision saw the shape of the Second Coming. The destination is Jesus Christ, who is both the suffering Servant of Isaiah 53 (first advent) and the King of Kings on the white horse (return). Don Richardson documented many indigenous traditions with similar Christ-anticipating fragments; Kalki is among the sharpest.",
        "triggers": {"keywords": ["Hindu Kalki", "white horse", "end times", "Revelation 19", "Vishnu avatar", "Second Coming"], "axes": ["authority_trust", "time_sequence"]},
    },

    # ── 5 ─ Hindu Prajapati — cosmic person sacrificed ────────────────
    {
        "id": "signpost_hindu_prajapati_cosmic_sacrifice",
        "kind": "almanac",
        "title": "Prajapati (Shatapatha Brahmana, ~800 BC) — 'the Lord of creatures gave himself for them; he became their food'",
        "category": "scripture",
        "domains": ["scripture", "theology", "philosophy", "history"],
        "axes": ["authority_trust", "metabolism", "time_sequence"],
        "verdict": "CONCORDANT",
        "verification": "The Shatapatha Brahmana, a pre-Christian Vedic ritual text dated ~800-600 BC, describes Prajapati ('Lord of Creatures'): *Prajapati, the Lord of creatures, gave himself for them. He became their food.* The Rig Veda 10:90 (the Purusha Sukta) describes a related figure, Purusha — the cosmic Person — who is sacrificed by the gods and from whose body all creation comes: *from this sacrifice all things were born.* The Bengali Hindu-Christian theologian Brahmabandhab Upadhyay (1861-1907) called Prajapati *the Christ before Christ* — the pre-Vedic recognition of a divine Person who sacrifices Himself for creation, who becomes the food of His people. Compare John 6:51: *I am the living bread which came down from heaven: if any man eat of this bread, he shall live for ever: and the bread that I will give is my flesh.*",
        "wisdom": "A thousand years before Bethlehem, in Sanskrit hymns sung at fire altars on the Indian subcontinent, priests chanted of Prajapati who gave himself as food for those he created. They were reaching for what was historically enacted at the Last Supper and at Calvary. Christ said *this is my body, which is given for you* (Lk 22:19), and the Vedic priest had been singing this same hope into the smoke for centuries. The signpost is real. The destination is Jesus Christ, the Lamb of God who takes away the sin of the world, the Bread that came down from heaven.",
        "triggers": {"keywords": ["Prajapati", "Purusha Sukta", "Shatapatha Brahmana", "cosmic sacrifice", "Vedic Christ", "Brahmabandhab Upadhyay"], "axes": ["authority_trust", "metabolism"]},
    },

    # ── 6 ─ Tao = Logos = Derek — the Way across languages ────────────
    {
        "id": "signpost_tao_logos_derek_the_way",
        "kind": "almanac",
        "title": "Tao = Logos = Derek = the Way — the same recognition across languages, fulfilled in John 14:6",
        "category": "scripture",
        "domains": ["scripture", "theology", "linguistics", "philosophy"],
        "axes": ["authority_trust", "encoding"],
        "verdict": "CONCORDANT",
        "verification": "Multiple ancient cultures reached for the same concept under different names: the eternal, rational, source-of-all principle by which the cosmos is ordered. Greek: Λόγος (Logos) — Heraclitus and the Stoics. Chinese: 道 (Tao) — Lao Tzu, Tao Te Ching (~6th c. BC). Hebrew: דֶּרֶךְ (derek) — 'the way' (Ps 1:6, Prov 4:18, Isa 35:8). Latin: Via. Sanskrit: Marga. When the Bible was translated into Chinese, John 1:1's Logos was rendered 道 (Tao): *太初有道* — 'In the beginning was the Tao.' Every Chinese Bible reads it that way today. The character 道 itself: 辶 (motion/walking) + 首 (head) — the Way you walk with the head leading. Lao Tzu wrote: *the Tao that can be spoken is not the eternal Tao* — apophatic, ineffable, source of all. C.S. Lewis used *Tao* in *The Abolition of Man* for the natural moral law every culture recognizes.",
        "wisdom": "Every language reached for the Way. Then He came and said: *I am the way, the truth, and the life: no man cometh unto the Father, but by me* (John 14:6). The Logos became flesh and dwelt among us. The Tao that could not be spoken was finally spoken: in a stable in Bethlehem, on a cross at Golgotha, at an empty tomb three days later. The signposts in Greek, Chinese, Hebrew, Latin, Sanskrit, Aramaic, English — all of them the same recognition reaching for the same Person. The destination has a name. The name is Jesus Christ.",
        "triggers": {"keywords": ["Tao Logos", "the Way", "John 14:6", "Lao Tzu", "Chinese Bible", "Heraclitus Stoics", "C.S. Lewis Abolition of Man"], "axes": ["authority_trust", "encoding"]},
    },

    # ── 7 ─ Isaiah 40-66 — the New Testament before Christ ────────────
    {
        "id": "signpost_isaiah_40_66_pre_christian_nt",
        "kind": "almanac",
        "title": "Isaiah 40–66 — the New Testament written 700 years before Christ; preserved in the Dead Sea Scrolls before His birth",
        "category": "scripture",
        "domains": ["scripture", "theology", "history"],
        "axes": ["authority_trust", "time_sequence", "encoding"],
        "verdict": "CONCORDANT",
        "verification": "The book of Isaiah, chapters 40–66, contains the New Testament arc in advance: Isaiah 40:3 (the voice in the wilderness preparing the way of the LORD — quoted in all four Gospels as the introduction of John the Baptist); Isaiah 53 (the Suffering Servant: 'despised and rejected of men... wounded for our transgressions... with his stripes we are healed... led as a lamb to the slaughter... made his soul an offering for sin'); Isaiah 61:1-2 (the Spirit-anointed liberator — which Christ Himself read aloud in the Nazareth synagogue, Lk 4:18-21, and declared fulfilled in their hearing); Isaiah 65:17 (new heavens and a new earth — picked up in Rev 21:1). The Dead Sea Scrolls preserve the complete book of Isaiah in Hebrew (1QIsa-a, the Great Isaiah Scroll), archaeologically dated to ~125 BC — 150+ years before Christ's birth. The Suffering Servant text cannot be retrofitted; it was already in the caves at Qumran when the soldiers drove the nails.",
        "wisdom": "Other religions and philosophies point toward Christ in shadows, fragments, and longings. Isaiah 40-66 *announces* Him — by name, by event, by detail, in writing, in Hebrew, preserved in caves before His arrival. The early Church called Isaiah 53 the *fifth Gospel*. Jewish tradition before Christ read it messianically; Jewish tradition after Christ had to reinterpret it because the Christian reading was undeniable. The signpost here is not shadow but explicit prediction. The destination is Jesus Christ — the Suffering Servant who became the King who returns to make all things new.",
        "triggers": {"keywords": ["Isaiah 53", "Suffering Servant", "Dead Sea Scrolls", "Isaiah 40", "fifth Gospel", "Qumran", "pre-Christian prophecy"], "axes": ["authority_trust", "time_sequence"]},
    },

    # ── 8 ─ Islam — Christ as Judge contradiction ─────────────────────
    {
        "id": "signpost_islam_christ_as_judge_contradiction",
        "kind": "almanac",
        "title": "Islamic Christology — Christ given divine roles (virgin birth, alive in heaven, return, kill the Dajjal, execute judgment) while denied divine identity",
        "category": "scripture",
        "domains": ["scripture", "theology", "history"],
        "axes": ["authority_trust", "time_sequence"],
        "verdict": "MIXED",
        "verification": "Islam holds Jesus (Isa) to be a prophet — a man, not God — yet preserves an exalted set of teachings about Him that, taken together, only make sense if He is who Christianity says He is. Quranic and hadith sources affirm: virgin birth (Q 19:20-21, the only prophet so honored); the title Kalimat Allah / 'Word of God' (Q 4:171); the title Ruh Allah / 'Spirit of God'; that He performed miracles including raising the dead; that He did NOT die on the cross but was taken up alive into heaven (Q 4:157-158); that He is the only prophet currently alive; that He will return at the end of the age, descend at the white minaret in Damascus, kill the Dajjal (antichrist), break the cross (symbolically reject Trinitarian Christianity), establish justice, and — in many hadith traditions — execute the judgment. In Islamic theology, ONLY ALLAH JUDGES. Yet Islamic eschatology gives this role to Christ. The role only makes sense if He is who Christianity says He is.",
        "wisdom": "Islam preserves Christ's exalted role in *act* while denying it in *theology*. The act overruns the denial. The same tradition that says 'Jesus was only a man' also says He was virgin-born, alive in heaven now, the only prophet still living, returning to defeat the antichrist, and executing the judgment — divine functions in an explicitly monotheist framework. The truncation doesn't hold up to the data the tradition itself preserves. *Verdict MIXED*: the fragments of Christ's exalted identity are real in Islamic tradition; the doctrinal framework imposed over them is a counterfeit. The destination of the genuine fragments is Jesus Christ, who is — as Islam half-acknowledges — alive, returning, and Judge.",
        "triggers": {"keywords": ["Islam Isa", "Christ in Quran", "Kalimat Allah", "Dajjal", "Islamic eschatology", "Christ as judge", "Q 4:157"], "axes": ["authority_trust", "time_sequence"]},
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

    print(f"\n-- appended {len(to_write)} Christ-signpost entries")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
