import assert from "node:assert/strict";
import test from "node:test";

import { InfiniMindHttpClient } from "./http-client.js";
import bridgePlugin from "./index.js";

type ToolDef = {
  name: string;
  execute: (toolCallId: string, params: Record<string, unknown>) => Promise<Record<string, unknown>>;
};

class FakePluginApi {
  pluginConfig: Record<string, unknown>;
  logger = {
    info: () => {
      // Keep test output deterministic.
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

function baseBridgeConfig(overrides: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    baseUrl: "http://localhost:8080",
    apiKey: "test-api-key",
    timeoutMs: 200,
    defaultScope: "user",
    includeSensitiveDefault: false,
    rerankDefault: "hybrid",
    fallbackMode: "legacy-compatible",
    identityFallback: "configured-default",
    defaultUserId: "fallback-user",
    ...overrides,
  };
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

test("memory tool mappings return stable response shapes", async () => {
  const api = new FakePluginApi(baseBridgeConfig());
  bridgePlugin.register(api as never);

  let call = 0;
  const restoreFetch = withMockedFetch(async (_url, _init) => {
    call += 1;
    if (call === 1) {
      return new Response(JSON.stringify({ action: "created", memory_id: "m-created" }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }
    if (call === 2) {
      return new Response(
        JSON.stringify({
          count: 1,
          memories: [
            {
              memory_id: "m-created",
              text: "remember this",
              category: "fact",
              importance: 0.8,
              score: 0.91,
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }
    return new Response(
      JSON.stringify({
        action: "candidates",
        found: 1,
        candidates: [{ memory_id: "m-created", text: "remember this", category: "fact", score: 0.9 }],
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  });

  const store = (await api.tools.memory_store.execute("tc-store", { text: "remember this" })) as any;
  assert.equal(store.details.action, "created");
  assert.equal(store.details.id, "m-created");

  const search = (await api.tools.memory_search.execute("tc-search", { query: "remember" })) as any;
  assert.equal(search.details.count, 1);
  assert.equal(search.details.memories[0].memory_id, "m-created");

  const forget = (await api.tools.memory_forget.execute("tc-forget", { query: "remember", limit: 5 })) as any;
  assert.equal(forget.details.action, "candidates");
  assert.equal(forget.details.candidates.length, 1);
  restoreFetch();
});

test("bridge tool calls surface upstream HTTP status failures explicitly", async () => {
  const api = new FakePluginApi(baseBridgeConfig());
  bridgePlugin.register(api as never);

  for (const statusCode of [401, 403, 500]) {
    const restoreFetch = withMockedFetch(async () => {
      return new Response("upstream failure", { status: statusCode });
    });
    await assert.rejects(
      () => api.tools.memory_recall.execute("tc-fail", { query: "x", userId: "user-1" }),
      new RegExp(`InfiniMind HTTP ${statusCode}`),
    );
    restoreFetch();
  }
});

test("http client enforces timeout via abort controller", async () => {
  const client = new InfiniMindHttpClient({
    baseUrl: "http://localhost:8080",
    apiKey: "test-api-key",
    timeoutMs: 10,
    defaultScope: "user",
    includeSensitiveDefault: false,
    rerankDefault: "hybrid",
    fallbackMode: "legacy-compatible",
    identityFallback: "error",
    defaultUserId: null,
  });

  const restoreFetch = withMockedFetch(async (_url, init) => {
    return await new Promise<Response>((_resolve, reject) => {
      const signal = init?.signal as AbortSignal | undefined;
      if (!signal) {
        reject(new Error("missing abort signal"));
        return;
      }
      signal.addEventListener("abort", () => {
        reject(new Error("aborted by timeout"));
      });
    });
  });

  await assert.rejects(
    () => client.post("/v1/memory/recall", { query: "x" }),
    /aborted by timeout/,
  );
  restoreFetch();
});
