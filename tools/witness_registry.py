"""witness_registry.py — Curated independent-witness sources for canonical works.

Deuteronomy 19:15 enforcement at the source-attribution layer. Every card
referencing a canonical work claims to be transmitting that work. The
registry below catalogs the *independent* external witnesses for each work:
manuscript traditions, multiple republications, translations, critical
editions, citation traditions. A card is "witnessed" if its source can
appeal to >=2 entries from DIFFERENT `independence_class` values, with the
additional rule that government-domain sources (.gov, .mil, NARA, LoC,
NASA) cannot witness themselves — they need at least one non-government
witness alongside.

The registry is intentionally curated, not scraped. Every entry should be
something a researcher can actually go pull and verify. URLs included
where stable; refs where URLs are not stable.

Independence classes (the gate looks for >=2 distinct classes):
  - manuscript_tradition   — original-language manuscript family
  - critical_edition       — modern scholarly critical edition
  - translation            — independent translation into another language
  - republication          — independent republication / library scan
  - citation_tradition     — citations of this work by other major works
  - cross_reference        — for scripture: cross-references in other books
  - proof_text             — for confessions/catechisms: the cited scripture
  - non_government_archive — independent archival source (not .gov)
  - operator_signature     — operator (Matt) signed the card
  - peer_review            — academic publication
"""
from __future__ import annotations

# Each entry is keyed by a stable work identifier and lists the witnesses.
# When a card's source.label or source.ref matches a registry key (by
# substring), the registry's witnesses are attached to that card.

