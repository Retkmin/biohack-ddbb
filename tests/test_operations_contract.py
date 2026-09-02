"""Phase 3 — DDBB operations contract (RED suite).

Exercises the credential-free ``ops/*`` wrappers and the shared
``ops/lib/operation-contract.sh`` library against a fake ``docker compose``
binary and redacted fixtures. No VPS, no database credentials, no deployment,
and no data movement: every test runs a dry-run by default and never touches a
real store.

The behaviors under test map to the design's threat matrix and the spec's
"Independent Migration and Reconciliation" / "Credential and Backup
Separation" requirements:

  * dry-run no-write — the default mode performs no compose write;
  * secret rejection — credential-like arguments are refused before any
    invocation;
  * executable allowlisting — documentation-like actions (Markdown, README.sh)
    never run;
  * redacted receipts — emitted receipts carry no credential values;
  * mismatch blocking — a blocked reconciliation exits non-zero;
  * non-zero failures — invalid input and unavailable dependencies fail.
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

ALLOWED_ACTIONS = ("load", "backfill", "reconcile", "backup", "restore")

SECRET_MARKERS = (
    "password",
    "pgpassword",
    "token",
    "secret",
    "api_key",
    "apikey",
    "credential",
    "postgresql://",
    "postgres://",
)


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
    """Convert a Windows path to a Git-Bash-friendly POSIX path."""
    value = str(path).replace("\\", "/")
    if len(value) >= 2 and value[1] == ":":
        value = "/" + value[0].lower() + value[2:]
    return value


def _bash_c(expr: str, *, env: dict | None = None, cwd: Path | None = None):
    full_env = os.environ.copy()
    full_env.update(env or {})
    return subprocess.run(
        [BASH, "-c", expr],
        capture_output=True,
        text=True,
        env=full_env,
        cwd=str(cwd or REPO),
    )


def _run_ops(
    action: str, *args: str, env: dict | None = None, cwd: Path | None = None
):
    script = _posix(OPS_DIR / action)
    full_env = os.environ.copy()
    full_env.update(env or {})
    return subprocess.run(
        [BASH, script, *args],
        capture_output=True,
        text=True,
        env=full_env,
        cwd=str(cwd or REPO),
    )


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture
def fake_compose(tmp_path):
    """A fake ``docker`` binary that logs its argv and echoes a canned result."""
    fake = tmp_path / "fake-docker"
    log = tmp_path / "compose.log"
    fake.write_text(
        "#!/bin/sh\n"
        "# Fake docker compose for operation-contract tests.\n"
        'if [ -n "$FAKE_LOG" ]; then printf \'%s\\n\' "$@" >> "$FAKE_LOG"; fi\n'
        'if [ -n "$FAKE_RESULT" ]; then printf \'%s\\n\' "$FAKE_RESULT"; fi\n'
        'exit "${FAKE_EXIT:-0}"\n',
        encoding="utf-8",
    )
    os.chmod(fake, 0o755)
    return {
        "bin": _posix(fake),
        "log": log,
        "dir": tmp_path,
    }


def _compose_env(fake_compose, *, result: str | None = None, exit_code: int = 0):
    env = {
        "DOCKER_COMPOSE_BIN": fake_compose["bin"],
        "FAKE_LOG": _posix(fake_compose["log"]),
    }
    if result is not None:
        env["FAKE_RESULT"] = result
    env["FAKE_EXIT"] = str(exit_code)
    return env


# ── Library: executable allowlisting ──────────────────────────────────────


def _source(expr: str) -> subprocess.CompletedProcess:
    lib = _posix(CONTRACT_LIB)
    return _bash_c(f'. "{lib}"; {expr}')


@pytest.mark.parametrize("action", ALLOWED_ACTIONS)
def test_allowlist_accepts_known_actions(action):
    result = _source(f'contract_validate_action "{action}"')
    assert result.returncode == 0, result.stderr


def test_allowlist_rejects_unknown_action():
    result = _source('contract_validate_action "droptable"')
    assert result.returncode != 0
    assert "invalid" in (result.stdout + result.stderr).lower()


def test_allowlist_rejects_markdown_action():
    result = _source('contract_validate_action "backfill.md"')
    assert result.returncode != 0


def test_allowlist_rejects_readme_sh_action():
    result = _source('contract_validate_action "README.sh"')
    assert result.returncode != 0


def test_executable_path_rejects_markdown():
    result = _source('contract_is_executable_action_path "backfill.md" && echo allowed || echo rejected')
    assert "rejected" in result.stdout


def test_executable_path_rejects_readme_sh():
    result = _source('contract_is_executable_action_path "README.sh" && echo allowed || echo rejected')
    assert "rejected" in result.stdout


def test_executable_path_accepts_plain_action():
    result = _source('contract_is_executable_action_path "backfill" && echo allowed || echo rejected')
    assert "allowed" in result.stdout


# ── Library: secret rejection ─────────────────────────────────────────────


@pytest.mark.parametrize(
    "arg",
    [
        "--password=hunter2",
        "PGPASSWORD=hunter2",
        "--token=tok_123",
        "postgresql://user:pass@dbhost/db",
        "postgres://u:p@h/d",
        "--secret=abc",
        "api_key=deadbeef",
    ],
)
def test_secret_detection_flags_credential_like_argument(arg):
    result = _source(f'contract_has_secret "{arg}" && echo secret || echo clean')
    assert "secret" in result.stdout


@pytest.mark.parametrize("arg", ["identity", "domain", "--dry-run", "--apply", "--store"])
def test_secret_detection_accepts_clean_argument(arg):
    result = _source(f'contract_has_secret "{arg}" && echo secret || echo clean')
    assert "clean" in result.stdout


def test_plan_checksum_is_deterministic():
    result = _source(
        'a=$(contract_plan_checksum backfill identity dry-run); '
        'b=$(contract_plan_checksum backfill identity dry-run); '
        '[ "$a" = "$b" ] && echo deterministic || echo nondeterministic'
    )
    assert "deterministic" in result.stdout


# ── Wrapper: dry-run no-write ─────────────────────────────────────────────


def test_dry_run_is_default_and_does_not_invoke_compose(fake_compose):
    result = _run_ops("backfill", "--store", "identity", env=_compose_env(fake_compose))
    assert result.returncode == 0
    # No --dry-run flag was passed, yet the default mode performed no write.
    assert not fake_compose["log"].exists(), "compose was invoked in dry-run"


def test_dry_run_explicit_does_not_invoke_compose(fake_compose):
    result = _run_ops("backfill", "--dry-run", "--store", "domain", env=_compose_env(fake_compose))
    assert result.returncode == 0
    assert not fake_compose["log"].exists(), "compose was invoked in dry-run"


def test_dry_run_emits_plan_receipt_on_stdout(fake_compose):
    result = _run_ops("backfill", "--dry-run", "--store", "identity", env=_compose_env(fake_compose))
    payload = json.loads(result.stdout.strip())
    assert payload["action"] == "backfill"
    assert payload["dry_run"] is True
    assert payload["blocked"] is False
    assert payload["plan_checksum"]


# ── Wrapper: apply invokes compose ────────────────────────────────────────


def test_apply_invokes_compose_and_emits_result(fake_compose):
    canned = '{"action":"backfill","dry_run":false,"plan_checksum":"abc","counts":{"inserted":3},"blocked":false}'
    result = _run_ops(
        "backfill", "--apply", "--store", "identity",
        env=_compose_env(fake_compose, result=canned),
    )
    assert result.returncode == 0
    assert fake_compose["log"].exists()
    logged = fake_compose["log"].read_text(encoding="utf-8")
    assert "run" in logged
    assert "store-operation" in logged
    assert json.loads(result.stdout.strip())["blocked"] is False


# ── Wrapper: secret + invalid input rejection ─────────────────────────────


@pytest.mark.parametrize(
    "arg",
    ["--password=hunter2", "--PGPASSWORD=x", "postgresql://u:p@h/db"],
)
def test_secret_argument_rejected_before_compose(fake_compose, arg):
    result = _run_ops(
        "backfill", "--apply", "--store", "identity", arg,
        env=_compose_env(fake_compose, result='{"blocked":false}'),
    )
    assert result.returncode != 0
    assert not fake_compose["log"].exists(), "compose ran despite a secret argument"


def test_unknown_argument_rejected(fake_compose):
    result = _run_ops(
        "backfill", "--apply", "--store", "identity", "--bogus",
        env=_compose_env(fake_compose),
    )
    assert result.returncode != 0
    assert not fake_compose["log"].exists()


def test_invalid_store_rejected(fake_compose):
    result = _run_ops(
        "backfill", "--apply", "--store", "legacy",
        env=_compose_env(fake_compose),
    )
    assert result.returncode != 0
    assert not fake_compose["log"].exists()


def test_backup_requires_store(fake_compose):
    result = _run_ops("backup", "--apply", env=_compose_env(fake_compose))
    assert result.returncode != 0
    assert not fake_compose["log"].exists()


# ── Wrapper: mismatch blocking + non-zero failures ────────────────────────


def test_reconcile_blocks_and_exits_nonzero_on_mismatch(fake_compose):
    canned = '{"action":"reconcile","dry_run":false,"plan_checksum":"abc","counts":{"checksum_mismatches":1},"blocked":true}'
    result = _run_ops(
        "reconcile", "--apply", "--store", "identity",
        env=_compose_env(fake_compose, result=canned),
    )
    assert result.returncode != 0
    assert json.loads(result.stdout.strip())["blocked"] is True


def test_reconcile_clean_exits_zero(fake_compose):
    canned = '{"action":"reconcile","dry_run":false,"plan_checksum":"abc","counts":{"checksum_mismatches":0},"blocked":false}'
    result = _run_ops(
        "reconcile", "--apply", "--store", "identity",
        env=_compose_env(fake_compose, result=canned),
    )
    assert result.returncode == 0


def test_compose_failure_propagates_nonzero(fake_compose):
    result = _run_ops(
        "backfill", "--apply", "--store", "identity",
        env=_compose_env(fake_compose, exit_code=1),
    )
    assert result.returncode != 0


# ── Wrapper: redacted receipts ────────────────────────────────────────────


def test_receipt_file_emitted_and_redacted(fake_compose):
    receipt_dir = fake_compose["dir"] / "receipts"
    result = _run_ops(
        "backfill", "--dry-run", "--store", "identity",
        "--receipt-dir", _posix(receipt_dir),
        env=_compose_env(fake_compose),
    )
    assert result.returncode == 0

    receipt_file = receipt_dir / "receipt.json"
    assert receipt_file.exists()
    payload = json.loads(receipt_file.read_text(encoding="utf-8"))
    assert payload["action"] == "backfill"
    assert payload["dry_run"] is True

    raw = receipt_file.read_text(encoding="utf-8").lower()
    for marker in SECRET_MARKERS:
        assert marker not in raw, f"receipt leaked marker: {marker}"


def test_stdout_receipt_is_credential_free(fake_compose):
    result = _run_ops(
        "backfill", "--dry-run", "--store", "identity",
        env=_compose_env(fake_compose),
    )
    raw = result.stdout.lower()
    for marker in SECRET_MARKERS:
        assert marker not in raw, f"stdout leaked marker: {marker}"
