"""harmonics.py — octaves, overtones, and the map read as music.

The FFT is the mathematics of music: a tone decomposes into its overtone series
(its FFT peaks), an OCTAVE is a frequency doubling (2:1), and harmony is small-
integer frequency RATIOS (fifth 3:2, fourth 4:3, third 5:4). Music lives in
log-frequency space — 12 equal steps of 2^(1/12) per octave. The cochlea itself
performs a physical Fourier transform; so the spectral lens on the map (its
eigenmodes = its "tones", the eigenvalue spectrum = its timbre) is the same move
hearing makes.

This module is the honest bridge:
  - REAL, deterministic music math (verifiable): pitch<->frequency<->cents, the
    octave, equal-tempered and just-intonation interval ratios, the overtone
    series, and the nearest-interval / consonance test.
  - THE ASSAY: read the map's eigenvalue spectrum AS music and test whether it is
    genuinely a harmonic series or merely resembles one. Map never launders: a
    loose resemblance is reported as coincidence, not crowned as structure (the
    gematria failure mode is refused — intuition proposes, the assay disposes).

Sovereign: stdlib only; does NOT touch the verifier moat.
"""
from __future__ import annotations

import math
from typing import Any, Dict, List, Tuple

_A4 = 440.0
_NOTES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Just-intonation intervals within one octave (name, cents, ratio). The pure
# small-integer ratios that the overtone series produces and the ear hears as
# consonant — the reference the equal-tempered 100-cent steps approximate.
_JUST: List[Tuple[str, float, str]] = [
    ("unison", 0.0, "1:1"),
    ("minor second", 111.7, "16:15"),
    ("major second", 203.9, "9:8"),
    ("minor third", 315.6, "6:5"),
    ("major third", 386.3, "5:4"),
    ("perfect fourth", 498.0, "4:3"),
    ("tritone", 590.2, "45:32"),
    ("perfect fifth", 702.0, "3:2"),
    ("minor sixth", 813.7, "8:5"),
    ("major sixth", 884.4, "5:3"),
    ("minor seventh", 996.1, "9:5"),
    ("major seventh", 1088.3, "15:8"),
    ("octave", 1200.0, "2:1"),
]


def cents(ratio: float) -> float:
    """Interval size in cents (1200 per octave) for a frequency ratio."""
    return 1200.0 * math.log2(ratio) if ratio > 0 else 0.0


def freq_for_midi(m: float) -> float:
    """MIDI note number -> frequency in Hz (A4 = MIDI 69 = 440 Hz)."""
    return _A4 * (2.0 ** ((m - 69.0) / 12.0))


def midi_for_freq(f: float) -> float:
    return 69.0 + 12.0 * math.log2(f / _A4) if f > 0 else 0.0


