"""Generate ready-to-paste social-media posts for each pilot.

Output: data/publish/<pilot>/social_posts.md
  - Twitter/X (280 char, two variants)
  - Threads
  - Bluesky
  - LinkedIn (long form)
  - Facebook
  - Reddit (r/oldtimeradio, r/scifi, r/Christianity, r/animation)
  - Hacker News title only
  - Email-blast template
"""
from __future__ import annotations
import argparse
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PUBLISH = REPO / "data" / "publish"

POSTS = {
    "soft_rains_v4": {
        "x_short": (
            "There Will Come Soft Rains — Ray Bradbury's 1950 story, broadcast on X Minus One in 1956, illustrated anew. "
            "Sci-Fi Theatre pilot. Free. Family-safe. \n\nwatch: narrowhighway.com/pilots.html"
        ),
        "x_quote": (
            "\"There will come soft rains, and the smell of the ground, and swallows circling with their shimmering sound...\"\n\n"
            "Sara Teasdale, 1918. Ray Bradbury, 1950. NBC, 1956. Now animated.\n\nnarrowhighway.com/pilots.html"
        ),
        "threads": (
            "We just published the pilot of Sci-Fi Theatre — Ray Bradbury's \"There Will Come Soft Rains\" "
            "(1950 story / 1956 X Minus One broadcast) given new animated visuals in the 1950 pulp magazine tradition. "
            "23 minutes. Family-safe. Closes with a pastoral observation. Free at narrowhighway.com/pilots.html — "
            "a curated internet for Christian families."
        ),
        "bluesky": (
            "🎬 Soft Rains — Bradbury 1950 / NBC 1956 — animated.\n\n"
            "First pilot of Sci-Fi Theatre on Narrow Highway. The audio is the original broadcast. The visuals are new. "
            "23 minutes, family-safe, free. With a pastoral close.\n\nnarrowhighway.com/pilots.html"
        ),
        "linkedin": (
            "Today we're releasing the pilot episode of Sci-Fi Theatre — an animated adaptation of Ray Bradbury's "
            "\"There Will Come Soft Rains\" (1950 short story / NBC X Minus One 1956 broadcast).\n\n"
            "The audio is the original 1956 NBC broadcast, untouched. The visuals are AI-rendered in the 1950 pulp magazine illustration tradition, "
            "animated in the Hanna-Barbera limited-animation style. 23 minutes. 1920×1080. Family-safe.\n\n"
            "Why we made it: Public-domain golden-age sci-fi radio drama is one of the great undervalued archives. Dimension X, X Minus One, "
            "Mercury Theatre — hundreds of episodes by Bradbury, Heinlein, Asimov, Vonnegut. Free to anyone. We're illustrating them "
            "for families who want classic literature in animated form, with a pastoral observation at the close of each episode.\n\n"
            "This is the first of twelve planned for the year. Watch the pilot: https://narrowhighway.com/pilots.html"
        ),
        "facebook": (
            "🎬 New pilot from Narrow Highway: \"There Will Come Soft Rains\" — Ray Bradbury's iconic 1950 story, animated.\n\n"
            "We took the original 1956 NBC radio broadcast (X Minus One) and added new visuals in the style of 1950s sci-fi magazine illustrations. "
            "23 minutes. Family-safe. Closes with a pastoral observation.\n\n"
            "Watch free at narrowhighway.com/pilots.html — a curated internet for Christian families."
        ),
        "reddit_oldtimeradio": (
            "Title: We animated the X Minus One \"There Will Come Soft Rains\" broadcast (1956)\n\n"
            "Body: Long-time OTR listener here. We took the original NBC X Minus One broadcast of Bradbury's \"There Will Come Soft Rains\" "
            "(Dec 5, 1956 — PD by non-renewal) and rendered new visuals in the 1950 pulp magazine illustration tradition, animated in the Hanna-Barbera "
            "limited-animation style. 23 minutes. Audio is the original broadcast, untouched. Free at narrowhighway.com/pilots.html.\n\n"
            "Why post here: a lot of you would recognize the broadcast immediately. Wanted to share + get feedback before we do the rest of X Minus One."
        ),
        "reddit_scifi": (
            "Title: Bradbury's \"There Will Come Soft Rains\" — fully animated (free, public domain audio + AI animation)\n\n"
            "Body: Animated adaptation of the 1956 X Minus One broadcast (PD audio) with new visuals in the 1950 pulp magazine tradition. "
            "23 min. Free. narrowhighway.com/pilots.html"
        ),
        "reddit_christianity": (
            "Title: Animated Bradbury for Christian families — \"There Will Come Soft Rains\" with a pastoral close\n\n"
            "Body: We've been building a curated internet for Christian families. Just released the pilot of Sci-Fi Theatre — Bradbury's classic adapted "
            "from the 1956 NBC broadcast with new animation. Each episode closes with a brief pastoral observation. This one's about "
            "Sara Teasdale's poem and the Father who weeps over the burning house. 23 min, family-safe, free. narrowhighway.com/pilots.html"
        ),
        "hn_title": "There Will Come Soft Rains (Bradbury 1950 + NBC 1956 audio + AI animation)",
        "email_blast": (
            "Subject: New from Narrow Highway: There Will Come Soft Rains, animated\n\n"
            "Dear friend,\n\n"
            "We just published the pilot episode of Sci-Fi Theatre — an animated adaptation of Ray Bradbury's \"There Will Come Soft Rains.\"\n\n"
            "The audio is the original 1956 NBC X Minus One broadcast. The visuals are AI-rendered in the 1950 pulp magazine illustration tradition. "
            "23 minutes. Family-safe. Closes with a brief pastoral observation about Sara Teasdale's poem and the Father who weeps over the burning house.\n\n"
            "Watch: https://narrowhighway.com/pilots.html\n\n"
            "If you enjoy it, the second pilot — Hundred Acre Theatre's adaptation of Milne's 1926 Winnie-the-Pooh Chapter 1 — is on the same page.\n\n"
            "Both are free. Both are family-safe. Both are part of a larger project to make the good ole days available to Christian families today.\n\n"
            "If you'd be willing to share with anyone you think might love this, we'd be grateful.\n\n"
            "Grace and peace,\nMatt"
        ),
    },
    "hundred_acre": {
        "x_short": (
            "Pooh, animated. Winnie-the-Pooh Chapter 1 (Milne 1926) — Hundred Acre Theatre pilot. 18 min. Family-safe. Free.\n\nnarrowhighway.com/pilots.html"
        ),
        "x_quote": (
            "\"Here is Edward Bear, coming downstairs now, bump, bump, bump, on the back of his head, behind Christopher Robin...\"\n\n"
            "A.A. Milne, 1926. PD as of 2022. Now illustrated anew.\n\nnarrowhighway.com/pilots.html"
        ),
        "threads": (
            "Hundred Acre Theatre Pilot 1 just dropped: A.A. Milne's original 1926 Winnie-the-Pooh Chapter 1, illustrated as Mr. Shepard "
            "first drew it, one hundred years ago. Public domain in the US since 2022. 18 minutes. Family-safe. Free at "
            "narrowhighway.com/pilots.html"
        ),
        "bluesky": (
            "🐻 Pooh Chapter 1 — Milne 1926 — animated.\n\n"
            "Public domain in the US since 2022. We illustrated it as Mr. Shepard first drew it. 18 minutes. Free.\n\n"
            "narrowhighway.com/pilots.html"
        ),
        "linkedin": (
            "We just released the pilot of Hundred Acre Theatre — an animated adaptation of A.A. Milne's original 1926 Winnie-the-Pooh, Chapter 1.\n\n"
            "Milne's text entered US public domain in January 2022. We illustrated it in the tradition of E.H. Shepard's first edition drawings. "
            "Audio is a CC0 LibriVox reading. 18 minutes. Family-safe. Closes with a pastoral observation.\n\n"
            "Visit: https://narrowhighway.com/pilots.html"
        ),
        "facebook": (
            "🐻 Winnie-the-Pooh Chapter 1 — animated as Mr. Shepard first drew it. New from Narrow Highway. 18 min. Family-safe. Free.\n\nnarrowhighway.com/pilots.html"
        ),
        "reddit_christianity": (
            "Title: Pooh, animated, with a pastoral close — Hundred Acre Theatre Pilot 1\n\n"
            "Body: A.A. Milne's original 1926 Winnie-the-Pooh, Chapter 1, illustrated and dramatized for Christian families. 18 min. "
            "Closes with: \"He sent His Son to lower us from the balloon.\" Family-safe, free. narrowhighway.com/pilots.html"
        ),
        "hn_title": "Winnie-the-Pooh Chapter 1, animated (Milne 1926, PD 2022)",
        "email_blast": (
            "Subject: New from Narrow Highway: Winnie-the-Pooh, Chapter 1, animated\n\n"
            "Dear friend,\n\n"
            "Today we're releasing the pilot of Hundred Acre Theatre — A.A. Milne's original 1926 Winnie-the-Pooh, Chapter 1, illustrated in the "
            "Shepard tradition. The book entered public domain in 2022. 18 minutes. Family-safe. Free.\n\n"
            "Watch: https://narrowhighway.com/pilots.html\n\n"
            "Closes with a brief pastoral observation:\n\n"
            "\"There is a kind of love that does not need its object to be clever, or useful, or even sensible. A small boy can love a foolish bear. "
            "There is one Father who loves us like that, while we are yet foolish — and while we are yet covered in mud. He sent His Son to lower us from the balloon.\"\n\n"
            "Grace and peace,\nMatt"
        ),
    },
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pilot", required=True)
    args = ap.parse_args()
    posts = POSTS.get(args.pilot)
    if not posts:
        print(f"Unknown pilot: {args.pilot}")
        return

    out_dir = PUBLISH / args.pilot
    out_dir.mkdir(parents=True, exist_ok=True)

    lines = [f"# Social-media posts — {args.pilot}\n",
             "Copy-paste each below into the matching platform. Both the X char count and Bluesky 300-char cap are respected.\n"]
    for platform, text in posts.items():
        lines.append(f"## {platform}\n")
        lines.append("```")
        lines.append(text)
        lines.append("```\n")
    out = out_dir / "social_posts.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
