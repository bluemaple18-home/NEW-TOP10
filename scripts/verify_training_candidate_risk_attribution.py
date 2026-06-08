#!/usr/bin/env python3
"""驗證候選模型風險歸因報告。

Verifier 只檢查研究 artifact 是否完整與安全；不做模型升版判斷。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "training-candidate-risk-attribution-verification.v1"
REPORT_SCHEMA = "training-candidate-risk-attribution.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify training candidate risk attribution")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/training_candidate_risk_attribution_verification_latest.json")
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def value_at(payload: dict[str, Any], *keys: str) -> Any:
    value: Any = payload
    for key in keys:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    headline = payload.get("headline") if isinstance(payload.get("headline"), dict) else {}
    matrix = payload.get("matrix_attribution") if isinstance(payload.get("matrix_attribution"), dict) else {}
    trade_attr = payload.get("trade_attribution") if isinstance(payload.get("trade_attribution"), dict) else {}
    hypotheses = payload.get("risk_hypotheses") if isinstance(payload.get("risk_hypotheses"), list) else []
    experiments = payload.get("next_experiments") if isinstance(payload.get("next_experiments"), list) else []
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}

    def input_exists(name: str) -> bool:
        path_text = inputs.get(name)
        resolved = resolve_path(path_text)
        return bool(resolved and resolved.exists())

    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "research_only", "ok": contract.get("research_only") is True, "value": contract},
        {"name": "model_changes_false", "ok": contract.get("model_changes") is False, "value": contract.get("model_changes")},
        {
            "name": "production_ranking_changes_false",
            "ok": contract.get("production_ranking_changes") is False,
            "value": contract.get("production_ranking_changes"),
        },
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {"name": "summary_input_exists", "ok": input_exists("summary"), "value": inputs.get("summary")},
        {"name": "candidate_matrix_exists", "ok": input_exists("candidate_matrix"), "value": inputs.get("candidate_matrix")},
        {"name": "production_matrix_exists", "ok": input_exists("production_matrix"), "value": inputs.get("production_matrix")},
        {
            "name": "return_delta_present",
            "ok": value_at(headline, "portfolio_40d_total_return", "delta") is not None
            and value_at(headline, "fixed_share_default_return_on_buy_cash", "delta") is not None,
            "value": headline,
        },
        {
            "name": "drawdown_delta_present",
            "ok": value_at(headline, "portfolio_40d_max_drawdown", "delta") is not None,
            "value": headline.get("portfolio_40d_max_drawdown"),
        },
        {
            "name": "sector_attribution_present",
            "ok": value_at(matrix, "sector_concentration_fixed_40d", "max_sector_buy_share_delta") is not None,
            "value": matrix.get("sector_concentration_fixed_40d"),
        },
        {
            "name": "rank_attribution_present",
            "ok": bool(matrix.get("candidate_top_rank_policies")),
            "value": len(matrix.get("candidate_top_rank_policies") or []),
        },
        {
            "name": "month_and_rank_trade_attribution_present",
            "ok": bool(trade_attr.get("by_month")) and bool(trade_attr.get("by_rank")),
            "value": {"months": len(trade_attr.get("by_month") or []), "ranks": len(trade_attr.get("by_rank") or [])},
        },
        {
            "name": "risk_hypotheses_minimum",
            "ok": len(hypotheses) >= 3,
            "value": len(hypotheses),
        },
        {
            "name": "next_experiments_minimum",
            "ok": len(experiments) >= 3,
            "value": len(experiments),
        },
        {
            "name": "decision_safe",
            "ok": value_at(payload, "decision", "promotion_ready") is False,
            "value": payload.get("decision"),
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "risk_hypothesis_count": len(hypotheses),
            "next_experiment_count": len(experiments),
            "decision": value_at(payload, "decision", "status"),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    if artifact is None or not artifact.exists():
        raise FileNotFoundError(f"artifact not found: {args.artifact}")
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
