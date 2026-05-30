#!/usr/bin/env python3
"""建立 portfolio risk overlay 的 promotion review packet。

此腳本只整理 evidence，不修改 production ranking 或設定。
正式接入 RankingPolicy / automation 前仍需要人工 review。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "portfolio-overlay-promotion-review.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build portfolio risk overlay promotion review packet")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--result-report", default=None)
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


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {"_missing": True, "_path": repo_path(path)}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def decision_from_report(report: dict[str, Any]) -> dict[str, Any]:
    for item in report.get("decisions", []):
        if item.get("experiment_id") == "model_exp_portfolio_risk_overlay_only":
            return item
    return {}


def build_packet(args: argparse.Namespace) -> dict[str, Any]:
    report_path = resolve_path(args.result_report) or OUTPUT_DIR / f"model_exp_result_report_{args.date}.json"
    report = load_json(report_path)
    decision = decision_from_report(report)
    metrics = decision.get("metrics", {})
    extended = metrics.get("extended", {})
    recent_ok = all(
        (safe_float(metrics.get(key)) or 0) > 0
        for key in ["delta_total_return", "delta_max_drawdown", "delta_score"]
    )
    extended_ok = extended.get("passed") is True
    review_ready = decision.get("status") == "PASS_TO_PROMOTION_REVIEW_QUEUE" and recent_ok and extended_ok
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "READY_FOR_HUMAN_REVIEW" if review_ready else "NOT_READY",
        "contract": {
            "review_packet_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
            "requires_manual_review_before_code_change": True,
        },
        "inputs": {
            "result_report": repo_path(report_path),
        },
        "summary": {
            "experiment_status": decision.get("status"),
            "recent_passed": recent_ok,
            "extended_passed": extended_ok,
            "recent_delta_total_return": metrics.get("delta_total_return"),
            "recent_delta_max_drawdown": metrics.get("delta_max_drawdown"),
            "recent_delta_score": metrics.get("delta_score"),
            "extended_delta_total_return": extended.get("delta_total_return"),
            "extended_delta_max_drawdown": extended.get("delta_max_drawdown"),
            "extended_delta_score": extended.get("delta_score"),
        },
        "candidate_change": {
            "scope": "post-ranking portfolio overlay only",
            "not_a_model_feature": True,
            "do_not_retrain_for_this_change": True,
            "expected_code_owner_area": [
                "app/trading/portfolio_policy.py",
                "app/trading/ranking_policy.py",
                "scripts/run_automation.py",
            ],
            "minimum_next_tests_before_promotion": [
                "dedicated review card for exact production integration diff",
                "daily dry-run comparing Top10 rows before/after overlay",
                "portfolio replay using production candidate integration path",
                "rollback switch or config flag default-off",
            ],
        },
        "decision": decision,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Portfolio Risk Overlay Promotion Review",
        "",
        f"- status：`{payload['status']}`",
        f"- experiment_status：`{summary['experiment_status']}`",
        f"- recent_delta_total_return：`{summary['recent_delta_total_return']}`",
        f"- extended_delta_total_return：`{summary['extended_delta_total_return']}`",
        f"- production_promotion_allowed：`{payload['contract']['production_promotion_allowed']}`",
        "",
        "## Required Before Promotion",
        "",
    ]
    for item in payload["candidate_change"]["minimum_next_tests_before_promotion"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_packet(args)
    output = resolve_path(args.output) or OUTPUT_DIR / f"portfolio_overlay_promotion_review_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] in {"READY_FOR_HUMAN_REVIEW", "NOT_READY"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
