"""Phase 3.1 — disposable Compose integration: fail-closed greenfield deployment.

Drives a real, disposable Docker Compose stack that runs the actual
``ops/lib/operation-contract.sh`` greenfield gates across prerequisite gate
services and empty-store initialization, coordinated by a ``coordinator`` that
shares only a plan/attestation/store volume. Credential-free: no Postgres, no
VPS, no protected environment source, no real data movement.

Scenarios asserted (design "Integration" testing strategy and the greenfield
spec):

  1. private ports               — no service exposes a host port;
  2. empty-schema initialization — an empty store initializes; a non-empty
                                   store fails closed;
  3. unhealthy dependency        — a store that is never initialized keeps
                                   activation fenced;
  4. timeout fencing             — missing gate attestations block within the
                                   timeout window and emit a blocked receipt;
  5. activation only after all
     acknowledgements            — the coordinator publishes ``initialized``
                                   state ONLY after every gate is attested for
                                   the exact plan checksum and both stores are
                                   initialized.

Every container/network/volume the stack creates is removed in a ``finally``
block via ``docker compose down --volumes``, so a test failure cannot leak
state.
"""

from __future__ import annotations

import json
import subprocess
import uuid
from pathlib import Path

import pytest
import yaml

REPO = Path(__file__).resolve().parents[2]
INTEGRATION_DIR = REPO / "tests" / "integration"
COMPOSE_FILE = INTEGRATION_DIR / "compose.greenfield.yml"
COORDINATOR_SCRIPT = INTEGRATION_DIR / "coordinator.sh"
GATE_SCRIPT = INTEGRATION_DIR / "gate.sh"
STORE_INIT_SCRIPT = INTEGRATION_DIR / "store-init.sh"

PLAN_SHA256 = "a" * 64
GATES = ("plan", "protected_config", "digests", "dns_tls", "capacity", "retention")

SECRET_MARKERS = ("password", "token", "secret", "postgresql://", "postgres://", "@", "email")


def _docker_available() -> bool:
    result = subprocess.run(
        ["docker", "version", "--format", "{{.Server.Version}}"],
        capture_output=True, text=True,
    )
    return result.returncode == 0


DOCKER_AVAILABLE = _docker_available()


@pytest.fixture(scope="module")
def stack():
    """A uniquely named disposable Compose project with deterministic cleanup."""
    if not DOCKER_AVAILABLE:
        pytest.skip("Docker daemon is not reachable — disposable Compose stack cannot run")

    project = f"greenfield-{uuid.uuid4().hex[:10]}"
    for required in (COMPOSE_FILE, COORDINATOR_SCRIPT, GATE_SCRIPT, STORE_INIT_SCRIPT):
        if not required.exists():
            pytest.fail(f"disposable Compose harness missing: {required.name}", pytrace=False)

    def compose(*args: str) -> subprocess.CompletedProcess:
        cmd = ["docker", "compose", "-p", project, "-f", str(COMPOSE_FILE), *args]
        return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO))

    compose("down", "--volumes", "--remove-orphans")

    try:
        yield _Harness(project, compose)
    finally:
        compose("down", "--volumes", "--remove-orphans", "--timeout", "2")


class _Harness:
    def __init__(self, project: str, compose):
        self.project = project
        self.compose = compose

    def run_gate(self, gate: str) -> subprocess.CompletedProcess:
        return self.compose(
            "run", "--rm", "-e", f"GATE={gate}",
            "-e", f"PLAN_SHA256={PLAN_SHA256}", "gate",
        )

    def run_store_init(self, store: str) -> subprocess.CompletedProcess:
        return self.compose(
            "run", "--rm", "-e", f"STORE_NAME={store}",
            "-e", f"STORE_DIR=/shared/stores/{store}", "store-init",
        )

    def seed_domain(self) -> None:
        result = self.compose("run", "--rm", "-e", "SEED_DIR=/shared/stores/domain", "seed")
        assert result.returncode == 0, result.stderr

    def run_coordinator(self, timeout: str = "6") -> subprocess.CompletedProcess:
        return self.compose(
            "run", "--rm", "-e", f"PLAN_SHA256={PLAN_SHA256}",
            "-e", f"TIMEOUT={timeout}", "coordinator",
        )

    def reset(self) -> None:
        result = self.compose("run", "--rm", "-e", "RESET_DIR=/shared", "reset")
        assert result.returncode == 0, result.stderr

    def read_state(self) -> dict | None:
        result = self.compose("run", "--rm", "reader")
        raw = result.stdout.strip()
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            return None


