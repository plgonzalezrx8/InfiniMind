#!/usr/bin/env python3
"""Validate service coverage thresholds used by beta release gates."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


# Critical modules keep explicit per-file floors so regressions are caught even
# when aggregate coverage remains high.
DEFAULT_MODULE_THRESHOLDS: dict[str, float] = {
    "services/infinimind-service/app/storage.py": 75.0,
    "services/infinimind-service/app/policy.py": 75.0,
    "services/infinimind-service/app/embeddings.py": 75.0,
    "services/infinimind-service/app/dependencies.py": 75.0,
}


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Check aggregate and critical-module coverage thresholds.",
    )
    parser.add_argument(
        "--coverage-json",
        default="/tmp/infinimind-service-coverage.json",
        help="Path to pytest-cov JSON report",
    )
    parser.add_argument(
        "--min-overall",
        type=float,
        default=85.0,
        help="Required minimum overall coverage percent",
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    report_path = Path(args.coverage_json)
    if not report_path.exists():
        print(f"coverage report not found: {report_path}", file=sys.stderr)
        return 2

    payload = json.loads(report_path.read_text(encoding="utf-8"))
    totals = payload.get("totals", {})
    files = payload.get("files", {})
    overall = float(totals.get("percent_covered", 0.0))

    failures: list[str] = []
    if overall < args.min_overall:
        failures.append(
            f"overall coverage {overall:.2f}% is below minimum {args.min_overall:.2f}%"
        )

    for module_path, threshold in DEFAULT_MODULE_THRESHOLDS.items():
        summary = files.get(module_path, {}).get("summary", {})
        covered = float(summary.get("percent_covered", 0.0))
        if covered < threshold:
            failures.append(
                f"{module_path} coverage {covered:.2f}% is below minimum {threshold:.2f}%"
            )

    if failures:
        print("Service coverage gate failed:", file=sys.stderr)
        for item in failures:
            print(f"- {item}", file=sys.stderr)
        return 1

    print(
        "Service coverage gate passed: "
        f"overall={overall:.2f}% "
        + " ".join(
            f"{module}={float(files[module]['summary']['percent_covered']):.2f}%"
            for module in DEFAULT_MODULE_THRESHOLDS
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
