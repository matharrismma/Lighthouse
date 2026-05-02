from __future__ import annotations
from typing import Any, Dict, List
from ..gates import reject, ok
from ..packet import GateResult


class MusicTheoryValidator:
    domain = "music_theory"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        mv = packet.get("MUS_VERIFY") or {}
        if not mv:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or not claims:
                errors.append("Music-theory packets must include either MUS_VERIFY{} or non-empty claims[]")
            return [reject("RED", *errors)] if errors else [ok("RED")]
        for fld in ("freq_a", "freq_b", "claimed_frequency_hz"):
            if fld in mv:
                try:
                    v = float(mv[fld])
                    if v <= 0:
                        errors.append(f"{fld} must be positive, got {v}")
                except (TypeError, ValueError):
                    errors.append(f"{fld} must be numeric")
        if "midi_note" in mv:
            try:
                v = int(mv["midi_note"])
                if not (0 <= v <= 127):
                    errors.append(f"midi_note must be 0-127, got {v}")
            except (TypeError, ValueError):
                errors.append("midi_note must be an integer")
        return [reject("RED", *errors)] if errors else [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        mv = packet.get("MUS_VERIFY") or {}
        if mv:
            keys = ("claimed_semitones", "claimed_interval", "claimed_frequency_hz", "claimed_in_scale")
            if not any(k in mv for k in keys):
                return [reject("FLOOR", "MUS_VERIFY block must contain at least one verifiable claim")]
        else:
            artifacts = packet.get("artifacts") or {}
            if not isinstance(artifacts, dict) or not artifacts:
                return [reject("FLOOR", "Music-theory packets without MUS_VERIFY must declare artifacts{}")]
        return [ok("FLOOR")]
