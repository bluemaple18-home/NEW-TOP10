"""全系統模型 registry。

這裡是模型組裝藍圖：先定義每個模型的責任，再讓 pipeline/API/UI 各自依契約接入。
"""

from __future__ import annotations

from .contracts import ModelSpec, ModelValidationIssue


MODEL_SPECS: tuple[ModelSpec, ...] = (
    ModelSpec(
        model_id="M1_TECHNICAL_FACTORS",
        name="技術因子模型",
        layer="factor",
        purpose="將 OHLCV 與量能資料轉換成可評估的 alpha factors。",
        inputs=("features.parquet: OHLCV", "chip optional", "volume"),
        outputs=("ma", "rsi", "macd", "bollinger", "breakout", "volume_ratio"),
        owner_module="app.indicators / app.volume_indicators",
        backtest_required=True,
        status="active",
    ),
    ModelSpec(
        model_id="M2_FUNDAMENTAL_QUALITY",
        name="基本面品質模型",
        layer="factor",
        purpose="衡量公司體質、獲利品質與財務風險。",
        inputs=("Goodinfo income statement", "Goodinfo balance sheet", "Goodinfo cash flow", "monthly revenue"),
        outputs=("roe", "roa", "gross_margin", "operating_margin", "debt_ratio", "current_ratio", "free_cash_flow"),
        owner_module="app.fundamentals",
        backtest_required=True,
        status="scaffolded",
    ),
    ModelSpec(
        model_id="M3_EVENT_SIGNALS",
        name="事件訊號模型",
        layer="signal",
        purpose="將技術與基本面條件轉成標準化 0/1 正負事件。",
        inputs=("features.parquet", "config/signals.yaml"),
        outputs=("events.parquet", "positive_signals", "risk_signals"),
        owner_module="app.event_detector",
        backtest_required=True,
        status="active",
    ),
    ModelSpec(
        model_id="M4_RETURN_PREDICTION",
        name="報酬預測模型",
        layer="prediction",
        purpose="預測未來持有期勝率與報酬方向。",
        inputs=("features.parquet", "events.parquet", "data/fundamentals cache", "labels"),
        outputs=("model_prob", "raw_prob", "expected_return"),
        owner_module="app.agent_b_modeling / app.agent_b_ranking",
        training_required=True,
        backtest_required=True,
        status="active",
    ),
    ModelSpec(
        model_id="M5_MARKET_REGIME",
        name="市場狀態模型",
        layer="risk",
        purpose="判斷當前市場是否適合提高曝險。",
        inputs=("market breadth", "breakout ratio", "avg rsi"),
        outputs=("RISK_ON", "NEUTRAL", "RISK_OFF", "risk_multiplier"),
        owner_module="app.trading.market_regime",
        backtest_required=True,
        status="active_thin",
    ),
    ModelSpec(
        model_id="M6_RISK_MODEL",
        name="風險模型",
        layer="risk",
        purpose="衡量單股踩雷風險與交易品質折扣。",
        inputs=("volatility", "liquidity", "technical risk events", "fundamental risk metrics"),
        outputs=("risk_penalty", "liquidity_factor", "setup_quality"),
        owner_module="app.trading.ranking_policy",
        backtest_required=True,
        status="active_thin",
    ),
    ModelSpec(
        model_id="M7_RANKING_FUSION",
        name="排名融合模型",
        layer="decision",
        purpose="整合預測、事件、風控與市場狀態，產生最終排序。",
        inputs=("model_prob", "rule_score", "risk_penalty", "market_regime", "risk_reward"),
        outputs=("risk_adjusted_score", "top_n"),
        owner_module="app.trading.ranking_policy",
        backtest_required=True,
        status="active",
    ),
    ModelSpec(
        model_id="M8_TRADE_PLAN",
        name="交易計畫模型",
        layer="decision",
        purpose="產生 entry / stop / target / position hint，讓操作規則一致。",
        inputs=("close", "ma20", "low_20d", "resistance", "p_win", "risk_multiplier"),
        outputs=("entry_zone", "stop_loss", "target_price", "risk_reward", "position_hint"),
        owner_module="app.trading.trade_plan",
        backtest_required=True,
        status="active_thin",
    ),
    ModelSpec(
        model_id="M9_PORTFOLIO_SIZING",
        name="投組配置模型",
        layer="portfolio",
        purpose="決定 Top N 之間的權重、單股上限與總曝險。",
        inputs=("risk_adjusted_score", "risk_penalty", "market_regime"),
        outputs=("suggested_weight", "gross_exposure", "allocated_exposure", "max_position_weight", "cash_weight", "exposure_note"),
        owner_module="app.trading.portfolio_policy",
        backtest_required=True,
        status="active_thin",
    ),
    ModelSpec(
        model_id="M10_BACKTEST_EVALUATION",
        name="回測評估模型",
        layer="evaluation",
        purpose="隔離評估交易規則與模型訊號，不讓 UI/API 觸發回測。",
        inputs=("signals", "trade_plan", "historical prices", "cost model"),
        outputs=("cagr", "sharpe", "max_drawdown", "win_rate", "turnover"),
        owner_module="app.backtesting",
        status="active_read_only",
    ),
    ModelSpec(
        model_id="M11_MODEL_MONITORING",
        name="模型監控模型",
        layer="monitoring",
        purpose="監控資料漂移、factor 衰退與近期績效失真。",
        inputs=("psi", "factor_ic", "recent hit rate", "latest backtest"),
        outputs=("monitor_status", "retrain_signal", "warnings"),
        owner_module="app.model_monitor",
        status="active_thin",
    ),
)


def get_model_spec(model_id: str) -> ModelSpec:
    for spec in MODEL_SPECS:
        if spec.model_id == model_id:
            return spec
    raise KeyError(f"未知模型：{model_id}")


def validate_model_registry(specs: tuple[ModelSpec, ...] = MODEL_SPECS) -> list[ModelValidationIssue]:
    issues: list[ModelValidationIssue] = []
    seen: set[str] = set()
    for spec in specs:
        if spec.model_id in seen:
            issues.append(ModelValidationIssue("ERROR", spec.model_id, "model_id 重複"))
        seen.add(spec.model_id)
        if not spec.inputs:
            issues.append(ModelValidationIssue("ERROR", spec.model_id, "缺少 inputs"))
        if not spec.outputs:
            issues.append(ModelValidationIssue("ERROR", spec.model_id, "缺少 outputs"))
        if spec.training_required and not spec.backtest_required:
            issues.append(ModelValidationIssue("WARN", spec.model_id, "需要訓練的模型通常也應有回測/驗證閘門"))
    return issues
