#!/usr/bin/env python3
# Build the offline WordNet 3.1 Layer-0 db (lw/00_source/wordnet/wordnet.db).
# Reproduce:
#   1. curl -sL https://wordnetcode.princeton.edu/wn3.1.dict.tar.gz -o wn31.tar.gz
#   2. tar -xzf wn31.tar.gz   (creates dict/)
#   3. python build_wordnet_index.py   (reads dict/, writes wordnet.db)
#   4. scp wordnet.db -> nh@nh-engine-1:~/Lighthouse/lw/00_source/wordnet/
# Source: Princeton WordNet 3.1 (WordNet License -- free use/redistribution with notice).
# Build the offline WordNet 3.1 index the engine reads (Layer-0 source).
# lemma (normalized) -> senses: [{pos, definition, synonyms[], hypernyms[]}].
import os, json, collections

HERE = os.path.dirname(os.path.abspath(__file__))
DICT = os.path.join(HERE, "dict")
POS_FILES = {"n": "noun", "v": "verb", "a": "adj", "r": "adv"}
NORM = {"n": "n", "v": "v", "a": "a", "s": "a", "r": "r"}  # adj-satellite s -> a


def norm_lemma(w):
    return w.replace("_", " ").lower()


# 1. data.* -> synset[(norm_pos, offset)] = {words, gloss, hypernyms:[(norm_pos,offset)]}
synset = {}
for p, fn in POS_FILES.items():
    path = os.path.join(DICT, "data." + fn)
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("  "):
                continue
            head, _, gloss = line.partition("|")
            t = head.split()
            if len(t) < 4:
                continue
            offset = t[0]
            try:
                w_cnt = int(t[3], 16)
            except ValueError:
                continue
            i = 4
            words = []
            for _w in range(w_cnt):
                if i >= len(t):
                    break
                words.append(t[i].replace("_", " "))
                i += 2
            hypers = []
            try:
                p_cnt = int(t[i]); i += 1
                for _ in range(p_cnt):
                    sym, tgt, ppos = t[i], t[i + 1], t[i + 2]
                    i += 4
                    if sym in ("@", "@i"):
                        hypers.append((NORM.get(ppos, ppos), tgt))
            except (IndexError, ValueError):
                pass
            g = gloss.strip()
            # keep only the definition part (before the first example in quotes/;)
            if ";" in g and '"' in g:
                g = g.split(';')[0].strip()
            synset[(NORM[p], offset)] = {"words": words, "gloss": g, "hypers": hypers}

# 2. index.* -> lemma -> [(norm_pos, [offsets])]
lemma_senses = collections.defaultdict(list)
for p, fn in POS_FILES.items():
    path = os.path.join(DICT, "index." + fn)
    with open(path, encoding="utf-8", errors="replace") as f:
        for line in f:
            if line.startswith("  "):
                continue
            t = line.split()
            if len(t) < 6:
                continue
            lemma = t[0]
            try:
                synset_cnt = int(t[2]); p_cnt = int(t[3])
            except ValueError:
                continue
            i = 4 + p_cnt + 2  # skip ptr symbols + sense_cnt + tagsense_cnt
            offsets = t[i:i + synset_cnt]
            lemma_senses[norm_lemma(lemma)].append((NORM[p], offsets))

# 3. build the lookup index
POS_LABEL = {"n": "noun", "v": "verb", "a": "adjective", "r": "adverb"}
out_index = {}
for lemma, sl in lemma_senses.items():
    senses = []
    for pos, offsets in sl:
        for off in offsets[:4]:  # cap senses per (lemma,pos)
            ss = synset.get((pos, off))
            if not ss:
                continue
            syns = [w for w in ss["words"] if w.lower() != lemma][:8]
            hyp = []
            for hp, ho in ss["hypers"][:4]:
                hs = synset.get((hp, ho))
                if hs and hs["words"]:
                    hyp.append(hs["words"][0])
            senses.append({"pos": POS_LABEL.get(pos, pos), "definition": ss["gloss"],
                           "synonyms": syns, "hypernyms": hyp})
    if senses:
        out_index[lemma] = senses[:6]

# write SQLite (low memory, query-by-key) -- the pattern for big offline sources
import sqlite3
outpath = os.path.join(HERE, "wordnet.db")
if os.path.exists(outpath):
    os.remove(outpath)
con = sqlite3.connect(outpath)
con.execute("CREATE TABLE senses (lemma TEXT PRIMARY KEY, data TEXT)")
con.execute("CREATE TABLE meta (k TEXT PRIMARY KEY, v TEXT)")
con.executemany("INSERT OR REPLACE INTO senses VALUES (?,?)",
                ((lemma, json.dumps(senses, ensure_ascii=False)) for lemma, senses in out_index.items()))
con.executemany("INSERT OR REPLACE INTO meta VALUES (?,?)", [
    ("source", "Princeton WordNet 3.1"),
    ("source_url", "https://wordnet.princeton.edu/"),
    ("license", "WordNet License (Princeton -- free use/redistribution with notice)"),
    ("lemmas", str(len(out_index)))])
con.commit()
con.execute("VACUUM")
con.close()
print("lemmas:", len(out_index), "| db size:", round(os.path.getsize(outpath) / 1024 / 1024, 2), "MB")
for q in ("dog", "run", "good", "shepherd", "grace"):
    s = out_index.get(q)
    if s:
        print("  %-9s [%s] %s" % (q, s[0]["pos"], s[0]["definition"][:62]))
        if s[0]["hypernyms"]:
            print("            is-a: %s | syn: %s" % (", ".join(s[0]["hypernyms"][:3]), ", ".join(s[0]["synonyms"][:4])))
