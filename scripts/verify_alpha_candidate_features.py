#!/usr/bin/env python3
"""驗證 shadow alpha 候選因子 materializer 的安全邊界。"""

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
ALPHA_COLUMNS = {
    "alpha_trend_stack_score",
    "alpha_breakout_volume_confirm",
    "alpha_volatility_compression_rank",
    "alpha_pullback_to_trend",
    "alpha_liquidity_rank",
}
BLOCKED_COLUMN_PREFIXES = ("future_", "target", "label_", "next_")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify shadow alpha candidate features")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/alpha_candidate_features_verification_latest.json")
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
    return pd.DataFrame(
        [
            {
                "date": "2026-01-02",
                "stock_id": "1111",
                "close": 110,
                "ma5": 108,
                "ma20": 100,
                "ma60": 90,
                "rsi": 50,
                "bias_20": 2,
                "break_20d_high": 1,
                "volume_ratio_20d": 2.0,
                "bb_width": 0.20,
                "avg_value_20d": 1000,
            },
            {
                "date": "2026-01-02",
                "stock_id": "2222",
                "close": 90,
                "ma5": 95,
                "ma20": 100,
                "ma60": 105,
                "rsi": 35,
                "bias_20": -10,
                "break_20d_high": 0,
                "volume_ratio_20d": 0.8,
                "bb_width": 0.50,
                "avg_value_20d": 100,
            },
            {
                "date": "2026-01-03",
                "stock_id": "1111",
                "close": 103,
                "ma5": 101,
                "ma20": 100,
                "ma60": 95,
                "rsi": 52,
                "bias_20": 1,
                "break_20d_high": 0,
                "volume_ratio_20d": 1.2,
                "bb_width": 0.30,
                "avg_value_20d": 300,
            },
            {
                "date": "2026-01-03",
                "stock_id": "2222",
                "close": 120,
                "ma5": 118,
                "ma20": 110,
                "ma60": 100,
                "rsi": 72,
                "bias_20": 8,
                "break_20d_high": 1,
                "volume_ratio_20d": 5.0,
                "bb_width": 0.10,
                "avg_value_20d": 900,
            },
        ]
    )


def synthetic_verification() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="top10-alpha-candidates-") as tmp:
        root = Path(tmp)
        features_path = root / "features.parquet"
        output_path = root / "alpha_candidate_features.parquet"
        synthetic_features().to_parquet(features_path, index=False)
        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "build_alpha_candidate_features.py"),
                "--features",
                str(features_path),
                "--date",
                "2026-01-03",
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
        frame = pd.read_parquet(output_path)
        metadata = json.loads(output_path.with_suffix(".json").read_text(encoding="utf-8"))
        lookup = {(str(row.date)[:10], str(row.stock_id)): row for row in frame.itertuples(index=False)}
        first = lookup[("2026-01-02", "1111")]
        second = lookup[("2026-01-02", "2222")]
        checks = {
            "synthetic_command": True,
            "schema": metadata.get("schema_version") == "alpha-candidate-features.v1",
            "required_columns": {"date", "stock_id", *ALPHA_COLUMNS} <= set(frame.columns),
            "no_blocked_columns": not any(column.startswith(BLOCKED_COLUMN_PREFIXES) for column in frame.columns),
            "unique_trade_keys": not frame.duplicated(["date", "stock_id"]).any(),
            "trend_stack_expected": float(first.alpha_trend_stack_score) == 3.0 and float(second.alpha_trend_stack_score) == 0.0,
            "breakout_volume_capped": float(lookup[("2026-01-03", "2222")].alpha_breakout_volume_confirm) == 3.0,
            "pullback_signal_expected": float(first.alpha_pullback_to_trend) == 1.0 and float(second.alpha_pullback_to_trend) == 0.0,
            "contract_shadow_only": metadata.get("contract", {}).get("shadow_only") is True,
            "contract_no_production_write": metadata.get("contract", {}).get("does_not_write_production_features") is True,
            "contract_no_training": metadata.get("contract", {}).get("does_not_train_model") is True,
            "contract_no_ranking_change": metadata.get("contract", {}).get("does_not_change_production_ranking") is True,
            "promotion_blocked": metadata.get("contract", {}).get("production_promotion_allowed") is False,
        }
        return {
            "status": "OK" if all(checks.values()) else "FAILED",
            "checks": checks,
            "synthetic_output": str(output_path),
        }


def artifact_verification(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {"status": "SKIPPED", "checks": {"artifact_provided": False}}
    metadata_path = path.with_suffix(".json")
    if not path.exists() or not metadata_path.exists():
        return {
            "status": "FAILED",
            "checks": {
                "artifact_exists": path.exists(),
                "metadata_exists": metadata_path.exists(),
            },
        }
    frame = pd.read_parquet(path)
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    contract = metadata.get("contract", {})
    checks = {
        "artifact_exists": True,
        "metadata_exists": True,
        "schema": metadata.get("schema_version") == "alpha-candidate-features.v1",
        "rows_non_empty": len(frame) > 0,
        "required_columns": {"date", "stock_id", *ALPHA_COLUMNS} <= set(frame.columns),
        "no_blocked_columns": not any(column.startswith(BLOCKED_COLUMN_PREFIXES) for column in frame.columns),
        "unique_trade_keys": not frame.duplicated(["date", "stock_id"]).any(),
        "coverage_recorded": set((metadata.get("summary") or {}).get("coverage", {})) == ALPHA_COLUMNS,
        "does_not_write_production_features": contract.get("does_not_write_production_features") is True,
        "does_not_train_model": contract.get("does_not_train_model") is True,
        "does_not_change_production_ranking": contract.get("does_not_change_production_ranking") is True,
        "production_promotion_blocked": contract.get("production_promotion_allowed") is False,
    }
    return {
        "status": "OK" if all(checks.values()) else "FAILED",
        "checks": checks,
        "artifact": repo_path(path),
        "summary": metadata.get("summary", {}),
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
        "schema_version": "alpha-candidate-features-verification.v1",
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
