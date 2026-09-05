"""Phase 2.3 — greenfield VPS production topology structural contract.

Proves the `deploy/production/compose.yml` topology satisfies the design's
greenfield network/database boundary and read-only plan/receipt decisions:

  * separate identity/domain stores and volumes — the two scoped PostgreSQL
    services own distinct named volumes and join distinct private networks;
  * private DB networks — ``internal``, ``identity``, and ``domain`` are
    private (``internal: true``);
  * Caddy-only host ports — only Caddy exposes host ports (80/443), no other
    service has ``ports``;
  * ``store-operation`` joins BOTH database networks (``identity`` and
    ``domain``) and mounts the deployment plan and receipts read-only.

Structural and environment-free: it parses the Compose file with PyYAML and
asserts the declared topology; it performs no Docker, database, credential, or
VPS action.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
COMPOSE = REPO / "deploy" / "production" / "compose.yml"


def _compose() -> dict:
    return yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))


def test_compose_parses_as_mapping():
    data = _compose()
    assert isinstance(data, dict)
    assert "services" in data
    assert "networks" in data
    assert "volumes" in data


def test_separate_identity_and_domain_stores_and_volumes():
    data = _compose()
    services = data["services"]
    volumes = data["volumes"]
    for name, volume in (("identity-postgres", "identity_postgres_data"), ("domain-postgres", "domain_postgres_data")):
        assert name in services, f"missing {name} service"
        assert volume in volumes, f"missing {volume} volume"
        mounts = [str(v) for v in services[name].get("volumes", [])]
        assert any(v == volume or v.startswith(volume + ":") for v in mounts), (
            f"{name} must mount {volume}"
        )


def test_database_and_internal_networks_are_private():
    data = _compose()
    networks = data["networks"]
    for name in ("internal", "identity", "domain"):
        assert name in networks
        assert networks[name].get("internal") is True, f"{name} must be internal"


def test_only_caddy_exposes_host_ports():
    data = _compose()
    for service, spec in data["services"].items():
        if service == "caddy":
            assert spec.get("ports") == ["80:80", "443:443"]
        else:
            assert "ports" not in spec, f"{service} must not expose host ports"


def test_store_operation_joins_both_database_networks():
    data = _compose()
    store = data["services"]["store-operation"]
    assert "identity" in store.get("networks", [])
    assert "domain" in store.get("networks", [])


def test_plan_and_receipt_mounts_are_read_only():
    data = _compose()
    store = data["services"]["store-operation"]
    bind_mounts = [v for v in store.get("volumes", []) if isinstance(v, dict)]
    assert len(bind_mounts) == 2
    for mount in bind_mounts:
        assert mount.get("type") == "bind"
    # The plan mount stays read-only; the receipts mount is writable so a
    # successful preflight can atomically persist its non-empty receipt.
    by_target = {m["target"]: m for m in bind_mounts}
    assert by_target["/var/lib/sam/plan"]["read_only"] is True
    assert "read_only" not in by_target["/var/lib/sam/receipts"]
    targets = sorted(m["target"] for m in bind_mounts)
    assert targets == ["/var/lib/sam/plan", "/var/lib/sam/receipts"]


def test_store_operation_receives_plan_path_env():
    data = _compose()
    store = data["services"]["store-operation"]
    env = store.get("environment", {})
    assert "DEPLOYMENT_PLAN_PATH" in env
    assert env["DEPLOYMENT_PLAN_PATH"] == "${DEPLOYMENT_PLAN_PATH:-/var/lib/sam/plan/plan.json}"


def test_store_operation_has_no_legacy_manifest_env():
    data = _compose()
    store = data["services"]["store-operation"]
    env = store.get("environment", {})
    assert "CONTROL_MANIFEST_PATH" not in env


def test_store_operation_runs_as_vps_owner_pid():
    # The plan/receipt bind mounts are owner-only (0700/0600) on the VPS owner
    # account. The sealed image's non-root ``appuser`` (uid 1000) differs from
    # the VPS owner uid (1001), so the container must be pinned to the owner
    # uid:gid to read the mounts without weakening the 0700 owner-only boundary.
    data = _compose()
    store = data["services"]["store-operation"]
    assert store.get("user") == "1001:1001", (
        "store-operation must run as the VPS owner uid:gid to read owner-only mounts"
    )


def test_store_operation_receives_receipt_path_env():
    data = _compose()
    store = data["services"]["store-operation"]
    env = store.get("environment", {})
    assert "OPERATION_RECEIPT_PATH" in env
    assert env["OPERATION_RECEIPT_PATH"] == "${OPERATION_RECEIPT_PATH:-/var/lib/sam/receipts/preflight.json}"


def test_store_operation_receives_health_evidence_path_env():
    # activate must read real persisted health evidence; the store-operation
    # service exposes the health attestation path so the adapter can gate
    # activation on a persisted health/smoke attestation.
    data = _compose()
    store = data["services"]["store-operation"]
    env = store.get("environment", {})
    assert "HEALTH_EVIDENCE_PATH" in env
    assert env["HEALTH_EVIDENCE_PATH"] == "${HEALTH_EVIDENCE_PATH:-/var/lib/sam/receipts/health.attestation.json}"


def test_store_operation_receipts_mount_is_writable():
    # The preflight receipt must be persisted atomically, so the receipts mount
    # is writable (unlike the immutable plan mount, which stays read-only).
    data = _compose()
    store = data["services"]["store-operation"]
    bind_mounts = {m["target"]: m for m in store.get("volumes", []) if isinstance(m, dict)}
    assert "read_only" not in bind_mounts["/var/lib/sam/receipts"], (
        "receipts mount must be writable so preflight can persist its receipt"
    )


# ── Post-verify correction: combined-store routing + mutable build contexts ──
#
# The verify report rejected the production Compose because it still routed
# core services through the legacy combined ``postgres`` store and resolved
# application artifacts from mutable ``build`` contexts. These tests pin the
# corrected topology: no combined store, scoped identity/domain routing, and
# digest-pinned image references only.

BACKEND_SERVICES = ("api", "worker", "beat", "migration", "store-operation")
FRONTEND_SERVICES = ("caddy",)
APP_SERVICES = ("api", "worker", "beat")


def test_no_legacy_combined_store_service():
    data = _compose()
    assert "postgres" not in data["services"]


def test_no_legacy_combined_store_volume():
    data = _compose()
    assert "postgres_data" not in data["volumes"]


def test_app_services_depend_on_scoped_stores():
    data = _compose()
    for service in APP_SERVICES:
        deps = set(data["services"][service].get("depends_on", {}))
        assert "postgres" not in deps, f"{service} must not depend on legacy postgres"
        assert {"identity-postgres", "domain-postgres"} <= deps, (
            f"{service} must depend on both scoped stores"
        )


def test_app_services_join_scoped_database_networks():
    data = _compose()
    for service in APP_SERVICES:
        networks = set(data["services"][service].get("networks", []))
        assert {"identity", "domain"} <= networks, (
            f"{service} must join the identity and domain networks"
        )


def test_app_services_use_scoped_store_urls():
    data = _compose()
    for service in APP_SERVICES:
        env = data["services"][service].get("environment", {})
        assert "DATABASE_URL" not in env, f"{service} must not use the combined DATABASE_URL"
        assert "IDENTITY_DATABASE_URL" in env, f"{service} must declare IDENTITY_DATABASE_URL"
        assert "DOMAIN_DATABASE_URL" in env, f"{service} must declare DOMAIN_DATABASE_URL"


def test_no_mutable_build_contexts():
    data = _compose()
    for service, spec in data["services"].items():
        assert "build" not in spec, f"{service} must not use a mutable build context"


def test_deployable_services_use_digest_pinned_images():
    data = _compose()
    for service in BACKEND_SERVICES:
        image = data["services"][service]["image"]
        assert "@sha256:${BACKEND_IMAGE_DIGEST:?required}" in image, (
            f"{service} must be digest-pinned to BACKEND_IMAGE_DIGEST"
        )
    for service in FRONTEND_SERVICES:
        image = data["services"][service]["image"]
        assert "@sha256:${FRONTEND_IMAGE_DIGEST:?required}" in image, (
            f"{service} must be digest-pinned to FRONTEND_IMAGE_DIGEST"
        )


def test_migration_runs_both_scoped_histories():
    data = _compose()
    command = data["services"]["migration"]["command"]
    joined = " ".join(command)
    assert "-n identity" in joined, "migration must run the identity history"
    assert "-n domain" in joined, "migration must run the domain history"
    assert "upgrade head" in joined
