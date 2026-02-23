#!/usr/bin/env python3
"""Benchmark harness for InfiniMind recall latency and quality proxies."""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from statistics import mean

import httpx



def percentile(values: list[float], pct: float) -> float:
    """Return percentile value using linear interpolation."""

    if not values:
        return 0.0
    ordered = sorted(values)
    rank = (len(ordered) - 1) * pct
    lower = math.floor(rank)
    upper = math.ceil(rank)
    if lower == upper:
        return ordered[lower]
    weight = rank - lower
    return ordered[lower] * (1 - weight) + ordered[upper] * weight



def build_headers(api_key: str) -> dict[str, str]:
    """Construct auth headers expected by InfiniMind."""

    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }



def seed_memories(client: httpx.Client, base_url: str, headers: dict[str, str], user_id: str, count: int) -> None:
    """Insert synthetic rows used for benchmark recall queries."""

    topics = ["deploy", "incident", "preference", "architecture", "testing"]
    for idx in range(count):
        topic = topics[idx % len(topics)]
        payload = {
            "tenant_id": "default",
            "user_id": user_id,
            "agent_id": "main",
            "text": f"Benchmark memory {idx}: {topic} workflow baseline",
            "category": "fact",
            "tags": [topic],
            "importance": round(random.uniform(0.5, 1.0), 3),
        }
        client.post(f"{base_url}/v1/memory/store", headers=headers, json=payload, timeout=10)



def benchmark_mode(
    client: httpx.Client,
    *,
    base_url: str,
    headers: dict[str, str],
    user_id: str,
    loops: int,
    rerank_mode: str,
) -> dict[str, float]:
    """Benchmark one rerank mode and return summary statistics."""

    queries = [
        ("deploy workflow", "deploy"),
        ("incident baseline", "incident"),
        ("testing baseline", "testing"),
        ("architecture workflow", "architecture"),
    ]
    latencies_ms: list[float] = []
    top1_hits = 0

    for idx in range(loops):
        query, expected = queries[idx % len(queries)]
        payload = {
            "tenant_id": "default",
            "user_id": user_id,
            "agent_id": "main",
            "query": query,
            "limit": 5,
            "rerank": rerank_mode,
        }

        start = time.perf_counter()
        response = client.post(f"{base_url}/v1/memory/recall", headers=headers, json=payload, timeout=15)
        elapsed_ms = (time.perf_counter() - start) * 1000.0
        latencies_ms.append(elapsed_ms)

        response.raise_for_status()
        body = response.json()
        memories = body.get("memories", [])
        if memories:
            top_text = str(memories[0].get("text", "")).lower()
            if expected in top_text:
                top1_hits += 1

    return {
        "loops": float(loops),
        "mean_ms": mean(latencies_ms) if latencies_ms else 0.0,
        "p50_ms": percentile(latencies_ms, 0.50),
        "p95_ms": percentile(latencies_ms, 0.95),
        "top1_hit_rate": (top1_hits / loops) if loops else 0.0,
    }



def main() -> None:
    """CLI entrypoint for benchmark execution."""

    parser = argparse.ArgumentParser(description="InfiniMind recall benchmark")
    parser.add_argument("--base-url", default="http://127.0.0.1:8080")
    parser.add_argument("--api-key", default="change-me-now")
    parser.add_argument("--user-id", default="benchmark-user")
    parser.add_argument("--seed-count", type=int, default=200)
    parser.add_argument("--loops", type=int, default=100)
    parser.add_argument("--output", default="")
    args = parser.parse_args()

    headers = build_headers(args.api_key)
    with httpx.Client() as client:
        seed_memories(client, args.base_url, headers, args.user_id, args.seed_count)

        results = {
            "off": benchmark_mode(
                client,
                base_url=args.base_url,
                headers=headers,
                user_id=args.user_id,
                loops=args.loops,
                rerank_mode="off",
            ),
            "hybrid": benchmark_mode(
                client,
                base_url=args.base_url,
                headers=headers,
                user_id=args.user_id,
                loops=args.loops,
                rerank_mode="hybrid",
            ),
        }

    print(json.dumps(results, indent=2))

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(results, handle, indent=2)


if __name__ == "__main__":
    main()
