# Concordance Known Issues

Three reproducible bugs surfaced while building the training set on 2026-04-27. Each includes a minimal repro, the wrong behavior, the right behavior, and a proposed fix. None can be fixed without server source access; document them so testers don't lose hours assuming user error.

---

## Issue #1 — `verify_statistics_pvalue` returns the wrong tail

**Severity:** High. Correct statistical claims are flagged as wrong.

**Repro:**

```json
{"spec": {"test": "two_sample_t", "n1": 30, "n2": 30, "mean1": 5.2, "mean2": 4.8, "sd1": 1.1, "sd2": 1.0, "tail": "two", "claimed_p": 0.15}}
```

**Observed output:**
```
status: MISMATCH
recomputed_t: 1.474
df: 57.48
recomputed_p: 0.927
```

**Expected:** Two-tailed p for t=1.474 on df≈57.5 is `2·sf(|t|) ≈ 0.146`. The engine returned 0.927, which equals `1 − one-tailed p = 1 − 0.073`. The engine is returning the wrong region of the distribution when `tail:"two"` is passed.

**Proposed fix:** In the p-value compute path, ensure that for `tail=="two"` (or `"two-sided"`, `"two_sided"`) the result is `2 * stats.t.sf(abs(t), df)`, not `stats.t.cdf(t, df)`. Add unit tests for all three accepted tail spellings.

**Workaround for testers:** Don't pass `tail` for two-tailed tests until fixed; or pass `tail:"right"` and double the returned p manually.

---

## Issue #2 — `verify_computer_science` test_cases doesn't unpack input

**Severity:** Medium. Multi-arg functions can't be tested without a workaround.

**Repro:**

```json
{
  "code": "def add(a, b):\n    return a + b",
  "function_name": "add",
  "test_cases": [{"input": [2, 3], "expected": 5}]
}
```

**Observed output:**
```
status: MISMATCH
case 0: raised TypeError: add() missing 2 required positional arguments: 'a' and 'b'
```

The engine called `add([2, 3])` instead of `add(2, 3)`.

**Expected:** A list-valued `input` should splat into positional args, OR the schema should be explicit about `args` (list, splatted) vs `input` (single value, passed as-is).

**Proposed fix (pick one):**
- **Option A (smaller)**: rename the field to `args` and document that it always splats.
- **Option B (more flexible)**: keep `input` for single-arg, add `args` (list) and `kwargs` (dict). The runner picks based on which is present.

**Workaround:** Wrap the function to accept a single argument:
```python
def add(args):
    a, b = args
    return a + b
```

---

## Issue #3 — `validate_packet` and `verify_governance_decision_packet` use different schemas

**Severity:** High. This is the bug most likely to make a tester give up.

**Repro:** The exact packet that PASSES `verify_governance_decision_packet` (CONFIRMED on shape and witness_consistency)…

```json
{
  "title": "Adopt weekly family budget review",
  "scope": "adapter",
  "red_items": ["debt_increase", "hidden_spending"],
  "floor_items": ["both_spouses_present", "written_record"],
  "way_path": "Sunday evening 30-minute review",
  "execution_steps": ["Print transactions", "Compare to targets", "Agree adjustments", "Log decisions"],
  "witnesses": ["Matt", "Spouse"],
  "scripture_anchors": ["Proverbs 27:23"],
  "wait_window_seconds": 0
}
```

…returns **QUARANTINE** from `validate_packet` (with `domain: "governance"` added) for these reasons:

```
RED: PASS — note: "no text to scan"
FLOOR: PASS — note: "no text to scan"
BROTHERS: PASS — witnesses: 0, required: 0
GOD: QUARANTINE — created_epoch missing
```

Three separate disagreements:
1. RED/FLOOR scan a text field, not the structured `red_items`/`floor_items` arrays.
2. BROTHERS counts witnesses from a different field path; sees 0 despite the `witnesses` array having 2 entries.
3. GOD requires `created_epoch`; the standalone verifier doesn't.

**Expected:** A packet should have one schema. Either both verifiers honor the same fields, or there's a documented "rich packet" shape that supersets both.

**Proposed fix:** Standardize on a single packet schema. Either:
- **Option A (preferred)**: Make `validate_packet` honor structured `red_items`/`floor_items` arrays *and* a free-text field if present, and have it count `witnesses` from the same array `verify_governance_decision_packet` uses. Make `created_epoch` default to the call time and emit a warning, not a QUARANTINE.
- **Option B**: Publish a single canonical schema (see `decision_packet_template.json`) and have `verify_governance_decision_packet` enforce a *subset* of what `validate_packet` requires, so any packet that passes the standalone verifier is also valid input for the engine.

**Workaround for testers:** Use the template in `decision_packet_template.json`, which carries every field both verifiers might want.

---

## Issue #4 — `validate_packet` ignores `wait_window_seconds: 0`; scope has a hidden default

**Severity:** Medium. Surprises the tester; affects every governance packet.

**Repro:** A packet with `scope: "adapter"`, `created_epoch: T`, `wait_window_seconds: 0`, evaluated at `now_epoch: T + 100`.

**Observed:**
```
GOD: QUARANTINE — "wait 100/3600 seconds"
```

The engine used a 3600-second default for `adapter` scope despite the packet asking for 0. Re-running with `now_epoch: T + 3700` produces `GOD: PASS — elapsed: 3700, required: 3600`.

**Expected:** Either honor the packet's `wait_window_seconds` (including 0), or document the scope-based defaults (likely something like `adapter: 3600s`, `mesh: 86400s`, `canon: 604800s`) and treat `wait_window_seconds` as a floor that *raises* the default but cannot lower it.

**Proposed fix:** Two parts.
1. Document the scope-based defaults explicitly in `schemas.md` and the engine's docstring.
2. Decide and document the override rule: is `wait_window_seconds` a strict override, a floor, or ignored? Current behavior says "ignored when smaller," which is fine if intentional but must be visible.

**Workaround for testers:** Set `now_epoch` to at least `created_epoch + 3600` for adapter scope. For real packets, the wait is the point — don't try to bypass it.
