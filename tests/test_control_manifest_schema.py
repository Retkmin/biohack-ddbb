"""Phase 1.1 / 2.2 — greenfield deployment-plan JSON Schema contract.

Proves the ``control-manifest.schema.json`` artifact is a real, enforceable
greenfield contract — not a decorative file:

  * it parses as valid JSON and declares draft 2020-12;
  * its ``required`` list covers every mandated greenfield field (immutable
    plan checksum, environment, release digests, DNS names, named human
    approvals, prerequisite attestations, retention, state, receipts, and
    residual-risk record);
  * it carries NO legacy authority-switch fields (no ``transition_id``,
    ``generation``, ``authority``, ``participants``, ``acknowledgements``,
    ``reconciliation_checksum``, ``restore_proof_id``, or
    ``legacy_copy_attestation``);
  * its ``$defs`` define the ``approval`` shape the backend validator
    (``control_manifest.py``) enforces.

Structural and environment-free: it reads the schema file and asserts the
declared contract; no Docker, database, credential, or VPS action. This is the
focused proof for task 2.2 (schema rework); the contract's runtime ENFORCEMENT
is proven by the greenfield validator suite in biohack-back.
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SCHEMA_PATH = REPO / "deploy" / "production" / "control-manifest.schema.json"

REQUIRED_TOP_LEVEL = [
    "plan_sha256",
    "environment",
    "backend_digest",
    "frontend_digest",
    "dns_names",
    "approvals",
    "protected_config_attestation",
    "tls_readiness",
    "capacity_limits",
    "retention_window",
    "state",
    "receipt_ids",
    "residual_risk_recorded",
]

# Legacy authority-switch fields must NOT exist in the greenfield contract.
LEGACY_FIELDS = (
    "transition_id",
    "generation",
    "authority",
    "participants",
    "acknowledgements",
    "reconciliation_checksum",
    "restore_proof_id",
    "legacy_copy_attestation",
    "windows",
)


def _schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_schema_parses_as_json_object():
    schema = _schema()
    assert isinstance(schema, dict)


def test_schema_declares_draft_2020_12():
    schema = _schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"


def test_schema_requires_all_mandated_top_level_fields():
    schema = _schema()
    assert sorted(schema["required"]) == sorted(REQUIRED_TOP_LEVEL)


def test_schema_rejects_unknown_top_level_fields():
    schema = _schema()
    assert schema.get("additionalProperties") is False


def test_schema_defines_approval_def():
    schema = _schema()
    assert set(schema["$defs"]) == {"approval"}


def test_schema_requires_all_named_approvals():
    schema = _schema()
    approvals = schema["properties"]["approvals"]
    assert sorted(approvals["required"]) == ["activation", "initialization", "preflight"]


def test_schema_requires_release_digests():
    schema = _schema()
    for key in ("backend_digest", "frontend_digest"):
        assert key in schema["properties"]
        assert "pattern" in schema["properties"][key]


def test_schema_environment_is_greenfield_only():
    schema = _schema()
    assert schema["properties"]["environment"]["enum"] == ["vps-greenfield"]


def test_schema_state_enum_matches_greenfield_states():
    schema = _schema()
    assert sorted(schema["properties"]["state"]["enum"]) == [
        "active",
        "blocked",
        "healthy",
        "initialized",
        "preflight",
    ]


def test_schema_has_no_legacy_authority_fields():
    schema = _schema()
    for field in LEGACY_FIELDS:
        assert field not in schema["properties"], f"legacy field leaked: {field}"
        assert field not in schema["required"], f"legacy field leaked in required: {field}"
