"""
seed_domains_wave5.py — Fifth wave: 5 domains with packets but zero journal seeds
──────────────────────────────────────────────────────────────────────────────────
Covers: acoustics, document_validation, optics, photography, witness

These domains already have verification packet data from prior runs but have
never been seeded in the journal retrieval corpus.

Usage: python scripts/seed/seed_domains_wave5.py [--delay N] [--dry-run] [--domain D] [--reset]
"""
from __future__ import annotations
import argparse, hashlib, json, os, sys, time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
try:
    import requests
except ImportError:
    sys.exit("pip install requests")

API_BASE   = os.environ.get("CONCORDANCE_API", "http://localhost:8000")
STATE_FILE = Path(__file__).parent / "seed_state_w5.json"

SEEDS: dict[str, list[str]] = {

    # ── ACOUSTICS ─────────────────────────────────────────────────────────────
    "acoustics": [
        "Sound is a longitudinal mechanical wave: air molecules oscillate parallel to the direction of propagation. Speed of sound in air at 20°C ≈ 343 m/s; increases ~0.6 m/s per °C.",
        "Frequency and pitch: frequency (Hz) is the number of oscillations per second; pitch is the perceptual correlate. The audible range for humans is ~20 Hz to 20 kHz; infrasound < 20 Hz; ultrasound > 20 kHz.",
        "Amplitude and loudness: decibel (dB) is a logarithmic ratio. SPL (sound pressure level) dB = 20 log₁₀(p/p₀) where p₀ = 20 μPa (threshold of hearing). 60 dB = 1,000× the reference pressure; 120 dB = threshold of pain.",
        "The inverse square law: in free field (outdoors), sound intensity decreases as 1/r². Every doubling of distance decreases level by 6 dB. Reflections from walls create a reverberant field that does not follow inverse square law.",
        "The Fourier theorem: any periodic waveform can be decomposed into a sum of sinusoidal components (harmonics). Timbre is determined by the spectrum — the relative amplitudes of harmonics.",
        "The Doppler effect: when source and observer are in relative motion, the observed frequency shifts. Approaching source: higher frequency (blue shift). Receding: lower frequency (red shift). f_observed = f_source · (v ± v_observer)/(v ∓ v_source).",
        "Resonance: a system vibrates at maximum amplitude when driven at its natural (resonant) frequency. Helmholtz resonators, tuned mass dampers, and musical instrument bodies exploit resonance.",
        "Room acoustics: reverberation time RT60 = time for sound to decay 60 dB after source stops. Sabine's equation: RT60 = 0.161 · V / A, where V = room volume and A = total absorption area. Concert halls: RT60 ≈ 1.8-2.2s.",
        "Sound absorption and transmission loss: porous absorbers (foam, carpet) absorb mid/high frequencies; Helmholtz resonators absorb specific low frequencies. Mass law: TL ≈ 20 log(f·m) - 47.5 dB per doubling of mass or frequency.",
        "Noise and hearing damage: continuous exposure > 85 dB can cause permanent hearing loss. NIOSH 85 dB criterion: 8-hour exposure limit. Every 3 dB increase halves the permitted exposure time.",
        "Architectural acoustics for speech: speech intelligibility requires low reverberation (< 0.8s), high signal-to-noise ratio (> 15 dB), no strong early reflections > 35 ms (echoes).",
        "Standing waves in rooms: at frequencies where room dimensions equal integer multiples of half-wavelengths, standing waves (room modes) create uneven bass response. Axial, tangential, oblique modes.",
        "Active noise control: microphones detect unwanted sound; loudspeakers emit the inverse waveform (anti-noise) to cancel by destructive interference. Effective at low frequencies (<1 kHz); used in ANC headphones, ducts.",
        "Psychoacoustics: how humans perceive sound. Fletcher-Munson equal-loudness contours: 1-4 kHz range is most sensitive. Masking: loud sounds mask nearby frequencies (temporal and spectral masking exploited in MP3 compression).",
        "Ultrasound applications: medical imaging uses 1-20 MHz sound waves. Pulse-echo method: measure time of flight to calculate depth. Resolution ~wavelength; higher frequency = better resolution but less penetration.",
        "Soundproofing vs sound absorption: absorption reduces reflections within a room (reduces RT60); isolation (soundproofing) blocks sound from entering or leaving. Mass, decoupling, and damping are the three isolation mechanisms.",
        "The speed of sound in materials: c = √(E/ρ) for longitudinal waves in solids, where E = elastic modulus and ρ = density. Steel: ~5960 m/s; concrete: ~3400 m/s; water: ~1480 m/s.",
        "Sonar (sound navigation and ranging): active sonar emits pulses and measures returns; passive sonar listens. Range = (speed of sound × time)/2. Applied to submarine detection, fishfinding, depth sounding.",
        "Binaural hearing and localization: two ears allow localization of sound sources via interaural time difference (ITD, up to 700 μs) for low frequencies and interaural level difference (ILD) for high frequencies.",
        "Musical temperament: equal temperament divides the octave into 12 semitones where each is a factor of 2^(1/12) ≈ 1.0595 higher than the previous. Pure intervals (just intonation) have simple frequency ratios (3/2 for perfect fifth).",
    ],

    # ── DOCUMENT VALIDATION ──────────────────────────────────────────────────
    "document_validation": [
        "Chain of custody: the chronological documentation of the collection, custody, control, transfer, analysis, and disposition of physical or electronic evidence. Required for admissibility in legal proceedings.",
        "Document authentication: establishing that a document is genuine. Methods: comparison with known samples, handwriting analysis, physical examination (paper, ink, watermarks), digital signatures, notarization.",
        "Notarization: a notary public verifies the identity of signatories and witnesses signatures on documents. Provides a formal record that the signing occurred voluntarily on the stated date. Does not verify document contents.",
        "Digital signatures: asymmetric cryptography where the signer's private key creates a signature; the corresponding public key verifies it. Provides authentication, integrity (tamper evidence), and non-repudiation.",
        "Hash functions for integrity: SHA-256 produces a 256-bit digest of a document. Any change to the document produces a completely different hash. Hash stored separately (or in a blockchain) allows verification of integrity.",
        "The X.509 certificate standard: digital certificates bind a public key to an identity (name, organization, domain). Issued by a Certificate Authority (CA). Used in TLS/SSL for web security and code signing.",
        "Forgery detection: UV light reveals paper security features (watermarks, security fibers); infrared reveals ink composition; magnification shows printing quality; ESDA (Electrostatic Detection Apparatus) reveals indented writing.",
        "Timestamp authorities: a trusted third party that digitally signs a hash + timestamp, proving a document existed at a specific time. RFC 3161 (Internet X.509 PKI Time-Stamp Protocol) is the standard.",
        "The Daubert standard (US): scientific or expert evidence must be based on a testable theory, subjected to peer review, have a known error rate, and be generally accepted in the relevant scientific community.",
        "EXIF metadata in photographs: camera, settings (ISO, aperture, shutter), GPS coordinates, and timestamp are embedded in JPEG/TIFF files. Can be used to verify or disprove claims about when/where a photo was taken.",
        "Blockchain for document provenance: immutable ledger records document hashes with timestamps. Tampering with a record would alter all subsequent block hashes. Used for land title records, supply chain, certificates.",
        "The chain of evidence rule: evidence must be continuous in custody from collection to court. Any gap allows a challenge. Sealed containers with tamper-evident seals and logs are standard practice.",
        "Legalese and plain language: legal documents often use precise but obscure language ('whereas', 'hereinafter', 'notwithstanding'). Plain language movement pushes for clarity. Ambiguous contracts are construed against the drafter.",
        "Document retention policies: organizations must retain certain records for defined periods (tax records: 7 years; employment records: vary by jurisdiction; legal holds override normal retention schedules).",
        "Electronic discovery (e-discovery): the process of identifying, collecting, and producing electronically stored information (ESI) for litigation. Governed by Federal Rules of Civil Procedure; requires litigation hold.",
        "PDF/A standard: ISO 14289 defines PDF/A for long-term archival — embeds all fonts and color profiles; prohibits encryption, external links, and dynamic content. Ensures documents render identically in the future.",
        "Steganography: hiding information within documents, images, or audio files (e.g., altering LSBs of pixels). Different from encryption (hidden existence vs hidden content). Detection: steganalysis.",
        "Open-source intelligence (OSINT) for document verification: reverse image search, social media verification, Whois lookups, archive.org for historical snapshots. Used by journalists and investigators to authenticate claims.",
        "The Concordance principle for document keeping: a witness record is only as strong as its chain of custody, the identity verification of its authors, and the integrity of its hash chain. These three form the verification substrate.",
        "Smart contracts as self-executing documents: code stored on a blockchain that automatically executes when conditions are met. Cannot be altered; execution is transparent and auditable. Eliminates need for trusted intermediary.",
    ],

    # ── OPTICS ───────────────────────────────────────────────────────────────
    "optics": [
        "Snell's law: n₁ sin θ₁ = n₂ sin θ₂. Light bends toward the normal when entering a denser medium. Critical angle: sin θ_c = n₂/n₁; total internal reflection occurs above this angle (basis of fiber optics).",
        "The thin lens equation: 1/f = 1/d_o + 1/d_i, where f = focal length, d_o = object distance, d_i = image distance. Positive f = converging (convex) lens; negative = diverging (concave) lens.",
        "Magnification: M = -d_i/d_o = h_i/h_o. Negative magnification means inverted image. For a simple magnifier: M = 25/f cm (near-point distance / focal length in cm).",
        "The wave nature of light: Young's double-slit experiment demonstrated interference (1801). Constructive interference: path difference = nλ; destructive: nλ + λ/2. Light behaves as both wave and particle (wave-particle duality).",
        "Diffraction: light bends around obstacles and apertures. Diffraction limited resolution (Rayleigh criterion): θ_min = 1.22 λ/D, where D = aperture diameter. Limits resolution of telescopes and microscopes.",
        "Polarization: transverse light waves can be linearly, circularly, or elliptically polarized. Malus's law: I = I₀ cos²θ. Brewster's angle: light reflected at this angle is completely polarized.",
        "Optical fibers: total internal reflection confines light in the core (high n) surrounded by cladding (low n). Single-mode fibers carry one ray path (minimal dispersion); multimode fibers allow multiple paths.",
        "The electromagnetic spectrum: radio, microwave, infrared, visible (400-700 nm), ultraviolet, X-ray, gamma. Visible light: red (~700 nm), green (~550 nm), blue (~450 nm). Photon energy E = hf = hc/λ.",
        "Antireflection coatings: thin film of thickness λ/4 (at refractive index √n₁n₂) causes destructive interference of reflected beams. Reduces reflectance from ~4% to < 0.5% at a specific wavelength.",
        "Lasers (Light Amplification by Stimulated Emission of Radiation): coherent, monochromatic, collimated light from stimulated emission. Four-level lasers: He-Ne (gas), Nd:YAG (solid-state), diode lasers (semiconductor).",
        "The compound microscope: objective lens creates a magnified intermediate image; eyepiece re-magnifies it. Total magnification = M_objective × M_eyepiece. Numerical aperture NA = n sin θ limits resolution.",
        "Spherical and chromatic aberration: spherical aberration — off-axis rays focus at different points from paraxial rays. Chromatic aberration — different wavelengths focus at different distances. Corrected with aspheric lenses and achromats.",
        "The human eye: cornea + crystalline lens focuses images on the retina. Accommodation: ciliary muscles change lens shape to focus near/far. Near-sightedness (myopia): image forms in front of retina; corrected with concave lens.",
        "Spectroscopy: each element emits or absorbs light at specific wavelengths (spectral lines). Hydrogen's Balmer series is visible. Used for chemical analysis (atomic absorption), astronomy, and remote sensing.",
        "Fourier optics: complex optical systems can be analyzed via the Fourier transform of the field amplitude. The lens performs a Fourier transform. Spatial filtering and holography are applications.",
        "Birefringence: anisotropic materials (calcite, quartz) have two refractive indices for different polarizations. Causes double refraction. Used in wave plates, polarizing beam splitters, and display technologies.",
        "Fiber Bragg gratings: periodic variations in fiber refractive index reflect specific wavelengths while transmitting others. Used as wavelength filters, sensors (temperature, strain), and in fiber lasers.",
        "Night vision and thermal imaging: image intensifiers amplify ambient light (Gen 1-3). Thermal cameras detect infrared radiation emitted by objects above absolute zero. Thermal = no illumination needed.",
        "The Abbe number (V-number): characterizes dispersion of optical glass. High V = low dispersion (crown glass, V > 50); low V = high dispersion (flint glass, V < 30). Chromatic aberration correction requires pairing crown and flint.",
        "Nonlinear optics: at high intensities, the refractive index depends on intensity (Kerr effect). Second-harmonic generation (SHG) converts two photons into one with double frequency. Used in green laser pointers (infrared → green via KTP crystal).",
    ],

    # ── PHOTOGRAPHY ──────────────────────────────────────────────────────────
    "photography": [
        "The exposure triangle: aperture (f-stop), shutter speed, and ISO together determine exposure. Each setting has trade-offs: aperture affects depth of field; shutter speed affects motion blur; ISO affects noise.",
        "F-stops: aperture diameter = focal length / f-number. f/2.8 lets in 4× more light than f/5.6. Full stops: f/1.4, f/2, f/2.8, f/4, f/5.6, f/8, f/11, f/16. Each full stop doubles or halves light.",
        "Depth of field: the range of distances in acceptable focus. Shallow DoF: large aperture (f/1.8), long focal length, close subject. Deep DoF: small aperture (f/16), short focal length, distant subject.",
        "The hyperfocal distance: the closest focus distance at which objects at infinity are acceptably sharp. Focus at hyperfocal distance for maximum DoF. H ≈ f²/(Nc) where f = focal length, N = f-number, c = circle of confusion.",
        "Shutter speed effects: fast shutter (1/1000s) freezes motion; slow shutter (1/30s) blurs motion. The rule of thumb: minimum shutter speed = 1/focal length to avoid camera shake (without stabilization).",
        "ISO and image noise: ISO amplifies the sensor signal. ISO 100 is base sensitivity; ISO 3200 has 5 stops more sensitivity but significantly more grain/noise. Modern mirrorless cameras are usable at ISO 6400-12800.",
        "RAW vs JPEG: RAW files contain unprocessed sensor data (12-14 bit). JPEG is compressed 8-bit processed image. RAW allows more latitude in post-processing exposure, white balance, and dynamic range.",
        "White balance: adjusts colors to account for light source color temperature. Daylight ≈ 5500K, tungsten ≈ 3200K, fluorescent ≈ 4000K. Auto white balance works well in neutral scenes; manual needed for mixed lighting.",
        "Lens focal length and perspective: wide angle (< 35mm) exaggerates foreground-background distance; telephoto (> 85mm) compresses depth. Perspective is determined by shooting position, not focal length.",
        "The zone system (Ansel Adams): divides the tonal range into 11 zones (Zone 0 = black, Zone X = white). Expose for the shadows; develop for the highlights. Systematic approach to film exposure and development.",
        "Histograms: graphical representation of tonal distribution. Peaks at left = underexposure; at right = overexposure; clipping = detail loss in shadows/highlights. Evaluating the histogram is more reliable than viewing the screen.",
        "Composition rules: rule of thirds (divide frame into 3×3 grid; place subjects at intersections), leading lines (draw viewer's eye), framing (use foreground elements to frame subject), rule of odds.",
        "Golden hour and blue hour: the hour after sunrise and before sunset (golden hour) provides warm, directional light with long shadows. The blue hour 20-30 minutes before/after golden hour gives cool, soft light.",
        "Sensor size and equivalence: larger sensors capture more light, have less noise, and shallower DoF. Full frame (36×24mm) vs APS-C (22×15mm, 1.5× crop factor) vs Micro Four Thirds (17×13mm, 2× crop). Equivalence: same DoF and noise requires proportionally wider aperture and lower ISO on crop sensor.",
        "Photogrammetry: creating 3D models from overlapping photographs. Requires multiple angles, common reference points, and known scale. Used in surveying, archaeology, forensics, and VFX. Software: Reality Capture, Metashape.",
        "Forensic photography: documents crime scenes before disturbance. Scale markers in every shot; overall, medium, and close-up views; measured diagrams. Chain of custody must be maintained from capture to presentation.",
        "HDR imaging: multiple exposures (±2 EV) are merged to capture scenes exceeding the camera's dynamic range (~12 stops). Tone mapping reduces to displayable range. Overcooking creates HDR 'look'; subtlety is preferred.",
        "Long exposure photography: 10-30 second exposures at night create light trails (vehicles), star trails, and silky water. Requires tripod, remote shutter, and mirror lockup to minimize vibration.",
        "The Sunny 16 rule: in bright sunlight, correct exposure is approximately f/16, 1/ISO shutter speed. ISO 100 → 1/100s at f/16. A useful baseline without a light meter.",
        "Color theory in photography: complementary colors (opposite on color wheel) create contrast and visual interest. Analogous colors (adjacent) create harmony. Color temperature shifts create mood: warm = inviting; cool = calm or cold.",
    ],

    # ── WITNESS (testimony, credibility, corroboration) ──────────────────────
    "witness": [
        "A witness is someone with direct personal knowledge of an event or fact. Eyewitness testimony is powerful evidence but notoriously unreliable — memory is reconstructive, not recording.",
        "The criteria for credible testimony: proximity (was the witness present?), competence (did they have the capacity to observe?), consistency (is the account internally coherent?), corroboration (do other witnesses or evidence agree?).",
        "The Concordance witness record: a sealed, cryptographically signed attestation of what was observed, when, and by whom. The four-gate protocol ensures only passes reach the GOD gate for permanent witnessing.",
        "False memory: Elizabeth Loftus' research demonstrated that eyewitness memories can be contaminated by post-event information, leading questions, and social pressure. Wrongful convictions often rely on faulty eyewitness testimony.",
        "Corroboration rules: in many legal systems, some categories of testimony (accomplice testimony, confessions, children's testimony) require corroboration — independent evidence supporting the account.",
        "The role of cross-examination: the primary tool for testing witness credibility in adversarial systems. Tests perception, memory, bias, consistency, and prior inconsistent statements.",
        "Hearsay: an out-of-court statement offered to prove the truth of its contents. Generally excluded because the original declarant cannot be cross-examined. Exceptions: dying declarations, excited utterances, business records.",
        "Expert witnesses: testify to specialized knowledge that assists the trier of fact. Standards: Daubert (US) — methodology must be scientifically valid; Frye — general acceptance in the relevant scientific community.",
        "The reliability of early witnesses: in historical testimony, nearness to events is crucial. Paul's argument in 1 Corinthians 15:6 — 'most of the 500 are still alive' — is an explicit appeal to living corroboration.",
        "Notarial witness: a disinterested party who verifies the identity and signing of documents. Not attesting to truth of content, but to the authenticity of the signature and the fact of signing.",
        "Blockchain as witness: immutable ledgers function as distributed witnesses — they record what happened, when, and in what order, with cryptographic proof that the record has not been altered.",
        "The oath: a formal declaration invoking a higher authority (God, one's honor) to guarantee truthfulness. Perjury (lying under oath) carries criminal penalties because it corrupts the judicial process.",
        "Witness protection in Scripture: 'A matter must be established by the testimony of two or three witnesses' (Deuteronomy 19:15; Matthew 18:16; 2 Corinthians 13:1). Multiple witnesses guard against false accusation.",
        "The false witness: Scripture condemns bearing false witness (Exodus 20:16, ninth commandment). Consequences: the false witness receives the punishment intended for the accused (Deuteronomy 19:18-19). Structural deterrent.",
        "Chain of custody and testimony: a gap in the chain of custody allows the defense to argue evidence was tampered with. Similarly, a gap in testimonial continuity weakens historical claims.",
        "The Concordance witness tier: after verification through the four gates, a packet can be sent to the witness register — a permanent, signed, timestamped record on the ledger. This is Path A (soulbound receipts).",
        "Spiritual discernment as witness: 'Test everything; hold fast what is good' (1 Thessalonians 5:21). The community of believers functions as a collective witness, testing claims against Scripture and lived experience.",
        "Forensic linguistics: analysis of linguistic features (vocabulary, syntax, style) to identify authorship, date of composition, or authenticity of documents. Used in plagiarism detection, will disputes, and historical source criticism.",
        "Witness in martyrdom: the Greek word 'martys' (witness) became 'martyr' because early Christians died for their testimony. Their willingness to die rather than recant distinguishes conviction from social pressure.",
        "The standard of proof: criminal (beyond reasonable doubt, ~99% certainty), civil (preponderance of evidence, > 50%), clear and convincing evidence (~75%). The stakes determine the required reliability of witness accounts.",
    ],
}


