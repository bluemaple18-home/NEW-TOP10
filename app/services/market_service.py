"""看盤台 service。

這層是 UI/BFF 的資料組裝邊界；回測績效會另建獨立 service，不混在這裡。
"""

from __future__ import annotations

from typing import Any

import pandas as pd

from app.contracts import (
    ApiHealth,
    ExposureBreakdownItem,
    LatestRankingResponse,
    RankingItem,
    RankingReferenceSummary,
    StockBar,
    StockOhlcvResponse,
)
from app.data.market_repository import MarketRepository
from app.data.reference_repository import ReferenceRepository
from app.trading import MarketRegimeService, PortfolioPolicy, TradePlanService


MARKET_OPTIONAL_FIELDS = [
    "ma5",
    "ma10",
    "ma20",
    "ma60",
    "bb_upper",
    "bb_middle",
    "bb_lower",
    "macd",
    "macd_signal",
    "macd_hist",
    "k",
    "d",
    "rsi",
    "volume_ratio_20d",
    "candle_doji",
    "candle_dragonfly_doji",
    "candle_tombstone_doji",
    "candle_hammer",
    "candle_hanging_man",
    "candle_shooting_star",
    "candle_inverted_hammer",
    "candle_bull_marubozu",
    "candle_bear_marubozu",
    "candle_bull_engulfing",
    "candle_bear_engulfing",
    "candle_bull_harami",
    "candle_bear_harami",
    "candle_piercing",
    "candle_dark_cloud",
    "candle_morning_star",
    "candle_evening_star",
    "candle_3white",
    "candle_3black",
    "td_count",
    "td_buy_setup",
    "td_sell_setup",
    "pattern_w_bottom",
    "pattern_m_top",
    "pattern_neckline",
    "pattern_stop_loss",
    "pattern_resistance",
]


def json_value(value: Any) -> Any:
    """把 pandas/numpy 型別轉成 JSON 友善值。"""
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return value.item()
    return value


