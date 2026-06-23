#!/usr/bin/env python3
"""建立 borrow-squeeze 價格/族群確認 replay 報告。

此報告只讀 borrow-squeeze materialized CSV 與既有 features/reference，
用來檢查「借券賣出接近上限」是否同時伴隨價格突破與族群轉強。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

RUN_DATE = "2026-06-22"
SCHEMA_VERSION = "borrow-squeeze-replay.v1"
HORIZONS = (3, 5, 10, 20)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build borrow-squeeze replay report")
    parser.add_argument("--borrow-csv", default=None, help="borrow-squeeze materialized CSV；未指定時使用最新檔")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--industry-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument("--near-cap-ratio", type=float, default=0.095)
    parser.add_argument("--cap-hit-ratio", type=float, default=0.099)
    parser.add_argument("--industry-return-5d-threshold", type=float, default=0.03)
    parser.add_argument("--industry-breakout-rate-threshold", type=float, default=0.03)
    parser.add_argument("--output", default=f"artifacts/model_experiments/borrow_squeeze_replay_{RUN_DATE}.json")
    parser.add_argument("--markdown-output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def latest_borrow_csv() -> Path | None:
    root = PROJECT_ROOT / "data" / "raw" / "borrow_squeeze"
    if not root.exists():
        return None
    files = sorted(
        path for path in root.glob("borrow_squeeze_materialized*.csv")
        if path.is_file() and "seed" not in path.name and "smoke" not in path.name
    )
    return files[-1] if files else None


def clean_number(value: Any, digits: int = 6) -> float | None:
    import pandas as pd

    if value is None or pd.isna(value):
        return None
    return round(float(value), digits)


def load_borrow(path: Path) -> Any:
    import pandas as pd

    frame = pd.read_csv(path, parse_dates=["date"], dtype={"stock_id": str})
    if frame.empty:
        return frame
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    return frame.sort_values(["stock_id", "date"])


def load_features(path: Path, industry_map_path: Path) -> Any:
    import pandas as pd

    frame = pd.read_parquet(path)
    date_column = "trade_date" if "trade_date" in frame.columns else "date"
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame[date_column])
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    keep = [
        "date",
        "stock_id",
        "stock_name",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "avg_volume_20d",
        "volume_ratio_5d",
        "volume_ratio_20d",
        "breakout_flag",
        "break_20d_high",
    ]
    for column in keep:
        if column not in frame.columns:
            frame[column] = None
    frame = frame[keep].sort_values(["stock_id", "date"]).copy()
    for column in ["open", "high", "low", "close", "volume", "avg_volume_20d", "volume_ratio_5d", "volume_ratio_20d"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["prev_close"] = frame.groupby("stock_id")["close"].shift(1)
    frame["return_1d"] = frame["close"] / frame["prev_close"] - 1
    frame["trailing_return_5d"] = frame.groupby("stock_id")["close"].pct_change(5)
    frame["prior_60d_high"] = frame.groupby("stock_id")["high"].transform(lambda item: item.shift(1).rolling(60, min_periods=20).max())
    frame["prior_120d_high"] = frame.groupby("stock_id")["high"].transform(lambda item: item.shift(1).rolling(120, min_periods=40).max())
    frame["new_60d_high"] = frame["close"] >= frame["prior_60d_high"]
    frame["new_120d_high"] = frame["close"] >= frame["prior_120d_high"]
    frame["price_breakout_confirm"] = (
        frame["new_60d_high"].fillna(False)
        | frame["new_120d_high"].fillna(False)
        | (pd.to_numeric(frame["breakout_flag"], errors="coerce").fillna(0) > 0)
        | (pd.to_numeric(frame["break_20d_high"], errors="coerce").fillna(0) > 0)
    )
    frame["volume_confirm"] = (
        (pd.to_numeric(frame["volume_ratio_20d"], errors="coerce").fillna(0) >= 1.2)
        | (pd.to_numeric(frame["volume_ratio_5d"], errors="coerce").fillna(0) >= 1.2)
    )

    industry = pd.read_csv(industry_map_path, dtype={"stock_id": str}) if industry_map_path.exists() else pd.DataFrame()
    if not industry.empty:
        industry["stock_id"] = industry["stock_id"].astype(str).str.zfill(4)
        industry = industry[["stock_id", "industry_name", "sector_name"]].drop_duplicates(subset=["stock_id"], keep="last")
        frame = frame.merge(industry, on="stock_id", how="left")
    else:
        frame["industry_name"] = None
        frame["sector_name"] = None

    group_cols = ["date", "industry_name"]
    industry_metrics = (
        frame.dropna(subset=["industry_name"])
        .groupby(group_cols)
        .agg(
            industry_stock_count=("stock_id", "nunique"),
            industry_avg_return_1d=("return_1d", "mean"),
            industry_avg_return_5d=("trailing_return_5d", "mean"),
            industry_breakout_rate=("price_breakout_confirm", "mean"),
            industry_volume_confirm_rate=("volume_confirm", "mean"),
        )
        .reset_index()
    )
    frame = frame.merge(industry_metrics, on=group_cols, how="left")
    return frame


def add_forward_returns(features: Any) -> Any:
    frame = features.sort_values(["stock_id", "date"]).copy()
    for horizon in HORIZONS:
        future_close = frame.groupby("stock_id")["close"].shift(-horizon)
        frame[f"forward_return_{horizon}d"] = future_close / frame["close"] - 1
    return frame


def build_observations(borrow: Any, features: Any, args: argparse.Namespace) -> list[dict[str, Any]]:
    import pandas as pd

    merged = borrow.merge(features, on=["date", "stock_id"], how="left", suffixes=("", "_feature"))
    observations: list[dict[str, Any]] = []
    for row in merged.sort_values(["date", "stock_id"]).itertuples(index=False):
        data = row._asdict()
        ratio = data.get("sbl_balance_to_issued_shares")
        ratio_float = float(ratio) if ratio is not None and pd.notna(ratio) else None
        cap_hit = bool(ratio_float is not None and ratio_float >= args.cap_hit_ratio)
        near_cap = bool(ratio_float is not None and ratio_float >= args.near_cap_ratio)
        price_confirm = bool(data.get("price_breakout_confirm")) if pd.notna(data.get("price_breakout_confirm")) else False
        volume_confirm = bool(data.get("volume_confirm")) if pd.notna(data.get("volume_confirm")) else False
        industry_return_5d = data.get("industry_avg_return_5d")
        industry_breakout_rate = data.get("industry_breakout_rate")
        industry_turning_strong = bool(
            industry_return_5d is not None
            and pd.notna(industry_return_5d)
            and float(industry_return_5d) >= args.industry_return_5d_threshold
            and industry_breakout_rate is not None
            and pd.notna(industry_breakout_rate)
            and float(industry_breakout_rate) >= args.industry_breakout_rate_threshold
        )
        composite = bool(cap_hit and price_confirm and industry_turning_strong)
        strong_composite = bool(composite and volume_confirm)
        observations.append(
            {
                "date": str(pd.to_datetime(data["date"]).date()),
                "stock_id": data["stock_id"],
                "stock_name": data.get("stock_name"),
                "industry_name": data.get("industry_name"),
                "sector_name": data.get("sector_name"),
                "close": clean_number(data.get("close"), 3),
                "sbl_balance_lots": clean_number(data.get("sbl_balance_lots"), 3),
                "issued_shares_lots": clean_number(data.get("issued_shares_lots"), 3),
                "sbl_balance_to_issued_shares": clean_number(ratio_float, 6),
                "sbl_pressure_score": clean_number(data.get("sbl_pressure_score"), 2),
                "near_cap": near_cap,
                "cap_hit": cap_hit,
                "new_60d_high": bool(data.get("new_60d_high")) if pd.notna(data.get("new_60d_high")) else False,
                "new_120d_high": bool(data.get("new_120d_high")) if pd.notna(data.get("new_120d_high")) else False,
                "price_breakout_confirm": price_confirm,
                "volume_confirm": volume_confirm,
                "volume_ratio_20d": clean_number(data.get("volume_ratio_20d"), 3),
                "trailing_return_5d": clean_number(data.get("trailing_return_5d"), 6),
                "industry_stock_count": None if pd.isna(data.get("industry_stock_count")) else int(data.get("industry_stock_count")),
                "industry_avg_return_5d": clean_number(industry_return_5d, 6),
                "industry_breakout_rate": clean_number(industry_breakout_rate, 6),
                "industry_turning_strong": industry_turning_strong,
                "composite_signal": composite,
                "strong_composite_signal": strong_composite,
                "forward_returns": {
                    str(horizon): clean_number(data.get(f"forward_return_{horizon}d"), 6)
                    for horizon in HORIZONS
                },
            }
        )
    return observations


def summarize_group(observations: list[dict[str, Any]], predicate: Any) -> dict[str, Any]:
    selected = [item for item in observations if predicate(item)]
    summary: dict[str, Any] = {"count": len(selected)}
    for horizon in HORIZONS:
        values = [
            item["forward_returns"][str(horizon)]
            for item in selected
            if item.get("forward_returns", {}).get(str(horizon)) is not None
        ]
        summary[f"available_forward_{horizon}d"] = len(values)
        summary[f"avg_forward_return_{horizon}d"] = clean_number(sum(values) / len(values), 6) if values else None
        summary[f"positive_rate_{horizon}d"] = clean_number(sum(1 for value in values if value > 0) / len(values), 6) if values else None
    return summary


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    borrow_path = resolve_path(args.borrow_csv) if args.borrow_csv else latest_borrow_csv()
    blockers: list[str] = []
    if borrow_path is None or not borrow_path.exists():
        blockers.append("borrow-squeeze materialized csv missing")
        return blocked_payload(args, borrow_path, blockers)
    features_path = resolve_path(args.features)
    industry_path = resolve_path(args.industry_map)
    if not features_path.exists():
        blockers.append("features parquet missing")
        return blocked_payload(args, borrow_path, blockers)

    borrow = load_borrow(borrow_path)
    features = add_forward_returns(load_features(features_path, industry_path))
    observations = build_observations(borrow, features, args)
    if not observations:
        blockers.append("replay produced zero observations")
    if not any(item["cap_hit"] for item in observations):
        blockers.append("no cap-hit observations")
    status = "OK" if not blockers else "BLOCKED"
    group_summary = {
        "all": summarize_group(observations, lambda item: True),
        "cap_hit": summarize_group(observations, lambda item: item["cap_hit"]),
        "cap_hit_price_confirm": summarize_group(observations, lambda item: item["cap_hit"] and item["price_breakout_confirm"]),
        "cap_hit_price_industry_confirm": summarize_group(observations, lambda item: item["composite_signal"]),
        "strong_composite": summarize_group(observations, lambda item: item["strong_composite_signal"]),
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "contract": {
            "research_only": True,
            "replay_only": True,
            "changes_model": False,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "does_not_send_push": True,
            "uses_existing_features_only": True,
        },
        "inputs": {
            "borrow_csv": repo_path(borrow_path),
            "features": repo_path(features_path),
            "industry_map": repo_path(industry_path),
            "near_cap_ratio": args.near_cap_ratio,
            "cap_hit_ratio": args.cap_hit_ratio,
            "industry_return_5d_threshold": args.industry_return_5d_threshold,
            "industry_breakout_rate_threshold": args.industry_breakout_rate_threshold,
        },
        "summary": {
            "observation_count": len(observations),
            "cap_hit_count": sum(1 for item in observations if item["cap_hit"]),
            "price_confirm_count": sum(1 for item in observations if item["price_breakout_confirm"]),
            "industry_turning_strong_count": sum(1 for item in observations if item["industry_turning_strong"]),
            "composite_signal_count": sum(1 for item in observations if item["composite_signal"]),
            "strong_composite_signal_count": sum(1 for item in observations if item["strong_composite_signal"]),
            "latest_observation_date": max((item["date"] for item in observations), default=None),
            "group_summary": group_summary,
        },
        "observations": observations,
        "blockers": blockers,
        "decision": {
            "status": "MONITOR_ONLY" if status == "OK" else "REPLAY_BLOCKED",
            "production_status": "BLOCKED",
            "primary_read": primary_read(observations, group_summary, status),
        },
    }


def blocked_payload(args: argparse.Namespace, borrow_path: Path | None, blockers: list[str]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "BLOCKED",
        "contract": {
            "research_only": True,
            "replay_only": True,
            "changes_model": False,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "does_not_send_push": True,
            "uses_existing_features_only": True,
        },
        "inputs": {
            "borrow_csv": repo_path(borrow_path) if borrow_path else None,
            "features": args.features,
            "industry_map": args.industry_map,
        },
        "summary": {},
        "observations": [],
        "blockers": blockers,
        "decision": {
            "status": "REPLAY_BLOCKED",
            "production_status": "BLOCKED",
            "primary_read": "borrow-squeeze replay 缺必要輸入，尚不能判斷。",
        },
    }


def primary_read(observations: list[dict[str, Any]], group_summary: dict[str, Any], status: str) -> str:
    if status != "OK":
        return "borrow-squeeze replay 尚未產出可用觀察。"
    composite_count = group_summary["cap_hit_price_industry_confirm"]["count"]
    forward_available = group_summary["cap_hit_price_industry_confirm"].get("available_forward_5d")
    if composite_count and not forward_available:
        return "已抓到 cap-hit + 價格突破 + 族群轉強的候選事件，但目前資料位於最新區間，尚未有足夠 forward return。"
    if composite_count:
        return "已抓到 cap-hit + 價格突破 + 族群轉強事件，可進一步擴大樣本做統計檢定。"
    cap_hit_count = group_summary["cap_hit"]["count"]
    if cap_hit_count:
        return "已抓到 cap-hit 事件，但尚未同時滿足價格突破與族群轉強；維持 monitor-only。"
    return "目前沒有接近上限事件。"


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload.get("summary") or {}
    lines = [
        "# Borrow Squeeze Replay",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- production_status: `{payload['decision']['production_status']}`",
        "",
        "## Primary Read",
        "",
        payload["decision"]["primary_read"],
        "",
        "## Summary",
        "",
    ]
    for key in [
        "observation_count",
        "cap_hit_count",
        "price_confirm_count",
        "industry_turning_strong_count",
        "composite_signal_count",
        "strong_composite_signal_count",
        "latest_observation_date",
    ]:
        lines.append(f"- {key}: `{summary.get(key)}`")
    lines.extend(["", "## Observations", ""])
    for item in payload.get("observations", [])[:20]:
        lines.append(
            "- {date} {stock_id} {name}: ratio={ratio}, close={close}, price={price}, industry={industry}, composite={composite}, fwd5={fwd5}".format(
                date=item["date"],
                stock_id=item["stock_id"],
                name=item.get("stock_name") or "",
                ratio=item.get("sbl_balance_to_issued_shares"),
                close=item.get("close"),
                price=item.get("price_breakout_confirm"),
                industry=item.get("industry_turning_strong"),
                composite=item.get("composite_signal"),
                fwd5=item.get("forward_returns", {}).get("5"),
            )
        )
    if not payload.get("observations"):
        lines.append("- none")
    lines.extend(["", "## Blockers", ""])
    lines.extend([f"- {item}" for item in payload.get("blockers", [])] or ["- none"])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output_path = resolve_path(args.output)
    markdown_path = resolve_path(args.markdown_output) if args.markdown_output else output_path.with_suffix(".md")
    payload = build_payload(args)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decision": payload["decision"]["status"],
                "output": repo_path(output_path),
                "blockers": payload["blockers"],
                "observation_count": payload.get("summary", {}).get("observation_count"),
                "composite_signal_count": payload.get("summary", {}).get("composite_signal_count"),
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
