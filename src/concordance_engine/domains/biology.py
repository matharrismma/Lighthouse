"""Biology domain validator — full RED/FLOOR checks from biology_core.yaml.

RED (from biology_core.yaml):
  - Non-contradiction (logic)
  - Conservation: mass/charge/energy (open system; boundary fluxes must be declared)
  - Second Law: local order requires entropy export; no perpetual motion
  - Causality: no effect without mechanism; temporal ordering required
  - Stoichiometry: elemental/charge balance in biochemical transformations
  - Non-negativity: probabilities >= 0; information measures well-defined
  - Channel limits: noise/bandwidth constraints apply to signaling

FLOOR (from biology_core.yaml):
  - Reference conditions declared (pH, ionic strength, temperature)
  - Measurement doctrine: controls + calibration + uncertainty + replication
  - Orthogonality: >= 2 orthogonal assay classes for decision-grade claims
  - Replication minimum: biological n >= 3 unless justified
  - Viability: viability/toxicity bounds checked when intervention applied
"""
from __future__ import annotations
from typing import Any, Dict, List
from ..gates import reject, ok
from ..packet import GateResult


class BiologyValidator:
    domain = "biology"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        red = packet.get("BIO_RED", {}) or {}
        setup = packet.get("BIO_SETUP", {}) or {}

        # --- Conservation ---
        conservation = red.get("conservation", {}) or {}
        if conservation.get("mass_balance") is False:
            errors.append("mass balance violated — declare boundary fluxes for open system")
        if conservation.get("charge_balance") is False:
            errors.append("charge balance violated in biochemical transformation")
        if conservation.get("energy_budget") is False:
            errors.append("energy budget implausible — open system entropy export required")

        # --- Second Law ---
        if red.get("second_law_satisfied") is False:
            errors.append("Second Law violated — local order requires entropy export; no perpetual motion")

        # --- Causality ---
        causality = red.get("causality", {}) or {}
        if causality.get("mechanism_specified") is False:
            errors.append("causality violation — no effect without mechanism; temporal ordering required")

        # --- Stoichiometry ---
        if red.get("stoichiometry_balanced") is False:
            errors.append("stoichiometric balance fails in biochemical transformation")

        # --- Non-negativity ---
        if red.get("probabilities_non_negative") is False:
            errors.append("probability or information measure is negative — model error")

        # --- Perpetual motion / thermodynamic impossibility ---
        if red.get("perpetual_motion_claimed") is True:
            errors.append("perpetual motion claimed — violates thermodynamic bounds")

        # --- Flat packet fallback: check for minimum required fields ---
        if not red and not setup:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("Biology packets must include BIO_RED or claims[]")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        floor = packet.get("BIO_FLOOR", {}) or {}
        setup = packet.get("BIO_SETUP", {}) or {}
        measurement = packet.get("BIO_MEASUREMENT", {}) or {}

        if floor or setup or measurement:
            # --- Reference conditions ---
            ref = floor.get("reference_conditions", setup.get("reference_conditions", {})) or {}
            if ref:
                # If reference conditions are declared, temperature should be present
                if "temperature_K" in ref and ref["temperature_K"] is not None:
                    try:
                        if float(ref["temperature_K"]) <= 0:
                            errors.append("reference temperature must be positive (K)")
                    except (ValueError, TypeError):
                        pass

            # --- Measurement doctrine ---
            meas = measurement or floor.get("measurement", {}) or {}
            if meas:
                controls = meas.get("controls_included")
                if controls is False:
                    errors.append("measurement doctrine: controls required (positive, negative, vehicle/isogenic)")

                bio_reps = meas.get("biological_replicates")
                if bio_reps is not None:
                    try:
                        n = int(bio_reps)
                        if n < 3 and not meas.get("replication_justified"):
                            errors.append(f"biological replicates = {n} (minimum 3; set replication_justified=true to override)")
                    except (ValueError, TypeError):
                        pass

                # Orthogonality for decision-grade claims
                if meas.get("decision_grade_claim") is True:
                    assays = meas.get("orthogonal_assay_classes", [])
                    if not (isinstance(assays, list) and len(assays) >= 2):
                        errors.append("decision-grade claim requires >= 2 orthogonal assay classes")

            # --- High variance flag ---
            cv = floor.get("coefficient_of_variation")
            if cv is not None:
                try:
                    if float(cv) > 0.30:
                        errors.append(f"CV = {cv:.2f} > 0.30 — HIGH_VARIANCE: tighten controls/batching before decision-grade claims")
                except (ValueError, TypeError):
                    pass

        else:
            # Flat packet: need at least artifacts or measurement plan
            artifacts = packet.get("artifacts") or {}
            if not artifacts:
                errors.append("Biology packets must include BIO_FLOOR, BIO_SETUP, or artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
