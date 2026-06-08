#!/usr/bin/env python3
"""產出 AUTO-TRAINING-14B BIG_BULL shadow monitor 報告。"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_backtest_replay  # noqa: E402


SCHEMA_VERSION = "big-bull-shadow-monitor.v1"
HORIZONS = [1, 3, 5, 10]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build BIG_BULL shadow monitor report")
    parser.add_argument("--date", required=True)
    parser.add_argument("--dry-run-report", default="artifacts/model_experiments/big_bull_ranking_only_shadow_dry_run_2026-06-01.json")
    parser.add_argument("--production-dir", default="artifacts/backtest/historical_rankings_current_model")
    parser.add_argument("--shadow-dir", default="artifacts/backtest/shadow_rankings_big_bull")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--model", default="models/latest_lgbm.pkl")
    parser.add_argument("--model-hash-before", required=True)
    parser.add_argument("--training-readiness", default="artifacts/training_automation_readiness_2026-06-01.json")
    parser.add_argument("--top-n", type=int, default=10)
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
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_digest(path: Path, pattern: str = "ranking_*.csv") -> str:
    digest = hashlib.sha256()
    for item in sorted(path.glob(pattern)):
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(item.read_bytes())
    return digest.hexdigest()


def glob_digest(root: Path, pattern: str) -> str:
    digest = hashlib.sha256()
    for item in sorted(root.glob(pattern)):
        if item.is_file():
            digest.update(str(item.relative_to(root)).encode("utf-8"))
            digest.update(item.read_bytes())
    return digest.hexdigest()


def replay_args(rankings_dir: Path, features: Path, top_n: int) -> argparse.Namespace:
    return argparse.Namespace(
        rankings_dir=str(rankings_dir),
        features=str(features),
        horizons=",".join(str(item) for item in HORIZONS),
        top_n=top_n,
        entry_delay_trade_days=1,
        max_ranking_files=None,
        fee_rate=0.001425,
        tax_rate=0.003,
        slippage_rate=0.001,
        max_position_weight=0.2,
        default_gross_exposure=0.65,
        output=None,
    )


def run_outcome(rankings_dir: Path, features: Path, top_n: int) -> dict[str, Any]:
    return run_backtest_replay.run_replay(replay_args(rankings_dir, features, top_n))


def outcome_dates(replay: dict[str, Any], monitor_dates: list[str]) -> dict[str, Any]:
    observations = replay.get("portfolio", {}).get("observations", [])
    by_horizon: dict[str, set[str]] = {str(item): set() for item in HORIZONS}
    for row in observations:
        by_horizon.setdefault(str(int(row["horizon"])), set()).add(str(row["ranking_date"]))
    result = {}
    for horizon in HORIZONS:
        key = str(horizon)
        matured = sorted(by_horizon.get(key, set()) & set(monitor_dates))
        pending = [date for date in monitor_dates if date not in matured]
        result[key] = {"matured": matured, "pending": pending}
    return result


def replay_summary(replay: dict[str, Any]) -> dict[str, Any]:
    portfolio = replay.get("summary", {}).get("portfolio_by_horizon", {})
    trades = replay.get("summary", {}).get("by_horizon", {})
    return {
        str(horizon): {
            "portfolio": portfolio.get(str(horizon), {}),
            "trades": trades.get(str(horizon), {}),
        }
        for horizon in HORIZONS
    }


def outcome_delta(shadow: dict[str, Any], production: dict[str, Any]) -> dict[str, Any]:
    result = {}
    for horizon in HORIZONS:
        key = str(horizon)
        shadow_port = shadow.get("summary", {}).get("portfolio_by_horizon", {}).get(key, {})
        prod_port = production.get("summary", {}).get("portfolio_by_horizon", {}).get(key, {})
        result[key] = {
            "shadow_avg_portfolio_return": shadow_port.get("avg_portfolio_return"),
            "production_avg_portfolio_return": prod_port.get("avg_portfolio_return"),
            "avg_return_delta": rounded_delta(shadow_port.get("avg_portfolio_return"), prod_port.get("avg_portfolio_return")),
            "shadow_total_compounded_return": shadow_port.get("total_compounded_return"),
            "production_total_compounded_return": prod_port.get("total_compounded_return"),
            "total_compounded_delta": rounded_delta(shadow_port.get("total_compounded_return"), prod_port.get("total_compounded_return")),
            "shadow_hit_rate": shadow_port.get("hit_rate"),
            "production_hit_rate": prod_port.get("hit_rate"),
        }
    return result


def rounded_delta(left: Any, right: Any) -> float | None:
    if left is None or right is None:
        return None
    return round(float(left) - float(right), 6)


def high_choppy_outcome(
    dry_run: dict[str, Any],
    shadow_replay: dict[str, Any],
    production_replay: dict[str, Any],
) -> dict[str, Any]:
    groups = dry_run.get("high_choppy_stratified", {})
    shadow_obs = pd.DataFrame(shadow_replay.get("portfolio", {}).get("observations", []))
    prod_obs = pd.DataFrame(production_replay.get("portfolio", {}).get("observations", []))
    result = {}
    for group_name, group_info in groups.items():
        dates = set(group_info.get("dates", []))
        result[group_name] = {
            "date_count": len(dates),
            "dry_run": group_info,
            "outcome_by_horizon": {
                str(horizon): summarize_observation_slice(shadow_obs, prod_obs, dates, horizon)
                for horizon in HORIZONS
            },
        }
    return result


def summarize_observation_slice(
    shadow_obs: pd.DataFrame,
    prod_obs: pd.DataFrame,
    dates: set[str],
    horizon: int,
) -> dict[str, Any]:
    if shadow_obs.empty:
        return {"matured_count": 0}
    shadow = shadow_obs[(shadow_obs["horizon"] == horizon) & (shadow_obs["ranking_date"].isin(dates))]
    prod = prod_obs[(prod_obs["horizon"] == horizon) & (prod_obs["ranking_date"].isin(dates))] if not prod_obs.empty else pd.DataFrame()
    if shadow.empty:
        return {"matured_count": 0}
    shadow_returns = pd.to_numeric(shadow["portfolio_return"], errors="coerce")
    prod_returns = pd.to_numeric(prod["portfolio_return"], errors="coerce") if not prod.empty else pd.Series(dtype=float)
    return {
        "matured_count": int(len(shadow)),
        "shadow_avg_portfolio_return": round(float(shadow_returns.mean()), 6),
        "production_avg_portfolio_return": round(float(prod_returns.mean()), 6) if len(prod_returns) else None,
        "avg_return_delta": rounded_delta(float(shadow_returns.mean()), float(prod_returns.mean())) if len(prod_returns) else None,
        "shadow_hit_rate": round(float((shadow_returns > 0).mean()), 6),
        "production_hit_rate": round(float((prod_returns > 0).mean()), 6) if len(prod_returns) else None,
    }


def readiness_promotion_ready(path: Path) -> bool:
    payload = read_json(path)
    body = payload.get("readiness") if isinstance(payload.get("readiness"), dict) else payload
    return bool(body.get("promotion_ready")) if body.get("promotion_ready") is not None else False


def decide_status(dry_run: dict[str, Any], outcome: dict[str, Any]) -> tuple[str, str, list[str]]:
    summary = dry_run.get("overlap_summary", {})
    sector = dry_run.get("sector_concentration", {})
    avg_overlap = float(summary.get("avg_overlap_count") or 0)
    avg_turnover = float(summary.get("avg_shadow_turnover_vs_previous") or 0)
    max_sector = float(sector.get("max_shadow_sector_share") or 0)
    reasons = []
    if avg_overlap < 3:
        reasons.append("avg overlap count below 3/10")
    if avg_turnover > 3:
        reasons.append("avg shadow turnover above 3 names/day")
    if max_sector >= 0.9:
        reasons.append("shadow sector concentration reaches >=90%")
    horizon10 = outcome.get("10", {})
    if horizon10.get("avg_return_delta") is not None and horizon10["avg_return_delta"] < 0:
        reasons.append("10D shadow average return under production")
    if reasons:
        return "RESTRICTED_SHADOW_ONLY", "RESTRICTED_SHADOW_ONLY", reasons
    return "READY_FOR_OVERLAY_PROPOSAL", "READY_FOR_OVERLAY_PROPOSAL", []


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    dry_run_path = resolve_path(args.dry_run_report)
    production_dir = resolve_path(args.production_dir)
    shadow_dir = resolve_path(args.shadow_dir)
    features = resolve_path(args.features)
    model = resolve_path(args.model)
    readiness = resolve_path(args.training_readiness)
    required = {
        "dry_run_report": dry_run_path.exists(),
        "production_dir": production_dir.exists(),
        "shadow_dir": shadow_dir.exists(),
        "features": features.exists(),
        "model": model.exists(),
        "training_readiness": readiness.exists(),
    }
    if not all(required.values()):
        missing = [name for name, ok in required.items() if not ok]
        return base_payload(args, "FAILED", required, [f"missing required input: {name}" for name in missing])

    production_digest_before = directory_digest(production_dir)
    clawd_digest_before = glob_digest(PROJECT_ROOT / "artifacts", "clawd_publish_message*.md")
    model_hash_before_seen = sha256(model)
    dry_run = read_json(dry_run_path)
    monitor_dates = list(dry_run.get("shadow_dates", {}).get("dates", []))
    shadow_replay = run_outcome(shadow_dir, features, args.top_n)
    production_replay = run_outcome(production_dir, features, args.top_n)
    production_digest_after = directory_digest(production_dir)
    clawd_digest_after = glob_digest(PROJECT_ROOT / "artifacts", "clawd_publish_message*.md")
    model_hash_after = sha256(model)

    outcome = outcome_delta(shadow_replay, production_replay)
    status, next_gate, restrictions = decide_status(dry_run, outcome)
    guard = {
        "production_ranking_changed": production_digest_before != production_digest_after,
        "risk_adjusted_score_changed": production_digest_before != production_digest_after,
        "models_latest_changed": args.model_hash_before != model_hash_after or model_hash_before_seen != model_hash_after,
        "clawd_message_created": clawd_digest_before != clawd_digest_after,
        "promotion_ready": readiness_promotion_ready(readiness),
    }
    errors = []
    if any(guard.values()):
        errors.append("shadow monitor guard failed")
    if dry_run.get("next_gate") != "READY_FOR_SHADOW_MONITOR":
        errors.append("Checkpoint A did not allow Checkpoint B")
    if not monitor_dates:
        errors.append("no monitor dates")
    return {
        **base_payload(args, "FAILED" if errors else "OK", required, errors),
        "checkpoint": "B_SHADOW_MONITOR",
        "shadow_monitor_status": "FAILED" if errors else status,
        "monitor_dates": {
            "date_count": len(monitor_dates),
            "start_date": monitor_dates[0] if monitor_dates else None,
            "end_date": monitor_dates[-1] if monitor_dates else None,
            "dates": monitor_dates,
        },
        "matured_outcome_dates": {
            "shadow": outcome_dates(shadow_replay, monitor_dates),
            "production": outcome_dates(production_replay, monitor_dates),
        },
        "pending_outcome_dates": {
            "shadow": {key: value["pending"] for key, value in outcome_dates(shadow_replay, monitor_dates).items()},
            "production": {key: value["pending"] for key, value in outcome_dates(production_replay, monitor_dates).items()},
        },
        "paper_outcome": {
            "shadow_summary": replay_summary(shadow_replay),
            "production_summary": replay_summary(production_replay),
            "shadow_vs_production": outcome,
        },
        "avg_overlap_count": dry_run.get("overlap_summary", {}).get("avg_overlap_count"),
        "avg_turnover": dry_run.get("overlap_summary", {}).get("avg_shadow_turnover_vs_previous"),
        "production_comparison": dry_run.get("production_comparison"),
        "overlap_summary": dry_run.get("overlap_summary"),
        "turnover": dry_run.get("turnover"),
        "sector_concentration": dry_run.get("sector_concentration"),
        "high_choppy_stratified": high_choppy_outcome(dry_run, shadow_replay, production_replay),
        **guard,
        "next_gate": "FAILED" if errors else next_gate,
        "restrictions": restrictions,
        "checkpoint_c_entry_allowed": (not errors and next_gate == "READY_FOR_OVERLAY_PROPOSAL"),
        "hashes": {
            "production_ranking_before": production_digest_before,
            "production_ranking_after": production_digest_after,
            "clawd_messages_before": clawd_digest_before,
            "clawd_messages_after": clawd_digest_after,
            "model_hash_before_arg": args.model_hash_before,
            "model_hash_before_seen": model_hash_before_seen,
            "model_hash_after": model_hash_after,
        },
    }


def base_payload(args: argparse.Namespace, status: str, required: dict[str, bool], errors: list[str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "contract": {
            "shadow_monitor_only": True,
            "does_not_write_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_create_formal_clawd_message": True,
            "does_not_output_promotion_ready": True,
            "does_not_create_overlay_proposal": True,
        },
        "required_inputs": required,
        "errors": errors,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# AUTO-TRAINING-14B BIG_BULL Shadow Monitor",
            "",
            f"- status: {payload.get('status')}",
            f"- checkpoint: {payload.get('checkpoint')}",
            f"- shadow_monitor_status: {payload.get('shadow_monitor_status')}",
            f"- monitor_dates: {payload.get('monitor_dates', {}).get('date_count')}",
            f"- avg_overlap_count: {payload.get('avg_overlap_count')}",
            f"- avg_turnover: {payload.get('avg_turnover')}",
            f"- next_gate: {payload.get('next_gate')}",
            f"- checkpoint_c_entry_allowed: {payload.get('checkpoint_c_entry_allowed')}",
            f"- production_ranking_changed: {payload.get('production_ranking_changed')}",
            f"- risk_adjusted_score_changed: {payload.get('risk_adjusted_score_changed')}",
            f"- models_latest_changed: {payload.get('models_latest_changed')}",
            f"- clawd_message_created: {payload.get('clawd_message_created')}",
            f"- promotion_ready: {payload.get('promotion_ready')}",
            "",
            "## Restrictions",
            "",
            *[f"- {item}" for item in payload.get("restrictions", [])],
            "",
            "## Errors",
            "",
            *[f"- {item}" for item in payload.get("errors", [])],
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"big_bull_shadow_monitor_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload.get("status"), "output": repo_path(output), "next_gate": payload.get("next_gate")}, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
