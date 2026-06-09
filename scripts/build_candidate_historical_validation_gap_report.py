#!/usr/bin/env python3
"""彙整候選策略長區間驗證缺口與相似盤勢區間。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_high_choppy_context_overlay import load_regime_frame, rolling_high_choppy  # noqa: E402
from scripts.research_regime_family_training_candidates import is_big_bull  # noqa: E402


SCHEMA_VERSION = "candidate-historical-validation-gap-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="建立候選策略長區間驗證缺口報告")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument(
        "--production-rankings-dir",
        default="artifacts/backtest/historical_rankings_current_model_batch_dense_2023-11-21_2026-05-15",
    )
    parser.add_argument(
        "--candidate-rankings-dir",
        default="artifacts/model_experiments/training_candidates/current_baseline_candidate_2026-06-08/candidate_rankings_2025-11-17_2026-05-15",
    )
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def ranking_dates(path: Path) -> list[str]:
    if not path.exists():
        return []
    dates: list[str] = []
    for item in sorted(path.glob("ranking_*.csv")):
        stem = item.stem.removeprefix("ranking_")
        if len(stem) >= 10:
            dates.append(stem[:10])
    return dates


def missing_required_inputs(features_path: Path, production_dir: Path, candidate_dir: Path, regime_path: Path) -> list[str]:
    missing_inputs: list[str] = []
    if not features_path.exists():
        missing_inputs.append("features")
    if not production_dir.exists():
        missing_inputs.append("production_rankings_dir")
    if not candidate_dir.exists():
        missing_inputs.append("candidate_rankings_dir")
    if not regime_path.exists():
        missing_inputs.append("market_regime_history")
    return missing_inputs


def date_window(dates: list[str]) -> dict[str, Any]:
    return {
        "exists": bool(dates),
        "start_date": dates[0] if dates else None,
        "end_date": dates[-1] if dates else None,
        "date_count": len(dates),
    }


def feature_window(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "start_date": None, "end_date": None, "row_count": 0, "stock_count": 0}
    frame = pd.read_parquet(path, columns=["date", "stock_id"])
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna()
    return {
        "exists": True,
        "start_date": dates.min().date().isoformat() if not dates.empty else None,
        "end_date": dates.max().date().isoformat() if not dates.empty else None,
        "row_count": int(len(frame)),
        "stock_count": int(frame["stock_id"].astype(str).nunique()),
        "rows_by_year": {str(year): int(count) for year, count in frame.groupby(dates.dt.year).size().items()},
    }


def contiguous_windows(dates: list[str]) -> list[dict[str, Any]]:
    if not dates:
        return []
    values = pd.to_datetime(pd.Series(sorted(set(dates))), errors="coerce").dropna().sort_values().tolist()
    windows: list[dict[str, Any]] = []
    start = values[0]
    previous = values[0]
    count = 1
    for value in values[1:]:
        if (value - previous).days <= 4:
            previous = value
            count += 1
            continue
        windows.append({"start_date": start.date().isoformat(), "end_date": previous.date().isoformat(), "trade_days": count})
        start = value
        previous = value
        count = 1
    windows.append({"start_date": start.date().isoformat(), "end_date": previous.date().isoformat(), "trade_days": count})
    return windows


def regime_windows(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"exists": False, "families": {}, "range": None}
    frame = load_regime_frame(path)
    frame["BIG_BULL"] = frame.apply(is_big_bull, axis=1)
    frame["HIGH_CHOPPY_CONTEXT"] = frame.apply(rolling_high_choppy, axis=1)
    trade_dates = pd.to_datetime(frame["trade_date_text"], errors="coerce")
    families: dict[str, Any] = {}
    for family in ("BIG_BULL", "HIGH_CHOPPY_CONTEXT"):
        dates = frame.loc[frame[family], "trade_date_text"].astype(str).tolist()
        windows = sorted(contiguous_windows(dates), key=lambda row: row["trade_days"], reverse=True)
        families[family] = {
            "date_count": len(dates),
            "top_windows": windows[:8],
        }
    return {
        "exists": True,
        "range": {
            "start_date": trade_dates.min().date().isoformat() if not trade_dates.empty else None,
            "end_date": trade_dates.max().date().isoformat() if not trade_dates.empty else None,
            "date_count": int(len(frame)),
        },
        "families": families,
    }


def intersection_count(left: list[str], right: list[str]) -> int:
    return len(set(left) & set(right))


def decision(
    features: dict[str, Any],
    production_dates: list[str],
    candidate_dates: list[str],
    regimes: dict[str, Any],
    missing_inputs: list[str],
) -> dict[str, Any]:
    production_count = len(production_dates)
    candidate_count = len(candidate_dates)
    production_set = set(production_dates)
    candidate_set = set(candidate_dates)
    missing_candidate_dates = sorted(production_set - candidate_set)
    extra_candidate_dates = sorted(candidate_set - production_set)
    overlap = len(production_set & candidate_set)
    blockers: list[str] = []
    for item in missing_inputs:
        blockers.append(f"缺少必要輸入：{item}")
    if missing_candidate_dates:
        blockers.append("candidate ranking 日期集合未完整覆蓋 production 長區間日期")
    if features.get("start_date") and features["start_date"] > "2023-11-21":
        blockers.append("features parquet 未覆蓋 2023-11-21 歷史起點")
    regime_range = regimes.get("range") or {}
    if regime_range.get("start_date") and regime_range["start_date"] > "2023-11-21":
        blockers.append("market regime history 未覆蓋完整 production 歷史區間")
    if blockers:
        status = "BLOCKED_NEEDS_HISTORICAL_CANDIDATE_RANKINGS"
        next_action = "先補 candidate 長區間 ranking 或補歷史 features/regime，再做三年與相似盤勢驗證。"
    else:
        status = "READY_FOR_LONG_HISTORICAL_REPLAY"
        next_action = "可直接跑長區間 candidate vs production replay。"
    return {
        "status": status,
        "promotion_ready": False,
        "production_ready": False,
        "production_ranking_days": production_count,
        "candidate_ranking_days": candidate_count,
        "comparable_overlap_days": overlap,
        "missing_candidate_ranking_days": len(missing_candidate_dates),
        "missing_candidate_dates_sample": missing_candidate_dates[:20],
        "extra_candidate_ranking_days": len(extra_candidate_dates),
        "extra_candidate_dates_sample": extra_candidate_dates[:20],
        "missing_inputs": missing_inputs,
        "blockers": blockers,
        "next_action": next_action,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    features_path = resolve_path(args.features)
    production_dir = resolve_path(args.production_rankings_dir)
    candidate_dir = resolve_path(args.candidate_rankings_dir)
    regime_path = resolve_path(args.market_regime_history)
    assert features_path is not None and production_dir is not None and candidate_dir is not None and regime_path is not None
    missing_inputs = missing_required_inputs(features_path, production_dir, candidate_dir, regime_path)
    production_dates = ranking_dates(production_dir)
    candidate_dates = ranking_dates(candidate_dir)
    features = feature_window(features_path)
    regimes = regime_windows(regime_path)
    decision_payload = decision(features, production_dates, candidate_dates, regimes, missing_inputs)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "FAILED" if missing_inputs else "OK",
        "contract": {
            "research_only": True,
            "audit_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_ready": False,
        },
        "inputs": {
            "features": repo_path(features_path),
            "production_rankings_dir": repo_path(production_dir),
            "candidate_rankings_dir": repo_path(candidate_dir),
            "market_regime_history": repo_path(regime_path),
        },
        "features": features,
        "rankings": {
            "production": date_window(production_dates),
            "candidate": date_window(candidate_dates),
            "overlap_days": intersection_count(production_dates, candidate_dates),
            "missing_candidate_dates": decision_payload["missing_candidate_dates_sample"],
            "missing_candidate_ranking_days": decision_payload["missing_candidate_ranking_days"],
        },
        "similar_regime_windows": regimes,
        "decision": decision_payload,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    decision_payload = payload["decision"]
    lines = [
        "# Candidate Historical Validation Gap",
        "",
        f"- status: {payload['status']}",
        f"- decision: {decision_payload['status']}",
        f"- promotion_ready: {decision_payload['promotion_ready']}",
        f"- next_action: {decision_payload['next_action']}",
        "",
        "## Coverage",
        "",
        f"- features: {payload['features'].get('start_date')} ~ {payload['features'].get('end_date')}",
        (
            f"- production rankings: {payload['rankings']['production'].get('start_date')} ~ "
            f"{payload['rankings']['production'].get('end_date')} "
            f"({payload['rankings']['production'].get('date_count')} days)"
        ),
        (
            f"- candidate rankings: {payload['rankings']['candidate'].get('start_date')} ~ "
            f"{payload['rankings']['candidate'].get('end_date')} "
            f"({payload['rankings']['candidate'].get('date_count')} days)"
        ),
        f"- overlap days: {payload['rankings']['overlap_days']}",
        f"- missing candidate ranking days: {payload['rankings'].get('missing_candidate_ranking_days')}",
        f"- missing inputs: {', '.join(decision_payload.get('missing_inputs') or []) or 'none'}",
        "",
        "## Regime Windows",
        "",
    ]
    families = payload["similar_regime_windows"].get("families", {})
    for family, item in families.items():
        lines.append(f"- {family}: {item.get('date_count')} days")
        for window in item.get("top_windows", [])[:3]:
            lines.append(f"  - {window['start_date']} ~ {window['end_date']} ({window['trade_days']} days)")
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"candidate_historical_validation_gap_report_{args.date}.json"
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(payload, output)
    print(json.dumps({"status": payload["status"], "decision": payload["decision"]["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
