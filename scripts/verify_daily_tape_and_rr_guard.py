#!/usr/bin/env python3
"""驗證 daily tape guard 不會把跌停股包裝成主攻。"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.trading.ranking_policy import RankingPolicy  # noqa: E402
from app.trading.tape_guard import add_tape_guard_columns  # noqa: E402
from scripts.build_clawd_publish_payload import (  # noqa: E402
    ai_feature_names,
    classified_publish_sections,
    notification_summary,
    raw_signal_texts,
)


def main() -> int:
    frame = pd.DataFrame(
        [
            {
                "stock_id": "3481",
                "open": 48.35,
                "high": 48.35,
                "low": 48.35,
                "close": 48.35,
                "prev_close": 53.70,
                "model_prob": 0.75,
                "rule_score": 1.5,
                "rule_score_norm": 1.0,
                "avg_value_20d": 34_526_684_178.0,
                "ma20": 45.74,
                "risk_signals": "",
            },
            {
                "stock_id": "9999",
                "open": 100.0,
                "high": 104.0,
                "low": 99.0,
                "close": 103.0,
                "prev_close": 100.0,
                "model_prob": 0.55,
                "rule_score": 1.0,
                "rule_score_norm": 0.7,
                "avg_value_20d": 80_000_000.0,
                "ma20": 98.0,
                "risk_signals": "",
            },
        ]
    )
    guarded = add_tape_guard_columns(frame)
    bad = guarded.loc[guarded["stock_id"] == "3481"].iloc[0]
    assert bad["limit_state"] == "ONE_PRICE_LIMIT_DOWN"
    assert bad["tape_guard_action"] == "EXCLUDE"

    production_ranked = RankingPolicy().apply(frame)
    production_bad = production_ranked.loc[production_ranked["stock_id"] == "3481"].iloc[0]
    assert float(production_bad["risk_adjusted_score"]) >= 0, "production ranking must not silently apply guarded selection"

    guarded_ranked = RankingPolicy().apply(frame, apply_selection_guards=True)
    assert str(guarded_ranked.iloc[0]["stock_id"]) != "3481"
    bad_ranked = guarded_ranked.loc[guarded_ranked["stock_id"] == "3481"].iloc[0]
    assert float(bad_ranked["risk_adjusted_score"]) < 0

    item = {
        "stock_id": "3481",
        "stock_name": "群創",
        "close": 48.35,
        "tape": {
            "open": 48.35,
            "high": 48.35,
            "low": 48.35,
            "close": 48.35,
            "prev_close": 53.70,
            "return_pct": -9.962756,
            "limit_state": "ONE_PRICE_LIMIT_DOWN",
            "tape_guard_action": "EXCLUDE",
            "tape_guard_reason": "一字跌停，當天沒有給出正常換手觀察點",
        },
        "scores": {"model_prob": 0.75, "risk_penalty": 0.0},
        "position": {},
        "trade_plan": {"entry": 48.3, "stop_loss": 44.8, "target_price": 53.2, "risk_reward": 2.67},
        "reference": {"industry_name": "面板業", "concept_tags": ["特斯拉", "低軌衛星"]},
        "reasons": ["W底突破", "AI: obv(+0.59) bb_width(+0.46) ma_squeeze(+0.21)"],
    }
    raw = raw_signal_texts(item["reasons"])
    ai = ai_feature_names(item["reasons"])
    summary = notification_summary(item, raw, ai)
    text = "\n".join([summary["conclusion"], *summary["why_bullets"], summary["translation"], summary["risk"]])
    forbidden = ["買盤有累積", "轉強", "可觀察進場"]
    hits = [word for word in forbidden if word in text]
    assert not hits, f"blocked tape wording still has bullish terms: {hits}\n{text}"
    assert "風險觀察" in summary["conclusion"]

    sections = classified_publish_sections([item], primary_count=1)
    risk_sections = [rows for title, _, _, rows in sections if title == "風險警示"]
    assert risk_sections and risk_sections[0][0]["stock_id"] == "3481", "blocked tape must be publish risk warning, not primary"

    print("DAILY_TAPE_RR_GUARD_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
