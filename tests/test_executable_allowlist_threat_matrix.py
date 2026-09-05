"""Phase 1.3 — executable allowlist threat matrix (regression suite).

Locks the design threat-matrix defense for the ``ops/*`` execution boundary:
documentation-like and non-operation paths MUST be rejected before any Compose
invocation. The exact cases from the design threat matrix are covered:

  * ``requirements.txt``  — a Python dependency manifest, not an operation;
  * ``CMakeLists.txt``    — a build manifest, not an operation;
  * executable Markdown   — ``backfill.md``, ``plan.md`` (and ``.markdown``);
  * executable MDX        — ``plan.mdx``;
  * ``README.sh``         — a documentation shell script.

The defense is implemented in ``ops/lib/operation-contract.sh``
(``contract_validate_action`` / ``contract_is_executable_action_path``). This
suite pins that behavior so a future refactor cannot silently allow a
documentation-like path to reach Compose. No VPS, database, credential, or data
movement is touched — every test sources the shared contract library only.
"""

from __future__ import annotations

import os
import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
CONTRACT_LIB = REPO / "ops" / "lib" / "operation-contract.sh"

# Documentation-like / non-operation paths that must never execute.
THREAT_PATHS = (
    "requirements.txt",
    "CMakeLists.txt",
    "backfill.md",
    "plan.md",
    "plan.markdown",
    "plan.mdx",
    "README.sh",
    "readme.sh",
)


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


@pytest.mark.parametrize("path", THREAT_PATHS)
def test_validate_action_rejects_documentation_like_path(path):
    result = _source(f'contract_validate_action "{path}"')
    assert result.returncode != 0, f"{path} was not rejected: {result.stdout}"


@pytest.mark.parametrize("path", THREAT_PATHS)
def test_executable_path_rejects_documentation_like_path(path):
    result = _source(
        f'contract_is_executable_action_path "{path}" && echo allowed || echo rejected'
    )
    assert "rejected" in result.stdout, f"{path} was classified executable"


@pytest.mark.parametrize("path", THREAT_PATHS)
def test_allowlist_rejects_documentation_like_path(path):
    result = _source(f'contract_is_allowed_action "{path}" && echo allowed || echo rejected')
    assert "rejected" in result.stdout, f"{path} was allowlisted"


def test_known_operation_still_allowed():
    result = _source('contract_validate_action "cutover"')
    assert result.returncode == 0, result.stderr


# ── Case-insensitive documentation-like extension ──────────────────────────
#
# An UPPERCASE extension is still a documentation-like path. ``backfill.MD``,
# ``plan.MDX``, ``requirements.TXT``, and ``CMakeLists.TXT`` must be rejected
# before any Compose invocation exactly like their lowercase equivalents.
# RED-first: these cases FAIL before the allowlist is made case-insensitive.

UPPERCASE_THREAT_PATHS = (
    "backfill.MD",
    "plan.MDX",
    "requirements.TXT",
    "CMakeLists.TXT",
    "plan.MARKDOWN",
    "backfill.RST",
    # Mixed case: forces genuinely case-insensitive matching, not an
    # uppercase-only pattern list.
    "Backfill.Md",
    "Plan.mDx",
    "Requirements.Txt",
)


@pytest.mark.parametrize("path", UPPERCASE_THREAT_PATHS)
def test_executable_path_rejects_uppercase_extension(path):
    result = _source(
        f'contract_is_executable_action_path "{path}" && echo allowed || echo rejected'
    )
    assert "rejected" in result.stdout, f"{path} was classified executable"


@pytest.mark.parametrize("path", UPPERCASE_THREAT_PATHS)
def test_validate_action_rejects_uppercase_extension(path):
    result = _source(f'contract_validate_action "{path}"')
    assert result.returncode != 0, f"{path} was not rejected"
