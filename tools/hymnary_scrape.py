"""Hymnary.org scraper — PD hymn texts + metadata.

Pulls from the curated `text instances` exposed on hymnary.org. We respect their
robots.txt (slow rate, ~1 req/2s) and only fetch text + meter + scripture-ref.
NO audio scraping (Hymnary's audio is mostly licensed user uploads — we render
our own via Piper TTS later if we want sung versions).

Output: site/hymns.json with one entry per acquired hymn:
    {
      "slug": "rock-of-ages",
      "title": "Rock of Ages",
      "author": "Augustus Toplady",
      "year": 1776,
      "meter": "7.7.7.7.7.7",
      "topic": ["atonement", "trust"],
      "scripture": ["1 Cor 10:4", "Isa 26:4"],
      "text": "Rock of Ages, cleft for me, / Let me hide myself in thee...",
      "source_url": "https://hymnary.org/text/rock_of_ages_cleft_for_me_let_me",
      "pd_basis": "PD by year (author died 1778)"
    }

Strict-PD test: only emit hymns where the AUTHOR died before 1900 (so text is
unambiguously PD even under life-plus-70 in any jurisdiction).

Usage:
    python tools/hymnary_scrape.py --seed-list seeds.txt   # explicit URL list
    python tools/hymnary_scrape.py --top 50                # top-50 popular hymns

Standing principle: every hymn passes the same alignment gate as everything
else. We curate; we don't scrape blindly.
"""
from __future__ import annotations
import argparse
import json
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parent.parent
OUT = REPO / "site" / "hymns.json"
RAW_DIR = REPO / "data" / "hymnary_raw"
RAW_DIR.mkdir(parents=True, exist_ok=True)

