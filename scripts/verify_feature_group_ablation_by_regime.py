#!/usr/bin/env python3
"""驗證 by-regime feature group 消融研究腳本的核心門檻。

此驗證只測純函式，不讀 production data、不訓練模型。
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import research_feature_group_ablation_by_regime as ablation  # noqa: E402

ARTIFACT_PATH = PROJECT_ROOT / "artifacts" / "feature_group_ablation_by_regime_verification_latest.json"


def main() -> int:
    checks = {
        "direction_consistency_positive": ablation.ic_direction_consistency(pd.Series([0.1, 0.2, -0.1, 0.3])) == 0.75,
        "direction_consistency_negative": ablation.ic_direction_consistency(pd.Series([-0.1, -0.2, 0.1, -0.3])) == 0.75,
        "status_shadow_candidate_requires_strength": ablation.metric_status(
            days=12,
            min_days=8,
            abs_ic_mean=0.05,
            ic_t_stat=1.5,
            direction_consistency=0.7,
            spread_mean=0.006,
        )
        == "SHADOW_CANDIDATE",
        "status_watch_when_t_stat_weak": ablation.metric_status(
            days=12,
            min_days=8,
            abs_ic_mean=0.05,
            ic_t_stat=0.3,
            direction_consistency=0.7,
            spread_mean=0.006,
        )
        == "WATCH",
        "status_weak_when_direction_unstable": ablation.metric_status(
            days=12,
            min_days=8,
            abs_ic_mean=0.05,
            ic_t_stat=1.5,
            direction_consistency=0.5,
            spread_mean=0.006,
        )
        == "WEAK_OR_NOISY",
        "status_insufficient_days": ablation.metric_status(
            days=3,
            min_days=8,
            abs_ic_mean=0.1,
            ic_t_stat=2.0,
            direction_consistency=0.8,
            spread_mean=0.01,
        )
        == "INSUFFICIENT_DAYS",
        "daily_top_bottom_spread_positive": _spread_positive(),
    }
    status = "OK" if all(checks.values()) else "FAILED"
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(
        json.dumps(
            {
                "schema_version": "feature-group-ablation-by-regime-verification.v1",
                "status": status,
                "checks": checks,
                "note": "pure-function verification; no production data writes and no model training",
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    if status == "OK":
        print(f"FEATURE_GROUP_ABLATION_BY_REGIME_OK output={ARTIFACT_PATH}")
        return 0
    print(f"FEATURE_GROUP_ABLATION_BY_REGIME_FAILED output={ARTIFACT_PATH}")
    return 1


def _spread_positive() -> bool:
    frame = pd.DataFrame(
        {
            "trade_date": ["2026-01-02"] * 10,
            "stock_id": [str(index).zfill(4) for index in range(10)],
            "factor": list(range(10)),
            "future_return": [value / 100 for value in range(10)],
        }
    )
    spreads = ablation.daily_top_bottom_spreads(frame)
    return len(spreads) == 1 and round(float(spreads.iloc[0]), 4) > 0


if __name__ == "__main__":
    raise SystemExit(main())
