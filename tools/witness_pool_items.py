"""witness_pool_items.py — Annotate FAST channel pool items with witnesses.

The channel manifest's content_pool contains pre-rendered media items
(hymn videos, OTR audio, classic TV, Spurgeon readings, etc.) that bypass
the card system. Each pool item type has its own provenance trail. This
tool walks the pool and attaches witness data per item-type, then writes
the updated manifest.

Witness rules per pool type, applying Deut 19:15 (>=2 independent witnesses)
and the no-government-self-witness rule:

  hymns                 — pre-1928 composers; multiple hymnal publications,
                          Hymnary.org, CCEL, Project Gutenberg
  scifi_audio_dramas    — original NBC/ABC/CBS broadcasts (Dimension X,
                          X Minus One, Lights Out, etc.); Internet Archive
                          OTR collection, otrcat.com collector archives,
                          Library of Congress radio history
  scifi_animated_pilots — our own productions; operator signature + script
                          attribution (Bradbury, Asimov etc.) + scripture
                          alignment
  kids_*_readings       — PD audiobooks (LibriVox / Internet Archive);
                          original publication + multiple republications
  spurgeon_*            — original 19th-cent. printings; CCEL, Spurgeon
                          Center, archive.org, citation tradition
  edwards_*             — Yale Edwards critical edition (Works of JE) +
                          CCEL + Banner of Truth Trust + Internet Archive
  classic_tv_video      — PD by failed renewal; Library of Congress
                          Copyright Office renewal records (LOC.gov, with
                          IA / collector cross-witness for non-gov),
                          Internet Archive Classic TV collection, collector
                          communities
  classic_animation     — same as classic_tv; PD cartoons
  silent_films          — PD by year (pre-1928); BFI, Library of Congress
                          + Internet Archive Silent Films collection
  otr_*_audio           — same OTR collector pattern; broadcast log + IA
                          + Old Time Radio Researchers Group + collector sites
  sports_*              — broadcast records + collector archives; for
                          modern sports require non-broadcaster witnesses
  nasa_video            — GOVERNMENT source (.gov); requires non-government
                          corroboration (IA + collector archives + Wikimedia)
  newsreel_video        — usually PD post-renewal; British Pathé archive +
                          IA + LoC + multiple distributors
  educational_video     — PD by mid-century; Prelinger Archives + IA + LoC
  prelinger_video       — Prelinger Archives (private collection, donated
                          to LoC); both LoC AND Prelinger as separate
                          witnesses, plus IA mirror

Output: writes content/channels/narrow_highway.json in place with each
pool item gaining a `witnesses[]` array and `witness_status`.

Run:
  python tools/witness_pool_items.py --dry-run
  python tools/witness_pool_items.py --apply
"""
from __future__ import annotations
import argparse
import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
MANIFEST = REPO / "content" / "channels" / "narrow_highway.json"


# ===== Witness sets keyed by content_pool key =====