# A seed of well-known unambiguously-PD hymns (author death pre-1900).
# This is the high-leverage starter pack — the canon-anchored hymnody every
# Christian audience knows. Expand via --seed-list <txt> with one URL per line.
SEED_HYMNS = [
    # title, slug, author, year_first_pub, est_author_death, scripture_anchor, topic, text_kjv-ish
    {
        "slug": "amazing-grace",
        "title": "Amazing Grace",
        "author": "John Newton",
        "year": 1779,
        "author_death": 1807,
        "meter": "8.6.8.6",
        "scripture": ["John 9:25", "Eph 2:8"],
        "topic": ["grace", "conversion", "testimony"],
        "pd_basis": "PD by year (Newton died 1807)",
        "source_url": "https://hymnary.org/text/amazing_grace_how_sweet_the_sound",
        "text": (
            "Amazing grace! How sweet the sound\n"
            "That saved a wretch like me!\n"
            "I once was lost, but now am found,\n"
            "Was blind, but now I see.\n\n"
            "'Twas grace that taught my heart to fear,\n"
            "And grace my fears relieved;\n"
            "How precious did that grace appear\n"
            "The hour I first believed.\n\n"
            "Through many dangers, toils, and snares,\n"
            "I have already come;\n"
            "'Tis grace hath brought me safe thus far,\n"
            "And grace will lead me home."
        ),
    },
    {
        "slug": "rock-of-ages",
        "title": "Rock of Ages",
        "author": "Augustus Toplady",
        "year": 1776,
        "author_death": 1778,
        "meter": "7.7.7.7.7.7",
        "scripture": ["1 Cor 10:4", "Exod 33:22", "Isa 26:4"],
        "topic": ["atonement", "trust", "salvation"],
        "pd_basis": "PD by year (Toplady died 1778)",
        "source_url": "https://hymnary.org/text/rock_of_ages_cleft_for_me_let_me",
        "text": (
            "Rock of Ages, cleft for me,\n"
            "Let me hide myself in Thee;\n"
            "Let the water and the blood,\n"
            "From Thy wounded side which flowed,\n"
            "Be of sin the double cure,\n"
            "Save from wrath and make me pure.\n\n"
            "Not the labor of my hands\n"
            "Can fulfill Thy law's demands;\n"
            "Could my zeal no respite know,\n"
            "Could my tears forever flow,\n"
            "All for sin could not atone;\n"
            "Thou must save, and Thou alone."
        ),
    },
    {
        "slug": "holy-holy-holy",
        "title": "Holy, Holy, Holy! Lord God Almighty",
        "author": "Reginald Heber",
        "year": 1826,
        "author_death": 1826,
        "meter": "11.12.12.10",
        "scripture": ["Rev 4:8", "Isa 6:3"],
        "topic": ["worship", "trinity", "majesty"],
        "pd_basis": "PD by year (Heber died 1826)",
        "source_url": "https://hymnary.org/text/holy_holy_holy_lord_god_almighty_early",
        "text": (
            "Holy, Holy, Holy! Lord God Almighty!\n"
            "Early in the morning our song shall rise to Thee;\n"
            "Holy, Holy, Holy! Merciful and Mighty,\n"
            "God in three Persons, blessed Trinity!\n\n"
            "Holy, Holy, Holy! All the saints adore Thee,\n"
            "Casting down their golden crowns around the glassy sea;\n"
            "Cherubim and seraphim falling down before Thee,\n"
            "Who wert, and art, and evermore shalt be."
        ),
    },
    {
        "slug": "great-is-thy-faithfulness",
        "title": "Great Is Thy Faithfulness",
        "author": "Thomas Chisholm",
        "year": 1923,
        "author_death": 1960,
        "meter": "11.10.11.10",
        "scripture": ["Lam 3:22-23"],
        "topic": ["faithfulness", "providence"],
        "pd_basis": "NOT PD (Chisholm died 1960; under copyright until 2030). SKIP.",
        "source_url": "https://hymnary.org/text/great_is_thy_faithfulness_o_god_my_fathe",
        "text": "[REDACTED — not yet PD]",
        "skip": True,
    },
    {
        "slug": "a-mighty-fortress",
        "title": "A Mighty Fortress Is Our God",
        "author": "Martin Luther",
        "year": 1529,
        "author_death": 1546,
        "meter": "8.7.8.7.6.6.6.6.7",
        "scripture": ["Psa 46"],
        "topic": ["protection", "battle", "reformation"],
        "pd_basis": "PD by year (Luther died 1546)",
        "source_url": "https://hymnary.org/text/a_mighty_fortress_is_our_god_a_bulwark",
        "text": (
            "A mighty fortress is our God,\n"
            "A bulwark never failing;\n"
            "Our helper He, amid the flood\n"
            "Of mortal ills prevailing:\n"
            "For still our ancient foe\n"
            "Doth seek to work us woe;\n"
            "His craft and power are great,\n"
            "And, armed with cruel hate,\n"
            "On earth is not his equal.\n\n"
            "Did we in our own strength confide,\n"
            "Our striving would be losing;\n"
            "Were not the right Man on our side,\n"
            "The Man of God's own choosing:\n"
            "Dost ask who that may be?\n"
            "Christ Jesus, it is He;\n"
            "Lord Sabaoth His Name,\n"
            "From age to age the same,\n"
            "And He must win the battle."
        ),
    },
    {
        "slug": "be-thou-my-vision",
        "title": "Be Thou My Vision",
        "author": "Irish, 8th c. / tr. Mary Byrne (1880)",
        "year": 1905,
        "author_death": 1931,  # Byrne died 1931 → translation PD 2001
        "meter": "10.10.10.10",
        "scripture": ["Psa 119:114", "Eph 1:17-18"],
        "topic": ["vision", "discipleship", "trust"],
        "pd_basis": "PD by year (translation pre-1929; original is 8th-century)",
        "source_url": "https://hymnary.org/text/be_thou_my_vision_o_lord_of_my_heart",
        "text": (
            "Be Thou my Vision, O Lord of my heart;\n"
            "Naught be all else to me, save that Thou art;\n"
            "Thou my best Thought, by day or by night,\n"
            "Waking or sleeping, Thy presence my light.\n\n"
            "Be Thou my Wisdom, and Thou my true Word;\n"
            "I ever with Thee and Thou with me, Lord;\n"
            "Thou my great Father, I Thy true son;\n"
            "Thou in me dwelling, and I with Thee one."
        ),
    },
    {
        "slug": "come-thou-fount",
        "title": "Come, Thou Fount of Every Blessing",
        "author": "Robert Robinson",
        "year": 1758,
        "author_death": 1790,
        "meter": "8.7.8.7 D",
        "scripture": ["1 Sam 7:12"],
        "topic": ["grace", "wandering heart", "ebenezer"],
        "pd_basis": "PD by year (Robinson died 1790)",
        "source_url": "https://hymnary.org/text/come_thou_fount_of_every_blessing",
        "text": (
            "Come, Thou Fount of every blessing,\n"
            "Tune my heart to sing Thy grace;\n"
            "Streams of mercy, never ceasing,\n"
            "Call for songs of loudest praise.\n"
            "Teach me some melodious sonnet,\n"
            "Sung by flaming tongues above;\n"
            "Praise the mount! I'm fixed upon it,\n"
            "Mount of God's unchanging love.\n\n"
            "Here I raise my Ebenezer;\n"
            "Hither by Thy help I'm come;\n"
            "And I hope, by Thy good pleasure,\n"
            "Safely to arrive at home.\n"
            "Jesus sought me when a stranger,\n"
            "Wandering from the fold of God;\n"
            "He, to rescue me from danger,\n"
            "Interposed His precious blood."
        ),
    },
    {
        "slug": "crown-him-with-many-crowns",
        "title": "Crown Him with Many Crowns",
        "author": "Matthew Bridges / Godfrey Thring",
        "year": 1851,
        "author_death": 1894,
        "meter": "6.6.8.6.6.6.8",
        "scripture": ["Rev 19:12"],
        "topic": ["coronation", "Christ enthroned"],
        "pd_basis": "PD by year",
        "source_url": "https://hymnary.org/text/crown_him_with_many_crowns",
        "text": (
            "Crown Him with many crowns,\n"
            "The Lamb upon His throne;\n"
            "Hark! how the heavenly anthem drowns\n"
            "All music but its own;\n"
            "Awake, my soul, and sing\n"
            "Of Him who died for thee,\n"
            "And hail Him as thy matchless King\n"
            "Through all eternity."
        ),
    },
    {
        "slug": "all-creatures-of-our-god",
        "title": "All Creatures of Our God and King",
        "author": "Francis of Assisi / tr. William Draper",
        "year": 1225,
        "author_death": 1933,  # Draper died 1933; translation PD 2003
        "meter": "8.8.4.4.8.8.alleluias",
        "scripture": ["Psa 148"],
        "topic": ["creation", "praise"],
        "pd_basis": "PD by year (translation 1919 pre-1929)",
        "source_url": "https://hymnary.org/text/all_creatures_of_our_god_and_king",
        "text": (
            "All creatures of our God and King,\n"
            "Lift up your voice and with us sing,\n"
            "Alleluia! Alleluia!\n"
            "Thou burning sun with golden beam,\n"
            "Thou silver moon with softer gleam,\n"
            "O praise Him! O praise Him!\n"
            "Alleluia! Alleluia! Alleluia!"
        ),
    },
    {
        "slug": "doxology",
        "title": "Doxology (Praise God from Whom All Blessings Flow)",
        "author": "Thomas Ken",
        "year": 1674,
        "author_death": 1711,
        "meter": "L.M.",
        "scripture": ["Psa 117"],
        "topic": ["praise", "trinity", "benediction"],
        "pd_basis": "PD by year (Ken died 1711)",
        "source_url": "https://hymnary.org/text/praise_god_from_whom_all_blessings_flow_p",
        "text": (
            "Praise God, from whom all blessings flow;\n"
            "Praise Him, all creatures here below;\n"
            "Praise Him above, ye heavenly host;\n"
            "Praise Father, Son, and Holy Ghost. Amen."
        ),
    },
    {
        "slug": "fairest-lord-jesus",
        "title": "Fairest Lord Jesus",
        "author": "Anonymous German, 1677 / tr. Joseph Seiss 1873",
        "year": 1677,
        "author_death": 1904,
        "meter": "5.6.8.5.5.8",
        "scripture": ["Song 5:10-16"],
        "topic": ["beauty of Christ", "love"],
        "pd_basis": "PD by year",
        "source_url": "https://hymnary.org/text/fairest_lord_jesus_ruler_of_all_nature",
        "text": (
            "Fairest Lord Jesus, Ruler of all nature,\n"
            "O Thou of God and man the Son,\n"
            "Thee will I cherish, Thee will I honor,\n"
            "Thou, my soul's glory, joy, and crown.\n\n"
            "Fair are the meadows, fairer still the woodlands,\n"
            "Robed in the blooming garb of spring:\n"
            "Jesus is fairer, Jesus is purer\n"
            "Who makes the woeful heart to sing."
        ),
    },
    {
        "slug": "o-for-a-thousand-tongues",
        "title": "O for a Thousand Tongues to Sing",
        "author": "Charles Wesley",
        "year": 1739,
        "author_death": 1788,
        "meter": "C.M.",
        "scripture": ["Psa 35:28"],
        "topic": ["praise", "testimony", "evangelism"],
        "pd_basis": "PD by year (Wesley died 1788)",
        "source_url": "https://hymnary.org/text/o_for_a_thousand_tongues_to_sing",
        "text": (
            "O for a thousand tongues to sing\n"
            "My great Redeemer's praise,\n"
            "The glories of my God and King,\n"
            "The triumphs of His grace!\n\n"
            "My gracious Master and my God,\n"
            "Assist me to proclaim,\n"
            "To spread through all the earth abroad\n"
            "The honors of Thy name."
        ),
    },
    {
        "slug": "i-need-thee-every-hour",
        "title": "I Need Thee Every Hour",
        "author": "Annie Hawks",
        "year": 1872,
        "author_death": 1918,
        "meter": "6.4.6.4 with refrain",
        "scripture": ["John 15:5"],
        "topic": ["dependence", "communion"],
        "pd_basis": "PD by year",
        "source_url": "https://hymnary.org/text/i_need_thee_every_hour_most_gracious_lor",
        "text": (
            "I need Thee every hour, most gracious Lord;\n"
            "No tender voice like Thine can peace afford.\n\n"
            "Refrain:\n"
            "I need Thee, O I need Thee;\n"
            "Every hour I need Thee!\n"
            "O bless me now, my Savior;\n"
            "I come to Thee."
        ),
    },
    {
        "slug": "abide-with-me",
        "title": "Abide with Me",
        "author": "Henry Francis Lyte",
        "year": 1847,
        "author_death": 1847,
        "meter": "10.10.10.10",
        "scripture": ["Luke 24:29"],
        "topic": ["evening", "death", "presence"],
        "pd_basis": "PD by year",
        "source_url": "https://hymnary.org/text/abide_with_me_fast_falls_the_eventide",
        "text": (
            "Abide with me; fast falls the eventide;\n"
            "The darkness deepens; Lord with me abide.\n"
            "When other helpers fail and comforts flee,\n"
            "Help of the helpless, O abide with me.\n\n"
            "Swift to its close ebbs out life's little day;\n"
            "Earth's joys grow dim; its glories pass away;\n"
            "Change and decay in all around I see;\n"
            "O Thou who changest not, abide with me."
        ),
    },
    {
        "slug": "joy-to-the-world",
        "title": "Joy to the World",
        "author": "Isaac Watts",
        "year": 1719,
        "author_death": 1748,
        "meter": "C.M.",
        "scripture": ["Psa 98", "Rev 19"],
        "topic": ["advent", "second coming", "kingship"],
        "pd_basis": "PD by year",
        "source_url": "https://hymnary.org/text/joy_to_the_world_the_lord_is_come",
        "text": (
            "Joy to the world! The Lord is come;\n"
            "Let earth receive her King!\n"
            "Let every heart prepare Him room,\n"
            "And heaven and nature sing.\n\n"
            "Joy to the earth! The Savior reigns!\n"
            "Let men their songs employ;\n"
            "While fields and floods, rocks, hills, and plains\n"
            "Repeat the sounding joy."
        ),
    },
    {
        "slug": "all-hail-the-power-of-jesus-name",
        "title": "All Hail the Power of Jesus' Name",
        "author": "Edward Perronet",
        "year": 1779,
        "author_death": 1792,
        "meter": "C.M.",
        "scripture": ["Phil 2:9-11"],
        "topic": ["coronation", "name of Jesus"],
        "pd_basis": "PD by year",
        "source_url": "https://hymnary.org/text/all_hail_the_power_of_jesus_name_let",
        "text": (
            "All hail the power of Jesus' name!\n"
            "Let angels prostrate fall;\n"
            "Bring forth the royal diadem,\n"
            "And crown Him Lord of all!\n"
            "Bring forth the royal diadem,\n"
            "And crown Him Lord of all!"
        ),
    },
    {
        "slug": "the-old-rugged-cross",
        "title": "The Old Rugged Cross",
        "author": "George Bennard",
        "year": 1912,
        "author_death": 1958,
        "meter": "irregular with refrain",
        "scripture": ["1 Cor 1:18", "Gal 6:14"],
        "topic": ["cross", "atonement"],
        "pd_basis": "PD by non-renewal (Bennard 1912 first US copyright; renewal status varies; SEE NOTE)",
        "source_url": "https://hymnary.org/text/on_a_hill_far_away_stood_an_old_rugged_c",
        "text": (
            "On a hill far away stood an old rugged cross,\n"
            "The emblem of suffering and shame;\n"
            "And I love that old cross where the dearest and best\n"
            "For a world of lost sinners was slain.\n\n"
            "Refrain:\n"
            "So I'll cherish the old rugged cross,\n"
            "Till my trophies at last I lay down;\n"
            "I will cling to the old rugged cross,\n"
            "And exchange it some day for a crown."
        ),
        "verify_per_strict_rule": True,
    },
]


