#!/usr/bin/env python3
"""封閉 OOS gate 單元驗證。"""

from __future__ import annotations

from pathlib import Path
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.modeling.sealed_oos import SealedOOSConfig, build_sealed_oos_split, evaluate_sealed_oos_model


class SignalModel:
    def predict(self, frame: pd.DataFrame):
        return pd.to_numeric(frame["signal"], errors="coerce").fillna(0.0).clip(0, 1).to_numpy()

    def feature_name(self) -> list[str]:
        return ["signal"]


def main() -> int:
    verify_split_excludes_sealed_and_embargo()
    verify_gate_passes_predictive_model()
    verify_gate_rejects_missing_split_metadata()
    print("SEALED_OOS_VERIFY_OK")
    return 0


def verify_split_excludes_sealed_and_embargo() -> None:
    frame = _labeled_fixture()
    config = _config()
    split = build_sealed_oos_split(frame, config, horizon=2, threshold=0.05)
    assert split.metadata["development_trade_days"] == 55
    assert split.metadata["embargo_trade_days"] == 5
    assert split.metadata["sealed_trade_days"] == 20
    assert split.development["trade_date"].max() < split.embargo["trade_date"].min()
    assert split.embargo["trade_date"].max() < split.sealed["trade_date"].min()


def verify_gate_passes_predictive_model() -> None:
    frame = _labeled_fixture()
    config = _config()
    split = build_sealed_oos_split(frame, config, horizon=2, threshold=0.05)
    payload = {
        "model": SignalModel(),
        "feature_names": ["signal"],
        "metadata": {
            "horizon": 2,
            "threshold": 0.05,
            "feature_names": ["signal"],
            "sealed_oos": split.metadata,
        },
    }
    report = evaluate_sealed_oos_model(
        model_payload=payload,
        labeled_frame=frame,
        config=config,
        horizon=2,
        threshold=0.05,
    )
    assert report["status"] == "OK", report
    assert report["metrics"]["auc"] > 0.99
    assert report["metrics"]["top_n_return_uplift"] > 0


def verify_gate_rejects_missing_split_metadata() -> None:
    payload = {
        "model": SignalModel(),
        "feature_names": ["signal"],
        "metadata": {"horizon": 2, "threshold": 0.05},
    }
    report = evaluate_sealed_oos_model(
        model_payload=payload,
        labeled_frame=_labeled_fixture(),
        config=_config(),
        horizon=2,
        threshold=0.05,
    )
    assert report["status"] == "FAILED"
    assert any("sealed_oos" in failure for failure in report["failures"])


def _config() -> SealedOOSConfig:
    return SealedOOSConfig(
        sealed_trade_days=20,
        embargo_trade_days=5,
        min_train_trade_days=50,
        min_sealed_trade_days=20,
        min_sealed_samples=80,
        min_positive_labels=10,
        min_negative_labels=10,
        min_auc=0.55,
        min_top_n_return_uplift=0.0,
        min_top_n_hit_rate_uplift=0.0,
        top_n=2,
        require_model_split_metadata=True,
    )


def _labeled_fixture() -> pd.DataFrame:
    rows = []
    dates = pd.bdate_range("2024-01-02", periods=80)
    stock_ids = ["1101", "1102", "1103", "1104", "1105"]
    for date_index, date in enumerate(dates):
        for stock_index, stock_id in enumerate(stock_ids):
            signal = ((date_index + stock_index) % len(stock_ids)) / (len(stock_ids) - 1)
            target = int(signal >= 0.5)
            rows.append(
                {
                    "date": date,
                    "trade_date": date.normalize(),
                    "stock_id": stock_id,
                    "signal": signal,
                    "target": target,
                    "future_return": 0.08 if target else -0.03,
                }
            )
    return pd.DataFrame(rows)


if __name__ == "__main__":
    raise SystemExit(main())
