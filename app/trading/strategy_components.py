"""策略元件 registry 與盤勢路由。

這層只負責回答「某個盤勢下哪些策略元件可啟用」。
策略是否真的改分數、過濾、調倉，必須由對應元件自己實作並通過 promotion gate。
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Any


RUNTIME_STATUSES = {"off", "shadow", "report_only", "production"}
EFFECT_TYPES = {"score_overlay", "filter", "risk_overlay", "sizing", "explanation"}
MUTATING_EFFECTS = {"score_overlay", "filter", "risk_overlay", "sizing"}
ANY_REGIME = "*"


@dataclass(frozen=True)
class StrategyComponent:
    component_id: str
    label: str
    category: str
    runtime_status: str
    effect_type: str
    applies_to_regimes: tuple[str, ...]
    blocked_regimes: tuple[str, ...] = ()
    input_columns: tuple[str, ...] = ()
    output_columns: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    promotion_gates: tuple[str, ...] = ()
    blocked_uses: tuple[str, ...] = ()
    can_change_production_ranking: bool = False
    description: str = ""

    def validate(self) -> None:
        if not self.component_id or " " in self.component_id:
            raise ValueError(f"invalid strategy component id: {self.component_id!r}")
        if self.runtime_status not in RUNTIME_STATUSES:
            raise ValueError(f"{self.component_id} has invalid runtime_status: {self.runtime_status}")
        if self.effect_type not in EFFECT_TYPES:
            raise ValueError(f"{self.component_id} has invalid effect_type: {self.effect_type}")
        if not self.applies_to_regimes:
            raise ValueError(f"{self.component_id} must declare applies_to_regimes")
        if self.runtime_status != "production" and self.can_change_production_ranking:
            raise ValueError(f"{self.component_id} cannot change production ranking outside production status")
        if self.runtime_status == "production" and self.effect_type in MUTATING_EFFECTS:
            if not self.can_change_production_ranking:
                raise ValueError(f"{self.component_id} production mutating component lacks explicit permission")
            if not self.evidence:
                raise ValueError(f"{self.component_id} production mutating component lacks evidence")
            if not self.promotion_gates:
                raise ValueError(f"{self.component_id} production mutating component lacks promotion gates")

    def applies_to(self, regime_label: str) -> bool:
        label = str(regime_label or "UNKNOWN")
        if label in self.blocked_regimes:
            return False
        return ANY_REGIME in self.applies_to_regimes or label in self.applies_to_regimes

    def is_mutating(self) -> bool:
        return self.effect_type in MUTATING_EFFECTS

    def to_dict(self) -> dict[str, Any]:
        return {
            "component_id": self.component_id,
            "label": self.label,
            "category": self.category,
            "runtime_status": self.runtime_status,
            "effect_type": self.effect_type,
            "applies_to_regimes": list(self.applies_to_regimes),
            "blocked_regimes": list(self.blocked_regimes),
            "input_columns": list(self.input_columns),
            "output_columns": list(self.output_columns),
            "evidence": list(self.evidence),
            "promotion_gates": list(self.promotion_gates),
            "blocked_uses": list(self.blocked_uses),
            "can_change_production_ranking": self.can_change_production_ranking,
            "description": self.description,
        }


@dataclass(frozen=True)
class StrategyRoute:
    regime_label: str
    production: tuple[str, ...]
    shadow: tuple[str, ...]
    report_only: tuple[str, ...]
    blocked: tuple[str, ...]
    production_mutators: tuple[str, ...]

    def to_columns(self) -> dict[str, Any]:
        return {
            "strategy_route_regime": self.regime_label,
            "strategy_route_production": "|".join(self.production),
            "strategy_route_shadow": "|".join(self.shadow),
            "strategy_route_report_only": "|".join(self.report_only),
            "strategy_route_blocked": "|".join(self.blocked),
            "strategy_route_mutates_production_score": bool(self.production_mutators),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "regime_label": self.regime_label,
            "production": list(self.production),
            "shadow": list(self.shadow),
            "report_only": list(self.report_only),
            "blocked": list(self.blocked),
            "production_mutators": list(self.production_mutators),
        }


class StrategyComponentRegistry:
    def __init__(self, components: list[StrategyComponent], enabled: bool = True):
        self.enabled = enabled
        self.components = tuple(components)
        self._by_id = {component.component_id: component for component in self.components}
        if len(self._by_id) != len(self.components):
            raise ValueError("strategy component ids must be unique")
        self.validate()

    @classmethod
    def default(cls) -> "StrategyComponentRegistry":
        return cls(default_components())

    @classmethod
    def from_mapping(cls, payload: dict[str, Any] | None) -> "StrategyComponentRegistry":
        data = payload or {}
        enabled = bool(data.get("enabled", True))
        components = list(default_components())
        overrides = data.get("components") or {}
        if isinstance(overrides, list):
            overrides = {
                str(item.get("component_id")): item
                for item in overrides
                if isinstance(item, dict) and item.get("component_id")
            }
        if isinstance(overrides, dict):
            components = [apply_override(component, overrides.get(component.component_id)) for component in components]
        return cls(components, enabled=enabled)

    def validate(self) -> None:
        for component in self.components:
            component.validate()

    def route(self, regime_label: str) -> StrategyRoute:
        label = str(regime_label or "UNKNOWN")
        if not self.enabled:
            return StrategyRoute(label, (), (), (), tuple(self._by_id), ())

        production: list[str] = []
        shadow: list[str] = []
        report_only: list[str] = []
        blocked: list[str] = []
        production_mutators: list[str] = []

        for component in self.components:
            if component.runtime_status == "off" or not component.applies_to(label):
                blocked.append(component.component_id)
                continue
            if component.runtime_status == "production":
                production.append(component.component_id)
                if component.is_mutating() and component.can_change_production_ranking:
                    production_mutators.append(component.component_id)
            elif component.runtime_status == "shadow":
                shadow.append(component.component_id)
            elif component.runtime_status == "report_only":
                report_only.append(component.component_id)

        return StrategyRoute(
            regime_label=label,
            production=tuple(production),
            shadow=tuple(shadow),
            report_only=tuple(report_only),
            blocked=tuple(blocked),
            production_mutators=tuple(production_mutators),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "component_count": len(self.components),
            "components": [component.to_dict() for component in self.components],
        }


def apply_override(component: StrategyComponent, payload: Any) -> StrategyComponent:
    if not isinstance(payload, dict):
        return component
    allowed = {
        "runtime_status",
        "applies_to_regimes",
        "blocked_regimes",
        "promotion_gates",
        "blocked_uses",
        "can_change_production_ranking",
    }
    values = {key: payload[key] for key in allowed if key in payload}
    for key in ("applies_to_regimes", "blocked_regimes", "promotion_gates", "blocked_uses"):
        if key in values:
            raw_value = values[key]
            values[key] = tuple(str(item) for item in raw_value) if isinstance(raw_value, list) else component.__dict__[key]
    return replace(component, **values)


def default_components() -> list[StrategyComponent]:
    return [
        StrategyComponent(
            component_id="base_regime_risk_multiplier",
            label="基礎盤勢風險倍率",
            category="regime_gate",
            runtime_status="production",
            effect_type="risk_overlay",
            applies_to_regimes=(ANY_REGIME,),
            input_columns=("close", "ma20", "rsi", "break_20d_high"),
            output_columns=("market_regime", "regime_factor", "risk_penalty"),
            evidence=("app/trading/market_regime.py", "app/trading/ranking_policy.py"),
            promotion_gates=("existing_production_baseline",),
            blocked_uses=("new_regime_label_without_replay",),
            can_change_production_ranking=True,
            description="正式 ranking 已使用的 RISK_ON/NEUTRAL/RISK_OFF 風險倍率。",
        ),
        StrategyComponent(
            component_id="high_entry_chase_protection",
            label="高位防追高",
            category="entry_filter",
            runtime_status="shadow",
            effect_type="filter",
            applies_to_regimes=("RISK_ON", "NEUTRAL", "NARROW_LEADER", "EARLY_REVERSAL", "MIXED_NEUTRAL"),
            blocked_regimes=("PANIC_SELLING",),
            input_columns=("rsi", "close", "ref_high_20d", "execution_risk_reward", "risk_reward_score"),
            output_columns=("rr_guard_action", "rr_guard_reason"),
            evidence=("scripts/build_strategy_archetype_evidence_map.py",),
            promotion_gates=("long_window_replay", "top10_fill_rate_non_worsening", "pm_promotion_review"),
            blocked_uses=("drop_top10_without_replacement", "unreviewed_production_filter"),
            description="強勢股可留在候選，但追高點必須等待拉回或由候補補位。",
        ),
        StrategyComponent(
            component_id="selloff_protection",
            label="急殺保護",
            category="risk_overlay",
            runtime_status="shadow",
            effect_type="risk_overlay",
            applies_to_regimes=("RISK_OFF", "PANIC_SELLING", "MIXED_NEUTRAL", "UNKNOWN"),
            input_columns=("breadth_ma20", "daily_return", "drawdown_from_20d_high"),
            output_columns=("gross_exposure", "cash_weight", "exposure_note"),
            evidence=("app/trading/portfolio_risk_overlay.py", "scripts/build_strategy_archetype_evidence_map.py"),
            promotion_gates=("regime_replay", "drawdown_non_worsening", "pm_promotion_review"),
            blocked_uses=("ranking_score_without_replay", "auto_sell_without_user_position"),
            description="盤勢轉弱時降低曝險或提高現金，定位是風險 overlay，不是選股 alpha。",
        ),
        StrategyComponent(
            component_id="strong_trend_hold",
            label="強趨勢續抱",
            category="exit_rule",
            runtime_status="report_only",
            effect_type="explanation",
            applies_to_regimes=("RISK_ON", "NARROW_LEADER", "EARLY_REVERSAL"),
            input_columns=("close", "ma20", "ref_low_10d", "risk_reward"),
            output_columns=("trade_plan", "action_checklist"),
            evidence=("app/trading/trade_plan.py", "app/reports/logic/daily_brief.py"),
            promotion_gates=("exit_rule_replay", "pm_promotion_review"),
            blocked_uses=("personal_position_sell_alert_without_user_holdings",),
            description="只在報告層提示續抱條件，不替使用者自動賣出。",
        ),
        StrategyComponent(
            component_id="concentration_control",
            label="集中度控制",
            category="sizing",
            runtime_status="shadow",
            effect_type="sizing",
            applies_to_regimes=("RISK_ON", "NEUTRAL", "NARROW_LEADER", "MIXED_NEUTRAL"),
            input_columns=("sector_name", "industry_name", "suggested_weight"),
            output_columns=("max_position_weight", "suggested_weight", "cash_weight"),
            evidence=("app/trading/portfolio_policy.py", "app/trading/portfolio_risk_overlay.py"),
            promotion_gates=("portfolio_replay", "concentration_non_worsening", "pm_promotion_review"),
            blocked_uses=("standalone_alpha_without_replay", "unreviewed_position_sizing"),
            description="處理族群或個股過度集中，避免 Top10 全押同一題材。",
        ),
        StrategyComponent(
            component_id="vwap_regime_gated_entry",
            label="VWAP 盤勢閘門進場品質",
            category="entry_filter",
            runtime_status="shadow",
            effect_type="score_overlay",
            applies_to_regimes=("NARROW_LEADER", "PANIC_SELLING"),
            input_columns=("vwap_5d", "vwap_20d", "close", "risk_adjusted_score", "market_regime"),
            output_columns=("vwap_overlay_score", "vwap_overlay_reason", "shadow_market_regime"),
            evidence=(
                "scripts/research_vwap_regime_gated_entry_quality.py",
                "scripts/materialize_vwap_regime_gated_rankings.py",
            ),
            promotion_gates=("sealed_replay", "turnover_non_worsening", "pm_promotion_review"),
            blocked_uses=("direct_production_rerank", "unreviewed_vwap_cost_basis_filter"),
            description="只在指定盤勢比較 VWAP 成本位置，研究是否能改善追高與急殺進場品質。",
        ),
        StrategyComponent(
            component_id="candidate_ranking_source",
            label="候選排名來源",
            category="ranking_source",
            runtime_status="shadow",
            effect_type="score_overlay",
            applies_to_regimes=(ANY_REGIME,),
            input_columns=("candidate_rank", "risk_adjusted_score", "model_prob"),
            output_columns=("shadow_score", "baseline_rank"),
            evidence=("scripts/build_long_candidate_validation_report.py",),
            promotion_gates=("long_window_replay", "recent_window_non_worsening", "pm_promotion_review"),
            blocked_uses=("unconditional_publish_replacement", "immediate_production_switch"),
            description="長窗候選 ranking 來源，可做 shadow 比較；近期輸 production 前不能正式替換。",
        ),
        StrategyComponent(
            component_id="trail10_exit_rule",
            label="Trail10 出場規則",
            category="exit_rule",
            runtime_status="report_only",
            effect_type="explanation",
            applies_to_regimes=(ANY_REGIME,),
            input_columns=("close", "entry_price", "highest_close_since_entry"),
            output_columns=("exit_watch", "action_checklist"),
            evidence=("scripts/build_long_candidate_validation_report.py",),
            promotion_gates=("position_ledger_contract", "exit_rule_replay", "pm_promotion_review"),
            blocked_uses=("auto_sell_without_user_position", "personal_position_sell_alert_without_user_holdings"),
            description="作為持有後的移動停利觀察語言，不在目前 ranking 流程替使用者下賣出決策。",
        ),
        StrategyComponent(
            component_id="chip_warning_overlay",
            label="籌碼警示 overlay",
            category="risk_overlay",
            runtime_status="off",
            effect_type="risk_overlay",
            applies_to_regimes=(ANY_REGIME,),
            input_columns=("foreign_buy", "trust_buy", "margin_purchase_balance_change", "short_sale_balance_change"),
            output_columns=("chip_warning_group", "risk_alerts"),
            evidence=("scripts/build_chip_warning_shadow_report.py",),
            promotion_gates=("chip_feature_materialization", "warning_effectiveness_replay", "pm_promotion_review"),
            blocked_uses=("ranking_score_without_replay", "primary_market_direction", "standalone_warning_channel"),
            description="籌碼資料尚未穩定進正式 features 前維持 off，只能作資料到位後的風險 overlay 候選。",
        ),
        StrategyComponent(
            component_id="feature_group_k9_shadow_fill",
            label="Feature-group K9 shadow 補位",
            category="ranking_transform",
            runtime_status="shadow",
            effect_type="score_overlay",
            applies_to_regimes=("NARROW_LEADER", "EARLY_REVERSAL", "MIXED_NEUTRAL", "RISK_OFF", "PANIC_SELLING"),
            input_columns=("industry_breadth_ma20_loo", "sector_return_1d_loo", "avg_value_20d", "pct_from_low_60d"),
            output_columns=("shadow_score", "production_overlay_source", "production_overlay_keep_count"),
            evidence=("app/agent_b_ranking.py", "config/signals.yaml"),
            promotion_gates=("production_overlay_promotion_review", "rollback_gate", "pm_promotion_review"),
            blocked_uses=("promotion_review_approved_false", "unbounded_top10_replacement"),
            description="保留 production 前 K 名，用 feature-group shadow score 補位；正式開啟需 promotion review。",
        ),
        StrategyComponent(
            component_id="industry_theme_context",
            label="產業與題材上下文",
            category="explanation",
            runtime_status="report_only",
            effect_type="explanation",
            applies_to_regimes=(ANY_REGIME,),
            input_columns=("sector_name", "industry_name", "theme_tags"),
            output_columns=("positive_catalysts", "risk_alerts", "market_summary"),
            evidence=("data/reference/stock_industry_map.csv", "data/reference/stock_concept_membership.csv"),
            promotion_gates=("reference_data_coverage", "message_accuracy_review"),
            blocked_uses=("standalone_alpha_without_replay", "ranking_score"),
            description="提供日報與推播可讀上下文；reference available 不等於 alpha validated。",
        ),
    ]
