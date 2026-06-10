#!/usr/bin/env python3
"""office_corpus.py — build the three offices' training corpora (no-lineage path).

The endgame: three small models trained FROM SCRATCH on our own data — no
lineage, "without descent." That makes the corpus the whole foundation, so this
generator is strict: every pair is validated against the FIXED label space
(data/offices/label_space.json), deduplicated, and split into train/eval. A
strong teacher (Anthropic) plays each office using its decision policy + the
CURRENT vocabulary; only clean, in-vocabulary pairs are kept.

Outputs (per office):
  data/training_corpus/offices/<office>.train.jsonl   — clean validated pairs
  data/training_corpus/offices/<office>.eval.jsonl    — held-out (~10%)
Both in narrowhighway.office_pair/1 shape, meta.via="teacher_distill".
(The organic live-minted <office>.jsonl is left untouched.)

Spend-guarded. Dry-run by default; --apply spends. Concurrent + resumable —
safe to run detached (nohup) and re-run to continue.

Usage:
    python tools/office_corpus.py --office all --count 1200            # dry-run plan
    nohup python tools/office_corpus.py --office all --count 1200 --apply \
        > /tmp/office_corpus.log 2>&1 &
"""

from __future__ import annotations

import argparse
import json
import os
import random
import re
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

REPO_ROOT = Path(os.environ.get(
    "NH_REPO_ROOT", str(Path(__file__).resolve().parent.parent))).resolve()
sys.path.insert(0, str(REPO_ROOT / "tools"))
OFFICE_DIR = REPO_ROOT / "data" / "training_corpus" / "offices"
LABEL_PATH = REPO_ROOT / "data" / "offices" / "label_space.json"

TEACHER_DECISION = os.environ.get("NH_BASE_MODEL", "claude-sonnet-4-5")
TEACHER_INPUTS = os.environ.get("NH_HAIKU_MODEL", "claude-haiku-4-5-20251001")
EST_DECISION = 0.006
EST_INPUT_BATCH = 0.01

# ── Fixed label space (loaded; falls back to inline if file missing) ──
try:
    LABELS = json.loads(LABEL_PATH.read_text("utf-8"))
except Exception:
    LABELS = {}

_STEWARD_DECISIONS = {"keep": {"admit", "quarantine", "deny"},
                      "provision": {"work", "yield"},
                      "build": {"build", "defer"}}


def _valid(office: str, d: dict) -> bool:
    """Validate a teacher decision against the fixed label space. Clean targets
    only — out-of-vocabulary pairs are dropped, not coerced."""
    ls = LABELS.get(office, {})
    if not isinstance(d, dict):
        return False
    if office == "shepherd":
        a = d.get("action")
        if a not in ("ask", "route"):
            return False
        if a == "route" and d.get("tool") not in ls.get("tool", []):
            return False
        return True
    if office == "scribe":
        return (d.get("kind") in ls.get("kind", []) and
                d.get("route") in ls.get("route", []))
    if office == "steward":
        asp = d.get("aspect")
        if asp not in ls.get("aspect", []):
            return False
        if d.get("decision") not in _STEWARD_DECISIONS.get(asp, set()):
            return False
        if asp == "keep":
            if d.get("gate") not in ("RED", "FLOOR", "BROTHERS", "GOD"):
                return False
        else:
            d["gate"] = ""  # normalize: gate only applies to keep
        return True
    return True


