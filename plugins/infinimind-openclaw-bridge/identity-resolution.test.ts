import assert from "node:assert/strict";
import test from "node:test";

import bridgePlugin from "./index.js";

type ToolDef = {
  name: string;
  execute: (toolCallId: string, params: Record<string, unknown>) => Promise<Record<string, unknown>>;
};

class FakePluginApi {
  pluginConfig: Record<string, unknown>;
  logger = {
    info: () => {
      // No-op logger for deterministic tests.
    },
  };
  tools: Record<string, ToolDef> = {};

  constructor(config: Record<string, unknown>) {
    this.pluginConfig = config;
  }

  registerTool(tool: ToolDef): void {
    this.tools[tool.name] = tool;
  }

  registerService(): void {
    // Service lifecycle hooks are irrelevant for these unit tests.
  }
}

function withMockedFetch(
  responder: (url: string, init?: RequestInit) => Promise<Response>,
): () => void {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = responder as typeof globalThis.fetch;
  return () => {
    globalThis.fetch = originalFetch;
  };
}

function baseBridgeConfig(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    baseUrl: "http://localhost:8080",
    apiKey: "test-api-key",
    timeoutMs: 4000,
    defaultScope: "user",
    includeSensitiveDefault: false,
    rerankDefault: "hybrid",
    fallbackMode: "legacy-compatible",
    identityFallback: "error",
    ...overrides,
  };
}

test("identityFallback=error rejects requests without any identity fields", async () => {
  const api = new FakePluginApi(baseBridgeConfig({ identityFallback: "error" }));
  bridgePlugin.register(api as never);

  let fetchCalled = false;
  const restoreFetch = withMockedFetch(async () => {
    fetchCalled = true;
    return new Response(JSON.stringify({ action: "created", memory_id: "m1" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  await assert.rejects(
    () => api.tools.memory_store.execute("tc-1", { text: "store this memory" }),
    /Identity is required\./,
  );
  assert.equal(fetchCalled, false);
  restoreFetch();
});

test("identityFallback=configured-default uses defaultUserId when identity is absent", async () => {
  const api = new FakePluginApi(
    baseBridgeConfig({ identityFallback: "configured-default", defaultUserId: "fallback-user" }),
  );
  bridgePlugin.register(api as never);

  let capturedBody: Record<string, unknown> = {};
  const restoreFetch = withMockedFetch(async (_url, init) => {
    capturedBody = JSON.parse(String(init?.body ?? "{}"));
    return new Response(JSON.stringify({ action: "created", memory_id: "m2" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  await api.tools.memory_store.execute("tc-2", { text: "remember this" });
  assert.equal(capturedBody.user_id, "fallback-user");
  restoreFetch();
});

test("identity precedence is userId -> actorId -> sessionId -> channelId", async () => {
  const api = new FakePluginApi(baseBridgeConfig({ identityFallback: "error" }));
  bridgePlugin.register(api as never);

  let capturedBody: Record<string, unknown> = {};
  const restoreFetch = withMockedFetch(async (_url, init) => {
    capturedBody = JSON.parse(String(init?.body ?? "{}"));
    return new Response(JSON.stringify({ count: 0, memories: [] }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  await api.tools.memory_recall.execute("tc-3", {
    query: "who am i",
    userId: "user-preferred",
    actorId: "actor-second",
    sessionId: "session-third",
    channelId: "channel-fourth",
  });
  assert.equal(capturedBody.user_id, "user-preferred");
  restoreFetch();
});
