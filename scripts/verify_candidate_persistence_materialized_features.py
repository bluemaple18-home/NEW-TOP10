#!/usr/bin/env python3
"""驗證 MODEL-EXP 用 candidate persistence materializer 不偷看當天或未來 ranking。"""

from __future__ import annotations

import argparse
import csv
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
    parser = argparse.ArgumentParser(description="verify candidate persistence materialized features")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--output", default="artifacts/model_experiments/candidate_persistence_features_verification_latest.json")
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


def write_ranking(path: Path, rows: list[str]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["stock_id", "stock_name", "close"])
        writer.writeheader()
        for stock_id in rows:
            writer.writerow({"stock_id": stock_id, "stock_name": f"測試{stock_id}", "close": "100"})


def synthetic_verification() -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix="top10-candidate-persistence-materializer-") as tmp:
        root = Path(tmp)
        rankings_dir = root / "rankings"
        rankings_dir.mkdir()
        write_ranking(rankings_dir / "ranking_2026-01-02.csv", ["1111", "2222"])
        write_ranking(rankings_dir / "ranking_2026-01-03.csv", ["3333", "1111"])
        write_ranking(rankings_dir / "ranking_2026-01-04.csv", ["4444", "3333"])

        features = pd.DataFrame(
            [
                {"date": date_text, "stock_id": stock_id}
                for date_text in ["2026-01-02", "2026-01-03", "2026-01-04"]
                for stock_id in ["1111", "2222", "3333", "4444", "5555"]
            ]
        )
        features_path = root / "features.parquet"
        output_path = root / "candidate_persistence_features.parquet"
        features.to_parquet(features_path, index=False)
        completed = subprocess.run(
            [
                sys.executable,
                str(PROJECT_ROOT / "scripts" / "build_candidate_persistence_materialized_features.py"),
                "--rankings-dir",
                str(rankings_dir),
                "--features",
                str(features_path),
                "--date",
                "2026-01-04",
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
        lookup = {
            (str(row.date), str(row.stock_id).zfill(4)): row
            for row in frame.itertuples(index=False)
        }
        checks = {
            "synthetic_command": True,
            "first_date_all_zero": int(lookup[("2026-01-02", "1111")].consecutive_ranked_days) == 0,
            "current_day_new_stock_not_leaked": int(lookup[("2026-01-03", "3333")].consecutive_ranked_days) == 0,
            "prior_day_streak_visible": int(lookup[("2026-01-03", "1111")].consecutive_ranked_days) == 1,
            "future_stock_not_leaked": int(lookup[("2026-01-03", "4444")].ranked_history_count) == 0,
            "non_ranked_stock_present": ("2026-01-04", "5555") in lookup,
            "future_date_updates_after_target_only": int(lookup[("2026-01-04", "3333")].consecutive_ranked_days) == 1,
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
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    contract = metadata.get("contract", {})
    frame = pd.read_parquet(path)
    checks = {
        "artifact_exists": True,
        "metadata_exists": True,
        "schema": metadata.get("schema_version") == "candidate-persistence-materialized-features.v1",
        "rows_non_empty": len(frame) > 0,
        "required_columns": {"date", "stock_id", "consecutive_ranked_days", "streak_bucket", "rank_delta_direction"} <= set(frame.columns),
        "does_not_write_production_features": contract.get("does_not_write_production_features") is True,
        "does_not_train_model": contract.get("does_not_train_model") is True,
        "no_current_day_ranking": contract.get("uses_current_day_ranking_result") is False,
        "no_future_rankings": contract.get("uses_future_rankings") is False,
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
        "schema_version": "candidate-persistence-materialized-features-verification.v1",
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
