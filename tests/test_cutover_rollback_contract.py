"""Phase 4 — cutover/rollback wrapper contract (RED suite).

Specifies the credential-free ``ops/cutover`` and ``ops/rollback`` wrappers that
task 4.2 will implement under explicit operator approval. The wrapper behaviors
mirror the existing ``ops/*`` contract:

  * allowlisting — ``cutover``/``rollback`` are the only new executable actions;
  * dry-run-first — the default mode performs no Compose write;
  * credential-free — secret-like arguments are refused before any invocation;
  * blocked propagation — a blocked rollback/cutover exits non-zero;
  * delegation — ``--apply`` reaches the backend adapter via ``store-operation``.

This suite is RED on purpose: ``ops/cutover`` and ``ops/rollback`` do not exist
yet, and neither action is allowlisted. When task 4.2 lands under approval, these
tests turn GREEN. No VPS, live data, credential, volume, backup, or cutover is
touched here — every test runs against a fake ``docker compose`` and dry-run
defaults.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
OPS_DIR = REPO / "ops"
CONTRACT_LIB = OPS_DIR / "lib" / "operation-contract.sh"


# ── Bash resolution (Git for Windows) ─────────────────────────────────────


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


def _source(expr: str) -> subprocess.CompletedProcess:
    lib = _posix(CONTRACT_LIB)
    return subprocess.run(
        [BASH, "-c", f'. "{lib}"; {expr}'],
        capture_output=True,
        text=True,
        cwd=str(REPO),
    )


def _run_ops(action: str, *args: str, env: dict | None = None):
    script = _posix(OPS_DIR / action)
    full_env = os.environ.copy()
    full_env.update(env or {})
    return subprocess.run(
        [BASH, script, *args],
        capture_output=True,
        text=True,
        env=full_env,
        cwd=str(REPO),
    )


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def fake_compose(tmp_path):
    fake = tmp_path / "fake-docker"
    log = tmp_path / "compose.log"
    fake.write_text(
        "#!/bin/sh\n"
        'if [ -n "$FAKE_LOG" ]; then printf \'%s\\n\' "$@" >> "$FAKE_LOG"; fi\n'
        'if [ -n "$FAKE_RESULT" ]; then printf \'%s\\n\' "$FAKE_RESULT"; fi\n'
        'exit "${FAKE_EXIT:-0}"\n',
        encoding="utf-8",
    )
    os.chmod(fake, 0o755)
    return {"bin": _posix(fake), "log": log, "dir": tmp_path}


def _compose_env(fake_compose, *, result: str | None = None, exit_code: int = 0):
    env = {
        "DOCKER_COMPOSE_BIN": fake_compose["bin"],
        "FAKE_LOG": _posix(fake_compose["log"]),
    }
    if result is not None:
        env["FAKE_RESULT"] = result
    env["FAKE_EXIT"] = str(exit_code)
    return env


# ── Allowlisting ──────────────────────────────────────────────────────────


@pytest.mark.parametrize("action", ["cutover", "rollback"])
def test_cutover_rollback_are_allowlisted(action):
    result = _source(f'contract_validate_action "{action}"')
    assert result.returncode == 0, result.stderr


# ── Dry-run first ─────────────────────────────────────────────────────────


def test_rollback_dry_run_default_does_not_invoke_compose(fake_compose):
    result = _run_ops("rollback", "--store", "identity", env=_compose_env(fake_compose))
    assert result.returncode == 0
    assert not fake_compose["log"].exists(), "compose was invoked in dry-run"


def test_cutover_dry_run_default_does_not_invoke_compose(fake_compose):
    result = _run_ops("cutover", "--store", "identity", env=_compose_env(fake_compose))
    assert result.returncode == 0
    assert not fake_compose["log"].exists(), "compose was invoked in dry-run"


# ── Delegation + blocked propagation ──────────────────────────────────────


def test_rollback_apply_invokes_store_operation(fake_compose):
    canned = (
        '{"action":"rollback","dry_run":false,"plan_checksum":"abc",'
        '"counts":{"authority":"legacy","new_store_writes_enabled":false},'
        '"blocked":false}'
    )
    result = _run_ops(
        "rollback", "--apply", "--store", "identity",
        env=_compose_env(fake_compose, result=canned),
    )
    assert result.returncode == 0
    assert fake_compose["log"].exists()
    assert "store-operation" in fake_compose["log"].read_text(encoding="utf-8")
    assert json.loads(result.stdout.strip())["blocked"] is False


def test_rollback_blocks_nonzero_on_blocked_result(fake_compose):
    canned = (
        '{"action":"rollback","dry_run":false,"plan_checksum":"abc",'
        '"counts":{"authority":"legacy"},"blocked":true}'
    )
    result = _run_ops(
        "rollback", "--apply", "--store", "identity",
        env=_compose_env(fake_compose, result=canned),
    )
    assert result.returncode != 0
    assert json.loads(result.stdout.strip())["blocked"] is True


def test_cutover_blocks_nonzero_on_blocked_result(fake_compose):
    canned = (
        '{"action":"cutover","dry_run":false,"plan_checksum":"abc",'
        '"counts":{"authority":"isolated"},"blocked":true}'
    )
    result = _run_ops(
        "cutover", "--apply", "--store", "identity",
        env=_compose_env(fake_compose, result=canned),
    )
    assert result.returncode != 0
    assert json.loads(result.stdout.strip())["blocked"] is True


# ── Credential-free ───────────────────────────────────────────────────────


@pytest.mark.parametrize("action", ["cutover", "rollback"])
def test_secret_argument_rejected_before_compose(fake_compose, action):
    result = _run_ops(
        action, "--apply", "--store", "identity", "--password=hunter2",
        env=_compose_env(fake_compose, result='{"blocked":false}'),
    )
    assert result.returncode != 0
    # The rejection must be the secret guard, not a missing wrapper.
    assert "secret" in (result.stdout + result.stderr).lower()
    assert not fake_compose["log"].exists(), "compose ran despite a secret argument"
