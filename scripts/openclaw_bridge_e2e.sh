#!/usr/bin/env bash
set -euo pipefail

# This script documents the OpenClaw + InfiniMind E2E flow and can be adapted
# directly for CI once an OpenClaw runtime workspace is available.

echo "1) Start InfiniMind sidecar"
docker compose -f deploy/docker-compose.yml up -d --build

echo "2) Install/enable bridge plugin in OpenClaw"
echo "   openclaw plugins install -l /absolute/path/to/plugins/infinimind-openclaw-bridge"
echo "   openclaw plugins enable infinimind-bridge"
echo "   openclaw plugins doctor"

echo "3) Apply config from deploy/openclaw-config.example.json"
echo "   Merge it into ~/.openclaw/openclaw.json and restart OpenClaw gateway"

echo "4) Verify memory tool path through OpenClaw"
echo "   openclaw plugins info infinimind-bridge"
echo "   Trigger memory_store/memory_recall from a test session"
