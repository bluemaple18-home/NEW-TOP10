#!/usr/bin/env python3
"""驗證 model health report 的 outcome 與狀態聚合邏輯。

使用 TemporaryDirectory 與 monkeypatch 後的 PROJECT_ROOT / ARTIFACTS_DIR，
不讀寫正式模型或正式 artifacts。
"""

from __future__ import annotations

import json
import pickle
import sys
import tempfile
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import scripts.generate_model_health_report as health
from scripts.verify_model_group_acceptance import acceptance_status


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="top10-model-health-") as tmp:
        root = Path(tmp)
        original_root = health.PROJECT_ROOT
        original_artifacts = health.ARTIFACTS_DIR
        health.PROJECT_ROOT = root
        health.ARTIFACTS_DIR = root / "artifacts"
        try:
            prepare_project(root)
            model = health.model_snapshot(root / "models" / "latest_lgbm.pkl")
            rankings = health.evaluate_rankings([root / "artifacts" / "ranking_2026-01-02.csv"], horizon=3, threshold=0.05)
            monitors = health.monitor_summary()
            baseline = health.baseline_summary()
            checks = health.build_checks(model, rankings, monitors, baseline, min_evaluated=2, min_hit_rate=0.4)
            assert model["status"] == "OK"
            assert model["feature_count"] == 2
            assert rankings[0].row_count == 10
            assert rankings[0].evaluated_count == 10
            assert rankings[0].pending_count == 0
            assert rankings[0].missing_count == 0
            assert rankings[0].hit_rate == 0.5
            assert baseline["status"] == "OK"
            assert health.worst_status([check["status"] for check in checks]) == "OK"

            (root / "artifacts" / "psi_report.json").write_text(json.dumps({"status": "CRITICAL"}), encoding="utf-8")
            (root / "artifacts" / "factor_monitor_report.json").write_text(
                json.dumps({"status": "WARN", "summary": {"factor_count": 2, "warn_count": 1}}),
                encoding="utf-8",
            )
            monitors = health.monitor_summary()
            checks = health.build_checks(model, rankings, monitors, baseline, min_evaluated=2, min_hit_rate=0.4)
            assert health.worst_status([check["status"] for check in checks]) == "CRITICAL"

            baseline_path = root / "models" / "baseline_stats.json"
            baseline_payload = json.loads(baseline_path.read_text(encoding="utf-8"))
            baseline_payload["metadata"]["model_feature_count"] = 3
            baseline_payload["metadata"]["monitored_model_feature_count"] = 2
            baseline_payload["metadata"]["skipped_empty_model_features"] = ["factor_c"]
            baseline_path.write_text(json.dumps(baseline_payload), encoding="utf-8")
            baseline = health.baseline_summary()
            checks = health.build_checks(model, rankings, monitors, baseline, min_evaluated=2, min_hit_rate=0.4)
            assert baseline["status"] == "WARN"
            assert any(check["name"] == "monitor.psi_baseline" and check["status"] == "WARN" for check in checks)

            assert acceptance_status(commands_ok=True, auto_retrain_enabled=False, auto_retrain_readiness="BLOCKED") == "OK"
            assert acceptance_status(commands_ok=True, auto_retrain_enabled=True, auto_retrain_readiness="BLOCKED") == "FAILED"
            assert acceptance_status(commands_ok=True, auto_retrain_enabled=True, auto_retrain_readiness="READY") == "OK"
            assert acceptance_status(commands_ok=False, auto_retrain_enabled=False, auto_retrain_readiness="READY") == "FAILED"
        finally:
            health.PROJECT_ROOT = original_root
            health.ARTIFACTS_DIR = original_artifacts
    print("MODEL_HEALTH_VERIFY_OK")
    return 0


def prepare_project(root: Path) -> None:
    (root / "models").mkdir(parents=True)
    (root / "data" / "clean").mkdir(parents=True)
    (root / "artifacts").mkdir(parents=True)
    (root / "models" / "latest_lgbm.pkl").write_bytes(
        pickle.dumps({"model": None, "feature_names": ["factor_a", "factor_b"], "metadata": {"source": "test"}, "calibrator": "test"})
    )
    (root / "models" / "baseline_stats.json").write_text(
        json.dumps(
            {
                "factor_a": {"distribution": [1, 2, 3]},
                "factor_b": {"distribution": [1, 2, 3]},
                "metadata": {
                    "schema_version": "model-baseline-stats.v1",
                    "model_feature_count": 2,
                    "monitored_model_feature_count": 2,
                    "skipped_empty_model_features": [],
                    "missing_model_features": [],
                },
            }
        ),
        encoding="utf-8",
    )
    dates = pd.bdate_range("2026-01-02", periods=5)
    rows = []
    stock_returns = {
        **{f"11{i:02d}": [100, 102, 103, 110, 112] for i in range(1, 6)},
        **{f"12{i:02d}": [100, 99, 98, 96, 95] for i in range(1, 6)},
    }
    for stock_id, close_values in stock_returns.items():
        for index, date in enumerate(dates):
            rows.append(
                {
                    "date": date,
                    "stock_id": stock_id,
                    "open": close_values[index],
                    "close": close_values[index],
                }
            )
    pd.DataFrame(rows).to_parquet(root / "data" / "clean" / "features.parquet", index=False)
    (root / "artifacts" / "ranking_2026-01-02.csv").write_text(
        "\n".join(
            [
                "stock_id,stock_name,risk_adjusted_score",
                *[
                    f"{stock_id},測試{index + 1},{1 - index * 0.01:.2f}"
                    for index, stock_id in enumerate(stock_returns)
                ],
            ]
        ),
        encoding="utf-8",
    )
    (root / "artifacts" / "psi_report.json").write_text(json.dumps({"status": "OK"}), encoding="utf-8")
    (root / "artifacts" / "factor_monitor_report.json").write_text(
        json.dumps({"status": "OK", "summary": {"factor_count": 2, "warn_count": 0}}),
        encoding="utf-8",
    )
    (root / "artifacts" / "industry_momentum_walkforward_shadow.json").write_text(
        json.dumps({"status": "OK", "recommendation": {"decision": "monitor_only"}}),
        encoding="utf-8",
    )


if __name__ == "__main__":
    raise SystemExit(main())
