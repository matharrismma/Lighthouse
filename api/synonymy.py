"""synonymy.py — a curated concept lexicon for the discernment domain.

The recall surfaces ("he remembers", "he has walked this with you", the
narrowing) match a person's words against their prior words. Bare token overlap
misses synonyms: "afraid" never meets "anxious", "my marriage is failing" never
meets "fighting with my wife". The long-noted ceiling.

The aligned fix here is NOT opaque embeddings (a 462MB-free box can't host one
safely, and a cosine threshold risks the exact failure the project refuses — a
FALSE connection, "a false trail is worse than none"). It is a CURATED,
EXPLAINABLE concept map: each surface word canonicalises to a concept; two words
are synonymous iff they share a concept. Purely ADDITIVE — it can only add a
concept-level match, never remove a literal one, and never invents a match unless
the lexicon miscurates (which is reviewable, deterministic, and ours to control).

Used by `offices.recall_connection` (so card + walk recall reach across synonyms)
and, conservatively, by `well_retriever` query expansion. No dependency, $0, no
data leaves, no model. The reach is the right word; retrieval is choosing.

Tokens are lowercase, >=3 chars (matching offices._otoks). There is no stemmer,
so common inflections are listed explicitly. A surface word belongs to at most
one concept — keep it that way (ambiguous words are left OUT, staying literal).
"""
from __future__ import annotations

from typing import Iterable, List, Set

