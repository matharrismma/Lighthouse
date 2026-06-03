#!/usr/bin/env python3
"""SEO schema injector — add page-specific Schema.org JSON-LD blocks to
the highest-value family pages. Rich results in Google searches (Recipe,
Quiz, CollectionPage, SoftwareApplication) require structured data.

Idempotent — re-running is a no-op (skips pages that already have any
application/ld+json block).

Run from repo root:
    python tools/seo_schema.py            # dry-run
    python tools/seo_schema.py --apply    # write
"""
import argparse
import json
import re
import sys
from pathlib import Path

SITE_DIR = Path(__file__).resolve().parent.parent / "site"
ORIGIN   = "https://narrowhighway.com"
ORG_ID   = f"{ORIGIN}/#org"

EXISTING_SCHEMA_RE = re.compile(r'<script\s+type="application/ld\+json"', re.IGNORECASE)
TITLE_RE = re.compile(r"<title>(.*?)</title>", re.IGNORECASE | re.DOTALL)
DESC_RE  = re.compile(r'<meta\s+name="description"\s+content="([^"]*)"\s*/?\s*>', re.IGNORECASE)
HEAD_END = re.compile(r"</head>", re.IGNORECASE)


def page_schema(filename: str, title: str, desc: str) -> dict | None:
    """Return the Schema.org dict for a given page, or None to skip."""
    url = f"{ORIGIN}/{filename}"
    base = {
        "@context": "https://schema.org",
        "url": url,
        "name": title,
        "description": desc,
        "isPartOf": {"@type": "WebSite", "@id": f"{ORIGIN}/#website"},
        "publisher": {"@id": ORG_ID},
    }
    name = filename.replace(".html", "")

    if name == "recipes":
        return {**base,
            "@type": "CollectionPage",
            "about": {"@type": "Recipe"},
            "keywords": "public domain recipes, heritage cookbook, Fannie Farmer, Mrs Beeton, family recipes",
            "inLanguage": "en",
        }
    if name == "hymns":
        return {**base,
            "@type": "CollectionPage",
            "about": {"@type": "MusicComposition"},
            "keywords": "Christian hymns, hymn lyrics, hymn history, public domain hymns",
            "inLanguage": "en",
        }
    if name == "bibles":
        return {**base,
            "@type": "CollectionPage",
            "about": {"@type": "Book", "inLanguage": "en"},
            "keywords": "public domain Bible translations, KJV, Geneva Bible, Tyndale, ASV, parallel Bibles",
        }
    if name == "bible-trivia":
        return {**base,
            "@type": "Quiz",
            "educationalLevel": "all ages",
            "learningResourceType": "Quiz",
            "keywords": "Bible trivia, Bible quiz, family Bible game, free Bible quiz",
        }
    if name == "encyclopedia":
        return {**base,
            "@type": "CollectionPage",
            "about": {"@type": "DefinedTermSet"},
            "keywords": "Christian encyclopedia, Easton's Bible Dictionary, public domain reference",
        }
    if name == "almanac":
        return {**base,
            "@type": "CollectionPage",
            "about": {"@type": "DataCatalog"},
            "keywords": "verified claims, almanac, folk wisdom, weather lore, traditional knowledge",
        }
    if name == "walks":
        return {**base,
            "@type": "WebApplication",
            "applicationCategory": "ReferenceApplication",
            "operatingSystem": "Web",
            "browserRequirements": "Requires JavaScript",
            "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
            "keywords": "discernment engine, claim verification, four gates, scripture-aligned reasoning",
        }
    if name == "kids":
        return {**base,
            "@type": "CollectionPage",
            "about": {"@type": "VideoObject"},
            "audience": {"@type": "PeopleAudience", "suggestedMinAge": 3, "suggestedMaxAge": 12},
            "keywords": "family safe cartoons, Christian kids videos, public domain animation, Bible stories for kids",
        }
    if name == "games":
        return {**base,
            "@type": "CollectionPage",
            "about": {"@type": "Game"},
            "keywords": "free family games, chess, Bible trivia, Christian games",
        }
    if name == "tools":
        return {**base,
            "@type": "CollectionPage",
            "about": {"@type": "WebApplication"},
            "keywords": "free family tools, calculator, dictionary, maps, music maker, drawing pad",
        }
    if name == "radio":
        return {**base,
            "@type": "RadioBroadcastService",
            "broadcastDisplayName": "Narrow Highway Radio",
            "broadcastFrequency": [
                {"@type": "BroadcastFrequencySpecification", "broadcastSignalModulation": "AM"},
                {"@type": "BroadcastFrequencySpecification", "broadcastSignalModulation": "FM"},
                {"@type": "BroadcastFrequencySpecification", "broadcastSignalModulation": "SW"},
            ],
        }
    if name == "apothecary":
        return {**base,
            "@type": "CollectionPage",
            "about": {"@type": "MedicalCondition"},
            "keywords": "Christian remedies, scripture for affliction, family-safe protocols",
        }
    if name == "hearth":
        return {**base,
            "@type": "WebApplication",
            "applicationCategory": "Lifestyle",
            "keywords": "Christian community, family Bible study, prayer rooms",
        }
    if name == "learn":
        return {**base,
            "@type": "CollectionPage",
            "about": {"@type": "EducationalOccupationalProgram"},
            "audience": {"@type": "PeopleAudience", "audienceType": "homeschool families"},
            "keywords": "homeschool curriculum, Christian education, phonics, reading, math, science",
        }
    return None


def process(path: Path, apply: bool) -> tuple[str, int]:
    try:
        text = path.read_text(encoding="utf-8")
    except Exception as e:
        return f"skip:read_error:{e}", 0
    if EXISTING_SCHEMA_RE.search(text):
        return "skip:already_has_schema", 0
    m_t, m_d = TITLE_RE.search(text), DESC_RE.search(text)
    if not m_t:
        return "skip:no_title", 0
    title = re.sub(r"\s+", " ", m_t.group(1)).strip()
    desc  = (m_d.group(1) if m_d else title).strip()
    schema = page_schema(path.name, title, desc)
    if schema is None:
        return "skip:no_schema_for_page", 0
    if not HEAD_END.search(text):
        return "skip:no_head_end", 0

    block = (
        '<script type="application/ld+json">\n'
        + json.dumps(schema, indent=2, ensure_ascii=False)
        + "\n</script>\n"
    )
    new_text = HEAD_END.sub(block + "</head>", text, count=1)
    if new_text == text:
        return "skip:replace_noop", 0
    if apply:
        path.write_text(new_text, encoding="utf-8")
    return "fix:schema_added", block.count("\n")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    args = ap.parse_args()

    targets = [
        "recipes.html", "hymns.html", "bibles.html", "bible-trivia.html",
        "encyclopedia.html", "almanac.html", "walks.html", "kids.html",
        "games.html", "tools.html", "radio.html", "apothecary.html",
        "hearth.html", "learn.html",
    ]
    by_status: dict[str, int] = {}
    for name in targets:
        p = SITE_DIR / name
        if not p.exists():
            print(f"  missing: {name}")
            continue
        st, _ = process(p, args.apply)
        by_status[st] = by_status.get(st, 0) + 1
        print(f"  {name:24s}  {st}")
    print("\nSummary:", dict(by_status))
    if not args.apply:
        print("\nRun with --apply to write.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
