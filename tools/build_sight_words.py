#!/usr/bin/env python3
"""Author the high-frequency / "heart word" units for the K-3 reading curriculum.

The phonics track teaches DECODING; but a child cannot read real text without the most
common high-frequency words (the, of, was, you, are ...), many of which are irregular.
This adds them honestly, using the Science-of-Reading "heart word" approach: teach the
REGULAR letters normally and learn only the one TRICKY part "by heart" -- and where a
so-called sight word is actually decodable by a rule (open-syllable he/she/we/me/be),
SAY SO rather than tell a child to memorize what they can sound out. The first ~30
high-frequency words make up a large share of all text, so this is the single biggest
unlock after basic phonics.

Idempotent: removes any existing track="phonics_sight_words" units, then appends these.
Output: appends to data/phonics/units.jsonl (served by GET /phonics + /phonics/{id}).

Usage:  python tools/build_sight_words.py
"""
from __future__ import annotations

import json
from pathlib import Path

TRACK = "phonics_sight_words"
_MODES = [
    {"id": "coach_reads", "label": "Coach reads",
     "instruction": "Adult reads each word, points to the HEART part (the tricky letter), names "
                    "why it is tricky, then reads the decodable sentence aloud while pointing.",
     "script": "Watch my finger. This word is 'the'. The hard part is the e -- it says /uh/. "
               "The 'th' you already know."},
    {"id": "take_turns", "label": "Take turns",
     "instruction": "Adult reads the first word, child the next, alternating down the list, then "
                    "swap and read the sentence together a word each.",
     "script": "My turn: the first word. Your turn: the next one."},
    {"id": "i_read", "label": "I read",
     "instruction": "Child reads the words then the sentence. Stuck on a heart word -> Echo (adult "
                    "says it), name the heart part, then Repeat. Stuck on a decodable one -> sound it out.",
     "script": "You read them now. If a word is tricky, I'll show you its heart."},
]
_WEDGES = ["wedge_repeat", "wedge_echo", "wedge_chunk", "wedge_phonics", "wedge_praise"]
_DOMAINS = ["linguistics", "reading", "pedagogy"]
_AXES = ["information_encoding", "authority_trust"]