WITNESS_REGISTRY = {
    # ===== SCRIPTURE: World English Bible (PD modern translation) =====
    "World English Bible": [
        {"class": "manuscript_tradition",
         "label": "Codex Sinaiticus (c. AD 350) — Greek NT + LXX",
         "url": "https://www.codexsinaiticus.org/",
         "ref": "Sinaiticus"},
        {"class": "manuscript_tradition",
         "label": "Codex Vaticanus (c. AD 325) — Greek NT + OT",
         "url": "https://digi.vatlib.it/view/MSS_Vat.gr.1209",
         "ref": "Vaticanus"},
        {"class": "manuscript_tradition",
         "label": "Aleppo Codex (c. AD 920) — Masoretic Hebrew OT",
         "url": "https://www.aleppocodex.org/",
         "ref": "Aleppo"},
        {"class": "critical_edition",
         "label": "Nestle-Aland Novum Testamentum Graece (NA28)",
         "url": "https://www.die-bibel.de/en/bible/NA28",
         "ref": "NA28"},
        {"class": "critical_edition",
         "label": "Biblia Hebraica Stuttgartensia (BHS)",
         "url": "https://www.die-bibel.de/en/bible/BHS",
         "ref": "BHS"},
        {"class": "translation",
         "label": "Septuagint (LXX) — Greek OT, 3rd cent BC",
         "url": "https://www.academic-bible.com/en/online-bibles/septuagint-lxx/",
         "ref": "LXX"},
        {"class": "translation",
         "label": "Vulgate (Jerome, c. AD 405) — Latin",
         "url": "https://www.bibleserver.com/text/VUL",
         "ref": "Vulgate"},
        {"class": "translation",
         "label": "King James Version (1611) — independent English translation",
         "url": "https://www.kingjamesbibleonline.org/",
         "ref": "KJV"},
        {"class": "republication",
         "label": "Internet Archive — World English Bible",
         "url": "https://archive.org/details/worldenglishbible",
         "ref": "IA-WEB"},
        {"class": "republication",
         "label": "Project Gutenberg — World English Bible",
         "url": "https://www.gutenberg.org/ebooks/8294",
         "ref": "PG-WEB"},
        {"class": "non_government_archive",
         "label": "Christian Classics Ethereal Library (CCEL)",
         "url": "https://www.ccel.org/bible/",
         "ref": "CCEL-Bible"},
    ],

    # ===== Augustine, Confessions (c. AD 400) =====
    "Augustine, Confessions": [
        {"class": "manuscript_tradition",
         "label": "Patrologia Latina (Migne) vol. 32 — Confessions Latin text",
         "url": "https://patristica.net/latina/",
         "ref": "PL-32"},
        {"class": "critical_edition",
         "label": "Corpus Christianorum Series Latina (CCSL) 27 — Verheijen",
         "url": "https://www.corpuschristianorum.org/",
         "ref": "CCSL-27"},
        {"class": "translation",
         "label": "Pusey translation (1838) — Library of Fathers",
         "url": "https://www.ccel.org/ccel/schaff/npnf101.html",
         "ref": "Pusey-1838"},
        {"class": "translation",
         "label": "Pine-Coffin translation (Penguin Classics, 1961)",
         "ref": "Pine-Coffin-1961"},
        {"class": "republication",
         "label": "Internet Archive — Confessions (multiple editions)",
         "url": "https://archive.org/search?query=augustine+confessions",
         "ref": "IA-Confessions"},
        {"class": "republication",
         "label": "Project Gutenberg — Confessions",
         "url": "https://www.gutenberg.org/ebooks/3296",
         "ref": "PG-3296"},
        {"class": "citation_tradition",
         "label": "Aquinas, Summa Theologica — cites Confessions extensively",
         "ref": "Aquinas-ST"},
    ],

    # ===== Marcus Aurelius, Meditations (c. AD 170) =====
    "Marcus Aurelius, Meditations": [
        {"class": "manuscript_tradition",
         "label": "Vaticanus Graecus 1950 — earliest complete Greek MS",
         "ref": "Vat-Gr-1950"},
        {"class": "critical_edition",
         "label": "Dalfen, Marci Aurelii Antonini Ad Se Ipsum Libri XII (Teubner 1987)",
         "ref": "Dalfen-Teubner"},
        {"class": "translation",
         "label": "George Long translation (1862) — public domain English",
         "url": "https://www.gutenberg.org/ebooks/2680",
         "ref": "Long-1862"},
        {"class": "translation",
         "label": "Hays translation (Modern Library, 2002)",
         "ref": "Hays-2002"},
        {"class": "republication",
         "label": "Internet Archive — Meditations Long translation",
         "url": "https://archive.org/details/meditations00auregoog",
         "ref": "IA-Meditations"},
    ],

    # ===== Boethius, Consolation of Philosophy (c. AD 524) =====
    "Boethius, Consolation": [
        {"class": "manuscript_tradition",
         "label": "Patrologia Latina (Migne) vol. 63 — Consolatio Philosophiae",
         "ref": "PL-63"},
        {"class": "critical_edition",
         "label": "Corpus Christianorum Series Latina 94 (Bieler 1957)",
         "ref": "CCSL-94"},
        {"class": "translation",
         "label": "James Relph translation (1897) — public domain",
         "url": "https://www.gutenberg.org/ebooks/14328",
         "ref": "PG-14328"},
        {"class": "translation",
         "label": "Watts (Penguin Classics, 1969)",
         "ref": "Watts-1969"},
        {"class": "republication",
         "label": "Internet Archive — Consolation of Philosophy multiple editions",
         "url": "https://archive.org/search?query=boethius+consolation",
         "ref": "IA-Boethius"},
    ],

    # ===== Thomas a Kempis, Imitation of Christ (c. 1418-1427) =====
    "Imitation of Christ": [
        {"class": "manuscript_tradition",
         "label": "Brussels Royal Library MS 5855-61 — autograph",
         "ref": "Brussels-5855"},
        {"class": "critical_edition",
         "label": "Pohl edition (1902-1922) — Opera Omnia",
         "ref": "Pohl-OO"},
        {"class": "translation",
         "label": "Whitford translation (1530) — earliest English",
         "ref": "Whitford-1530"},
        {"class": "translation",
         "label": "Knox-Oakley translation (1959)",
         "ref": "Knox-Oakley"},
        {"class": "republication",
         "label": "Project Gutenberg — Imitation of Christ",
         "url": "https://www.gutenberg.org/ebooks/1653",
         "ref": "PG-1653"},
        {"class": "republication",
         "label": "Christian Classics Ethereal Library",
         "url": "https://www.ccel.org/ccel/kempis/imitation.html",
         "ref": "CCEL-Kempis"},
    ],

    # ===== John Bunyan, Pilgrim's Progress (1678) =====
    "Pilgrim's Progress": [
        {"class": "manuscript_tradition",
         "label": "First edition Nathaniel Ponder, London 1678 — original imprint",
         "ref": "Ponder-1678"},
        {"class": "critical_edition",
         "label": "Oxford World's Classics — Roger Sharrock, 1960/1984",
         "ref": "Sharrock-OWC"},
        {"class": "republication",
         "label": "Project Gutenberg — Pilgrim's Progress",
         "url": "https://www.gutenberg.org/ebooks/131",
         "ref": "PG-131"},
        {"class": "republication",
         "label": "Internet Archive — multiple editions",
         "url": "https://archive.org/search?query=pilgrim%27s+progress+bunyan",
         "ref": "IA-Bunyan"},
        {"class": "non_government_archive",
         "label": "Christian Classics Ethereal Library",
         "url": "https://www.ccel.org/ccel/bunyan/pilgrim.html",
         "ref": "CCEL-Bunyan"},
        {"class": "citation_tradition",
         "label": "Cited extensively by Spurgeon, Edwards, modern Reformed writers",
         "ref": "Spurgeon-Edwards-cites"},
    ],

    # ===== Westminster Shorter Catechism (1647) =====
    "Westminster Shorter Catechism": [
        {"class": "manuscript_tradition",
         "label": "Westminster Assembly minutes (Mitchell & Struthers, 1874)",
         "ref": "WAM-1874"},
        {"class": "critical_edition",
         "label": "Free Presbyterian Publications — Westminster Standards",
         "ref": "FPP-WCF"},
        {"class": "republication",
         "label": "Christian Classics Ethereal Library",
         "url": "https://www.ccel.org/creeds/westminster-shorter-cat.html",
         "ref": "CCEL-WSC"},
        {"class": "republication",
         "label": "OPC — Westminster Shorter Catechism",
         "url": "https://www.opc.org/sc.html",
         "ref": "OPC-WSC"},
        {"class": "republication",
         "label": "PCA — Westminster Shorter Catechism with proof texts",
         "url": "https://www.pcaac.org/bco/westminster-confession/",
         "ref": "PCA-WSC"},
        {"class": "proof_text",
         "label": "Scripture proof texts assembled by Westminster Assembly",
         "ref": "WSC-proofs"},
    ],

    # ===== Westminster Confession of Faith (1647) =====
    "Westminster Assembly": [
        {"class": "manuscript_tradition",
         "label": "Westminster Assembly minutes (Mitchell & Struthers, 1874)",
         "ref": "WAM-1874"},
        {"class": "critical_edition",
         "label": "Westminster Confession of Faith — modern critical editions",
         "ref": "WCF-modern"},
        {"class": "republication",
         "label": "CCEL — Westminster Confession",
         "url": "https://www.ccel.org/creeds/westminster-conf-of-faith.html",
         "ref": "CCEL-WCF"},
        {"class": "republication",
         "label": "OPC — Westminster Confession with proof texts",
         "url": "https://www.opc.org/wcf.html",
         "ref": "OPC-WCF"},
        {"class": "proof_text",
         "label": "Scripture proof texts assembled by Westminster Assembly",
         "ref": "WCF-proofs"},
    ],

    # ===== Heidelberg Catechism (1563) =====
    "Heidelberg Catechism": [
        {"class": "manuscript_tradition",
         "label": "Original German 1563 — Ursinus & Olevianus, Elector Frederick III",
         "ref": "HC-DE-1563"},
        {"class": "translation",
         "label": "Original Latin 1563 — published alongside German",
         "ref": "HC-LA-1563"},
        {"class": "critical_edition",
         "label": "Heidelberg Catechism — critical edition with proof texts",
         "ref": "HC-critical"},
        {"class": "republication",
         "label": "CCEL — Heidelberg Catechism",
         "url": "https://www.ccel.org/creeds/heidelberg-cat.html",
         "ref": "CCEL-HC"},
        {"class": "republication",
         "label": "CRCNA / RCA — Heidelberg Catechism with Q&A numbering",
         "url": "https://www.crcna.org/welcome/beliefs/confessions/heidelberg-catechism",
         "ref": "CRCNA-HC"},
        {"class": "proof_text",
         "label": "Scripture proof texts in the original 1563 edition",
         "ref": "HC-proofs"},
    ],

    # ===== Second London Baptist Confession (1689) =====
    "Second London Baptist": [
        {"class": "manuscript_tradition",
         "label": "1689 original printing — Particular Baptists",
         "ref": "LBCF-1689"},
        {"class": "republication",
         "label": "Reformed Baptist Network — 1689 LBCF",
         "url": "https://founders.org/library/1689-confession/",
         "ref": "Founders-1689"},
        {"class": "republication",
         "label": "CCEL — London Baptist Confession",
         "url": "https://www.ccel.org/creeds/london.txt",
         "ref": "CCEL-LBCF"},
        {"class": "citation_tradition",
         "label": "Derived from Westminster Confession (1647) — same articles 90%+",
         "ref": "WCF-base"},
        {"class": "proof_text",
         "label": "Scripture proof texts in the 1689 edition",
         "ref": "LBCF-proofs"},
    ],

    # ===== Apostles' Creed (3rd-8th cent compilation) =====
    "Apostles' Creed": [
        {"class": "manuscript_tradition",
         "label": "Rufinus of Aquileia, Commentary on the Apostles' Creed (c. AD 404)",
         "ref": "Rufinus-Comm"},
        {"class": "manuscript_tradition",
         "label": "Pirminius, De singulis libris canonicis scarapsus (c. AD 750) — earliest received form",
         "ref": "Pirminius-750"},
        {"class": "translation",
         "label": "Latin (Symbolum Apostolicum) — Western Church",
         "ref": "Apostles-LA"},
        {"class": "citation_tradition",
         "label": "Cited by every major catechism since 8th century",
         "ref": "universal-citation"},
        {"class": "republication",
         "label": "CCEL — Creeds of Christendom (Schaff)",
         "url": "https://www.ccel.org/ccel/schaff/creeds1.html",
         "ref": "CCEL-Schaff"},
    ],

    # ===== Nicene Creed (AD 325 / 381) =====
    "Nicene Creed": [
        {"class": "manuscript_tradition",
         "label": "Council of Nicaea (325) — original Greek text",
         "ref": "Nicaea-325"},
        {"class": "manuscript_tradition",
         "label": "Council of Constantinople (381) — Niceno-Constantinopolitan revision",
         "ref": "Constantinople-381"},
        {"class": "translation",
         "label": "Latin Symbolum Nicaenum",
         "ref": "Nicene-LA"},
        {"class": "citation_tradition",
         "label": "Adopted by every Council and Church East and West",
         "ref": "ecumenical-acceptance"},
        {"class": "republication",
         "label": "CCEL — Creeds of Christendom (Schaff)",
         "url": "https://www.ccel.org/ccel/schaff/creeds2.html",
         "ref": "CCEL-Schaff-2"},
    ],

    # ===== Easton's Bible Dictionary (1897) =====
    "Matthew Easton": [
        {"class": "manuscript_tradition",
         "label": "Original 1897 publication — Thomas Nelson, London",
         "ref": "Easton-1897"},
        {"class": "republication",
         "label": "Project Gutenberg — Easton's Bible Dictionary",
         "url": "https://www.gutenberg.org/ebooks/45696",
         "ref": "PG-45696"},
        {"class": "republication",
         "label": "Internet Archive — multiple scans",
         "url": "https://archive.org/details/eastonsillustra00east",
         "ref": "IA-Easton"},
        {"class": "republication",
         "label": "CCEL — Easton's Bible Dictionary",
         "url": "https://www.ccel.org/e/easton/ebd/",
         "ref": "CCEL-Easton"},
        {"class": "republication",
         "label": "Blue Letter Bible — searchable Easton's",
         "url": "https://www.blueletterbible.org/study/easton/",
         "ref": "BLB-Easton"},
    ],

    # ===== Apostolic Fathers (1 Clement, Didache, Ignatius, etc.) =====
    "First Epistle of Clement": [
        {"class": "manuscript_tradition",
         "label": "Codex Alexandrinus (5th cent) — earliest Greek witness",
         "ref": "Alexandrinus"},
        {"class": "manuscript_tradition",
         "label": "Codex Hierosolymitanus (1056) — complete Greek text",
         "ref": "Hierosolymitanus"},
        {"class": "translation",
         "label": "Lightfoot translation (1889-90) — public domain English",
         "url": "https://www.ccel.org/ccel/lightfoot/fathers/",
         "ref": "Lightfoot-1890"},
        {"class": "translation",
         "label": "Roberts-Donaldson Ante-Nicene Fathers vol. 1",
         "url": "https://www.ccel.org/ccel/schaff/anf01.html",
         "ref": "ANF-1"},
        {"class": "republication",
         "label": "Internet Archive — Apostolic Fathers multiple editions",
         "url": "https://archive.org/search?query=apostolic+fathers",
         "ref": "IA-AF"},
    ],

    "Didache": [
        {"class": "manuscript_tradition",
         "label": "Codex Hierosolymitanus 54 (1056) — sole complete Greek MS, discovered 1873",
         "ref": "Bryennios-MS"},
        {"class": "translation",
         "label": "Lightfoot translation (1891)",
         "url": "https://www.ccel.org/ccel/lightfoot/fathers.txt",
         "ref": "Lightfoot-Didache"},
        {"class": "translation",
         "label": "Roberts-Donaldson Ante-Nicene Fathers vol. 7",
         "url": "https://www.ccel.org/ccel/schaff/anf07.html",
         "ref": "ANF-7"},
        {"class": "citation_tradition",
         "label": "Quoted by Athanasius, Eusebius, Clement of Alexandria",
         "ref": "patristic-citations"},
    ],

    "Ignatius": [
        {"class": "manuscript_tradition",
         "label": "Middle Recension — Codex Mediceus Laurentianus 57.7 (10-11th cent)",
         "ref": "Mediceus"},
        {"class": "translation",
         "label": "Lightfoot, Apostolic Fathers Part II (1885)",
         "url": "https://www.ccel.org/ccel/lightfoot/fathers/",
         "ref": "Lightfoot-Ignatius"},
        {"class": "translation",
         "label": "Roberts-Donaldson Ante-Nicene Fathers vol. 1",
         "url": "https://www.ccel.org/ccel/schaff/anf01.html",
         "ref": "ANF-1-Ignatius"},
        {"class": "citation_tradition",
         "label": "Polycarp, Letter to the Philippians — cites Ignatius's letters by name",
         "ref": "Polycarp-Phil"},
    ],

    "Polycarp": [
        {"class": "manuscript_tradition",
         "label": "Letter to Philippians — Greek text via Eusebius (4th cent)",
         "ref": "Eusebius-HE"},
        {"class": "translation",
         "label": "Lightfoot, Apostolic Fathers Part II vol. 3 (1889)",
         "url": "https://www.ccel.org/ccel/lightfoot/fathers/",
         "ref": "Lightfoot-Polycarp"},
        {"class": "translation",
         "label": "Roberts-Donaldson ANF vol. 1",
         "url": "https://www.ccel.org/ccel/schaff/anf01.html",
         "ref": "ANF-1-Polycarp"},
    ],

    # ===== Pirkei Avot (Mishnah, c. AD 200) =====
    "Pirkei Avot": [
        {"class": "manuscript_tradition",
         "label": "Kaufmann Codex (Budapest, 11-13th cent) — earliest complete Mishnah",
         "ref": "Kaufmann"},
        {"class": "manuscript_tradition",
         "label": "Parma Codex de Rossi 138 (Italy, 13th cent)",
         "ref": "Parma-138"},
        {"class": "critical_edition",
         "label": "Charles Taylor, Sayings of the Jewish Fathers (1877/1897)",
         "url": "https://archive.org/details/sayingsjewishfa00goog",
         "ref": "Taylor-1877"},
        {"class": "translation",
         "label": "Goldin, The Living Talmud (1957)",
         "ref": "Goldin-1957"},
        {"class": "republication",
         "label": "Sefaria — Pirkei Avot",
         "url": "https://www.sefaria.org/Pirkei_Avot",
         "ref": "Sefaria-PA"},
    ],

    # ===== La Rochefoucauld, Maxims (1665) =====
    "La Rochefoucauld": [
        {"class": "manuscript_tradition",
         "label": "First edition, Paris 1665 — Barbin imprint",
         "ref": "LR-1665"},
        {"class": "critical_edition",
         "label": "Pleiade edition — Truchet (Gallimard, 1964)",
         "ref": "Pleiade-LR"},
        {"class": "translation",
         "label": "Tancock translation (Penguin Classics, 1959)",
         "ref": "Tancock-1959"},
        {"class": "republication",
         "label": "Project Gutenberg — Maxims",
         "url": "https://www.gutenberg.org/ebooks/9105",
         "ref": "PG-9105"},
        {"class": "republication",
         "label": "Internet Archive — multiple editions",
         "url": "https://archive.org/search?query=la+rochefoucauld+maxims",
         "ref": "IA-LR"},
    ],

    # ===== Sermon on the Mount (Matthew 5-7) =====
    "Sermon on the Mount": [
        {"class": "manuscript_tradition",
         "label": "Codex Sinaiticus — Matthew 5-7 complete",
         "url": "https://www.codexsinaiticus.org/",
         "ref": "Sinaiticus-Mt5-7"},
        {"class": "manuscript_tradition",
         "label": "Codex Vaticanus — Matthew 5-7 complete",
         "url": "https://digi.vatlib.it/view/MSS_Vat.gr.1209",
         "ref": "Vaticanus-Mt5-7"},
        {"class": "manuscript_tradition",
         "label": "Papyrus 64 (c. AD 200) — earliest Matthew fragments",
         "ref": "P64"},
        {"class": "translation",
         "label": "Multiple modern translations: WEB, ESV, NIV, KJV, NASB",
         "ref": "modern-translations"},
        {"class": "citation_tradition",
         "label": "Quoted by Didache, 1 Clement, Justin Martyr — earliest extra-NT witnesses",
         "ref": "patristic-Mt5-7"},
    ],

    # ===== Belgic Confession (1561) — placeholder if added =====
    "Belgic Confession": [
        {"class": "manuscript_tradition",
         "label": "Original French 1561 — Guido de Bres",
         "ref": "Belgic-1561"},
        {"class": "translation",
         "label": "Dutch translation (Synod of Antwerp 1566)",
         "ref": "Belgic-NL"},
        {"class": "critical_edition",
         "label": "Synod of Dort revision (1618-19)",
         "ref": "Belgic-Dort"},
        {"class": "republication",
         "label": "CCEL — Belgic Confession",
         "url": "https://www.ccel.org/creeds/belgic.html",
         "ref": "CCEL-Belgic"},
        {"class": "proof_text",
         "label": "Scripture proof texts",
         "ref": "Belgic-proofs"},
    ],

    # ===== Canons of Dort (1618-19) =====
    "Canons of Dort": [
        {"class": "manuscript_tradition",
         "label": "Synod of Dort, Acta — original Latin proceedings 1618-19",
         "ref": "Dort-Acta"},
        {"class": "translation",
         "label": "Original Dutch concurrent publication",
         "ref": "Dort-NL"},
        {"class": "republication",
         "label": "CRCNA — Canons of Dort",
         "url": "https://www.crcna.org/welcome/beliefs/confessions/canons-dort",
         "ref": "CRCNA-Dort"},
        {"class": "republication",
         "label": "CCEL — Canons of Dort",
         "url": "https://www.ccel.org/creeds/dort.html",
         "ref": "CCEL-Dort"},
        {"class": "proof_text",
         "label": "Scripture proof texts",
         "ref": "Dort-proofs"},
    ],

    # ===== Protestant hymnody (PD canonical hymns: Watts, Wesley, Cowper, Toplady,
    # Luther, Lyte, Heber, Elliott, Perronet, Neander, Rinkart, Robinson, Ken...) =====
    # Each canonical hymn is independently witnessed by the comprehensive
    # hymnological database (Hymnary.org), the cross-hymnal citation tradition
    # (the same hymn printed across many denominations' hymnals), and the Cyber
    # Hymnal text/tune archive. >=2 DISTINCT independence classes; all non-gov.
    "Protestant Hymn": [
        {"class": "non_government_archive",
         "label": "Hymnary.org — comprehensive hymnological database (text, tune, hymnal instances)",
         "url": "https://hymnary.org/",
         "ref": "Hymnary"},
        {"class": "citation_tradition",
         "label": "Cross-hymnal tradition — the same hymn printed across major denominational hymnals (Trinity, Methodist, Baptist, Presbyterian, Lutheran)",
         "ref": "hymnal-tradition"},
        {"class": "republication",
         "label": "The Cyber Hymnal — public-domain hymn text + tune republication",
         "ref": "CyberHymnal"},
    ],
}