WITNESS_BY_POOL_KEY = {
    "hymns": [
        {"class": "manuscript_tradition",
         "label": "Original composer publication (pre-1928 PD by year)",
         "ref": "PD-pre-1928"},
        {"class": "republication",
         "label": "Hymnary.org — 1.6M hymn database with publication metadata",
         "url": "https://hymnary.org/",
         "ref": "Hymnary"},
        {"class": "republication",
         "label": "Christian Classics Ethereal Library — hymn collection",
         "url": "https://www.ccel.org/hymn/",
         "ref": "CCEL-hymn"},
        {"class": "republication",
         "label": "Cyber Hymnal — comprehensive PD hymn texts and tunes",
         "url": "https://hymnary.org/hymnal/CYBER",
         "ref": "CyberHymnal"},
        {"class": "citation_tradition",
         "label": "Sung in every major denomination's hymnal post-publication",
         "ref": "universal-hymnal-use"},
    ],

    "scifi_audio_dramas": [
        {"class": "manuscript_tradition",
         "label": "Original broadcast logs — NBC/ABC/CBS network archives",
         "ref": "broadcast-logs"},
        {"class": "republication",
         "label": "Internet Archive Old Time Radio collection",
         "url": "https://archive.org/details/oldtimeradio",
         "ref": "IA-OTR"},
        {"class": "non_government_archive",
         "label": "Old Time Radio Researchers Group — restored episodes",
         "url": "https://www.otrr.org/",
         "ref": "OTRR"},
        {"class": "non_government_archive",
         "label": "OTRCat — commercial OTR collector reference",
         "url": "https://www.otrcat.com/",
         "ref": "OTRCat"},
        {"class": "citation_tradition",
         "label": "Cited in Sci-Fi Encyclopedia (Clute & Nicholls) and broadcast histories",
         "ref": "scifi-encyclopedia"},
    ],

    "otr_mystery_audio": [  # same as scifi_audio_dramas
        {"class": "manuscript_tradition",
         "label": "Original broadcast logs — NBC/ABC/CBS/Mutual network archives",
         "ref": "broadcast-logs"},
        {"class": "republication",
         "label": "Internet Archive Old Time Radio collection",
         "url": "https://archive.org/details/oldtimeradio",
         "ref": "IA-OTR"},
        {"class": "non_government_archive",
         "label": "Old Time Radio Researchers Group",
         "url": "https://www.otrr.org/",
         "ref": "OTRR"},
        {"class": "non_government_archive",
         "label": "OTRCat collector reference",
         "url": "https://www.otrcat.com/",
         "ref": "OTRCat"},
    ],

    "otr_western_audio":   None,  # filled at runtime from mystery_audio
    "otr_anthology_drama": None,
    "otr_comedy_audio":    None,

    "scifi_animated_pilots": [
        {"class": "operator_signature",
         "label": "Operator signature — Matt Harris / Narrow Highway production",
         "ref": "operator"},
        {"class": "manuscript_tradition",
         "label": "Source script attribution (Bradbury / Asimov / public-domain author)",
         "ref": "script-attribution"},
        {"class": "non_government_archive",
         "label": "Internet Archive — Sci-Fi Theatre channel",
         "ref": "IA-NH"},
    ],

    "kids_pooh_readings": [
        {"class": "manuscript_tradition",
         "label": "A.A. Milne, Winnie-the-Pooh (1926) — original Methuen & Co. publication",
         "ref": "Milne-1926"},
        {"class": "republication",
         "label": "Project Gutenberg Australia — Pooh (PD in Australia 2007)",
         "url": "https://gutenberg.net.au/ebooks02/0201131h.html",
         "ref": "PG-AU-Pooh"},
        {"class": "republication",
         "label": "LibriVox — Winnie-the-Pooh audio recordings",
         "url": "https://librivox.org/winnie-the-pooh-by-a-a-milne/",
         "ref": "LibriVox-Pooh"},
        {"class": "republication",
         "label": "Internet Archive — Winnie-the-Pooh multiple editions",
         "url": "https://archive.org/details/winniethepooh00mils",
         "ref": "IA-Pooh"},
        {"class": "citation_tradition",
         "label": "Universally cited in children's literature scholarship",
         "ref": "childrens-lit-canon"},
    ],

    "kids_potter_readings": [
        {"class": "manuscript_tradition",
         "label": "Beatrix Potter, Peter Rabbit (1902) — Frederick Warne & Co.",
         "ref": "Potter-1902"},
        {"class": "republication",
         "label": "Project Gutenberg — Tale of Peter Rabbit",
         "url": "https://www.gutenberg.org/ebooks/14838",
         "ref": "PG-14838"},
        {"class": "republication",
         "label": "LibriVox — Beatrix Potter readings",
         "url": "https://librivox.org/author/74",
         "ref": "LibriVox-Potter"},
        {"class": "republication",
         "label": "Internet Archive — Potter multiple editions",
         "url": "https://archive.org/search?query=beatrix+potter",
         "ref": "IA-Potter"},
    ],

    "kids_andersen_readings": [
        {"class": "manuscript_tradition",
         "label": "Hans Christian Andersen, Fairy Tales (1835-1872) — Danish originals",
         "ref": "Andersen-orig"},
        {"class": "translation",
         "label": "Multiple PD English translations (Boner, Howitt, Dulcken)",
         "ref": "Andersen-translations"},
        {"class": "republication",
         "label": "Project Gutenberg — Andersen Fairy Tales",
         "url": "https://www.gutenberg.org/ebooks/27200",
         "ref": "PG-Andersen"},
        {"class": "republication",
         "label": "LibriVox — Andersen audio collection",
         "url": "https://librivox.org/author/77",
         "ref": "LibriVox-Andersen"},
    ],

    "kids_blue_fairy_readings": [
        {"class": "manuscript_tradition",
         "label": "Andrew Lang, Blue Fairy Book (1889) — Longmans, Green & Co.",
         "ref": "Lang-1889"},
        {"class": "republication",
         "label": "Project Gutenberg — Blue Fairy Book",
         "url": "https://www.gutenberg.org/ebooks/503",
         "ref": "PG-503"},
        {"class": "republication",
         "label": "LibriVox — Blue Fairy Book",
         "url": "https://librivox.org/the-blue-fairy-book-by-andrew-lang/",
         "ref": "LibriVox-Blue"},
    ],

    "kids_velveteen": [
        {"class": "manuscript_tradition",
         "label": "Margery Williams, Velveteen Rabbit (1922)",
         "ref": "Williams-1922"},
        {"class": "republication",
         "label": "Project Gutenberg — Velveteen Rabbit",
         "url": "https://www.gutenberg.org/ebooks/11757",
         "ref": "PG-11757"},
        {"class": "republication",
         "label": "LibriVox audio",
         "url": "https://librivox.org/the-velveteen-rabbit-by-margery-williams-bianco/",
         "ref": "LibriVox-Velveteen"},
    ],

    "spurgeon_morning_evening": [
        {"class": "manuscript_tradition",
         "label": "Morning and Evening — Charles Spurgeon, Passmore & Alabaster, 1865/1869",
         "ref": "Spurgeon-orig"},
        {"class": "republication",
         "label": "CCEL — Morning and Evening",
         "url": "https://www.ccel.org/ccel/spurgeon/morneve.html",
         "ref": "CCEL-Spurgeon"},
        {"class": "republication",
         "label": "Spurgeon.org — full Spurgeon archive",
         "url": "https://www.spurgeon.org/",
         "ref": "Spurgeon-org"},
        {"class": "republication",
         "label": "Internet Archive — multiple Spurgeon editions",
         "url": "https://archive.org/search?query=spurgeon+morning+evening",
         "ref": "IA-Spurgeon"},
    ],

    "spurgeon_all_of_grace": [
        {"class": "manuscript_tradition",
         "label": "All of Grace — Charles Spurgeon, Passmore & Alabaster, 1886",
         "ref": "Spurgeon-AoG-1886"},
        {"class": "republication",
         "label": "CCEL — All of Grace",
         "url": "https://www.ccel.org/ccel/spurgeon/grace.html",
         "ref": "CCEL-AoG"},
        {"class": "republication",
         "label": "Spurgeon.org",
         "url": "https://www.spurgeon.org/",
         "ref": "Spurgeon-org"},
        {"class": "republication",
         "label": "Project Gutenberg",
         "url": "https://www.gutenberg.org/ebooks/636",
         "ref": "PG-636"},
    ],

    "edwards_select_sermons": [
        {"class": "critical_edition",
         "label": "Yale Edwards Critical Edition — Works of Jonathan Edwards",
         "url": "https://edwards.yale.edu/",
         "ref": "Yale-WJE"},
        {"class": "republication",
         "label": "CCEL — Edwards sermons",
         "url": "https://www.ccel.org/ccel/edwards/",
         "ref": "CCEL-Edwards"},
        {"class": "republication",
         "label": "Banner of Truth Trust — Works of JE",
         "url": "https://banneroftruth.org/us/store/jonathan-edwards-works/",
         "ref": "BOT-Edwards"},
        {"class": "republication",
         "label": "Internet Archive — Edwards multiple editions",
         "url": "https://archive.org/search?query=jonathan+edwards",
         "ref": "IA-Edwards"},
    ],

    "edwards_religious_affections": [
        {"class": "critical_edition",
         "label": "Yale WJE Volume 2 — Religious Affections (J. E. Smith, ed.)",
         "url": "https://edwards.yale.edu/research/major-works/religious-affections",
         "ref": "Yale-RA"},
        {"class": "republication",
         "label": "CCEL — Religious Affections",
         "url": "https://www.ccel.org/ccel/edwards/affections.html",
         "ref": "CCEL-RA"},
        {"class": "republication",
         "label": "Banner of Truth — Religious Affections",
         "ref": "BOT-RA"},
        {"class": "republication",
         "label": "Internet Archive",
         "url": "https://archive.org/details/treatiseconcerni0000edwa",
         "ref": "IA-RA"},
    ],

    "classic_tv_video": [
        {"class": "manuscript_tradition",
         "label": "Original broadcast records / production logs (1948-1963 PD-by-non-renewal era)",
         "ref": "production-logs"},
        {"class": "non_government_archive",
         "label": "Internet Archive — Classic TV collection",
         "url": "https://archive.org/details/classic_tv",
         "ref": "IA-ClassicTV"},
        {"class": "non_government_archive",
         "label": "TV.com / IMDB historical records (cross-witness)",
         "ref": "TVCom-IMDB"},
        {"class": "non_government_archive",
         "label": "Classic TV collector communities — DVD/file provenance chains",
         "ref": "ClassicTV-Collectors"},
        {"class": "peer_review",
         "label": "Library of Congress Copyright Office renewal records (gov, requires cross-witness)",
         "url": "https://www.loc.gov/copyright/",
         "ref": "LoC-Renewals"},
    ],

    "classic_animation": [
        {"class": "manuscript_tradition",
         "label": "Original studio production records (Fleischer, Van Beuren, Iwerks et al)",
         "ref": "studio-records"},
        {"class": "non_government_archive",
         "label": "Internet Archive — Classic Cartoons collection",
         "url": "https://archive.org/details/classic_cartoons",
         "ref": "IA-Cartoons"},
        {"class": "non_government_archive",
         "label": "Cartoon Research / Animation Trail historical documentation",
         "url": "https://cartoonresearch.com/",
         "ref": "CartoonResearch"},
        {"class": "peer_review",
         "label": "LoC Copyright Office records (gov, cross-witness required)",
         "url": "https://www.loc.gov/copyright/",
         "ref": "LoC-Renewals-Cartoons"},
    ],

    "silent_films": [
        {"class": "manuscript_tradition",
         "label": "Original 35mm or 16mm reels (pre-1928 PD by year)",
         "ref": "original-reels"},
        {"class": "non_government_archive",
         "label": "Internet Archive — Silent Films collection",
         "url": "https://archive.org/details/silent_films",
         "ref": "IA-Silent"},
        {"class": "non_government_archive",
         "label": "BFI National Archive (UK)",
         "url": "https://www.bfi.org.uk/film-collections",
         "ref": "BFI"},
        {"class": "peer_review",
         "label": "Library of Congress National Film Registry (gov, cross-witness)",
         "url": "https://www.loc.gov/programs/national-film-preservation-board/",
         "ref": "LoC-NFR"},
    ],

    "newsreel_video": [
        {"class": "manuscript_tradition",
         "label": "Original newsreel studio records (Pathé, Movietone, Hearst Metrotone)",
         "ref": "newsreel-studios"},
        {"class": "non_government_archive",
         "label": "British Pathé archive",
         "url": "https://www.britishpathe.com/",
         "ref": "BritishPathe"},
        {"class": "non_government_archive",
         "label": "Internet Archive Newsreels collection",
         "url": "https://archive.org/details/newsreels",
         "ref": "IA-Newsreels"},
    ],

    "educational_video": [
        {"class": "non_government_archive",
         "label": "Prelinger Archives (private collection, accessible via IA)",
         "url": "https://archive.org/details/prelinger",
         "ref": "Prelinger"},
        {"class": "non_government_archive",
         "label": "Internet Archive Educational Films collection",
         "url": "https://archive.org/details/educationalfilms",
         "ref": "IA-Educational"},
        {"class": "peer_review",
         "label": "Library of Congress (gov, requires non-gov cross-witness above)",
         "ref": "LoC-Educational"},
    ],

    "prelinger_video": [
        {"class": "non_government_archive",
         "label": "Prelinger Archives — Rick Prelinger's private archive (1986-2002)",
         "ref": "Prelinger-archive"},
        {"class": "non_government_archive",
         "label": "Internet Archive — Prelinger collection mirror",
         "url": "https://archive.org/details/prelinger",
         "ref": "IA-Prelinger"},
        {"class": "peer_review",
         "label": "Library of Congress (gov, donated by Prelinger 2002 — pre-donation provenance non-gov)",
         "ref": "LoC-Prelinger"},
    ],

    "nasa_video": [
        {"class": "peer_review",
         "label": "NASA.gov — official source (.gov, REQUIRES non-gov cross-witness below)",
         "url": "https://www.nasa.gov/",
         "ref": "NASA"},
        {"class": "non_government_archive",
         "label": "Internet Archive — NASA media collection",
         "url": "https://archive.org/details/nasa",
         "ref": "IA-NASA"},
        {"class": "non_government_archive",
         "label": "Wikimedia Commons — NASA media (independent mirror with verification)",
         "url": "https://commons.wikimedia.org/wiki/Category:Images_from_NASA",
         "ref": "Wikimedia-NASA"},
        {"class": "citation_tradition",
         "label": "Cited extensively in independent space/science publications",
         "ref": "space-publications"},
    ],

    "government_video": [
        {"class": "peer_review",
         "label": "Original .gov source (REQUIRES non-gov cross-witness)",
         "ref": "gov-original"},
        {"class": "non_government_archive",
         "label": "Internet Archive — government media collection mirror",
         "url": "https://archive.org/details/usgovernment",
         "ref": "IA-USGov"},
        {"class": "non_government_archive",
         "label": "Wikimedia Commons — government media",
         "ref": "Wikimedia-USGov"},
    ],

    "sports_boxing_video": [
        {"class": "manuscript_tradition",
         "label": "Original fight footage / broadcast records",
         "ref": "fight-broadcasts"},
        {"class": "non_government_archive",
         "label": "Internet Archive Boxing collection",
         "url": "https://archive.org/details/boxing",
         "ref": "IA-Boxing"},
        {"class": "non_government_archive",
         "label": "BoxRec — independent boxing reference database",
         "url": "https://boxrec.com/",
         "ref": "BoxRec"},
    ],

    "sports_misc_video": [
        {"class": "manuscript_tradition",
         "label": "Original broadcast / production records",
         "ref": "sports-broadcasts"},
        {"class": "non_government_archive",
         "label": "Internet Archive Sports collection",
         "url": "https://archive.org/details/sports",
         "ref": "IA-Sports"},
        {"class": "non_government_archive",
         "label": "Sports historical databases (era-specific)",
         "ref": "sports-databases"},
    ],

    "sports_roller_derby": [
        {"class": "manuscript_tradition",
         "label": "Original roller derby broadcast records (1949-1953 PD era)",
         "ref": "rd-broadcasts"},
        {"class": "non_government_archive",
         "label": "Internet Archive Roller Derby collection",
         "url": "https://archive.org/details/rollerderby",
         "ref": "IA-RD"},
        {"class": "non_government_archive",
         "label": "National Roller Derby Hall of Fame",
         "ref": "RDHOF"},
    ],

    "fishing_film": [
        {"class": "manuscript_tradition",
         "label": "Original production records (mid-century outdoor sports films)",
         "ref": "outdoor-production"},
        {"class": "non_government_archive",
         "label": "Internet Archive Outdoor Sports collection",
         "ref": "IA-Outdoor"},
        {"class": "non_government_archive",
         "label": "Outdoor/fishing collector archives",
         "ref": "outdoor-collectors"},
    ],

    "racing_film": [
        {"class": "manuscript_tradition",
         "label": "Original race footage / production records",
         "ref": "racing-records"},
        {"class": "non_government_archive",
         "label": "Internet Archive Racing collection",
         "ref": "IA-Racing"},
        {"class": "non_government_archive",
         "label": "Racing history databases (NASCAR / IndyCar / dirt-track communities)",
         "ref": "racing-databases"},
    ],

    "rodeo_film": [
        {"class": "manuscript_tradition",
         "label": "Original rodeo broadcast / production records (mid-20th cent.)",
         "ref": "rodeo-records"},
        {"class": "non_government_archive",
         "label": "Internet Archive Rodeo / Western collection",
         "ref": "IA-Rodeo"},
        {"class": "non_government_archive",
         "label": "ProRodeo Hall of Fame archives",
         "ref": "ProRodeo-HOF"},
    ],

    "hist_video": [
        {"class": "manuscript_tradition",
         "label": "Original historical footage / studio records",
         "ref": "hist-records"},
        {"class": "non_government_archive",
         "label": "Internet Archive Historical Films collection",
         "ref": "IA-Hist"},
        {"class": "non_government_archive",
         "label": "Independent historical archives",
         "ref": "hist-archives"},
    ],

    "vegas_variety": [
        {"class": "manuscript_tradition",
         "label": "Original Vegas-era variety show production records",
         "ref": "vegas-records"},
        {"class": "non_government_archive",
         "label": "Internet Archive variety / live performance collection",
         "ref": "IA-Variety"},
        {"class": "non_government_archive",
         "label": "Las Vegas historical archives",
         "ref": "Vegas-archives"},
    ],

    "performance_shorts": [
        {"class": "manuscript_tradition",
         "label": "Original short-film production records",
         "ref": "shorts-records"},
        {"class": "non_government_archive",
         "label": "Internet Archive Short Films collection",
         "ref": "IA-Shorts"},
        {"class": "non_government_archive",
         "label": "Independent short-film archives",
         "ref": "shorts-archives"},
    ],

    # Aspirational / user-facing categories — empty pools today
    "kids_animated_pilots": [
        {"class": "operator_signature",
         "label": "Operator signature — Narrow Highway / Hundred Acre Theatre production",
         "ref": "operator"},
        {"class": "manuscript_tradition",
         "label": "Source attribution: Milne Pooh / public-domain children's works",
         "ref": "source-attribution"},
        {"class": "non_government_archive",
         "label": "Internet Archive — Hundred Acre Theatre channel",
         "ref": "IA-HAT"},
    ],

    "user_content_primary":   None,
    "user_content_secondary": None,
    "user_content_cancelled": None,
}


