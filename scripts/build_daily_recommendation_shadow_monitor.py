#!/usr/bin/env python3
"""建立每日推薦 shadow monitor 報告。

此腳本比較 production Top10 與 research-only constrained shadow Top10，
用於觀察候選排序規則是否值得長期監控。它不改 production ranking、不推播。
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "daily-recommendation-shadow-monitor.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build daily recommendation shadow monitor report")
    parser.add_argument("--date", default="2026-06-04")
    parser.add_argument("--candidate-id", default="feature_group_constrained_k9")
    parser.add_argument("--production-dir", default="artifacts")
    parser.add_argument("--shadow-dir", required=True)
    parser.add_argument("--shadow-source-summary", default=None)
    parser.add_argument("--top-n", type=int, default=10)
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


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def ranking_dates(path: Path) -> list[str]:
    return sorted(item.stem.removeprefix("ranking_") for item in path.glob("ranking_*.csv"))


def read_ranking(path: Path, top_n: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))[:top_n]
    normalized = []
    for idx, row in enumerate(rows, start=1):
        normalized.append(
            {
                "rank": idx,
                "stock_id": str(row.get("stock_id", "")).strip().zfill(4),
                "stock_name": row.get("stock_name"),
                "risk_adjusted_score": parse_float(row.get("risk_adjusted_score")),
                "model_prob": parse_float(row.get("model_prob")),
                "market_regime": row.get("market_regime"),
                "shadow_market_regime": row.get("shadow_market_regime"),
                "constrained_shadow_source": row.get("constrained_shadow_source"),
            }
        )
    return normalized


def source_regime_by_date(summary_path: Path | None) -> dict[str, str]:
    if summary_path is None or not summary_path.exists():
        return {}
    source_dir = summary_path.parent
    regimes: dict[str, str] = {}
    for date_text in ranking_dates(source_dir):
        rows = read_ranking(source_dir / f"ranking_{date_text}.csv", top_n=1)
        if rows:
            regimes[date_text] = str(rows[0].get("shadow_market_regime") or "UNKNOWN")
    return regimes


def parse_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(parsed) else round(parsed, 6)


def compare_date(date_text: str, production_rows: list[dict[str, Any]], shadow_rows: list[dict[str, Any]]) -> dict[str, Any]:
    prod_ids = [row["stock_id"] for row in production_rows]
    shadow_ids = [row["stock_id"] for row in shadow_rows]
    prod_set = set(prod_ids)
    shadow_set = set(shadow_ids)
    added = [row for row in shadow_rows if row["stock_id"] not in prod_set]
    removed = [row for row in production_rows if row["stock_id"] not in shadow_set]
    kept = [row for row in shadow_rows if row["stock_id"] in prod_set]
    return {
        "date": date_text,
        "overlap_count": len(prod_set & shadow_set),
        "added_vs_production": added,
        "removed_vs_production": removed,
        "kept_count": len(kept),
        "shadow_top10": shadow_rows,
        "production_top10": production_rows,
        "shadow_source_counts": dict(Counter(row.get("constrained_shadow_source") or "unknown" for row in shadow_rows)),
        "shadow_regime_counts": dict(Counter(row.get("shadow_market_regime") or "UNKNOWN" for row in shadow_rows)),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    production_dir = resolve_path(args.production_dir)
    shadow_dir = resolve_path(args.shadow_dir)
    if production_dir is None or shadow_dir is None:
        raise RuntimeError("production/shadow dir resolution failed")
    dates = sorted(set(ranking_dates(production_dir)) & set(ranking_dates(shadow_dir)))
    rows = []
    for date_text in dates:
        rows.append(
            compare_date(
                date_text,
                read_ranking(production_dir / f"ranking_{date_text}.csv", args.top_n),
                read_ranking(shadow_dir / f"ranking_{date_text}.csv", args.top_n),
            )
        )
    source_summary = read_json(resolve_path(args.shadow_source_summary))
    source_regimes = source_regime_by_date(resolve_path(args.shadow_source_summary) if args.shadow_source_summary else None)
    unknown_regime_dates = [date_text for date_text, regime in sorted(source_regimes.items()) if regime == "UNKNOWN"]
    overlap = [row["overlap_count"] for row in rows]
    added_count = [len(row["added_vs_production"]) for row in rows]
    latest = rows[-1] if rows else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "candidate_id": args.candidate_id,
        "contract": {
            "research_only": True,
            "shadow_monitor_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_send_push": True,
            "promotion_ready": False,
        },
        "inputs": {
            "production_dir": repo_path(production_dir),
            "shadow_dir": repo_path(shadow_dir),
            "shadow_source_summary": repo_path(resolve_path(args.shadow_source_summary)) if args.shadow_source_summary else None,
            "top_n": args.top_n,
        },
        "summary": {
            "date_count": len(rows),
            "start_date": rows[0]["date"] if rows else None,
            "end_date": rows[-1]["date"] if rows else None,
            "avg_overlap_count": round(sum(overlap) / len(overlap), 6) if overlap else None,
            "min_overlap_count": min(overlap) if overlap else None,
            "avg_added_vs_production": round(sum(added_count) / len(added_count), 6) if added_count else None,
            "unknown_regime_dates": unknown_regime_dates,
            "source_regime_by_date": source_regimes,
            "decision": "DAILY_SHADOW_READY_WITH_REGIME_GAP" if unknown_regime_dates else "DAILY_SHADOW_READY",
        },
        "latest": latest,
        "rows": rows,
        "errors": [] if rows else ["no overlapping production/shadow ranking dates"],
    }


def stock_label(row: dict[str, Any]) -> str:
    return f"{row.get('stock_id')} {row.get('stock_name') or ''}".strip()


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    latest = payload.get("latest") or {}
    lines = [
        "# RQ10 每日推薦 Shadow Monitor",
        "",
        f"- candidate: `{payload['candidate_id']}`",
        f"- decision: `{summary['decision']}`",
        f"- window: `{summary['start_date']} ~ {summary['end_date']}`",
        f"- date_count: `{summary['date_count']}`",
        f"- avg_overlap_count: `{summary['avg_overlap_count']}`",
        f"- min_overlap_count: `{summary['min_overlap_count']}`",
        f"- avg_added_vs_production: `{summary['avg_added_vs_production']}`",
        f"- unknown_regime_dates: `{summary['unknown_regime_dates']}`",
        "",
        "## 最新日差異",
        "",
        f"- latest_date: `{latest.get('date')}`",
        "- shadow 新增：" + ("、".join(stock_label(row) for row in latest.get("added_vs_production", [])) or "無"),
        "- production 被替換：" + ("、".join(stock_label(row) for row in latest.get("removed_vs_production", [])) or "無"),
        "",
        "| Rank | Shadow Top10 | Source |",
        "|---:|---|---|",
    ]
    for row in latest.get("shadow_top10", []):
        lines.append(f"| {row['rank']} | {stock_label(row)} | {row.get('constrained_shadow_source')} |")
    lines.extend(["", "## 邊界", ""])
    lines.extend(
        [
            "- 這是每日推薦 shadow monitor，不是 production ranking。",
            "- 不訓練模型、不改模型、不送推播。",
            "- `UNKNOWN` regime 日期要補 market regime history 後才能視為完整 daily shadow。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else OUTPUT_DIR / f"daily_recommendation_shadow_monitor_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK" if not payload["errors"] else "FAILED",
                "output": repo_path(output),
                "decision": payload["summary"]["decision"],
                "latest_date": payload.get("latest", {}).get("date"),
                "errors": payload["errors"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if not payload["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
