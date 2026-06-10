"""Internet Archive library downloader.

Pulls PD content from archive.org using their public metadata + download
APIs. For each target series:
  • Queries the IA metadata endpoint for file listing
  • Filters to relevant formats (mp3 for audio shows, mp4/avi for video)
  • Downloads each file with resumable HTTP
  • Computes SHA-256 hash
  • Writes a manifest at data/library_inventory/acquired/<slug>.json
  • Logs verification evidence (collection ID, IA metadata URL, claimed PD status)

PER-EPISODE VERIFICATION still required by Matt's protocol. This script
*acquires* candidate files and captures evidence; legal sign-off on each
item remains a human review step before ingestion into the channel.

Usage:
    python scripts/library_download_ia.py [--series SLUG] [--limit N]
                                          [--storage PATH] [--list]
                                          [--dry-run]

Targets are configured in TARGETS below. Add to TARGETS or pass --series
to download specific items.
"""
import hashlib
import json
import os
import re
import sys
import time
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path

import requests  # uses certifi-bundled CA store; works on Windows stock Python

REPO = Path(__file__).resolve().parent.parent
INVENTORY = REPO / "data" / "library_inventory"
ACQUIRED = INVENTORY / "acquired"
# Storage offloaded to external drive 2026-05-16 (C: filled at 237GB).
# Override with --storage PATH; keeping C: lean and OneDrive sync-free.
DEFAULT_STORAGE = Path("D:/library_files")


