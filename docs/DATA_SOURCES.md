# Data sources for verification -- the grounding queue

Survey date: 2026-06-15. The question: which authoritative external sources
should the engine tap so its verifiers can check claims against a real ground
truth -- and in what order. Every source here is EXTERNAL, ATTRIBUTED Layer-0:
we store it offline, cite it, and never author it. Selection bar: open license
+ clean offline download + authoritative (the source a domain expert cites) +
serves a verifier we already have + not already wired.

Legend: **PD** = public domain, **offline** = single bulk artifact we can vendor,
**API** = network-at-query-time (slice + cache locally).

---

## Already grounded (do NOT re-wire)

- **Embedded reference (in-engine, cited):** CODATA 2018 constants
  (`physical_constants`), IUPAC 2021 atomic weights (`periodic_table`), atomic
  electron structure (`atomic`), Meeus ephemeris algorithms (`ephemeris`).
- **Layer-0 lookups (wired):** PHOIBLE phonemes (`language_data`), WordNet
  semantics (`word_meaning`), Wikidata facts (`wikidata`), GeoNames places
  (`place_lookup`), original-language lexicon (`word_study`).
- **Pure computation -- needs NO data source:** `mathematics`, `geometry`,
  `number_theory` (formulas), `combinatorics` (formulas), `formal_logic`,
  `statistics`, `probability`, `information_theory` (Shannon closed-form),
  `operations_research` (LP/graph algorithms), `music_theory` (12-TET / MIDI
  formula: A4=440, 2^(1/12)), `linear_algebra`. Ground these in code, not data.

---

## TIER 1 -- wire first (small, offline, open, highest grounding-per-byte)

| Source | Verifier(s) | License | Access | Why first |
|---|---|---|---|---|
| **IANA tz database (tzdata)** -- WIRED (`timezone_offset`, IANA 2026b, lw/00_source/tzdata/tzdata.zip) | calendar_time | PD | offline ~300KB | Place's zone name (from GeoNames) -> exact UTC/DST offset at any instant. Single highest-leverage add. |
| **UCUM units (ucum-essence.xml)** -- WIRED (`unit_convert`, UCUM 2.2, lw/00_source/ucum/ucum.json) | physics_dimensional + ALL dimensional checks | royalty-free | offline 1 file | The units *substrate*; unblocks unit verification across every domain. Deterministic recursive evaluator, fails closed. |
| **OEIS (stripped.gz + names.gz)** -- WIRED (`sequence_lookup`, 396,600 seqs, lw/00_source/oeis/oeis.db) | number_theory, combinatorics | CC BY-SA | offline ~126MB SQLite | Only source for sequence name<->terms ("A000045 = Fibonacci"); by A-number or term-run identification. |
| **CMU Pronouncing Dictionary** -- WIRED (`word_pronunciation`, 126k words + IPA/syllables/stress, lw/00_source/cmudict/cmudict.db) | linguistics | BSD-2 | offline ~7MB SQLite | Word -> ARPABET pronunciation; completes the language tree (PHOIBLE=inventory, this=word). |
| **IANA port/protocol registries + RFC index** -- WIRED (`port_lookup` + `rfc_lookup`, 12,571 ports + 9,777 RFCs, lw/00_source/protocols/protocols.db) | networking, cryptography | PD | offline ~2MB SQLite | "TCP 443 = HTTPS", "which RFC defines X" (+ superseded_by flag, e.g. HTTP/2 RFC7540->9113). |
| **HYG star catalog (hyg_v42)** -- WIRED (`star_lookup`, 119,626 stars, lw/00_source/hyg/hyg.db) | astronomy | CC BY-SA | offline ~11MB SQLite | Star position / magnitude / spectral type / distance / constellation membership; by proper name or constellation-brightest, fully offline. |
| **CoolProp / IF97** -- WIRED (`fluid_property`, CoolProp 7.2.0 pip dep, fails-closed) | thermodynamics, energy, phase | MIT | pip-embedded code lib | Water-steam + 100+ fluids; deterministic PropsSI; gated on known values (water Tboil 373.12K, Tcrit 647.1K). |
| **IERS leap-seconds.list** | calendar_time | open | offline few KB | TAI<->UTC precision (leap-second history). |

## TIER 2 -- mission-critical (SERVE: the Table + the Apothecary), open + offline

| Source | Verifier(s) | License | Access | Mission |
|---|---|---|---|---|
| **USDA FoodData Central (SR Legacy)** -- WIRED (`food_nutrition`, 7,793 foods + 644k nutrient rows, lw/00_source/usda/usda.db) | nutrition | PD | offline ~21MB SQLite | The Table -- feed the hungry. Key nutrients per 100g, by name search. |
| **DailyMed + openFDA** (pair) | medicine | PD | offline bulk (labels + AE + NDC) | The Apothecary -- heal the sick; no license gate. |
| **DrugCentral** | medicine | CC BY-SA | offline SQL dump | Open structured pharmacology (the open alt to license-gated DrugBank). |
| **MedlinePlus Herbs + NCCIH Herbs at a Glance** | medicine | PD | offline monographs | Best OPEN herb monographs for the Apothecary. |
| **GBIF Backbone + NCBI Taxonomy** | biology, ecology, genetics | CC0 / PD | offline DwC-A / taxdump ~60MB | Species name authority ("tomato = Solanum lycopersicum"). |
| **Natural Earth** | geography, oceanography | PD | offline GPKG ~400MB | Boundaries / coastlines / named features, no API, no attribution. |

