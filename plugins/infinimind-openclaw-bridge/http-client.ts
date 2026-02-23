import type { BridgeConfig } from "./config.js";

export class InfiniMindHttpClient {
  constructor(private readonly cfg: BridgeConfig) {}

  async post<TResponse>(path: string, body: Record<string, unknown>): Promise<TResponse> {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), this.cfg.timeoutMs);

    try {
      const response = await fetch(`${this.cfg.baseUrl}${path}`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${this.cfg.apiKey}`,
        },
        body: JSON.stringify(body),
        signal: controller.signal,
      });

      if (!response.ok) {
        const raw = await response.text();
        throw new Error(`InfiniMind HTTP ${response.status}: ${raw}`);
      }

      return (await response.json()) as TResponse;
    } finally {
      clearTimeout(timeout);
    }
  }
}