# Target catalog — series we want to acquire from Internet Archive.
# IDs verified via IA's advancedsearch API + metadata fetches (2026-05-15).
# Each target: { slug, title, ia_collection_id, claimed_status, formats }
TARGETS = [
    # ── Originally verified working ──
    {
        "slug": "x_minus_one",
        "title": "X Minus One",
        "ia_collection": "OTRR_X_Minus_One_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Sci-fi anthology, 1955-58, adaptations of Bradbury/Asimov/Heinlein/Sturgeon. NBC.",
    },
    {
        "slug": "dimension_x",
        "title": "Dimension X",
        "ia_collection": "OTRR_Dimension_X_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Sister show to X Minus One. NBC, 1950-51.",
    },
    {
        "slug": "suspense",
        "title": "Suspense",
        "ia_collection": "OTRR_Suspense_Singles",
        "claimed_status": "PD by non-renewal (per OTRR)",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "CBS thriller anthology, 1942-62. Big-name stars.",
    },
    {
        "slug": "cavalcade_of_america",
        "title": "Cavalcade of America",
        "ia_collection": "OTRR_Cavalcade_of_America_Singles",
        "claimed_status": "PD by non-renewal (DuPont sponsored)",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Historical dramatizations with moral/civic framing, 1935-53.",
    },

    # ── Corrected IDs ──
    {
        "slug": "lone_ranger",
        "title": "The Lone Ranger",
        "ia_collection": "OTRR_LoneRanger_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Classic Western, 1933-56. Mountain ethics — Dade-adjacent.",
    },
    {
        "slug": "mercury_theatre",
        "title": "Mercury Theatre on the Air",
        "ia_collection": "TheMercuryTheatreontheAir",
        "claimed_status": "PD by year (1938)",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Orson Welles, 22 episodes including War of the Worlds.",
    },
    {
        "slug": "quiet_please",
        "title": "Quiet, Please",
        "ia_collection": "Quiet_Please",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Wyllis Cooper — artistic peak of radio drama, 1947-49.",
    },
    {
        "slug": "lum_and_abner",
        "title": "Lum and Abner",
        "ia_collection": "Lum-and-Abner-OTR",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Appalachian-flavored comedy, 1931-55. Dade tonal fit. ~1,647 episodes.",
    },
    {
        "slug": "you_are_there",
        "title": "You Are There",
        "ia_collection": "You_Are_There_OTR",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Cronkite historical dramatization. History Channel format, 1947-57.",
    },

    # ── High-value additions (top OTRR_*_Singles by download count) ──
    {
        "slug": "gunsmoke",
        "title": "Gunsmoke",
        "ia_collection": "OTRR_Gunsmoke_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Adult Western, 1952-61. William Conrad as Matt Dillon. 7.2M downloads — most popular OTR.",
    },
    {
        "slug": "yours_truly_johnny_dollar",
        "title": "Yours Truly, Johnny Dollar",
        "ia_collection": "OTRR_YoursTrulyJohnnyDollar_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Insurance investigator, 1949-62. Tight episodic mysteries.",
    },
    {
        "slug": "dragnet",
        "title": "Dragnet",
        "ia_collection": "OTRR_Dragnet_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Police procedural, 1949-57. Jack Webb. Documentary-style true-crime substrate.",
    },
    {
        "slug": "philip_marlowe",
        "title": "Adventures of Philip Marlowe",
        "ia_collection": "OTRR_Philip_Marlowe_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Noir detective, 1947-51.",
    },
    {
        "slug": "whistler",
        "title": "The Whistler",
        "ia_collection": "OTRR_Whistler_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Mystery anthology, 1942-55.",
    },
    {
        "slug": "escape",
        "title": "Escape",
        "ia_collection": "OTRR_Escape_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Adventure anthology, 1947-54. CBS prestige.",
    },
    {
        "slug": "six_shooter",
        "title": "The Six Shooter",
        "ia_collection": "OTRR_The_Six_Shooter_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "James Stewart Western, 1953-54. One season; high quality.",
    },
    {
        "slug": "inner_sanctum",
        "title": "Inner Sanctum Mysteries",
        "ia_collection": "OTRR_Inner_Sanctum_Mysteries_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Horror anthology, 1941-52. Iconic creaking-door intro.",
    },
    {
        "slug": "crime_classics",
        "title": "Crime Classics",
        "ia_collection": "OTRR_Crime_Classics_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "True-crime dramatizations, 1953-54.",
    },
    {
        "slug": "theater_five",
        "title": "Theater Five",
        "ia_collection": "OTRR_Theater_Five_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "ABC anthology, 1964-65. Late-OTR.",
    },
    {
        "slug": "frontier_gentleman",
        "title": "Frontier Gentleman",
        "ia_collection": "OTRR_FrontierGentleman_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Adult Western, British correspondent in the West, 1958.",
    },
    {
        "slug": "have_gun",
        "title": "Have Gun, Will Travel",
        "ia_collection": "OTRR_Have_Gun_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Adult Western, 1958-60. Paladin.",
    },
    {
        "slug": "ranger_bill",
        "title": "Ranger Bill",
        "ia_collection": "OTRR_Ranger_Bill_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Christian children's adventure show — Moody Bible Institute, 1950-54. Faith substrate fit.",
    },
    {
        "slug": "american_history",
        "title": "American History Through The Eyes Of Radio",
        "ia_collection": "OTRR_American_History_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Historical dramatization compilation. History Channel programming fit.",
    },
    {
        "slug": "cbs_radio_workshop",
        "title": "CBS Radio Workshop",
        "ia_collection": "OTRR_CBS_Radio_Workshop_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Experimental literary anthology, 1956-57. Brave New World, etc.",
    },
    {
        "slug": "father_knows_best",
        "title": "Father Knows Best",
        "ia_collection": "OTRR_Father_Knows_Best_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Family drama, 1949-54.",
    },
    {
        "slug": "2000_plus",
        "title": "2000 Plus",
        "ia_collection": "OTRR_2000_Plus_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Sci-fi anthology, 1950-52. Original (not adapted) sci-fi.",
    },
    {
        "slug": "family_theater",
        "title": "Family Theater",
        "ia_collection": "OTRR_Family_Theater_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Father Patrick Peyton's Catholic family drama series, 1947-57. Faith substrate fit.",
    },
    {
        "slug": "lux_radio_theater",
        "title": "Lux Radio Theater",
        "ia_collection": "OTRR_Lux_Radio_Theater_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Hollywood adaptations of plays/films, 1934-55. High budget production.",
    },
    {
        "slug": "boston_blackie",
        "title": "Boston Blackie",
        "ia_collection": "OTRR_Boston_Blackie_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Reformed-thief crime drama, 1944-50.",
    },
    {
        "slug": "challenge_of_yukon",
        "title": "Challenge of the Yukon",
        "ia_collection": "OTRR_Challenge_of_the_Yukon_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Sergeant Preston + Yukon King, 1947-55. Northern adventure.",
    },
    {
        "slug": "nero_wolfe",
        "title": "New Adventures of Nero Wolfe",
        "ia_collection": "OTRR_New_Adventures_of_Nero_Wolfe_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Detective drama, 1950-51.",
    },
    {
        "slug": "great_gildersleeve",
        "title": "The Great Gildersleeve",
        "ia_collection": "Otrr_The_Great_Gildersleeve_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Sitcom, 1941-58. First spin-off in broadcasting history.",
    },
    {
        "slug": "richard_diamond",
        "title": "Richard Diamond, Private Detective",
        "ia_collection": "OTRR_Richard_Diamond_Private_Detective_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Light-hearted detective, 1949-53.",
    },
    {
        "slug": "frontier_town",
        "title": "Frontier Town",
        "ia_collection": "OTRR_Frontier_Town_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Western, 1949-51.",
    },
    {
        "slug": "weird_circle",
        "title": "Weird Circle",
        "ia_collection": "OTRR_Weird_Circle_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Gothic horror anthology, 1943-45. Adaptations of classic literature.",
    },
    {
        "slug": "mysterious_traveler",
        "title": "The Mysterious Traveler",
        "ia_collection": "OTRR_Mysterious_Traveler_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Mystery anthology, 1943-52.",
    },

    # ─────────────── AUDIOBOOKS (LibriVox PD) ───────────────
    # Each LibriVox audiobook is a single IA identifier with many MP3 files (one per chapter).
    # All LibriVox recordings are CC0 / public domain.
    {
        "slug": "lv_pilgrims_progress",
        "title": "Pilgrim's Progress (LibriVox)",
        "ia_collection": "pilgrims_progress_la_0902_librivox",
        "claimed_status": "PD recording (CC0); PD source text (Bunyan, 1678)",
        "formats": ["mp3", "ogg"],
        "category": "audiobook",
        "notes": "John Bunyan, classic of English Christian literature.",
    },
    {
        "slug": "lv_confessions_augustine",
        "title": "Confessions of St. Augustine (LibriVox)",
        "ia_collection": "confessions_augustine_2009_librivox",
        "claimed_status": "PD recording (CC0); PD source text",
        "formats": ["mp3", "ogg"],
        "category": "audiobook",
        "notes": "Augustine of Hippo, Pusey translation. Already in your substrate as text.",
    },
    {
        "slug": "lv_imitation_of_christ",
        "title": "The Imitation of Christ (LibriVox)",
        "ia_collection": "imitation_christ_1003_librivox",
        "claimed_status": "PD recording (CC0); PD source text",
        "formats": ["mp3", "ogg"],
        "category": "audiobook",
        "notes": "Thomas à Kempis, classic devotional. Already in your substrate as text.",
    },
    {
        "slug": "lv_aesops_fables",
        "title": "Aesop's Fables (LibriVox)",
        "ia_collection": "aesops_fables_volume_one_librivox",
        "claimed_status": "PD recording (CC0); PD ancient text",
        "formats": ["mp3", "ogg"],
        "category": "audiobook",
        "notes": "Townsend translation. Already in your substrate as text.",
    },
    {
        "slug": "lv_paradise_lost",
        "title": "Paradise Lost (LibriVox)",
        "ia_collection": "paradise_lost_librivox",
        "claimed_status": "PD recording; PD source (Milton 1667)",
        "formats": ["mp3", "ogg"],
        "category": "audiobook",
        "notes": "John Milton's epic.",
    },
    {
        "slug": "lv_divine_comedy",
        "title": "The Divine Comedy (LibriVox)",
        "ia_collection": "divine_comedy_dramatic_1601_librivox",
        "claimed_status": "PD recording; PD source",
        "formats": ["mp3", "ogg"],
        "category": "audiobook",
        "notes": "Dante's epic; Longfellow translation.",
    },
    {
        "slug": "lv_consolation_of_philosophy",
        "title": "Consolation of Philosophy (LibriVox)",
        "ia_collection": "consolation_philosophy_librivox",
        "claimed_status": "PD recording; PD source (Boethius)",
        "formats": ["mp3", "ogg"],
        "category": "audiobook",
        "notes": "Boethius. Already in your substrate as text.",
    },
    {
        "slug": "lv_meditations_marcus_aurelius",
        "title": "Meditations (LibriVox)",
        "ia_collection": "meditations_1107_librivox",
        "claimed_status": "PD recording; PD ancient source",
        "formats": ["mp3", "ogg"],
        "category": "audiobook",
        "notes": "Marcus Aurelius.",
    },

    # ─────────────── ANIMATION / CARTOONS ───────────────
    # Individual films / shorts. Verify per-item.
    {
        "slug": "fleischer_gullivers_travels",
        "title": "Gulliver's Travels (1939 Fleischer)",
        "ia_collection": "gullivers_travels1939",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "animation",
        "notes": "Fleischer Studios animated feature, 76 min.",
    },
    {
        "slug": "fleischer_betty_boop_snow_white",
        "title": "Betty Boop: Snow White (1933)",
        "ia_collection": "bb_snow_white",
        "claimed_status": "PD by year (pre-1929? or non-renewal)",
        "formats": ["mp4", "mpeg4", "h.264", "avi", "mov"],
        "category": "animation",
        "notes": "Fleischer Studios short, 7 min. Cab Calloway voice.",
    },

    # ─────────────── PD FEATURE FILMS ───────────────
    {
        "slug": "silent_phantom_opera",
        "title": "The Phantom of the Opera (1925)",
        "ia_collection": "ThePhantomoftheOpera",
        "claimed_status": "PD by year (1925, pre-1929 = PD by date in US)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "feature_film",
        "notes": "Lon Chaney, silent. PD by date.",
    },
    {
        "slug": "silent_20000_leagues",
        "title": "20,000 Leagues Under the Sea (1916)",
        "ia_collection": "20000LeaguesUndertheSea",
        "claimed_status": "PD by year (1916)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "feature_film",
        "notes": "Stuart Paton's silent adaptation of Jules Verne.",
    },
    # REMOVED 2026-05-16: soviet_voyage_planet + soviet_snow_queen.
    # Soviet content under Soyuzmultfilm/Mosfilm is permissive-use, not PD; won't
    # be PD within 1 year. Per Matt's strict PD rule, deleted from TARGETS + disk.

    # ── Complete animation series (Matt 2026-05-16: "all the complete... we can find") ──
    {
        "slug": "anim_fleischer_color_classics_complete",
        "title": "Max Fleischer's Color Classics — The Complete Collection (1934-1941)",
        "ia_collection": "max-fleischers-color-classics",
        "claimed_status": "PD by non-renewal (Fleischer Studios pre-1942)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "animation",
        "notes": "Fleischer's answer to Disney's Silly Symphonies. ~3 GB. Lighthouse Kids fit.",
    },
    {
        "slug": "anim_little_lulu_complete",
        "title": "Little Lulu — The Complete Collection (1943-48)",
        "ia_collection": "little-lulu-the-complete-collection-1943-48",
        "claimed_status": "PD by non-renewal (Famous Studios/Paramount)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "animation",
        "notes": "Famous Studios theatrical shorts. ~2.2 GB. Lighthouse Kids fit.",
    },
    {
        "slug": "anim_herman_katnip_complete",
        "title": "Herman and Katnip — The Complete Series",
        "ia_collection": "herman-and-katnip_202409",
        "claimed_status": "PD by non-renewal (Famous Studios)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "animation",
        "notes": "Famous Studios theatrical shorts. ~541 MB.",
    },
    {
        "slug": "anim_clutch_cargo_complete",
        "title": "Clutch Cargo — Complete Series (1959)",
        "ia_collection": "clutch-cargo",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "animation",
        "notes": "Classic Cambria Productions animation (Syncro-Vox lips). ~6.3 GB.",
    },

    # ─────────────── PRELINGER ARCHIVES (industrial / educational) ───────────────
    # 10,309 films available. We add a handful of popular ones; bulk acquisition would
    # use --category prelinger and a separate batch process.
    {
        "slug": "prelinger_about_bananas",
        "title": "About Bananas (1935)",
        "ia_collection": "AboutBan1935",
        "claimed_status": "PD by federal-employee rule / Prelinger Archives release",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "prelinger",
        "notes": "Iconic industrial film, 27M downloads.",
    },
    {
        "slug": "prelinger_health_posture",
        "title": "Health: Your Posture (1953)",
        "ia_collection": "HealthYo1953",
        "claimed_status": "PD",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "prelinger",
        "notes": "Health educational film.",
    },

    # ─────────────── MUSIC (78rpm sample) ───────────────
    # 187,018 78rpm records on IA. Curated sample for vintage music block.
    # Note: 78rpm collection is `georgeblood` — bulk via separate batch.
    {
        "slug": "78_house_rising_sun",
        "title": "House of the Rising Sun (Josh White, 1942)",
        "ia_collection": "78_house-of-the-rising-sun_josh-white-and-his-guitar_gbia0001628b",
        "claimed_status": "PD claimed via 78rpm collection",
        "formats": ["mp3", "ogg", "flac"],
        "category": "music_78rpm",
        "notes": "Josh White folk recording.",
    },

    # ─────────────── UNIVERSITY LECTURES (CC-BY-NC-SA — NC restriction!) ───────────────
    # MIT OCW + Yale Open Courses + Berkeley + Stanford = thousands of professor lectures
    # License caveat: most are CC-BY-NC-SA. NC = non-commercial only.
    #   → Main channel (free, no advertisers) qualifies as non-commercial
    #   → Sponsor-as-studio funded shows = commercial; NC fails
    #   → Cable-access tier with creator ads = commercial; NC fails
    # Quarantine handles this: items tagged "NC" require an extra broadcast-channel check.
    # REMOVED 2026-05-16: 3 MIT OCW lectures (linear_algebra / calculus_1 / physics_1).
    # CC-BY-NC-SA is NOT public domain — licensed terms (attribution, non-commercial,
    # share-alike). Per Matt's strict PD rule, deleted from TARGETS + disk.

    # ─────────────── EDUCATIONAL PD FILMS (how-to / informational / historical) ───────────────
    # Per Matt 2026-05-15: "How to videos that are public domain or any informational
    # or historical. Video from professors that we know is public."
    # These are individual films in the academic_films and prelinger educational collections.
    # Status: mostly PD by federal-employee rule OR PD by Prelinger Archives release.
    {
        "slug": "edu_frames_of_reference",
        "title": "Frames of Reference (1960)",
        "ia_collection": "frames_of_reference",
        "claimed_status": "PD (Educational Services Inc.)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "education",
        "notes": "Iconic physics educational film. Real-world examples of relativity / reference frames.",
    },
    {
        "slug": "edu_bacteria_friend_and_foe",
        "title": "Bacteria: Friend and Foe (1962)",
        "ia_collection": "bacteria_friend_and_foe",
        "claimed_status": "PD claimed via Prelinger",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "education",
        "notes": "Educational science film. 1.8M downloads — popular content.",
    },
    {
        "slug": "edu_intro_holography",
        "title": "Introduction to Holography",
        "ia_collection": "IntroductionToHolography",
        "claimed_status": "PD claimed via academic_films",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "education",
        "notes": "Educational physics film.",
    },
    {
        "slug": "edu_happy_city",
        "title": "Happy City",
        "ia_collection": "happy_city",
        "claimed_status": "PD claimed via academic_films",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "education",
        "notes": "Sociology / urban planning educational film.",
    },

    # ─────────────── HISTORICAL / NEWSREEL ───────────────
    # Pre-1929 newsreels = PD by date. Government newsreels often PD by federal-employee rule.
    {
        "slug": "hist_arrival_immigrants_1906",
        "title": "Arrival of Immigrants, Ellis Island (1906)",
        "ia_collection": "ArrivalOfImmigrants",
        "claimed_status": "PD by year (1906)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "history",
        "notes": "Billy Bitzer cinematography. Iconic early-1900s immigration footage.",
    },
    {
        "slug": "hist_casting_scene_1904",
        "title": "Casting Scene (1904)",
        "ia_collection": "CastingScene1904",
        "claimed_status": "PD by year (1904)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "history",
        "notes": "Billy Bitzer cinematography.",
    },
    {
        "slug": "hist_last_bomb_1945",
        "title": "The Last Bomb (1945)",
        "ia_collection": "TheLastBomb1945",
        "claimed_status": "PD by federal-employee rule (US military production)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "history",
        "notes": "USAAF WWII documentary. 1.13M downloads.",
    },

    # ─────────────── OBSERVATORY / SPACE / NASA ───────────────
    # All NASA productions PD by federal-employee rule.
    {
        "slug": "nasa_apollo11_16mm",
        "title": "Apollo 11 16mm Onboard Film",
        "ia_collection": "Apollo1116mmOnboardFilm",
        "claimed_status": "PD by federal-employee rule (NASA)",
        "formats": ["mp4", "mpeg4", "h.264", "avi", "mov"],
        "category": "observatory",
        "notes": "Iconic NASA footage. Moon landing primary source.",
    },
    {
        "slug": "nasa_scientific_method",
        "title": "NASA SCI Files - The Scientific Method",
        "ia_collection": "NasaSciFiles-TheScientificMethod",
        "claimed_status": "PD by federal-employee rule",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "observatory",
        "notes": "NASA educational. Good for kids/educational channels.",
    },
    {
        "slug": "nasa_arecibo_our_world",
        "title": "Our World: Arecibo - The Largest Radio Telescope",
        "ia_collection": "nasa_eclips_081009",
        "claimed_status": "PD by federal-employee rule",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "observatory",
        "notes": "Arecibo telescope (now collapsed). 165k downloads. Historical/educational.",
    },
    {
        "slug": "nasa_mission_patches",
        "title": "NASA Our World - Mission Patches",
        "ia_collection": "NASA_Our_World_Mission_Patches_HD",
        "claimed_status": "PD by federal-employee rule",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "observatory",
        "notes": "Mission patches series, educational.",
    },

    # ─────────────── GOVERNMENT DOCUMENTARIES (FedFlix) ───────────────
    # FedFlix collection: 22M downloads, thousands of government documentaries
    {
        "slug": "gov_fred_food_safety",
        "title": "Fred and the Voice of Food Safety: Food-Borne Illness",
        "ia_collection": "gov.ntis.ava18185vnb1",
        "claimed_status": "PD by federal-employee rule",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "documentary",
        "notes": "USDA / NTIS film, 2.3M downloads. How-to / informational.",
    },
    {
        "slug": "gov_fda_slide_show",
        "title": "FDA Approved - The Slide Show",
        "ia_collection": "gov.ntis.ava17487vnb1",
        "claimed_status": "PD by federal-employee rule",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "documentary",
        "notes": "FDA educational, 1.6M downloads.",
    },

    # ─────────────── EDUCATIONAL SCIENCE ───────────────
    {
        "slug": "edu_journey_triangle",
        "title": "Journey to the Center of a Triangle",
        "ia_collection": "journey_to_the_center_of_a_triangle",
        "claimed_status": "PD claimed via academic_films",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "education",
        "notes": "Math educational film, animated visualization.",
    },
    {
        "slug": "edu_congruent_triangles",
        "title": "Congruent Triangles",
        "ia_collection": "afana_congruent_triangles",
        "claimed_status": "PD claimed",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "education",
        "notes": "Geometry educational film.",
    },

    # ═══════════════════════════════════════════════════════════════
    # COMEDY — high-interest, audience-validated by download counts
    # Matt 2026-05-15 22:45: "Focus on most likely to be interesting. Comedy is a plus."
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "fibber_mcgee",
        "title": "Fibber McGee and Molly",
        "ia_collection": "fibber-mc-gee-and-molly",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Classic sitcom, 1935-59. 1,254 episodes — the closet gag was iconic. 256k downloads.",
    },
    {
        "slug": "jack_benny_1941_42",
        "title": "Jack Benny - Episodes 1941-1942",
        "ia_collection": "OTRR_Jack_Benny_Singles_1941-1942",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Peak-era Jack Benny — tight character comedy.",
    },
    {
        "slug": "jack_benny_1946_47",
        "title": "Jack Benny - Episodes 1946-1947",
        "ia_collection": "OTRR_Jack_Benny_Singles_1946-1947",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Post-war Jack Benny.",
    },
    {
        "slug": "jack_benny_1949_50",
        "title": "Jack Benny - Episodes 1949-1950",
        "ia_collection": "OTRR_Jack_Benny_Singles_1949-1950",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Late-stage Jack Benny — show at its mature peak.",
    },
    {
        "slug": "phil_harris_alice_faye",
        "title": "The Phil Harris-Alice Faye Show",
        "ia_collection": "OTRR_Harris_Faye_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Hollywood couple comedy. 200k downloads.",
    },
    {
        "slug": "halls_of_ivy",
        "title": "The Halls of Ivy",
        "ia_collection": "OTRR_Halls_Of_Ivy_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Ronald Colman comedy. College-president character. 159k downloads.",
    },
    {
        "slug": "evening_with_groucho",
        "title": "An Evening With Groucho",
        "ia_collection": "OTRR_An_Evening_With_Groucho_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Groucho Marx, 267k downloads.",
    },
    {
        "slug": "abbott_costello",
        "title": "Abbott and Costello",
        "ia_collection": "OTRR_Abbott_Costello_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Classic comedy duo. Who's on First.",
    },
    {
        "slug": "bing_crosby_clooney",
        "title": "The Bing Crosby-Rosemary Clooney Show",
        "ia_collection": "OTRR_BCRC_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Musical comedy, 1960. 87k downloads.",
    },
    {
        "slug": "damon_runyon_theatre",
        "title": "The Damon Runyon Theatre",
        "ia_collection": "OTRR_Damon_Runyon_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Damon Runyon short stories dramatized. Broadway humor. 174k downloads.",
    },
    {
        "slug": "mel_blanc_show",
        "title": "The Mel Blanc Show",
        "ia_collection": "OTRR_Mel_Blanc_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Mel Blanc (voice of Bugs/Daffy/etc.) comedy. 104k downloads.",
    },
    {
        "slug": "old_gold_comedy_theater",
        "title": "Old Gold Comedy Theater",
        "ia_collection": "OTRR_Old_Gold_Comedy_Theater_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Comedy anthology, 1944-45.",
    },
    {
        "slug": "duffys_tavern",
        "title": "Duffy's Tavern",
        "ia_collection": "OTRR_Duffys_Tavern_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Bar comedy with Archie the manager, 1941-51.",
    },
    {
        "slug": "my_friend_irma",
        "title": "My Friend Irma",
        "ia_collection": "OTRR_My_Friend_Irma_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Marie Wilson scatterbrained comedy.",
    },
    {
        "slug": "life_with_luigi",
        "title": "Life with Luigi",
        "ia_collection": "OTRR_Life_with_Luigi_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Italian immigrant in Chicago, J. Carrol Naish, 1948-53.",
    },
    {
        "slug": "danny_kaye_show",
        "title": "The Danny Kaye Show",
        "ia_collection": "OTRR_Danny_Kaye_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Variety + comedy, 1945-46.",
    },

    # ── Big complete-radio finds (Matt 2026-05-16: "all the complete radio series") ──
    {
        "slug": "radio_cbsrmt_complete",
        "title": "CBS Radio Mystery Theater — Complete Series (1399 episodes, 1974-1982)",
        "ia_collection": "cbsrmt-74-02-08-33-conspiracy-to-defraud",
        "claimed_status": "PD by notice failure / mass-distribution era",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "FLAGSHIP COMPLETE RADIO. ~910k downloads on IA. 1399 episodes / 16.3 GB. E. G. Marshall host.",
    },
    {
        "slug": "radio_cbsrmt_complete_alt",
        "title": "CBS Radio Mystery Theater — Complete Collection (alternate)",
        "ia_collection": "cbs_radio_mystery_theater",
        "claimed_status": "PD by notice failure",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Backup of CBSRMT. ~14.6 GB. Fills gaps in primary.",
    },
    {
        "slug": "radio_suspense_restored",
        "title": "SUSPENSE — Digitally Restored Complete Collection",
        "ia_collection": "SUSPENSE_Radio_Digitally_Restored_Collection",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "HQ restored version of the Suspense classic. ~10 GB.",
    },
    {
        "slug": "radio_bob_and_ray_complete",
        "title": "Bob & Ray — The Complete Collection",
        "ia_collection": "bobandraycompletecollection",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Legendary deadpan comedy. ~6.2 GB.",
    },
    {
        "slug": "radio_fibber_mcgee_15min",
        "title": "Fibber McGee & Molly — Complete 15-Minute Series (1953-1956)",
        "ia_collection": "fmm15minuteseries",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Later 15-min format. ~10.6 GB. Complements existing fibber_mcgee target.",
    },
    {
        "slug": "radio_cinnamon_bear_complete",
        "title": "The Cinnamon Bear — The Complete Radio Show",
        "ia_collection": "cinnamon-bear-1937-11-30-4-the-inkaboos",
        "claimed_status": "PD by year (1937)",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Christmas-season children's classic, 26 episodes. ~205 MB. Lighthouse Kids fit.",
    },
    {
        "slug": "radio_harry_lime_complete",
        "title": "The Lives of Harry Lime — Complete (Orson Welles)",
        "ia_collection": "lives-of-harry-lime-1951-08-17-3-clay-pigeon",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Orson Welles as Harry Lime from The Third Man. ~2.8 GB.",
    },
    {
        "slug": "radio_have_gun_complete",
        "title": "Have Gun, Will Travel — Complete Series (106 episodes)",
        "ia_collection": "have-gun-will-travel",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "John Dehner. 1958-60. Western. ~662 MB. Lean and complete.",
    },
    {
        "slug": "radio_zero_hour_complete",
        "title": "Zero Hour — Complete Series (130 episodes)",
        "ia_collection": "zero-hour-1974-02-06-38-a-die-in-the-country-chapter-3",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Rod Serling's 1973-74 radio drama anthology. ~940 MB.",
    },
    {
        "slug": "radio_i_love_adventure_complete",
        "title": "I Love Adventure — Complete Series",
        "ia_collection": "I_Love_Adventure",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "1948. Spin-off of I Love a Mystery. ~92 MB. Lean and complete.",
    },
    {
        "slug": "radio_frontier_gentleman_hq",
        "title": "Frontier Gentleman — Complete Series HQ",
        "ia_collection": "FrontierGentlemanHQ",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "John Dehner. 1958 western. Higher-quality version. ~911 MB.",
    },
    # REMOVED 2026-05-16: radio_navy_lark_1 + _2.
    # BBC archival = not PD; BBC retains rights into the future. Per strict PD rule.
    {
        "slug": "radio_orson_welles_shakespeare",
        "title": "Orson Welles — Shakespeare Collection",
        "ia_collection": "Orson_Welles_Shakespeare_Collection",
        "claimed_status": "PD source (Shakespeare); recording era PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Welles Shakespeare radio adaptations. ~803 MB.",
    },
    {
        "slug": "radio_christmas_mysteries_otr",
        "title": "Christmas Mysteries — Old-Time Radio Collection",
        "ia_collection": "ChristmasMysteriesCollection",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Themed Christmas mystery episodes for holiday rotation. ~1.2 GB.",
    },
    {
        "slug": "radio_horror_collection",
        "title": "Horror Collection — Old-Time Radio",
        "ia_collection": "HorrorCollection",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "radio",
        "notes": "Themed horror-radio collection. ~522 MB. Filter heavy via alignment gate.",
    },

    # ═══════════════════════════════════════════════════════════════
    # THEATRE — radio adaptations of plays, anthology drama
    # Matt 2026-05-15: "There is probably a lot of theatre productions too"
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "academy_award_theater",
        "title": "Academy Award Theater",
        "ia_collection": "OTRR_Academy_Award_Theater_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "theatre",
        "notes": "Oscar-winning film adaptations, 1946. Big stars. 166k downloads.",
    },
    {
        "slug": "screen_directors_playhouse",
        "title": "Screen Directors Playhouse",
        "ia_collection": "OTRR_Screen_Directors_Playhouse_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "theatre",
        "notes": "Film directors adapt their own films, 1949-51.",
    },
    {
        "slug": "theatre_royal",
        "title": "Theatre Royal",
        "ia_collection": "OTRR_Theatre_Royal_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "theatre",
        "notes": "Laurence Olivier hosted; classic literary adaptations.",
    },
    {
        "slug": "encore_theater",
        "title": "Encore Theater",
        "ia_collection": "OTRR_Encore_Theater_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "theatre",
        "notes": "Classic dramatic anthology re-presentations.",
    },
    {
        "slug": "matinee_theater",
        "title": "Matinee Theater",
        "ia_collection": "OTRR_Matinee_Theater_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "theatre",
        "notes": "Drama anthology.",
    },

    # LibriVox dramatized plays (CC0 recordings; PD source texts)
    {
        "slug": "lv_romeo_and_juliet",
        "title": "Romeo and Juliet (LibriVox)",
        "ia_collection": "romeo_and_juliet_librivox",
        "claimed_status": "PD recording (CC0); PD source (Shakespeare)",
        "formats": ["mp3", "ogg"],
        "category": "theatre",
        "notes": "Full Shakespeare play. 3.65M downloads — most popular LibriVox theatre.",
    },

    # ═══════════════════════════════════════════════════════════════
    # WESTERN — rodeo/cowboy cultural fit, Matt 2026-05-15 22:53
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "roy_rogers_show",
        "title": "The Roy Rogers Show",
        "ia_collection": "OTRR_Roy_Rogers_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "western",
        "notes": "Singing cowboy radio show, 1944-55.",
    },
    {
        "slug": "melody_ranch",
        "title": "Melody Ranch (Gene Autry)",
        "ia_collection": "OTRR_Melody_Ranch_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "western",
        "notes": "Gene Autry, singing cowboy, 1940-56.",
    },
    {
        "slug": "hopalong_cassidy",
        "title": "Hopalong Cassidy",
        "ia_collection": "OTRR_Hopalong_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "western",
        "notes": "William Boyd cowboy radio, 1950-52.",
    },
    {
        "slug": "wild_bill_hickok",
        "title": "Wild Bill Hickok",
        "ia_collection": "OTRR_Wild_Bill_Hickock_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "western",
        "notes": "Wild West radio adventure. 161k downloads.",
    },
    {
        "slug": "texas_rangers",
        "title": "Tales of the Texas Rangers",
        "ia_collection": "OTRR_Tales_of_the_Texas_Rangers_Single",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "western",
        "notes": "Joel McCrea, modern Texas Rangers, 1950-52. 134k downloads.",
    },
    {
        "slug": "tales_diamond_k",
        "title": "Tales of the Diamond K",
        "ia_collection": "OTRR_Tales_From_The_Diamond_K_Singles",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp3", "ogg"],
        "category": "western",
        "notes": "Western ranch tales.",
    },

    # ═══════════════════════════════════════════════════════════════
    # SPORTS — racing + rodeo PD films, Matt 2026-05-15
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "racing_speed_kings_1913",
        "title": "The Speed Kings (1913)",
        "ia_collection": "TheSpeedKings_1913",
        "claimed_status": "PD by year (1913)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "Early auto racing silent film. Sennett comedy with real racing footage.",
    },
    {
        "slug": "racing_silks_saddles_1921",
        "title": "Silks and Saddles (1921)",
        "ia_collection": "Silks_And_Saddles",
        "claimed_status": "PD by year (1921)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "Horse racing silent feature.",
    },
    {
        "slug": "racing_first_auto_1927",
        "title": "The First Auto (1927)",
        "ia_collection": "the-first-auto-1927_202507",
        "claimed_status": "PD by year (1927)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "Early automobile history film. Warner Bros silent.",
    },
    {
        "slug": "annie_oakley_1894",
        "title": "Annie Oakley (1894)",
        "ia_collection": "AnnieOakley",
        "claimed_status": "PD by year (1894)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "Edison film of Annie Oakley shooting. Wild West / sharpshooting heritage.",
    },
    {
        "slug": "rodeo_junior_daredevils_1949",
        "title": "Junior Rodeo Daredevils (1949)",
        "ia_collection": "0309_Junior_Rodeo_Daredevils_10_49_44_00",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "Rodeo newsreel. 47k downloads — popular niche.",
    },
    # REMOVED 2026-05-16: rodeo_1929 (borderline 1929 PD claim — under strict rule, deleted).
    {
        "slug": "sports_golden_years_1960",
        "title": "Golden Years (1960)",
        "ia_collection": "GoldenYe1960",
        "claimed_status": "PD claimed via Prelinger / sports collections",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "Sports newsreel compilation. 358k downloads.",
    },

    # ── Historic PD boxing — for "Top 10 / Greatest Knockouts / Boxing Legends" countdown content
    # (Matt 2026-05-16 "Sports highlights too. Top 10, Top 100, Best dunks ever, that stuff") ──
    {
        "slug": "sports_joe_louis_story_film",
        "title": "The Joe Louis Story (1953 biographical film)",
        "ia_collection": "TheJoeLouisStory",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "2.1 GB. Bio-pic; substrate for Joe Louis countdown. 61k downloads.",
    },
    {
        "slug": "sports_box_louis_vs_schmeling_1938",
        "title": "Joe Louis vs Max Schmeling II (June 22, 1938)",
        "ia_collection": "JoeLouisVsMaxSchmeling",
        "claimed_status": "PD by year (1938)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "**Most politically loaded fight in history.** 88 MB. PRIORITY content for highlight pieces.",
    },
    {
        "slug": "sports_box_schmeling_vs_louis_1936",
        "title": "Max Schmeling vs Joe Louis I (June 19, 1936)",
        "ia_collection": "MaxSchmelingVsJoeLouis",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "Schmeling's upset win. 508 MB.",
    },
    {
        "slug": "sports_box_louis_vs_braddock_1937",
        "title": "James Braddock vs Joe Louis (June 22, 1937)",
        "ia_collection": "JamesBraddockVsJoeLouis",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "Louis wins the title. 449 MB.",
    },
    {
        "slug": "sports_box_louis_vs_baer_1935",
        "title": "Max Baer vs Joe Louis (September 24, 1935)",
        "ia_collection": "MaxBaerVsJoeLouis",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "458 MB.",
    },
    {
        "slug": "sports_box_louis_vs_carnera_1935",
        "title": "Primo Carnera vs Joe Louis (June 25, 1935)",
        "ia_collection": "PrimoCarneraVsJoeLouis",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "365 MB. Louis early career.",
    },
    {
        "slug": "sports_box_louis_vs_sharkey_1936",
        "title": "Joe Louis vs Jack Sharkey (August 18, 1936)",
        "ia_collection": "JoeLouisVsJackSharkey",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "278 MB.",
    },
    {
        "slug": "sports_box_louis_brown_bomber_doc",
        "title": "Joe Louis — The Brown Bomber (1939 documentary)",
        "ia_collection": "JoeLouisTheBrownBomber",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "190 MB.",
    },
    {
        "slug": "sports_box_louis_in_training",
        "title": "Joe Louis in Training (1937)",
        "ia_collection": "JoeLouisInTraining",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "118 MB. Training-camp footage.",
    },
    {
        "slug": "sports_box_dempsey_willard_1919",
        "title": "Jack Dempsey vs Jess Willard (July 4, 1919) — title-winning KO",
        "ia_collection": "JackDempseyVsJessWillard",
        "claimed_status": "PD by year (1919)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "687 MB. Dempsey wins the title with 7 knockdowns in round 1. **Top-10 fight.**",
    },
    {
        "slug": "sports_box_dempsey_carpentier_1921",
        "title": "Jack Dempsey vs Georges Carpentier (July 2, 1921) — first million-dollar gate",
        "ia_collection": "JackDempseyVsGeorgesCarpentier",
        "claimed_status": "PD by year (1921)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "448 MB. First-ever million-dollar boxing gate.",
    },
    {
        "slug": "sports_box_dempsey_firpo_1923",
        "title": "Jack Dempsey vs Luis Firpo (September 14, 1923) — Dempsey-out-of-the-ring",
        "ia_collection": "JackDempseyVsLuisFirpo",
        "claimed_status": "PD by year (1923)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "160 MB. **Iconic** — Dempsey knocked through the ropes; helped back in.",
    },
    {
        "slug": "sports_box_dempsey_gibbons_1923",
        "title": "Jack Dempsey vs Tommy Gibbons (July 4, 1923)",
        "ia_collection": "JackDempseyVersusTommyGibbons",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "189 MB.",
    },
    {
        "slug": "sports_box_tunney_dempsey_1927",
        "title": "Gene Tunney vs Jack Dempsey II (September 22, 1927) — the 'Long Count'",
        "ia_collection": "GeneTunneyVersusJackDempsey",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "678 MB. **The Long Count Fight.** Most controversial referee call in heavyweight history.",
    },
    {
        "slug": "sports_box_dempsey_sharkey_1927",
        "title": "Jack Dempsey vs Jack Sharkey (July 21, 1927)",
        "ia_collection": "JackDempseyVsJackSharkey",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "498 MB.",
    },
    {
        "slug": "sports_box_dempsey_brennan_1920",
        "title": "Jack Dempsey vs Bill Brennan (December 14, 1920)",
        "ia_collection": "JackDempseyVsBillBrennan",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "184 MB.",
    },
    {
        "slug": "sports_box_dempsey_levinsky_1932",
        "title": "Jack Dempsey vs King Levinsky (February 18, 1932)",
        "ia_collection": "JackDempseyVsKingLevinsky",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "279 MB. Post-retirement exhibition.",
    },
    {
        "slug": "sports_box_dempsey_newsreel_1920s",
        "title": "Jack Dempsey Newsreel Compilation (1920s)",
        "ia_collection": "JackDempseyNewsreel1920s",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "244 MB. Mixed clips for highlight reels.",
    },
    {
        "slug": "sports_box_johnson_jeffries_1910",
        "title": "Jack Johnson vs James J. Jeffries (July 4, 1910) — 'Fight of the Century'",
        "ia_collection": "JackJohnsonVsJamesJJeffries",
        "claimed_status": "PD by year (1910)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "235 MB. The first 'Fight of the Century' — first black heavyweight champion defends.",
    },
    {
        "slug": "sports_box_johnson_burns_1908",
        "title": "Jack Johnson vs Tommy Burns (December 26, 1908) — Johnson wins title",
        "ia_collection": "JackJohnsonVsTommyBurns",
        "claimed_status": "PD by year (1908)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "234 MB. First Black heavyweight champion.",
    },
    {
        "slug": "sports_box_johnson_willard_1915",
        "title": "Jack Johnson vs Jess Willard (April 5, 1915)",
        "ia_collection": "JackJohnsonVsJessWillard",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "129 MB. Johnson loses title.",
    },
    {
        "slug": "sports_box_johnson_ketchel_1909",
        "title": "Jack Johnson vs Stanley Ketchel (October 16, 1909)",
        "ia_collection": "JackJohnsonVsStanleyKetchel",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "239 MB.",
    },
    {
        "slug": "sports_box_marciano_matthews_1952",
        "title": "Rocky Marciano vs Harry Matthews (July 28, 1952)",
        "ia_collection": "RockyMarcianoVsHarryMatthews",
        "claimed_status": "PD by year/non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "239 MB. Marciano pre-title.",
    },
    {
        "slug": "sports_olympics_paris_1924",
        "title": "The Olympic Games in Paris 1924 (silent feature)",
        "ia_collection": "silent-the-olympic-games-in-paris-1924",
        "claimed_status": "PD by year (1925 release)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "**15.6 GB.** Massive substrate for Olympic countdown content.",
    },
    {
        "slug": "sports_olympics_berlin_1936",
        "title": "Olympic Games Berlin 1936 (German production)",
        "ia_collection": "OlympicGamesBerlin1936German",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "398 MB. Jesse Owens-era; alignment-gate carefully (1936 was Nazi-host; surface athlete-stories not regime-context).",
    },

    # ── Old TV sports shows (Matt 2026-05-16) ──
    {
        "slug": "sports_home_run_derby_1960",
        "title": "Home Run Derby — Complete (1960, Mark Scott)",
        "ia_collection": "home-run-derby-s-01-e-02-mickey-mantle-vs-ernie-banks",
        "claimed_status": "PD by non-renewal (syndicated, Mark Scott died, copyright lapsed)",
        "formats": ["mp4", "mpeg4", "h.264", "avi", "mkv"],
        "category": "sports",
        "notes": "26-episode original. Mantle, Banks, Aaron, Mays. ~6.8 GB. PRIORITY: Matt specifically named this.",
    },
    {
        "slug": "sports_you_asked_for_it_1950",
        "title": "You Asked For It — Anthology (1950)",
        "ia_collection": "you_asked_for_it",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "Audience-request anthology (1950-59). Stunts, performances, oddities. 2.1 GB.",
    },
    {
        "slug": "sports_you_asked_lugosi",
        "title": "You Asked For It — Bela Lugosi episode",
        "ia_collection": "YouAskedForIt_BelaLugosi",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "Specific notable episode. 194 MB.",
    },
    {
        "slug": "sports_roller_derby_1949",
        "title": "Roller Derby — NY vs Philadelphia (1949)",
        "ia_collection": "1949-RollerDerby-NewYorkVsPhiladelphia",
        "claimed_status": "PD by year (1949)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "sports",
        "notes": "Original roller derby televised match. 854 MB.",
    },
    # NOTE: Patterson-Johansson 1959 boxing broadcast REMOVED 2026-05-16.
    # The fight as event isn't copyrightable, but the network television broadcast
    # of it is. PD claim too weak per Matt's "make sure they are PD" directive.

    # ═══════════════════════════════════════════════════════════════
    # FISHING — old outdoor TV shows (Matt 2026-05-16: "really fun")
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "fishing_gabby_goes_1941",
        "title": "Gabby Goes Fishing (1941)",
        "ia_collection": "Gabby_Goes_Fishing_1941",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "fishing",
        "notes": "Animated short. 46k downloads. Lighthouse Kids fit. ~192 MB.",
    },
    {
        "slug": "fishing_my_hero_story_1953",
        "title": "My Hero — The Fishing Story (1953)",
        "ia_collection": "MyHero-FishingStory",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "fishing",
        "notes": "Sitcom episode about fishing. 1.1 GB.",
    },
    {
        "slug": "fishing_vagabonds_1955",
        "title": "Fishing Vagabonds (1955)",
        "ia_collection": "0351_Fishing_Vagabonds_05_17_31_00",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "fishing",
        "notes": "Outdoor fishing travelogue. 309 MB.",
    },
    {
        "slug": "fishing_cobb_goes_1930",
        "title": "Cobb Goes Fishing (1930)",
        "ia_collection": "oacobb-goes-fishing",
        "claimed_status": "PD by year (1930)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "fishing",
        "notes": "Ty Cobb fishing — baseball legend in retirement. 256 MB. Crossover sports + fishing.",
    },
    {
        "slug": "fishing_silent_1921",
        "title": "Fishing (1921, silent)",
        "ia_collection": "silent-fishing",
        "claimed_status": "PD by year (1921)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "fishing",
        "notes": "Silent fishing film. 134 MB.",
    },
    {
        "slug": "fishing_by_the_sea_1947",
        "title": "Fishing by the Sea (1947)",
        "ia_collection": "fishing-by-the-sea-1947",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "fishing",
        "notes": "1947 educational/promotional fishing short. 37 MB.",
    },

    # ═══════════════════════════════════════════════════════════════
    # CABLE ACCESS — REMOVED 2026-05-16 per Matt's "make sure they are PD" directive.
    # Public access TV is owned by individual producers; not PD even when IA hosts.
    # Future path: direct permission outreach to producers, then sponsor-as-studio-tier
    # inclusion. Not an acquisition target.
    # ═══════════════════════════════════════════════════════════════

    # ═══════════════════════════════════════════════════════════════
    # PERFORMANCES — Soundies, Lawrence Welk, vintage live music
    # Matt 2026-05-16: "original live performances"
    # Soundies = 1940s music-video shorts shown in Panoram jukeboxes; all PD.
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "perf_soundies_master",
        "title": "Soundies — Master Collection",
        "ia_collection": "AFP-37BJ_NET_352",
        "claimed_status": "PD by year (1940s)",
        "formats": ["mp4", "mpeg4", "h.264", "avi", "mkv"],
        "category": "performances",
        "notes": "Soundies master compilation. 13.9 GB. Foundation of the performances category.",
    },
    {
        "slug": "perf_soundies_black_music_1940",
        "title": "Soundies — Black Music (1940)",
        "ia_collection": "0751_Soundies_Black_Music_15_01_07_00",
        "claimed_status": "PD by year (1940)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "performances",
        "notes": "Cab Calloway / Louis Armstrong / Fats Waller era. 802 MB.",
    },
    {
        "slug": "perf_aa_soundies_armstrong_calloway",
        "title": "African American Soundies 1940s — Calloway / Armstrong / Waller",
        "ia_collection": "xd-38984c-official-films-african-americanand-southern-soundies-vwr",
        "claimed_status": "PD by year",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "performances",
        "notes": "Featured-artist compilation. 223 MB.",
    },
    {
        "slug": "perf_aa_soundies_bessie_smith",
        "title": "African American Soundies 1930s — Bessie Smith / James P. Johnson",
        "ia_collection": "xd-44594-african-american-sounds-bessie-smith-vwr",
        "claimed_status": "PD by year (1930s)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "performances",
        "notes": "St. Louis Blues etc. 599 MB.",
    },
    # NOTE: Lawrence Welk Pilot 1955 entry REMOVED 2026-05-16 — PD claim contested;
    # ABC's archive disputes lapse. The 1934 orchestra material below is solidly PD by year.
    {
        "slug": "perf_lawrence_welk_orchestra_1934",
        "title": "Lawrence Welk Orchestra (1934)",
        "ia_collection": "1934-USA-Archives-1934-00-00-Lawrence-Welk-Orchestra-001",
        "claimed_status": "PD by year (1934)",
        "formats": ["mp4", "mpeg4", "h.264", "avi", "mp3"],
        "category": "performances",
        "notes": "Earliest Welk material. 2.6 MB.",
    },
    # NOTE: Hank Williams "I Saw the Light" 1952 RECORDING entry REMOVED 2026-05-16.
    # Williams song lyrics are PD as of 2024 (life+70 since his 1953 death), but the
    # 1952 RECORDING is protected until 2047 (pre-1972 sound recording rule).
    # To use this song: re-record under a CC0 license, or wait for sound-recording PD.
    {
        "slug": "perf_ted_weems_cheer_up_1930",
        "title": "Ted Weems and His Orchestra — Cheer Up, Good Times Are Coming! (1930)",
        "ia_collection": "TedWeemsAndHisOrchestraCheerUp1930480p25fpsH264128kbitAAC",
        "claimed_status": "PD by year (1930)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "performances",
        "notes": "Depression-era hopeful song. 17 MB.",
    },
    {
        "slug": "perf_felix_prologues_1925",
        "title": "Felix Prologues (1925)",
        "ia_collection": "FelixPrologues",
        "claimed_status": "PD by year (1925)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "performances",
        "notes": "Felix the Cat live-action introduction reel. 16 MB.",
    },

    # ═══════════════════════════════════════════════════════════════
    # VEGAS — old Las Vegas variety / Liberace (Matt 2026-05-16: "old vegas shows")
    # The Liberace Show (1952-1955 syndicated) is a strong PD-by-non-renewal vein.
    # Sinatra Timex Show entries are MIXED PD (CBS/ABC renewed most) — excluded.
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "vegas_liberace_christmas_1954",
        "title": "The Liberace Show — 1954 Christmas Episode",
        "ia_collection": "TheLiberaceShow-1954ChristmasEpisode",
        "claimed_status": "PD by non-renewal (Guild Films syndication)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "vegas",
        "notes": "Top-downloaded Liberace episode. 19k downloads. 520 MB. Christmas-rotation fit.",
    },
    {
        "slug": "vegas_liberace_thanksgiving",
        "title": "The Liberace Show — Thanksgiving",
        "ia_collection": "Liberace_Thanksgiving",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "vegas",
        "notes": "Holiday-rotation fit. 360 MB.",
    },
    {
        "slug": "vegas_liberace_great_personalities",
        "title": "The Liberace Show — Great Personalities",
        "ia_collection": "theLiberaceShow-GreatPersonalities",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "vegas",
        "notes": "850 MB.",
    },
    {
        "slug": "vegas_liberace_san_francisco",
        "title": "The Liberace Show — San Francisco (1952)",
        "ia_collection": "LiberaceSanFrancisco",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "vegas",
        "notes": "1.4 GB.",
    },
    {
        "slug": "vegas_liberace_american_composers",
        "title": "Liberace — American Composers (1956)",
        "ia_collection": "liberace-Americancomposers",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "vegas",
        "notes": "Tribute to American composers. 880 MB.",
    },
    {
        "slug": "vegas_liberace_great_ladies",
        "title": "Liberace — Tribute to the Great Ladies in Theatre (1955)",
        "ia_collection": "LiberaceTributetothegreatladiesofthetheatre",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "vegas",
        "notes": "900 MB.",
    },
    {
        "slug": "vegas_liberace_personal_holidays",
        "title": "The Liberace Show — Personal Holidays (1956)",
        "ia_collection": "LiberacePersonalHolidays",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "vegas",
        "notes": "1.4 GB.",
    },
    {
        "slug": "vegas_liberace_tiger_rag_soundie",
        "title": "Liberace — Tiger Rag (Soundie 1950)",
        "ia_collection": "soundie-liberace-tiger-rag",
        "claimed_status": "PD by year (1950)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "vegas",
        "notes": "Early Liberace short. 50 MB.",
    },
    {
        "slug": "vegas_las_vegas_story_1952",
        "title": "The Las Vegas Story (1952, RKO)",
        "ia_collection": "the-las-vegas-story-1952-jane-russell-vincent-price-1",
        "claimed_status": "PD by non-renewal (RKO library; Howard Hughes era)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "vegas",
        "notes": "Jane Russell + Vincent Price. RKO film noir. 2 GB.",
    },
    {
        "slug": "vegas_jack_benny_liberace_1954",
        "title": "The Jack Benny Program — Liberace Show (S04e07, 1954)",
        "ia_collection": "540117TheJackBennyProgramS04e07LiberaceShow",
        "claimed_status": "PD by non-renewal (Jack Benny syndication)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "vegas",
        "notes": "Jack Benny hosts Liberace. 210 MB.",
    },
    {
        "slug": "vegas_jack_benny_las_vegas_1961",
        "title": "The Jack Benny Program — Las Vegas Show (S11e22, 1961)",
        "ia_collection": "610319TheJackBennyProgramS11e22LasVegasShow",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "vegas",
        "notes": "Jack Benny Vegas-themed episode. 180 MB.",
    },

    # ═══════════════════════════════════════════════════════════════
    # MAGAZINES — render as webpages / curate articles (Matt 2026-05-16)
    # Bulk PD magazine archives: pre-1929 by year; some 1929-1964 by non-renewal.
    # Popular Mechanics 1936-1938 + Popular Science decade-bundles are well-verified PD.
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "mag_popular_science_1900_1909",
        "title": "Popular Science Monthly — Selected 1900-1909 (PD by year)",
        "ia_collection": "popularsciencemo60newy",
        "claimed_status": "PD by year (pre-1929)",
        "formats": ["pdf", "epub", "txt"],
        "category": "magazines",
        "notes": "Representative early issue (1901). Pre-1929 = PD. We seed; ingest more later.",
    },
    {
        "slug": "mag_popular_science_1920_1924",
        "title": "Popular Science — 1920 to 1924 (Bulk)",
        "ia_collection": "1920-to-1924-popular-science",
        "claimed_status": "PD by year (pre-1929)",
        "formats": ["pdf", "epub", "txt"],
        "category": "magazines",
        "notes": "5-year bulk archive. 9.5k downloads. Solid PD.",
    },
    {
        "slug": "mag_popular_science_1925_1929",
        "title": "Popular Science — 1925 to 1929 (Bulk)",
        "ia_collection": "1925-to-1929-popular-science",
        "claimed_status": "PD by year (pre-1929) for most; 1929 individual issue varies",
        "formats": ["pdf", "epub", "txt"],
        "category": "magazines",
        "notes": "5-year bulk archive.",
    },
    {
        "slug": "mag_popular_mechanics_1936",
        "title": "Popular Mechanics 1936 (Complete Year)",
        "ia_collection": "PopularMechanics1936",
        "claimed_status": "PD by non-renewal",
        "formats": ["pdf", "epub", "txt"],
        "category": "magazines",
        "notes": "50k downloads. Full year of issues.",
    },
    {
        "slug": "mag_popular_mechanics_1937",
        "title": "Popular Mechanics 1937 (Complete Year)",
        "ia_collection": "PopularMechanics1937",
        "claimed_status": "PD by non-renewal",
        "formats": ["pdf", "epub", "txt"],
        "category": "magazines",
        "notes": "35k downloads.",
    },
    {
        "slug": "mag_popular_mechanics_1938",
        "title": "Popular Mechanics 1938 (Complete Year)",
        "ia_collection": "PopularMechanics1938",
        "claimed_status": "PD by non-renewal",
        "formats": ["pdf", "epub", "txt"],
        "category": "magazines",
        "notes": "51k downloads.",
    },
    {
        "slug": "mag_saturday_evening_post_1918",
        "title": "The Saturday Evening Post (Oct-Dec 1918)",
        "ia_collection": "ElgwAQAAMAAJ",
        "claimed_status": "PD by year (1918)",
        "formats": ["pdf", "epub", "txt"],
        "category": "magazines",
        "notes": "Norman Rockwell era. Solid PD. 6.8k downloads.",
    },
    {
        "slug": "mag_saturday_evening_post_1922_q2",
        "title": "The Saturday Evening Post (Apr-Jun 1922)",
        "ia_collection": "JCkkAQAAMAAJ",
        "claimed_status": "PD by year (1922)",
        "formats": ["pdf", "epub", "txt"],
        "category": "magazines",
        "notes": "Q2 1922 issues bundle.",
    },
    {
        "slug": "mag_saturday_evening_post_1920_47",
        "title": "The Saturday Evening Post — Vol 192 Iss 47 (May 22, 1920)",
        "ia_collection": "sim_saturday-evening-post_1920-05-22_192_47",
        "claimed_status": "PD by year (1920)",
        "formats": ["pdf", "epub", "txt"],
        "category": "magazines",
        "notes": "Individual issue, Rockwell era.",
    },
    {
        "slug": "mag_boys_life_1915",
        "title": "Boys' Life Magazine (1915)",
        "ia_collection": "boyslife191500boys",
        "claimed_status": "PD by year",
        "formats": ["pdf", "epub", "txt"],
        "category": "magazines",
        "notes": "17.9k downloads. Boy Scout era classic. Lighthouse Kids fit.",
    },
    {
        "slug": "mag_mechanics_young_america_1905",
        "title": "Mechanics for Young America (1905)",
        "ia_collection": "mechanicsforyoun00chic",
        "claimed_status": "PD by year (1905)",
        "formats": ["pdf", "epub", "txt"],
        "category": "magazines",
        "notes": "Period DIY book for boys. 5.2k downloads.",
    },

    # ═══════════════════════════════════════════════════════════════
    # CHILDREN — Lighthouse Kids deck source content
    # Matt 2026-05-16: "Children's books and content"
    # All LibriVox audiobooks (CC0 recordings, PD source texts).
    # Massive audience signal: Alice 24M dl, Secret Garden 6.7M dl, etc.
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "kids_alice_in_wonderland",
        "title": "Alice's Adventures in Wonderland",
        "ia_collection": "alice_in_wonderland_librivox",
        "claimed_status": "PD source (1865); CC0 LibriVox recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "Lewis Carroll. **24M downloads — most popular LibriVox audiobook of all.**",
    },
    {
        "slug": "kids_wizard_of_oz",
        "title": "The Wonderful Wizard of Oz",
        "ia_collection": "wizard_of_oz",
        "claimed_status": "PD source (1900); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "L. Frank Baum. 3.5M downloads.",
    },
    {
        "slug": "kids_peter_pan",
        "title": "Peter Pan",
        "ia_collection": "peter_pan_0707_librivox",
        "claimed_status": "PD source (1911); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "J.M. Barrie. 6.8M downloads.",
    },
    {
        "slug": "kids_secret_garden",
        "title": "The Secret Garden",
        "ia_collection": "secret_garden_librivox",
        "claimed_status": "PD source (1911); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "Frances Hodgson Burnett. 6.7M downloads.",
    },
    {
        "slug": "kids_anne_green_gables",
        "title": "Anne of Green Gables",
        "ia_collection": "anne_greengables_librivox",
        "claimed_status": "PD source (1908); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "Lucy Maud Montgomery. 3.6M downloads.",
    },
    {
        "slug": "kids_black_beauty",
        "title": "Black Beauty",
        "ia_collection": "blackbeauty_librivox",
        "claimed_status": "PD source (1877); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "Anna Sewell. 1.6M downloads.",
    },
    {
        "slug": "kids_wind_willows",
        "title": "The Wind in the Willows",
        "ia_collection": "wind_in_the_willows_collab_librivox",
        "claimed_status": "PD source (1908); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "Kenneth Grahame. 959k downloads.",
    },
    {
        "slug": "kids_just_so_stories",
        "title": "Just So Stories",
        "ia_collection": "just_so_stories",
        "claimed_status": "PD source (1902); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "Rudyard Kipling. Animal-origin tales. 243k downloads.",
    },
    {
        "slug": "kids_winnie_the_pooh",
        "title": "Winnie-the-Pooh",
        "ia_collection": "winniethepooh_2201_librivox",
        "claimed_status": "PD source (1926, entered US PD 2022); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "A.A. Milne. Recently entered PD (2022).",
    },
    {
        "slug": "kids_house_at_pooh_corner",
        "title": "The House at Pooh Corner",
        "ia_collection": "house_pooh_corner_2401_librivox",
        "claimed_status": "PD source (1928, entered US PD 2024); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "A.A. Milne sequel. Introduces Tigger. Entered PD Jan 1, 2024.",
    },
    {
        "slug": "kids_when_we_were_very_young",
        "title": "When We Were Very Young",
        "ia_collection": "whenweweresix_1903_librivox",
        "claimed_status": "PD source (1924, entered US PD 2020); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "A.A. Milne poems. First appearance of Edward Bear (proto-Pooh). PD since 2020.",
    },
    {
        "slug": "kids_now_we_are_six",
        "title": "Now We Are Six",
        "ia_collection": "now_we_are_six_1909_librivox",
        "claimed_status": "PD source (1927, entered US PD 2023); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "A.A. Milne poems featuring Christopher Robin and Pooh. PD since 2023.",
    },
    {
        "slug": "kids_velveteen_rabbit",
        "title": "The Velveteen Rabbit",
        "ia_collection": "velveteenduet_librivox",
        "claimed_status": "PD source (1922); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "Margery Williams. Theological resonance — the becoming-real story.",
    },
    {
        "slug": "kids_beatrix_potter_treasury",
        "title": "Great Big Treasury of Beatrix Potter",
        "ia_collection": "potter_treasury_librivox",
        "claimed_status": "PD source (1901-1930s most PD); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "Peter Rabbit + Squirrel Nutkin + many. 457k downloads.",
    },
    {
        "slug": "kids_andersen_fairy_tales",
        "title": "Hans Christian Andersen Fairy Tales (Vol 1)",
        "ia_collection": "andersenfairytalesvol1_1204_librivox",
        "claimed_status": "PD source (19th century); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "Andersen died 1875. The Snow Queen, Little Mermaid, Ugly Duckling, etc.",
    },
    {
        "slug": "kids_blue_fairy_book",
        "title": "The Blue Fairy Book",
        "ia_collection": "blue_fairy_book_0707_librivox",
        "claimed_status": "PD source (1889); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "Andrew Lang's first Fairy Book. 1.1M downloads. (11 more colors available.)",
    },
    {
        "slug": "kids_mother_goose_prose",
        "title": "Mother Goose in Prose",
        "ia_collection": "mother_goose_prose_librivox",
        "claimed_status": "PD source (1897); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "L. Frank Baum's nursery-rhyme expansions. 1.1M downloads.",
    },
    {
        "slug": "kids_alice_drama",
        "title": "Alice in Wonderland (Dramatic Reading)",
        "ia_collection": "aliceinwonderland_drama_1310_librivox",
        "claimed_status": "PD source; CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "children",
        "notes": "Multi-voice dramatic reading — better than solo for kids' listening.",
    },

    # ═══════════════════════════════════════════════════════════════
    # COMIC BOOKS — Golden Age PD (non-renewal lapse)
    # Matt 2026-05-16: "comic books?"
    # ═══════════════════════════════════════════════════════════════
    # REMOVED 2026-05-16: comic_action_comics_1_to_200.
    # DC Comics actively asserts copyright on Superman and Action Comics. Mixed PD
    # claim too weak. Per strict PD rule, deleted. (#1 1938 becomes PD in 2034.)
    {
        "slug": "comic_plastic_man_v1_001",
        "title": "Plastic Man Vol 1 #001 (Quality Comics, 1943)",
        "ia_collection": "PlasticManV1001",
        "claimed_status": "PD by non-renewal (Quality Comics)",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "Jack Cole's Plastic Man — clearly PD.",
    },
    {
        "slug": "comic_daredevil_lev_gleason_01",
        "title": "Daredevil Comics #1 (Lev Gleason, 1941)",
        "ia_collection": "daredevilcomics01c2clevgleason1941julytitanfan",
        "claimed_status": "PD by non-renewal (Lev Gleason)",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "Daredevil Battles Hitler — NOT the Marvel character. Lev Gleason's original.",
    },
    {
        "slug": "comic_silver_streak_009",
        "title": "Silver Streak Comics #009",
        "ia_collection": "SilverStreakComics009",
        "claimed_status": "PD by non-renewal",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "Silver Streak / The Claw — Lev Gleason golden-age PD.",
    },
    {
        "slug": "comic_captain_marvel_thrill_book",
        "title": "Captain Marvel Thrill Book #001 (Fawcett, 1941)",
        "ia_collection": "captain-marvel-thrill-book",
        "claimed_status": "PD by non-renewal (Fawcett Publications)",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "Original Captain Marvel (Shazam). Fawcett's PD universe.",
    },
    {
        "slug": "comic_sub_mariner_001",
        "title": "Sub-Mariner Comics Vol 1 #001 (Timely, 1941)",
        "ia_collection": "sub-mariner-comics-vol-1-001-c2c",
        "claimed_status": "PD by non-renewal (Timely/Atlas pre-Marvel)",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "Bill Everett's Sub-Mariner. Timely-era (pre-Marvel rebrand). Verify renewal.",
    },
    # REMOVED 2026-05-16: comic_batman_1940_1_to_50.
    # DC actively asserts on Batman. Per strict PD rule.

    # ── Fawcett / Quality / Fox PD comic runs (Matt 2026-05-16: comics as well) ──
    # Fawcett Comics: PD by non-renewal after Fawcett left comics in 1953 (DC settlement)
    {
        "slug": "comic_captain_marvel_adv_001",
        "title": "Captain Marvel Adventures #001 (Fawcett, 1941)",
        "ia_collection": "Captain_Marvel_Adventures_001_Reprint",
        "claimed_status": "PD by non-renewal (Fawcett ceased comics 1953)",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "Original Captain Marvel / Shazam. Top Fawcett title. Full series 1-150 available across IA.",
    },
    {
        "slug": "comic_captain_marvel_adv_148",
        "title": "Captain Marvel Adventures #148 (Fawcett, final issue, 1953)",
        "ia_collection": "Captain_Marvel_Adventures_148",
        "claimed_status": "PD by non-renewal",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "Final issue. Bookend to the run.",
    },
    {
        "slug": "comic_bulletman_001",
        "title": "Bulletman #001 (Fawcett, 1941)",
        "ia_collection": "bulletman-comics-01",
        "claimed_status": "PD by non-renewal (Fawcett)",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "Bulletman: detective-turned-superhero. Fawcett era.",
    },
    {
        "slug": "comic_spy_smasher_006",
        "title": "Spy Smasher #6 (Fawcett, 1942)",
        "ia_collection": "Spy_Smasher_6",
        "claimed_status": "PD by non-renewal (Fawcett)",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "WWII-era Fawcett patriotic hero.",
    },
    {
        "slug": "comic_blue_beetle_021",
        "title": "Blue Beetle #021 (Fox, 1955)",
        "ia_collection": "BlueBeetle0211955",
        "claimed_status": "PD by non-renewal (Fox Publications)",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "Blue Beetle Fox-era run.",
    },
    {
        "slug": "comic_blue_beetle_v5_001",
        "title": "Blue Beetle V5 #001 (Fox)",
        "ia_collection": "BlueBeetleV5001",
        "claimed_status": "PD by non-renewal (Fox)",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "Volume 5 series start.",
    },
    {
        "slug": "comic_fawcett_marvel_coloring_1941",
        "title": "Fawcett Captain Marvel Coloring Book (1941)",
        "ia_collection": "fawcett_Captain_Marvel_Coloring_Book_1941",
        "claimed_status": "PD by non-renewal (Fawcett)",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "Kids-friendly Captain Marvel coloring book. Lighthouse Kids fit.",
    },

    # ── More complete comic-series collections (Matt 2026-05-16: complete series) ──
    # REMOVED 2026-05-16: comic_turok_son_of_stone_complete.
    # Mixed PD; later issues actively owned by Gold Key/Western successor. Per strict PD rule.
    {
        "slug": "comic_exotic_romances_complete",
        "title": "Exotic Romances — Complete Series #22-31 (1955)",
        "ia_collection": "exotic-romances-comic-collection",
        "claimed_status": "PD by non-renewal",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "Romance genre — alignment-gate carefully, may filter heavily.",
    },
    {
        "slug": "comic_true_war_romances_complete",
        "title": "True War Romances — Complete (1952-1954, issues 1-21)",
        "ia_collection": "true-war-romances-04-jan-1953-true-war-romances-comic",
        "claimed_status": "PD by non-renewal",
        "formats": ["cbz", "cbr", "pdf"],
        "category": "comics",
        "notes": "Period romance comics. Alignment-gate check on content.",
    },

    # ═══════════════════════════════════════════════════════════════
    # BOARD GAME REFERENCE — PD Hoyle rulebooks for Games-deck implementation
    # Matt 2026-05-16: "any boardgame that is out of copyright"
    # These are RULES SOURCES — used as authoritative reference when building
    # multiplayer card/board game cards in the Games deck.
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "bg_hoyle_backgammon_1743",
        "title": "A Short Treatise on the Game of Back-Gammon (Hoyle, 1743)",
        "ia_collection": "bim_eighteenth-century_a-short-treatise-on-the-_hoyle-edmond_1743_2",
        "claimed_status": "PD by year (1743) — oldest extant Hoyle",
        "formats": ["pdf", "epub", "txt"],
        "category": "board_games_reference",
        "notes": "Edmond Hoyle's original backgammon treatise. Authoritative ancient rules.",
    },
    {
        "slug": "bg_bohns_handbook_1851",
        "title": "Bohn's New Hand-Book of Games (1851)",
        "ia_collection": "bohnsnewhandboo00hoylgoog",
        "claimed_status": "PD by year (1851)",
        "formats": ["pdf", "epub", "txt"],
        "category": "board_games_reference",
        "notes": "Whist, piquet, chess, draughts, backgammon — period rules.",
    },
    {
        "slug": "bg_american_hoyle_1875",
        "title": "The American Hoyle — Gentleman's Hand-book of Games (1875)",
        "ia_collection": "americanhoyleorg00dick_1",
        "claimed_status": "PD by year (1875)",
        "formats": ["pdf", "epub", "txt"],
        "category": "board_games_reference",
        "notes": "Top-downloaded Hoyle on IA (4900+). Comprehensive 19c rules reference.",
    },
    {
        "slug": "bg_book_of_games_1886",
        "title": "The Book of Games (1886)",
        "ia_collection": "bookofgames00stod",
        "claimed_status": "PD by year (1886)",
        "formats": ["pdf", "epub", "txt"],
        "category": "board_games_reference",
        "notes": "Broad rules reference.",
    },
    {
        "slug": "bg_handbook_games_pastimes_1887",
        "title": "Hand Book of Games and Pastimes (1887)",
        "ia_collection": "handbookofgamesp00chic",
        "claimed_status": "PD by year (1887)",
        "formats": ["pdf", "epub", "txt"],
        "category": "board_games_reference",
        "notes": "Period family pastimes book.",
    },
    {
        "slug": "bg_book_of_games_directions_1898",
        "title": "The Book of Games, with Directions How to Play Them (1898)",
        "ia_collection": "bookofgameswithd02whit",
        "claimed_status": "PD by year (1898)",
        "formats": ["pdf", "epub", "txt"],
        "category": "board_games_reference",
        "notes": "Top-downloaded period rule book on IA (7200+).",
    },
    {
        "slug": "bg_fosters_complete_hoyle_1909",
        "title": "Foster's Complete Hoyle — Encyclopedia of Games (1909)",
        "ia_collection": "fosterscomplete02fostgoog",
        "claimed_status": "PD by year (1909)",
        "formats": ["pdf", "epub", "txt"],
        "category": "board_games_reference",
        "notes": "R.F. Foster's authoritative comprehensive edition.",
    },
    {
        "slug": "bg_hoyles_games_america_1920",
        "title": "Hoyle's Games — America's Complete Hand-book (1920)",
        "ia_collection": "hoylesgamesameri00hoyl",
        "claimed_status": "PD by year (1920)",
        "formats": ["pdf", "epub", "txt"],
        "category": "board_games_reference",
        "notes": "Cleanest 20c American edition. Use as primary build reference.",
    },
    {
        "slug": "bg_book_of_games_parties_1920",
        "title": "The Book of Games and Parties for All Occasions (1920)",
        "ia_collection": "bookofgamesparti00wolcuoft",
        "claimed_status": "PD by year (1920)",
        "formats": ["pdf", "epub", "txt"],
        "category": "board_games_reference",
        "notes": "Family party games — Lighthouse Kids deck source material.",
    },
    {
        "slug": "bg_kate_greenaway_book_of_games_1889",
        "title": "Kate Greenaway's Book of Games (1889)",
        "ia_collection": "kategreenawaysbo00gree",
        "claimed_status": "PD by year (1889)",
        "formats": ["pdf", "epub", "txt"],
        "category": "board_games_reference",
        "notes": "Classic illustrated children's-games book.",
    },

    # ═══════════════════════════════════════════════════════════════
    # PULP MAGAZINES — sci-fi, horror, detective source fiction
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "pulp_amazing_stories_v01n01",
        "title": "Amazing Stories Vol 1 No 1 (1926)",
        "ia_collection": "AmazingStoriesVolume01Number01",
        "claimed_status": "PD by year (1926)",
        "formats": ["pdf", "epub", "txt"],
        "category": "pulp",
        "notes": "First sci-fi magazine. Hugo Gernsback. Source for adaptation.",
    },
    {
        "slug": "pulp_weird_tales_v01n01",
        "title": "Weird Tales Vol 1 No 1 (1923)",
        "ia_collection": "WeirdTalesV01n01192303",
        "claimed_status": "PD by year (1923)",
        "formats": ["pdf", "epub", "txt"],
        "category": "pulp",
        "notes": "First Weird Tales — Lovecraft + Howard published here.",
    },
    {
        "slug": "pulp_weird_tales_1937_dec",
        "title": "Weird Tales, December 1937",
        "ia_collection": "wt_1937_12",
        "claimed_status": "PD by non-renewal",
        "formats": ["pdf", "epub", "txt"],
        "category": "pulp",
        "notes": "Late-thirties Weird Tales.",
    },

    # ═══════════════════════════════════════════════════════════════
    # NEWSREELS — Universal Newsreels (history channel programming)
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "newsreel_king_alexander_assassination",
        "title": "King Alexander Assassination (1934)",
        "ia_collection": "1934-10-17_King_Alexander_Assassination",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "newsreel",
        "notes": "First actual footage. Universal Newsreel.",
    },
    {
        "slug": "newsreel_florida_1960",
        "title": "Florida 1960",
        "ia_collection": "1960-05-23_florida",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "newsreel",
        "notes": "Universal Newsreel.",
    },
    {
        "slug": "newsreel_pacific_cataclysm_1960",
        "title": "Cataclysm: Volcano + Tidal Waves, Pacific 1960",
        "ia_collection": "1960-05-27_cataclysm",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "newsreel",
        "notes": "Pacific Rim disaster footage. Universal Newsreel.",
    },

    # ═══════════════════════════════════════════════════════════════
    # HISTORIC SERMONS — Spurgeon, Edwards, Whitefield
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "sermon_spurgeon_morning_evening",
        "title": "Morning and Evening: Daily Readings (Spurgeon)",
        "ia_collection": "morning_evening_1105_librivox",
        "claimed_status": "PD source (Spurgeon died 1892); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "sermon",
        "notes": "Charles Spurgeon's daily devotional readings.",
    },
    {
        "slug": "sermon_spurgeon_all_of_grace",
        "title": "All of Grace (Spurgeon)",
        "ia_collection": "all_of_grace_1011_librivox",
        "claimed_status": "PD source; CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "sermon",
        "notes": "Charles Spurgeon on salvation by grace.",
    },
    {
        "slug": "sermon_edwards_select",
        "title": "Select Sermons of Jonathan Edwards",
        "ia_collection": "select_sermons_edwards_0911_librivox",
        "claimed_status": "PD source (Edwards died 1758); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "sermon",
        "notes": "Including Sinners in the Hands of an Angry God.",
    },
    {
        "slug": "sermon_edwards_religious_affections",
        "title": "Religious Affections (Edwards)",
        "ia_collection": "religiousaffections_1501_librivox",
        "claimed_status": "PD source; CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "sermon",
        "notes": "Edwards's theological masterwork on true religious experience.",
    },

    # ═══════════════════════════════════════════════════════════════
    # PD TV — non-renewed episodes of mid-century shows
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "tv_andy_griffith_discovers_america",
        "title": "The Andy Griffith Show: Andy Discovers America (S3 E23)",
        "ia_collection": "Andy-Griffith-Show_Andy-Discovers-America",
        "claimed_status": "PD by non-renewal (specific episode)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "One of the genuinely PD Andy Griffith episodes. 109k downloads.",
    },
    {
        "slug": "tv_beverly_hillbillies_clampetts_strike_oil",
        "title": "Beverly Hillbillies Ep01: The Clampetts Strike Oil",
        "ia_collection": "Beverly_Hillbillies_Ep01_The_Clampetts_Strike_Oil",
        "claimed_status": "PD by non-renewal (first episode)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Series pilot. 187k downloads.",
    },
    {
        "slug": "tv_beverly_hillbillies_s01_e01_e18",
        "title": "Beverly Hillbillies S01 E01-E18",
        "ia_collection": "bevhill-s01e01-36",
        "claimed_status": "PD by non-renewal (early season episodes)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "First-season block. 404k downloads.",
    },
    {
        "slug": "tv_lone_ranger_full",
        "title": "The Lone Ranger TV Show (full PD set)",
        "ia_collection": "theloneranger_201705",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Complete Lone Ranger TV. 513k downloads.",
    },
    {
        "slug": "tv_cisco_kid",
        "title": "The Cisco Kid (PD Episodes Collection)",
        "ia_collection": "TheCiscoKidpublicdomain",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Western, 1950-56. 156k downloads. PD series.",
    },
    {
        "slug": "tv_mister_ed",
        "title": "Mister Ed (PD episodes)",
        "ia_collection": "MisterEdS02E14EdTheBeneficiary",
        "claimed_status": "PD by non-renewal (specific episode)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Talking horse comedy. Some episodes PD. 160k downloads.",
    },
    {
        "slug": "tv_burns_allen_pd",
        "title": "Burns and Allen (TV PD Episodes)",
        "ia_collection": "pdburnsallen",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "George Burns + Gracie Allen TV. 68k downloads.",
    },

    # ── Sketch comedy + classic variety (Matt 2026-05-16: "tons of great sketch comedy
    # skits out there. Adding the ones that have lapsed to PD"). All clear PD-by-
    # non-renewal cases. ──
    {
        "slug": "tv_burns_allen_alt",
        "title": "Burns and Allen — secondary PD collection",
        "ia_collection": "burns-and-allen",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "2 GB · fills gaps in pdburnsallen. 21k downloads.",
    },
    {
        "slug": "tv_ernie_kovacs_box_set",
        "title": "Ernie Kovacs — 5-Hour PD Box Set",
        "ia_collection": "ERNIE_KOVACS_5_HR_VHS_BOX_SET",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "9.5 GB. Iconic absurdist sketch comedy 1950s-62. 10k downloads.",
    },
    {
        "slug": "tv_steve_allen_1953",
        "title": "The Steve Allen Show — 30 December 1953",
        "ia_collection": "TheSteveAllenShow30december1953",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Pre-Tonight-Show Steve Allen. 13k downloads.",
    },
    {
        "slug": "tv_steve_allen_1957",
        "title": "The Steve Allen Show — 1 December 1957",
        "ia_collection": "SteveAllen1December1957",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "2.8 GB. 12k downloads.",
    },
    {
        "slug": "tv_steve_allen_plymouth_1959",
        "title": "The Steve Allen Plymouth Show — 16 November 1959",
        "ia_collection": "SteveAllenPlymouthShow",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "3.6 GB. Late Plymouth-sponsored era. 7k downloads.",
    },
    {
        "slug": "tv_texaco_star_theater_1949_03",
        "title": "Texaco Star Theater (Milton Berle) — 22 March 1949",
        "ia_collection": "TexacoStarTheater22March1949",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Mr. Television himself. 11.6k downloads.",
    },
    {
        "slug": "tv_texaco_star_theater_1949_11",
        "title": "Texaco Star Theater — 29 November 1949",
        "ia_collection": "TexacoStarTheater",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "1.8 GB. 5.9k downloads.",
    },
    {
        "slug": "tv_texaco_star_theater_1950",
        "title": "Texaco Star Theater — 28 February 1950",
        "ia_collection": "TexacoStarTheater28February1950",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "1.9 GB.",
    },
    {
        "slug": "tv_texaco_star_theater_1951",
        "title": "Texaco Star Theater — 29 May 1951",
        "ia_collection": "TexacoStarTheatre-29May1951",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "1.2 GB.",
    },
    {
        "slug": "tv_milton_berle_show_1956_03",
        "title": "The Milton Berle Show — 13 March 1956",
        "ia_collection": "theMiltonBerleShow-13March1956",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Post-Texaco era.",
    },
    {
        "slug": "tv_milton_berle_show_1956_04a",
        "title": "The Milton Berle Show — 3 April 1956",
        "ia_collection": "theMiltonBerleShow-3April1956",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "9k downloads.",
    },
    {
        "slug": "tv_milton_berle_show_1956_04b",
        "title": "The Milton Berle Show — 24 April 1956",
        "ia_collection": "berle24April1956",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "2.4 GB.",
    },
    {
        "slug": "tv_milton_berle_show_1956_05",
        "title": "The Milton Berle Show — 8 May 1956 (with Mickey Rooney + Peggy King)",
        "ia_collection": "MiltonBerleMickeyRooneyPeggyKing",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "2.7 GB.",
    },
    {
        "slug": "tv_buick_berle_show_1954",
        "title": "The Buick-Berle Show — 21 September 1954",
        "ia_collection": "The_Buick_Berle_Show_Sept_21_1954",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Buick-sponsored Berle era. 6.3k downloads.",
    },
    {
        "slug": "tv_your_show_of_shows_1953",
        "title": "Your Show of Shows (Sid Caesar) — 21 March 1953",
        "ia_collection": "YourShowOfShows03211953",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "2.5 GB. Sid Caesar / Imogene Coca / Carl Reiner / Mel Brooks writing.",
    },
    {
        "slug": "tv_your_show_of_shows_compilation",
        "title": "Ten From Your Show of Shows (compilation, Sid Caesar)",
        "ia_collection": "10.from.Your.Show.of.Shows",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "3 GB. 10-sketch compilation, 1973 PD-era release.",
    },
    {
        "slug": "tv_colgate_comedy_hour_abbott_costello",
        "title": "Colgate Comedy Hour — Abbott and Costello (1951)",
        "ia_collection": "ColgateComedyHour_AbbottCostello",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "47k downloads. NBC variety. Bud + Lou TV.",
    },
    {
        "slug": "tv_colgate_comedy_hour_1951_03",
        "title": "Colgate Comedy Hour — 11 March 1951 (Abbott & Costello)",
        "ia_collection": "TheColgateComedyHour11March1951",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "1.4 GB.",
    },
    {
        "slug": "tv_colgate_comedy_hour_martin_lewis",
        "title": "Colgate Comedy Hour — Dean Martin & Jerry Lewis (S6E1)",
        "ia_collection": "Colgate-Comedy-Hour-S6E1",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "2.3 GB. Martin & Lewis peak.",
    },
    {
        "slug": "tv_make_room_for_daddy_full",
        "title": "Make Room for Daddy (Danny Thomas Show) — bulk",
        "ia_collection": "make-room-for-daddy",
        "claimed_status": "PD by non-renewal (early seasons)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "8.3 GB. ABC/CBS 1953-65. Per-episode legal review for late seasons.",
    },
    {
        "slug": "tv_lucy_desi_whats_my_line",
        "title": "What's My Line — Lucille Ball & Desi Arnaz",
        "ia_collection": "Lucy_Desi",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "1.2 GB. Goodson-Todman game-show panel; 23k downloads.",
    },
    {
        "slug": "tv_sky_king",
        "title": "Sky King TV Series",
        "ia_collection": "sky-king-tv-series",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Aviation adventure, 1951-62.",
    },
    {
        "slug": "tv_lassie_pd",
        "title": "Lassie (PD episodes — The Tree House)",
        "ia_collection": "lassie-treehouse",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Classic Lassie episodes. Various PD episodes available.",
    },
    {
        "slug": "tv_topper_pd",
        "title": "Topper (PD episodes)",
        "ia_collection": "Topper-HenriettaSellsTheHouse",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Ghost comedy, 1953-55.",
    },
    {
        "slug": "tv_sherlock_howard_pd",
        "title": "Sherlock Holmes (Ronald Howard 1954)",
        "ia_collection": "SherlockHolmes-TheCaseoftheShyBallerina",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Ronald Howard as Holmes, 1954 series. 131k downloads.",
    },
    {
        "slug": "tv_ozzie_harriet_pd",
        "title": "Ozzie and Harriet (PD episodes)",
        "ia_collection": "OzzieNelsonInLaws",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Family sitcom, 1952-66.",
    },
    {
        "slug": "tv_public_defender",
        "title": "Public Defender TV",
        "ia_collection": "public-defender",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Legal drama, 1954-55. 128 items in IA.",
    },
    {
        "slug": "tv_racket_squad",
        "title": "Racket Squad",
        "ia_collection": "RacketSquadTheSaltedMine1951",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Anti-crime show, 1951-53.",
    },
    {
        "slug": "tv_death_valley_days",
        "title": "Death Valley Days",
        "ia_collection": "Death_Valley_Days_-_Sego_Lillies",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Western anthology, 1952-70.",
    },
    {
        "slug": "tv_annie_oakley",
        "title": "Annie Oakley TV (1954)",
        "ia_collection": "AnnieOakleySanta",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Gail Davis as Annie Oakley, 1954-57.",
    },
    {
        "slug": "tv_roy_rogers_pd",
        "title": "The Roy Rogers Show TV (PD)",
        "ia_collection": "RoyRogersShow-LandSwindle",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Roy Rogers TV (separate from his radio show, also in catalog).",
    },
    {
        "slug": "tv_robin_hood_1955",
        "title": "The Adventures of Robin Hood (British TV 1955-60)",
        "ia_collection": "RobinHood_Blackmail_3D",
        "claimed_status": "PD by non-renewal (UK + US)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Richard Greene as Robin Hood. British classic.",
    },

    # ── Modern / near-modern PD TV (Matt 2026-05-16: "biggest is any modern TV that lapsed") ──
    {
        "slug": "tv_green_acres_complete",
        "title": "Green Acres — Complete Series (1965-1971)",
        "ia_collection": "GreenAcresCompleteSeries",
        "claimed_status": "PD by non-renewal (Filmways)",
        "formats": ["mp4", "mpeg4", "h.264", "avi", "mkv"],
        "category": "pd_tv",
        "notes": "All 6 seasons, ~78 GB. Filmways failed to renew. Comedy core. Matt: yes to all.",
    },
    {
        "slug": "tv_green_acres_s1",
        "title": "Green Acres Season 1",
        "ia_collection": "Green_Acres_Season_1",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Season 1 standalone. Backup if complete series is gappy.",
    },
    {
        "slug": "tv_green_acres_s2",
        "title": "Green Acres Season 2",
        "ia_collection": "Green_Acres_Season_2",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Season 2 standalone.",
    },
    # REMOVED 2026-05-16: tv_get_smart. Only Ep 1 confirmed PD; rest still owned.
    # Per strict PD rule.
    {
        "slug": "tv_dragnet_1951",
        "title": "Dragnet (1951-1959)",
        "ia_collection": "Dragnet1951",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Jack Webb. Original Dragnet TV series. ~14 GB.",
    },
    {
        "slug": "tv_dragnet_collection",
        "title": "Dragnet (additional collection)",
        "ia_collection": "dragnet_202101",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Additional Dragnet episodes; fills gaps in Dragnet1951.",
    },
    {
        "slug": "tv_you_bet_your_life_collection",
        "title": "You Bet Your Life Collection (Groucho Marx)",
        "ia_collection": "ybylcollection",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi", "mp3"],
        "category": "pd_tv",
        "notes": "Groucho game show 1950-1961. Comedy-leaning. Matt-priority.",
    },
    # REMOVED 2026-05-16: tv_kolchak_night_stalker (1974, Universal still owns most),
    # tv_ufo_complete + tv_space_1999_s1 + tv_space_1999_s2 (ITC British, Carlton owns).
    # Per strict PD rule. Carlton actively licenses ITC catalog.
    {
        "slug": "tv_sherlock_holmes_1954",
        "title": "The Adventures of Sherlock Holmes (1954 TV)",
        "ia_collection": "SherlockHolmes1954",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Ronald Howard as Holmes. UK/US co-production. ~8 GB.",
    },
    {
        "slug": "tv_sherlock_holmes_1954_alt",
        "title": "Sherlock Holmes 1954 (alternate collection)",
        "ia_collection": "Sherlock_Holmes_1954",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Alternate IA collection of same series. ~10 GB. Fills gaps.",
    },
    {
        "slug": "tv_bonanza_pd",
        "title": "Bonanza — Public Domain Episodes",
        "ia_collection": "Bonanza_pd",
        "claimed_status": "PD by non-renewal (NBC; certain episodes)",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Bonanza PD aggregator. Per-episode verified-PD set.",
    },
    {
        "slug": "tv_lone_ranger_main",
        "title": "The Lone Ranger TV Show",
        "ia_collection": "theloneranger_201705",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Most-downloaded PD TV item on IA (513k). ~3 GB. Pairs with Lone Ranger radio.",
    },

    # ── Complete-series finds (Matt 2026-05-16: "all the complete TV series we can find") ──
    # REMOVED 2026-05-16: All Gerry Anderson ITC titles (Captain Scarlet / Fireball XL5
    # / Stingray) — Carlton/ITV Studios owns and licenses. Also McHale's Navy
    # (Universal owns). Per strict PD rule.
    {
        "slug": "tv_tate_complete",
        "title": "Tate — Complete Series (1960)",
        "ia_collection": "tate_20251219",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Western. One-armed gunslinger. ~1.5 GB.",
    },
    {
        "slug": "tv_jamie_mcpheeters_complete",
        "title": "Travels of Jamie McPheeters — Complete Series (1963-64)",
        "ia_collection": "travels-of-jamie-mcpheeters",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Family western. Kurt Russell child actor. ~1 GB. Lighthouse Kids fit.",
    },
    {
        "slug": "tv_law_plainsman_complete",
        "title": "Law of the Plainsman — Complete Series (1959-60)",
        "ia_collection": "s-01-e-28-lotp-jebs-daughters",
        "claimed_status": "PD by non-renewal",
        "formats": ["mp4", "mpeg4", "h.264", "avi"],
        "category": "pd_tv",
        "notes": "Western. 30 episodes. ~15 GB.",
    },

    # ═══════════════════════════════════════════════════════════════
    # BIBLE AUDIO — for 24/7 Scripture stream
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "bible_kjv_pentateuch_1",
        "title": "Bible (KJV) Genesis, Exodus, Leviticus (LibriVox)",
        "ia_collection": "bible_kjv_01_02_03_0908_librivox",
        "claimed_status": "PD source (KJV); CC0 recording",
        "formats": ["mp3", "ogg"],
        "category": "bible_audio",
        "notes": "First three books of the Bible, KJV. For Scripture 24/7 channel.",
    },

    # ═══════════════════════════════════════════════════════════════
    # CHILDREN MUSIC — 78rpm sample for Lighthouse Kids
    # ═══════════════════════════════════════════════════════════════
    {
        "slug": "kids_music_jungle_book",
        "title": "Rudyard Kipling's Jungle Book (78rpm recording)",
        "ia_collection": "RudyardKiplingsJungleBook",
        "claimed_status": "PD source; PD recording era",
        "formats": ["mp3", "ogg", "flac"],
        "category": "children",
        "notes": "Kipling's Jungle Book as 78rpm narrated recording.",
    },
]