# concept_id -> the surface forms (and inflections) that express it.
# Curated for the pastoral / discernment domain: emotions, relationships,
# struggles, virtues, spiritual states, and life events. Conservative on
# purpose — only words that genuinely denote the SAME concept.
_CONCEPTS = {
    # ── inner states / emotions ──────────────────────────────────────────
    "fear": ["afraid", "fear", "fearful", "fears", "scared", "scare", "scary",
             "anxious", "anxiety", "worried", "worry", "worries", "worrying",
             "dread", "dreading", "terrified", "terror", "nervous", "panic",
             "panicked", "apprehensive", "frightened", "fright"],
    "anger": ["angry", "anger", "angered", "wrath", "rage", "raging", "furious",
              "fury", "mad", "resentment", "resentful", "resent", "bitter",
              "bitterness", "irritated", "irritation", "indignant", "livid",
              "hostile", "hostility", "seething"],
    "grief": ["grief", "grieve", "grieving", "grieved", "mourn", "mourning",
              "mourned", "sorrow", "sorrowful", "lament", "lamenting", "bereaved",
              "bereavement", "heartbroken", "heartbreak", "anguish"],
    "sadness": ["sad", "sadness", "unhappy", "depressed", "depression", "despair",
                "despairing", "hopeless", "hopelessness", "melancholy", "downcast",
                "dejected", "gloom", "gloomy", "miserable", "misery"],
    "shame": ["shame", "ashamed", "shameful", "embarrassed", "embarrassment",
              "humiliated", "humiliation", "disgrace", "disgraced", "unworthy",
              "worthless", "self-loathing"],
    "guilt": ["guilt", "guilty", "remorse", "remorseful", "regret", "regretful",
              "regrets", "conscience", "convicted", "conviction", "condemned"],
    "loneliness": ["lonely", "loneliness", "alone", "isolated", "isolation",
                   "abandoned", "lonesome", "friendless", "forsaken", "unloved"],
    "peace": ["peace", "peaceful", "calm", "calmness", "serene", "serenity",
              "rest", "restful", "stillness", "tranquil", "contentment", "content"],
    "joy": ["joy", "joyful", "joyous", "glad", "gladness", "rejoice", "rejoicing",
            "delight", "delighted", "happy", "happiness", "cheerful"],
    "hope": ["hope", "hopeful", "hoping", "expectant", "expectation", "longing",
             "yearning", "yearn"],
    "gratitude": ["grateful", "gratitude", "thankful", "thanks", "thanksgiving",
                  "appreciative", "blessed", "blessing"],
    "doubt": ["doubt", "doubtful", "doubting", "uncertain", "uncertainty",
              "unsure", "skeptical", "skepticism", "questioning", "wavering"],

    # ── relationships ────────────────────────────────────────────────────
    "marriage": ["marriage", "married", "marry", "marrying", "spouse", "wife",
                 "husband", "wedded", "wed", "wedding", "matrimony", "marital"],
    "divorce": ["divorce", "divorced", "divorcing", "separation", "separated",
                "estranged", "estrangement", "annulment"],
    "children": ["child", "children", "kid", "kids", "son", "sons", "daughter",
                 "daughters", "parenting", "parent", "parents", "fatherhood",
                 "motherhood", "raising"],
    "family": ["family", "families", "household", "relatives", "kin", "kinship"],
    "friendship": ["friend", "friends", "friendship", "companion", "companionship",
                   "fellowship"],
    "conflict": ["conflict", "quarrel", "quarreling", "argument", "arguing",
                 "argue", "argued", "fight", "fighting", "fought", "feud",
                 "dispute", "strife", "discord", "clash"],
    "betrayal": ["betray", "betrayed", "betrayal", "unfaithful", "infidelity",
                 "adultery", "cheated", "cheating", "affair", "deceived",
                 "backstabbed", "disloyal"],
    "reconciliation": ["reconcile", "reconciled", "reconciliation", "mend",
                       "mending", "restored", "restoration", "amends", "peacemaking"],

    # ── struggles / sins ─────────────────────────────────────────────────
    "lust": ["lust", "lustful", "lusting", "pornography", "porn", "fornication",
             "impurity", "impure", "seduction"],
    "pride": ["pride", "prideful", "proud", "arrogant", "arrogance", "vanity",
              "vain", "conceit", "conceited", "haughty", "boastful", "boasting"],
    "greed": ["greed", "greedy", "covet", "coveting", "covetous", "covetousness",
              "avarice", "materialism", "materialistic"],
    "envy": ["envy", "envious", "jealous", "jealousy", "begrudge"],
    "addiction": ["addiction", "addicted", "addict", "dependency", "compulsion",
                  "compulsive", "craving", "habit", "drunkenness", "drunk"],
    "deceit": ["lie", "lies", "lying", "lied", "deceit", "deceitful", "deceive",
               "dishonest", "dishonesty", "falsehood", "hypocrisy", "hypocrite"],
    "temptation": ["tempt", "tempted", "temptation", "tempting", "enticed",
                   "enticement", "lured", "allure"],
    "sin": ["sin", "sins", "sinful", "sinning", "sinned", "transgression",
            "transgress", "iniquity", "wickedness", "wicked", "evil", "wrongdoing"],

    # ── virtues ──────────────────────────────────────────────────────────
    "forgiveness": ["forgive", "forgave", "forgiven", "forgiving", "forgiveness",
                    "pardon", "mercy", "merciful", "grace", "absolution"],
    "patience": ["patience", "patient", "longsuffering", "endurance", "endure",
                 "perseverance", "persevere", "steadfast", "steadfastness"],
    "humility": ["humble", "humbled", "humility", "meek", "meekness", "lowliness",
                 "modest", "modesty"],
    "courage": ["courage", "courageous", "brave", "bravery", "bold", "boldness",
                "valor", "fearless"],
    "self_control": ["discipline", "disciplined", "self-control", "restraint",
                     "temperance", "moderation", "sober", "sobriety"],
    "generosity": ["generous", "generosity", "giving", "charitable", "charity",
                   "almsgiving", "openhanded"],

    # ── spiritual states ─────────────────────────────────────────────────
    "prayer": ["pray", "praying", "prayed", "prayer", "prayers", "intercession",
               "interceding", "supplication", "petition"],
    "faith": ["faith", "faithful", "faithfulness", "belief", "believe", "believing",
              "trust", "trusting", "trusted", "trustworthy", "devotion", "devout"],
    "repentance": ["repent", "repented", "repentance", "repenting", "contrite",
                   "contrition", "turning", "penitence"],
    "salvation": ["salvation", "saved", "redeemed", "redemption", "born-again",
                  "regeneration", "delivered", "deliverance"],
    "suffering": ["suffering", "suffer", "suffered", "affliction", "afflicted",
                  "trial", "trials", "tribulation", "hardship", "adversity",
                  "ordeal", "persecuted", "persecution"],
    "calling": ["calling", "vocation", "purpose", "mission", "destiny", "called",
                "summoned", "appointed"],

    # ── life events ──────────────────────────────────────────────────────
    "death": ["death", "died", "dying", "dead", "deceased", "passing", "passed",
              "funeral", "mortality"],
    "illness": ["sick", "sickness", "illness", "ill", "disease", "diagnosed",
                "diagnosis", "cancer", "ailment", "infirmity", "unwell"],
    "money": ["money", "finances", "financial", "debt", "debts", "bills", "income",
              "wages", "salary", "wealth", "riches", "savings"],
    "poverty": ["poverty", "poor", "broke", "destitute", "needy", "homeless",
                "hunger", "hungry", "starving"],
    "work": ["work", "working", "job", "jobs", "career", "employment", "employed",
             "unemployed", "unemployment", "occupation", "labor"],
    "decision": ["decision", "decide", "deciding", "decided", "choice", "choose",
                 "choosing", "chose", "crossroads", "discern", "discernment",
                 "guidance", "direction"],
}