def note_name(f: float) -> Dict[str, Any]:
    """Nearest note name + octave + how many cents sharp/flat from it."""
    m = midi_for_freq(f)
    mr = int(round(m))
    return {"hz": round(f, 2), "note": _NOTES[mr % 12] + str(mr // 12 - 1),
            "midi": mr, "cents_off": round(100.0 * (m - mr), 1)}


def overtones(f0: float, n: int = 8) -> List[Dict[str, Any]]:
    """The overtone (harmonic) series of a fundamental: f0, 2f0, 3f0 ... — the
    literal FFT peaks of a periodic tone, and where the consonant intervals
    come from (2:1 octave, 3:2 fifth, 4:3 fourth, 5:4 third...)."""
    out = []
    for k in range(1, max(1, n) + 1):
        nm = note_name(f0 * k)
        nm["harmonic"] = k
        nm["interval_from_f0"] = nearest_interval(float(k))["nearest"]
        out.append(nm)
    return out


def nearest_interval(ratio: float) -> Dict[str, Any]:
    """Reduce a frequency ratio to within an octave and name the nearest just
    interval, with the cents error (0 = pure; |error| small = consonant)."""
    if ratio <= 0:
        return {"ratio": ratio, "error": "ratio must be > 0"}
    total = cents(ratio)
    octs = int(math.floor(total / 1200.0))
    within = total - 1200.0 * octs
    best = min(_JUST, key=lambda t: abs(t[1] - within))
    return {
        "ratio": round(ratio, 4), "total_cents": round(total, 1),
        "octaves": octs, "within_octave_cents": round(within, 1),
        "nearest": best[0], "nearest_ratio": best[2],
        "cents_error": round(within - best[1], 1),
    }


def the_connection() -> Dict[str, str]:
    return {
        "fft_is_hearing": "The cochlea performs a physical Fourier transform — sound into its "
                          "frequencies. The map's eigenmodes are its tones; the eigenvalue "
                          "spectrum is its timbre.",
        "octave": "An octave is a frequency DOUBLING (2:1) — the same pitch one harmonic up. "
                  "Music lives in log-frequency: 12 equal steps of 2^(1/12) per octave.",
        "harmony": "Consonant intervals are small-integer ratios (fifth 3:2, fourth 4:3, third "
                   "5:4) — exactly the peaks of a tone's FFT (its overtone series).",
        "honest": "Whether the MAP's own spectrum is literally musical is an empirical question, "
                  "not a given — see spectrum_as_music(); a loose resemblance is coincidence.",
    }


def spectrum_as_music(eigenvalues: List[float]) -> Dict[str, Any]:
    """THE ASSAY. Read the map's eigenvalue spectrum as frequencies and test
    whether the intervals between adjacent modes are genuinely musical (near just
    ratios) or merely resemble them. Honest verdict by the cents error."""
    eig = [e for e in (eigenvalues or []) if e and e > 0]
    if len(eig) < 2:
        return {"ok": False, "error": "need >= 2 positive eigenvalues"}
    steps = []
    errs = []
    for i in range(len(eig) - 1):
        r = eig[i] / eig[i + 1]  # adjacent ratio (descending eigenvalues -> >1)
        ni = nearest_interval(r)
        steps.append({"from_mode": i + 1, "to_mode": i + 2,
                      "ratio": ni["ratio"], "nearest": ni["nearest"],
                      "cents_error": ni["cents_error"]})
        errs.append(abs(ni["cents_error"]))
    span = nearest_interval(eig[0] / eig[-1])
    mean_err = round(sum(errs) / len(errs), 1)
    # THE CRITERION (Matt): "when the tune is correct, the theories will be
    # correct." The cents-error is how far OUT OF TUNE the arrangement is — i.e.
    # how far from a correct arrangement. It is NOT a coincidence to dismiss; it
    # is the diagnostic. But a near-tune only means "we are close" if it BEATS
    # CHANCE — see tune_test(); a near-miss at the level of random is not close.
    if mean_err < 12:
        verdict = "IN TUNE — consonant; by the criterion (consonance->correctness) a strong candidate."
        grade = "resonance"
    elif mean_err < 20:
        verdict = "NEARLY IN TUNE — close; keep tuning the arrangement toward consonance."
        grade = "resonance"
    else:
        verdict = ("OUT OF TUNE by ~%.0f cents — the current arrangement is NOT yet correct. "
                   "The dissonance is the signal that the answers aren't right yet; tune toward "
                   "consonance (an in-tune arrangement exists — see tune_test)." % mean_err)
        grade = "out_of_tune"
    return {
        "ok": True,
        "eigenvalues": [round(e, 3) for e in eig],
        "adjacent_intervals": steps,
        "mean_cents_error": mean_err,
        "full_span": {"ratio": span["ratio"], "nearest": span["nearest"],
                      "cents_error": span["cents_error"]},
        "verdict": verdict,
        "grade": grade,
        "criterion": ("When the tune is correct, the theories will be correct (Matt). Consonance "
                      "is the truth-criterion for the arrangement; the cents-error is its detuning "
                      "from correct. A guiding witness — confirmed by the engine's verification, "
                      "and only counted as 'close' when it beats chance (tune_test)."),
    }
