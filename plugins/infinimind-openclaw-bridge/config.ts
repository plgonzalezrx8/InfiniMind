export type BridgeConfig = {
  baseUrl: string;
  apiKey: string;
  timeoutMs: number;
  defaultScope: "global" | "user" | "channel" | "session";
  includeSensitiveDefault: boolean;
  rerankDefault: "off" | "hybrid";
  fallbackMode: "off" | "legacy-compatible";
  identityFallback: "error" | "configured-default";
  defaultUserId: string | null;
  autoRecall: {
    enabled: boolean;
    hook: "before_prompt_build" | "before_agent_start";
    limit: number;
    minScore: number;
    timeoutMs: number;
    maxInjectedChars: number;
    includeSensitive: boolean;
  };
  autoCapture: {
    enabled: boolean;
    maxPerTurn: number;
    minChars: number;
    maxChars: number;
    dedupeThreshold: number;
    defaultCategory: "preference" | "fact" | "decision" | "entity" | "other";
    sensitivityDefault: "low" | "medium" | "high";
    ttlHoursDefault: number | null;
  };
};

const DEFAULT_SCOPES = ["global", "user", "channel", "session"] as const;
const RERANK_MODES = ["off", "hybrid"] as const;
const FALLBACK_MODES = ["off", "legacy-compatible"] as const;
const AUTO_RECALL_HOOKS = ["before_prompt_build", "before_agent_start"] as const;
const MEMORY_CATEGORIES = ["preference", "fact", "decision", "entity", "other"] as const;
const SENSITIVITY_MODES = ["low", "medium", "high"] as const;

function assertAllowedKeys(value: Record<string, unknown>, allowed: string[], label: string) {
  const unknown = Object.keys(value).filter((key) => !allowed.includes(key));
  if (unknown.length === 0) {
    return;
  }
  throw new Error(`${label} has unknown keys: ${unknown.join(", ")}`);
}

function resolveEnvVars(value: string): string {
  return value.replace(/\$\{([^}]+)\}/g, (_, envVar) => {
    const envValue = process.env[envVar];
    if (!envValue) {
      throw new Error(`Environment variable ${envVar} is not set`);
    }
    return envValue;
  });
}

function parseIntegerInRange(
  value: unknown,
  defaults: { fallback: number; min: number; max: number; label: string },
): number {
  const parsed =
    typeof value === "number" && Number.isFinite(value) ? Math.floor(value) : defaults.fallback;
  if (parsed < defaults.min || parsed > defaults.max) {
    throw new Error(`${defaults.label} must be between ${defaults.min} and ${defaults.max}`);
  }
  return parsed;
}

function parseNumberInRange(
  value: unknown,
  defaults: { fallback: number; min: number; max: number; label: string },
): number {
  const parsed = typeof value === "number" && Number.isFinite(value) ? value : defaults.fallback;
  if (parsed < defaults.min || parsed > defaults.max) {
    throw new Error(`${defaults.label} must be between ${defaults.min} and ${defaults.max}`);
  }
  return parsed;
}

function parseOptionalObject(value: unknown, label: string): Record<string, unknown> {
  if (value === undefined) {
    return {};
  }
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
  return value as Record<string, unknown>;
}