# Reverse map: surface word -> concept id. First concept wins on any accidental
# duplicate (a curation error to avoid; build flags it below in __main__).
_WORD_TO_CONCEPT = {}
for _concept, _words in _CONCEPTS.items():
    for _w in _words:
        _WORD_TO_CONCEPT.setdefault(_w, _concept)


def canonical(token: str) -> str:
    """The token's concept id if it has one, else the token unchanged. This is the
    canonicalisation that makes synonyms collide on overlap (afraid, anxious ->
    'fear') WITHOUT inflating a literal self-match (afraid vs afraid -> 'fear', 1)."""
    return _WORD_TO_CONCEPT.get((token or "").lower(), token)


def signature(tokens: Iterable[str]) -> Set[str]:
    """The set of concept ids / literal tokens for an iterable of word stems. Used
    on BOTH sides of an overlap: shared concepts and shared literals each count
    once. Synonyms now meet; explainability is kept (concept ids read plainly:
    'fear', 'marriage', 'forgiveness')."""
    return {canonical(t) for t in tokens if t}


def surface_forms(concept: str) -> List[str]:
    """All surface words that express a concept (for query expansion)."""
    return list(_CONCEPTS.get(concept, []))


def expand_query(tokens: Iterable[str]) -> Set[str]:
    """Query expansion for retrieval: the original tokens PLUS every surface form
    of any concept they belong to, so a query word reaches documents that use a
    synonym. Returns the literal tokens unioned with their concept siblings."""
    out: Set[str] = set()
    for t in tokens:
        if not t:
            continue
        tl = t.lower()
        out.add(tl)
        c = _WORD_TO_CONCEPT.get(tl)
        if c:
            out.update(_CONCEPTS.get(c, ()))
    return out


def concepts_in(tokens: Iterable[str]) -> Set[str]:
    """The set of (named) concepts present in the tokens — used to count DISTINCT
    concepts when integrity wants 'two different ideas matched', not two synonyms
    of one idea."""
    return {c for c in (_WORD_TO_CONCEPT.get((t or "").lower()) for t in tokens) if c}


if __name__ == "__main__":
    # Curation guard: report any word claimed by two concepts (should be none).
    seen = {}
    dups = []
    for c, ws in _CONCEPTS.items():
        for w in ws:
            if w in seen and seen[w] != c:
                dups.append((w, seen[w], c))
            seen[w] = c
    print(f"concepts: {len(_CONCEPTS)} | surface words: {len(seen)} | duplicates: {len(dups)}")
    for w, a, b in dups:
        print(f"  DUP '{w}': {a} & {b}")
