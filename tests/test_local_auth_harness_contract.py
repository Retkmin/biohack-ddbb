"""Structural contract for the local-only isolated auth harness.

These checks parse configuration only. They never start Docker, connect to a
database, or read deployment configuration.
"""

from __future__ import annotations

from pathlib import Path

import yaml

REPO = Path(__file__).resolve().parents[1]
LOCAL_COMPOSE = REPO / "docker-compose.local-test.yml"
LOCAL_ENV_TEMPLATE = REPO / "local-test.env.template"


def _local_compose() -> dict:
    return yaml.safe_load(LOCAL_COMPOSE.read_text(encoding="utf-8"))


def _template_values() -> dict[str, str]:
    return {
        key: value
        for line in LOCAL_ENV_TEMPLATE.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
        for key, value in [line.split("=", 1)]
    }


def test_local_postgres_ports_are_random_and_loopback_only():
    services = _local_compose()["services"]
    for service in ("identity-postgres", "domain-postgres"):
        [port] = services[service]["ports"]
        assert port == {
            "target": 5432,
            "published": "0",
            "host_ip": "127.0.0.1",
        }


def test_local_template_is_explicitly_non_production():
    values = _template_values()
    expected = {
        "IDENTITY_POSTGRES_USER": "biohack_identity_test",
        "IDENTITY_POSTGRES_PASSWORD": "biohack_identity_test_password",
        "IDENTITY_POSTGRES_DB": "biohack_identity_test",
        "DOMAIN_POSTGRES_USER": "biohack_domain_test",
        "DOMAIN_POSTGRES_PASSWORD": "biohack_domain_test_password",
        "DOMAIN_POSTGRES_DB": "biohack_domain_test",
    }
    assert {key: values.get(key) for key in expected} == expected
    assert all("test" in value for value in expected.values())
