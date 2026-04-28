from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Tuple

try:
    import jsonschema
    _HAS_JSONSCHEMA = True
except ImportError:
    jsonschema = None
    _HAS_JSONSCHEMA = False


def sha256_bytes(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def canonical_json_bytes(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def load_schema(schema_path: Path) -> Dict[str, Any]:
    return json.loads(schema_path.read_text(encoding="utf-8"))


def _fallback_validate(packet: Dict[str, Any], schema: Dict[str, Any]) -> None:
    """Minimal structural validation when jsonschema is not installed.

    Checks: required top-level fields, top-level type, and that any keys
    present are recognized in the schema's properties. This is a triage
    pass — install jsonschema for the full validator.
    """
    errors: List[str] = []
    required = schema.get("required", [])
    for r in required:
        if r not in packet:
            errors.append(f"missing required field: {r!r}")

    schema_type = schema.get("type")
    if schema_type == "object" and not isinstance(packet, dict):
        errors.append(f"top-level must be object, got {type(packet).__name__}")

    if schema.get("additionalProperties") is False and isinstance(packet, dict):
        properties = set(schema.get("properties", {}).keys())
        for k in packet.keys():
            if k not in properties:
                errors.append(f"unrecognized key: {k!r}")

    if errors:
        raise ValueError("schema validation failed: " + "; ".join(errors))


def validate_against_schema(packet: Dict[str, Any], schema: Dict[str, Any]) -> None:
    """Validate packet against schema. Uses jsonschema if available, else structural fallback."""
    if _HAS_JSONSCHEMA:
        jsonschema.validate(instance=packet, schema=schema)
    else:
        _fallback_validate(packet, schema)


def compute_packet_hash(packet: Dict[str, Any]) -> str:
    return sha256_bytes(canonical_json_bytes(packet))
