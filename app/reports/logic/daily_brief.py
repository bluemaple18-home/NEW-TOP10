"""每日晨報決策文案建構器。

這層只把既有 ranking / 交易計畫欄位轉成可讀文案，不重算排名、不呼叫 LLM。
"""

from __future__ import annotations

import math
from typing import Any

import pandas as pd

try:
    from app.trading import StrategyComponentRegistry
except ImportError:
    from trading import StrategyComponentRegistry


SCHEMA_VERSION = "top10.daily_brief.v1"
NOT_SUPPORTED = "not_supported"


class DailyBriefBuilder:
    """將排名證據轉成固定欄位的晨報區塊。"""

    def __init__(self, strategy_registry: StrategyComponentRegistry | None = None):
        self.strategy_registry = strategy_registry or StrategyComponentRegistry.default()
        self.strategy_labels = {
            component.component_id: component.label
            for component in self.strategy_registry.components
        }

    def build(
        self,
        *,
        row: pd.Series,
        latest: pd.Series,
        triggers: list[dict[str, Any]],
        risks: list[str],
        trade_plan: dict[str, Any],
        verdict: str,
        p_win: float,
    ) -> dict[str, Any]:
        score_breakdown = self._score_breakdown(row)
        why_pick = self._why_pick(row=row, latest=latest, triggers=triggers, p_win=p_win)
        risk_alerts = self._risk_alerts(row=row, latest=latest, risks=risks)
        positive_catalysts = self._positive_catalysts(row=row, triggers=triggers)
        action_checklist = self._action_checklist(row=row, trade_plan=trade_plan, verdict=verdict)
        strategy_route = self._strategy_route(row)

        return {
            "schema_version": SCHEMA_VERSION,
            "core_conclusion": self._core_conclusion(row=row, verdict=verdict, p_win=p_win),
            "why_pick": why_pick,
            "score_breakdown": score_breakdown,
            "risk_alerts": risk_alerts,
            "positive_catalysts": positive_catalysts,
            "action_checklist": action_checklist,
            "strategy_route": strategy_route,
            "data_coverage": self._data_coverage(row),
        }

    def _core_conclusion(self, *, row: pd.Series, verdict: str, p_win: float) -> str:
        score = self._number(row.get("risk_adjusted_score"))
        if score is not None:
            return f"{verdict}，模型勝率 {p_win * 100:.1f}%，風險調整分數 {score:.2f}。"
        return f"{verdict}，模型勝率 {p_win * 100:.1f}%。"

    def _why_pick(
        self,
        *,
        row: pd.Series,
        latest: pd.Series,
        triggers: list[dict[str, Any]],
        p_win: float,
    ) -> list[str]:
        reasons: list[str] = []
        reasons.append(f"模型勝率 {p_win * 100:.1f}%，作為候選排序的主要量化依據。")

        risk_adjusted = self._number(row.get("risk_adjusted_score"))
        if risk_adjusted is not None:
            reasons.append(f"風險調整分數 {risk_adjusted:.2f}，已納入 setup、品質與風險扣分。")

        component_parts = []
        for label, column in (
            ("prediction", "prediction_score"),
            ("setup", "setup_score"),
            ("quality", "quality_score"),
            ("risk_penalty", "risk_penalty"),
        ):
            value = self._number(row.get(column))
            if value is not None:
                component_parts.append(f"{label}={value:.2f}")
        if component_parts:
            reasons.append("分數拆解：" + " / ".join(component_parts) + "。")

        for trigger in triggers[:2]:
            text = str(trigger.get("plain_text") or trigger.get("name") or "").strip()
            if text:
                reasons.append(text)

        technical_reason = str(row.get("reasons") or "").strip()
        if technical_reason and not triggers:
            reasons.append(self._compact_text(technical_reason))

        rsi = self._number(latest.get("rsi"))
        close = self._number(latest.get("close"))
        ma20 = self._number(latest.get("ma20"))
        if rsi is not None and close is not None and ma20 is not None:
            side = "站上" if close >= ma20 else "跌破"
            reasons.append(f"最新 RSI {rsi:.1f}，收盤價 {side} MA20 ({ma20:.2f})。")

        return self._dedupe(reasons)[:5]

    def _score_breakdown(self, row: pd.Series) -> dict[str, Any]:
        result: dict[str, Any] = {"source": "ranking_policy"}
        for column in (
            "model_prob",
            "risk_adjusted_score",
            "prediction_score",
            "setup_score",
            "quality_score",
            "risk_penalty",
            "risk_reward",
            "execution_risk_reward",
        ):
            value = self._number(row.get(column))
            result[column] = round(value, 4) if value is not None else None
        return result

    def _risk_alerts(self, *, row: pd.Series, latest: pd.Series, risks: list[str]) -> list[str]:
        alerts = [str(item).strip() for item in risks if str(item).strip()]

        risk_signals = [item for item in str(row.get("risk_signals") or "").split("|") if item]
        alerts.extend(f"風險訊號：{item}" for item in risk_signals[:3])

        rsi = self._number(latest.get("rsi"))
        if rsi is not None and rsi > 75:
            alerts.append(f"RSI {rsi:.1f} 偏熱，追價風險升高。")

        rr_action = str(row.get("rr_guard_action") or "").strip()
        rr_reason = str(row.get("rr_guard_reason") or "").strip()
        if rr_action and rr_action != "ALLOW":
            alerts.append(rr_reason or f"風險報酬檢查為 {rr_action}。")

        tape_action = str(row.get("tape_guard_action") or "").strip()
        tape_reason = str(row.get("tape_guard_reason") or "").strip()
        if tape_action and tape_action != "ALLOW":
            alerts.append(tape_reason or f"當日 tape guard 為 {tape_action}。")

        return self._dedupe(alerts)[:5]

    def _positive_catalysts(self, *, row: pd.Series, triggers: list[dict[str, Any]]) -> list[str]:
        catalysts: list[str] = []
        positive_signals = [item for item in str(row.get("positive_signals") or "").split("|") if item]
        catalysts.extend(f"技術催化：{item}" for item in positive_signals[:3])
        for trigger in triggers[:3]:
            name = str(trigger.get("name") or "").strip()
            evidence = str(trigger.get("evidence") or "").strip()
            if name and evidence:
                catalysts.append(f"{name}：{evidence}")
        return self._dedupe(catalysts)[:5]

    def _action_checklist(self, *, row: pd.Series, trade_plan: dict[str, Any], verdict: str) -> list[str]:
        checklist = []
        entry = trade_plan.get("entry_zone") if isinstance(trade_plan, dict) else {}
        if isinstance(entry, dict) and entry.get("low") is not None and entry.get("high") is not None:
            checklist.append(f"進場區間：{entry['low']} - {entry['high']}，不要追過上緣。")

        invalidation = trade_plan.get("invalidation") if isinstance(trade_plan, dict) else None
        if invalidation:
            checklist.append(f"失效條件：{invalidation}。")

        target = trade_plan.get("target_price") if isinstance(trade_plan, dict) else None
        if target is not None:
            checklist.append(f"第一目標價：{target}，到價後檢查量價與長上影。")

        if verdict == "避免":
            checklist.append("若要重回觀察名單，需等待模型勝率或風險報酬重新轉強。")
        else:
            checklist.append("收盤前檢查是否跌破 MA20、停損價或出現新風險訊號。")

        rr_action = str(row.get("rr_guard_action") or "").strip()
        if rr_action and rr_action != "ALLOW":
            checklist.append("風險報酬未放行前，只能等待拉回或確認突破。")

        return self._dedupe(checklist)

    def _strategy_route(self, row: pd.Series) -> dict[str, Any]:
        regime = str(row.get("strategy_route_regime") or row.get("market_regime") or "").strip()
        production = self._route_items(row.get("strategy_route_production"))
        shadow = self._route_items(row.get("strategy_route_shadow"))
        report_only = self._route_items(row.get("strategy_route_report_only"))
        blocked = self._route_items(row.get("strategy_route_blocked"))
        production_mutates = self._truthy(row.get("strategy_route_mutates_production_score"))

        if not any([regime, production, shadow, report_only, blocked]):
            return {
                "status": "missing",
                "regime": None,
                "production": [],
                "shadow": [],
                "report_only": [],
                "blocked": [],
                "production_mutates_score": False,
                "summary": "ranking artifact 尚未提供策略路由欄位。",
            }

        summary_parts = []
        if production:
            summary_parts.append("正式生效：" + "、".join(item["label"] for item in production))
        if shadow:
            summary_parts.append("影子觀察：" + "、".join(item["label"] for item in shadow[:3]))
        if report_only:
            summary_parts.append("報告提示：" + "、".join(item["label"] for item in report_only[:3]))

        return {
            "status": "supported",
            "regime": regime or None,
            "production": production,
            "shadow": shadow,
            "report_only": report_only,
            "blocked": blocked,
            "production_mutates_score": production_mutates,
            "summary": "；".join(summary_parts) if summary_parts else "此盤勢沒有啟用策略元件。",
        }

    def _data_coverage(self, row: pd.Series) -> list[dict[str, str]]:
        coverage = [
            {
                "field": "ranking_score",
                "status": "supported" if self._number(row.get("risk_adjusted_score")) is not None else "missing",
                "reason": "來自 RankingPolicy 產出的風險調整分數。",
            },
            {
                "field": "trade_plan",
                "status": "supported" if isinstance(row.get("trade_plan"), dict) else "derived",
                "reason": "優先使用 ranking 交易計畫；缺少時由報告層依同一 TradePlanService 補足。",
            },
            {
                "field": "news_catalysts",
                "status": NOT_SUPPORTED,
                "reason": "TOP10new 目前尚未把外部新聞納入正式 ranking artifact，避免在報告中編造催化因素。",
            },
            {
                "field": "notification_delivery",
                "status": NOT_SUPPORTED,
                "reason": "本切片只產生可推送 artifact，通知渠道會在後續切片接入。",
            },
            {
                "field": "strategy_route",
                "status": "supported" if row.get("strategy_route_regime") else "missing",
                "reason": "來自 StrategyComponentRegistry 的盤勢策略路由；shadow/report_only 不改正式排名。",
            },
        ]
        return coverage

    def _route_items(self, value: Any) -> list[dict[str, str]]:
        if value is None or pd.isna(value):
            return []
        ids = [item for item in str(value or "").split("|") if item]
        return [{"component_id": item, "label": self.strategy_labels.get(item, item)} for item in ids]

    def _truthy(self, value: Any) -> bool:
        if isinstance(value, bool):
            return value
        if value is None or pd.isna(value):
            return False
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _compact_text(self, text: str) -> str:
        lines = [line.strip(" •") for line in text.splitlines() if line.strip()]
        useful = [line for line in lines if not line.startswith("**")]
        return "；".join(useful[:3]) if useful else text[:120]

    def _dedupe(self, values: list[str]) -> list[str]:
        result = []
        seen = set()
        for value in values:
            text = str(value).strip()
            if not text or text in seen:
                continue
            seen.add(text)
            result.append(text)
        return result

    def _number(self, value: Any) -> float | None:
        try:
            parsed = float(value)
        except (TypeError, ValueError):
            return None
        if pd.isna(parsed) or not math.isfinite(parsed):
            return None
        return parsed
