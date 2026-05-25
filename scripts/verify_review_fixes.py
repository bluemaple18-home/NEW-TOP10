"""Code review findings regression checks."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent_b_modeling import LightGBMTrainer
from app.agent_b_ranking import StockRanker
from app.data.fundamental_repository import FundamentalRepository
from app.data.market_repository import MarketRepository
from app.data.monitoring_repository import MonitoringRepository
from app.modeling.feature_contract import build_m4_feature_frame, candidate_feature_columns
from app.monitoring.factor_monitor import FactorMonitor, _daily_cross_sectional_ic
from app.pipeline.validation import PipelineDataValidator
from app.services.market_service import MarketService
from app.trading import MarketRegime, PortfolioPolicy, RankingPolicy


def main() -> int:
    verify_ranking_trade_date_merge()
    verify_ranking_uses_m4_feature_contract_for_inference()
    verify_ranking_rejects_duplicate_trade_keys()
    verify_factor_monitor_rejects_duplicate_trade_keys()
    verify_factor_ic_is_daily_cross_sectional()
    verify_factor_monitor_warns_when_ic_unavailable()
    verify_latest_ranking_uses_filename_date()
    verify_fundamental_cache_rejects_path_fragments()
    verify_monitoring_repository_reads_fresh_artifact()
    verify_walk_forward_purge()
    verify_walk_forward_uses_trade_dates()
    verify_modeling_rejects_duplicate_label_keys()
    verify_validator_rejects_duplicate_trade_keys()
    verify_m4_feature_contract_rejects_duplicate_trade_keys()
    verify_m4_feature_contract_preserves_missing_fundamentals()
    verify_ranking_policy_score_decomposition()
    verify_ranking_policy_ignores_fundamentals_until_gate_passes()
    verify_latest_ranking_backfills_score_decomposition()
    verify_portfolio_policy_allocation_caps()
    verify_ranking_missing_features_raises()
    print("REVIEW_FIXES_OK")
    return 0


def verify_ranking_trade_date_merge() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data_dir = root / "data"
        data_dir.mkdir()
        base = pd.Timestamp("2024-01-02")
        rows = []
        events = []
        universe = []
        for i, stock_id in enumerate(["1101", "1102"]):
            timestamp = base + pd.Timedelta(hours=10 + i)
            for day in range(25):
                date = timestamp - pd.Timedelta(days=24 - day)
                rows.append(
                    {
                        "date": date,
                        "stock_id": stock_id,
                        "open": 10 + day,
                        "high": 11 + day,
                        "low": 9 + day,
                        "close": 10.5 + day,
                        "volume": 1000,
                        "ma20": 20,
                        "rsi": 50,
                    }
                )
            events.append({"date": timestamp, "stock_id": stock_id, "break_20d_high": 1 if stock_id == "1101" else 0})
            universe.append({"date": timestamp, "stock_id": stock_id, "close": 35, "avg_value_20d": 30_000_000})

        pd.DataFrame(rows).to_parquet(data_dir / "features.parquet", index=False)
        pd.DataFrame(events).to_parquet(data_dir / "events.parquet", index=False)
        pd.DataFrame(universe).to_parquet(data_dir / "universe.parquet", index=False)

        df, _ = StockRanker(data_dir=str(data_dir), artifact_dir=str(root / "artifacts")).load_daily_data("2024-01-02")
        assert set(df["stock_id"]) == {"1101", "1102"}
        assert int(df.loc[df["stock_id"] == "1101", "event_break_20d_high"].iloc[0]) == 1
        assert int(df.loc[df["stock_id"] == "1102", "event_break_20d_high"].iloc[0]) == 0


def verify_ranking_uses_m4_feature_contract_for_inference() -> None:
    class FakeM4Model:
        def feature_name(self):
            return ["ma20", "event_break_20d_high", "fundamental_roe"]

        def predict(self, X):
            assert "event_break_20d_high" in X.columns
            assert "fundamental_roe" in X.columns
            assert X["event_break_20d_high"].notna().all()
            assert X["fundamental_roe"].notna().all()
            return [0.7] * len(X)

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data_dir = root / "data"
        data_dir.mkdir()
        rows = []
        events = []
        universe = []
        dates = pd.bdate_range("2024-01-02", periods=25)
        for date_index, date in enumerate(dates):
            rows.append(
                {
                    "date": date,
                    "stock_id": "1101",
                    "open": 10 + date_index,
                    "high": 11 + date_index,
                    "low": 9 + date_index,
                    "close": 10.5 + date_index,
                    "volume": 1000,
                    "ma20": 20,
                    "rsi": 50,
                }
            )
            events.append({"date": date, "stock_id": "1101", "break_20d_high": 1 if date == dates[-1] else 0})
            universe.append({"date": date, "stock_id": "1101", "close": 35, "avg_value_20d": 30_000_000})

        pd.DataFrame(rows).to_parquet(data_dir / "features.parquet", index=False)
        pd.DataFrame(events).to_parquet(data_dir / "events.parquet", index=False)
        pd.DataFrame(universe).to_parquet(data_dir / "universe.parquet", index=False)
        FundamentalRepository(root).write_cached(
            "1101",
            {"metrics": [{"year": "2023", "available_from": "2024-01-01", "roe": 15.0}]},
        )

        ranker = StockRanker(data_dir=str(data_dir), artifact_dir=str(root / "artifacts"))
        df, _ = ranker.load_daily_data(str(dates[-1].date()))
        assert "event_break_20d_high" in df.columns
        assert "fundamental_roe" in df.columns
        ranker.model = FakeM4Model()
        scored = ranker.calculate_scores(df)
        assert float(scored["model_prob"].iloc[0]) == 0.7


def verify_ranking_rejects_duplicate_trade_keys() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        data_dir = root / "data"
        data_dir.mkdir()
        rows = [
            {
                "date": pd.Timestamp("2024-01-02 10:00"),
                "stock_id": "1101",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 1000,
            },
            {
                "date": pd.Timestamp("2024-01-02 11:00"),
                "stock_id": "1101",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.6,
                "volume": 1000,
            },
        ]
        pd.DataFrame(rows).to_parquet(data_dir / "features.parquet", index=False)
        try:
            StockRanker(data_dir=str(data_dir), artifact_dir=str(root / "artifacts")).load_daily_data("2024-01-02")
        except ValueError as exc:
            assert "同股同交易日" in str(exc)
            return
        raise AssertionError("duplicate trade keys should be rejected")


def verify_factor_monitor_rejects_duplicate_trade_keys() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        data_dir.mkdir()
        rows = [
            {
                "date": pd.Timestamp("2024-01-02 10:00"),
                "stock_id": "1101",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 1000,
            },
            {
                "date": pd.Timestamp("2024-01-02 11:00"),
                "stock_id": "1101",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.6,
                "volume": 1000,
            },
        ]
        pd.DataFrame(rows).to_parquet(data_dir / "features.parquet", index=False)
        try:
            FactorMonitor(data_dir=data_dir, artifacts_dir=Path(tmp) / "artifacts")._load_model_frame()
        except ValueError as exc:
            assert "同股同交易日" in str(exc)
            return
        raise AssertionError("factor monitor should reject duplicate trade keys")


def verify_factor_ic_is_daily_cross_sectional() -> None:
    valid = pd.DataFrame(
        {
            "trade_date": [pd.Timestamp("2024-01-02")] * 3 + [pd.Timestamp("2024-01-03")] * 3,
            "stock_id": ["1101", "1102", "1103"] * 2,
            "factor": [1, 2, 3, 1, 2, 3],
            "future_return": [0.1, 0.2, 0.3, 0.3, 0.2, 0.1],
        }
    )
    daily_ic = _daily_cross_sectional_ic(valid)
    assert daily_ic.round(6).tolist() == [1.0, -1.0]


def verify_factor_monitor_warns_when_ic_unavailable() -> None:
    dates = pd.date_range("2024-01-02", periods=5)
    rows = []
    for date in dates:
        for i, stock_id in enumerate(["1101", "1102", "1103"]):
            rows.append(
                {
                    "trade_date": date,
                    "stock_id": stock_id,
                    "constant_factor": 1,
                    "future_return": 0.01 * (i + 1),
                }
            )
    metric = FactorMonitor(min_observations=10)._metric_for_factor(pd.DataFrame(rows), "constant_factor", recent_days=60)
    assert metric.status == "WARN"
    assert metric.ic is None
    assert metric.ic_days == 0


def verify_latest_ranking_uses_filename_date() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifacts = root / "artifacts"
        artifacts.mkdir()
        (root / "data" / "clean").mkdir(parents=True)
        old_file = artifacts / "ranking_2024-01-01.csv"
        new_file = artifacts / "ranking_2024-01-03.csv"
        old_file.write_text("stock_id\n1101\n", encoding="utf-8")
        new_file.write_text("stock_id\n1103\n", encoding="utf-8")
        os.utime(old_file, (2_000_000_000, 2_000_000_000))
        os.utime(new_file, (1_000_000_000, 1_000_000_000))
        df, ranking_date = MarketRepository(root).load_latest_ranking()
        assert ranking_date == "2024-01-03"
        assert df.iloc[0]["stock_id"] == "1103"


def verify_fundamental_cache_rejects_path_fragments() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        repo = FundamentalRepository(Path(tmp))
        try:
            repo.cache_path("../evil")
        except ValueError:
            return
        raise AssertionError("path fragment stock_id should be rejected")


def verify_monitoring_repository_reads_fresh_artifact() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifacts = root / "artifacts"
        artifacts.mkdir()
        path = artifacts / "factor_monitor_report.json"
        path.write_text('{"status": "WARN"}', encoding="utf-8")
        repo = MonitoringRepository(root)
        assert repo.load_factor_report()["status"] == "WARN"
        path.write_text('{"status": "OK"}', encoding="utf-8")
        assert repo.load_factor_report()["status"] == "OK"


def verify_walk_forward_purge() -> None:
    trainer = LightGBMTrainer(horizon=10)
    train_dates = pd.date_range("2024-01-01", periods=20).values
    val_dates = pd.date_range("2024-01-21", periods=5).values
    purged = trainer._purge_train_dates(train_dates, val_dates)
    assert pd.Timestamp(purged.max()) < pd.Timestamp("2024-01-11")


def verify_walk_forward_uses_trade_dates() -> None:
    trainer = LightGBMTrainer(horizon=2)
    df = pd.DataFrame(
        {
            "date": [
                pd.Timestamp("2024-01-02 10:00"),
                pd.Timestamp("2024-01-02 11:00"),
                pd.Timestamp("2024-01-03 10:00"),
            ],
            "stock_id": ["1101", "1102", "1101"],
            "target": [0, 1, 0],
        }
    )
    with_trade_date = trainer._with_trade_date(df)
    unique_dates = trainer._unique_trade_dates(with_trade_date)
    assert [pd.Timestamp(date).strftime("%Y-%m-%d") for date in unique_dates] == ["2024-01-02", "2024-01-03"]


def verify_modeling_rejects_duplicate_label_keys() -> None:
    trainer = LightGBMTrainer(horizon=2)
    df = pd.DataFrame(
        {
            "date": [pd.Timestamp("2024-01-02 10:00"), pd.Timestamp("2024-01-02 11:00")],
            "stock_id": ["1101", "1101"],
            "open": [10, 11],
            "close": [10.5, 11.5],
        }
    )
    try:
        trainer.generate_labels(df)
    except ValueError as exc:
        assert "同股同交易日" in str(exc)
        return
    raise AssertionError("modeling labels should reject duplicate trade keys")


def verify_validator_rejects_duplicate_trade_keys() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        clean_dir = root / "clean"
        clean_dir.mkdir()
        df = pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2024-01-02 10:00"),
                    "stock_id": "1101",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10.5,
                    "volume": 1000,
                    "ma5": 10,
                    "ma20": 10,
                    "rsi": 50,
                    "macd": 0,
                    "macd_signal": 0,
                    "bb_middle": 10,
                    "avg_value_20d": 30_000_000,
                },
                {
                    "date": pd.Timestamp("2024-01-02 11:00"),
                    "stock_id": "1101",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10.6,
                    "volume": 1000,
                    "ma5": 10,
                    "ma20": 10,
                    "rsi": 50,
                    "macd": 0,
                    "macd_signal": 0,
                    "bb_middle": 10,
                    "avg_value_20d": 30_000_000,
                },
            ]
        )
        path = clean_dir / "features.parquet"
        df.to_parquet(path, index=False)
        validator = PipelineDataValidator(data_dir=root)
        summary = validator.validate_contract(validator.features_contract())
        assert any("交易日/股票主鍵重複" in issue.message for issue in summary.issues)


def verify_m4_feature_contract_rejects_duplicate_trade_keys() -> None:
    df = pd.DataFrame(
        [
            {
                "date": pd.Timestamp("2024-01-02 10:00"),
                "stock_id": "1101",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.5,
                "volume": 1000,
                "ma20": 10,
            },
            {
                "date": pd.Timestamp("2024-01-02 11:00"),
                "stock_id": "1101",
                "open": 10,
                "high": 11,
                "low": 9,
                "close": 10.6,
                "volume": 1000,
                "ma20": 10,
            },
        ]
    )
    try:
        build_m4_feature_frame(df)
    except ValueError as exc:
        assert "同股同交易日" in str(exc)
        return
    raise AssertionError("M4 feature contract should reject duplicate trade keys")


def verify_m4_feature_contract_preserves_missing_fundamentals() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        features = pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2024-01-02"),
                    "stock_id": "1101",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10.5,
                    "volume": 1000,
                    "ma20": 10,
                }
            ]
        )
        events = pd.DataFrame([{"date": pd.Timestamp("2024-01-02"), "stock_id": "1101", "break_20d_high": 1}])
        frame, metadata = build_m4_feature_frame(features, events, FundamentalRepository(Path(tmp)))
        assert len(frame) == 1
        assert frame["fundamental_roe"].isna().all()
        assert metadata.fundamental_cache_coverage == 0
        assert "fundamental_roe" in metadata.feature_groups["fundamental"].columns
        assert "event_break_20d_high" in candidate_feature_columns(frame, metadata)
        assert "fundamental_roe" not in candidate_feature_columns(frame, metadata)


def verify_ranking_policy_score_decomposition() -> None:
    df = pd.DataFrame(
        [
            {
                "stock_id": "HIGH_RISK",
                "model_prob": 0.98,
                "raw_prob": 0.98,
                "final_score": 0.98,
                "rule_score": 1.0,
                "rule_score_norm": 0.2,
                "avg_value_20d": 1_000_000,
                "close": 90,
                "ma20": 100,
                "low_20d": 85,
                "rsi": 84,
                "risk_signals": "長上影線|",
            },
            {
                "stock_id": "BALANCED",
                "model_prob": 0.65,
                "raw_prob": 0.65,
                "final_score": 0.65,
                "rule_score": 3.0,
                "rule_score_norm": 0.8,
                "avg_value_20d": 80_000_000,
                "close": 110,
                "ma20": 100,
                "low_20d": 95,
                "rsi": 55,
                "risk_signals": "",
                "fundamental_roe": 16,
                "fundamental_gross_margin": 42,
                "fundamental_debt_ratio": 35,
            },
        ]
    )
    ranked = RankingPolicy().apply(
        df,
        MarketRegime("NEUTRAL", 1.0, breadth_ma20=0.5, breakout_ratio=0.2, avg_rsi=55, notes="test"),
    )
    required = {"prediction_score", "setup_score", "quality_score", "risk_penalty", "risk_adjusted_score"}
    assert required.issubset(ranked.columns)
    for _, row in ranked.iterrows():
        expected = row["prediction_score"] + row["setup_score"] + row["quality_score"] - row["risk_penalty"]
        assert abs(row["risk_adjusted_score"] - max(expected, 0)) < 1e-9
    assert ranked.iloc[0]["stock_id"] == "BALANCED"
    high_risk = ranked.loc[ranked["stock_id"] == "HIGH_RISK"].iloc[0]
    assert high_risk["prediction_score"] > 0.9
    assert high_risk["risk_penalty"] >= 1.0


def verify_ranking_policy_ignores_fundamentals_until_gate_passes() -> None:
    base = pd.DataFrame(
        [
            {
                "stock_id": "BASE",
                "model_prob": 0.6,
                "final_score": 0.6,
                "rule_score_norm": 0.5,
                "avg_value_20d": 30_000_000,
                "close": 100,
                "ma20": 95,
            }
        ]
    )
    with_fundamentals = base.assign(
        fundamental_roe=30,
        fundamental_gross_margin=80,
        fundamental_debt_ratio=5,
    )
    regime = MarketRegime("NEUTRAL", 1.0, breadth_ma20=0.5, breakout_ratio=0.2, avg_rsi=55, notes="test")
    base_ranked = RankingPolicy().apply(base, regime)
    fundamental_ranked = RankingPolicy().apply(with_fundamentals, regime)
    assert abs(base_ranked["quality_score"].iloc[0] - fundamental_ranked["quality_score"].iloc[0]) < 1e-9
    assert abs(base_ranked["risk_adjusted_score"].iloc[0] - fundamental_ranked["risk_adjusted_score"].iloc[0]) < 1e-9


def verify_latest_ranking_backfills_score_decomposition() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        artifacts = root / "artifacts"
        clean = root / "data" / "clean"
        artifacts.mkdir()
        clean.mkdir(parents=True)
        pd.DataFrame(
            [
                {
                    "date": pd.Timestamp("2024-01-02"),
                    "stock_id": "1101",
                    "open": 10,
                    "high": 11,
                    "low": 9,
                    "close": 10.5,
                    "volume": 1000,
                }
            ]
        ).to_parquet(clean / "features.parquet", index=False)
        (artifacts / "ranking_2024-01-02.csv").write_text(
            "stock_id,final_score,model_prob,rule_score\n1101,0.5,0.6,0\n1102,0.4,0.9,2\n",
            encoding="utf-8",
        )
        response = MarketService(MarketRepository(root)).latest_ranking()
        item = response.items[0]
        assert item.stock_id == "1102"
        assert item.prediction_score == 0.9
        assert item.setup_score == 1.0
        assert item.quality_score == 0.5
        assert item.risk_penalty == 0.0
        assert item.risk_adjusted_score == 2.4
        assert item.suggested_weight is not None and item.suggested_weight > 0
        assert item.max_position_weight is not None and item.suggested_weight <= item.max_position_weight
        assert item.gross_exposure is not None and item.gross_exposure > 0
        assert item.allocated_exposure is not None and item.allocated_exposure > 0
        assert item.cash_weight is not None and item.cash_weight < 1


def verify_portfolio_policy_allocation_caps() -> None:
    df = pd.DataFrame(
        [
            {"stock_id": "A", "risk_adjusted_score": 3.0, "risk_penalty": 0.0},
            {"stock_id": "B", "risk_adjusted_score": 2.0, "risk_penalty": 0.1},
            {"stock_id": "C", "risk_adjusted_score": 1.5, "risk_penalty": 1.2},
            {"stock_id": "D", "risk_adjusted_score": 1.0, "risk_penalty": 0.0},
        ]
    )
    policy = PortfolioPolicy(base_max_position_weight=0.2)
    risk_on = policy.apply(df, MarketRegime("RISK_ON", 1.08, 0.6, 0.2, 55, "on"))
    risk_off = policy.apply(df, MarketRegime("RISK_OFF", 0.72, 0.3, 0.1, 45, "off"))

    required = {"suggested_weight", "max_position_weight", "gross_exposure", "allocated_exposure", "cash_weight", "exposure_note"}
    assert required.issubset(risk_on.columns)
    assert risk_on["suggested_weight"].sum() <= risk_on["gross_exposure"].iloc[0] + 1e-9
    assert risk_on["allocated_exposure"].iloc[0] == round(float(risk_on["suggested_weight"].sum()), 4)
    assert (risk_on["suggested_weight"] <= risk_on["max_position_weight"] + 1e-9).all()
    assert risk_off["gross_exposure"].iloc[0] < risk_on["gross_exposure"].iloc[0]

    high_risk_weight = risk_on.loc[risk_on["stock_id"] == "C", "suggested_weight"].iloc[0]
    low_risk_weight = risk_on.loc[risk_on["stock_id"] == "B", "suggested_weight"].iloc[0]
    assert high_risk_weight < low_risk_weight
    assert risk_on["cash_weight"].iloc[0] == round(1 - float(risk_on["suggested_weight"].sum()), 4)


def verify_ranking_missing_features_raises() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        try:
            StockRanker(data_dir=str(Path(tmp) / "missing"), artifact_dir=str(Path(tmp) / "artifacts")).run_ranking()
        except FileNotFoundError:
            return
        raise AssertionError("missing features should raise")


if __name__ == "__main__":
    raise SystemExit(main())