# ── Office decision policies (current vocabulary, no-lineage targets) ──
OFFICES = {
    "shepherd": {
        "input_spec": ("a single thing a Christian person brings to the Shepherd — a "
                       "question, a worry, an idea, a teaching to weigh, a verse question, "
                       "a claim to check, a parenting/homeschool need, or a message to send"),
        "system": (
            "You are the Shepherd of the Narrow Highway household. Through brief "
            "discernment, EITHER ask one short clarifying question (only if the right help "
            "is genuinely unclear) OR route to the proper tool. Tools: discern (weigh a "
            "teaching/claim through the four gates), walk (surface related cards), verify "
            "(a factual/computational claim), scripture (resolve/study a verse), teach "
            "(open the learning pathway), draft (draft a message for the person's review; "
            "never sent). Respond with ONLY JSON: "
            '{"action":"ask","say":"..."} or '
            '{"action":"route","tool":"discern|walk|verify|scripture|teach|draft","query":"..."}'),
    },
    "scribe": {
        "input_spec": ("a single raw item that lands in the box and needs filing — a note, "
                       "a task, a question, submitted content, a message to send, a testimony"),
        "system": (
            "You are the Scribe of the Narrow Highway household. Sort and file the item. "
            "Respond with ONLY JSON: "
            '{"kind":"question|idea|task|message|content|testimony",'
            '"route":"shepherd|well|learn|discern|draft|keep|outside","tags":["short"]}'),
    },
    "steward": {
        "input_spec": ("a single situation the Steward must decide — an item at the airlock "
                       "to verify; OR a resource/load/budget state; OR a substrate gap to maybe build"),
        "system": (
            "You are the Steward — keeper and quartermaster. Decide faithfully. "
            "Respond with ONLY JSON: "
            '{"aspect":"keep|provision|build",'
            '"decision":"(keep: admit|quarantine|deny ; provision: work|yield ; build: build|defer)",'
            '"gate":"(keep only: RED|FLOOR|BROTHERS|GOD ; else empty)"}'),
    },
}

TOPIC_SEEDS = [
    "Christian living", "parenting", "marriage", "homeschool", "phonics and early reading",
    "a popular teaching to weigh", "a sermon claim", "a Bible verse in context",
    "a hard providence", "doubt and anxiety", "church drift", "prayer", "fasting",
    "money and contentment", "work and vocation", "a recommended book or product",
    "a recipe or household task", "apologetics", "a cult or false teaching", "end-times claims",
    "a factual claim to check", "a number or statistic", "a historical date", "science vs faith",
    "a testimony to record", "content someone submitted", "forgiveness", "discipline of children",
    "friendship and community", "loneliness", "grief", "calling and gifts", "stewardship of time",
    "evangelism", "the sacraments", "denominational differences", "a verse that troubles them",
    "raising teens", "media and screens", "a moral dilemma at work",
]
ANGLES = [
    "as a worried parent", "terse, just a few words", "as a new believer", "as a skeptic",
    "calm and curious", "anxious", "comparing two views", "asking for a child", "in plain words",
    "a bit rambling", "very specific", "vague and unsure", "in a hurry",
]


def _load_key() -> str:
    k = os.environ.get("ANTHROPIC_API_KEY", "")
    if k:
        return k.strip().lstrip("<").rstrip(">")
    for d in [REPO_ROOT, Path(__file__).parent]:
        ef = d / ".env"
        if ef.exists():
            for line in ef.read_text("utf-8", errors="replace").splitlines():
                m = re.match(r"ANTHROPIC_API_KEY=(.+)", line.strip())
                if m:
                    return m.group(1).strip().strip('"').strip("'").lstrip("<").rstrip(">")
    return ""


def _client():
    import anthropic
    return anthropic.Anthropic(api_key=_load_key())


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip().lower())[:300]