export const bridgeConfigSchema = {
  parse(value: unknown): BridgeConfig {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
      throw new Error("infinimind bridge config required");
    }

    const cfg = value as Record<string, unknown>;
    assertAllowedKeys(
      cfg,
      [
        "baseUrl",
        "apiKey",
        "timeoutMs",
        "defaultScope",
        "includeSensitiveDefault",
        "rerankDefault",
        "fallbackMode",
        "identityFallback",
        "defaultUserId",
        "autoRecall",
        "autoCapture",
      ],
      "infinimind bridge config",
    );

    if (typeof cfg.baseUrl !== "string" || cfg.baseUrl.length === 0) {
      throw new Error("baseUrl is required");
    }
    if (typeof cfg.apiKey !== "string" || cfg.apiKey.length === 0) {
      throw new Error("apiKey is required");
    }

    const timeoutMs =
      typeof cfg.timeoutMs === "number" && Number.isFinite(cfg.timeoutMs)
        ? Math.floor(cfg.timeoutMs)
        : 4000;
    if (timeoutMs < 100 || timeoutMs > 120_000) {
      throw new Error("timeoutMs must be between 100 and 120000");
    }

    const defaultScope =
      typeof cfg.defaultScope === "string" ? (cfg.defaultScope as BridgeConfig["defaultScope"]) : "user";
    if (!DEFAULT_SCOPES.includes(defaultScope)) {
      throw new Error(`defaultScope must be one of: ${DEFAULT_SCOPES.join(", ")}`);
    }

    const rerankDefault =
      typeof cfg.rerankDefault === "string" ? (cfg.rerankDefault as BridgeConfig["rerankDefault"]) : "hybrid";
    if (!RERANK_MODES.includes(rerankDefault)) {
      throw new Error(`rerankDefault must be one of: ${RERANK_MODES.join(", ")}`);
    }

    const fallbackMode =
      typeof cfg.fallbackMode === "string"
        ? (cfg.fallbackMode as BridgeConfig["fallbackMode"])
        : "legacy-compatible";
    if (!FALLBACK_MODES.includes(fallbackMode)) {
      throw new Error(`fallbackMode must be one of: ${FALLBACK_MODES.join(", ")}`);
    }
    const identityFallback =
      typeof cfg.identityFallback === "string"
        ? (cfg.identityFallback as BridgeConfig["identityFallback"])
        : "error";
    if (identityFallback !== "error" && identityFallback !== "configured-default") {
      throw new Error("identityFallback must be one of: error, configured-default");
    }
    const defaultUserId =
      typeof cfg.defaultUserId === "string" && cfg.defaultUserId.trim().length > 0
        ? cfg.defaultUserId.trim()
        : null;
    if (identityFallback === "configured-default" && !defaultUserId) {
      throw new Error("defaultUserId is required when identityFallback=configured-default");
    }

    const autoRecall = parseOptionalObject(cfg.autoRecall, "autoRecall");
    assertAllowedKeys(
      autoRecall,
      ["enabled", "hook", "limit", "minScore", "timeoutMs", "maxInjectedChars", "includeSensitive"],
      "autoRecall",
    );

    const autoRecallHook =
      typeof autoRecall.hook === "string"
        ? (autoRecall.hook as BridgeConfig["autoRecall"]["hook"])
        : "before_prompt_build";
    if (!AUTO_RECALL_HOOKS.includes(autoRecallHook)) {
      throw new Error(`autoRecall.hook must be one of: ${AUTO_RECALL_HOOKS.join(", ")}`);
    }

    const autoCapture = parseOptionalObject(cfg.autoCapture, "autoCapture");
    assertAllowedKeys(
      autoCapture,
      [
        "enabled",
        "maxPerTurn",
        "minChars",
        "maxChars",
        "dedupeThreshold",
        "defaultCategory",
        "sensitivityDefault",
        "ttlHoursDefault",
      ],
      "autoCapture",
    );

    const autoCaptureDefaultCategory =
      typeof autoCapture.defaultCategory === "string"
        ? (autoCapture.defaultCategory as BridgeConfig["autoCapture"]["defaultCategory"])
        : "other";
    if (!MEMORY_CATEGORIES.includes(autoCaptureDefaultCategory)) {
      throw new Error(`autoCapture.defaultCategory must be one of: ${MEMORY_CATEGORIES.join(", ")}`);
    }

    const autoCaptureSensitivity =
      typeof autoCapture.sensitivityDefault === "string"
        ? (autoCapture.sensitivityDefault as BridgeConfig["autoCapture"]["sensitivityDefault"])
        : "low";
    if (!SENSITIVITY_MODES.includes(autoCaptureSensitivity)) {
      throw new Error(`autoCapture.sensitivityDefault must be one of: ${SENSITIVITY_MODES.join(", ")}`);
    }

    const autoCaptureMinChars = parseIntegerInRange(autoCapture.minChars, {
      fallback: 20,
      min: 1,
      max: 20_000,
      label: "autoCapture.minChars",
    });
    const autoCaptureMaxChars = parseIntegerInRange(autoCapture.maxChars, {
      fallback: 800,
      min: 10,
      max: 100_000,
      label: "autoCapture.maxChars",
    });
    if (autoCaptureMinChars > autoCaptureMaxChars) {
      throw new Error("autoCapture.minChars must be less than or equal to autoCapture.maxChars");
    }

    let ttlHoursDefault: number | null = null;
    if (autoCapture.ttlHoursDefault === null || autoCapture.ttlHoursDefault === undefined) {
      ttlHoursDefault = null;
    } else {
      ttlHoursDefault = parseIntegerInRange(autoCapture.ttlHoursDefault, {
        fallback: 1,
        min: 1,
        max: 24 * 365,
        label: "autoCapture.ttlHoursDefault",
      });
    }

    return {
      baseUrl: cfg.baseUrl.replace(/\/$/, ""),
      apiKey: resolveEnvVars(cfg.apiKey),
      timeoutMs,
      defaultScope,
      includeSensitiveDefault: cfg.includeSensitiveDefault === true,
      rerankDefault,
      fallbackMode,
      identityFallback,
      defaultUserId,
      autoRecall: {
        enabled: autoRecall.enabled === true,
        hook: autoRecallHook,
        limit: parseIntegerInRange(autoRecall.limit, {
          fallback: 3,
          min: 1,
          max: 20,
          label: "autoRecall.limit",
        }),
        minScore: parseNumberInRange(autoRecall.minScore, {
          fallback: 0.3,
          min: 0,
          max: 1,
          label: "autoRecall.minScore",
        }),
        timeoutMs: parseIntegerInRange(autoRecall.timeoutMs, {
          fallback: 1500,
          min: 100,
          max: 120_000,
          label: "autoRecall.timeoutMs",
        }),
        maxInjectedChars: parseIntegerInRange(autoRecall.maxInjectedChars, {
          fallback: 2500,
          min: 128,
          max: 32_000,
          label: "autoRecall.maxInjectedChars",
        }),
        includeSensitive: autoRecall.includeSensitive === true,
      },
      autoCapture: {
        enabled: autoCapture.enabled === true,
        maxPerTurn: parseIntegerInRange(autoCapture.maxPerTurn, {
          fallback: 3,
          min: 1,
          max: 20,
          label: "autoCapture.maxPerTurn",
        }),
        minChars: autoCaptureMinChars,
        maxChars: autoCaptureMaxChars,
        dedupeThreshold: parseNumberInRange(autoCapture.dedupeThreshold, {
          fallback: 0.9,
          min: 0,
          max: 1,
          label: "autoCapture.dedupeThreshold",
        }),
        defaultCategory: autoCaptureDefaultCategory,
        sensitivityDefault: autoCaptureSensitivity,
        ttlHoursDefault,
      },
    };
  },
  uiHints: {
    baseUrl: {
      label: "InfiniMind Base URL",
      placeholder: "http://infinimind:8080",
      help: "HTTP endpoint for the InfiniMind service",
    },
    apiKey: {
      label: "InfiniMind API Key",
      sensitive: true,
      placeholder: "${INFINIMIND_API_KEY}",
      help: "Bearer token used to authenticate bridge requests",
    },
    timeoutMs: {
      label: "Request Timeout (ms)",
      placeholder: "4000",
      advanced: true,
    },
    defaultScope: {
      label: "Default Scope",
      help: "Default recall scope when not provided in tool params",
    },
    includeSensitiveDefault: {
      label: "Include Sensitive by Default",
      help: "If enabled, bridge requests can ask for sensitive memories by default",
      advanced: true,
    },
    rerankDefault: {
      label: "Default Rerank Mode",
      help: "Controls whether hybrid reranking is used when not specified",
      advanced: true,
    },
    fallbackMode: {
      label: "Fallback Mode",
      help: "Controls recall expansion behavior when strict filters return too few candidates",
      advanced: true,
    },
    identityFallback: {
      label: "Identity Fallback",
      help: "Controls behavior when user identity is missing from tool input",
      advanced: true,
    },
    defaultUserId: {
      label: "Default User ID",
      help: "Used only when identityFallback=configured-default",
      advanced: true,
    },
    "autoRecall.enabled": {
      label: "Auto Recall Enabled",
      help: "Inject relevant memories automatically before each agent run",
      advanced: true,
    },
    "autoRecall.hook": {
      label: "Auto Recall Hook",
      help: "Preferred hook is before_prompt_build; before_agent_start is legacy-compatible",
      advanced: true,
    },
    "autoRecall.limit": {
      label: "Auto Recall Limit",
      help: "Maximum number of memories injected into prompt context",
      advanced: true,
    },
    "autoRecall.minScore": {
      label: "Auto Recall Min Score",
      help: "Score floor for injected memories",
      advanced: true,
    },
    "autoCapture.enabled": {
      label: "Auto Capture Enabled",
      help: "Store durable user facts/preferences automatically on agent completion",
      advanced: true,
    },
    "autoCapture.maxPerTurn": {
      label: "Auto Capture Max Per Turn",
      advanced: true,
    },
    "autoCapture.dedupeThreshold": {
      label: "Auto Capture Dedupe Threshold",
      help: "Skip capture when a near-duplicate memory already exists",
      advanced: true,
    },
  },
};
