"""Music theory verifier (sits at the acoustics ↔ formal-reasoning seam).

Interval semitones, equal-temperament frequencies, scale membership.
Public-domain conventions (12-tone equal temperament, A4 = 440 Hz, the
canonical Western reference; major / minor scale formulas widely
documented).

Checks:
  * music.interval_semitones      — count of semitones between two notes
  * music.frequency_ratio         — interval ratio matches claimed (octave 2:1 etc.)
  * music.equal_temperament_freq  — f = 440 · 2^((n - 69) / 12) for MIDI note n
  * music.scale_membership        — note belongs to claimed key's major/minor scale

MUS_VERIFY shape (any subset):
    {
      "note_a": "C4", "note_b": "G4",
      "claimed_semitones": 7,

      "freq_a": 440, "freq_b": 880,
      "claimed_interval": "octave",   # octave / fifth / fourth / major_third / minor_third

      "midi_note": 69,
      "claimed_frequency_hz": 440.0,

      "key": "C", "mode": "major",
      "note": "E",
      "claimed_in_scale": true,
    }
"""
from __future__ import annotations
import math
from typing import Any, Dict, List

from .base import VerifierResult, na, confirm, mismatch, error


# Note name → semitones above C (0..11).
_NOTE_TO_SEMI = {
    "C": 0, "C#": 1, "Db": 1,
    "D": 2, "D#": 3, "Eb": 3,
    "E": 4, "Fb": 4, "E#": 5,
    "F": 5, "F#": 6, "Gb": 6,
    "G": 7, "G#": 8, "Ab": 8,
    "A": 9, "A#": 10, "Bb": 10,
    "B": 11, "Cb": 11, "B#": 0,
}

# Major scale intervals (semitones from tonic): W W H W W W H = 0,2,4,5,7,9,11
_MAJOR_INTERVALS = (0, 2, 4, 5, 7, 9, 11)
# Natural minor: W H W W H W W = 0,2,3,5,7,8,10
_NATURAL_MINOR_INTERVALS = (0, 2, 3, 5, 7, 8, 10)

# Common interval ratios (just intonation reference; equal temperament
# differs slightly but matches within ~1%).
_INTERVAL_RATIOS = {
    "unison":      1.0,
    "octave":      2.0,
    "fifth":       1.5,           # 3:2
    "fourth":      4.0/3.0,
    "major_third": 5.0/4.0,
    "minor_third": 6.0/5.0,
    "major_sixth": 5.0/3.0,
    "minor_sixth": 8.0/5.0,
    "major_second": 9.0/8.0,
    "minor_second": 16.0/15.0,
    "major_seventh": 15.0/8.0,
    "minor_seventh": 9.0/5.0,
}


def _parse_note(note: str):
    """Parse 'C4', 'F#5', 'Bb3' → (semitone, octave). Plain 'C', 'F#', 'Bb'
    default to octave 4 (the conventional "middle" octave). Returns None
    on failure."""
    if not note or not isinstance(note, str):
        return None
    s = note.strip()
    # Find octave digit (last digit chars).
    octave_idx = None
    for i, c in enumerate(s):
        if c.isdigit() or (c == "-" and i + 1 < len(s) and s[i + 1].isdigit()):
            octave_idx = i
            break
    if octave_idx is None:
        # No octave digit. Treat the whole string as a note name with
        # default octave 4. ("C" → C4, "F#" → F#4, "Bb" → Bb4.)
        if s in _NOTE_TO_SEMI:
            return _NOTE_TO_SEMI[s], 4
        return None
    name = s[:octave_idx]
    try:
        octave = int(s[octave_idx:])
    except ValueError:
        return None
    if name not in _NOTE_TO_SEMI:
        return None
    return _NOTE_TO_SEMI[name], octave


def verify_interval_semitones(spec: Dict[str, Any]) -> VerifierResult:
    name = "music.interval_semitones"
    a = spec.get("note_a")
    b = spec.get("note_b")
    claimed = spec.get("claimed_semitones")
    if a is None or b is None or claimed is None:
        return na(name)
    pa = _parse_note(str(a))
    pb = _parse_note(str(b))
    if pa is None or pb is None:
        # Unparseable note input — this verifier doesn't apply to this
        # spec shape. NA, not ERROR (the verifier isn't broken; the
        # input just isn't a note).
        return na(name)
    semi_a = pa[0] + pa[1] * 12
    semi_b = pb[0] + pb[1] * 12
    actual = semi_b - semi_a
    try:
        c = int(claimed)
    except (TypeError, ValueError):
        return error(name, f"claimed_semitones must be int, got {claimed!r}")
    data = {"note_a": a, "note_b": b,
            "actual_semitones": actual, "claimed_semitones": c,
            "rule": "12 semitones per octave; signed (b - a)"}
    if actual == c:
        return confirm(name, f"{a} → {b} = {actual} semitones (matches claim)", data)
    return mismatch(name, f"{a} → {b} = {actual} semitones, claimed {c}", data)