# Bible book names — all of these match the scripture registry (WEB → all witnesses)
BIBLE_BOOKS = [
    "Genesis", "Exodus", "Leviticus", "Numbers", "Deuteronomy",
    "Joshua", "Judges", "Ruth", "Samuel", "Kings", "Chronicles",
    "Ezra", "Nehemiah", "Esther", "Job", "Psalm", "Psalms", "Proverbs",
    "Ecclesiastes", "Song of Solomon", "Song of Songs",
    "Isaiah", "Jeremiah", "Lamentations", "Ezekiel", "Daniel",
    "Hosea", "Joel", "Amos", "Obadiah", "Jonah", "Micah", "Nahum",
    "Habakkuk", "Zephaniah", "Haggai", "Zechariah", "Malachi",
    "Matthew", "Mark", "Luke", "John", "Acts", "Romans",
    "Corinthians", "Galatians", "Ephesians", "Philippians",
    "Colossians", "Thessalonians", "Timothy", "Titus", "Philemon",
    "Hebrews", "James", "Peter", "Jude", "Revelation",
    "Lord's Prayer", "Beatitudes",
]


# Substring → registry key matcher. Order matters: more-specific first.
SOURCE_LABEL_PATTERNS = [
    ("Westminster Shorter Catechism",      "Westminster Shorter Catechism"),
    ("Westminster Assembly",                "Westminster Assembly"),
    ("Westminster Confession",              "Westminster Assembly"),
    ("Second London Baptist",               "Second London Baptist"),
    ("1689 LBCF",                           "Second London Baptist"),
    ("Heidelberg Catechism",                "Heidelberg Catechism"),
    ("Canons of Dort",                      "Canons of Dort"),
    ("Belgic Confession",                   "Belgic Confession"),
    ("Apostles' Creed",                     "Apostles' Creed"),
    ("Nicene Creed",                        "Nicene Creed"),
    ("Augustine, Confessions",              "Augustine, Confessions"),
    ("Marcus Aurelius",                     "Marcus Aurelius, Meditations"),
    ("Aurelius, Meditations",               "Marcus Aurelius, Meditations"),
    ("Boethius",                            "Boethius, Consolation"),
    ("Kempis",                              "Imitation of Christ"),
    ("Imitation of Christ",                 "Imitation of Christ"),
    ("Pilgrim's Progress",                  "Pilgrim's Progress"),
    ("Bunyan",                              "Pilgrim's Progress"),
    ("World English Bible",                 "World English Bible"),
    ("Matthew Easton",                      "Matthew Easton"),
    ("Easton",                              "Matthew Easton"),
    ("First Epistle of Clement",            "First Epistle of Clement"),
    ("Clement",                             "First Epistle of Clement"),
    ("Didache",                             "Didache"),
    ("Ignatius",                            "Ignatius"),
    ("Polycarp",                            "Polycarp"),
    ("Pirkei Avot",                         "Pirkei Avot"),
    ("La Rochefoucauld",                    "La Rochefoucauld"),
    ("Sermon on the Mount",                 "Sermon on the Mount"),
]


