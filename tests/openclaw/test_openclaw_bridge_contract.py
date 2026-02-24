"""Contract checks for the OpenClaw bridge plugin and config wiring."""

from __future__ import annotations

import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
MANIFEST_PATH = REPO_ROOT / "plugins" / "infinimind-openclaw-bridge" / "openclaw.plugin.json"
CONFIG_EXAMPLE_PATH = REPO_ROOT / "deploy" / "openclaw-config.example.json"
BRIDGE_INDEX_PATH = REPO_ROOT / "plugins" / "infinimind-openclaw-bridge" / "index.ts"


def test_bridge_manifest_is_strict_and_memory_kind() -> None:
    """Bridge manifest must satisfy OpenClaw strict schema expectations."""

    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    schema = manifest["configSchema"]

    assert manifest["id"] == "infinimind-bridge"
    assert manifest["kind"] == "memory"
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == {"baseUrl", "apiKey"}

    fallback_enum = schema["properties"]["fallbackMode"]["enum"]
    assert fallback_enum == ["off", "legacy-compatible"]


def test_openclaw_config_example_wires_memory_slot() -> None:
    """Example config must point plugins.slots.memory at the bridge plugin."""

    cfg = json.loads(CONFIG_EXAMPLE_PATH.read_text(encoding="utf-8"))
    plugins = cfg["plugins"]
    entries = plugins["entries"]

    assert plugins["slots"]["memory"] == "infinimind-bridge"
    assert "infinimind-bridge" in plugins["allow"]
    assert entries["infinimind-bridge"]["enabled"] is True

    bridge_cfg = entries["infinimind-bridge"]["config"]
    assert bridge_cfg["defaultScope"] == "user"
    assert bridge_cfg["rerankDefault"] == "hybrid"
    assert bridge_cfg["fallbackMode"] == "legacy-compatible"


def test_bridge_declares_memory_forget_mapping() -> None:
    """Bridge source should expose memory_forget and call the matching service endpoint."""

    source = BRIDGE_INDEX_PATH.read_text(encoding="utf-8")
    assert 'name: "memory_forget"' in source
    assert '"/v1/memory/forget"' in source
    assert '"deleted" | "candidates" | "not_found" | "missing_param"' in source
