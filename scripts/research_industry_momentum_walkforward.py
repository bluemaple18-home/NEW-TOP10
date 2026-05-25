"""M13-06：產業動能 leave-one-out shadow ranking / walk-forward 評估。

本腳本只輸出研究 artifact，不修改 production ranking、模型或 API。
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import sys
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.reference_repository import ReferenceRepository
from app.labels import LabelGenerator
from app.trading import MarketRegimeService, RankingPolicy


HORIZON_DAYS = 10
INDUSTRY_MIN_MEMBERS = 5
SECTOR_MIN_MEMBERS = 20
TOP_N = 10


def main() -> int:
    artifacts_dir = PROJECT_ROOT / "artifacts"
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    frame = _load_shadow_frame()
    scored = _score_shadow(frame)
    report = {
        "status": "OK",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "horizon_days": HORIZON_DAYS,
        "method": {
            "industry_factor": "leave-one-out / ex-self",
            "industry_min_members": INDUSTRY_MIN_MEMBERS,
            "sector_min_members": SECTOR_MIN_MEMBERS,
            "production_score_unchanged": True,
            "writes_production_ranking": False,
        },
        "summary": _summary(scored),
        "factor_quality": _factor_quality(scored),
        "walkforward": _walkforward(scored),
        "latest_shadow_top": _latest_top(scored),
        "recommendation": _recommendation(scored),
    }

    json_path = artifacts_dir / "industry_momentum_walkforward_shadow.json"
    md_path = artifacts_dir / "industry_momentum_walkforward_shadow.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_markdown(report), encoding="utf-8")
    print(f"INDUSTRY_MOMENTUM_WALKFORWARD_OK json={json_path} md={md_path}")
    return 0


def _load_shadow_frame() -> pd.DataFrame:
    features = pd.read_parquet(PROJECT_ROOT / "data" / "clean" / "features.parquet")
    features["date"] = pd.to_datetime(features["date"]).dt.normalize()
    features["trade_date"] = features["date"]
    features["stock_id"] = features["stock_id"].astype(str).str.strip()
    duplicated = features.duplicated(["trade_date", "stock_id"], keep=False)
    if duplicated.any():
        sample = features.loc[duplicated, ["trade_date", "stock_id"]].head(5).to_dict(orient="records")
        raise ValueError(f"features 含同股同交易日重複資料：{sample}")

    features = features.sort_values(["stock_id", "trade_date"]).copy()
    for column in ("close", "ma20", "avg_value_20d"):
        features[column] = pd.to_numeric(features.get(column), errors="coerce")
    features["stock_return_20d"] = features.groupby("stock_id")["close"].pct_change(20)
    features["above_ma20"] = (features["close"] > features["ma20"]).astype("Float64")

    repository = ReferenceRepository(PROJECT_ROOT)
    industries = [repository.stock_industry(stock_id) for stock_id in features["stock_id"]]
    features["industry_name"] = [item.industry_name or "未分類" for item in industries]
    features["sector_name"] = [item.sector_name or "未分類" for item in industries]
    features = _add_leave_one_out_factors(features)

    labeled = LabelGenerator(horizon=HORIZON_DAYS).generate_labels(features)
    return labeled.dropna(subset=["future_return"]).copy()


def _add_leave_one_out_factors(features: pd.DataFrame) -> pd.DataFrame:
    frame = features.copy()
    frame = _add_ex_self_mean(
        frame,
        group_cols=["trade_date", "industry_name"],
        value_col="stock_return_20d",
        count_col="industry_member_count",
        output_col="industry_momentum_20d_ex_self",
        min_members=INDUSTRY_MIN_MEMBERS,
    )
    frame = _add_ex_self_mean(
        frame,
        group_cols=["trade_date", "industry_name"],
        value_col="above_ma20",
        count_col="industry_member_count",
        output_col="industry_breadth_ma20_ex_self",
        min_members=INDUSTRY_MIN_MEMBERS,
    )
    frame = _add_ex_self_mean(
        frame,
        group_cols=["trade_date", "sector_name"],
        value_col="stock_return_20d",
        count_col="sector_member_count",
        output_col="sector_rotation_score_20d_ex_self",
        min_members=SECTOR_MIN_MEMBERS,
    )
    return frame


def _add_ex_self_mean(
    frame: pd.DataFrame,
    group_cols: list[str],
    value_col: str,
    count_col: str,
    output_col: str,
    min_members: int,
) -> pd.DataFrame:
    values = pd.to_numeric(frame[value_col], errors="coerce")
    grouped = values.groupby([frame[col] for col in group_cols])
    group_sum = grouped.transform("sum")
    valid_count = grouped.transform("count")
    member_count = frame.groupby(group_cols)["stock_id"].transform("nunique")
    numerator = group_sum - values.fillna(0)
    denominator = valid_count - values.notna().astype(int)
    ex_self = numerator / denominator.where(denominator > 0)
    ex_self = ex_self.where(member_count >= min_members)
    frame[count_col] = member_count
    frame[f"{output_col}_valid_peers"] = denominator
    frame[output_col] = ex_self
    return frame


def _score_shadow(frame: pd.DataFrame) -> pd.DataFrame:
    daily_frames = []
    ranking_policy = RankingPolicy()
    regime_service = MarketRegimeService()
    for trade_date, group in frame.groupby("trade_date"):
        daily = group.copy()
        if len(daily) < 20:
            continue
        if "model_prob" not in daily.columns:
            daily["model_prob"] = 0.5
        if "rule_score" not in daily.columns:
            daily["rule_score"] = _rule_score_proxy(daily)
        daily["rule_score_norm"] = _normalize(daily["rule_score"])
        daily["final_score"] = 0.5 * pd.to_numeric(daily["model_prob"], errors="coerce").fillna(0.5) + 0.5 * daily[
            "rule_score_norm"
        ]
        history = frame[frame["trade_date"] <= trade_date]
        regime = regime_service.evaluate(history, target_date=trade_date)
        ranked = ranking_policy.apply(daily, regime)
        ranked["production_rank"] = ranked["risk_adjusted_score"].rank(ascending=False, method="first")
        ranked["industry_shadow_score"] = _industry_shadow_score(ranked)
        ranked["shadow_risk_adjusted_score"] = (
            ranked["risk_adjusted_score"] + ranked["industry_shadow_score"] * 0.12
        ).clip(lower=0)
        ranked["shadow_rank"] = ranked["shadow_risk_adjusted_score"].rank(ascending=False, method="first")
        daily_frames.append(ranked)
    if not daily_frames:
        raise ValueError("沒有足夠資料可做 shadow ranking")
    return pd.concat(daily_frames, ignore_index=True)


def _rule_score_proxy(df: pd.DataFrame) -> pd.Series:
    score = pd.Series(0.0, index=df.index)
    for column, weight in {
        "break_20d_high": 1.5,
        "close_above_bb_mid": 0.7,
        "macd_bullish_cross": 1.0,
        "volume_spike": 0.8,
        "long_upper_shadow": -0.8,
        "td_sell_setup": -1.0,
        "pattern_m_top": -1.2,
    }.items():
        if column in df.columns:
            score = score + (pd.to_numeric(df[column], errors="coerce").fillna(0) > 0).astype(float) * weight
    return score


def _industry_shadow_score(df: pd.DataFrame) -> pd.Series:
    parts = []
    for column in (
        "industry_momentum_20d_ex_self",
        "industry_breadth_ma20_ex_self",
        "sector_rotation_score_20d_ex_self",
    ):
        values = pd.to_numeric(df[column], errors="coerce")
        parts.append(_daily_percentile(values))
    score = pd.concat(parts, axis=1).mean(axis=1, skipna=True)
    return score.fillna(0.5).clip(0, 1)


def _daily_percentile(values: pd.Series) -> pd.Series:
    if values.notna().sum() < 3 or values.nunique(dropna=True) < 2:
        return pd.Series(0.5, index=values.index)
    return values.rank(pct=True).fillna(0.5)


def _normalize(values: pd.Series) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").fillna(0)
    if numeric.max() <= numeric.min():
        return pd.Series(0.5, index=values.index)
    return ((numeric - numeric.min()) / (numeric.max() - numeric.min())).clip(0, 1)


def _summary(scored: pd.DataFrame) -> dict[str, Any]:
    return {
        "rows": int(len(scored)),
        "stocks": int(scored["stock_id"].nunique()),
        "trade_days": int(scored["trade_date"].nunique()),
        "latest_trade_date": str(scored["trade_date"].max().date()),
        "production_score_columns_present": ["risk_adjusted_score", "shadow_risk_adjusted_score"],
        "shadow_only_columns": ["industry_shadow_score", "shadow_risk_adjusted_score", "shadow_rank"],
    }


def _factor_quality(scored: pd.DataFrame) -> dict[str, Any]:
    factors = [
        "industry_momentum_20d_ex_self",
        "industry_breadth_ma20_ex_self",
        "sector_rotation_score_20d_ex_self",
    ]
    return {
        factor: {
            "coverage": round(float(scored[factor].notna().mean()), 4),
            "latest_coverage": round(
                float(scored.loc[scored["trade_date"] == scored["trade_date"].max(), factor].notna().mean()), 4
            ),
            "member_count_min": int(scored.loc[scored[factor].notna(), _count_col_for(factor)].min())
            if scored[factor].notna().any()
            else None,
            "valid_peer_count_min": int(scored.loc[scored[factor].notna(), _valid_peer_col_for(factor)].min())
            if scored[factor].notna().any()
            else None,
            "valid_peer_count_p10": _round_or_none(scored.loc[scored[factor].notna(), _valid_peer_col_for(factor)].quantile(0.1))
            if scored[factor].notna().any()
            else None,
            "rows_with_lt_2_valid_peers": int((scored.loc[scored[factor].notna(), _valid_peer_col_for(factor)] < 2).sum()),
            "rows_with_lt_3_valid_peers": int((scored.loc[scored[factor].notna(), _valid_peer_col_for(factor)] < 3).sum()),
            "rows_with_lt_5_valid_peers": int((scored.loc[scored[factor].notna(), _valid_peer_col_for(factor)] < 5).sum()),
        }
        for factor in factors
    }


def _count_col_for(factor: str) -> str:
    return "sector_member_count" if factor.startswith("sector_") else "industry_member_count"


def _valid_peer_col_for(factor: str) -> str:
    return f"{factor}_valid_peers"


def _walkforward(scored: pd.DataFrame) -> dict[str, Any]:
    daily_rows = []
    for trade_date, group in scored.groupby("trade_date"):
        if len(group) < TOP_N:
            continue
        production_top = group.nsmallest(TOP_N, "production_rank")
        shadow_top = group.nsmallest(TOP_N, "shadow_rank")
        daily_rows.append(
            {
                "trade_date": str(trade_date.date()),
                "production_mean_return": float(production_top["future_return"].mean()),
                "shadow_mean_return": float(shadow_top["future_return"].mean()),
                "production_hit_rate": float((production_top["future_return"] > 0).mean()),
                "shadow_hit_rate": float((shadow_top["future_return"] > 0).mean()),
                "production_downside": float(production_top["future_return"].clip(upper=0).mean()),
                "shadow_downside": float(shadow_top["future_return"].clip(upper=0).mean()),
                "production_top_industry_concentration": _top_industry_concentration(production_top),
                "shadow_top_industry_concentration": _top_industry_concentration(shadow_top),
                "overlap_count": int(len(set(production_top["stock_id"]) & set(shadow_top["stock_id"]))),
            }
        )
    daily = pd.DataFrame(daily_rows)
    if daily.empty:
        raise ValueError("walk-forward daily rows 為空")
    return {
        "days": int(len(daily)),
        "production_mean_return": _round_or_none(daily["production_mean_return"].mean()),
        "shadow_mean_return": _round_or_none(daily["shadow_mean_return"].mean()),
        "return_uplift": _round_or_none((daily["shadow_mean_return"] - daily["production_mean_return"]).mean()),
        "production_hit_rate": _round_or_none(daily["production_hit_rate"].mean()),
        "shadow_hit_rate": _round_or_none(daily["shadow_hit_rate"].mean()),
        "hit_rate_uplift": _round_or_none((daily["shadow_hit_rate"] - daily["production_hit_rate"]).mean()),
        "production_downside": _round_or_none(daily["production_downside"].mean()),
        "shadow_downside": _round_or_none(daily["shadow_downside"].mean()),
        "production_top_industry_concentration": _round_or_none(daily["production_top_industry_concentration"].mean()),
        "shadow_top_industry_concentration": _round_or_none(daily["shadow_top_industry_concentration"].mean()),
        "average_overlap_count": _round_or_none(daily["overlap_count"].mean()),
    }


def _top_industry_concentration(top: pd.DataFrame) -> float:
    if top.empty:
        return 0.0
    return float(top["industry_name"].value_counts(normalize=True).iloc[0])


def _latest_top(scored: pd.DataFrame) -> list[dict[str, Any]]:
    latest = scored[scored["trade_date"] == scored["trade_date"].max()].nsmallest(TOP_N, "shadow_rank")
    columns = [
        "stock_id",
        "stock_name",
        "industry_name",
        "sector_name",
        "risk_adjusted_score",
        "industry_shadow_score",
        "shadow_risk_adjusted_score",
        "production_rank",
        "shadow_rank",
        "future_return",
    ]
    return latest[[column for column in columns if column in latest.columns]].to_dict(orient="records")


def _recommendation(scored: pd.DataFrame) -> dict[str, str]:
    walkforward = _walkforward(scored)
    return_uplift = walkforward["return_uplift"] or 0
    hit_rate_uplift = walkforward["hit_rate_uplift"] or 0
    concentration_delta = (walkforward["shadow_top_industry_concentration"] or 0) - (
        walkforward["production_top_industry_concentration"] or 0
    )
    if return_uplift > 0.005 and hit_rate_uplift >= 0 and concentration_delta <= 0.1:
        return {
            "decision": "production_candidate_needs_card",
            "reason": "ex-self 產業 shadow ranking 有正向 return uplift，且未明顯增加產業集中；仍需另開 production integration / 回測卡。",
        }
    if return_uplift > 0:
        return {
            "decision": "monitor_only",
            "reason": "shadow 有些微正向結果，但 hit rate 或集中度條件不足，先保留監控。",
        }
    return {
        "decision": "reject",
        "reason": "ex-self shadow ranking 未改善 production baseline，不建議進 production。",
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        "# M13-06 Industry Momentum Walkforward Shadow",
        "",
        f"- 狀態：`{report['status']}`",
        f"- 產生時間：`{report['generated_at']}`",
        f"- horizon：`{report['horizon_days']}` trading days",
        "",
        "## 結論",
        "",
        f"- 決策：`{report['recommendation']['decision']}`",
        f"- 理由：{report['recommendation']['reason']}",
        "",
        "## Method",
        "",
    ]
    for key, value in report["method"].items():
        lines.append(f"- `{key}`：{value}")
    lines.extend(["", "## Walkforward", ""])
    for key, value in report["walkforward"].items():
        lines.append(f"- `{key}`：{value}")
    lines.extend(["", "## Factor Quality", ""])
    for factor, payload in report["factor_quality"].items():
        lines.append(f"- `{factor}`：{payload}")
    lines.extend(["", "## Latest Shadow Top", ""])
    for item in report["latest_shadow_top"]:
        lines.append(
            "- "
            f"{item.get('stock_id')} {item.get('stock_name')} "
            f"{item.get('industry_name')} shadow_rank={item.get('shadow_rank')} "
            f"production_rank={item.get('production_rank')}"
        )
    lines.extend(
        [
            "",
            "## 邊界",
            "",
            "- 本研究不修改 production `risk_adjusted_score`。",
            "- 本研究不修改 LightGBM feature list。",
            "- shadow score 只存在本 artifact，不寫入正式 ranking CSV/API。",
            "",
        ]
    )
    return "\n".join(lines)


def _round_or_none(value: Any, digits: int = 4) -> float | None:
    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


if __name__ == "__main__":
    raise SystemExit(main())
