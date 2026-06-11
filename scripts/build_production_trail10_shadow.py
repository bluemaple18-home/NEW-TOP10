#!/usr/bin/env python3
"""產出 production ranking + trail10 的每日 shadow artifact。"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "production-trail10-shadow.v1"
STATUS_ORDER = ["candidate_active", "min_hold_not_met", "hold", "trail_stop_zone", "exit_triggered", "expired_or_removed"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build production trail10 shadow artifact")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--rankings-dir", default="artifacts")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--lookback-ranking-days", type=int, default=45)
    parser.add_argument("--max-holding-days", type=int, default=40)
    parser.add_argument("--min-holding-days", type=int, default=5)
    parser.add_argument("--trail-pct", type=float, default=0.10)
    parser.add_argument("--trail-zone-buffer", type=float, default=0.02)
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


def ranking_date(path: Path) -> str:
    match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking filename not parseable: {path}")
    return match.group(1)


def ranking_files(path: Path, run_date: str) -> list[Path]:
    files = [
        item
        for item in path.glob("ranking_*.csv")
        if re.match(r"ranking_\d{4}-\d{2}-\d{2}\.csv$", item.name) and ranking_date(item) <= run_date
    ]
    if not files:
        raise FileNotFoundError(f"找不到 ranking_*.csv：{path}")
    return sorted(files, key=ranking_date)


def read_ranking(path: Path, top_n: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = []
        for rank, row in enumerate(csv.DictReader(handle), start=1):
            if rank > top_n:
                break
            rows.append(
                {
                    "rank": rank,
                    "stock_id": str(row.get("stock_id", "")).strip().replace(".0", "").zfill(4),
                    "stock_name": row.get("stock_name"),
                    "close": to_float(row.get("close")),
                    "model_prob": to_float(row.get("model_prob")),
                    "risk_adjusted_score": to_float(row.get("risk_adjusted_score")),
                    "market_regime": row.get("market_regime"),
                }
            )
        return rows


def to_float(value: Any) -> float | None:
    try:
        if value is None or value == "":
            return None
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(parsed) else parsed


def load_prices(path: Path, run_date: str) -> tuple[list[str], dict[tuple[str, str], dict[str, float]], str]:
    if not path.exists():
        raise FileNotFoundError(f"features parquet 不存在：{path}")
    frame = pd.read_parquet(path, columns=["date", "stock_id", "open", "high", "low", "close"])
    frame = frame.copy()
    frame["date_text"] = pd.to_datetime(frame["date"]).dt.date.astype(str)
    frame = frame[frame["date_text"] <= run_date]
    if frame.empty:
        raise RuntimeError(f"features 沒有 <= {run_date} 的資料")
    frame["stock_id"] = frame["stock_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    trade_dates = sorted(frame["date_text"].unique())
    prices = {
        (str(row.stock_id), str(row.date_text)): {
            "open": float(row.open),
            "high": float(row.high),
            "low": float(row.low),
            "close": float(row.close),
        }
        for row in frame[["stock_id", "date_text", "open", "high", "low", "close"]].itertuples(index=False)
        if not pd.isna(row.open) and not pd.isna(row.high) and not pd.isna(row.low) and not pd.isna(row.close)
    }
    return trade_dates, prices, trade_dates[-1]


def next_trade_date(trade_dates: list[str], ranking_day: str) -> str | None:
    for trade_date in trade_dates:
        if trade_date > ranking_day:
            return trade_date
    return None


def trade_date_index(trade_dates: list[str]) -> dict[str, int]:
    return {value: index for index, value in enumerate(trade_dates)}


def simulate_position(
    *,
    row: dict[str, Any],
    ranking_day: str,
    trade_dates: list[str],
    date_index: dict[str, int],
    prices: dict[tuple[str, str], dict[str, float]],
    as_of_date: str,
    min_holding_days: int,
    max_holding_days: int,
    trail_pct: float,
    trail_zone_buffer: float,
) -> dict[str, Any]:
    stock_id = row["stock_id"]
    entry_date = next_trade_date(trade_dates, ranking_day)
    if entry_date is None or entry_date > as_of_date:
        return {
            "ranking_date": ranking_day,
            "entry_date": entry_date,
            "stock_id": stock_id,
            "stock_name": row.get("stock_name"),
            "source_rank": row.get("rank"),
            "status": "candidate_active",
            "status_reason": "latest production Top10 candidate; D+1 entry proxy not available yet",
            "personalized_sell_instruction": False,
        }
    entry_bar = prices.get((stock_id, entry_date))
    if not entry_bar:
        return {
            "ranking_date": ranking_day,
            "entry_date": entry_date,
            "stock_id": stock_id,
            "stock_name": row.get("stock_name"),
            "source_rank": row.get("rank"),
            "status": "expired_or_removed",
            "status_reason": "missing entry open price",
            "personalized_sell_instruction": False,
        }
    start_index = date_index[entry_date]
    end_index = date_index[as_of_date]
    high_water = float(entry_bar["open"])
    exit_date = None
    exit_price = None
    exit_reason = None
    threshold = high_water * (1 - trail_pct)
    days_held = 0
    for index in range(start_index, min(end_index, start_index + max_holding_days - 1) + 1):
        current_date = trade_dates[index]
        bar = prices.get((stock_id, current_date))
        if not bar:
            continue
        days_held = index - start_index + 1
        threshold = high_water * (1 - trail_pct)
        # 先用前一日以前已知 high_water 判斷，避免同日新高又同日停損的後照鏡。
        if days_held >= min_holding_days and float(bar["low"]) <= threshold:
            exit_date = current_date
            exit_price = threshold
            exit_reason = "trail10_exit_triggered"
            break
        high_water = max(high_water, float(bar["high"]))
    latest_bar = prices.get((stock_id, as_of_date)) or {}
    if exit_date is not None:
        status = "exit_triggered" if exit_date == as_of_date else "expired_or_removed"
        status_reason = "trail10 exit triggered today" if status == "exit_triggered" else f"trail10 exit already triggered on {exit_date}"
    elif end_index - start_index + 1 >= max_holding_days:
        status = "expired_or_removed"
        status_reason = "shadow max holding window reached"
    elif days_held < min_holding_days:
        status = "min_hold_not_met"
        status_reason = "minimum holding days not met; exit cannot trigger yet"
    else:
        close = to_float(latest_bar.get("close"))
        if close is not None and close <= threshold * (1 + trail_zone_buffer):
            status = "trail_stop_zone"
            status_reason = "close is near trail10 threshold; non-personal weakening watch"
        else:
            status = "hold"
            status_reason = "above trail10 threshold"
    return {
        "ranking_date": ranking_day,
        "entry_date": entry_date,
        "as_of_date": as_of_date,
        "stock_id": stock_id,
        "stock_name": row.get("stock_name"),
        "source_rank": row.get("rank"),
        "entry_open_proxy": round(float(entry_bar["open"]), 4),
        "latest_close": round(float(latest_bar["close"]), 4) if latest_bar.get("close") is not None else None,
        "days_held": days_held,
        "min_holding_days": min_holding_days,
        "trail_high_known": round(high_water, 4),
        "trail_threshold": round(threshold, 4),
        "trail_pct": trail_pct,
        "exit_date": exit_date,
        "exit_price": round(exit_price, 4) if exit_price is not None else None,
        "exit_reason": exit_reason,
        "status": status,
        "status_reason": status_reason,
        "personalized_sell_instruction": False,
    }


def state_sort_key(row: dict[str, Any]) -> tuple[int, str, int]:
    return (STATUS_ORDER.index(row.get("status")) if row.get("status") in STATUS_ORDER else 99, str(row.get("stock_id")), int(row.get("source_rank") or 99))


def warning_candidates(positions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for row in positions:
        if row.get("status") not in {"trail_stop_zone", "exit_triggered"}:
            continue
        result.append(
            {
                "stock_id": row.get("stock_id"),
                "stock_name": row.get("stock_name"),
                "status": row.get("status"),
                "plain_warning": "這檔進入轉弱觀察區；未進場者不要追，已持有者自行檢查持倉。",
                "personalized_sell_instruction": False,
            }
        )
    return result


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"# Production Trail10 Shadow - {payload['run_date']}",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']}`",
        f"- as_of_price_date: `{payload['inputs']['as_of_price_date']}`",
        f"- latest production Top10: `{summary['production_top10_count']}`",
        "",
        "## Status Counts",
        "",
    ]
    for status in STATUS_ORDER:
        lines.append(f"- {status}: `{summary['status_counts'].get(status, 0)}`")
    lines.extend(["", "## Current Shadow Positions", "", "| Stock | Rank | Entry | Status | Trail | Close | Reason |", "|---|---:|---|---|---:|---:|---|"])
    for row in payload["shadow_positions"]:
        if row.get("status") == "expired_or_removed":
            continue
        lines.append(
            "| {sid} {name} | {rank} | {entry} | {status} | {trail} | {close} | {reason} |".format(
                sid=row.get("stock_id"),
                name=row.get("stock_name") or "",
                rank=row.get("source_rank"),
                entry=row.get("entry_date"),
                status=row.get("status"),
                trail=row.get("trail_threshold"),
                close=row.get("latest_close"),
                reason=row.get("status_reason"),
            )
        )
    lines.extend(
        [
            "",
            "## Boundary",
            "",
            "- 這是 production ranking + trail10 的非個人化 shadow artifact。",
            "- 不改正式 Top10，不改 Clawd live message，不代表個人持倉賣出指令。",
        ]
    )
    return "\n".join(lines) + "\n"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    rankings_dir = resolve_path(args.rankings_dir)
    features_path = resolve_path(args.features)
    if rankings_dir is None or not rankings_dir.exists():
        raise FileNotFoundError(f"找不到 rankings dir：{args.rankings_dir}")
    if features_path is None or not features_path.exists():
        raise FileNotFoundError(f"找不到 features：{args.features}")
    files = ranking_files(rankings_dir, args.date)
    selected = files[-args.lookback_ranking_days :]
    latest_ranking = next((path for path in reversed(files) if ranking_date(path) == args.date), files[-1])
    production_top10 = read_ranking(latest_ranking, args.top_n)
    trade_dates, prices, as_of_price_date = load_prices(features_path, args.date)
    date_index = trade_date_index(trade_dates)
    positions = []
    for path in selected:
        day = ranking_date(path)
        for row in read_ranking(path, args.top_n):
            positions.append(
                simulate_position(
                    row=row,
                    ranking_day=day,
                    trade_dates=trade_dates,
                    date_index=date_index,
                    prices=prices,
                    as_of_date=as_of_price_date,
                    min_holding_days=args.min_holding_days,
                    max_holding_days=args.max_holding_days,
                    trail_pct=args.trail_pct,
                    trail_zone_buffer=args.trail_zone_buffer,
                )
            )
    positions = sorted(positions, key=state_sort_key)
    events = [
        row
        for row in positions
        if row.get("status") in {"candidate_active", "exit_triggered", "trail_stop_zone"}
    ]
    status_counts = Counter(row.get("status") for row in positions)
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "shadow" / "production_trail10" / f"production_trail10_shadow_{args.date}.json"
    latest_output = output.parent / "production_trail10_shadow_latest.json"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": args.date,
        "status": "OK",
        "contract": {
            "shadow_only": True,
            "production_ranking_source_unchanged": True,
            "changes_production_ranking": False,
            "changes_clawd_live_message": False,
            "changes_model": False,
            "personalized_sell_instruction": False,
            "uses_future_data_for_exit": False,
            "non_personal_observation_only": True,
            "does_not_send_push": True,
        },
        "inputs": {
            "rankings_dir": repo_path(rankings_dir),
            "features": repo_path(features_path),
            "latest_ranking": repo_path(latest_ranking),
            "ranking_files": [repo_path(path) for path in selected],
            "as_of_price_date": as_of_price_date,
            "lookback_ranking_days": args.lookback_ranking_days,
            "top_n": args.top_n,
        },
        "production_top10": production_top10,
        "shadow_positions": positions,
        "shadow_events": events,
        "exit_policy": {
            "entry": "D+1 open proxy",
            "minimum_holding_trading_days": args.min_holding_days,
            "trail_high": "entry open and subsequent known highs up to current day; exit check uses prior known high before same-day high update",
            "trail_threshold": f"high_water * (1 - {args.trail_pct})",
            "max_holding_days": args.max_holding_days,
            "no_future_data": True,
        },
        "capital_policy": {
            "initial_cash": 300_000,
            "odd_lot": True,
            "max_position_weight": 0.10,
            "max_gross_exposure_shadow_reference": 0.90,
        },
        "warning_candidates": warning_candidates(positions),
        "summary": {
            "production_top10_count": len(production_top10),
            "shadow_position_count": len(positions),
            "status_counts": dict(status_counts),
            "warning_candidate_count": len(warning_candidates(positions)),
        },
        "decision": "PRODUCTION_TRAIL10_SHADOW_READY",
        "blocked_reasons": [],
        "outputs": {
            "json": repo_path(output),
            "markdown": repo_path(output.with_suffix(".md")),
            "latest": repo_path(latest_output),
        },
    }


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "shadow" / "production_trail10" / f"production_trail10_shadow_{args.date}.json"
    if output is None:
        raise RuntimeError("output resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    latest_output = output.parent / "production_trail10_shadow_latest.json"
    latest_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "decision": payload["decision"], "output": repo_path(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
