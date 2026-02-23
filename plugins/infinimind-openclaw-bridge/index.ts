import type { OpenClawPluginApi } from "openclaw/plugin-sdk";

import { bridgeConfigSchema } from "./config.js";
import { InfiniMindHttpClient } from "./http-client.js";

const infinimindBridgePlugin = {
  id: "infinimind-bridge",
  name: "InfiniMind Bridge",
  description: "Standalone InfiniMind memory bridge for OpenClaw",
  kind: "memory" as const,
  configSchema: bridgeConfigSchema,

  register(api: OpenClawPluginApi) {
    const cfg = bridgeConfigSchema.parse(api.pluginConfig);
    const client = new InfiniMindHttpClient(cfg);

    api.registerService({
      id: "infinimind-bridge",
      start: async () => {
        // Best-effort startup probe keeps failures visible in logs.
        try {
          await client.post("/v1/memory/recall", {
            tenant_id: "default",
            user_id: "bridge-health",
            query: "health-check",
            limit: 1,
            rerank: "off",
            fallback_mode: "off",
          });
        } catch (error) {
          api.logger.warn(`infinimind-bridge: startup probe failed: ${String(error)}`);
        }
        api.logger.info("infinimind-bridge: service initialized");
      },
      stop: () => {
        api.logger.info("infinimind-bridge: service stopped");
      },
    });
  },
};

export default infinimindBridgePlugin;
