"""Chemistry domain validator — full RED/FLOOR checks from chemistry_core.yaml.

RED constraints (all 7 from core):
  1. Mass conservation: atoms conserved within defined system boundary
  2. Charge conservation: all reaction stoichiometries
  3. Dimensional consistency: unit errors invalidate results
  4. State/path integrity: U, H, S, G path-independent; no mixing with path quantities
  5. Activity equilibrium: Keq defined in activities; concentration form requires explicit assumption
  6. Non-negative concentrations: rate laws and extents must be physically admissible
  7. Absolute temperature: thermodynamic relations require T > 0 K

FLOOR bounds (all 5 from core):
  1. Units and reference states declared (DH, DG, E, sign conventions)
  2. Significant figures consistent with input precision
  3. System boundary (closed/open), phase(s), ideality assumption declared
  4. Limiting cases checked (c->0, high dilution, high pressure)
  5. Safety notes included for hazardous reagents/conditions when relevant

Diagnostic chain (from core): root -> regime_check -> data_check -> sanity_check
"""
from __future__ import annotations
from typing import Any, Dict, List
from ..gates import reject, ok
from ..packet import GateResult


class ChemistryValidator:
    domain = "chemistry"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        setup = packet.get("CHEM_SETUP", packet.get("regime", {})) or {}
        red = packet.get("CHEM_RED", {}) or {}

        # 1. Mass conservation
        if red.get("mass_conserved") is False:
            errors.append("mass/atom balance violated — atoms must be conserved within system boundary")

        # 2. Charge conservation
        if red.get("charge_conserved") is False:
            errors.append("charge conservation violated in reaction stoichiometry")

        # 3. Dimensional consistency
        if red.get("dimensional_consistency") is False:
            errors.append("dimensional inconsistency — unit errors invalidate all derived results")

        # 4. State/path function integrity
        if red.get("state_path_integrity") is False:
            errors.append("state/path function mixing — U,H,S,G are path-independent; do not mix with path quantities")

        # 5. Equilibrium constants in activities
        if red.get("equilibrium_in_activities") is False:
            errors.append("equilibrium constant must use activities; concentration form requires explicit ideality declaration")

        # 6. Non-negative concentrations
        if red.get("non_negative_concentrations") is False:
            errors.append("negative concentration computed — rate law or reaction extent error")

        # 7. Absolute temperature
        temp = setup.get("temperature_K", setup.get("temperature"))
        if temp is not None:
            try:
                if float(temp) <= 0:
                    errors.append(f"temperature must be positive absolute (K); got {temp}")
            except (ValueError, TypeError):
                pass

        # Diagnostic chain signals
        for d in (packet.get("diagnostics") or []):
            if isinstance(d, dict):
                sig = str(d.get("signal", "")).lower()
                diag = str(d.get("diagnosis", "")).upper()
                if "balance" in sig and "fail" in sig:
                    errors.append(f"diagnostic: {d.get('signal')}")
                if "negative" in sig:
                    errors.append(f"diagnostic: {d.get('signal')}")
                if diag in ("SPECIFICATION_OR_BALANCING_ERROR", "RED_VIOLATION"):
                    errors.append(f"diagnostic RED: {d.get('diagnosis')} — {d.get('action', '')}")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        setup = packet.get("CHEM_SETUP", packet.get("regime", {})) or {}
        floor = packet.get("CHEM_FLOOR", {}) or {}

        if floor or setup:
            # 1. Units and sign conventions
            if floor.get("units_stated") is False:
                errors.append("units and reference states not declared (DH, DG, E require sign convention)")
            if floor.get("sign_conventions_declared") is False:
                errors.append("sign conventions not declared — DH, DG, E are ambiguous without convention")

            # 2. Significant figures
            if floor.get("significant_figures_consistent") is False:
                errors.append("significant figures inconsistent with input precision")

            # 3. System boundary, phase, ideality
            if floor.get("system_boundary_declared") is False:
                errors.append("system boundary (closed/open) and phase(s) not declared")
            if floor.get("ideality_stated") is False:
                errors.append("ideality assumption not stated — ideal gas/solution requires explicit declaration")

            # 4. Limiting cases
            if floor.get("limiting_cases_checked") is False:
                errors.append("limiting case checks not performed — verify at c->0, high dilution, relevant extremes")

            # 5. Safety notes
            if floor.get("hazardous_conditions") is True and floor.get("safety_notes_included") is False:
                errors.append("hazardous conditions flagged but safety notes not included")

            # Diagnostic chain: FLOOR-level diagnostics
            for d in (packet.get("diagnostics") or []):
                if isinstance(d, dict):
                    diag = str(d.get("diagnosis", "")).upper()
                    if diag == "MODEL_MISMATCH":
                        errors.append(f"FLOOR: MODEL_MISMATCH — {d.get('action', 'switch to activity/fugacity model')}")
                    if diag == "DATA_SCOPE_ERROR":
                        errors.append(f"FLOOR: DATA_SCOPE_ERROR — {d.get('action', 'use T/ionic-strength corrections')}")

        else:
            if not packet.get("claims") and not packet.get("regime"):
                errors.append("Chemistry packets must include CHEM_SETUP or CHEM_FLOOR or claims[]")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