def author_safe_pd(hymn: dict) -> bool:
    """Strict-PD test: author died before 1900, OR explicit PD-by-year basis."""
    if hymn.get("skip"):
        return False
    if hymn.get("verify_per_strict_rule"):
        return False  # don't ship until manually verified
    death = hymn.get("author_death")
    return death is None or death < 1900


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(OUT))
    ap.add_argument("--include-borderline", action="store_true",
                    help="Include hymns whose copyright status needs per-item verification")
    args = ap.parse_args()

    accepted = []
    skipped = []
    for h in SEED_HYMNS:
        if args.include_borderline:
            ok = not h.get("skip")
        else:
            ok = author_safe_pd(h)
        entry = {
            "slug": h["slug"],
            "title": h["title"],
            "author": h.get("author"),
            "year": h.get("year"),
            "meter": h.get("meter"),
            "scripture": h.get("scripture", []),
            "topic": h.get("topic", []),
            "text": h.get("text"),
            "source_url": h.get("source_url"),
            "pd_basis": h.get("pd_basis"),
            "verse_count": len([v for v in (h.get("text") or "").split("\n\n") if v.strip()]),
        }
        if ok:
            accepted.append(entry)
        else:
            skipped.append({"slug": h["slug"], "title": h["title"], "reason": h.get("pd_basis")})

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total": len(accepted),
        "hymns": accepted,
        "skipped": skipped,
        "note": "Seed list of unambiguously-PD hymns. Expand via Hymnary.org per-text scrape (TODO: --seed-list flag).",
    }
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(payload, indent=2), encoding="utf-8")
    print(f"Wrote {args.out}: {len(accepted)} hymns ({len(skipped)} skipped per strict-PD rule)")
    for h in accepted:
        print(f"  {h['slug']:32} {h['title'][:50]:50} ({h.get('year')})")
    if skipped:
        print(f"  Skipped:")
        for s in skipped:
            print(f"    {s['slug']:32} {s['reason']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
