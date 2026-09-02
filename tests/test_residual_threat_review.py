"""Phase 4 — residual-threat review documentation contract (covering test).

Covers the spec requirement "Cutover Rollback and Residual Threats", scenario
"Residual-threat review":

    GIVEN the isolation boundary is approved for deployment
    WHEN operators review its security documentation
    THEN residual same-VPS threats and the future managed-resource
         migration path are explicit

The security documentation under test is the operator runbook
``docs/database-isolation-runbook.md``. This is a documentation-content test:
it reads the runbook and asserts the required statements are present and
operator-visible. No VPS, no credentials, no deployment, and no data movement.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
RUNBOOK = REPO / "docs" / "database-isolation-runbook.md"

# Same-VPS residual threats the spec requires the documentation to state.
RESIDUAL_THREATS = (
    "host-root compromise",
    "shared administration",
    "deployment-secret compromise",
    "application-memory exposure",
    "wrongly scoped export/backup",
)

# Contract-compatible path to independently managed resources.
MANAGED_RESOURCE_PATH_MARKERS = (
    "independently managed resource",
    "without changing the contract",
)


def _residual_section() -> str:
    """Return the runbook's residual-threats section with line wrapping folded.

    Markdown wraps prose across lines, so substring assertions must run over
    whitespace-normalized text (any whitespace run folded to a single space) to
    match the operator-visible statement rather than the source line breaks.
    """
    text = RUNBOOK.read_text(encoding="utf-8")
    heading = "## Residual threats"
    index = text.find(heading)
    assert index != -1, "runbook is missing the '## Residual threats' section"
    return re.sub(r"\s+", " ", text[index:])


@pytest.mark.parametrize("threat", RESIDUAL_THREATS)
def test_runbook_states_residual_threat(threat):
    section = _residual_section()
    assert threat in section, f"residual threat is not explicit: {threat!r}"


@pytest.mark.parametrize("marker", MANAGED_RESOURCE_PATH_MARKERS)
def test_runbook_states_managed_resource_migration_path(marker):
    section = _residual_section()
    assert (
        marker in section
    ), f"managed-resource migration path marker missing: {marker!r}"
