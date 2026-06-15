#!/usr/bin/env python3
# Build the offline PHOIBLE+Glottolog Layer-0 index (lw/00_source/phoible/phoible_index.json).
# Reproduce:
#   1. curl -sL https://raw.githubusercontent.com/phoible/dev/master/data/phoible.csv -o phoible.csv
#   2. curl -sL https://raw.githubusercontent.com/cldf-datasets/phoible/master/cldf/languages.csv -o languages.csv
#   3. python build_phoible_index.py   (reads both from this dir; writes phoible_index.json)
#   4. scp phoible_index.json -> nh@nh-engine-1:~/Lighthouse/lw/00_source/phoible/
# Sources: PHOIBLE 2.0 (CC-BY-SA 3.0) + Glottolog (CC-BY 4.0). External Layer-0; attributed.
# Build the offline PHOIBLE+Glottolog index the engine will read (Layer-0 source).
# One entry per language: representative phoneme inventory + family + macroarea + coords.
import csv, json, os, collections

HERE = os.path.dirname(os.path.abspath(__file__))


def _f(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# 1. language metadata (glottocode -> name, family, macroarea, coords) from CLDF languages.csv
meta = {}
with open(os.path.join(HERE, "languages.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        gc = r.get("Glottocode") or r.get("ID")
        if not gc:
            continue
        meta[gc] = {
            "name": r.get("Name", ""),
            "iso": r.get("ISO639P3code", ""),
            "family": r.get("Family_Name", "") or "(isolate/unclassified)",
            "macroarea": r.get("Macroarea", ""),
            "lat": _f(r.get("Latitude")),
            "lon": _f(r.get("Longitude")),
        }

# 2. phoneme inventories from phoible.csv, grouped by (glottocode, inventory_id)
inv = collections.defaultdict(lambda: {"consonant": [], "vowel": [], "tone": [], "source": ""})
with open(os.path.join(HERE, "phoible.csv"), encoding="utf-8") as f:
    for r in csv.DictReader(f):
        gc = r.get("Glottocode")
        iid = r.get("InventoryID")
        if not gc or not iid:
            continue
        key = (gc, iid)
        seg = (r.get("SegmentClass") or "").strip().lower()
        ph = r.get("Phoneme", "")
        inv[key]["source"] = r.get("Source", "")
        if seg in ("consonant", "vowel", "tone") and ph:
            inv[key][seg].append(ph)

# 3. per glottocode: pick the RICHEST inventory (most phonemes) as representative; count inventories
by_gc_inv = collections.defaultdict(list)
for (gc, iid), d in inv.items():
    n = len(d["consonant"]) + len(d["vowel"]) + len(d["tone"])
    by_gc_inv[gc].append((n, iid, d))

by_glottocode = {}
name_index = {}
for gc, lst in by_gc_inv.items():
    lst.sort(reverse=True)  # richest first
    n, iid, d = lst[0]
    m = meta.get(gc, {})
    name = m.get("name", "")
    entry = {
        "glottocode": gc,
        "name": name,
        "iso": m.get("iso", ""),
        "family": m.get("family", ""),
        "macroarea": m.get("macroarea", ""),
        "lat": m.get("lat"), "lon": m.get("lon"),
        "n_inventories": len(lst),
        "inventory_source": d["source"],
        "n_phonemes": n,
        "n_consonants": len(d["consonant"]),
        "n_vowels": len(d["vowel"]),
        "n_tones": len(d["tone"]),
        "consonants": d["consonant"],
        "vowels": d["vowel"],
        "tones": d["tone"],
    }
    by_glottocode[gc] = entry
    if name:
        name_index[name.lower()] = gc
    if m.get("iso"):
        name_index[m["iso"].lower()] = gc
    name_index[gc.lower()] = gc

out = {
    "meta": {
        "source": "PHOIBLE 2.0 (CLDF) + Glottolog classification",
        "source_urls": ["https://phoible.org/", "https://glottolog.org/"],
        "license": "CC-BY-SA 3.0 (PHOIBLE) / CC-BY 4.0 (Glottolog)",
        "note": "External Layer-0 source -- attributed, not engine-authored. Representative = the richest inventory per language.",
        "languages": len(by_glottocode),
    },
    "by_glottocode": by_glottocode,
    "name_index": name_index,
}
outpath = os.path.join(HERE, "phoible_index.json")
json.dump(out, open(outpath, "w", encoding="utf-8"), ensure_ascii=False)
print("languages:", len(by_glottocode), "| name_index keys:", len(name_index))
print("size:", round(os.path.getsize(outpath) / 1024 / 1024, 2), "MB")
# spot check
for q in ("korean", "eng", "haw", "xoo"):
    gc = name_index.get(q)
    if gc:
        e = by_glottocode[gc]
        print("  %-8s -> %-14s %s | %d phonemes (%dC/%dV/%dT) | %s" % (
            q, e["name"], e["family"], e["n_phonemes"], e["n_consonants"], e["n_vowels"], e["n_tones"], e["macroarea"]))
