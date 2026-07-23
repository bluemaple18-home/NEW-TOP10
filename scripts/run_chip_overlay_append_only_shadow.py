#!/usr/bin/env python3
"""固定 10% chip overlay 的 append-only 前瞻 shadow ledger。"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_backtest_replay  # noqa: E402
from scripts.research_alpha_candidate_overlay_portfolio_replay import (  # noqa: E402
    load_group_map,
    simulate_bucket,
    turnover,
)
from scripts.research_feature_group_ablation_by_regime import add_forward_returns, load_frame  # noqa: E402
from scripts.research_feature_group_regime_walkforward import (  # noqa: E402
    apply_research_universe,
    build_group_score,
    clean_feature_groups,
    mask_unavailable_source_features,
)


SCHEMA_VERSION = "chip-overlay-append-only-shadow-ledger.v1"
DEFAULT_CONFIG = PROJECT_ROOT / "config" / "chip_liquidity_overlay_shadow_v1.json"
DEFAULT_LEDGER = PROJECT_ROOT / "artifacts" / "model_experiments" / "chip_overlay_shadow_ledger_v1.json"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run append-only chip overlay shadow")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    parser.add_argument("--ledger", default=str(DEFAULT_LEDGER))
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument(
        "--market-regime-history",
        default="artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json",
    )
    parser.add_argument("--industry-map", default="data/reference/stock_industry_map.csv")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def canonical_digest(payload: Any) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def regime_anchor(payload: dict[str, Any], through: str) -> tuple[int, str]:
    rows = payload.get("rows")
    if not isinstance(rows, list):
        raise ValueError("regime history 缺少 rows")
    anchored = sorted(
        [row for row in rows if str(row.get("trade_date") or "") <= through],
        key=lambda row: str(row.get("trade_date") or ""),
    )
    dates = [str(row.get("trade_date") or "") for row in anchored]
    if not anchored or any(not date_text for date_text in dates) or len(dates) != len(set(dates)):
        raise ValueError("regime history anchor 為空、缺日期或含重複日期")
    return len(anchored), canonical_digest(anchored)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root 必須是 object：{path}")
    return payload


def validate_config(config: dict[str, Any]) -> None:
    if config.get("schema_version") != "chip-liquidity-overlay-shadow-candidate.v1":
        raise ValueError("candidate config schema_version 不符")
    if float((config.get("portfolio") or {}).get("chip_overlay_weight") or 0) != 0.10:
        raise ValueError("candidate 必須固定為 10% chip overlay")
    if (config.get("universe") or {}).get("mode") != "point-in-time-liquidity":
        raise ValueError("candidate universe 必須為 point-in-time-liquidity")
    if int((config.get("acceptance") or {}).get("required_independent_dates") or 0) != 60:
        raise ValueError("candidate acceptance 必須固定為前 60 個獨立日期")
    if (config.get("acceptance") or {}).get("promotion_allowed") is not False:
        raise ValueError("shadow candidate 不得允許直接 promotion")
    if not config.get("seal_date") or not isinstance(config.get("selected"), dict):
        raise ValueError("candidate 缺少 seal_date 或 selected")
    regime = config.get("regime_history") or {}
    if regime.get("anchor_through") != config["seal_date"] or not regime.get("anchor_sha256"):
        raise ValueError("candidate 缺少與 seal date 一致的 regime history anchor")


def empty_ledger(config: dict[str, Any], config_path: Path) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "candidate": {
            "candidate_id": config["candidate_id"],
            "config": repo_path(config_path),
            "config_sha256": canonical_digest(config),
            "seal_date": config["seal_date"],
        },
        "contract": {
            "append_only": True,
            "single_writer_role": config["ledger_writer_role"],
            "existing_dates_recomputed": False,
            "dates_must_be_after_seal": True,
            "acceptance_uses_first_60_complete_dates": True,
            "production_promotion_allowed": False,
        },
        "observations": [],
        "warnings_and_exclusions": [],
    }


def validate_ledger(ledger: dict[str, Any], config: dict[str, Any]) -> None:
    if ledger.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("ledger schema_version 不符")
    candidate = ledger.get("candidate") or {}
    if candidate.get("candidate_id") != config["candidate_id"]:
        raise ValueError("ledger candidate_id 與 frozen config 不符")
    if candidate.get("config_sha256") != canonical_digest(config):
        raise ValueError("frozen config 已改變；禁止沿用既有 ledger")
    dates = [str(row.get("ranking_date")) for row in ledger.get("observations", [])]
    if len(dates) != len(set(dates)):
        raise ValueError("ledger 含重複 ranking_date")
    if any(date_text <= config["seal_date"] for date_text in dates):
        raise ValueError("ledger 含 seal date 以前的 observation")


def merge_append_only(
    ledger: dict[str, Any],
    observations: list[dict[str, Any]],
    warnings: list[dict[str, Any]],
) -> tuple[int, int]:
    existing_dates = {str(row["ranking_date"]) for row in ledger["observations"]}
    new_dates = [str(row["ranking_date"]) for row in observations]
    if len(new_dates) != len(set(new_dates)):
        raise ValueError("本次 observations 含重複 ranking_date")
    append_rows = [row for row in observations if str(row["ranking_date"]) not in existing_dates]
    ledger["observations"].extend(append_rows)
    ledger["observations"].sort(key=lambda row: str(row["ranking_date"]))
    existing_warnings = {
        (str(row.get("record")), str(row.get("reason_code")), str(row.get("stage")))
        for row in ledger["warnings_and_exclusions"]
    }
    append_warnings = [
        row
        for row in warnings
        if (str(row.get("record")), str(row.get("reason_code")), str(row.get("stage"))) not in existing_warnings
    ]
    ledger["warnings_and_exclusions"].extend(append_warnings)
    ledger["warnings_and_exclusions"].sort(
        key=lambda row: (str(row.get("record")), str(row.get("reason_code")))
    )
    return len(append_rows), len(append_warnings)


def atomic_write(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(body)
        temporary = handle.name
    os.replace(temporary, path)


def top_ids(frame: pd.DataFrame, score: str, top_n: int) -> list[str]:
    ranked = frame.sort_values([score, "stock_id"], ascending=[False, True]).head(top_n)
    return ranked["stock_id"].astype(str).str.zfill(4).tolist()


def frozen_daily_selection(
    daily: pd.DataFrame,
    config: dict[str, Any],
) -> tuple[dict[str, list[str]] | None, dict[str, Any] | None]:
    regime = str(daily["regime_label"].iloc[0])
    selected = (config.get("selected") or {}).get(regime)
    if not selected:
        return None, {
            "record": str(daily["trade_date"].iloc[0].date()),
            "reason_code": "NO_FROZEN_SELECTION_FOR_REGIME",
            "stage": "shadow_scoring",
            "impact_count": int(len(daily)),
            "regime_label": regime,
        }
    liquidity = build_group_score(daily, selected["liquidity_activity"])
    chip = build_group_score(daily, selected["chip_flow"])
    scored = pd.DataFrame(
        {
            "stock_id": daily["stock_id"].astype(str).str.zfill(4),
            "liquidity": liquidity,
            "chip": chip,
        }
    ).dropna()
    coverage = float(len(scored) / len(daily)) if len(daily) else 0.0
    minimum = float(config["training_contract"]["min_daily_coverage"])
    if coverage < minimum:
        return None, {
            "record": str(daily["trade_date"].iloc[0].date()),
            "reason_code": "PAIRED_SCORE_COVERAGE_BELOW_MINIMUM",
            "stage": "shadow_scoring",
            "impact_count": int(len(daily) - len(scored)),
            "coverage": round(coverage, 6),
            "minimum": minimum,
        }
    scored["liquidity_rank"] = scored["liquidity"].rank(pct=True)
    scored["chip_rank"] = scored["chip"].rank(pct=True)
    weight = float(config["portfolio"]["chip_overlay_weight"])
    scored["overlay_rank"] = (1 - weight) * scored["liquidity_rank"] + weight * scored["chip_rank"]
    top_n = int(config["portfolio"]["top_n"])
    return {
        "baseline": top_ids(scored, "liquidity_rank", top_n),
        "overlay": top_ids(scored, "overlay_rank", top_n),
    }, None


def summarize(ledger: dict[str, Any], config: dict[str, Any]) -> dict[str, Any]:
    required = int(config["acceptance"]["required_independent_dates"])
    observations = sorted(ledger["observations"], key=lambda row: str(row["ranking_date"]))
    acceptance_rows = observations[:required]
    if not acceptance_rows:
        return {
            "status": "WAITING_FOR_NEW_OOS_DATES",
            "observation_count": 0,
            "required_observation_count": required,
            "promotion_ready": False,
        }
    deltas = pd.Series([float(row["return_delta"]) for row in acceptance_rows], dtype=float)
    baseline_turnover = turnover(
        [{"ids": row["baseline"]["stock_ids"]} for row in acceptance_rows],
        "ids",
    )
    overlay_turnover = turnover(
        [{"ids": row["overlay"]["stock_ids"]} for row in acceptance_rows],
        "ids",
    )
    turnover_delta = (
        float(overlay_turnover) - float(baseline_turnover)
        if baseline_turnover is not None and overlay_turnover is not None
        else None
    )
    exposure_deltas = pd.Series(
        [
            float(row["overlay"]["max_group_exposure"]) - float(row["baseline"]["max_group_exposure"])
            for row in acceptance_rows
        ],
        dtype=float,
    )
    monthly = (
        pd.DataFrame(
            {
                "month": [str(row["ranking_date"])[:7] for row in acceptance_rows],
                "delta": deltas,
            }
        )
        .groupby("month", sort=True)["delta"]
        .mean()
    )
    positive_month_rate = float((monthly > 0).mean()) if len(monthly) else 0.0
    metrics = {
        "avg_net_return_delta": round(float(deltas.mean()), 6),
        "positive_day_rate": round(float((deltas > 0).mean()), 6),
        "monthly_bucket_count": int(len(monthly)),
        "positive_monthly_bucket_rate": round(positive_month_rate, 6),
        "baseline_turnover": baseline_turnover,
        "overlay_turnover": overlay_turnover,
        "turnover_delta": round(turnover_delta, 6) if turnover_delta is not None else None,
        "avg_group_exposure_delta": round(float(exposure_deltas.mean()), 6),
    }
    if len(acceptance_rows) < required:
        status = "ACCUMULATING"
        failures: list[str] = []
    else:
        policy = config["acceptance"]
        failures = []
        if metrics["avg_net_return_delta"] <= float(policy["min_avg_net_return_delta"]):
            failures.append("avg_net_return_delta<=0")
        if metrics["monthly_bucket_count"] < int(policy["required_monthly_buckets"]):
            failures.append("monthly_bucket_count_below_minimum")
        if metrics["positive_monthly_bucket_rate"] < float(policy["min_positive_monthly_bucket_rate"]):
            failures.append("positive_monthly_bucket_rate_below_minimum")
        if metrics["turnover_delta"] is None or metrics["turnover_delta"] > float(policy["max_turnover_delta"]):
            failures.append("turnover_delta_above_maximum")
        if metrics["avg_group_exposure_delta"] > float(policy["max_avg_group_exposure_delta"]):
            failures.append("avg_group_exposure_delta_above_maximum")
        status = "READY_FOR_INDEPENDENT_REVIEW" if not failures else "NO_GO_EVIDENCE"
    return {
        "status": status,
        "observation_count": len(observations),
        "acceptance_observation_count": len(acceptance_rows),
        "required_observation_count": required,
        "acceptance_start": acceptance_rows[0]["ranking_date"],
        "acceptance_end": acceptance_rows[-1]["ranking_date"],
        "metrics": metrics,
        "failures": failures,
        "promotion_ready": False,
    }


def build_new_observations(
    config: dict[str, Any],
    existing_dates: set[str],
    args: argparse.Namespace,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    data_dir = resolve_path(args.data_dir)
    regime_path = resolve_path(args.market_regime_history)
    industry_path = resolve_path(args.industry_map)
    regime_payload = read_json(regime_path)
    if (regime_payload.get("contract") or {}).get("append_only") is not True:
        raise ValueError("shadow 必須使用 append-only regime history")
    anchor_rows, anchor_sha256 = regime_anchor(regime_payload, config["regime_history"]["anchor_through"])
    if anchor_rows != int(config["regime_history"]["anchor_rows"]):
        raise ValueError("regime history seal anchor row count drift")
    if anchor_sha256 != config["regime_history"]["anchor_sha256"]:
        raise ValueError("regime history seal anchor digest drift")
    frame, source_groups, _ = load_frame(data_dir, regime_path, industry_path)
    groups, _ = clean_feature_groups(source_groups)
    frame, source_receipt = mask_unavailable_source_features(frame, groups)
    frame = add_forward_returns(frame, [int(config["portfolio"]["holding_trade_days"])])
    target = f"future_return_{int(config['portfolio']['holding_trade_days'])}d"
    frame = frame[frame["regime_label"].ne("UNKNOWN")].copy()
    frame, universe_receipt = apply_research_universe(
        frame,
        mode=config["universe"]["mode"],
        liquidity_top_n=int(config["universe"]["liquidity_top_n"]),
    )
    mature_dates = sorted(
        str(date.date())
        for date in frame.loc[frame[target].notna(), "trade_date"].drop_duplicates()
        if str(date.date()) > config["seal_date"]
    )
    new_dates = [date_text for date_text in mature_dates if date_text not in existing_dates]
    price_frame = run_backtest_replay.load_price_frame(resolve_path("data/clean/features.parquet"))
    trade_dates = run_backtest_replay.market_trade_dates(price_frame)
    price_index = run_backtest_replay.build_price_index(price_frame)
    group_map = load_group_map(industry_path)
    portfolio = config["portfolio"]
    replay_args = argparse.Namespace(
        entry_delay_trade_days=int(portfolio["entry_delay_trade_days"]),
        horizon=int(portfolio["holding_trade_days"]),
        fee_rate=float(portfolio["fee_rate"]),
        tax_rate=float(portfolio["tax_rate"]),
        slippage_rate=float(portfolio["slippage_rate"]),
    )
    observations = []
    warnings = []
    for date_text in new_dates:
        daily = frame[frame["trade_date"].eq(pd.Timestamp(date_text))]
        ids, warning = frozen_daily_selection(daily, config)
        if warning is not None:
            warnings.append(warning)
            continue
        baseline = simulate_bucket(price_index, trade_dates, date_text, ids["baseline"], group_map, replay_args)
        overlay = simulate_bucket(price_index, trade_dates, date_text, ids["overlay"], group_map, replay_args)
        top_n = int(portfolio["top_n"])
        if baseline["valid_trade_count"] < top_n or overlay["valid_trade_count"] < top_n:
            warnings.append(
                {
                    "record": date_text,
                    "reason_code": "INCOMPLETE_FORWARD_OHLC_BUCKET",
                    "stage": "shadow_replay",
                    "impact_count": int(
                        (top_n - baseline["valid_trade_count"]) + (top_n - overlay["valid_trade_count"])
                    ),
                    "baseline_valid_trade_count": baseline["valid_trade_count"],
                    "overlay_valid_trade_count": overlay["valid_trade_count"],
                }
            )
            continue
        observations.append(
            {
                "ranking_date": date_text,
                "regime_label": str(daily["regime_label"].iloc[0]),
                "baseline": baseline,
                "overlay": overlay,
                "return_delta": round(
                    float(overlay["avg_net_return"]) - float(baseline["avg_net_return"]),
                    6,
                ),
            }
        )
    receipt = {
        "source_and_grain": "data/clean stock_id × trade_date",
        "latest_source_date": str(frame["trade_date"].max().date()),
        "latest_mature_date": mature_dates[-1] if mature_dates else config["seal_date"],
        "mature_dates_after_seal": len(mature_dates),
        "new_dates_attempted": len(new_dates),
        "regime_anchor_rows": anchor_rows,
        "regime_anchor_sha256": anchor_sha256,
        "source_mask_receipt": source_receipt,
        "universe_receipt": universe_receipt,
    }
    return observations, warnings, receipt


def render_markdown(ledger: dict[str, Any]) -> str:
    summary = ledger["summary"]
    lines = [
        "# Chip Overlay Append-only Shadow",
        "",
        f"- status：`{summary['status']}`",
        f"- observations：`{summary['observation_count']}/{summary['required_observation_count']}`",
        f"- candidate：`{ledger['candidate']['candidate_id']}`",
        "- production promotion allowed：`false`",
    ]
    if summary.get("metrics"):
        lines.extend(
            [
                f"- avg net return delta：`{summary['metrics']['avg_net_return_delta']}`",
                f"- turnover delta：`{summary['metrics']['turnover_delta']}`",
                f"- avg group exposure delta：`{summary['metrics']['avg_group_exposure_delta']}`",
            ]
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    config_path = resolve_path(args.config)
    ledger_path = resolve_path(args.ledger)
    config = read_json(config_path)
    validate_config(config)
    ledger = read_json(ledger_path) if ledger_path.exists() else empty_ledger(config, config_path)
    validate_ledger(ledger, config)
    existing_dates = {str(row["ranking_date"]) for row in ledger["observations"]}
    observations, warnings, receipt = build_new_observations(config, existing_dates, args)
    appended, warning_count = merge_append_only(ledger, observations, warnings)
    ledger["updated_at"] = datetime.now(timezone.utc).isoformat()
    ledger["last_run_receipt"] = {
        **receipt,
        "observations_appended": appended,
        "warnings_appended": warning_count,
    }
    ledger["summary"] = summarize(ledger, config)
    atomic_write(ledger_path, ledger)
    ledger_path.with_suffix(".md").write_text(render_markdown(ledger), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": ledger["summary"]["status"],
                "ledger": repo_path(ledger_path),
                "observation_count": ledger["summary"]["observation_count"],
                "observations_appended": appended,
                "warnings_appended": warning_count,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