# ── Runner ────────────────────────────────────────────────────────────────────

def load_state() -> set:
    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
            return set(data.get("posted", []))
        except Exception:
            return set()
    return set()

def save_state(posted: set):
    STATE_FILE.write_text(
        json.dumps({"posted": sorted(posted)}, indent=2),
        encoding="utf-8"
    )

def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()[:16]

def post_seed(session: requests.Session, domain: str, text: str, dry_run: bool) -> bool:
    preview = text[:60].replace("\n", " ")
    if dry_run:
        print(f"  [DRY] {domain}: {preview}…")
        return True
    payload = {
        "text": text,
        "source": f"seed:{domain}",
        "tags": [domain, "seed", "curated"],
    }
    try:
        r = session.post(f"{API_BASE}/capture", json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        total = (data.get("calibration") or {}).get("total_entries_to_date", "?")
        print(f"  ✓ [{domain}] #{total}  {preview}…")
        return True
    except Exception as e:
        print(f"  ✗ [{domain}] {e}  {preview}…")
        return False


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--domain", help="Run only this domain")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--delay", type=float, default=1.2)
    parser.add_argument("--reset", action="store_true")
    args = parser.parse_args()

    posted = set() if args.reset else load_state()
    session = requests.Session()

    domains = {args.domain: SEEDS[args.domain]} if args.domain else SEEDS

    total_seeds = sum(len(v) for v in domains.values())
    total_new = sum(
        1 for seeds in domains.values()
        for s in seeds if fingerprint(s) not in posted
    )
    print(f"\nWave 5 — {total_seeds} seeds across {len(domains)} domains")
    print(f"Already posted: {len(posted)}  New: {total_new}\n")

    for domain, seeds in domains.items():
        new_in_domain = [s for s in seeds if fingerprint(s) not in posted]
        if not new_in_domain:
            print(f"── {domain.upper()} — all {len(seeds)} already posted, skipping")
            continue

        print(f"\n── {domain.upper()} ({len(new_in_domain)} new / {len(seeds)} total) ──")
        for text in new_in_domain:
            fp = fingerprint(text)
            ok = post_seed(session, domain, text, args.dry_run)
            if ok and not args.dry_run:
                posted.add(fp)
                save_state(posted)
            if not args.dry_run:
                time.sleep(args.delay)

    print(f"\nDone. Total posted this run: {total_new if not args.dry_run else 0}")


if __name__ == "__main__":
    main()