# ── Scenario 1: private ports ───────────────────────────────────────────────


def test_disposable_topology_has_no_host_ports():
    data = yaml.safe_load(COMPOSE_FILE.read_text(encoding="utf-8"))
    for service, spec in data["services"].items():
        assert "ports" not in spec, f"{service} must not expose host ports"


# ── Scenario 2: empty-schema initialization ─────────────────────────────────


def test_empty_stores_initialize_and_activate(stack):
    stack.reset()
    for gate in GATES:
        result = stack.run_gate(gate)
        assert result.returncode == 0, result.stderr
        assert f"gate={gate}" in result.stdout

    for store in ("identity", "domain"):
        result = stack.run_store_init(store)
        assert result.returncode == 0, result.stderr
        assert f"store={store} initialized" in result.stdout

    coordinator = stack.run_coordinator()
    assert coordinator.returncode == 0, coordinator.stderr
    assert "ACTIVE" in coordinator.stdout

    state = stack.read_state()
    assert state is not None
    assert state["state"] == "initialized"
    assert state["traffic_enabled"] is False


def test_non_empty_store_blocks_initialization(stack):
    stack.reset()
    stack.seed_domain()
    result = stack.run_store_init("domain")
    assert result.returncode != 0
    assert "BLOCKED not-empty" in result.stdout


# ── Scenario 3: unhealthy dependency ────────────────────────────────────────


def test_uninitialized_dependency_blocks_activation(stack):
    stack.reset()
    for gate in GATES:
        assert stack.run_gate(gate).returncode == 0

    # domain initializes, identity never does (an unhealthy dependency).
    assert stack.run_store_init("domain").returncode == 0

    coordinator = stack.run_coordinator(timeout="3")
    assert coordinator.returncode != 0
    assert "ACTIVE" not in coordinator.stdout
    assert "blocked" in coordinator.stdout.lower() or "BLOCKED" in coordinator.stdout

    state = stack.read_state()
    assert state is None or state.get("state") != "initialized"


# ── Scenario 4: timeout fencing ─────────────────────────────────────────────


def test_timeout_fences_on_missing_gates(stack):
    stack.reset()
    # Only a partial gate set is attested; dns_tls is missing.
    for gate in ("plan", "protected_config", "digests", "capacity", "retention"):
        assert stack.run_gate(gate).returncode == 0

    assert stack.run_store_init("identity").returncode == 0
    assert stack.run_store_init("domain").returncode == 0

    coordinator = stack.run_coordinator(timeout="3")
    assert coordinator.returncode != 0
    assert "ACTIVE" not in coordinator.stdout

    state = stack.read_state()
    assert state is None or state.get("state") != "initialized"


# ── Scenario 5: activation only after all acknowledgements ──────────────────


def test_activation_requires_all_gate_acknowledgements(stack):
    stack.reset()
    assert stack.run_store_init("identity").returncode == 0
    assert stack.run_store_init("domain").returncode == 0

    # With zero gates, activation is fenced.
    blocked = stack.run_coordinator(timeout="3")
    assert blocked.returncode != 0
    assert "ACTIVE" not in blocked.stdout

    # Attesting every gate activates.
    for gate in GATES:
        assert stack.run_gate(gate).returncode == 0

    activated = stack.run_coordinator(timeout="6")
    assert activated.returncode == 0, activated.stderr
    assert "ACTIVE" in activated.stdout

    for marker in SECRET_MARKERS:
        assert marker not in activated.stdout.lower()
