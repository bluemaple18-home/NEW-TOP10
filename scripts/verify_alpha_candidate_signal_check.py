#!/usr/bin/env python3
"""驗證 alpha candidate signal check 只產生研究證據。"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify alpha candidate signal check")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/alpha_candidate_signal_check_verification_latest.json")
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def synthetic_features() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    stock_ids = [f"100{index}" for index in range(1, 7)]
    alpha_rank = {stock_id: index for index, stock_id in enumerate(stock_ids, start=1)}
    dates = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
    for date_text in dates:
        for stock_id in stock_ids:
            rank = alpha_rank[stock_id]
            rows.append(
                {
                    "date": date_text,
                    "stock_id": stock_id,
                    "open": 100.0,
                    "close": 96.0 + rank * 2.0,
                }
            )
    return pd.DataFrame(rows)


def synthetic_alpha() -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    stock_ids = [f"100{index}" for index in range(1, 7)]
    dates = ["2026-01-01", "2026-01-02", "2026-01-03", "2026-01-04"]
    for date_text in dates:
        for rank, stock_id in enumerate(stock_ids, start=1):
            rows.append(
                {
                    "date": date_text,
                    "stock_id": stock_id,
                    "alpha_good": float(rank),
                    "alpha_flat": 1.0,
                }
            )
    return pd.DataFrame(rows)


def synthetic_verification() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="top10-alpha-signal-check-") as tmp:
        root = Path(tmp)
        features_path = root / "features.parquet"
        alpha_path = root / "alpha.parquet"
        output_path = root / "alpha_signal_check.json"
        synthetic_features().to_parquet(features_path, index=False)
        synthetic_alpha().to_parquet(alpha_path, index=False)
        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "research_alpha_candidate_signal_check.py"),
                "--features",
                str(features_path),
                "--alpha-artifact",
                str(alpha_path),
                "--date",
                "2026-01-04",
                "--horizon",
                "1",
                "--min-ic-days",
                "2",
                "--min-coverage",
                "0.5",
                "--output",
                str(output_path),
            ],
            cwd=PROJECT_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            return {
                "status": "FAILED",
                "stdout": completed.stdout,
                "stderr": completed.stderr,
                "checks": {"synthetic_command": False},
            }
        payload = json.loads(output_path.read_text(encoding="utf-8"))
        metrics = {row["factor"]: row for row in payload.get("metrics", [])}
        contract = payload.get("contract", {})
        checks = {
            "synthetic_command": True,
            "schema": payload.get("schema_version") == "alpha-candidate-signal-check.v1",
            "alpha_good_candidate": metrics.get("alpha_good", {}).get("status") == "SHADOW_CANDIDATE",
            "alpha_good_positive_ic": (metrics.get("alpha_good", {}).get("ic_mean") or 0) > 0,
            "alpha_flat_monitor_only": metrics.get("alpha_flat", {}).get("status") == "MONITOR_ONLY",
            "research_only": contract.get("research_only") is True,
            "does_not_train_model": contract.get("does_not_train_model") is True,
            "does_not_write_model": contract.get("does_not_write_models_latest_lgbm") is True,
            "does_not_write_production_features": contract.get("does_not_write_production_features") is True,
            "does_not_change_ranking": contract.get("does_not_change_production_ranking") is True,
            "promotion_blocked": contract.get("production_promotion_allowed") is False,
        }
        return {
            "status": "OK" if all(checks.values()) else "FAILED",
            "checks": checks,
            "synthetic_output": str(output_path),
        }


def artifact_verification(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"status": "SKIPPED", "checks": {"artifact_provided": False}}
    if not path.exists():
        return {"status": "FAILED", "checks": {"artifact_exists": False}}
    payload = json.loads(path.read_text(encoding="utf-8"))
    contract = payload.get("contract", {})
    checks = {
        "artifact_exists": True,
        "schema": payload.get("schema_version") == "alpha-candidate-signal-check.v1",
        "status_ok": payload.get("status") == "OK",
        "metrics_present": bool(payload.get("metrics")),
        "research_only": contract.get("research_only") is True,
        "does_not_train_model": contract.get("does_not_train_model") is True,
        "does_not_write_model": contract.get("does_not_write_models_latest_lgbm") is True,
        "does_not_write_production_features": contract.get("does_not_write_production_features") is True,
        "does_not_change_ranking": contract.get("does_not_change_production_ranking") is True,
        "promotion_blocked": contract.get("production_promotion_allowed") is False,
    }
    return {
        "status": "OK" if all(checks.values()) else "FAILED",
        "checks": checks,
        "artifact": repo_path(path),
        "summary": payload.get("summary", {}),
    }


def build_report(artifact: Path | None) -> dict[str, Any]:
    synthetic = synthetic_verification()
    artifact_report = artifact_verification(artifact)
    failed = [
        name
        for name, section in {"synthetic": synthetic, "artifact": artifact_report}.items()
        if section["status"] not in {"OK", "SKIPPED"}
    ]
    return {
        "schema_version": "alpha-candidate-signal-check-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "input": repo_path(artifact),
        "summary": {
            "failed_sections": failed,
            "artifact_checked": artifact is not None,
        },
        "synthetic": synthetic,
        "artifact": artifact_report,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    report = build_report(artifact)
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output path resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": repo_path(output), **report["summary"]}, ensure_ascii=False))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
