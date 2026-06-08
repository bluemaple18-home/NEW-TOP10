#!/usr/bin/env python3
"""彙總多份 chip warning replay 報告。

用途：多次 shadow replay 可能覆蓋相同 date/stock_id。本腳本只讀 replay
artifact，去重後重新計算 group outcome，避免把重複樣本誤當成證據。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = datetime.now().strftime("%Y-%m-%d")
SCHEMA_VERSION = "chip-warning-replay-aggregate.v1"
HORIZONS = ("3", "5", "10")
GROUPS = ("CHIP_RISK", "FOREIGN_SELL_ONLY", "MARGIN_UP_ONLY", "CHIP_SUPPORTIVE", "NEUTRAL")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build aggregate chip warning replay report")
    parser.add_argument(
        "--reports",
        nargs="+",
        default=[
            "artifacts/model_experiments/chip_warning_shadow_report_2026-06-06.json",
            "artifacts/model_experiments/chip_warning_shadow_report_recent_top10_2026-06-06.json",
            "artifacts/model_experiments/chip_warning_shadow_report_tail10_subset_2026-06-06.json",
            "artifacts/model_experiments/chip_warning_shadow_report_top3_60d_2026-06-07.json",
            "artifacts/model_experiments/chip_warning_shadow_report_top10_20d_2026-06-08.json",
        ],
    )
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/chip_warning_replay_aggregate_{RUN_DATE}.json",
    )
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def summarize(values: list[float]) -> dict[str, Any]:
    if not values:
        return {"count": 0, "avg_return": None, "median_return": None, "negative_rate": None, "loss_gt_5pct_rate": None}
    return {
        "count": len(values),
        "avg_return": round(sum(values) / len(values), 6),
        "median_return": round(float(median(values)), 6),
        "negative_rate": round(sum(1 for value in values if value < 0) / len(values), 6),
        "loss_gt_5pct_rate": round(sum(1 for value in values if value <= -0.05) / len(values), 6),
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    report_paths = [resolve_path(path) for path in args.reports]
    source_reports: list[dict[str, Any]] = []
    deduped: dict[tuple[str, str], dict[str, Any]] = {}
    duplicate_count = 0

    for path in report_paths:
        payload = load_json(path)
        replay = payload.get("replay") or {}
        source_reports.append(
            {
                "path": repo_path(path),
                "status": payload.get("status"),
                "decision": (payload.get("decision") or {}).get("status"),
                "observation_count": replay.get("observation_count"),
                "target_dates": replay.get("target_dates"),
            }
        )
        observations = replay.get("observations") or replay.get("observations_sample") or []
        for observation in observations:
            key = (str(observation.get("date")), str(observation.get("stock_id")).zfill(4))
            if key in deduped:
                duplicate_count += 1
                continue
            deduped[key] = observation

    observations = list(deduped.values())
    by_group_horizon: dict[str, dict[str, list[float]]] = {group: {horizon: [] for horizon in HORIZONS} for group in GROUPS}
    group_counts: Counter[str] = Counter()
    signal_counts: Counter[str] = Counter()
    target_dates = sorted({str(item.get("date")) for item in observations})

    for item in observations:
        group = str(item.get("chip_group"))
        if group not in by_group_horizon:
            continue
        group_counts[group] += 1
        signal_counts.update(item.get("signals") or [])
        returns = item.get("forward_returns") or {}
        for horizon in HORIZONS:
            if horizon in returns:
                by_group_horizon[group][horizon].append(float(returns[horizon]))

    group_outcomes = {
        group: {horizon: summarize(values) for horizon, values in horizon_values.items()}
        for group, horizon_values in by_group_horizon.items()
    }

    risk_5d = group_outcomes["CHIP_RISK"]["5"]
    supportive_5d = group_outcomes["CHIP_SUPPORTIVE"]["5"]
    risk_directional = (
        risk_5d["count"] >= 10
        and supportive_5d["count"] >= 10
        and risk_5d["avg_return"] is not None
        and supportive_5d["avg_return"] is not None
        and risk_5d["avg_return"] < supportive_5d["avg_return"]
    )
    if risk_directional:
        decision_status = "PARTIAL_MONITOR_ONLY"
        primary_read = "去重彙總後 CHIP_RISK 的 5D 平均報酬低於 CHIP_SUPPORTIVE，但差距很小，只能研究監控。"
    else:
        decision_status = "NOT_STABLE_ENOUGH_FOR_WARNING_CHANNEL"
        primary_read = "去重彙總後仍無法證明 CHIP_RISK 穩定劣於 CHIP_SUPPORTIVE，不能做正式 warning。"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "research_only": True,
            "warning_only": True,
            "changes_model": False,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "does_not_send_push": True,
        },
        "inputs": {"reports": source_reports},
        "summary": {
            "raw_observation_count": sum(int(item.get("observation_count") or 0) for item in source_reports),
            "duplicate_observation_count": duplicate_count,
            "deduped_observation_count": len(observations),
            "target_dates": target_dates,
            "target_date_count": len(target_dates),
            "group_counts": dict(group_counts),
            "signal_counts": dict(signal_counts),
            "group_outcomes": group_outcomes,
        },
        "decision": {
            "status": decision_status,
            "production_status": "BLOCKED",
            "primary_read": primary_read,
            "next_step": "不要單獨推 chip warning；若要保留，需證明更嚴格的 composite 門檻有效。",
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Chip Warning Replay Aggregate",
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
        f"- raw_observation_count: `{summary['raw_observation_count']}`",
        f"- duplicate_observation_count: `{summary['duplicate_observation_count']}`",
        f"- deduped_observation_count: `{summary['deduped_observation_count']}`",
        f"- target_date_count: `{summary['target_date_count']}`",
        f"- group_counts: `{summary['group_counts']}`",
        "",
        "| group | 3D avg | 5D avg | 10D avg | 5D negative | count 5D |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for group in GROUPS:
        row = summary["group_outcomes"][group]
        h3 = row["3"]
        h5 = row["5"]
        h10 = row["10"]
        lines.append(
            f"| `{group}` | {pct(h3['avg_return'])} | {pct(h5['avg_return'])} | {pct(h10['avg_return'])} | "
            f"{pct(h5['negative_rate'])} | {h5['count']} |"
        )
    lines.extend(["", "## Next Step", "", f"- {payload['decision']['next_step']}"])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output_path = resolve_path(args.output)
    markdown_path = resolve_path(args.markdown_output) if args.markdown_output else output_path.with_suffix(".md")
    payload = build_payload(args)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "decision": payload["decision"]["status"],
                "output": repo_path(output_path),
                "markdown": repo_path(markdown_path),
                "deduped_observation_count": payload["summary"]["deduped_observation_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
