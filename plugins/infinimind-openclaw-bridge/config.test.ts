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