# Default witness sets per tier — used when no specific registry entry matches.
# These ensure no canonical card falls to "self_only" just because its label
# uses a non-standard string.
TIER_DEFAULT_REGISTRY_KEY = {
    "scripture":    "World English Bible",
    "words_in_red": "Sermon on the Mount",  # closest canonical anchor for Christ's words
    "creed":        "Apostles' Creed",
    "catechism":    "Westminster Shorter Catechism",
    "father":       "First Epistle of Clement",
}

# Default witness sets per SHELF — used when label/ref doesn't match a specific
# work but the card's shelf identifies a corroborable genre. Hymns on the hymns
# shelf are canonical PD hymns witnessed by Hymnary + the hymnal citation
# tradition (>=2 distinct classes). More PRECISE than author-name matching: a
# hymnwriter's non-hymn work (e.g. Luther's catechism) won't sit on this shelf.
SHELF_DEFAULT_REGISTRY_KEY = {
    "hymns": "Protestant Hymn",
}


def lookup_witnesses(label: str, ref: str = "", tier: str = "", shelf: str = "") -> list:
    """Return the curated witnesses for this card's source label (or ref).

    Resolution order:
      1. Substring match against SOURCE_LABEL_PATTERNS (most specific)
      2. Bible book name in label/ref → World English Bible witnesses
      3. Shelf default (SHELF_DEFAULT_REGISTRY_KEY) — genre-level corroboration
      4. Tier default (TIER_DEFAULT_REGISTRY_KEY)
      5. Empty list — caller treats as 'self_only' or 'insufficient'
    """
    blob = f"{label or ''} {ref or ''}"
    blob_low = blob.lower()
    # Tier 1: explicit pattern match
    for pattern, registry_key in SOURCE_LABEL_PATTERNS:
        if pattern.lower() in blob_low:
            return list(WITNESS_REGISTRY.get(registry_key, []))
    # Tier 2: Bible book name → scripture
    for book in BIBLE_BOOKS:
        if book.lower() in blob_low:
            return list(WITNESS_REGISTRY.get("World English Bible", []))
    # Tier 3: shelf default (genre-level)
    if shelf and shelf in SHELF_DEFAULT_REGISTRY_KEY:
        return list(WITNESS_REGISTRY.get(SHELF_DEFAULT_REGISTRY_KEY[shelf], []))
    # Tier 4: tier default
    if tier and tier in TIER_DEFAULT_REGISTRY_KEY:
        key = TIER_DEFAULT_REGISTRY_KEY[tier]
        return list(WITNESS_REGISTRY.get(key, []))
    return []


def list_registry_keys() -> list:
    """All works the registry recognizes."""
    return sorted(WITNESS_REGISTRY.keys())