_SESSION = requests.Session()
_SESSION.headers.update({"User-Agent": "NarrowHighway-Library/1.0 (research/PD-acquisition)"})


def _http_get_json(url: str) -> dict:
    r = _SESSION.get(url, headers={"Accept": "application/json"}, timeout=30)
    r.raise_for_status()
    return r.json()


def _http_download(url: str, dest: Path, expected_size: int = 0,
                   chunk: int = 65536) -> int:
    """Resumable HTTP download. Returns total bytes after completion."""
    headers = {}
    existing = 0
    if dest.exists():
        existing = dest.stat().st_size
        if expected_size and existing >= expected_size:
            return existing  # already complete
        if existing > 0:
            headers["Range"] = f"bytes={existing}-"

    mode = "ab" if existing > 0 else "wb"
    with _SESSION.get(url, headers=headers, stream=True, timeout=120) as r:
        r.raise_for_status()
        with open(dest, mode) as f:
            for buf in r.iter_content(chunk_size=chunk):
                if buf:
                    f.write(buf)
    return dest.stat().st_size


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while True:
            buf = f.read(1 << 16)
            if not buf:
                break
            h.update(buf)
    return h.hexdigest()


def _ia_search_collection(collection_id: str, limit: int = 9999) -> list[dict]:
    """List items in an IA collection. Returns list of item identifiers."""
    base = "https://archive.org/advancedsearch.php"
    params = {
        "q":      f"collection:{collection_id}",
        "fl[]":   "identifier,title,date,year,format",
        "rows":   str(limit),
        "page":   "1",
        "output": "json",
    }
    url = f"{base}?{urllib.parse.urlencode(params, doseq=True)}"
    data = _http_get_json(url)
    return data.get("response", {}).get("docs", [])


