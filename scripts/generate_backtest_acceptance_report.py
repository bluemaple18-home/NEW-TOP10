#!/usr/bin/env python3
"""彙整 backtest 研究 artifacts 的 acceptance report。"""

from __future__ import annotations

import argparse
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "backtest-acceptance-report.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="generate backtest acceptance report")
    parser.add_argument("--portfolio", default=None)
    parser.add_argument("--persistence", default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | None, pattern: str) -> Path:
    if value:
        path = Path(value).expanduser()
        return path if path.is_absolute() else PROJECT_ROOT / path
    matches = sorted((PROJECT_ROOT / "artifacts" / "backtest").glob(pattern))
    if not matches:
        raise FileNotFoundError(f"找不到 artifact：{pattern}")
    return matches[-1]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def finite_number(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed if math.isfinite(parsed) else None


def portfolio_checks(payload: dict[str, Any]) -> dict[str, bool]:
    summary = payload.get("summary", {})
    inputs = payload.get("inputs", {})
    contract = payload.get("contract", {})
    max_gross = inputs.get("max_gross_exposure")
    max_group = inputs.get("max_group_exposure")
    max_gross_value = finite_number(max_gross)
    gross_metric = finite_number(summary.get("max_gross_exposure"))
    checks = {
        "schema_ok": payload.get("schema_version") == "overlap-portfolio-replay.v1",
        "overlap_contract": contract.get("overlapping_positions") is True,
        "model_feature_false": contract.get("model_feature") is False,
        "trade_count_positive": int(summary.get("trade_count") or 0) > 0,
        "gross_exposure_metric_present": gross_metric is not None,
        "gross_exposure_cap_numeric": max_gross_value is not None,
        "gross_exposure_capped": gross_metric is not None
        and max_gross_value is not None
        and gross_metric <= max_gross_value + 1e-6,
    }
    if max_group is not None:
        max_group_value = finite_number(max_group)
        group_metric = finite_number(summary.get("max_group_exposure"))
        checks["group_exposure_metric_present"] = group_metric is not None
        checks["group_exposure_cap_numeric"] = max_group_value is not None
        checks["group_exposure_capped"] = (
            group_metric is not None and max_group_value is not None and group_metric <= max_group_value + 1e-6
        )
        checks["group_policy_declared"] = bool(contract.get("group_exposure_policy"))
    if inputs.get("stop_loss_pct") is not None or inputs.get("take_profit_pct") is not None:
        checks["event_exit_policy_declared"] = bool(contract.get("event_exit_policy"))
        checks["event_exit_fields_present"] = all(
            "exit_reason" in trade and "ambiguous_intraday_order" in trade for trade in payload.get("trades", [])
        )
    return checks


def persistence_checks(payload: dict[str, Any]) -> dict[str, bool]:
    summary = payload.get("summary", {})
    contract = payload.get("contract", {})
    return {
        "schema_ok": payload.get("schema_version") == "candidate-persistence-backtest.v1",
        "model_feature_false": contract.get("model_feature") is False,
        "no_future_rankings": contract.get("uses_future_rankings") is False,
        "trade_count_positive": int(summary.get("trade_count") or 0) > 0,
        "streak_summary_exists": bool(summary.get("by_horizon_and_streak")),
        "rank_delta_direction_summary_exists": bool(summary.get("by_rank_delta_direction")),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    portfolio_path = resolve_path(args.portfolio, "portfolio_replay_*.json")
    persistence_path = resolve_path(args.persistence, "persistence_study_*.json")
    portfolio = read_json(portfolio_path)
    persistence = read_json(persistence_path)
    checks = {
        "portfolio": portfolio_checks(portfolio),
        "persistence": persistence_checks(persistence),
    }
    all_checks = [value for group in checks.values() for value in group.values()]
    status = "OK" if all(all_checks) else "FAILED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "artifacts": {
            "portfolio": str(portfolio_path),
            "persistence": str(persistence_path),
        },
        "checks": checks,
        "summary": {
            "portfolio": portfolio.get("summary", {}),
            "persistence": {
                "trade_count": persistence.get("summary", {}).get("trade_count"),
                "streak_bucket_count": len(persistence.get("summary", {}).get("by_horizon_and_streak", {})),
                "rank_delta_bucket_count": len(persistence.get("summary", {}).get("by_rank_delta_direction", {})),
            },
        },
        "decision": {
            "production_model_change": False,
            "ranking_score_change": False,
            "ready_for_review": status == "OK",
            "next_research": [
                "用較長 ranking window 重跑 portfolio replay，觀察 max_drawdown 與 group concentration",
                "若 persistence bucket 穩定，下一步只進 shadow feature，不直接進 production score",
            ],
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    portfolio = payload["summary"]["portfolio"]
    persistence = payload["summary"]["persistence"]
    lines = [
        "# Backtest Acceptance Report",
        "",
        f"- status：{payload['status']}",
        f"- portfolio final_equity：{portfolio.get('final_equity')}",
        f"- portfolio total_return：{pct(portfolio.get('total_return'))}",
        f"- portfolio max_drawdown：{pct(portfolio.get('max_drawdown'))}",
        f"- portfolio max_gross_exposure：{pct(portfolio.get('max_gross_exposure'))}",
        f"- portfolio max_group_exposure：{pct(portfolio.get('max_group_exposure'))}",
        f"- persistence trades：{persistence.get('trade_count')}",
        f"- persistence streak buckets：{persistence.get('streak_bucket_count')}",
        "",
        "## Checks",
        "",
    ]
    for group, checks in payload["checks"].items():
        lines.append(f"### {group}")
        for key, value in checks.items():
            lines.append(f"- {key}: {'OK' if value else 'FAILED'}")
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
    output_path = Path(args.output).expanduser() if args.output else PROJECT_ROOT / "artifacts" / "backtest" / f"acceptance_report_{run_date}.json"
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path
    md_path = output_path.with_suffix(".md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    md_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": str(output_path), "markdown": str(md_path)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
