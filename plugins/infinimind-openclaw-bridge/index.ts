import { Type } from "@sinclair/typebox";
import type { OpenClawPluginApi } from "openclaw/plugin-sdk";

import { bridgeConfigSchema } from "./config.js";
import { InfiniMindHttpClient } from "./http-client.js";

type StoreResponse = {
  action: "created" | "duplicate";
  memory_id: string;
  duplicate_of?: string | null;
};

type RecallItem = {
  memory_id: string;
  text: string;
  category: string;
  importance: number;
  score: number;
};

type RecallResponse = {
  count: number;
  memories: RecallItem[];
  debug?: Record<string, unknown> | null;
};

const MEMORY_CATEGORIES = ["preference", "fact", "decision", "entity", "other"] as const;

const infinimindBridgePlugin = {
  id: "infinimind-bridge",
  name: "InfiniMind Bridge",
  description: "Standalone InfiniMind memory bridge for OpenClaw",
  kind: "memory" as const,
  configSchema: bridgeConfigSchema,

  register(api: OpenClawPluginApi) {
    const cfg = bridgeConfigSchema.parse(api.pluginConfig);
    const client = new InfiniMindHttpClient(cfg);

    api.registerTool(
      {
        name: "memory_store",
        label: "Memory Store",
        description: "Store memory entries through the external InfiniMind service.",
        parameters: Type.Object({
          text: Type.String({ description: "Information to remember" }),
          importance: Type.Optional(Type.Number({ description: "Importance 0-1 (default: 0.7)" })),
          category: Type.Optional(
            Type.Unsafe<(typeof MEMORY_CATEGORIES)[number]>({
              type: "string",
              enum: [...MEMORY_CATEGORIES],
            }),
          ),
          scope: Type.Optional(Type.String()),
          channelId: Type.Optional(Type.String()),
          sessionId: Type.Optional(Type.String()),
          actorId: Type.Optional(Type.String()),
          tags: Type.Optional(Type.Array(Type.String())),
          sensitivity: Type.Optional(Type.String()),
          ttlHours: Type.Optional(Type.Number()),
          dedupeKey: Type.Optional(Type.String()),
          metadata: Type.Optional(Type.Record(Type.String(), Type.Any())),
          userId: Type.Optional(Type.String()),
          tenantId: Type.Optional(Type.String()),
          agentId: Type.Optional(Type.String()),
          provenance: Type.Optional(Type.Record(Type.String(), Type.Any())),
          quality: Type.Optional(Type.Record(Type.String(), Type.Any())),
        }),
        async execute(_toolCallId, params) {
          const p = params as Record<string, unknown>;
          const payload = {
            tenant_id: typeof p.tenantId === "string" ? p.tenantId : "default",
            user_id: typeof p.userId === "string" ? p.userId : "default-user",
            agent_id: typeof p.agentId === "string" ? p.agentId : "main",
            text: p.text,
            importance: typeof p.importance === "number" ? p.importance : 0.7,
            category: typeof p.category === "string" ? p.category : "other",
            scope: typeof p.scope === "string" ? p.scope : cfg.defaultScope,
            channel_id: typeof p.channelId === "string" ? p.channelId : null,
            session_id: typeof p.sessionId === "string" ? p.sessionId : null,
            actor_id: typeof p.actorId === "string" ? p.actorId : null,
            tags: Array.isArray(p.tags) ? p.tags : [],
            sensitivity: typeof p.sensitivity === "string" ? p.sensitivity : "low",
            ttl_hours: typeof p.ttlHours === "number" ? p.ttlHours : null,
            dedupe_key: typeof p.dedupeKey === "string" ? p.dedupeKey : null,
            metadata: p.metadata && typeof p.metadata === "object" ? p.metadata : {},
            provenance: p.provenance && typeof p.provenance === "object" ? p.provenance : {},
            quality: p.quality && typeof p.quality === "object" ? p.quality : {},
          };

          const result = await client.post<StoreResponse>("/v1/memory/store", payload);
          if (result.action === "duplicate") {
            return {
              content: [{ type: "text", text: `Similar memory already exists (${result.memory_id}).` }],
              details: {
                action: "duplicate",
                existingId: result.memory_id,
                duplicateOf: result.duplicate_of ?? null,
              },
            };
          }

          return {
            content: [{ type: "text", text: `Stored memory ${result.memory_id}.` }],
            details: { action: "created", id: result.memory_id },
          };
        },
      },
      { name: "memory_store" },
    );

    api.registerTool(
      {
        name: "memory_recall",
        label: "Memory Recall",
        description: "Recall memories through the external InfiniMind service.",
        parameters: Type.Object({
          query: Type.String({ description: "Search query" }),
          limit: Type.Optional(Type.Number({ description: "Max results (default: 5)" })),
          scope: Type.Optional(Type.String()),
          channelId: Type.Optional(Type.String()),
          sessionId: Type.Optional(Type.String()),
          actorId: Type.Optional(Type.String()),
          categories: Type.Optional(Type.Array(Type.String())),
          tagsAny: Type.Optional(Type.Array(Type.String())),
          minImportance: Type.Optional(Type.Number()),
          since: Type.Optional(Type.String()),
          until: Type.Optional(Type.String()),
          includeExpired: Type.Optional(Type.Boolean()),
          includeSensitive: Type.Optional(Type.Boolean()),
          rerank: Type.Optional(Type.Unsafe<"off" | "hybrid">({ type: "string", enum: ["off", "hybrid"] })),
          debug: Type.Optional(Type.Boolean()),
          userId: Type.Optional(Type.String()),
          tenantId: Type.Optional(Type.String()),
          agentId: Type.Optional(Type.String()),
          trustLevel: Type.Optional(Type.Unsafe<"low" | "medium" | "high">({ type: "string", enum: ["low", "medium", "high"] })),
          fallbackMode: Type.Optional(
            Type.Unsafe<"off" | "legacy-compatible">({ type: "string", enum: ["off", "legacy-compatible"] }),
          ),
        }),
        async execute(_toolCallId, params) {
          const p = params as Record<string, unknown>;
          const payload = {
            tenant_id: typeof p.tenantId === "string" ? p.tenantId : "default",
            user_id: typeof p.userId === "string" ? p.userId : "default-user",
            agent_id: typeof p.agentId === "string" ? p.agentId : "main",
            query: p.query,
            limit: typeof p.limit === "number" ? p.limit : 5,
            scope: typeof p.scope === "string" ? p.scope : cfg.defaultScope,
            channel_id: typeof p.channelId === "string" ? p.channelId : null,
            session_id: typeof p.sessionId === "string" ? p.sessionId : null,
            actor_id: typeof p.actorId === "string" ? p.actorId : null,
            categories: Array.isArray(p.categories) ? p.categories : [],
            tags_any: Array.isArray(p.tagsAny) ? p.tagsAny : [],
            min_importance: typeof p.minImportance === "number" ? p.minImportance : null,
            since: typeof p.since === "string" ? p.since : null,
            until: typeof p.until === "string" ? p.until : null,
            include_expired: p.includeExpired === true,
            include_sensitive:
              typeof p.includeSensitive === "boolean" ? p.includeSensitive : cfg.includeSensitiveDefault,
            rerank: typeof p.rerank === "string" ? p.rerank : cfg.rerankDefault,
            debug: p.debug === true,
            trust_level: typeof p.trustLevel === "string" ? p.trustLevel : "medium",
            fallback_mode: typeof p.fallbackMode === "string" ? p.fallbackMode : cfg.fallbackMode,
          };

          const result = await client.post<RecallResponse>("/v1/memory/recall", payload);
          if (result.count === 0) {
            return {
              content: [{ type: "text", text: "No relevant memories found." }],
              details: { count: 0, memories: [] },
            };
          }

          const text = result.memories
            .map(
              (memory, idx) =>
                `${idx + 1}. [${memory.category}] ${memory.text} (${(memory.score * 100).toFixed(0)}%)`,
            )
            .join("\n");

          return {
            content: [{ type: "text", text: `Found ${result.count} memories:\n\n${text}` }],
            details: {
              count: result.count,
              memories: result.memories,
              debug: result.debug ?? null,
            },
          };
        },
      },
      { name: "memory_recall" },
    );

    api.registerService({
      id: "infinimind-bridge",
      start: async () => {
        api.logger.info("infinimind-bridge: service initialized");
      },
      stop: () => {
        api.logger.info("infinimind-bridge: service stopped");
      },
    });
  },
};

export default infinimindBridgePlugin;
