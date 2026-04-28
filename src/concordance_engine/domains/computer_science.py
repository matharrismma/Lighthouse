"""Computer Science domain validator — full RED/FLOOR checks from cs_core.yaml.

RED constraints (7 from core):
  1. Algorithm termination: must terminate or non-termination proven intentional
  2. Complexity variable defined: n must be explicit in any O/Omega/Theta claim
  3. No undefined behavior: OOB access, null dereference, data races, type errors
  4. Reduction direction stated: A reduces to B means B is at least as hard as A
  5. Encoding bijectivity stated: one-way functions not called encodings without qualification
  6. Formal model specified: language claims must state DFA/PDA/TM/etc.
  7. Distributed consistency cited: linearizability/serializability claims need formal model

FLOOR bounds (6 from core):
  1. Input/output domains declared
  2. Case analysis stated: best/worst/average/amortized
  3. Space complexity alongside time when memory is relevant
  4. Proof technique named for correctness claims
  5. Fault model declared for distributed systems
  6. Memory model cited for concurrent systems
"""
from __future__ import annotations
from typing import Any, Dict, List
from ..gates import reject, ok
from ..packet import GateResult


class ComputerScienceValidator:
    domain = "computer_science"

    def validate_red(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        red = packet.get("CS_RED", {}) or {}
        complexity = packet.get("CS_COMPLEXITY", {}) or {}

        # 1. Termination
        if red.get("termination_proven") is False:
            errors.append("algorithm termination unproven — add loop variant or classify as non-terminating by design")

        # 2. Complexity variable defined
        if red.get("complexity_variable_defined") is False:
            errors.append("complexity claim missing input variable definition — state what n represents")

        # Also catch complexity block without input variable
        if complexity and not complexity.get("input_variable"):
            if complexity.get("time_bound") or complexity.get("space_bound"):
                errors.append("CS_COMPLEXITY block present but input_variable not defined")

        # 3. Undefined behavior
        if red.get("no_undefined_behavior") is False:
            errors.append("undefined behavior present — OOB access, null dereference, data race, or type error detected")

        # 4. Reduction direction
        if red.get("reduction_direction_stated") is False:
            errors.append("reduction direction not stated — A reduces to B means B is at least as hard as A; direction matters")

        # 5. Encoding bijectivity
        if red.get("encoding_bijectivity_stated") is False:
            errors.append("encoding bijectivity not stated — declare injective/surjective/bijective or qualify one-way functions")

        # 6. Formal model for language claims
        if red.get("formal_model_specified") is False:
            errors.append("formal language claim without model of computation — specify DFA, PDA, TM, etc.")

        # 7. Distributed consistency model
        if red.get("consistency_model_cited") is False:
            errors.append("distributed consistency claim without formal model — cite linearizability, sequential consistency, or eventual consistency definition")

        # Diagnostic signals
        for d in (packet.get("diagnostics") or []):
            if isinstance(d, dict):
                diag = str(d.get("diagnosis", "")).upper()
                if diag in ("TERMINATION_UNPROVEN", "UNDEFINED_BEHAVIOR_RISK"):
                    errors.append(f"diagnostic RED: {diag} — {d.get('action', '')}")

        # Flat packet fallback
        if not red and not complexity:
            claims = packet.get("claims", [])
            if not isinstance(claims, list) or len(claims) == 0:
                errors.append("CS packets must include CS_RED, CS_COMPLEXITY, or claims[]")

        if errors:
            return [reject("RED", *errors)]
        return [ok("RED")]

    def validate_floor(self, packet: Dict[str, Any]) -> List[GateResult]:
        errors: List[str] = []
        floor = packet.get("CS_FLOOR", {}) or {}
        complexity = packet.get("CS_COMPLEXITY", {}) or {}

        if floor or complexity:
            # 1. Input/output domains
            if floor.get("input_output_declared") is False:
                errors.append("input and output domains not declared for algorithm")

            # 2. Case analysis
            if floor.get("case_analysis_stated") is False:
                errors.append("complexity case not stated — specify worst/average/best/amortized")

            # Also check complexity block
            if complexity and not complexity.get("case"):
                errors.append("CS_COMPLEXITY block missing case field (worst/average/best/amortized)")

            # 3. Space complexity
            if floor.get("space_complexity_stated") is False:
                errors.append("space complexity not stated — required when memory is a relevant constraint")

            # 4. Proof technique
            if floor.get("proof_technique_named") is False:
                errors.append("correctness proof technique not named — state loop invariant, induction, bisimulation, etc.")

            # 5. Fault model for distributed
            if floor.get("fault_model_declared") is False:
                errors.append("distributed system fault model not declared — specify crash-stop, crash-recovery, or Byzantine")

            # 6. Memory model for concurrent
            if floor.get("memory_model_cited") is False:
                errors.append("concurrent system memory model not cited — specify sequential consistency, TSO, release-acquire, etc.")

            # Diagnostic signals
            for d in (packet.get("diagnostics") or []):
                if isinstance(d, dict):
                    diag = str(d.get("diagnosis", "")).upper()
                    if diag in ("COMPLEXITY_UNDERSPECIFIED", "CONSISTENCY_UNSPECIFIED"):
                        errors.append(f"FLOOR diagnostic: {diag} — {d.get('action', '')}")

        else:
            artifacts = packet.get("artifacts") or {}
            if not artifacts:
                errors.append("CS packets must include CS_FLOOR, CS_COMPLEXITY, or artifacts{}")

        if errors:
            return [reject("FLOOR", *errors)]
        return [ok("FLOOR")]