## TIER 3 -- high value, larger or API-only (escalation / when needed)

| Source | Verifier(s) | License | Access | Note |
|---|---|---|---|---|
| **ChEBI** (prefer over PubChem for clean license) | chemistry, nutrition | CC BY | offline SDF/OBO | Open chemistry layer; PubChem FTP SDF is the heavier high-coverage option. |
| **USGS ComCat** | geology | PD | API (slice+cache) | Earthquake magnitude/depth -- the citable authority. |
| **GEBCO 2024** | oceanography | ~PD | offline NetCDF ~7.5GB | Ocean depth / below-sea-level elevation. |
| **Copernicus DEM GLO-30** | geography, geology | open (attrib) | offline AWS tiles | Global elevation (Everest 8849 m); pull tiles as needed. |
| **World Bank Open Data** | economics | CC BY | offline CSV + no-key API | GDP / inflation / population. |
| **US BLS flat files** | labor | PD | offline flat files | Unemployment / CPI (offline beats the daily API cap). |
| **ECB eurofxref-hist.csv (Frankfurter)** | finance | free (attrib) | offline ~1MB CSV | Daily FX reference rate back to 1999. |
| **SEC EDGAR companyfacts.zip** | finance | PD | offline multi-GB | Company filings / XBRL facts. |
| **Caselaw Access Project** | law | **CC0** | offline bulk JSON (tens GB) | Cleanest possible license on the full US case-law corpus. |
| **US Code (OLRC USLM XML)** | law, governance | PD | offline XML | Statutory text by title/section. |
| **NIST ASD / NNDC ENSDF** | atomic, optics, nuclear_physics | PD/open | API/CSV | Spectral lines; nuclide half-lives/decay. |
| **USGS GNIS** | geography | PD | offline pipe-delimited | Named US non-city features (fills the GeoNames cities gap). |
| **NOAA Climate Normals / GHCN-Daily** | meteorology | PD | offline CSV (AWS) | US + global station climate baseline. |
| **Materials Project** | materials_science | CC BY | API + AWS snapshot | Computed materials properties. |
| **Smithsonian GVP** | geology | free (cite) | offline CSV | Volcano / eruption catalog. |
| **World Historical Gazetteer** | history_chronology | CC BY | dataset downloads | Places across time (GeoNames is present-day only). |
| **FAOSTAT** | agriculture | CC BY | offline ZIP/CSV | Crop/production statistics (feed-the-hungry supply side). |
| **USDA PLANTS** | agriculture, ecology | PD | offline CSV | US plant names + distribution (herb sourcing). |

---

## RESTRICTED -- flag, do not embed; use the open substitute

- **SNOMED CT** -- affiliate-license gated. Substitute: MeSH + ICD-11 + RxNorm + DrugCentral.
- **DrugBank** -- redistribution license / paid commercial. Substitute: DailyMed/openFDA + DrugCentral + RxNav.
- **WHO ICD-11** -- CC BY-ND: lookup OK, NO derivative code lists.
- **Natural Medicines** -- closed/subscription. Substitute: MedlinePlus Herbs + NCCIH.
- **RxNorm full RRF** -- free but UMLS-account gated; RxNav API is open/no-key.
- **Universal Dependencies** -- per-treebank licenses (some NC); vendor only the open ones.

## Corrections surfaced by the research

- "ICD code for type-2 diabetes = E11" is **ICD-10-CM** (CMS, PD bulk download),
  NOT ICD-11. Wire CMS ICD-10-CM if exact US codes are needed.
- JPL HORIZONS, NIST Chemistry WebBook are API-only / scrape-and-cache (no clean
  bulk). USGS Water, NOAA CO-OPS are US-only -- pair with global sources.

---

## Wiring order (extends the autonomous data-sources loop)

Phase 5 = GeoNames, 6 = tzdata, 7 = UCUM, 8 = OEIS, 9 = CMU dict (DONE -- the
language tree's phonics level; all 5 linguistic levels now grounded), 10 = IANA
ports + RFC index, 11 = HYG stars, 12 = CoolProp (TIER 1 COMPLETE), 13 = USDA
FoodData / the Table (DONE -- first SERVE source). Queue from here (TIER 2 SERVE):
**DailyMed/openFDA (the Apothecary) -> DrugCentral + MedlinePlus/NCCIH herbs ->
GBIF/NCBI (species) -> Natural Earth (geography)**, then Tier 3 as depth is needed. One
source per tick: offline build -> reproducible `tools/build_<src>_index.py` -> SQLite (big)
or JSON (small) at `lw/00_source/<src>/` -> lookup tool -> deploy -> benchmark
58/58 -> verify live -> one commit -> push.