# Fill OTR variants by copying mystery
for key in ("otr_western_audio", "otr_anthology_drama", "otr_comedy_audio"):
    WITNESS_BY_POOL_KEY[key] = list(WITNESS_BY_POOL_KEY["otr_mystery_audio"])


def evaluate_pool_item(pool_key: str, item: dict) -> dict:
    """Return witnesses + status for a single pool item."""
    witnesses = WITNESS_BY_POOL_KEY.get(pool_key)
    if witnesses is None:
        return {
            "witnesses": [],
            "witness_status": "pending",
            "witness_status_reason": f"no witness template defined for pool key {pool_key!r} (user_content or unmapped)",
        }
    classes = {w.get("class") for w in witnesses}
    if len(classes) < 2:
        return {
            "witnesses": witnesses,
            "witness_status": "single_witness",
            "witness_status_reason": f"template has only {len(classes)} class",
        }
    # Government rule check
    gov_classes = {"peer_review"} if any(("gov" in (w.get("ref","") or "").lower()
                                          or ".gov" in (w.get("url","") or "").lower()
                                          or "loc" in (w.get("ref","") or "").lower()
                                          or "NASA" in (w.get("ref","") or ""))
                                         for w in witnesses) else set()
    non_gov_classes = classes - gov_classes
    if gov_classes and not non_gov_classes:
        return {
            "witnesses": witnesses,
            "witness_status": "gov_only",
            "witness_status_reason": "all witnesses are gov; need non-gov corroboration",
        }
    return {
        "witnesses": witnesses,
        "witness_status": "passed",
        "witness_status_reason": f"{len(witnesses)} witnesses across {len(classes)} classes: {sorted(classes)}",
    }


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--apply", action="store_true")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    if not (args.apply or args.dry_run):
        args.dry_run = True

    m = json.loads(MANIFEST.read_text(encoding="utf-8"))
    pool = m.get("content_pool", {})

    status_count = Counter()
    by_key_status: dict = {}
    total = 0
    for pool_key, items in pool.items():
        for it in items:
            total += 1
            result = evaluate_pool_item(pool_key, it)
            status_count[result["witness_status"]] += 1
            by_key_status.setdefault(pool_key, Counter())[result["witness_status"]] += 1
            if args.apply:
                it["witnesses"] = result["witnesses"]
                it["witness_status"] = result["witness_status"]
                it["witness_status_reason"] = result["witness_status_reason"]

    print(f"pool items evaluated: {total}")
    print()
    print("witness_status distribution:")
    for s, n in status_count.most_common():
        print(f"  {s:<20} {n:>5}")
    print()
    print("by pool key:")
    for k, cnt in sorted(by_key_status.items()):
        print(f"  {k}: " + " ".join(f"{s}={n}" for s, n in cnt.most_common()))

    if args.apply:
        MANIFEST.write_text(json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
        print()
        print(f"WROTE {MANIFEST}")
    else:
        print()
        print("DRY-RUN — manifest not modified.")


if __name__ == "__main__":
    main()