class MarketService:
    def __init__(self, repository: MarketRepository, reference_repository: ReferenceRepository | None = None):
        self.repository = repository
        self.reference_repository = reference_repository or ReferenceRepository(repository.project_root)
        self.market_regime_service = MarketRegimeService()
        self.portfolio_policy = PortfolioPolicy()
        self.trade_plan_service = TradePlanService()

    def health(self) -> ApiHealth:
        return ApiHealth(
            ok=True,
            features_exists=self.repository.features_exists(),
            ranking_files=self.repository.ranking_file_count(),
        )

    def latest_ranking(self, limit: int = 10) -> LatestRankingResponse:
        ranking, ranking_date = self.repository.load_latest_ranking()
        features = self.repository.load_features()
        names = self._latest_stock_names(features)
        ranking = self._with_score_decomposition_fallback(ranking)
        ranking = self._with_portfolio_allocation_fallback(ranking, features)
        ranking = self._sort_ranking_for_display(ranking)
        ranking = self.reference_repository.annotate_ranking(ranking)

        if ranking.empty:
            stock_ids = features.groupby("stock_id").tail(1)["stock_id"].head(limit).tolist()
            items = [RankingItem(stock_id=stock_id, stock_name=names.get(stock_id, stock_id)) for stock_id in stock_ids]
            return LatestRankingResponse(
                date=None,
                items=items,
                reference_summary=RankingReferenceSummary(notes="ranking artifact 為空。"),
            )

        items = []
        display_ranking = ranking.head(limit).copy()
        for _, row in display_ranking.iterrows():
            stock_id = str(row["stock_id"]).strip()
            item = {key: json_value(value) for key, value in row.to_dict().items()}
            item["stock_id"] = stock_id
            item["stock_name"] = item.get("stock_name") or names.get(stock_id, stock_id)
            items.append(RankingItem(**item))

        return LatestRankingResponse(date=ranking_date, items=items, reference_summary=self._reference_summary(display_ranking))

    def _with_score_decomposition_fallback(self, ranking: pd.DataFrame) -> pd.DataFrame:
        """讓舊 ranking artifact 也能滿足 M7 API contract。"""
        if ranking.empty:
            return ranking
        result = ranking.copy()
        had_decomposition = {"prediction_score", "setup_score", "quality_score", "risk_penalty"}.issubset(result.columns)
        if "prediction_score" not in result.columns:
            source = result["model_prob"] if "model_prob" in result.columns else result.get("final_score", 0.5)
            result["prediction_score"] = pd.to_numeric(source, errors="coerce").fillna(0.5).clip(0, 1)
        if "setup_score" not in result.columns:
            if "rule_score" in result.columns:
                score = pd.to_numeric(result["rule_score"], errors="coerce").fillna(0)
                min_score = score.min()
                max_score = score.max()
                result["setup_score"] = 0.5 if max_score <= min_score else ((score - min_score) / (max_score - min_score)).clip(0, 1)
            else:
                result["setup_score"] = 0.5
        if "quality_score" not in result.columns:
            result["quality_score"] = 0.5
        if "risk_penalty" not in result.columns:
            result["risk_penalty"] = 0.0
        if "risk_adjusted_score" not in result.columns or not had_decomposition:
            result["risk_adjusted_score"] = (
                result["prediction_score"] + result["setup_score"] + result["quality_score"] - result["risk_penalty"]
            ).clip(lower=0)
        return result

    def _with_portfolio_allocation_fallback(self, ranking: pd.DataFrame, features: pd.DataFrame) -> pd.DataFrame:
        """讓舊 ranking artifact 也有保守 M9 欄位。"""
        if ranking.empty:
            return ranking
        required = {"suggested_weight", "max_position_weight", "gross_exposure", "allocated_exposure", "cash_weight", "exposure_note"}
        if required.issubset(ranking.columns):
            return ranking
        regime = self.market_regime_service.evaluate(features)
        ranked = self._sort_ranking_for_display(ranking)
        return self.portfolio_policy.apply(ranked, regime)

    def _sort_ranking_for_display(self, ranking: pd.DataFrame) -> pd.DataFrame:
        if ranking.empty or "risk_adjusted_score" not in ranking.columns:
            return ranking
        result = ranking.copy()
        result["risk_adjusted_score"] = pd.to_numeric(result["risk_adjusted_score"], errors="coerce")
        return result.sort_values("risk_adjusted_score", ascending=False, kind="mergesort").copy()

    def market_regime(self):
        features = self.repository.load_features()
        return self.market_regime_service.evaluate(features)

    def stock_ohlcv(self, stock_id: str, limit: int = 1200) -> StockOhlcvResponse | None:
        features = self.repository.load_features()
        ranking, _ = self.repository.load_latest_ranking()
        target = str(stock_id).strip()
        stock_df = features[features["stock_id"] == target].tail(limit)

        if stock_df.empty:
            return None

        existing_optional_fields = [field for field in MARKET_OPTIONAL_FIELDS if field in stock_df.columns]
        bars = []
        for _, row in stock_df.iterrows():
            date = pd.Timestamp(row["date"])
            record = {
                "timestamp": int(date.timestamp() * 1000),
                "time": date.strftime("%Y-%m-%d"),
                "open": json_value(row["open"]),
                "high": json_value(row["high"]),
                "low": json_value(row["low"]),
                "close": json_value(row["close"]),
                "volume": json_value(row["volume"]),
            }
            for field in existing_optional_fields:
                record[field] = json_value(row[field])
            bars.append(StockBar(**record))

        return StockOhlcvResponse(
            stock_id=target,
            stock_name=self._resolve_stock_name(target, stock_df, ranking),
            items=bars,
        )

    def clear_cache(self) -> None:
        self.repository.clear_cache()
        self.reference_repository.clear_cache()

    def _reference_summary(self, ranking: pd.DataFrame) -> RankingReferenceSummary:
        if ranking.empty:
            return RankingReferenceSummary()
        weights = self._portfolio_weights_for_summary(ranking)
        industry_exposure = self._exposure_breakdown(ranking, "industry_name", weights)
        sector_exposure = self._exposure_breakdown(ranking, "sector_name", weights)
        etf_ids: set[str] = set()
        if "major_etfs" in ranking.columns:
            for value in ranking["major_etfs"].dropna():
                etf_ids.update(etf_id for etf_id in str(value).split("|") if etf_id)
        top_industry = industry_exposure[0].weight if industry_exposure else None
        return RankingReferenceSummary(
            industry_exposure=industry_exposure,
            sector_exposure=sector_exposure,
            etf_overlap_count=len(etf_ids),
            top_industry_concentration=top_industry,
            notes="曝險以建議權重估算；若無建議權重則以顯示清單等權估算。",
        )

    def _portfolio_weights_for_summary(self, ranking: pd.DataFrame) -> pd.Series:
        if "suggested_weight" in ranking.columns:
            weights = pd.to_numeric(ranking["suggested_weight"], errors="coerce").fillna(0)
            if weights.sum() > 0:
                return weights / weights.sum()
        return pd.Series([1 / len(ranking)] * len(ranking), index=ranking.index)

    def _exposure_breakdown(self, ranking: pd.DataFrame, column: str, weights: pd.Series) -> list[ExposureBreakdownItem]:
        if column not in ranking.columns:
            return []
        frame = pd.DataFrame(
            {
                "name": ranking[column].fillna("未分類").astype(str),
                "weight": weights,
            }
        )
        grouped = frame.groupby("name", dropna=False).agg(weight=("weight", "sum"), count=("name", "size"))
        grouped = grouped.sort_values("weight", ascending=False)
        return [
            ExposureBreakdownItem(name=str(name), weight=round(float(row["weight"]), 6), count=int(row["count"]))
            for name, row in grouped.iterrows()
        ]

    def _latest_stock_names(self, features: pd.DataFrame) -> dict[str, str]:
        if "stock_name" not in features.columns:
            return {}

        latest = features.dropna(subset=["stock_id"]).groupby("stock_id").tail(1)
        return {
            str(row["stock_id"]): str(row["stock_name"])
            for _, row in latest.iterrows()
            if pd.notna(row.get("stock_name"))
        }

    def _resolve_stock_name(self, stock_id: str, stock_df: pd.DataFrame, ranking: pd.DataFrame) -> str:
        ranking_match = ranking[ranking["stock_id"] == stock_id] if not ranking.empty else pd.DataFrame()
        ranking_name = (
            str(ranking_match.iloc[0]["stock_name"])
            if not ranking_match.empty and pd.notna(ranking_match.iloc[0].get("stock_name"))
            else None
        )
        feature_name = (
            str(stock_df["stock_name"].dropna().iloc[-1])
            if "stock_name" in stock_df.columns and not stock_df["stock_name"].dropna().empty
            else None
        )
        return ranking_name or feature_name or stock_id
