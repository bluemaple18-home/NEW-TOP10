"""本週動能候選決策 service。"""

from __future__ import annotations

from collections import Counter
from typing import Any

import pandas as pd

from app.contracts import (
    InvestmentSettingsContract,
    OpportunityComponentContract,
    RankingItem,
    WeeklyCandidateContract,
    WeeklyCandidateLayerContract,
    WeeklyCandidatesResponse,
    WeeklyChangeContract,
    WeeklyMarketSummaryContract,
    WeeklyModelPoolItemContract,
    WeeklySettingsEffectContract,
    WeeklySnapshotContract,
)
from app.services.market_service import MarketService, json_value


STATUS_ORDER: list[str] = ["可分批", "等回測", "觀察突破", "續強觀察", "暫停操作"]


class WeeklyDecisionService:
    """把模型排行、設定、市場狀態收斂成本週候選 contract。"""

    def __init__(self, market_service: MarketService):
        self.market_service = market_service

    def weekly_candidates(self, settings: InvestmentSettingsContract, limit: int = 10) -> WeeklyCandidatesResponse:
        ranking, snapshot_payload = self.market_service.repository.load_latest_weekly_snapshot()
        ranking_date = None
        snapshot = None
        if snapshot_payload:
            ranking_date = snapshot_payload.get("ranking_date") or snapshot_payload.get("snapshot_date")
            snapshot = WeeklySnapshotContract(
                snapshot_date=snapshot_payload.get("snapshot_date"),
                ranking_date=snapshot_payload.get("ranking_date"),
                week_version=snapshot_payload.get("week_version"),
                source=snapshot_payload.get("source") or "weekly_snapshot",
                artifact_path=snapshot_payload.get("artifact_path"),
                generated_at=snapshot_payload.get("generated_at"),
                model_pool_count=int(snapshot_payload.get("model_pool_count") or len(ranking)),
            )
        else:
            ranking, ranking_date = self.market_service.repository.load_latest_ranking()
            snapshot = WeeklySnapshotContract(
                snapshot_date=ranking_date,
                ranking_date=ranking_date,
                week_version=ranking_date,
                source="latest_ranking_fallback",
                model_pool_count=len(ranking),
            )
        features = self.market_service.repository.load_features()
        names = self.market_service._latest_stock_names(features)
        ranking = self.market_service._with_score_decomposition_fallback(ranking)
        ranking = self.market_service._with_portfolio_allocation_fallback(ranking, features)
        ranking = self.market_service._sort_ranking_for_display(ranking)
        ranking = self.market_service.reference_repository.annotate_ranking(ranking)

        regime = self.market_service.market_regime()
        stock_rows = ranking.head(limit).copy()
        model_pool = [
            self._model_pool_item_from_row(row=row, priority=index + 1, names=names)
            for index, (_, row) in enumerate(stock_rows.iterrows())
        ]
        stock_candidates = [
            self._candidate_from_row(row=row, priority=index + 1, settings=settings, names=names)
            for index, (_, row) in enumerate(stock_rows.iterrows())
        ]
        visible_stock_candidates = stock_candidates if settings.target_type in ("stocks", "both") else []
        visible_rows = stock_rows if settings.target_type in ("stocks", "both") else stock_rows.iloc[0:0]
        status_counts = Counter(candidate.status for candidate in visible_stock_candidates)
        candidate_layer = self._candidate_layer(
            settings=settings,
            model_pool=model_pool,
            visible_candidates=visible_stock_candidates,
        )

        return WeeklyCandidatesResponse(
            date=ranking_date,
            version_label=ranking_date or "本機資料",
            snapshot=snapshot,
            settings=settings,
            status_order=STATUS_ORDER,
            market_summary=self._market_summary(
                rows=visible_rows,
                candidates=visible_stock_candidates,
                settings=settings,
                regime_label=regime.label,
                status_counts=status_counts,
            ),
            model_pool_count=snapshot.model_pool_count if snapshot else len(ranking),
            model_pool=model_pool,
            candidate_layer=candidate_layer,
            stock_candidates=visible_stock_candidates,
            etf_candidates=[],
            other_candidates=[],
            week_changes=self._week_changes(settings=settings),
        )

    def _candidate_from_row(
        self,
        row: pd.Series,
        priority: int,
        settings: InvestmentSettingsContract,
        names: dict[str, str],
    ) -> WeeklyCandidateContract:
        item = {key: json_value(value) for key, value in row.to_dict().items()}
        stock_id = str(item.get("stock_id", "")).strip()
        item["stock_id"] = stock_id
        item["stock_name"] = item.get("stock_name") or names.get(stock_id, stock_id)
        ranking_item = RankingItem(**item)
        status = self._status(ranking_item, settings)

        return WeeklyCandidateContract(
            priority=priority,
            target_type="stock",
            stock_id=stock_id,
            stock_name=ranking_item.stock_name,
            status=status,
            risk_label=self._risk_label(ranking_item, settings),
            next_step=self._next_step(ranking_item, status, settings),
            key_price=self._key_price(ranking_item),
            primary_reasons=self._primary_reasons(ranking_item),
            ranking=ranking_item,
        )

    def _model_pool_item_from_row(
        self,
        row: pd.Series,
        priority: int,
        names: dict[str, str],
    ) -> WeeklyModelPoolItemContract:
        item = {key: json_value(value) for key, value in row.to_dict().items()}
        stock_id = str(item.get("stock_id", "")).strip()
        item["stock_id"] = stock_id
        item["stock_name"] = item.get("stock_name") or names.get(stock_id, stock_id)
        return WeeklyModelPoolItemContract(
            priority=priority,
            target_type="stock",
            stock_id=stock_id,
            stock_name=item.get("stock_name"),
            ranking=RankingItem(**item),
        )

    def _candidate_layer(
        self,
        settings: InvestmentSettingsContract,
        model_pool: list[WeeklyModelPoolItemContract],
        visible_candidates: list[WeeklyCandidateContract],
    ) -> WeeklyCandidateLayerContract:
        stock_pool_count = sum(1 for item in model_pool if item.target_type == "stock")
        etf_pool_count = sum(1 for item in model_pool if item.target_type == "etf")
        hidden_by_settings = len(model_pool) - len(visible_candidates)
        effects: list[WeeklySettingsEffectContract] = []
        if settings.target_type == "etfs" and stock_pool_count:
            effects.append(
                WeeklySettingsEffectContract(
                    reason="target_type",
                    count=stock_pool_count,
                    notes="目前設定只看 ETF，因此個股模型初選池不進本週候選。",
                )
            )
        if settings.target_type == "stocks" and etf_pool_count:
            effects.append(
                WeeklySettingsEffectContract(
                    reason="target_type",
                    count=etf_pool_count,
                    notes="目前設定只看個股，因此 ETF 模型初選池不進本週候選。",
                )
            )
        return WeeklyCandidateLayerContract(
            model_pool_count=len(model_pool),
            stock_model_pool_count=stock_pool_count,
            etf_model_pool_count=etf_pool_count,
            visible_candidate_count=len(visible_candidates),
            hidden_by_settings_count=max(hidden_by_settings, 0),
            settings_effects=effects,
        )

    def _market_summary(
        self,
        rows: pd.DataFrame,
        candidates: list[WeeklyCandidateContract],
        settings: InvestmentSettingsContract,
        regime_label: str,
        status_counts: Counter[str],
    ) -> WeeklyMarketSummaryContract:
        average_score = self._average([candidate.ranking.risk_adjusted_score for candidate in candidates])
        high_quality_count = sum((candidate.ranking.risk_adjusted_score or 0) >= 0.72 for candidate in candidates)
        dominant_groups = self._dominant_groups(rows)
        market_state = {"RISK_ON": "大盤偏進攻", "RISK_OFF": "大盤偏防守"}.get(regime_label, "大盤中性")
        operation = self._operation_environment(regime_label, settings)
        opportunity = (
            "候選品質尚可"
            if high_quality_count >= 3 and average_score >= 0.7
            else "少數標的可觀察"
            if high_quality_count > 0
            else "本週機會偏薄"
        )

        return WeeklyMarketSummaryContract(
            market_state=market_state,
            operation_environment=operation,
            opportunity_quality=opportunity,
            opportunity_components=[
                OpportunityComponentContract(label="大盤條件", value=market_state, notes=operation),
                OpportunityComponentContract(label="符合設定數量", value=f"{len(candidates)} 檔"),
                OpportunityComponentContract(
                    label="操作狀態分布",
                    value="、".join(f"{status} {status_counts.get(status, 0)}" for status in STATUS_ORDER),
                ),
                OpportunityComponentContract(
                    label="主要壓低品質原因",
                    value=self._quality_drag_reason(candidates),
                ),
            ],
            dominant_groups=dominant_groups,
            risk_alerts=self._risk_alerts(settings),
            setting_interpretation=(
                f"{self._risk_style_label(settings.risk_style)}、{self._holding_period_label(settings.holding_period)}，"
                f"以{self._entry_preference_label(settings.entry_preference)}節奏解讀。"
            ),
        )

    def _status(self, item: RankingItem, settings: InvestmentSettingsContract) -> str:
        score = item.risk_adjusted_score if item.risk_adjusted_score is not None else item.model_prob or 0
        risk_reward = item.risk_reward
        risk_penalty = item.risk_penalty or 0
        if (risk_reward is not None and risk_reward < 1.6) or risk_penalty >= 0.35:
            return "暫停操作"
        if settings.entry_preference == "pullback" and score >= 0.82:
            return "等回測"
        if score >= 0.82:
            return "可分批"
        if score >= 0.73:
            return "等回測"
        if score >= 0.66:
            return "觀察突破"
        return "續強觀察"

    def _risk_label(self, item: RankingItem, settings: InvestmentSettingsContract) -> str:
        risk_reward = item.risk_reward or 0
        if settings.risk_style == "conservative" and risk_reward < 2.2:
            return "風險偏高"
        if risk_reward >= 3:
            return "風險中低"
        if risk_reward >= 2:
            return "風險中"
        return "風險偏高"

    def _next_step(self, item: RankingItem, status: str, settings: InvestmentSettingsContract) -> str:
        price = self._price(item.close)
        if status == "可分批":
            return f"接近 {price} 可分批，先守停損"
        if status == "等回測":
            return "突破後不追，等量價確認" if settings.entry_preference == "breakout" else f"等回測 {price} 附近再看"
        if status == "觀察突破":
            return "等突破與量能同步確認"
        if status == "續強觀察":
            return "趨勢仍在，等下一個整理點"
        return "暫停新進，等風險條件解除"

    def _key_price(self, item: RankingItem) -> str:
        risk_reward = f"風報比 {item.risk_reward:.2f}" if item.risk_reward is not None else "風報比待補"
        return f"{self._price(item.close)}｜{risk_reward}"

    def _primary_reasons(self, item: RankingItem) -> list[str]:
        reasons = []
        if item.reasons and "綜合技術指標轉強" in item.reasons:
            reasons.append("綜合技術指標轉強")
        if not reasons:
            reasons.append("模型初選 + 動能排序")
        return reasons[:2]

    def _dominant_groups(self, rows: pd.DataFrame) -> list[str]:
        if rows.empty:
            return []
        names = []
        for column in ("industry_name", "sector_name"):
            if column in rows.columns:
                names.extend(str(value).strip() for value in rows[column].dropna() if str(value).strip())
        return [name for name, _ in Counter(names).most_common(3)]

    def _operation_environment(self, regime_label: str, settings: InvestmentSettingsContract) -> str:
        if regime_label == "RISK_OFF":
            return "暫緩追價，保留觀察名單"
        if settings.risk_style == "aggressive":
            return "可小部位試單，優先確認停損"
        return "等回測或突破確認後分批"

    def _risk_alerts(self, settings: InvestmentSettingsContract) -> list[str]:
        if settings.risk_limit == "acceptHighVolatility":
            return ["高波動標的需縮小部位", "避免單一題材過度集中"]
        if settings.risk_limit == "lowVolatility":
            return ["波動過高者不進候選", "等回測比追價更重要"]
        return ["避免追高", "停損距離過遠者降級"]

    def _quality_drag_reason(self, candidates: list[WeeklyCandidateContract]) -> str:
        if not candidates:
            return "尚無候選"
        if any(candidate.status == "暫停操作" for candidate in candidates):
            return "部分標的風險條件升高"
        if any(candidate.status == "等回測" for candidate in candidates):
            return "追價風險較高，需要等回測"
        return "主要風險來自停損距離與題材集中"

    def _week_changes(self, settings: InvestmentSettingsContract) -> list[WeeklyChangeContract]:
        if settings.target_type == "etfs":
            return [
                WeeklyChangeContract(
                    kind="新增觀察",
                    title="ETF 候選尚未接入",
                    notes="第一版 contract 已保留 ETF 分區；目前資料來源仍以個股候選為主。",
                )
            ]
        return []

    def _price(self, value: Any) -> str:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return "關鍵價待補"
        if pd.isna(parsed):
            return "關鍵價待補"
        return f"{parsed:,.2f}"

    def _average(self, values: list[float | None]) -> float:
        valid = [value for value in values if value is not None and not pd.isna(value)]
        if not valid:
            return 0.0
        return float(sum(valid) / len(valid))

    def _risk_style_label(self, value: str) -> str:
        return {"conservative": "保守動能", "aggressive": "積極動能"}.get(value, "穩健動能")

    def _holding_period_label(self, value: str) -> str:
        return {"midterm": "中期", "longterm": "中長期"}.get(value, "波段")

    def _entry_preference_label(self, value: str) -> str:
        return {"breakout": "突破", "pullback": "回測", "continuation": "趨勢延續"}.get(value, "綜合")
