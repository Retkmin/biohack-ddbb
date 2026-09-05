"""Phase 2.2 — greenfield deployment protocol (disposable-stack simulation).

Proves the fail-closed greenfield primitives in
``ops/lib/operation-contract.sh`` using temporary attestation/store files (the
disposable-stack equivalent of the real prerequisite gates):

  * plan identity                 — the plan-file checksum is deterministic and
                                    redacted;
  * prerequisite attestations     — a missing or negative attestation blocks;
  * empty-store fencing           — a non-empty scoped store blocks
                                    initialization;
  * atomic state publication      — state is published atomically with no temp
                                    file leftover;
  * activation gating             — activation requires every gate attestation
                                    for the exact plan checksum;
  * secret-free blocked receipt   — a blocked gate emits a redacted receipt.

No VPS, database, credential, or data movement is touched — every test sources
the shared contract library and writes only redacted temporary files.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONTRACT_LIB = REPO / "ops" / "lib" / "operation-contract.sh"

SECRET_MARKERS = ("password", "token", "secret", "postgresql://", "postgres://", "@", "email")

GATES = ("plan", "protected_config", "digests", "dns_tls", "capacity", "retention")


def _find_bash() -> str:
    candidates = (
        os.environ.get("BASH"),
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
    )
    for candidate in candidates:
        if candidate and os.path.isfile(candidate):
            return candidate
    for name in ("bash", "sh"):
        found = shutil.which(name)
        if found:
            return found
    pytest.skip("bash is not available in this environment")


BASH = _find_bash()


def _posix(path: Path) -> str:
    value = str(path).replace("\\", "/")
    if len(value) >= 2 and value[1] == ":":
        value = "/" + value[0].lower() + value[2:]
    return value


def _script(body: str, *, cwd: Path | None = None) -> subprocess.CompletedProcess:
    lib = _posix(CONTRACT_LIB)
    return subprocess.run(
        [BASH, "-c", f'. "{lib}"; {body}'],
        capture_output=True,
        text=True,
        cwd=str(cwd or REPO),
    )


def _write_attestation(gates_dir: Path, gate: str, plan_sha: str, attested: bool = True) -> None:
    gates_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps({"gate": gate, "plan_sha256": plan_sha, "attested": attested})
    (gates_dir / f"{gate}.attestation.json").write_text(payload, encoding="utf-8")


# ── Action allowlist ───────────────────────────────────────────────────────


def test_preflight_and_verify_empty_are_allowlisted():
    for action in ("preflight", "verify-empty", "initialize", "activate"):
        result = _script(f'contract_validate_action "{action}" && echo ok')
        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout


def test_lifecycle_actions_map_to_store_operation_service():
    for action in ("initialize", "activate"):
        result = _script(
            f'service=$(contract_service_for "{action}" identity); [ "$service" = "store-operation" ] && echo ok'
        )
        assert result.returncode == 0, result.stderr
        assert "ok" in result.stdout


def test_legacy_authority_primitives_removed():
    for name in ("contract_record_acknowledgement", "contract_all_acknowledged", "contract_drain_proof_ok"):
        result = _script(f'command -v {name} >/dev/null 2>&1 && echo present || echo absent')
        assert "absent" in result.stdout, f"{name} should have been removed"


# ── Plan identity ──────────────────────────────────────────────────────────


def test_plan_file_checksum_is_deterministic(tmp_path):
    plan = tmp_path / "plan.json"
    plan.write_text('{"plan_sha256":"%s"}' % ("a" * 64), encoding="utf-8")
    result = _script(
        f'a=$(contract_plan_file_checksum "{_posix(plan)}"); '
        f'b=$(contract_plan_file_checksum "{_posix(plan)}"); '
        f'[ "$a" = "$b" ] && echo deterministic; echo "sha=$a"'
    )
    assert "deterministic" in result.stdout
    sha_line = next(line for line in result.stdout.splitlines() if line.startswith("sha="))
    for marker in SECRET_MARKERS:
        assert marker not in sha_line


# ── Prerequisite attestation ───────────────────────────────────────────────


def test_attestation_ok_accepts_attested(tmp_path):
    gates = tmp_path / "gates"
    _write_attestation(gates, "plan", "a" * 64)
    result = _script(
        f'contract_attestation_ok "{_posix(gates / "plan.attestation.json")}" && echo ok'
    )
    assert result.returncode == 0
    assert "ok" in result.stdout


def test_attestation_ok_rejects_missing(tmp_path):
    result = _script(f'contract_attestation_ok "{_posix(tmp_path / "nope.json")}"')
    assert result.returncode != 0
    assert "missing attestation" in result.stderr


def test_attestation_ok_rejects_negative(tmp_path):
    gates = tmp_path / "gates"
    _write_attestation(gates, "digests", "a" * 64, attested=False)
    result = _script(
        f'contract_attestation_ok "{_posix(gates / "digests.attestation.json")}"'
    )
    assert result.returncode != 0
    assert "attestation not granted" in result.stderr


# ── Empty-store fencing ────────────────────────────────────────────────────


def test_empty_store_ok_accepts_empty(tmp_path):
    store = tmp_path / "identity"
    store.mkdir()
    result = _script(f'contract_empty_store_ok "{_posix(store)}" && echo ok')
    assert result.returncode == 0
    assert "ok" in result.stdout


def test_empty_store_ok_rejects_non_empty(tmp_path):
    store = tmp_path / "domain"
    store.mkdir()
    (store / "row.dat").write_text("data", encoding="utf-8")
    result = _script(f'contract_empty_store_ok "{_posix(store)}"')
    assert result.returncode != 0
    assert "store not empty" in result.stderr


# ── Atomic publication ─────────────────────────────────────────────────────


def test_atomic_publish_writes_complete_content(tmp_path):
    target = tmp_path / "state.json"
    result = _script(
        f'contract_atomic_publish "{_posix(target)}" \'{{"state":"initialized"}}\' && echo published'
    )
    assert result.returncode == 0
    assert "published" in result.stdout
    assert json.loads(target.read_text(encoding="utf-8")) == {"state": "initialized"}


def test_atomic_publish_leaves_no_temp_file(tmp_path):
    target = tmp_path / "state.json"
    result = _script(
        f'contract_atomic_publish "{_posix(target)}" \'{{"state":"initialized"}}\''
    )
    assert result.returncode == 0
    leftovers = [p.name for p in tmp_path.iterdir() if p.name != "state.json"]
    assert leftovers == []


# ── Activation gating (all gates) ──────────────────────────────────────────


def test_all_gates_ok_accepts_complete_set(tmp_path):
    gates = tmp_path / "gates"
    for gate in GATES:
        _write_attestation(gates, gate, "a" * 64)
    result = _script(
        f'contract_all_gates_ok "{_posix(gates)}" {"a" * 64} && echo ok'
    )
    assert result.returncode == 0
    assert "ok" in result.stdout


@pytest.mark.parametrize("missing", GATES)
def test_all_gates_ok_rejects_missing_gate(tmp_path, missing):
    gates = tmp_path / "gates"
    for gate in GATES:
        if gate != missing:
            _write_attestation(gates, gate, "a" * 64)
    result = _script(
        f'contract_all_gates_ok "{_posix(gates)}" {"a" * 64}'
    )
    assert result.returncode != 0
    assert f"missing attestation: {missing}" in result.stderr


def test_all_gates_ok_rejects_stale_plan_checksum(tmp_path):
    gates = tmp_path / "gates"
    for gate in GATES:
        _write_attestation(gates, gate, "a" * 64)
    result = _script(
        f'contract_all_gates_ok "{_posix(gates)}" {"b" * 64}'
    )
    assert result.returncode != 0
    assert "stale attestation" in result.stderr


# ── Secret-free blocked receipt ────────────────────────────────────────────


def test_blocked_receipt_is_redacted():
    result = _script(
        'contract_emit_blocked_receipt preflight "missing attestation: digests" || true'
    )
    payload = json.loads(result.stdout.strip())
    assert payload["blocked"] is True
    assert payload["counts"] is None
    assert payload["action"] == "preflight"
    for marker in SECRET_MARKERS:
        assert marker not in result.stdout.lower()


# ── Image digest validation (fail-closed) ──────────────────────────────────
#
# The production Compose resolves application artifacts by immutable
# ``@sha256:<digest>`` references. These primitives validate that an approved
# release digest is present and well-formed before any activation; a missing or
# malformed digest fails closed.


def test_image_digest_ok_accepts_well_formed():
    result = _script(f'contract_image_digest_ok "{"a" * 64}" && echo ok')
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_image_digest_ok_rejects_malformed():
    for bad in ("short", "A" * 64, "g" * 64, "z" * 64, "a" * 63, "a" * 65):
        result = _script(f'contract_image_digest_ok "{bad}"')
        assert result.returncode != 0, f"digest {bad!r} must be rejected"
        assert "malformed image digest" in result.stderr


def test_release_digests_ok_accepts_both_well_formed():
    result = _script(
        f'contract_release_digests_ok "{"a" * 64}" "{"b" * 64}" && echo ok'
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_release_digests_ok_rejects_malformed_frontend():
    result = _script(f'contract_release_digests_ok "{"a" * 64}" "short"')
    assert result.returncode != 0
    assert "malformed image digest" in result.stderr


def test_release_digests_ok_rejects_malformed_backend():
    result = _script(f'contract_release_digests_ok "not-a-digest" "{"b" * 64}"')
    assert result.returncode != 0
    assert "malformed image digest" in result.stderr


# ── Complete immutable release manifest ─────────────────────────────────────
#
# The release ``SHA256SUMS`` must cover every artifact the release claims and
# every entry must verify against the actual file content, binding each
# artifact's digest to its canonical content rather than a well-formed 64-hex
# placeholder.


RELEASE_ARTIFACTS = ("plan.json", "compose.yml", "control-manifest.schema.json", "README.md")


def _write_release(release_dir: Path, *, omit_checksum_for: str | None = None) -> None:
    release_dir.mkdir(parents=True, exist_ok=True)
    contents = {
        "plan.json": '{"plan_sha256":"' + "a" * 64 + '"}',
        "compose.yml": "services: {}\n",
        "control-manifest.schema.json": '{"type":"object"}\n',
        "README.md": "# release\n",
    }
    for name, text in contents.items():
        # LF endings so GNU ``sha256sum -c`` parses the manifest on Windows/CRLF
        # hosts without mistaking a trailing ``\r`` for part of the filename.
        (release_dir / name).write_text(text, encoding="utf-8", newline="\n")
    lines = []
    for name in RELEASE_ARTIFACTS:
        if name == omit_checksum_for:
            continue
        digest = hashlib.sha256((release_dir / name).read_bytes()).hexdigest()
        lines.append(f"{digest}  {name}")
    (release_dir / "SHA256SUMS").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def test_release_manifest_ok_accepts_complete_manifest(tmp_path):
    release = tmp_path / "release"
    _write_release(release)
    result = _script(f'contract_release_manifest_ok "{_posix(release)}" && echo ok')
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_release_manifest_ok_rejects_missing_artifact(tmp_path):
    release = tmp_path / "release"
    _write_release(release)
    (release / "compose.yml").unlink()
    result = _script(f'contract_release_manifest_ok "{_posix(release)}"')
    assert result.returncode != 0
    assert "missing artifact: compose.yml" in result.stderr


def test_release_manifest_ok_rejects_missing_checksum_entry(tmp_path):
    release = tmp_path / "release"
    _write_release(release, omit_checksum_for="README.md")
    result = _script(f'contract_release_manifest_ok "{_posix(release)}"')
    assert result.returncode != 0
    assert "missing checksum entry: README.md" in result.stderr


def test_release_manifest_ok_rejects_checksum_mismatch(tmp_path):
    release = tmp_path / "release"
    _write_release(release)
    (release / "README.md").write_text("# tampered\n", encoding="utf-8")
    result = _script(f'contract_release_manifest_ok "{_posix(release)}"')
    assert result.returncode != 0
    assert "checksum mismatch" in result.stderr


# ── Apply-mode digest + manifest gate (dispatch wiring) ─────────────────────


def test_apply_gates_ok_accepts_complete_digests_and_manifest(tmp_path):
    release = tmp_path / "release"
    _write_release(release)
    result = _script(
        f'BACKEND_IMAGE_DIGEST="{"a" * 64}" FRONTEND_IMAGE_DIGEST="{"b" * 64}" '
        f'DDBB_RELEASE_DIR="{_posix(release)}" contract_apply_gates_ok && echo ok'
    )
    assert result.returncode == 0, result.stderr
    assert "ok" in result.stdout


def test_apply_gates_ok_rejects_missing_digest():
    result = _script("contract_apply_gates_ok")
    assert result.returncode != 0
    assert "malformed image digest" in result.stderr
