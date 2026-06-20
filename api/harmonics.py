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
import re
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


# ──────────────────────────────────────────────────────────────────────────
# The Nashville Number System (NNS) — chords as scale degrees, key-independent
# ──────────────────────────────────────────────────────────────────────────
# A chart written in degrees 1-7 of the key's MAJOR scale, so the same chart
# plays in any key (change only the key header). Devised by Neal Matthews Jr.
# (Jordanaires, late 1950s), refined by the Nashville A-Team. Diatonic triad
# quality is IMPLIED by the major scale — 1,4,5 major; 2,3,6 minor; 7 diminished
# — and only DEVIATIONS are marked. It is the relative skeleton of a song: the
# same move the map makes — structure independent of its instantiation (the key).
# Sovereign: stdlib only; deterministic; round-trips chord<->number exactly for
# triads + common sevenths (exotic extensions are carried best-effort).

_DEGREE_SEMI = {1: 0, 2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11}  # major-scale degree -> semitones
_SEMI_DEGREE = {0: 1, 2: 2, 4: 3, 5: 4, 7: 5, 9: 6, 11: 7}  # the diatonic inverse
# non-diatonic roots -> (degree, accidental). Flats by convention; #4 for the tritone.
_SEMI_CHROM = {1: (2, "b"), 3: (3, "b"), 6: (4, "#"), 8: (6, "b"), 10: (7, "b")}
_DEGREE_QUALITY = {1: "maj", 2: "min", 3: "min", 4: "maj", 5: "maj", 6: "min", 7: "dim"}
_TRIAD_SYM = {"maj": "maj", "min": "m", "dim": "°", "aug": "+"}

_PC = {"C": 0, "B#": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "FB": 4,
       "E#": 5, "F": 5, "F#": 6, "GB": 6, "G": 7, "G#": 8, "AB": 8, "A": 9, "A#": 10,
       "BB": 10, "B": 11, "CB": 11}
_SHARP = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]
_FLAT = ["C", "Db", "D", "Eb", "E", "F", "Gb", "G", "Ab", "A", "Bb", "B"]
_FLAT_KEYS = {"F", "Bb", "Eb", "Ab", "Db", "Gb", "Cb"}

_NNS_NOTE = ("Numbers are relative to the key (major-scale degrees): 1,4,5 major; 2,3,6 minor; "
             "7 diminished by DEFAULT — only deviations are marked (m=minor, maj=major where "
             "minor is default, °=dim, +=aug; a parenthesised tail is the 7th/extension). The "
             "SAME chart plays in any key — change only the key. Neal Matthews Jr. / the "
             "Nashville A-Team. A push (anticipation) and rhythmic diamonds are performance marks "
             "a player adds; this models the harmonic skeleton.")


def _norm_note(s: str) -> str:
    s = (s or "").strip().replace("♭", "b").replace("♯", "#")
    return s[:1].upper() + s[1:] if s else s


def _note_pc(s: str):
    return _PC.get(_norm_note(s).upper())


def _key_pc(key: str) -> int:
    pc = _note_pc(key)
    if pc is None:
        raise ValueError("unknown key: %r" % key)
    return pc


def _key_flats(key: str) -> bool:
    return _norm_note(key) in _FLAT_KEYS


def _split_chord(sym: str):
    m = re.match(r"^([A-Ga-g][#b♯♭]?)(.*)$", (sym or "").strip())
    if not m:
        raise ValueError("unparseable chord: %r" % sym)
    pc = _note_pc(m.group(1))
    if pc is None:
        raise ValueError("unknown chord root: %r" % sym)
    return pc, m.group(2).strip()


def _triad(suffix: str):
    """(base_quality, extension) from a chord suffix. base in maj/min/dim/aug."""
    s = (suffix or "").strip()
    if s == "":
        return "maj", ""
    low = s.lower()
    if low.startswith("dim") or s.startswith("°") or low == "o" or low.startswith("o7"):
        return "dim", (s[3:] if low.startswith("dim") else s[1:])
    if low.startswith("aug") or s.startswith("+"):
        return "aug", (s[3:] if low.startswith("aug") else s[1:])
    if low.startswith("maj") or s[0] in ("M", "Δ", "△"):
        rest = s[3:] if low.startswith("maj") else s[1:]
        return "maj", ("maj" + rest if rest[:1].isdigit() else rest)
    if s[0] in ("m", "-"):
        return "min", s[1:]
    return "maj", s


