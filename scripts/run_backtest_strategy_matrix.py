#!/usr/bin/env python3
"""執行 portfolio replay 策略矩陣。

此腳本只讀既有 ranking artifacts 與 features parquet，不訓練模型、不重跑 ETL。
用途是比較 horizon、停損、停利、同族群曝險上限等參數組合的穩定度。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_portfolio_replay  # noqa: E402
from scripts import run_autonomous_research as regime_research  # noqa: E402
from app.research.parameter_catalog import (  # noqa: E402
    entrypoint_cli_defaults,
    validate_executable_parameters,
)


SCHEMA_VERSION = "backtest-strategy-matrix.v1"
MAX_DRAWDOWN_LIMIT = -0.25
NEIGHBOR_P_VALUE_LIMIT = 0.05
SCENARIO_PARAMETER_FIELDS = ("horizon", "stop_loss_pct", "take_profit_pct", "max_group_exposure")
TRUSTED_RESEARCH_CONTRACT_PATH = PROJECT_ROOT / "config" / "regime_research_contract.json"
MATRIX_CLI_DEFAULTS = entrypoint_cli_defaults("strategy_matrix")


def _file_sha256(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def _execution_settings(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "max_ranking_files": args.max_ranking_files,
        "top_n": args.top_n,
        "max_gross_exposure": args.max_gross_exposure,
        "max_position_weight": args.max_position_weight,
        "fee_rate": args.fee_rate,
        "tax_rate": args.tax_rate,
        "slippage_rate": args.slippage_rate,
        "same_day_hit_priority": args.same_day_hit_priority,
        "runner_policy_version": "strategy-matrix-replay.v1",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run backtest strategy matrix")
    parser.add_argument("--rankings-dir", default="artifacts")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument(
        "--max-ranking-files",
        type=int,
        default=None,
        help="限制處理最近 N 份 ranking；預設跑完整期間，避免正式研究誤用抽樣結果",
    )
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--horizons", default=MATRIX_CLI_DEFAULTS["horizon"])
    parser.add_argument("--stop-loss-pcts", default=MATRIX_CLI_DEFAULTS["stop_loss_pct"])
    parser.add_argument("--take-profit-pcts", default=MATRIX_CLI_DEFAULTS["take_profit_pct"])
    parser.add_argument(
        "--max-group-exposures", default=MATRIX_CLI_DEFAULTS["max_group_exposure"]
    )
    parser.add_argument("--max-gross-exposure", type=float, default=0.65)
    parser.add_argument("--max-position-weight", type=float, default=0.2)
    parser.add_argument("--fee-rate", type=float, default=0.001425)
    parser.add_argument("--tax-rate", type=float, default=0.003)
    parser.add_argument("--slippage-rate", type=float, default=0.001)
    parser.add_argument("--same-day-hit-priority", choices=["stop_loss", "take_profit"], default="stop_loss")
    parser.add_argument("--require-exact-regime", action="store_true")
    parser.add_argument("--market-regime-history", default=None)
    parser.add_argument("--base-regime", default=None)
    parser.add_argument("--family-tags", default="")
    parser.add_argument("--allowed-episode-ids", default=None)
    parser.add_argument(
        "--development-only",
        action="store_true",
        help="只允許 immutable development episodes；不接受 pre-registration 或正式候選輸出",
    )
    parser.add_argument("--pre-registration", default=None)
    parser.add_argument("--experiment-registry", default=None)
    parser.add_argument("--output", default=None)
    parser.add_argument("--research-run-id", default=None)
    parser.add_argument("--research-intent-id", default=None)
    parser.add_argument("--research-variant-role", choices=["baseline", "candidate"], default=None)
    parser.add_argument("--requested-trial-spec-ids", default=None)
    return parser.parse_args()


def replay_args(base: argparse.Namespace, scenario: dict[str, Any]) -> argparse.Namespace:
    return argparse.Namespace(
        rankings_dir=base.rankings_dir,
        features=base.features,
        horizon=scenario["horizon"],
        top_n=base.top_n,
        entry_delay_trade_days=1,
        max_ranking_files=base.max_ranking_files,
        initial_cash=1.0,
        max_gross_exposure=base.max_gross_exposure,
        market_regime_history=getattr(base, "market_regime_history", None),
        exact_regime_episode_by_date=getattr(base, "exact_regime_episode_by_date", None),
        big_bull_gross_exposure=None,
        high_choppy_gross_exposure=None,
        other_family_gross_exposure=None,
        max_position_weight=base.max_position_weight,
        fee_rate=base.fee_rate,
        tax_rate=base.tax_rate,
        slippage_rate=base.slippage_rate,
        group_map="data/reference/stock_industry_map.csv",
        group_column="industry_name",
        max_group_exposure=scenario["max_group_exposure"],
        stop_loss_pct=scenario["stop_loss_pct"],
        take_profit_pct=scenario["take_profit_pct"],
        trailing_stop_pct=None,
        min_event_holding_days=1,
        same_day_hit_priority=base.same_day_hit_priority,
        output=None,
    )


def scenario_id(scenario: dict[str, Any]) -> str:
    return "h{horizon}_sl{sl}_tp{tp}_gc{gc}".format(
        horizon=scenario["horizon"],
        sl=fmt_token(scenario["stop_loss_pct"]),
        tp=fmt_token(scenario["take_profit_pct"]),
        gc=fmt_token(scenario["max_group_exposure"]),
    )


def fmt_token(value: Any) -> str:
    if value is None:
        return "none"
    return str(value).replace(".", "p")


def exact_regime_context(
    args: argparse.Namespace,
) -> tuple[dict[str, Any] | None, set[str] | None, dict[str, str] | None]:
    if not bool(args.require_exact_regime):
        return None, None, None
    if not args.market_regime_history or not args.base_regime:
        raise ValueError("--require-exact-regime 必須提供 --market-regime-history 與 --base-regime")
    path = run_portfolio_replay.resolve_path(args.market_regime_history)
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    as_of_check = regime_research.validate_as_of_regime_rows(rows)
    if not as_of_check["ok"]:
        raise ValueError(f"market regime history 不符合 as-of 契約：{as_of_check['violations'][:3]}")
    identity = regime_research.canonical_regime_identity(
        {
            "base_regime": args.base_regime,
            "family_tags": [item.strip() for item in args.family_tags.split(",") if item.strip()],
        }
    )
    requested_episode_ids = {
        item.strip()
        for item in str(getattr(args, "allowed_episode_ids", "") or "").split(",")
        if item.strip()
    }
    if not requested_episode_ids:
        raise ValueError("--require-exact-regime 必須提供 immutable --allowed-episode-ids")
    regime_id = regime_research.regime_identity_id(identity)
    episodes = [
        episode
        for episode in regime_research.build_regime_episodes(rows)
        if episode.get("regime_id") == regime_id
    ]
    by_id = {str(episode["episode_id"]): episode for episode in episodes}
    missing_episode_ids = sorted(requested_episode_ids - set(by_id))
    if missing_episode_ids:
        raise ValueError(f"immutable episode split 引用了未知 episode IDs：{missing_episode_ids}")
    allowed_dates: set[str] = set()
    episode_by_date: dict[str, str] = {}
    for episode_id in sorted(requested_episode_ids):
        for trade_date in by_id[episode_id]["trade_dates"]:
            if trade_date in episode_by_date:
                raise ValueError(f"immutable episode split 交易日重疊：{trade_date}")
            allowed_dates.add(str(trade_date))
            episode_by_date[str(trade_date)] = episode_id
    if not allowed_dates:
        raise ValueError(f"exact-match 盤勢沒有可用日期：{regime_research.regime_identity_id(identity)}")
    return identity, allowed_dates, episode_by_date


@contextmanager
def exact_ranking_file_scope(allowed_dates: set[str] | None):
    """在 portfolio replay 建立 entry plan 前限制 ranking date。"""

    if allowed_dates is None:
        yield
        return
    replay_module = run_portfolio_replay.run_backtest_replay
    original = replay_module.ranking_files

    def filtered(rankings_dir: Path, max_files: int | None) -> list[Path]:
        files = original(rankings_dir, None)
        exact = [path for path in files if replay_module.ranking_date(path) in allowed_dates]
        if not exact:
            raise FileNotFoundError("ranking artifacts 沒有 exact-match regime 日期")
        return exact[-max_files:] if max_files else exact

    replay_module.ranking_files = filtered
    try:
        yield
    finally:
        replay_module.ranking_files = original


def exact_horizon_safe_ranking_dates(
    allowed_dates: set[str] | None,
    episode_by_date: dict[str, str] | None,
    trade_dates: list[Any],
    *,
    horizon: int,
    entry_delay_trade_days: int = 1,
) -> set[str] | None:
    """排除會讓 D+N holding window 跨出 immutable episode 的 ranking date。"""

    if allowed_dates is None:
        return None
    if episode_by_date is None:
        raise ValueError("exact-match horizon scope 缺少 episode authority")
    safe: set[str] = set()
    for ranking_date in sorted(allowed_dates):
        entry_date = run_portfolio_replay.run_backtest_replay.next_market_trade_date(
            trade_dates,
            ranking_date,
            entry_delay_trade_days,
        )
        if entry_date is None:
            continue
        holding_dates = run_portfolio_replay.run_backtest_replay.market_holding_dates(
            trade_dates,
            entry_date,
            horizon,
        )
        if holding_dates is None:
            continue
        episode_id = episode_by_date.get(ranking_date)
        window_dates = [ranking_date, *(item.isoformat() for item in holding_dates)]
        if episode_id and all(episode_by_date.get(item) == episode_id for item in window_dates):
            safe.add(ranking_date)
    if not safe:
        raise ValueError(
            "NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE: "
            f"horizon={horizon} allowed_date_count={len(allowed_dates)}"
        )
    return safe


def event_counts(trades: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for trade in trades:
        reason = str(trade.get("exit_reason") or "unknown")
        counts[reason] = counts.get(reason, 0) + 1
    return counts


def matrix_row(scenario: dict[str, Any], replay: dict[str, Any]) -> dict[str, Any]:
    summary = replay.get("summary", {})
    total_return = finite(summary.get("total_return"))
    max_drawdown = finite(summary.get("max_drawdown"))
    avg_trade_return = finite(summary.get("avg_trade_return"))
    win_rate = finite(summary.get("win_rate"))
    score = strategy_score(total_return, max_drawdown, win_rate, avg_trade_return)
    statistical_evidence = independent_episode_sign_test(replay.get("trades", []))
    return {
        "scenario_id": scenario_id(scenario),
        "combination_id": regime_research.canonical_json_hash(scenario),
        "horizon": scenario["horizon"],
        "stop_loss_pct": scenario["stop_loss_pct"],
        "take_profit_pct": scenario["take_profit_pct"],
        "max_group_exposure": scenario["max_group_exposure"],
        "final_equity": summary.get("final_equity"),
        "total_return": total_return,
        "max_drawdown": max_drawdown,
        "trade_count": int(summary.get("trade_count") or 0),
        "win_rate": win_rate,
        "avg_trade_return": avg_trade_return,
        "max_gross_exposure": summary.get("max_gross_exposure"),
        "max_group_exposure_observed": summary.get("max_group_exposure"),
        "exit_reason_counts": event_counts(replay.get("trades", [])),
        "score": score,
        "p_value": statistical_evidence["p_value"],
        "statistical_unit_policy": "independent_regime_episode_cluster.v1",
        "statistical_unit_ids": statistical_evidence["statistical_unit_ids"],
        "statistical_unit_count": statistical_evidence["statistical_unit_count"],
        "pseudo_replication_detected": statistical_evidence["pseudo_replication_detected"],
        "pseudo_replication_reasons": statistical_evidence["pseudo_replication_reasons"],
        "robust_neighbor_lineage": [],
        "robust_neighbor_pass_count": 0,
        "drawdown_within_limit": max_drawdown is not None and max_drawdown >= MAX_DRAWDOWN_LIMIT,
    }


def independent_episode_sign_test(trades: list[dict[str, Any]]) -> dict[str, Any]:
    """以獨立 regime episode 聚合報酬，並拒絕重複或跨 alias 重疊交易。"""

    reasons: set[str] = set()
    fingerprints: set[tuple[str, str, str]] = set()
    returns_by_episode: dict[str, list[float]] = {}
    intervals_by_stock: dict[str, list[tuple[str, str, str]]] = {}
    for trade in trades:
        net_return = finite(trade.get("net_return"))
        if net_return is None or net_return == 0:
            continue
        episode_id = str(trade.get("regime_episode_id") or "")
        stock_id = str(trade.get("stock_id") or "")
        entry_date = str(trade.get("entry_date") or "")
        exit_date = str(trade.get("exit_date") or "")
        if not episode_id:
            reasons.add("MISSING_INDEPENDENT_EPISODE_ID")
            continue
        if not stock_id or not entry_date or not exit_date:
            reasons.add("MISSING_TRADE_IDENTITY")
            continue
        fingerprint = (stock_id, entry_date, exit_date)
        if fingerprint in fingerprints:
            reasons.add("DUPLICATE_TRADE_IDENTITY")
        fingerprints.add(fingerprint)
        returns_by_episode.setdefault(episode_id, []).append(net_return)
        intervals_by_stock.setdefault(stock_id, []).append((entry_date, exit_date, episode_id))
    for intervals in intervals_by_stock.values():
        active: list[tuple[str, str]] = []
        for entry_date, exit_date, episode_id in sorted(intervals):
            active = [(end_date, prior_episode) for end_date, prior_episode in active if end_date >= entry_date]
            if any(prior_episode != episode_id for _, prior_episode in active):
                reasons.add("OVERLAPPING_ALIAS_EPISODES")
            active.append((exit_date, episode_id))
    cluster_returns = [
        sum(values) / len(values)
        for _, values in sorted(returns_by_episode.items())
        if values
    ]
    non_zero = [value for value in cluster_returns if value != 0]
    if not non_zero:
        p_value = None
    else:
        wins = sum(value > 0 for value in non_zero)
        sample_count = len(non_zero)
        tail = sum(math.comb(sample_count, count) for count in range(wins, sample_count + 1))
        p_value = round(tail / (2**sample_count), 12)
    return {
        "p_value": p_value,
        "statistical_unit_ids": sorted(returns_by_episode),
        "statistical_unit_count": len(non_zero),
        "pseudo_replication_detected": bool(reasons),
        "pseudo_replication_reasons": sorted(reasons),
    }


def bind_trade_episode_clusters(
    replay: dict[str, Any],
    episode_by_date: dict[str, str] | None,
) -> dict[str, Any]:
    """以 immutable ranking-date episode map 綁定統計 cluster，不信任 trade payload alias。"""

    if episode_by_date is None:
        return replay
    trades = [
        {
            **trade,
            "regime_episode_id": episode_by_date.get(str(trade.get("ranking_date") or "")),
        }
        for trade in replay.get("trades", [])
    ]
    return {**replay, "trades": trades}


def exact_sign_test_p_value(trades: list[dict[str, Any]]) -> float | None:
    return independent_episode_sign_test(trades)["p_value"]


def annotate_statistical_lineage(rows: list[dict[str, Any]], *, correction_family_id: str) -> None:
    for row in rows:
        lineage = []
        for neighbor in rows:
            if neighbor is row:
                continue
            differing_fields = sum(row.get(field) != neighbor.get(field) for field in SCENARIO_PARAMETER_FIELDS)
            if differing_fields != 1:
                continue
            p_value = finite(neighbor.get("p_value"))
            if (
                p_value is not None
                and p_value <= NEIGHBOR_P_VALUE_LIMIT
                and bool(neighbor.get("drawdown_within_limit"))
                and (finite(neighbor.get("total_return")) or 0.0) > 0
            ):
                lineage.append(str(neighbor["combination_id"]))
        row["correction_family_id"] = correction_family_id
        row["robust_neighbor_lineage"] = sorted(lineage)
        row["robust_neighbor_pass_count"] = len(lineage)


def finite(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def strategy_score(
    total_return: float | None,
    max_drawdown: float | None,
    win_rate: float | None,
    avg_trade_return: float | None,
) -> float | None:
    if total_return is None or max_drawdown is None:
        return None
    drawdown_penalty = abs(min(max_drawdown, 0.0))
    win_bonus = (win_rate or 0.0) * 0.1
    trade_bonus = (avg_trade_return or 0.0) * 2
    return round(total_return - drawdown_penalty + win_bonus + trade_bonus, 6)


def score_sort_value(item: dict[str, Any]) -> float:
    score = item.get("score")
    return float(score) if score is not None else -999.0


def expected_statistical_family(args: argparse.Namespace) -> dict[str, Any] | None:
    if (
        bool(getattr(args, "development_only", False))
        or not bool(args.require_exact_regime)
        or not getattr(args, "pre_registration", None)
    ):
        return None
    path = run_portfolio_replay.resolve_path(args.pre_registration)
    payload = json.loads(path.read_text(encoding="utf-8"))
    registry_path_value = getattr(args, "experiment_registry", None)
    registry_path = (
        run_portfolio_replay.resolve_path(registry_path_value)
        if registry_path_value
        else None
    )
    registry: list[dict[str, Any]] = []
    if registry_path and registry_path.exists():
        registry = [
            json.loads(line)
            for line in registry_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    contract = json.loads(TRUSTED_RESEARCH_CONTRACT_PATH.read_text(encoding="utf-8"))
    trusted_authority = regime_research.statistical_family_contract(contract)
    expected_regime_id = regime_research.regime_identity_id(
        {
            "base_regime": args.base_regime,
            "family_tags": [
                item.strip()
                for item in str(getattr(args, "family_tags", "") or "").split(",")
                if item.strip()
            ],
        }
    )
    allowed_episode_ids = [
        item.strip()
        for item in str(getattr(args, "allowed_episode_ids", "") or "").split(",")
        if item.strip()
    ]
    history_path = run_portfolio_replay.resolve_path(args.market_regime_history)
    history = json.loads(history_path.read_text(encoding="utf-8"))
    history_rows = history.get("rows") if isinstance(history.get("rows"), list) else []
    expected_lineage = regime_research.statistical_lineage_authority(
        rows=history_rows,
        contract=contract,
        regime_id=expected_regime_id,
        horizons=[
            int(item.strip())
            for item in str(args.horizons).split(",")
            if item.strip()
        ],
    )
    validation = regime_research.validate_statistical_family_registration(
        payload,
        contract=contract,
        registry=registry,
        expected_regime_id=expected_regime_id,
        expected_development_episode_ids=allowed_episode_ids,
        expected_lineage=expected_lineage,
    )
    return {
        "tested_combination_ids": payload.get("tested_combination_ids"),
        "tested_combination_ids_hash": payload.get("tested_combination_ids_hash"),
        "correction_family_combination_ids": payload.get("correction_family_combination_ids"),
        "correction_family_id": payload.get("correction_family_id"),
        "correction_family_size": payload.get("correction_family_size"),
        "partition_policy": payload.get("partition_policy"),
        "contract_hash": payload.get("contract_hash"),
        "global_combination_ids_hash": payload.get("global_combination_ids_hash"),
        "registry_record_hash": payload.get("registry_record_hash"),
        "minimum_statistical_unit_count": trusted_authority[
            "minimum_statistical_unit_count"
        ],
        "registration_valid": validation["ok"],
        "registration_validation_reason": validation["reason_code"],
    }


def validate_development_scope(args: argparse.Namespace) -> dict[str, Any] | None:
    if not bool(getattr(args, "development_only", False)):
        return None
    if not bool(args.require_exact_regime):
        raise ValueError("--development-only 必須搭配 --require-exact-regime")
    if getattr(args, "pre_registration", None) or getattr(args, "experiment_registry", None):
        raise ValueError("--development-only 禁止 pre-registration 與 experiment registry")
    if not args.market_regime_history or not args.base_regime:
        raise ValueError("--development-only 缺少 exact-regime authority")
    history_path = run_portfolio_replay.resolve_path(args.market_regime_history)
    history = json.loads(history_path.read_text(encoding="utf-8"))
    history_rows = history.get("rows") if isinstance(history.get("rows"), list) else []
    contract = json.loads(TRUSTED_RESEARCH_CONTRACT_PATH.read_text(encoding="utf-8"))
    regime_id = regime_research.regime_identity_id(
        {
            "base_regime": args.base_regime,
            "family_tags": [
                item.strip()
                for item in str(getattr(args, "family_tags", "") or "").split(",")
                if item.strip()
            ],
        }
    )
    lineage = regime_research.statistical_lineage_authority(
        rows=history_rows,
        contract=contract,
        regime_id=regime_id,
        horizons=[
            int(item.strip())
            for item in str(args.horizons).split(",")
            if item.strip()
        ],
    )
    requested = {
        item.strip()
        for item in str(getattr(args, "allowed_episode_ids", "") or "").split(",")
        if item.strip()
    }
    expected = set(lineage["development_episode_ids"])
    if requested != expected:
        raise ValueError(
            "DEVELOPMENT_EPISODE_SCOPE_MISMATCH: "
            f"expected={sorted(expected)} observed={sorted(requested)}"
        )
    excluded = (
        set(lineage["validation_episode_ids"])
        | set(lineage["embargo_episode_ids"])
        | set(lineage["sealed_episode_ids"])
    )
    if requested & excluded:
        raise ValueError("DEVELOPMENT_SCOPE_CONTAINS_NON_DEVELOPMENT_EPISODE")
    return {
        "ok": True,
        "reason_code": "DEVELOPMENT_EPISODES_ONLY",
        "development_episode_ids": sorted(expected),
        "excluded_episode_ids_hash": regime_research.canonical_json_hash(sorted(excluded)),
        "sealed_trade_date_hash": lineage["sealed_trade_date_hash"],
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    scenarios = regime_research.validation_profile_combinations(
        args.horizons,
        args.stop_loss_pcts,
        args.take_profit_pcts,
        args.max_group_exposures,
    )
    validate_executable_parameters(
        {
            parameter: list(dict.fromkeys(row[parameter] for row in scenarios))
            for parameter in SCENARIO_PARAMETER_FIELDS
        }
    )
    development_scope = validate_development_scope(args)
    price_frame = run_portfolio_replay.run_backtest_replay.load_price_frame(
        run_portfolio_replay.resolve_path(args.features)
    )
    expected_family = expected_statistical_family(args)
    regime_identity, allowed_dates, episode_by_date = exact_regime_context(args)
    args.exact_regime_episode_by_date = episode_by_date
    trade_dates = run_portfolio_replay.run_backtest_replay.market_trade_dates(price_frame)
    rows: list[dict[str, Any]] = []
    horizon_safe_ranking_date_counts: dict[str, int] = {}
    for scenario in scenarios:
        horizon_safe_dates = exact_horizon_safe_ranking_dates(
            allowed_dates,
            episode_by_date,
            trade_dates,
            horizon=int(scenario["horizon"]),
            entry_delay_trade_days=1,
        )
        horizon_safe_ranking_date_counts[str(scenario["horizon"])] = len(
            horizon_safe_dates or []
        )
        with exact_ranking_file_scope(horizon_safe_dates):
            try:
                resolved_rankings = run_portfolio_replay.run_backtest_replay.ranking_files(
                    run_portfolio_replay.resolve_path(args.rankings_dir),
                    args.max_ranking_files,
                )
            except FileNotFoundError:
                # replay 本身仍會依既有語意 fail；这里只避免 provenance 探查先改變例外時機。
                resolved_rankings = []
            replay = run_portfolio_replay.run_portfolio_from_price_frame(replay_args(args, scenario), price_frame)
            row = matrix_row(scenario, bind_trade_episode_clusters(replay, episode_by_date))
            features_path = run_portfolio_replay.resolve_path(args.features)
            dataset_manifest = {
                "resolution_status": "RESOLVED" if features_path.is_file() else "UNRESOLVED",
                "files": (
                    [{"name": features_path.name, "hash": _file_sha256(features_path)}]
                    if features_path.is_file()
                    else []
                ),
            }
            episode_authority = development_scope or {"episode_ids": []}
            actual_episode_ids = sorted(
                {
                    str((episode_by_date or {}).get(
                        run_portfolio_replay.run_backtest_replay.ranking_date(path)
                    ))
                    for path in resolved_rankings
                    if (episode_by_date or {}).get(
                        run_portfolio_replay.run_backtest_replay.ranking_date(path)
                    )
                }
            )
            row["execution_authority"] = {
                "research_stage": (
                    regime_research.DEVELOPMENT_SCREEN_STAGE
                    if bool(getattr(args, "development_only", False))
                    else "COARSE_SCREEN"
                ),
                "regime_scope": regime_identity or {"regime_id": "UNSCOPED"},
                "episode_ids": actual_episode_ids,
                "episode_authority_hash": regime_research.canonical_json_hash(
                    episode_authority
                ),
                "episode_authority": episode_authority,
                "dataset_hash": _file_sha256(features_path),
                "dataset_manifest": dataset_manifest,
                "ranking_manifest": {
                    "resolution_status": "RESOLVED",
                    "files": [
                        {"name": path.name, "hash": _file_sha256(path)}
                        for path in resolved_rankings
                    ],
                },
                "execution_settings": _execution_settings(args),
            }
            rows.append(row)
    correction_family_id = str((expected_family or {}).get("correction_family_id") or "")
    annotate_statistical_lineage(rows, correction_family_id=correction_family_id)
    ranked_rows = sorted(rows, key=lambda item: (item["score"] is not None, score_sort_value(item)), reverse=True)
    best = ranked_rows[0] if ranked_rows else None
    if bool(getattr(args, "development_only", False)):
        statistical_gate = {
            "ok": False,
            "reason_code": "DEVELOPMENT_ONLY_NO_FORMAL_GATE",
            "eligible_ids": [],
            "evidence_complete": False,
        }
    else:
        statistical_gate = (
            regime_research.multiple_testing_gate(ranked_rows, expected_family=expected_family)
            if args.require_exact_regime
            else None
        )
    research_stage = (
        regime_research.DEVELOPMENT_SCREEN_STAGE
        if bool(getattr(args, "development_only", False))
        else "COARSE_SCREEN"
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_spine": {
            "run_id": getattr(args, "research_run_id", None),
            "intent_id": getattr(args, "research_intent_id", None),
            "variant_role": getattr(args, "research_variant_role", None),
            "requested_trial_spec_ids": (
                json.loads(getattr(args, "requested_trial_spec_ids", ""))
                if getattr(args, "requested_trial_spec_ids", None)
                else []
            ),
        },
        "contract": {
            "source": "portfolio_replay_matrix",
            "research_stage": research_stage,
            "development_only": bool(getattr(args, "development_only", False)),
            "development_episodes_only": bool(getattr(args, "development_only", False)),
            "sealed_data_read_allowed": False
            if bool(getattr(args, "development_only", False))
            else None,
            "experiment_registry_write_allowed": False
            if bool(getattr(args, "development_only", False))
            else True,
            "model_feature": False,
            "ranking_score_change": False,
            "resource_mode": "read_existing_artifacts_only",
            "features_load_policy": "load_once_per_matrix",
            "same_day_hit_priority": args.same_day_hit_priority,
            "exact_match_regime_required": bool(args.require_exact_regime),
            "transition_and_unknown_excluded": bool(args.require_exact_regime),
            "production_promotion_allowed": False,
            "raw_best_is_diagnostic_only": bool(args.require_exact_regime),
            "formal_candidate_allowed": not bool(getattr(args, "development_only", False)),
        },
        "inputs": {
            "rankings_dir": str(run_portfolio_replay.resolve_path(args.rankings_dir)),
            "features": str(run_portfolio_replay.resolve_path(args.features)),
            "max_ranking_files": args.max_ranking_files,
            "top_n": args.top_n,
            "scenario_count": len(rows),
            "regime_identity": regime_identity,
            "exact_match_ranking_date_count": len(allowed_dates or []),
            "exact_match_episode_ids": sorted(set((episode_by_date or {}).values())),
            "horizon_safe_ranking_date_counts": horizon_safe_ranking_date_counts,
            "market_regime_history": args.market_regime_history,
            "exact_match_dataset_hash": (
                regime_research.canonical_json_hash(sorted(allowed_dates)) if allowed_dates is not None else None
            ),
            "parameter_space_hash": regime_research.canonical_json_hash(scenarios),
            "correction_family_id": rows[0]["correction_family_id"] if rows else None,
            "pre_registration": getattr(args, "pre_registration", None),
            "experiment_registry": getattr(args, "experiment_registry", None),
            "contract_hash": (expected_family or {}).get("contract_hash"),
            "global_combination_ids_hash": (
                (expected_family or {}).get("global_combination_ids_hash")
            ),
            "registry_record_hash": (expected_family or {}).get("registry_record_hash"),
            "development_scope": development_scope,
            "execution_settings": _execution_settings(args),
            "tested_combination_ids_hash": (
                (expected_family or {}).get("tested_combination_ids_hash")
                if args.require_exact_regime
                else None
            ),
        },
        "summary": {
            "scenario_count": len(rows),
            "best_scenario_id": best.get("scenario_id") if best else None,
            "best_score": best.get("score") if best else None,
            "positive_return_count": sum((row.get("total_return") or 0) > 0 for row in rows),
            "negative_return_count": sum((row.get("total_return") or 0) < 0 for row in rows),
            "statistical_gate": statistical_gate,
            "formal_candidate_scenario_ids": (
                []
                if bool(getattr(args, "development_only", False))
                else (statistical_gate or {}).get("eligible_ids", [])
            ),
            "round_decision": (
                "DEVELOPMENT_SIGNAL_ONLY"
                if bool(getattr(args, "development_only", False))
                else
                regime_research.research_round_decision(
                    [{"passed": True} for _ in (statistical_gate or {}).get("eligible_ids", [])],
                    sufficient_evidence=bool((statistical_gate or {}).get("evidence_complete")),
                )
                if args.require_exact_regime
                else None
            ),
        },
        "scenarios": ranked_rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Backtest Strategy Matrix",
        "",
        f"- status：OK",
        f"- scenario_count：{payload['summary']['scenario_count']}",
        f"- best_scenario_id：{payload['summary']['best_scenario_id']}",
        f"- best_score：{payload['summary']['best_score']}",
        "",
        "| Scenario | Return | Max DD | Win | Trades | Score |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["scenarios"][:20]:
        lines.append(
            "| {scenario_id} | {ret} | {dd} | {win} | {trades} | {score} |".format(
                scenario_id=row["scenario_id"],
                ret=pct(row["total_return"]),
                dd=pct(row["max_drawdown"]),
                win=pct(row["win_rate"]),
                trades=row["trade_count"],
                score=row["score"],
            )
        )
    lines.append("")
    return "\n".join(lines)


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    run_date = datetime.now().strftime("%Y-%m-%d")
    output_path = Path(args.output).expanduser() if args.output else PROJECT_ROOT / "artifacts" / "backtest" / f"strategy_matrix_{run_date}.json"
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    md_path = output_path.with_suffix(".md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": str(output_path), "markdown": str(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