def _ia_item_metadata(identifier: str) -> dict:
    url = f"https://archive.org/metadata/{identifier}"
    return _http_get_json(url)


def _pick_files(metadata: dict, formats: list[str]) -> list[dict]:
    """From an IA item's metadata.files list, pick the best file per format."""
    files = metadata.get("files", [])
    out = []
    # Prefer original > derivative; prefer formats in order
    for fmt in formats:
        candidates = [f for f in files
                      if f.get("name", "").lower().endswith(f".{fmt}")]
        if not candidates:
            continue
        # Prefer original source
        originals = [f for f in candidates if f.get("source") == "original"]
        chosen = originals[0] if originals else candidates[0]
        out.append(chosen)
        break  # one file per item is enough
    return out


def download_target(target: dict, storage: Path, limit: int = 0,
                    dry_run: bool = False, on_progress=None) -> dict:
    """Download a target series. Returns a manifest dict.

    Handles both shapes:
      (a) Single-item identifier (e.g. OTRR_X_Minus_One_Singles) — fetch its
          metadata once, iterate over its `files` list to get each episode.
      (b) True collection identifier — search advancedsearch for items in
          the collection.
    """
    series_dir = storage / target["slug"]
    if not dry_run:
        series_dir.mkdir(parents=True, exist_ok=True)

    ident_or_collection = target["ia_collection"]

    print(f"\n=== {target['title']} ({target['slug']}) ===", flush=True)
    print(f"  IA identifier: {ident_or_collection}", flush=True)
    print(f"  Status claim:  {target['claimed_status']}", flush=True)

    # First try: treat as a single item; pull metadata + files
    try:
        meta = _ia_item_metadata(ident_or_collection)
    except Exception as e:
        print(f"  Failed to fetch metadata: {e}", flush=True)
        meta = {}

    files = meta.get("files", [])

    # Filter to files matching our preferred formats by filename extension
    fmts = target["formats"]
    def _format_match(fn: str) -> bool:
        return any(fn.lower().endswith(f".{x}") for x in fmts)
    episode_files = [
        f for f in files
        if f.get("name") and _format_match(f["name"])
           and f.get("source") in (None, "original", "derivative")
    ]
    # Prefer originals; group derivatives only when no original exists
    originals = [f for f in episode_files if f.get("source") == "original"]
    if originals:
        episode_files = originals

    items = []  # list of pseudo-items with same shape as collection-search

    if episode_files:
        # Single-item-with-many-files shape
        print(f"  Single-item shape: {len(episode_files)} {fmts} files within {ident_or_collection}", flush=True)
        for f in episode_files:
            items.append({
                "identifier":    ident_or_collection,
                "title":         f.get("title") or f.get("name"),
                "filename":      f["name"],
                "filesize":      int(f.get("size", 0)),
                "format":        f.get("format"),
                "date":          f.get("mtime"),
                "year":          None,
                "_single_item":  True,
                "_file_info":    f,
            })
    else:
        # Try collection-search shape
        try:
            search_items = _ia_search_collection(ident_or_collection)
            print(f"  Collection shape: {len(search_items)} items", flush=True)
            items = search_items
        except Exception as e:
            print(f"  No items found via either shape: {e}", flush=True)
            items = []

    if limit and len(items) > limit:
        items = items[:limit]
        print(f"  Limited to first {limit}", flush=True)

    manifest = {
        "slug":             target["slug"],
        "title":            target["title"],
        "ia_collection":    target["ia_collection"],
        "claimed_status":   target["claimed_status"],
        "category":         target["category"],
        "notes":            target["notes"],
        "acquired_at_iso":  datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "verified":         False,  # Operator must run verification protocol
        "verified_at":      None,
        "verified_by":      None,
        "storage_path":     str(series_dir),
        "items":            [],
    }

    total_bytes = 0
    n_success = 0
    n_error = 0
    t0 = time.time()

    for i, item in enumerate(items, start=1):
        ident = item.get("identifier", "")
        if not ident: continue
        try:
            # If item came from the single-item-with-files path, file info is already attached
            if item.get("_single_item"):
                file_info = item["_file_info"]
                fname = file_info["name"]
                file_size = int(file_info.get("size", 0))
            else:
                meta = _ia_item_metadata(ident)
                files = _pick_files(meta, target["formats"])
                if not files:
                    print(f"  [{i}/{len(items)}] {ident}: no {target['formats']} file", flush=True)
                    continue
                file_info = files[0]
                fname = file_info["name"]
                file_size = int(file_info.get("size", 0))

            dest = series_dir / fname
            if dry_run:
                print(f"  [{i}/{len(items)}] [dry-run] would download {fname} ({file_size:,}b)", flush=True)
                continue

            url = f"https://archive.org/download/{ident}/{urllib.parse.quote(fname)}"
            try:
                bytes_written = _http_download(url, dest, expected_size=file_size)
            except Exception as e:
                print(f"  [{i}/{len(items)}] {ident}: download failed: {e}", flush=True)
                n_error += 1
                continue

            sha = _sha256(dest)
            item_entry = {
                "ia_identifier":  ident,
                "title":          item.get("title") or ident,
                "year":           item.get("year"),
                "date":           item.get("date"),
                "filename":       fname,
                "local_path":     str(dest),
                "size_bytes":     bytes_written,
                "sha256":         sha,
                "ia_url":         f"https://archive.org/details/{ident}",
                "download_url":   url,
            }
            manifest["items"].append(item_entry)
            total_bytes += bytes_written
            n_success += 1

            if i % 5 == 0 or i == len(items):
                elapsed = time.time() - t0
                rate = total_bytes / elapsed / (1024 * 1024) if elapsed > 0 else 0
                print(f"  [{i:4d}/{len(items)}] {fname} ({bytes_written/1024/1024:5.1f} MB) | total {total_bytes/1024/1024:7.1f} MB | {rate:5.1f} MB/s", flush=True)
        except requests.HTTPError as e:
            code = e.response.status_code if e.response is not None else "?"
            print(f"  [{i}/{len(items)}] {ident}: HTTP {code}: {str(e)[:120]}", flush=True)
            n_error += 1
        except Exception as e:
            print(f"  [{i}/{len(items)}] {ident}: {type(e).__name__}: {str(e)[:200]}", flush=True)
            n_error += 1

    manifest["items_acquired"] = n_success
    manifest["items_failed"]   = n_error
    manifest["total_bytes"]    = total_bytes
    manifest["total_mb"]       = round(total_bytes / (1024 * 1024), 2)
    manifest["elapsed_seconds"] = round(time.time() - t0)

    if not dry_run:
        manifest_path = ACQUIRED / f"{target['slug']}.json"
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"  Wrote manifest: {manifest_path}", flush=True)

    print(f"\n  [OK] {target['title']}: {n_success} acquired, {n_error} failed, "
          f"{total_bytes/1024/1024:.1f} MB total", flush=True)
    return manifest