def _extract_json(text: str):
    m = re.search(r"\{.*\}", text, re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def _train_path(o: str) -> Path:
    return OFFICE_DIR / f"{o}.train.jsonl"


def _eval_path(o: str) -> Path:
    return OFFICE_DIR / f"{o}.eval.jsonl"


def existing_prompts(office: str) -> set:
    """Normalized prompts already present (train + eval + organic live) — for dedup/resume."""
    seen = set()
    for p in (_train_path(office), _eval_path(office), OFFICE_DIR / f"{office}.jsonl"):
        if not p.exists():
            continue
        for line in p.read_text("utf-8", errors="replace").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                seen.add(_norm(json.loads(line).get("prompt", "")))
            except Exception:
                continue
    return seen


def gen_inputs(client, office: str, n: int, exclude: set) -> list:
    spec = OFFICES[office]["input_spec"]
    out, seen, attempts = [], set(exclude), 0
    while len(out) < n and attempts < (n // 8 + 12):
        attempts += 1
        chunk = min(15, n - len(out))
        seeds = ", ".join(random.sample(TOPIC_SEEDS, k=min(6, len(TOPIC_SEEDS))))
        angle = random.choice(ANGLES)
        prompt = (f"Generate {chunk} varied, realistic, DISTINCT examples of {spec}. "
                  f"Phrase them {angle}. Spread across these themes: {seeds}. "
                  f"One or two sentences each, a real person's voice. "
                  f"Output ONLY a JSON array of {chunk} strings.")
        try:
            resp = client.messages.create(model=TEACHER_INPUTS, max_tokens=1500,
                                          messages=[{"role": "user", "content": prompt}])
            raw = "".join(getattr(b, "text", "") for b in resp.content)
            arr = re.search(r"\[.*\]", raw, re.DOTALL)
            items = json.loads(arr.group(0)) if arr else []
        except Exception as e:
            print(f"[office] input-gen {office}: {str(e)[:100]}", file=sys.stderr)
            items = []
        for x in items:
            xs = str(x).strip()
            nk = _norm(xs)
            if xs and nk not in seen:
                seen.add(nk)
                out.append(xs)
        try:
            import spend_guard
            spend_guard.record(f"bg_office_inputs_{office}", EST_INPUT_BATCH)
        except Exception:
            pass
    return out[:n]


def decide(client, office: str, text: str) -> dict | None:
    system = OFFICES[office]["system"]
    for attempt in range(3):
        try:
            resp = client.messages.create(model=TEACHER_DECISION, max_tokens=400,
                                          system=system,
                                          messages=[{"role": "user", "content": text}])
            return _extract_json("".join(getattr(b, "text", "") for b in resp.content))
        except Exception as e:
            if attempt == 2:
                print(f"[office] decide {office}: {str(e)[:100]}", file=sys.stderr)
            else:
                import time
                time.sleep(2 * (attempt + 1))
    return None


_write_lock = threading.Lock()


def _write(office: str, prompt: str, completion: dict, split: str) -> None:
    rec = {"schema": "narrowhighway.office_pair/1", "office": office, "prompt": prompt,
           "completion": json.dumps(completion, ensure_ascii=False),
           "at": datetime.now(timezone.utc).isoformat(),
           "meta": {"via": "teacher_distill", "teacher": TEACHER_DECISION, "split": split}}
    path = _eval_path(office) if split == "eval" else _train_path(office)
    with _write_lock:
        OFFICE_DIR.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


# ── Balanced (class-targeted) generation ──────────────────────────────
# The standard run lets the teacher choose labels freely → class imbalance
# (majority label dominates → from-scratch classifiers collapse to it). The
# balanced run targets EACH class with class-conditional input hints, then
# filters labels back to the target so each class gets equal representation.
# This is the proven lever once the model dimension is exhausted.
BALANCED_HINTS = {
    "shepherd": {
        "tool": {
            "verify":    "a specific factual or numerical claim that needs checking — a number, a date, a scientific or historical fact",
            "scripture": "a specific Bible verse, passage, or scripture question — what does X say, look up Y, the context of Z",
            "teach":     "a request to start or continue teaching a child — phonics, reading, math, a lesson, a homeschool subject",
            "draft":     "a request to compose or send a written message — an email, a reply, a letter, a note",
            "walk":      "an open-ended exploratory question — what connects to this, what's related, browsing a theme",
            "discern":   "a teaching, sermon, doctrine, or claim that needs weighing through Scripture and the four gates",
        },
        "action": {
            "ask":       "a VAGUE, partial, or ambiguous user thought that does NOT clearly indicate what help is needed — too little context to route",
        },
    },
    "scribe": {
        "route": {
            "shepherd":  "a question or thought that should go to the Shepherd for discernment first",
            "well":      "a fact, source, or knowledge item to add to the substrate (the Well)",
            "learn":     "homeschool / curriculum / lesson material — educational content for children",
            "discern":   "a teaching or claim that needs the discernment engine's four-gate weighing",
            "draft":     "a message or reply that needs to be drafted for the user's review (never auto-sent)",
            "keep":      "personal notes, records, or testimonies to keep — journal entries, things to remember",
            "outside":   "a question or task that should be referred to an external resource",
        },
    },
    "steward": {
        # Cover all 7 valid (aspect, decision) combos. For keep we mention the
        # gate in the hint so gates also get balanced organically.
        "_combo": {
            ("keep", "admit"):      "an item arriving at the airlock with clear evidence, named sources, witnesses present — passes all four gates",
            ("keep", "quarantine"): "an item that's incomplete or ambiguous — sources unverified, witness count below threshold (fails BROTHERS gate)",
            ("keep", "deny"):       "an item with disqualifying material — heretical claim, advocates sin, plainly contradicts Scripture (fails RED gate)",
            ("provision", "work"):  "an idle resource state with budget headroom — live demand low, background work can proceed",
            ("provision", "yield"): "a high-load or low-budget resource state — live traffic is busy, background work should yield",
            ("build", "build"):     "a clear, scoped capability gap with demand evidence — worth building",
            ("build", "defer"):     "a build proposal lacking demand, scope, or alignment — defer",
        },
    },
}


def gen_targeted_inputs(client, office: str, hint: str, n: int, exclude: set) -> list:
    """Generate n unique inputs constrained to match a per-class hint."""
    out, seen, attempts = [], set(exclude), 0
    while len(out) < n and attempts < (n // 8 + 14):
        attempts += 1
        chunk = min(15, n - len(out))
        topics = ", ".join(random.sample(TOPIC_SEEDS, k=min(6, len(TOPIC_SEEDS))))
        angle = random.choice(ANGLES)
        prompt = (f"Generate {chunk} varied, realistic, DISTINCT examples that match "
                  f"THIS PATTERN: {hint}\n\n"
                  f"Phrase them {angle}. Touch on these themes: {topics}. "
                  f"One or two sentences each, a real person's voice. "
                  f"Output ONLY a JSON array of {chunk} strings.")
        try:
            resp = client.messages.create(model=TEACHER_INPUTS, max_tokens=1500,
                                          messages=[{"role": "user", "content": prompt}])
            raw = "".join(getattr(b, "text", "") for b in resp.content)
            arr = re.search(r"\[.*\]", raw, re.DOTALL)
            items = json.loads(arr.group(0)) if arr else []
        except Exception as e:
            print(f"[balanced] input-gen {office}: {str(e)[:100]}", file=sys.stderr)
            items = []
        for x in items:
            xs = str(x).strip()
            nk = _norm(xs)
            if xs and nk not in seen:
                seen.add(nk)
                out.append(xs)
        try:
            import spend_guard
            spend_guard.record(f"bg_office_inputs_balanced_{office}", EST_INPUT_BATCH)
        except Exception:
            pass
    return out[:n]


def _balanced_targets(office: str) -> list:
    """Return list of (description, field, target_value, hint, aspect_filter)."""
    out = []
    h = BALANCED_HINTS.get(office, {})
    if office == "steward":
        for (asp, dec), hint in h.get("_combo", {}).items():
            out.append((f"aspect={asp}/decision={dec}", "decision", dec, hint, asp))
    else:
        for field, classes in h.items():
            for cls, hint in classes.items():
                out.append((f"{field}={cls}", field, cls, hint, None))
    return out


def _matches_target(field: str, target: str, decision: dict, aspect_filter) -> bool:
    if aspect_filter is not None and decision.get("aspect") != aspect_filter:
        return False
    return decision.get(field) == target


def run_balanced(office: str, per_class: int, apply: bool, workers: int, eval_frac: float) -> tuple:
    targets = _balanced_targets(office)
    if not targets:
        print(f"[balanced] {office}: no class targets defined.")
        return (0, 0)
    n_combos = len(targets)
    est = per_class * n_combos * (EST_DECISION + EST_INPUT_BATCH / 12) * 1.4  # +40% filter loss
    if not apply:
        print(f"  — DRY RUN — {office}: {n_combos} class-targets × ~{per_class} each "
              f"(~${est:.2f} with filter loss), {workers} workers")
        for desc, *_ in targets:
            print(f"    · {desc}")
        return (0, 0)

    try:
        import spend_guard
    except Exception:
        print("[balanced] spend_guard unavailable.", file=sys.stderr)
        return (0, 0)
    if not spend_guard.can_spend(est):
        print(f"[balanced] OVER BUDGET — remaining ${spend_guard.remaining()}, need ~${est:.2f}",
              file=sys.stderr)
        return (0, 0)
    if not _load_key():
        print("[balanced] no ANTHROPIC_API_KEY.", file=sys.stderr)
        return (0, 0)

    client = _client()
    seen = existing_prompts(office)
    print(f"[balanced] {office}: {len(seen)} existing; {n_combos} class-targets × {per_class} each…")

    kept_total = dropped_total = 0
    for desc, field, target, hint, aspect_filter in targets:
        n_gen = int(per_class * 1.5)  # over-generate to absorb filter loss
        inputs = gen_targeted_inputs(client, office, hint, n_gen, seen)
        seen |= {_norm(t) for t in inputs}
        kept = dropped = 0
        with ThreadPoolExecutor(max_workers=workers) as ex:
            futs = {ex.submit(decide, client, office, t): t for t in inputs}
            for fut in as_completed(futs):
                text = futs[fut]
                if kept >= per_class:
                    continue  # got enough; remaining results discarded
                d = fut.result()
                if not (d and _valid(office, d)):
                    dropped += 1
                    continue
                if not _matches_target(field, target, d, aspect_filter):
                    dropped += 1
                    continue
                split = "eval" if random.random() < eval_frac else "train"
                _write(office, text, d, split)
                kept += 1
                try:
                    spend_guard.record(f"bg_office_balanced_{office}", EST_DECISION)
                except Exception:
                    pass
        print(f"  · {desc}: kept {kept} (dropped {dropped})")
        kept_total += kept
        dropped_total += dropped
    print(f"[balanced] {office}: kept {kept_total} (dropped {dropped_total}) -> "
          f"{office}.train.jsonl / .eval.jsonl")
    return (kept_total, dropped_total)


def run_office(office: str, count: int, apply: bool, workers: int, eval_frac: float) -> tuple:
    est = count * (EST_DECISION + EST_INPUT_BATCH / 12)
    if not apply:
        print(f"  — DRY RUN — {office}: up to {count} pairs (~${est:.2f}), {workers} workers, "
              f"eval_frac={eval_frac}, teacher={TEACHER_DECISION}")
        return (0, 0)
    try:
        import spend_guard
    except Exception:
        print("[office] spend_guard unavailable — refusing to spend.", file=sys.stderr)
        return (0, 0)
    if not spend_guard.can_spend(est):
        print(f"[office] OVER BUDGET — remaining ${spend_guard.remaining()}; need ~${est:.2f}",
              file=sys.stderr)
        return (0, 0)
    if not _load_key():
        print("[office] no ANTHROPIC_API_KEY.", file=sys.stderr)
        return (0, 0)

    client = _client()
    seen = existing_prompts(office)
    print(f"[office] {office}: {len(seen)} existing; generating up to {count} inputs…")
    inputs = gen_inputs(client, office, count, seen)
    print(f"[office] {office}: {len(inputs)} unique new inputs; labeling with {workers} workers…")

    kept = dropped = 0
    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {ex.submit(decide, client, office, t): t for t in inputs}
        for i, fut in enumerate(as_completed(futs), 1):
            text = futs[fut]
            d = fut.result()
            if d and _valid(office, d):
                split = "eval" if random.random() < eval_frac else "train"
                _write(office, text, d, split)
                kept += 1
                try:
                    spend_guard.record(f"bg_office_{office}", EST_DECISION)
                except Exception:
                    pass
            else:
                dropped += 1
            if i % 50 == 0:
                print(f"   · {office}: {i}/{len(inputs)} (kept {kept}, dropped {dropped})")
    print(f"[office] {office}: kept {kept} (dropped {dropped} out-of-vocab) -> "
          f"{office}.train.jsonl / .eval.jsonl")
    return (kept, dropped)


def main() -> int:
    ap = argparse.ArgumentParser(description="Build the offices' training corpora")
    ap.add_argument("--office", choices=["shepherd", "scribe", "steward", "all"], default="all")
    ap.add_argument("--count", type=int, default=1200, help="target inputs per office (standard mode)")
    ap.add_argument("--balanced", action="store_true",
                    help="class-balanced mode: generate per (field, class) target with filtering")
    ap.add_argument("--per-class", type=int, default=150,
                    help="target pairs per class in balanced mode")
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--eval-frac", type=float, default=0.1)
    args = ap.parse_args()

    targets = ["shepherd", "scribe", "steward"] if args.office == "all" else [args.office]
    tot_kept = tot_drop = 0
    for office in targets:
        if args.balanced:
            k, d = run_balanced(office, args.per_class, args.apply, args.workers, args.eval_frac)
        else:
            k, d = run_office(office, args.count, args.apply, args.workers, args.eval_frac)
        tot_kept += k
        tot_drop += d
    if args.apply:
        mode = "balanced" if args.balanced else "standard"
        print(f"[office] DONE ({mode}) — kept {tot_kept}, dropped {tot_drop} across {len(targets)} office(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
