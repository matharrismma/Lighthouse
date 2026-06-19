#!/usr/bin/env python3
"""Go through past conversations CHEAPLY — harvest the operator's directives.

Matt: "Can you go through our past conversations more cheaply than new? ... Any
truth we find, we need to keep. I don't want to pay for it twice."

The session transcripts (~400MB of JSONL) are far too big to read into a model's
context — that would be paying for it twice (and then some). But they are local
files, so a plain STREAMING PASS (file I/O + filtering, ~zero model cost) can pull
out the operator's own turns — the directives, the seeds, the corrections — and
write them to a small digest. A human (or a cheap follow-up) then curates the
genuinely-new truths into the keep (api/teachings.py), so each is captured once.

Cheap by construction: streams line by line (constant memory), no model calls,
stdlib only. Reads ~/.claude/projects/<dir>/*.jsonl.

    python tools/harvest_transcripts.py [--dir <transcripts dir>] [--max-len 2000]
"""
import argparse
import glob
import json
import os
import re

# Noise that is NOT an operator directive: slash-command bodies, tool results,
# system reminders, interrupt markers, pasted skill text.
_NOISE = (
    "<command-name>", "<command-message>", "<command-args>", "system-reminder",
    "tool_result", "[Request interrupted", "## Parsing", "ScheduleWakeup",
    "<task-notification>", "stdout", "Caveat:", "antml:", "function_results",
)


def _texts_from(content):
    """Pull plain user text out of a message 'content' (string or block list)."""
    if isinstance(content, str):
        return [content]
    out = []
    if isinstance(content, list):
        for b in content:
            if isinstance(b, dict) and b.get("type") == "text" and isinstance(b.get("text"), str):
                out.append(b["text"])
            elif isinstance(b, str):
                out.append(b)
    return out


def harvest(transcripts_dir, max_len=2000):
    seen = set()
    out = []
    files = sorted(glob.glob(os.path.join(transcripts_dir, "*.jsonl")))
    scanned = 0
    for path in files:
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:  # streaming — constant memory
                    line = line.strip()
                    if not line or '"user"' not in line:
                        continue
                    try:
                        ev = json.loads(line)
                    except Exception:
                        continue
                    msg = ev.get("message") or {}
                    if (ev.get("type") != "user") or (msg.get("role") != "user"):
                        continue
                    for t in _texts_from(msg.get("content")):
                        t = (t or "").strip()
                        scanned += 1
                        if not (8 <= len(t) <= max_len):
                            continue
                        if any(n in t for n in _NOISE):
                            continue
                        key = re.sub(r"\s+", " ", t.lower())[:200]
                        if key in seen:
                            continue
                        seen.add(key)
                        out.append({"text": t, "source": os.path.basename(path)})
        except Exception:
            continue
    return out, scanned, files


def main():
    default_dir = os.path.join(os.path.expanduser("~"), ".claude", "projects",
                               "C--Users-hdven-OneDrive-Desktop")
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir", default=default_dir)
    ap.add_argument("--max-len", type=int, default=2000)
    args = ap.parse_args()

    cands, scanned, files = harvest(args.dir, args.max_len)
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(root, "data", "teachings")
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, "harvest_candidates.jsonl")
    with open(out_path, "w", encoding="utf-8") as f:
        for c in cands:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")

    total_mb = sum(os.path.getsize(p) for p in files) / 1e6
    print("scanned %d files (%.0f MB), %d user blocks -> %d candidate directives"
          % (len(files), total_mb, scanned, len(cands)))
    print("written: %s" % out_path)
    print("--- a few candidates ---")
    for c in cands[:12]:
        print("  [%s] %s" % (c["source"][:8], c["text"][:90].replace("\n", " ")))


if __name__ == "__main__":
    main()
