import assert from "node:assert/strict";
import test from "node:test";

import bridgePlugin from "./index.js";

type ToolDef = {
  name: string;
  execute: (toolCallId: string, params: Record<string, unknown>) => Promise<Record<string, unknown>>;
};

type HookHandler = (event: any, ctx: any) => Promise<Record<string, unknown> | void> | Record<string, unknown> | void;

class FakePluginApi {
  pluginConfig: Record<string, unknown>;
  logger = {
    info: () => {
      // Keep output deterministic in tests.
    },
    warn: () => {
      // Keep output deterministic in tests.
    },
  };
  tools: Record<string, ToolDef> = {};
  hooks: Record<string, HookHandler> = {};

  constructor(config: Record<string, unknown>) {
    this.pluginConfig = config;
  }

  registerTool(tool: ToolDef): void {
    this.tools[tool.name] = tool;
  }

  registerService(): void {
    // Service lifecycle is not needed in these unit tests.
  }

  on(name: string, handler: HookHandler): void {
    this.hooks[name] = handler;
  }
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

function withMockedFetch(
  responder: (url: string, init?: RequestInit) => Promise<Response>,
): () => void {
  const originalFetch = globalThis.fetch;
  globalThis.fetch = responder as typeof globalThis.fetch;
  return () => {
    globalThis.fetch = originalFetch;
  };
}

test("autoRecall registers before_prompt_build and injects escaped prependContext", async () => {
  const api = new FakePluginApi(
    baseBridgeConfig({
      autoRecall: {
        enabled: true,
        hook: "before_prompt_build",
        limit: 3,
        minScore: 0.3,
        timeoutMs: 1000,
        maxInjectedChars: 1000,
        includeSensitive: false,
      },
    }),
  );
  bridgePlugin.register(api as never);
  assert.ok(api.hooks.before_prompt_build);

  let capturedBody: Record<string, unknown> = {};
  const restoreFetch = withMockedFetch(async (_url, init) => {
    capturedBody = JSON.parse(String(init?.body ?? "{}"));
    return new Response(
      JSON.stringify({
        count: 1,
        memories: [
          {
            memory_id: "m-1",
            text: "Use <script>alert('x')</script> never",
            category: "fact",
            importance: 0.7,
            score: 0.91,
          },
        ],
      }),
      { status: 200, headers: { "Content-Type": "application/json" } },
    );
  });

  const hookResult = (await api.hooks.before_prompt_build(
    { prompt: "remember deployment constraints", messages: [] },
    { sessionKey: "Chat:ABC", sessionId: "s-1", agentId: "main" },
  )) as any;
  restoreFetch();

  assert.equal(capturedBody.user_id, "hook:chat:abc");
  assert.ok(typeof hookResult.prependContext === "string");
  assert.match(String(hookResult.prependContext), /<relevant-memories>/);
  assert.match(String(hookResult.prependContext), /&lt;script&gt;alert\(&#39;x&#39;\)&lt;\/script&gt;/);
});

test("autoRecall hook fails open on upstream error", async () => {
  const api = new FakePluginApi(
    baseBridgeConfig({
      autoRecall: {
        enabled: true,
        hook: "before_prompt_build",
      },
    }),
  );
  bridgePlugin.register(api as never);

  const restoreFetch = withMockedFetch(async () => {
    throw new Error("network unavailable");
  });
  const hookResult = await api.hooks.before_prompt_build(
    { prompt: "remember deployment constraints", messages: [] },
    { sessionKey: "chat-1", sessionId: "s-2", agentId: "main" },
  );
  restoreFetch();

  assert.equal(hookResult, undefined);
});

test("autoCapture stores user messages and skips near-duplicates", async () => {
  const api = new FakePluginApi(
    baseBridgeConfig({
      autoCapture: {
        enabled: true,
        maxPerTurn: 3,
        minChars: 10,
        maxChars: 500,
        dedupeThreshold: 0.9,
        defaultCategory: "fact",
        sensitivityDefault: "low",
      },
    }),
  );
  bridgePlugin.register(api as never);
  assert.ok(api.hooks.agent_end);

  const calls: Array<{ url: string; body: Record<string, unknown> }> = [];
  let callCount = 0;
  const restoreFetch = withMockedFetch(async (url, init) => {
    const body = JSON.parse(String(init?.body ?? "{}")) as Record<string, unknown>;
    calls.push({ url, body });
    callCount += 1;

    if (callCount === 1) {
      // Dedupe probe for first candidate: treat as duplicate.
      return new Response(
        JSON.stringify({
          count: 1,
          memories: [
            {
              memory_id: "m-existing",
              text: "Remember release owner is ops@example.com",
              category: "fact",
              importance: 0.8,
              score: 0.95,
            },
          ],
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      );
    }

    if (callCount === 2) {
      // Dedupe probe for second candidate: not a duplicate.
      return new Response(JSON.stringify({ count: 0, memories: [] }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      });
    }

    return new Response(JSON.stringify({ action: "created", memory_id: "m-created" }), {
      status: 200,
      headers: { "Content-Type": "application/json" },
    });
  });

  await api.hooks.agent_end(
    {
      success: true,
      messages: [
        { role: "user", content: "Remember release owner is ops@example.com" },
        { role: "assistant", content: "I noted that." },
        { role: "user", content: "Remember escalation contact is +15555550123" },
      ],
    },
    { sessionKey: "chat:ops", sessionId: "sess-22", agentId: "main" },
  );
  restoreFetch();

  const recallCalls = calls.filter((call) => call.url.endsWith("/v1/memory/recall"));
  const storeCalls = calls.filter((call) => call.url.endsWith("/v1/memory/store"));

  assert.equal(recallCalls.length, 2);
  assert.equal(storeCalls.length, 1);
  assert.equal(storeCalls[0].body.user_id, "hook:chat:ops");
  assert.deepEqual(storeCalls[0].body.tags, ["auto-captured"]);
});
