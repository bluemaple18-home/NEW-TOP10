#!/usr/bin/env python3
"""以具名 section 建立三組 exit-rule 研究驗證報告。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Mapping


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_operational_rule_validation_report import regime_map  # noqa: E402


SCHEMA_VERSION = "exit-rule-validation-suite.v1"
MODEL_SHA256 = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"
PROFILES = ("half_year_decision", "portfolio_level", "rolling_regime")

WATCH_POLICIES = [
    "fixed_20d",
    "fixed_30d",
    "fixed_40d",
    "h30_early_tp07",
    "h40_early_tp07",
    "h30_early_tp12",
    "h40_early_tp12",
    "h30_early_tp15",
    "h40_early_tp15",
    "h30_tp18_sl08",
    "h30_tp25_sl10",
    "h30_trail10",
    "h40_trail12",
]

PORTFOLIO_VARIANTS = {
    "h40_fixed65": "artifacts/backtest/portfolio_replay_half_year_dense_h40_fixed65_2026-06-02.json",
    "h40_gross55": "artifacts/backtest/portfolio_replay_half_year_dense_h40_gross55_2026-06-02.json",
    "h40_tp15_fixed65": "artifacts/backtest/portfolio_replay_half_year_dense_h40_tp15_fixed65_2026-06-02.json",
    "h40_tp15_gross55": "artifacts/backtest/portfolio_replay_half_year_dense_h40_tp15_gross55_2026-06-02.json",
    "h30_tp25_sl10_fixed65": "artifacts/backtest/portfolio_replay_half_year_dense_h30_tp25_sl10_fixed65_2026-06-02.json",
    "h30_tp25_sl10_gross55": "artifacts/backtest/portfolio_replay_half_year_dense_h30_tp25_sl10_gross55_2026-06-02.json",
}

ROLLING_VARIANTS = {
    "h40_fixed65": PORTFOLIO_VARIANTS["h40_fixed65"],
    "h40_tp15_fixed65": PORTFOLIO_VARIANTS["h40_tp15_fixed65"],
    "h30_tp25_sl10_fixed65": PORTFOLIO_VARIANTS["h30_tp25_sl10_fixed65"],
    "h40_tp15_gross55": PORTFOLIO_VARIANTS["h40_tp15_gross55"],
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build exit rule validation suite")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--profile", choices=("all", *PROFILES), default="all")
    parser.add_argument(
        "--matrix",
        default="artifacts/backtest/fixed_share_hypothesis_matrix_production_half_year_2026-06-02.json",
    )
    parser.add_argument(
        "--manifest",
        default="artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15/manifest.json",
    )
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def pct(value: Any) -> str:
    return f"{n(value):.2%}"


def compact_policy(label: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy": label,
        "trade_count": row.get("trade_count"),
        "ranking_day_count": row.get("ranking_day_count"),
        "return_on_buy_cash": row.get("return_on_buy_cash"),
        "win_rate": row.get("win_rate"),
        "avg_trade_net_return": row.get("avg_trade_net_return"),
        "median_trade_net_return": row.get("median_trade_net_return"),
        "avg_mae": row.get("avg_mae"),
        "worst_mae": row.get("worst_mae"),
        "avg_mfe": row.get("avg_mfe"),
        "avg_giveback": row.get("avg_giveback"),
        "p90_giveback": row.get("p90_giveback"),
    }


def half_year_deltas(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "return_delta": round(n(row.get("return_on_buy_cash")) - n(baseline.get("return_on_buy_cash")), 6),
        "win_rate_delta": round(n(row.get("win_rate")) - n(baseline.get("win_rate")), 6),
        "avg_mae_delta": round(n(row.get("avg_mae")) - n(baseline.get("avg_mae")), 6),
        "worst_mae_delta": round(n(row.get("worst_mae")) - n(baseline.get("worst_mae")), 6),
        "p90_giveback_delta": round(n(row.get("p90_giveback")) - n(baseline.get("p90_giveback")), 6),
    }


def score_policy(row: dict[str, Any]) -> float:
    # 此分數只重現舊報告的透明排序，不是 production 權重。
    return (
        n(row.get("return_on_buy_cash"))
        + n(row.get("win_rate")) * 0.08
        + n(row.get("worst_mae")) * 0.35
        - n(row.get("p90_giveback")) * 0.18
    )


def choose_candidates(policies: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fixed40 = policies["fixed_40d"]
    early_tp07 = policies["h40_early_tp07"]
    early_tp15 = policies["h40_early_tp15"]
    stop_take = policies["h30_tp25_sl10"]
    candidates = [policies[key] for key in policies if key not in {"fixed_20d", "fixed_30d", "fixed_40d"}]
    ranked = sorted(candidates, key=score_policy, reverse=True)
    return {
        "highest_return_baseline": "fixed_40d",
        "primary_balanced_candidate": "h40_early_tp15",
        "defensive_candidate": "h30_tp25_sl10",
        "reject_early_tp07": True,
        "reject_reason_early_tp07": "7% 早停利勝率很高，但在近半年牛市太早把波段砍掉。",
        "baseline_warning": (
            "fixed_40d 報酬最高，但 worst MAE 與 p90 giveback 太大，不符合小白使用者的風險感受。"
            if n(fixed40.get("worst_mae")) < -0.5
            else "fixed_40d 可保留為高風險參考。"
        ),
        "early_tp07_vs_early_tp15": half_year_deltas(early_tp07, early_tp15),
        "early_tp15_vs_fixed40": half_year_deltas(early_tp15, fixed40),
        "stop_take_vs_fixed40": half_year_deltas(stop_take, fixed40),
        "ranked_candidates": [
            {"policy": row["policy"], "score": round(score_policy(row), 6)} for row in ranked[:8]
        ],
    }


def compact_manifest(path: Path) -> dict[str, Any]:
    manifest = read_json(path)
    rankings = (manifest.get("outputs") or {}).get("rankings") or [{}]
    return {
        "path": repo_path(path),
        "status": manifest.get("status"),
        "ranking_count": (manifest.get("outputs") or {}).get("ranking_count"),
        "first_date": rankings[0].get("date"),
        "last_date": rankings[-1].get("date"),
        "failure_count": len(manifest.get("failures") or []),
    }


def build_half_year_section(date_text: str, matrix_path: str | Path, manifest_path: str | Path) -> dict[str, Any]:
    matrix_file = resolve_path(matrix_path)
    manifest_file = resolve_path(manifest_path)
    matrix = read_json(matrix_file)
    exit_policy = (matrix.get("matrix") or {}).get("exit_policy") or {}
    policies = {key: compact_policy(key, exit_policy.get(key) or {}) for key in WATCH_POLICIES}
    fixed40 = policies["fixed_40d"]
    comparisons = {key: half_year_deltas(row, fixed40) for key, row in policies.items() if key != "fixed_40d"}
    missing = [key for key, row in policies.items() if not row.get("trade_count")]
    return {
        "schema_version": "exit-rule-half-year-decision-report.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date_text,
        "status": "OK" if not missing else "MISSING_INPUT",
        "contract": {
            "research_only": True,
            "fixed_100_share_backtest": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_clawd_message": True,
            "production_default_allowed": False,
            "model_sha256": MODEL_SHA256,
        },
        "inputs": {
            "matrix": repo_path(matrix_file),
            "manifest": compact_manifest(manifest_file),
            "source_matrix_contract": matrix.get("contract") or {},
        },
        "summary": {
            "decision": "EXIT_RULE_RESEARCH_SELECTS_BALANCED_CANDIDATE",
            "primary_candidate": "h40_early_tp15",
            "defensive_candidate": "h30_tp25_sl10",
            "rejected": ["h30_early_tp07", "h40_early_tp07"],
            "next_gate": "PORTFOLIO_LEVEL_REPLAY_FOR_H40_EARLY_TP15_AND_H30_TP25_SL10",
        },
        "candidate_decision": choose_candidates(policies),
        "policies": policies,
        "comparisons_vs_fixed40": comparisons,
        "missing": missing,
    }


def exit_counts(payload: dict[str, Any]) -> dict[str, int]:
    daily = payload.get("daily") or []
    return {
        "scheduled": sum(int(row.get("scheduled_exits") or 0) for row in daily),
        "stop_loss": sum(int(row.get("stop_loss_exits") or 0) for row in daily),
        "take_profit": sum(int(row.get("take_profit_exits") or 0) for row in daily),
        "trailing_stop": sum(int(row.get("trailing_stop_exits") or 0) for row in daily),
    }


def compact_portfolio(label: str, path_text: str | Path) -> dict[str, Any]:
    path = resolve_path(path_text)
    payload = read_json(path)
    summary = payload.get("summary") or {}
    return {
        "label": label,
        "path": repo_path(path),
        "exists": bool(payload),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "trade_count": summary.get("trade_count"),
        "win_rate": summary.get("win_rate"),
        "avg_trade_return": summary.get("avg_trade_return"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "exit_counts": exit_counts(payload),
        "inputs": payload.get("inputs") or {},
    }


def portfolio_delta(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_return_delta": round(n(row.get("total_return")) - n(baseline.get("total_return")), 6),
        "max_drawdown_delta": round(n(row.get("max_drawdown")) - n(baseline.get("max_drawdown")), 6),
        "win_rate_delta": round(n(row.get("win_rate")) - n(baseline.get("win_rate")), 6),
        "avg_gross_delta": round(n(row.get("avg_gross_exposure")) - n(baseline.get("avg_gross_exposure")), 6),
    }


def build_portfolio_section(date_text: str, variants: Mapping[str, str | Path]) -> dict[str, Any]:
    rows = {label: compact_portfolio(label, path) for label, path in variants.items()}
    baseline = rows["h40_fixed65"]
    comparisons = {
        label: portfolio_delta(row, baseline) for label, row in rows.items() if label != "h40_fixed65"
    }
    return {
        "schema_version": "exit-rule-portfolio-level-report.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date_text,
        "status": "OK" if all(row["exists"] for row in rows.values()) else "MISSING_INPUT",
        "contract": {
            "research_only": True,
            "portfolio_level_replay": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "production_default_allowed": False,
        },
        "summary": {
            "decision": "PORTFOLIO_LEVEL_SUPPORTS_EXIT_RULE_SHADOW",
            "highest_return": "h40_fixed65",
            "primary_shadow_candidate": "h40_tp15_fixed65",
            "defensive_shadow_candidate": "h30_tp25_sl10_fixed65",
            "gross55_combination": "MONITOR_ONLY_LOWER_DRAWDOWN_LOWER_RETURN",
            "next_gate": "RUN_ROLLING_OR_REGIME_SLICED_EXIT_RULE_REPLAY",
        },
        "rows": rows,
        "comparisons_vs_h40_fixed65": comparisons,
    }


def read_daily(path_text: str | Path) -> list[dict[str, Any]]:
    return read_json(resolve_path(path_text)).get("daily") or []


def compound(rows: list[dict[str, Any]]) -> float:
    value = 1.0
    for row in rows:
        value *= 1 + n(row.get("daily_return"))
    return value - 1


def max_drawdown(rows: list[dict[str, Any]]) -> float:
    high = None
    worst = 0.0
    for row in rows:
        equity = n(row.get("equity"))
        if equity <= 0:
            continue
        high = equity if high is None else max(high, equity)
        worst = min(worst, equity / high - 1 if high else 0.0)
    return worst


def rolling_rows(rows: list[dict[str, Any]], window: int) -> list[dict[str, Any]]:
    ordered = sorted(rows, key=lambda row: str(row.get("date") or ""))
    result: list[dict[str, Any]] = []
    if len(ordered) < window:
        return result
    for index in range(0, len(ordered) - window + 1):
        sliced = ordered[index : index + window]
        result.append(
            {
                "start_date": sliced[0].get("date"),
                "end_date": sliced[-1].get("date"),
                "return": compound(sliced),
                "max_drawdown": max_drawdown(sliced),
            }
        )
    return result


def rolling_pair(
    baseline_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]], window: int
) -> dict[str, Any]:
    baseline = rolling_rows(baseline_rows, window)
    candidate = rolling_rows(candidate_rows, window)
    pairs = list(zip(baseline, candidate, strict=False))
    if not pairs:
        return {"window": window, "count": 0}
    return_deltas = [candidate_row["return"] - baseline_row["return"] for baseline_row, candidate_row in pairs]
    dd_deltas = [
        candidate_row["max_drawdown"] - baseline_row["max_drawdown"] for baseline_row, candidate_row in pairs
    ]
    return {
        "window": window,
        "count": len(pairs),
        "avg_return_delta": round(sum(return_deltas) / len(return_deltas), 6),
        "worst_return_delta": round(min(return_deltas), 6),
        "best_return_delta": round(max(return_deltas), 6),
        "return_beats_rate": round(sum(item > 0 for item in return_deltas) / len(return_deltas), 6),
        "avg_drawdown_delta": round(sum(dd_deltas) / len(dd_deltas), 6),
        "drawdown_improves_rate": round(sum(item > 0 for item in dd_deltas) / len(dd_deltas), 6),
    }


def labels_for(date_text: str, regimes: dict[str, dict[str, Any]]) -> list[str]:
    info = regimes.get(date_text) or {}
    labels = ["ALL", str(info.get("base_regime") or "UNKNOWN")]
    if info.get("BIG_BULL"):
        labels.append("BIG_BULL")
    if info.get("HIGH_CHOPPY_CONTEXT"):
        labels.append("HIGH_CHOPPY_CONTEXT")
    if not info.get("BIG_BULL") and not info.get("HIGH_CHOPPY_CONTEXT"):
        labels.append("OTHER_FAMILY")
    return labels


def regime_slices(rows: list[dict[str, Any]], regimes: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        date_text = str(row.get("date") or "")
        for label in labels_for(date_text, regimes):
            buckets.setdefault(label, []).append(row)
    return {
        label: {
            "daily_count": len(items),
            "compound_return": round(compound(items), 6),
            "max_drawdown": round(max_drawdown(items), 6),
            "positive_day_rate": round(sum(n(row.get("daily_return")) > 0 for row in items) / len(items), 6)
            if items
            else None,
        }
        for label, items in sorted(buckets.items())
        if items
    }


def compact_rolling(
    label: str, path_text: str | Path, regimes: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    path = resolve_path(path_text)
    payload = read_json(path)
    summary = payload.get("summary") or {}
    daily = payload.get("daily") or []
    return {
        "label": label,
        "path": repo_path(path),
        "exists": bool(payload),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "win_rate": summary.get("win_rate"),
        "trade_count": summary.get("trade_count"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "by_regime": regime_slices(daily, regimes),
    }


def compare_regime(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    candidate_regimes = candidate.get("by_regime") or {}
    baseline_regimes = baseline.get("by_regime") or {}
    result = {}
    for label in sorted(set(candidate_regimes) | set(baseline_regimes)):
        cand = candidate_regimes.get(label) or {}
        base = baseline_regimes.get(label) or {}
        result[label] = {
            "daily_count": cand.get("daily_count") or base.get("daily_count"),
            "return_delta": round(n(cand.get("compound_return")) - n(base.get("compound_return")), 6),
            "drawdown_delta": round(n(cand.get("max_drawdown")) - n(base.get("max_drawdown")), 6),
            "positive_day_rate_delta": round(
                n(cand.get("positive_day_rate")) - n(base.get("positive_day_rate")), 6
            ),
        }
    return result


def choose_contextual_rules(
    rows: dict[str, dict[str, Any]], regime_comparisons: dict[str, Any]
) -> dict[str, Any]:
    baseline = rows["h40_fixed65"]
    tp15 = rows["h40_tp15_fixed65"]
    stop_take = rows["h30_tp25_sl10_fixed65"]
    tp15_regime = regime_comparisons["h40_tp15_fixed65"]
    gross_tp15_regime = regime_comparisons["h40_tp15_gross55"]

    def candidate_score(candidate: str, regime_label: str) -> float:
        row = (regime_comparisons.get(candidate) or {}).get(regime_label) or {}
        # 情境路由只重現舊報告的透明分數，不是 production 權重。
        return n(row.get("return_delta")) + n(row.get("drawdown_delta")) * 4 + n(
            row.get("positive_day_rate_delta")
        ) * 0.03

    def best_candidate(regime_label: str, candidates: list[str]) -> str:
        return max(candidates, key=lambda candidate: candidate_score(candidate, regime_label))

    candidates = ["h40_tp15_fixed65", "h30_tp25_sl10_fixed65", "h40_tp15_gross55"]
    return {
        "overall_default": "h40_fixed65",
        "overall_shadow": "h40_tp15_fixed65",
        "defensive_shadow": "h30_tp25_sl10_fixed65",
        "big_bull_preference": (
            "h40_fixed65"
            if n((tp15_regime.get("BIG_BULL") or {}).get("return_delta")) < -0.05
            else "h40_tp15_fixed65"
        ),
        "high_choppy_preference": best_candidate("HIGH_CHOPPY_CONTEXT", candidates),
        "risk_off_preference": best_candidate("RISK_OFF", candidates),
        "context_scores": {
            regime_label: {
                candidate: round(candidate_score(candidate, regime_label), 6) for candidate in candidates
            }
            for regime_label in ("HIGH_CHOPPY_CONTEXT", "RISK_OFF")
        },
        "notes": [
            f"fixed65 total={n(baseline.get('total_return')):.2%}, dd={n(baseline.get('max_drawdown')):.2%}",
            f"tp15 total={n(tp15.get('total_return')):.2%}, dd={n(tp15.get('max_drawdown')):.2%}",
            f"stop_take total={n(stop_take.get('total_return')):.2%}, dd={n(stop_take.get('max_drawdown')):.2%}",
            f"gross_tp15 risk_off_dd_delta={n((gross_tp15_regime.get('RISK_OFF') or {}).get('drawdown_delta')):.2%}",
        ],
    }


def build_rolling_section(
    date_text: str, market_regime_history: str | Path, variants: Mapping[str, str | Path]
) -> dict[str, Any]:
    regimes = regime_map(resolve_path(market_regime_history))
    rows = {label: compact_rolling(label, path, regimes) for label, path in variants.items()}
    daily = {label: read_daily(path) for label, path in variants.items()}
    baseline = rows["h40_fixed65"]
    rolling = {
        label: {
            "20d": rolling_pair(daily["h40_fixed65"], daily[label], 20),
            "40d": rolling_pair(daily["h40_fixed65"], daily[label], 40),
        }
        for label in variants
        if label != "h40_fixed65"
    }
    regime_comparisons = {
        label: compare_regime(rows[label], baseline) for label in variants if label != "h40_fixed65"
    }
    return {
        "schema_version": "exit-rule-rolling-regime-report.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date_text,
        "status": "OK" if all(row["exists"] for row in rows.values()) else "MISSING_INPUT",
        "contract": {
            "research_only": True,
            "rolling_and_regime_sliced": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "production_default_allowed": False,
        },
        "summary": {
            "decision": "EXIT_RULE_CONTEXTUAL_ROUTING_CANDIDATE",
            "next_gate": "WIRE_CONTEXTUAL_EXIT_RULES_TO_DAILY_SHADOW_MONITOR",
        },
        "contextual_rules": choose_contextual_rules(rows, regime_comparisons),
        "rows": rows,
        "rolling_vs_h40_fixed65": rolling,
        "regime_vs_h40_fixed65": regime_comparisons,
    }


def build_section(
    profile: str,
    *,
    date_text: str,
    matrix_path: str | Path,
    manifest_path: str | Path,
    market_regime_history: str | Path,
    portfolio_variants: Mapping[str, str | Path] = PORTFOLIO_VARIANTS,
    rolling_variants: Mapping[str, str | Path] = ROLLING_VARIANTS,
) -> dict[str, Any]:
    if profile == "half_year_decision":
        return build_half_year_section(date_text, matrix_path, manifest_path)
    if profile == "portfolio_level":
        return build_portfolio_section(date_text, portfolio_variants)
    if profile == "rolling_regime":
        return build_rolling_section(date_text, market_regime_history, rolling_variants)
    raise ValueError(f"unsupported exit-rule profile: {profile}")


def build_suite(date_text: str, sections: Mapping[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date_text,
        "status": "OK" if all(section.get("status") == "OK" for section in sections.values()) else "MISSING_INPUT",
        "contract": {
            "research_only": True,
            "profile_specific_sections": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_default_allowed": False,
        },
        "summary": {
            "profiles": list(sections),
            "decisions": {profile: section["summary"]["decision"] for profile, section in sections.items()},
        },
        "sections": dict(sections),
    }


def render_half_year_markdown(payload: dict[str, Any]) -> str:
    policies = payload["policies"]
    comparisons = payload["comparisons_vs_fixed40"]
    lines = [
        "# Exit Rule Half-Year Decision Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['summary']['decision']}`",
        f"- primary_candidate: `{payload['summary']['primary_candidate']}`",
        f"- defensive_candidate: `{payload['summary']['defensive_candidate']}`",
        f"- next_gate: `{payload['summary']['next_gate']}`",
        "",
        "## Key Policies",
        "",
        "| Policy | Return | Win | Avg MAE | Worst MAE | P90 Giveback | Δ Return vs fixed40 | Δ Worst MAE |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ["fixed_40d", "h40_early_tp07", "h40_early_tp15", "h30_tp25_sl10", "h30_tp18_sl08", "h40_trail12"]:
        row = policies[key]
        comp = comparisons.get(key) or {}
        lines.append(
            "| {policy} | {ret} | {win} | {mae} | {worst} | {giveback} | {dret} | {dworst} |".format(
                policy=key,
                ret=pct(row.get("return_on_buy_cash")),
                win=pct(row.get("win_rate")),
                mae=pct(row.get("avg_mae")),
                worst=pct(row.get("worst_mae")),
                giveback=pct(row.get("p90_giveback")),
                dret=pct(comp.get("return_delta")) if comp else "--",
                dworst=pct(comp.get("worst_mae_delta")) if comp else "--",
            )
        )
    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            f"- {payload['candidate_decision']['baseline_warning']}",
            f"- {payload['candidate_decision']['reject_reason_early_tp07']}",
            "- `h40_early_tp15` 是主要候選：保留較多牛市波段，同時降低回吐與極端 MAE。",
            "- `h30_tp25_sl10` 是防守候選：犧牲勝率，但把 worst MAE 壓得更低。",
            "",
        ]
    )
    return "\n".join(lines)


def render_portfolio_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    comps = payload["comparisons_vs_h40_fixed65"]
    lines = [
        "# Exit Rule Portfolio-Level Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['summary']['decision']}`",
        f"- primary_shadow_candidate: `{payload['summary']['primary_shadow_candidate']}`",
        f"- defensive_shadow_candidate: `{payload['summary']['defensive_shadow_candidate']}`",
        "",
        "| Variant | Return | DD | Win | Avg Gross | Take | Stop | Δ Return | Δ DD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in PORTFOLIO_VARIANTS:
        row = rows[label]
        comp = comps.get(label) or {}
        exits = row["exit_counts"]
        lines.append(
            "| {label} | {ret} | {dd} | {win} | {gross} | {take} | {stop} | {dret} | {ddd} |".format(
                label=label,
                ret=pct(row.get("total_return")),
                dd=pct(row.get("max_drawdown")),
                win=pct(row.get("win_rate")),
                gross=pct(row.get("avg_gross_exposure")),
                take=exits.get("take_profit", 0),
                stop=exits.get("stop_loss", 0),
                dret=pct(comp.get("total_return_delta")) if comp else "--",
                ddd=pct(comp.get("max_drawdown_delta")) if comp else "--",
            )
        )
    lines.append("")
    return "\n".join(lines)


def render_rolling_markdown(payload: dict[str, Any]) -> str:
    rows = payload["rows"]
    rolling = payload["rolling_vs_h40_fixed65"]
    rules = payload["contextual_rules"]
    lines = [
        "# Exit Rule Rolling / Regime Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['summary']['decision']}`",
        f"- overall_default: `{rules['overall_default']}`",
        f"- overall_shadow: `{rules['overall_shadow']}`",
        f"- big_bull_preference: `{rules['big_bull_preference']}`",
        f"- high_choppy_preference: `{rules['high_choppy_preference']}`",
        f"- risk_off_preference: `{rules['risk_off_preference']}`",
        "",
        "## Overall",
        "",
        "| Variant | Return | DD | Win | 20D Ret Beat | 20D DD Improve | 40D Ret Beat | 40D DD Improve |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for label in ROLLING_VARIANTS:
        row = rows[label]
        roll = rolling.get(label) or {}
        lines.append(
            "| {label} | {ret} | {dd} | {win} | {r20} | {d20} | {r40} | {d40} |".format(
                label=label,
                ret=pct(row.get("total_return")),
                dd=pct(row.get("max_drawdown")),
                win=pct(row.get("win_rate")),
                r20=pct((roll.get("20d") or {}).get("return_beats_rate")) if roll else "--",
                d20=pct((roll.get("20d") or {}).get("drawdown_improves_rate")) if roll else "--",
                r40=pct((roll.get("40d") or {}).get("return_beats_rate")) if roll else "--",
                d40=pct((roll.get("40d") or {}).get("drawdown_improves_rate")) if roll else "--",
            )
        )
    lines.append("")
    return "\n".join(lines)


SECTION_RENDERERS = {
    "half_year_decision": render_half_year_markdown,
    "portfolio_level": render_portfolio_markdown,
    "rolling_regime": render_rolling_markdown,
}


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Exit Rule Validation Suite",
        "",
        f"- status: `{payload['status']}`",
        f"- profiles: `{', '.join(payload['summary']['profiles'])}`",
        "",
    ]
    for profile, section in payload["sections"].items():
        rendered = SECTION_RENDERERS[profile](section).splitlines()
        lines.extend([f"## {profile}", "", *rendered[2:], ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    selected = PROFILES if args.profile == "all" else (args.profile,)
    sections = {
        profile: build_section(
            profile,
            date_text=args.date,
            matrix_path=args.matrix,
            manifest_path=args.manifest,
            market_regime_history=args.market_regime_history,
        )
        for profile in selected
    }
    payload = build_suite(args.date, sections)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"exit_rule_validation_suite_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "profiles": payload["summary"]["profiles"],
                "decisions": payload["summary"]["decisions"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