def verify_frequency_ratio(spec: Dict[str, Any]) -> VerifierResult:
    name = "music.frequency_ratio"
    fa = spec.get("freq_a")
    fb = spec.get("freq_b")
    claimed = spec.get("claimed_interval")
    if fa is None or fb is None or claimed is None:
        return na(name)
    try:
        af, bf = float(fa), float(fb)
    except (TypeError, ValueError):
        return error(name, "frequencies must be numeric")
    if af <= 0 or bf <= 0:
        return error(name, "frequencies must be positive")
    cn = str(claimed).lower().strip()
    if cn not in _INTERVAL_RATIOS:
        return na(name, f"unknown interval name {claimed!r}; supported: {sorted(_INTERVAL_RATIOS.keys())}")
    expected = _INTERVAL_RATIOS[cn]
    actual = bf / af
    rel_tol = float(spec.get("tolerance_relative", 0.02))
    diff = abs(actual - expected)
    threshold = max(1e-3, rel_tol * expected)
    data = {"freq_a": af, "freq_b": bf, "actual_ratio": actual,
            "claimed_interval": cn, "expected_ratio": expected,
            "diff": diff, "tolerance_relative": rel_tol}
    if diff <= threshold:
        return confirm(name,
                       f"{bf}/{af} = {actual:.4f} matches {cn} ratio {expected:.4f}",
                       data)
    return mismatch(name,
                    f"{bf}/{af} = {actual:.4f}; {cn} requires {expected:.4f} (diff {diff:.4f})",
                    data)


def verify_equal_temperament_freq(spec: Dict[str, Any]) -> VerifierResult:
    """f = 440 · 2^((n - 69) / 12) for MIDI note n (A4 = MIDI 69 = 440 Hz)."""
    name = "music.equal_temperament_freq"
    n = spec.get("midi_note")
    claimed = spec.get("claimed_frequency_hz")
    if n is None or claimed is None:
        return na(name)
    try:
        nf = int(n)
        c = float(claimed)
    except (TypeError, ValueError):
        return error(name, "midi_note int and claimed_frequency_hz numeric required")
    if not (0 <= nf <= 127):
        return error(name, f"MIDI note must be 0-127, got {nf}")
    actual = 440.0 * (2.0 ** ((nf - 69) / 12.0))
    rel_tol = float(spec.get("tolerance_relative", 1e-3))
    diff = abs(actual - c)
    threshold = max(0.01, rel_tol * abs(actual))
    data = {"midi_note": nf, "actual_freq_hz": actual,
            "claimed_freq_hz": c, "diff_hz": diff,
            "formula": "f = 440·2^((n−69)/12); A4 = 440 Hz"}
    if diff <= threshold:
        return confirm(name,
                       f"MIDI {nf} → {actual:.4f} Hz (matches claim {c})",
                       data)
    return mismatch(name,
                    f"MIDI {nf} → {actual:.4f} Hz, claimed {c} (diff {diff:.4f})",
                    data)


def verify_scale_membership(spec: Dict[str, Any]) -> VerifierResult:
    name = "music.scale_membership"
    key = spec.get("key")
    mode = (spec.get("mode") or "major").lower()
    note = spec.get("note")
    claimed = spec.get("claimed_in_scale")
    if key is None or note is None or claimed is None:
        return na(name)
    if str(key) not in _NOTE_TO_SEMI:
        return error(name, f"unknown key {key!r}")
    if str(note) not in _NOTE_TO_SEMI:
        return error(name, f"unknown note {note!r}")
    intervals = _MAJOR_INTERVALS if mode == "major" else _NATURAL_MINOR_INTERVALS if mode in ("minor", "natural_minor") else None
    if intervals is None:
        return na(name, f"unknown mode {mode!r}; supported: major, minor")
    tonic = _NOTE_TO_SEMI[str(key)]
    note_semi = _NOTE_TO_SEMI[str(note)]
    interval = (note_semi - tonic) % 12
    actual = interval in intervals
    data = {"key": key, "mode": mode, "note": note,
            "interval_from_tonic": interval,
            "actual_in_scale": actual, "claimed_in_scale": bool(claimed),
            "scale_intervals": list(intervals)}
    if actual == bool(claimed):
        return confirm(name,
                       f"{note} is{'  ' if actual else ' NOT '}in {key} {mode} (matches claim)",
                       data)
    return mismatch(name,
                    f"{note} {'in' if actual else 'NOT in'} {key} {mode}, claimed {bool(claimed)}",
                    data)


def run(packet: Dict[str, Any]) -> List[VerifierResult]:
    results: List[VerifierResult] = []
    mv = packet.get("MUS_VERIFY") or {}
    if all(mv.get(k) is not None for k in ("note_a", "note_b", "claimed_semitones")):
        results.append(verify_interval_semitones(mv))
    if all(mv.get(k) is not None for k in ("freq_a", "freq_b", "claimed_interval")):
        results.append(verify_frequency_ratio(mv))
    if all(mv.get(k) is not None for k in ("midi_note", "claimed_frequency_hz")):
        results.append(verify_equal_temperament_freq(mv))
    if all(mv.get(k) is not None for k in ("key", "note", "claimed_in_scale")):
        results.append(verify_scale_membership(mv))
    if not results:
        results.append(na("music_theory", "no MUS_VERIFY artifacts present"))
    return results
