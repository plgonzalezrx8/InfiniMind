"""CI-safe CLI integration harness for OpenClaw bridge wiring checks."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from uuid import uuid4

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
E2E_SCRIPT = REPO_ROOT / "scripts" / "openclaw_bridge_e2e.sh"


@pytest.mark.skipif(
    os.environ.get("RUN_OPENCLAW_E2E") != "1",
    reason="Set RUN_OPENCLAW_E2E=1 to run OpenClaw CLI E2E integration checks.",
)
def test_openclaw_bridge_cli_e2e_harness() -> None:
    """Run the executable bridge E2E script with an isolated profile."""

    profile = f"infinimind-ci-{uuid4().hex[:8]}"
    env = os.environ.copy()
    env.setdefault("OPENCLAW_BIN", "openclaw")
    env.setdefault("INFINIMIND_EMBEDDING_PROVIDER", "mock")
    env.setdefault("INFINIMIND_EMBEDDING_MODEL", "text-embedding-3-large")
    env.setdefault("INFINIMIND_API_KEY", "infinimind-e2e-token")
    env.setdefault("INFINIMIND_ADMIN_API_KEY", "infinimind-e2e-admin-token")

    result = subprocess.run(
        [str(E2E_SCRIPT), "--profile", profile],
        cwd=str(REPO_ROOT),
        env=env,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise AssertionError(
            "OpenClaw bridge E2E script failed.\n"
            f"stdout:\n{result.stdout}\n\nstderr:\n{result.stderr}"
        )
