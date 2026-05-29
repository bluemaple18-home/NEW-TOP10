#!/usr/bin/env python3
"""拆解 production replay 表現，避免把單一總分誤判成模型穩定。

此腳本只讀既有 replay artifact，不訓練模型、不調參、不改 ranking。
用途是定位拖累來源：sealed / 非 sealed、盤勢曝險、排名段、產業集中度。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "replay-diagnostics.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="diagnose replay slices without training")
    parser.add_argument("--replay", required=True, help="run_backtest_replay.py 產出的 JSON")
    parser.add_argument("--sealed-start", default=None, help="sealed 起始日，例如 2026-02-04")
    parser.add_argument("--sealed-end", default=None, help="sealed 結束日，例如 2026-05-13")
    parser.add_argument("--market-regime-history", default=None, help="build_market_regime_history.py 產出的 JSON")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def gross_exposure_regime(value: Any) -> str:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return "UNKNOWN"
    if float(parsed) >= 0.8:
        return "RISK_ON"
    if float(parsed) >= 0.6:
        return "NEUTRAL"
    return "RISK_OFF"


def load_market_regime_map(path_value: str | None) -> dict[str, str]:
    if not path_value:
        return {}
    path = resolve_path(path_value)
    if not path.exists():
        raise FileNotFoundError(f"market regime history 不存在：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    mapping: dict[str, str] = {}
    for row in payload.get("rows", []):
        date = str(row.get("trade_date") or "").strip()
        label = str(row.get("regime_label") or "").strip()
        if date and label:
            mapping[date] = label
    if not mapping:
        raise ValueError(f"market regime history 沒有可用 rows：{path}")
    return mapping


def rank_bucket(value: Any) -> str:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return "unknown"
    rank = int(parsed)
    if rank <= 3:
        return "1-3"
    if rank <= 5:
        return "4-5"
    return "6-10"


def split_bucket(value: Any, sealed_start: str | None, sealed_end: str | None) -> str:
    if not sealed_start or not sealed_end:
        return "unknown"
    date = pd.to_datetime(value, errors="coerce")
    start = pd.to_datetime(sealed_start, errors="coerce")
    end = pd.to_datetime(sealed_end, errors="coerce")
    if pd.isna(date) or pd.isna(start) or pd.isna(end):
        return "unknown"
    if start <= date <= end:
        return "sealed"
    if date < start:
        return "pre_sealed"
    return "post_sealed"


def summarize_group(group: pd.DataFrame) -> dict[str, Any]:
    returns = pd.to_numeric(group["net_return"], errors="coerce")
    return {
        "trade_count": int(len(group)),
        "avg_net_return": round(float(returns.mean()), 6),
        "median_net_return": round(float(returns.median()), 6),
        "hit_rate": round(float((returns > 0).mean()), 6),
        "avg_mae": round(float(pd.to_numeric(group["mae"], errors="coerce").mean()), 6),
        "avg_mfe": round(float(pd.to_numeric(group["mfe"], errors="coerce").mean()), 6),
    }


def summarize_by(frame: pd.DataFrame, columns: list[str]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for keys, group in frame.groupby(columns, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        label = "::".join(str(key) for key in keys)
        result[label] = summarize_group(group)
    return result


def top_contributors(frame: pd.DataFrame, group_col: str, horizon: int, limit: int = 12) -> list[dict[str, Any]]:
    subset = frame[frame["horizon"] == horizon].copy()
    rows = []
    for name, group in subset.groupby(group_col, dropna=False):
        if len(group) < 5:
            continue
        summary = summarize_group(group)
        rows.append({"group": str(name), **summary})
    return sorted(rows, key=lambda row: row["avg_net_return"])[:limit]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    replay_path = resolve_path(args.replay)
    replay = json.loads(replay_path.read_text(encoding="utf-8"))
    frame = pd.DataFrame(replay.get("trades", []))
    if frame.empty:
        raise ValueError("replay trades is empty")
    regime_map = load_market_regime_map(args.market_regime_history)
    frame["ranking_date"] = pd.to_datetime(frame["ranking_date"], errors="coerce")
    frame["split_bucket"] = frame["ranking_date"].map(lambda value: split_bucket(value, args.sealed_start, args.sealed_end))
    date_key = frame["ranking_date"].dt.date.astype(str)
    if regime_map:
        frame["regime_bucket"] = date_key.map(regime_map).fillna("UNKNOWN")
        regime_source = "market_regime_history"
    else:
        frame["regime_bucket"] = frame["gross_exposure"].map(gross_exposure_regime)
        regime_source = "gross_exposure_fallback"
    frame["rank_bucket"] = frame["rank"].map(rank_bucket)
    frame["sector_name"] = frame.get("sector_name", "unknown").fillna("unknown")
    frame["industry_name"] = frame.get("industry_name", "unknown").fillna("unknown")

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "source": "production_replay_trades",
            "research_only": True,
            "trains_model": False,
            "tunes_ranking": False,
            "anti_overfit_note": "此診斷只定位問題，不可直接用單次 slice 結果調參。",
        },
        "inputs": {
            "replay": str(replay_path),
            "sealed_start": args.sealed_start,
            "sealed_end": args.sealed_end,
            "market_regime_history": str(resolve_path(args.market_regime_history)) if args.market_regime_history else None,
            "regime_source": regime_source,
            "trade_count": int(len(frame)),
        },
        "summary": {
            "by_horizon": summarize_by(frame, ["horizon"]),
            "by_split_horizon": summarize_by(frame, ["split_bucket", "horizon"]),
            "by_regime_horizon": summarize_by(frame, ["regime_bucket", "horizon"]),
            "by_rank_bucket_horizon": summarize_by(frame, ["rank_bucket", "horizon"]),
            "worst_sectors_10d": top_contributors(frame, "sector_name", horizon=10),
            "worst_industries_10d": top_contributors(frame, "industry_name", horizon=10),
        },
    }


def pct(value: float | int | None) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def metric_row(name: str, item: dict[str, Any]) -> str:
    return "| {name} | {n} | {avg} | {med} | {hit} | {mae} | {mfe} |".format(
        name=name,
        n=item["trade_count"],
        avg=pct(item["avg_net_return"]),
        med=pct(item["median_net_return"]),
        hit=pct(item["hit_rate"]),
        mae=pct(item["avg_mae"]),
        mfe=pct(item["avg_mfe"]),
    )


def render_table(title: str, rows: dict[str, dict[str, Any]]) -> list[str]:
    lines = [
        f"## {title}",
        "",
        "| Group | Trades | Avg Return | Median | Hit Rate | Avg MAE | Avg MFE |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for key, item in sorted(rows.items()):
        lines.append(metric_row(key, item))
    lines.append("")
    return lines


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Replay Diagnostics",
        "",
        f"- generated_at：{payload['generated_at']}",
        f"- replay：{payload['inputs']['replay']}",
        f"- trade_count：{payload['inputs']['trade_count']}",
        f"- sealed：{payload['inputs']['sealed_start']} ~ {payload['inputs']['sealed_end']}",
        "",
    ]
    summary = payload["summary"]
    lines.extend(render_table("By Horizon", summary["by_horizon"]))
    lines.extend(render_table("By Split And Horizon", summary["by_split_horizon"]))
    lines.extend(render_table("By Regime And Horizon", summary["by_regime_horizon"]))
    lines.extend(render_table("By Rank Bucket And Horizon", summary["by_rank_bucket_horizon"]))
    for key in ["worst_sectors_10d", "worst_industries_10d"]:
        lines.extend([f"## {key}", "", "| Group | Trades | Avg Return | Hit Rate |", "|---|---:|---:|---:|"])
        for row in summary[key]:
            lines.append(f"| {row['group']} | {row['trade_count']} | {pct(row['avg_net_return'])} | {pct(row['hit_rate'])} |")
        lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output_path = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "backtest" / "replay_diagnostics_latest.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": str(output_path), "markdown": str(output_path.with_suffix('.md'))}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
