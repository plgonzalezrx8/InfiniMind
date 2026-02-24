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
};

const DEFAULT_SCOPES = ["global", "user", "channel", "session"] as const;
const RERANK_MODES = ["off", "hybrid"] as const;
const FALLBACK_MODES = ["off", "legacy-compatible"] as const;

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
  },
};
