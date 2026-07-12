#!/usr/bin/env python3
"""驗證 VWAP 成本線 materializer 的安全邊界與基本公式。"""

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
VWAP_COLUMNS = {
    "daily_vwap",
    "rolling_vwap_5d",
    "rolling_vwap_20d",
    "close_vs_vwap_5d",
    "close_vs_vwap_20d",
    "vwap_reclaim_20d",
    "vwap_loss_20d",
}
BLOCKED_COLUMN_PREFIXES = ("future_", "target", "label_", "next_")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify VWAP cost-basis research-only features")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/vwap_cost_basis_features_verification_latest.json")
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
    for day in range(1, 23):
        close = 100 + day
        volume = 1000 + day * 10
        rows.append(
            {
                "date": f"2026-01-{day:02d}",
                "stock_id": "1111",
                "open": close - 1,
                "high": close + 2,
                "low": close - 2,
                "close": close,
                "volume": volume,
                "value": close * volume,
            }
        )
    return pd.DataFrame(rows)


def synthetic_verification() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="top10-vwap-cost-basis-") as tmp:
        root = Path(tmp)
        features_path = root / "features.parquet"
        output_path = root / "vwap_cost_basis_features.parquet"
        synthetic_features().to_parquet(features_path, index=False)
        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "build_vwap_cost_basis_features.py"),
                "--features",
                str(features_path),
                "--date",
                "2026-01-22",
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
        last = frame.sort_values(["date", "stock_id"]).iloc[-1]
        expected_5d = sum((100 + day) * (1000 + day * 10) for day in range(18, 23)) / sum(
            1000 + day * 10 for day in range(18, 23)
        )
        checks = {
            "synthetic_command": True,
            "schema": metadata.get("schema_version") == "vwap-cost-basis-features.v1",
            "required_columns": {"date", "stock_id", *VWAP_COLUMNS} <= set(frame.columns),
            "no_blocked_columns": not any(column.startswith(BLOCKED_COLUMN_PREFIXES) for column in frame.columns),
            "unique_trade_keys": not frame.duplicated(["date", "stock_id"]).any(),
            "daily_vwap_unit_usable": metadata.get("summary", {}).get("diagnostics", {}).get("value_volume_unit_usable") is True,
            "daily_vwap_expected": abs(float(last.daily_vwap) - 122.0) < 1e-9,
            "rolling_vwap_5d_expected": abs(float(last.rolling_vwap_5d) - expected_5d) < 1e-9,
            "contract_shadow_only": metadata.get("contract", {}).get("shadow_only") is True,
            "contract_first_wave": metadata.get("contract", {}).get("research_lane") == "FIRST_WAVE_INSERT",
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
        "schema": metadata.get("schema_version") == "vwap-cost-basis-features.v1",
        "rows_non_empty": len(frame) > 0,
        "required_columns": {"date", "stock_id", *VWAP_COLUMNS} <= set(frame.columns),
        "no_blocked_columns": not any(column.startswith(BLOCKED_COLUMN_PREFIXES) for column in frame.columns),
        "unique_trade_keys": not frame.duplicated(["date", "stock_id"]).any(),
        "coverage_recorded": set((metadata.get("summary") or {}).get("coverage", {})) == VWAP_COLUMNS,
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
        "schema_version": "vwap-cost-basis-features-verification.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "failed_sections": failed,
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
    print(json.dumps({"status": report["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