def main():
    args = sys.argv[1:]
    series_filter = None
    category_filter = None
    skip_series = set()
    limit = 0
    storage = DEFAULT_STORAGE
    dry_run = False
    list_only = False

    i = 0
    while i < len(args):
        a = args[i]
        if a == "--series" and i + 1 < len(args):
            series_filter = args[i + 1]; i += 1
        elif a == "--category" and i + 1 < len(args):
            category_filter = args[i + 1]; i += 1
        elif a == "--skip" and i + 1 < len(args):
            skip_series.add(args[i + 1]); i += 1
        elif a == "--limit" and i + 1 < len(args):
            limit = int(args[i + 1]); i += 1
        elif a == "--storage" and i + 1 < len(args):
            storage = Path(args[i + 1]); i += 1
        elif a == "--dry-run":
            dry_run = True
        elif a == "--list":
            list_only = True
        i += 1

    if list_only:
        from collections import defaultdict
        by_cat = defaultdict(list)
        for t in TARGETS: by_cat[t["category"]].append(t)
        print(f"Targets configured: {len(TARGETS)} across {len(by_cat)} categories")
        for cat in sorted(by_cat.keys()):
            print(f"\n--- {cat} ({len(by_cat[cat])}) ---")
            for t in by_cat[cat]:
                print(f"  {t['slug']:32} {t['title'][:48]:48} {t['claimed_status'][:35]}")
        return

    storage.mkdir(parents=True, exist_ok=True)
    ACQUIRED.mkdir(parents=True, exist_ok=True)

    targets_to_run = TARGETS
    if category_filter:
        targets_to_run = [t for t in targets_to_run if t["category"] == category_filter]
        if not targets_to_run:
            print(f"No targets in category: {category_filter}", file=sys.stderr)
            cats = sorted(set(t["category"] for t in TARGETS))
            print(f"Available categories: {cats}", file=sys.stderr)
            sys.exit(1)
    if series_filter:
        targets_to_run = [t for t in targets_to_run if t["slug"] == series_filter]
        if not targets_to_run:
            print(f"No target matching slug: {series_filter}", file=sys.stderr)
            print(f"Available: {[t['slug'] for t in TARGETS]}", file=sys.stderr)
            sys.exit(1)
    if skip_series:
        before = len(targets_to_run)
        targets_to_run = [t for t in targets_to_run if t["slug"] not in skip_series]
        print(f"Skipping {before - len(targets_to_run)} series: {sorted(skip_series)}", file=sys.stderr)

    print(f"=== IA library downloader ===")
    print(f"Storage: {storage}")
    print(f"Targets: {len(targets_to_run)}")
    if limit: print(f"Limit per target: {limit}")
    if dry_run: print("DRY RUN")
    print()

    summaries = []
    for t in targets_to_run:
        try:
            m = download_target(t, storage, limit=limit, dry_run=dry_run)
            summaries.append({
                "slug": t["slug"],
                "acquired": m.get("items_acquired", 0),
                "failed":   m.get("items_failed", 0),
                "mb":       m.get("total_mb", 0),
            })
        except Exception as e:
            print(f"\n!!! {t['slug']} FAILED: {type(e).__name__}: {e}", file=sys.stderr)
            summaries.append({"slug": t["slug"], "acquired": 0, "failed": 0, "error": str(e)})

    print("\n=== Summary ===")
    total = 0
    for s in summaries:
        if "error" in s:
            print(f"  {s['slug']:30} ERROR: {s['error'][:80]}")
        else:
            print(f"  {s['slug']:30} {s['acquired']:5} items  {s['mb']:7.1f} MB  ({s.get('failed',0)} failed)")
            total += s.get("mb", 0)
    print(f"\nTotal acquired this run: {total:,.1f} MB ({total/1024:.2f} GB)")


if __name__ == "__main__":
    main()