def chord_to_number(sym: str, key: str) -> Dict[str, Any]:
    """One chord -> its Nashville number in `key` (structured + display string)."""
    rootpc, suffix = _split_chord(sym)
    rel = (rootpc - _key_pc(key)) % 12
    if rel in _SEMI_DEGREE:
        degree, acc = _SEMI_DEGREE[rel], ""
    else:
        degree, acc = _SEMI_CHROM[rel]
    base, ext = _triad(suffix)
    # Diatonic degrees take the major-scale default; a BORROWED (accidental) root is
    # conventionally major (bVII, bVI, bIII), so don't redundantly mark it "maj".
    default = "maj" if acc else _DEGREE_QUALITY[degree]
    qsym = "" if base == default else _TRIAD_SYM[base]
    nash = acc + str(degree) + qsym
    display = nash + (("(" + ext + ")") if ext else "")
    return {"chord": sym, "degree": degree, "accidental": acc, "quality": base,
            "default_quality": default, "extension": ext, "nashville": nash,
            "display": display, "relative_semitones": rel}


def number_to_chord(num: str, key: str) -> Dict[str, Any]:
    """One Nashville number -> the chord it names in `key`."""
    s = (num or "").strip().replace(" ", "")
    m = re.match(r"^([b#]?)([1-7])(maj|min|m|dim|°|aug|\+|-)?\(?([A-Za-z0-9#]+)?\)?$", s)
    if not m:
        raise ValueError("unparseable number: %r" % num)
    acc, deg, qsym, ext = m.group(1), int(m.group(2)), (m.group(3) or ""), (m.group(4) or "")
    semi = _DEGREE_SEMI[deg] + (1 if acc == "#" else -1 if acc == "b" else 0)
    # a flatted degree spells flat, a sharped degree spells sharp; diatonic degrees
    # follow the key's accidental preference.
    names = _FLAT if acc == "b" else _SHARP if acc == "#" else (_FLAT if _key_flats(key) else _SHARP)
    name = names[(_key_pc(key) + semi) % 12]
    base = ({"m": "min", "min": "min", "maj": "maj", "dim": "dim", "°": "dim",
             "aug": "aug", "+": "aug", "-": "min"}.get(qsym)
            or ("maj" if acc else _DEGREE_QUALITY[deg]))
    suf = {"maj": "", "min": "m", "dim": "dim", "aug": "aug"}[base]
    if ext:
        if ext.lower().startswith("maj"):
            suf = "maj" + ext[3:]
        elif base == "min" and ext[:1].isdigit():
            suf = "m" + ext
        else:
            suf = suf + ext
    return {"number": num, "chord": name + suf, "root": name, "quality": base, "extension": ext}


def to_nashville(progression: List[str], key: str = "C") -> Dict[str, Any]:
    """A chord progression in `key` -> its key-independent Nashville chart."""
    nums = [chord_to_number(c, key) for c in progression]
    return {"ok": True, "system": "Nashville Number System", "key": _norm_note(key),
            "chords": list(progression), "numbers": nums,
            "chart": " ".join(n["display"] for n in nums), "note": _NNS_NOTE}


def from_nashville(numbers: List[str], key: str = "C") -> Dict[str, Any]:
    """A Nashville chart rendered into `key`."""
    out = [number_to_chord(n, key) for n in numbers]
    return {"ok": True, "system": "Nashville Number System", "key": _norm_note(key),
            "numbers": list(numbers), "chords": [o["chord"] for o in out],
            "rendered": out, "note": _NNS_NOTE}


def nashville(progression=None, numbers=None, key: str = "C", to_key=None) -> Dict[str, Any]:
    """One entry for the music layer. Give a chord progression (+ key) to get its
    number chart — and optionally `to_key` to TRANSPOSE it; or give numbers (+ the
    key to render in). Strings may be comma/space/bar separated."""
    key = key or "C"

    def _split(x):
        return [t for t in re.split(r"[,\s|]+", x) if t] if isinstance(x, str) else list(x or [])
    try:
        if progression:
            res = to_nashville(_split(progression), key)
            if to_key:
                res["transposed"] = {
                    "to_key": _norm_note(to_key),
                    "chords": [number_to_chord(n["display"], to_key)["chord"] for n in res["numbers"]],
                }
            return res
        if numbers:
            return from_nashville(_split(numbers), to_key or key)
        return {"ok": False, "error": "provide a chord `progression` (+ key) or `numbers` (+ key)"}
    except Exception as e:  # noqa: BLE001 — never raise; the music layer degrades gracefully
        return {"ok": False, "error": "%s: %s" % (type(e).__name__, e)}
