import assert from "node:assert/strict";
import test from "node:test";

import { bridgeConfigSchema } from "./config.js";

function baseConfig(overrides: Record<string, unknown> = {}): Record<string, unknown> {
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

test("parse rejects invalid defaultScope", () => {
  assert.throws(
    () => bridgeConfigSchema.parse(baseConfig({ defaultScope: "team" })),
    /defaultScope must be one of/,
  );
});

test("parse rejects invalid rerankDefault", () => {
  assert.throws(
    () => bridgeConfigSchema.parse(baseConfig({ rerankDefault: "semantic" })),
    /rerankDefault must be one of/,
  );
});

test("parse rejects invalid fallbackMode", () => {
  assert.throws(
    () => bridgeConfigSchema.parse(baseConfig({ fallbackMode: "relaxed" })),
    /fallbackMode must be one of/,
  );
});

test("parse applies safe defaults for autoRecall and autoCapture", () => {
  const parsed = bridgeConfigSchema.parse(baseConfig());
  assert.equal(parsed.autoRecall.enabled, false);
  assert.equal(parsed.autoRecall.hook, "before_prompt_build");
  assert.equal(parsed.autoRecall.limit, 3);
  assert.equal(parsed.autoRecall.minScore, 0.3);
  assert.equal(parsed.autoCapture.enabled, false);
  assert.equal(parsed.autoCapture.maxPerTurn, 3);
  assert.equal(parsed.autoCapture.dedupeThreshold, 0.92);
  assert.equal(parsed.autoCapture.defaultCategory, "other");
  assert.equal(parsed.autoCapture.ttlHoursDefault, null);
});

test("parse rejects invalid autoRecall hook enum", () => {
  assert.throws(
    () =>
      bridgeConfigSchema.parse(
        baseConfig({
          autoRecall: {
            enabled: true,
            hook: "before_llm",
          },
        }),
      ),
    /autoRecall\.hook must be one of/,
  );
});

test("parse rejects invalid autoCapture defaults and ranges", () => {
  assert.throws(
    () =>
      bridgeConfigSchema.parse(
        baseConfig({
          autoCapture: {
            enabled: true,
            minChars: 500,
            maxChars: 100,
          },
        }),
      ),
    /autoCapture\.minChars must be less than or equal to autoCapture\.maxChars/,
  );

  assert.throws(
    () =>
      bridgeConfigSchema.parse(
        baseConfig({
          autoCapture: {
            defaultCategory: "task",
          },
        }),
      ),
    /autoCapture\.defaultCategory must be one of/,
  );
});