UNITS = [
    {
        "id": "sight_words_set_1", "seq": 1,
        "title": "Heart words, set 1 -- the, a, I, to, and",
        "rule": "Some words appear so often you must know them INSTANTLY -- you cannot sound out a "
                "whole book one letter at a time. Most of these high-frequency words are MOSTLY "
                "regular: sound out the regular letters and learn only the one TRICKY part 'by heart'. "
                "That tricky part is the word's HEART. and = /a/ /n/ /d/ (fully regular -- no heart). "
                "a = says a quick /uh/ (schwa). I = always a CAPITAL letter and says its long name /i/. "
                "the = 'th' is regular; the e is the HEART (says /uh/, not short /e/). to = t is regular; "
                "the o is the HEART (says /oo/, not short /o/).",
        "examples": ["and -- /a/ /n/ /d/, fully decodable, no heart",
                     "a -- one letter, a quick /uh/ (schwa)",
                     "I -- always capital, says its name /i/",
                     "the -- th + e; the e is the HEART (/uh/)",
                     "to -- t + o; the o is the HEART (/oo/)"],
        "decodable_sentence": "I go to the dog and the cat.",
        "check": {"prompt": "In the word 'the', which letter is the heart (the part you learn by "
                            "heart), and what does the rest say?",
                  "answer": "The HEART is the e -- it says /uh/ here, not its usual short /e/. The "
                            "rest, 'th', is a regular digraph you already know /th/. So 'the' = /th/ + /uh/.",
                  "teaching_note": "Frame every high-frequency word as 'mostly regular + a small heart'. "
                                   "It is far less to remember than a whole word, and it keeps decoding "
                                   "the main strategy."},
        "prerequisites": ["phonics_letter_sounds"], "next": "sight_words_set_2",
        "summary": "The five most common words. and is fully decodable; a and I are one-piece; the "
                   "and to each carry a single 'heart' (e=/uh/, o=/oo/). Introduces the heart-word idea.",
    },
    {
        "id": "sight_words_set_2", "seq": 2,
        "title": "Heart words, set 2 -- is, it, in, on, at",
        "rule": "Five short, common words. FOUR are fully decodable (it, in, on, at) -- just practice "
                "until they are instant, no heart needed. ONE has a heart: is = /i/ + s, but the s says "
                "/z/ (feel your throat buzz). Knowing which words need a heart and which are just "
                "regular keeps a reader from 'memorizing' words they can already sound out.",
        "examples": ["it -- /i/ /t/ decodable", "in -- /i/ /n/ decodable", "on -- /o/ /n/ decodable",
                     "at -- /a/ /t/ decodable", "is -- /i/ + s, but s says /z/ (HEART)"],
        "decodable_sentence": "The cat is on it. A bug is in the cup.",
        "check": {"prompt": "Of these four -- it, in, is, at -- one has a heart and three do not. "
                            "Which one, and why?",
                  "answer": "'is' has the heart: the s says /z/, not /s/. The other three (it, in, at) "
                            "follow the regular closed-syllable short-vowel pattern, so they are fully "
                            "decodable.",
                  "teaching_note": "The 's says /z/' pattern returns in many words (his, has, was, as). "
                                   "Naming it once here pays off repeatedly."},
        "prerequisites": ["sight_words_set_1"], "next": "sight_words_set_3",
        "summary": "Four fully-decodable high-frequency words plus 'is' (s=/z/). Teaches the learner to "
                   "tell decodable words from true heart words.",
    },
    {
        "id": "sight_words_set_3", "seq": 3,
        "title": "Heart words, set 3 -- of, you, was, for, are",
        "rule": "The BIG tricky ones -- the most irregular high-frequency words, mostly heart. Learn "
                "them slowly and on purpose. of: looks like 'off' but the f says /v/ -> /u/ /v/. you: "
                "y + 'ou' saying /oo/. was: the a says /o/ and the s says /z/ -> /w/ /o/ /z/. for: the "
                "'or' is r-controlled (a regular pattern -- the r changes the vowel) -> /for/. are: "
                "almost all heart, says /ar/ (also r-controlled).",
        "examples": ["of -- /u/ /v/; the f says /v/, so it sounds like 'uv', NOT 'off'",
                     "you -- /y/ /oo/; the 'ou' says /oo/",
                     "was -- /w/ /o/ /z/; the a says /o/, the s says /z/",
                     "for -- /f/ + r-controlled 'or' -> /for/ (a regular pattern)",
                     "are -- /ar/; r-controlled, mostly heart"],
        "decodable_sentence": "You are for the dog. It was a cup of jam.",
        "check": {"prompt": "What is the most surprising thing about the word 'of', and what does it "
                            "actually sound like?",
                  "answer": "The f says /v/ (not /f/), so 'of' sounds like 'uv' -- it does NOT rhyme "
                            "with 'off'. The o is a quick schwa /u/. 'of' is one of the few words where "
                            "f says /v/, so it is worth memorizing that heart.",
                  "teaching_note": "Contrast 'of' (/uv/) with 'off' (/of/) directly -- children routinely "
                                   "confuse them. Say both, exaggerate the /v/ vs /f/."},
        "prerequisites": ["sight_words_set_2"], "next": "sight_words_set_4",
        "summary": "The hardest common irregulars (of, you, was) plus two r-controlled words (for, are) "
                   "that are regular once r-control is known. The heaviest heart-word load.",
    },
    {
        "id": "sight_words_set_4", "seq": 4,
        "title": "Not heart words at all -- he, she, we, me, be",
        "rule": "These five look like sight words but they are NOT -- they share a RULE. When a vowel "
                "is the LAST letter of a syllable (an 'open syllable'), it says its long name. So the e "
                "says /ee/. he, she, we, me, be are all just consonant + /ee/. Never make a child "
                "memorize a word they can decode -- teach the rule instead. (Compare: in 'met' the e is "
                "closed in by t, so it says short /e/; in 'me' the e is open, so it says long /ee/.)",
        "examples": ["he -- /h/ /ee/", "she -- /sh/ /ee/", "we -- /w/ /ee/",
                     "me -- /m/ /ee/", "be -- /b/ /ee/"],
        "decodable_sentence": "He and she can see me. We can be glad.",
        "check": {"prompt": "Why does the e say long /ee/ in 'me' but short /e/ in 'met'?",
                  "answer": "In 'me' the e is the LAST letter -- an OPEN syllable -- so it says its long "
                            "name /ee/. In 'met' the e is closed in by the t -- a CLOSED syllable -- so it "
                            "says short /e/. Open syllable = long vowel; closed syllable = short vowel.",
                  "teaching_note": "This is the honest core of the lesson: many 'sight words' are "
                                   "decodable by rule. Teaching the open-syllable rule here removes guessing "
                                   "and transfers to go, so, hi, no, my, and hundreds more."},
        "prerequisites": ["sight_words_set_3"], "next": "sight_words_set_5",
        "summary": "The open-syllable rule (final vowel says its long name) -- he/she/we/me/be are "
                   "decodable, not sight words. Replaces memorizing with a transferable rule.",
    },
    {
        "id": "sight_words_set_5", "seq": 5,
        "title": "Heart words, set 5 -- this, that, then, with, them",
        "rule": "Five very common words that all use the digraph 'th'. Every one is DECODABLE once you "
                "know th -> th + short vowel (+ consonant). Practice them for SPEED, not memorization. "
                "(Tiny note: the s in 'this' drifts toward /z/ for some speakers -- a soft heart at most.)",
        "examples": ["this -- /th/ /i/ /s/", "that -- /th/ /a/ /t/", "then -- /th/ /e/ /n/",
                     "with -- /w/ /i/ /th/", "them -- /th/ /e/ /m/"],
        "decodable_sentence": "This is for them. Then that cat sat with us.",
        "check": {"prompt": "Are these (this, that, then, with, them) mostly heart words or mostly "
                            "decodable, and why?",
                  "answer": "Mostly DECODABLE. Once you know the 'th' digraph, they follow the regular "
                            "closed-syllable pattern (th + short vowel + consonant). At most, the s in "
                            "'this' leans toward /z/. So practice them for fluency, don't memorize them.",
                  "teaching_note": "Ending the set on decodable words reinforces the throughline: reach "
                                   "for decoding first; reserve 'by heart' only for the genuine tricky part."},
        "prerequisites": ["sight_words_set_4"], "next": None,
        "summary": "Five th- words, all decodable -- closes the set by reinforcing that most "
                   "high-frequency words are sounded out, with heart reserved for true irregularities.",
    },
]


def _to_unit(u):
    return {
        "id": u["id"], "title": u["title"], "unit_seq": u["seq"], "track": TRACK,
        "rule": u["rule"], "examples": u["examples"],
        "decodable_sentence": u["decodable_sentence"],
        "modes": _MODES, "check": u["check"], "wedges": _WEDGES,
        "prerequisites": u["prerequisites"], "next": u["next"],
        "summary": u["summary"], "domains": _DOMAINS, "axes": _AXES,
    }


def main():
    path = Path(__file__).resolve().parents[1] / "data" / "phonics" / "units.jsonl"
    kept = []
    if path.exists():
        for ln in path.read_text(encoding="utf-8").splitlines():
            s = ln.strip()
            if not s:
                continue
            try:
                if json.loads(s).get("track") == TRACK:
                    continue   # drop old sight-word units (idempotent)
            except Exception:
                pass
            kept.append(s)
    new = [json.dumps(_to_unit(u), ensure_ascii=False) for u in UNITS]
    path.write_text("\n".join(kept + new) + "\n", encoding="utf-8")
    print(f"kept {len(kept)} existing + added {len(new)} sight-word units -> {path}")


if __name__ == "__main__":
    main()
