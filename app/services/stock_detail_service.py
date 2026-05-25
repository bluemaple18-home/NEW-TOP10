"""個股詳情聚合 service。

只讀既有市場、基本面與回測 service；不觸發外部抓取或回測長任務。
"""

from __future__ import annotations

import re
from typing import Any

import pandas as pd

from app.contracts import (
    StockDetailBacktestSection,
    StockDetailFundamentalSection,
    StockDetailPriceSection,
    StockDetailReferenceSection,
    StockDetailResponse,
    StockDetailTradePlanSection,
    StockPatternOverlayLine,
    StockPatternSignal,
)
from app.services.backtest_service import BacktestService
from app.services.fundamental_service import FundamentalService
from app.services.market_service import MarketService, json_value
from app.signals import PATTERN_SIGNAL_DEFINITIONS
from app.trading import TradePlanService


STOCK_ID_PATTERN = re.compile(r"[0-9A-Za-z._-]{1,20}")
SYSTEM_BACKTEST_SCOPE = "system"
SYSTEM_BACKTEST_NOTE = "系統層回測，非個股專屬。"


class StockDetailService:
    def __init__(
        self,
        market_service: MarketService,
        fundamental_service: FundamentalService,
        backtest_service: BacktestService,
    ):
        self.market_service = market_service
        self.fundamental_service = fundamental_service
        self.backtest_service = backtest_service
        self.trade_plan_service = TradePlanService()

    def stock_detail(self, stock_id: str, limit: int = 1200) -> StockDetailResponse:
        target = self._normalize_stock_id(stock_id)
        price = self._price_section(target, limit=limit)
        return StockDetailResponse(
            stock_id=target,
            price=price,
            reference=self._reference_section(target),
            fundamentals=self._fundamental_section(target),
            trade_plan=self._trade_plan_section(target),
            backtest=self._backtest_section(stock_exists=price.available),
        )

    def _normalize_stock_id(self, stock_id: str) -> str:
        target = str(stock_id).strip()
        if not STOCK_ID_PATTERN.fullmatch(target):
            raise ValueError(f"非法股票代號：{stock_id}")
        return target

    def _price_section(self, stock_id: str, limit: int) -> StockDetailPriceSection:
        ohlcv = self.market_service.stock_ohlcv(stock_id=stock_id, limit=limit)
        if ohlcv is None:
            return StockDetailPriceSection(
                available=False,
                stock_id=stock_id,
                notes="找不到本地 K 線資料。",
            )
        return StockDetailPriceSection(
            available=bool(ohlcv.items),
            stock_id=ohlcv.stock_id,
            stock_name=ohlcv.stock_name,
            items=ohlcv.items,
            signals=self._pattern_signals(ohlcv.items),
            overlays=self._pattern_overlays(ohlcv.items),
            notes=None if ohlcv.items else "本地 K 線資料為空。",
        )

    def _pattern_signals(self, bars: list[Any]) -> list[StockPatternSignal]:
        signals: list[StockPatternSignal] = []
        for bar in bars:
            payload = bar.model_dump() if hasattr(bar, "model_dump") else dict(bar)
            for signal_id in self._visible_pattern_signal_ids(payload):
                definition = PATTERN_SIGNAL_DEFINITIONS[signal_id]
                if pd.to_numeric(payload.get(signal_id), errors="coerce") > 0:
                    signals.append(
                        StockPatternSignal(
                            date=str(payload["time"]),
                            signal_id=signal_id,
                            label=definition.label,
                            category=definition.category,
                            polarity=definition.polarity,
                            price=self._signal_anchor_price(payload, definition.polarity),
                            beginner_note=definition.beginner_note,
                            action_hint=definition.action_hint,
                        )
                    )
            td_count = pd.to_numeric(payload.get("td_count"), errors="coerce")
            if pd.notna(td_count) and 4 <= abs(int(td_count)) < 9:
                polarity = "bearish" if td_count > 0 else "bullish"
                signals.append(
                    StockPatternSignal(
                        date=str(payload["time"]),
                        signal_id="td_count",
                        label=f"TD {abs(int(td_count))}",
                        category="td_sequential",
                        polarity=polarity,
                        price=self._signal_anchor_price(payload, polarity),
                        beginner_note="TD 計數進入 4-8，代表連續結構正在累積，接近 9 時轉折風險會升高。",
                        action_hint="先當成節奏提醒，不單獨作為買賣依據。",
                    )
                )
        return signals

    def _visible_pattern_signal_ids(self, payload: dict[str, Any]) -> list[str]:
        """同日期同分類只顯示一個訊號，依 registry 的 display_priority 決定。"""

        selected_by_category: dict[str, tuple[str, int, int]] = {}
        for order, (signal_id, definition) in enumerate(PATTERN_SIGNAL_DEFINITIONS.items()):
            if not self._signal_is_active(payload, signal_id):
                continue
            current = selected_by_category.get(definition.category)
            candidate = (signal_id, definition.display_priority, order)
            if current is None or (candidate[1], -candidate[2]) > (current[1], -current[2]):
                selected_by_category[definition.category] = candidate

        selected_ids = {signal_id for signal_id, _, _ in selected_by_category.values()}
        return [signal_id for signal_id in PATTERN_SIGNAL_DEFINITIONS if signal_id in selected_ids]

    def _signal_is_active(self, payload: dict[str, Any], signal_id: str) -> bool:
        value = pd.to_numeric(payload.get(signal_id), errors="coerce")
        return bool(pd.notna(value) and value > 0)

    def _pattern_overlays(self, bars: list[Any]) -> list[StockPatternOverlayLine]:
        overlays: list[StockPatternOverlayLine] = []
        for bar in bars:
            payload = bar.model_dump() if hasattr(bar, "model_dump") else dict(bar)
            date = str(payload["time"])
            if pd.to_numeric(payload.get("pattern_w_bottom"), errors="coerce") > 0:
                neckline = json_value(payload.get("pattern_neckline"))
                stop_loss = json_value(payload.get("pattern_stop_loss"))
                points = []
                if neckline is not None:
                    points.append({"time": date, "price": float(neckline), "role": "neckline"})
                if stop_loss is not None:
                    points.append({"time": date, "price": float(stop_loss), "role": "stop_loss"})
                overlays.append(
                    StockPatternOverlayLine(
                        signal_id="pattern_w_bottom",
                        label="W 底突破",
                        points=points,
                        notes="目前提供頸線與失效點；後續 UI 可用 pivot metadata 畫完整 W 形。",
                    )
                )
            if pd.to_numeric(payload.get("pattern_m_top"), errors="coerce") > 0:
                neckline = json_value(payload.get("pattern_neckline"))
                resistance = json_value(payload.get("pattern_resistance"))
                points = []
                if neckline is not None:
                    points.append({"time": date, "price": float(neckline), "role": "neckline"})
                if resistance is not None:
                    points.append({"time": date, "price": float(resistance), "role": "resistance"})
                overlays.append(
                    StockPatternOverlayLine(
                        signal_id="pattern_m_top",
                        label="M 頭跌破",
                        points=points,
                        notes="目前提供頸線與壓力點；後續 UI 可用 pivot metadata 畫完整 M 形。",
                    )
                )
        return overlays

    def _signal_anchor_price(self, payload: dict[str, Any], polarity: str) -> float | None:
        if polarity == "bullish":
            return json_value(payload.get("low") or payload.get("close"))
        if polarity == "bearish":
            return json_value(payload.get("high") or payload.get("close"))
        return json_value(payload.get("close"))

    def _fundamental_section(self, stock_id: str) -> StockDetailFundamentalSection:
        fundamentals = self.fundamental_service.stock_fundamentals(stock_id)
        return StockDetailFundamentalSection(
            available=fundamentals.available,
            data=fundamentals,
            notes=fundamentals.notes,
        )

    def _reference_section(self, stock_id: str) -> StockDetailReferenceSection:
        reference = self.market_service.reference_repository.stock_reference(stock_id)
        return StockDetailReferenceSection(
            available=reference.available,
            data=reference,
            notes=reference.notes,
        )

    def _trade_plan_section(self, stock_id: str) -> StockDetailTradePlanSection:
        latest_row = self._latest_feature_row(stock_id)
        if latest_row is None:
            return StockDetailTradePlanSection(
                available=False,
                notes="找不到本地價格特徵，無法產生交易計畫。",
            )

        ranking_item = self._ranking_item(stock_id)
        ranking_data = ranking_item or {}
        regime = self.market_service.market_regime()
        plan = self.trade_plan_service.build(
            latest_row,
            p_win=ranking_data.get("model_prob"),
            risk_multiplier=regime.risk_multiplier,
        )
        return StockDetailTradePlanSection(
            available=True,
            horizon_days=plan.horizon_days,
            entry_low=plan.entry_low,
            entry_high=plan.entry_high,
            stop_loss=plan.stop_loss,
            target_price=plan.target_price,
            risk_reward=plan.risk_reward,
            position_hint=plan.position_hint,
            suggested_weight=json_value(ranking_data.get("suggested_weight")),
            max_position_weight=json_value(ranking_data.get("max_position_weight")),
            gross_exposure=json_value(ranking_data.get("gross_exposure")),
            allocated_exposure=json_value(ranking_data.get("allocated_exposure")),
            cash_weight=json_value(ranking_data.get("cash_weight")),
            exposure_note=ranking_data.get("exposure_note"),
            notes=None if ranking_item else "此股票不在最新 ranking artifact 內，權重欄位暫無。",
        )

    def _backtest_section(self, stock_exists: bool) -> StockDetailBacktestSection:
        if not stock_exists:
            return StockDetailBacktestSection(
                available=False,
                reports=[],
                curves=[],
                scope=SYSTEM_BACKTEST_SCOPE,
                notes="找不到本地 K 線資料；系統層回測不套用到此股票。",
            )
        summary = self.backtest_service.summary()
        available = bool(summary.reports or summary.curves)
        return StockDetailBacktestSection(
            available=available,
            reports=summary.reports,
            curves=summary.curves,
            scope=SYSTEM_BACKTEST_SCOPE,
            notes=SYSTEM_BACKTEST_NOTE if available else "尚無既有回測 artifact。",
        )

    def _latest_feature_row(self, stock_id: str) -> dict[str, Any] | None:
        features = self.market_service.repository.load_features()
        target = str(stock_id).strip()
        stock_df = features[features["stock_id"] == target].tail(1)
        if stock_df.empty:
            return None
        row = stock_df.iloc[-1].to_dict()
        return {key: json_value(value) for key, value in row.items()}

    def _ranking_item(self, stock_id: str) -> dict[str, Any] | None:
        ranking = self.market_service.latest_ranking(limit=100)
        target = str(stock_id).strip()
        for item in ranking.items:
            if item.stock_id == target:
                return item.model_dump()
        return None
