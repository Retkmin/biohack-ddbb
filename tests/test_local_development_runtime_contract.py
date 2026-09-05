"""Structural contracts for the persistent local PostgreSQL development replica."""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
COMPOSE = REPO / "docker-compose.local-development.yml"
TEMPLATE = REPO / "config" / "local-development-postgres.template"
OPERATOR_TEMPLATE = REPO / "ops" / "operator-access.template"
OPERATOR_RUNBOOK = REPO / "docs" / "private-operator-access.md"


def test_local_development_replica_uses_two_loopback_postgres_stores():
    services = yaml.safe_load(COMPOSE.read_text(encoding="utf-8"))["services"]
    expected = {
        "identity-postgres": "127.0.0.1:54321:5432",
        "domain-postgres": "127.0.0.1:54322:5432",
    }

    for name, port in expected.items():
        service = services[name]
        assert service["image"] == "postgres:15.12-alpine"
        assert service["ports"] == [port]
        assert service["healthcheck"]


def test_local_development_template_is_non_production_and_complete():
    template = TEMPLATE.read_text(encoding="utf-8")
    assert "ENVIRONMENT=" not in template
    for key in (
        "IDENTITY_POSTGRES_USER",
        "IDENTITY_POSTGRES_PASSWORD",
        "IDENTITY_POSTGRES_DB",
        "DOMAIN_POSTGRES_USER",
        "DOMAIN_POSTGRES_PASSWORD",
        "DOMAIN_POSTGRES_DB",
    ):
        assert f"{key}=" in template


def test_operator_access_remains_unprovisioned_and_has_no_public_database_route():
    template = OPERATOR_TEMPLATE.read_text(encoding="utf-8")
    runbook = OPERATOR_RUNBOOK.read_text(encoding="utf-8")
    assert "OPERATOR_TARGET=UNSET" in template
    assert "OPERATOR_ROUTE=UNPROVISIONED" in template
    assert "127.0.0.1" in template
    assert "postgresql://" not in template.casefold()
    assert "no generic `ssh -l` command" in runbook.casefold()
    assert "public postgresql mapping" in runbook.casefold()
