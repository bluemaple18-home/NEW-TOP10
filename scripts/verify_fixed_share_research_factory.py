#!/usr/bin/env python3
"""驗證固定股數研究工廠 artifacts。

這個 verifier 只檢查研究結果的結構、邊界與可自動化條件；它不判定模型可升版，
也不取代 sealed OOS / replay / rollback / promotion gate。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "fixed-share-research-factory-verification.v1"
MATRIX_SCHEMA = "fixed-share-hypothesis-matrix.v1"
REPORT_SCHEMA = "fixed-share-research-factory-report.v1"

MATRIX_INPUTS = {
    "production_half_year": "artifacts/backtest/fixed_share_hypothesis_matrix_production_half_year_{date}.json",
    "a1_half_year": "artifacts/backtest/fixed_share_hypothesis_matrix_sector_context_top7_fill3_half_year_{date}.json",
    "production_extended": "artifacts/backtest/fixed_share_hypothesis_matrix_production_extended_{date}.json",
    "a1_extended": "artifacts/backtest/fixed_share_hypothesis_matrix_sector_context_top7_fill3_extended_{date}.json",
}
REPORT_PATH = "artifacts/model_experiments/fixed_share_research_factory_report_{date}.json"

REQUIRED_MATRIX_SECTIONS = {
    "exit_policy",
    "rank_policy",
    "persistence_policy",
    "regime_policy",
    "sector_policy",
    "sizing_policy",
    "sector_concentration",
}
REQUIRED_EXIT_POLICIES = {
    "fixed_30d",
    "fixed_40d",
    "h40_early_tp07",
    "h40_early_tp15",
}
REQUIRED_RISK_FIELDS = {
    "avg_mae",
    "worst_mae",
    "avg_mfe",
    "avg_giveback",
    "p90_giveback",
}
REQUIRED_DECISIONS = {"EXIT-01", "EXIT-02", "A1-01", "PAGE-01"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify fixed-share research factory artifacts")
    parser.add_argument("--date", default=date.today().isoformat())
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


def add_error(errors: list[dict[str, Any]], code: str, path: Path, detail: Any = None) -> None:
    errors.append({"code": code, "path": repo_path(path), "detail": detail})


def contract_is_research_only(payload: dict[str, Any]) -> bool:
    contract = payload.get("contract", {})
    return (
        contract.get("research_only") is True
        and contract.get("model_changes") is False
        and contract.get("production_changes") is False
    )


def verify_matrix(label: str, path: Path, errors: list[dict[str, Any]]) -> dict[str, Any]:
    if not path.exists():
        add_error(errors, "MISSING_MATRIX", path, label)
        return {"label": label, "path": repo_path(path), "status": "FAILED"}
    payload = read_json(path)
    if payload.get("schema_version") != MATRIX_SCHEMA:
        add_error(errors, "BAD_MATRIX_SCHEMA", path, payload.get("schema_version"))
    if not contract_is_research_only(payload):
        add_error(errors, "MATRIX_CONTRACT_NOT_RESEARCH_ONLY", path, payload.get("contract"))

    matrix = payload.get("matrix", {})
    missing_sections = sorted(REQUIRED_MATRIX_SECTIONS - set(matrix))
    if missing_sections:
        add_error(errors, "MISSING_MATRIX_SECTIONS", path, missing_sections)

    exit_policy = matrix.get("exit_policy", {})
    missing_policies = sorted(REQUIRED_EXIT_POLICIES - set(exit_policy))
    if missing_policies:
        add_error(errors, "MISSING_EXIT_POLICIES", path, missing_policies)
    for policy in sorted(REQUIRED_EXIT_POLICIES & set(exit_policy)):
        item = exit_policy.get(policy, {})
        if int(item.get("trade_count") or 0) <= 0:
            add_error(errors, "EMPTY_EXIT_POLICY", path, policy)
        missing_risk = sorted(REQUIRED_RISK_FIELDS - set(item))
        if missing_risk:
            add_error(errors, "MISSING_RISK_FIELDS", path, {"policy": policy, "fields": missing_risk})

    if not payload.get("summary", {}).get("sizing_policy_top"):
        add_error(errors, "EMPTY_SIZING_POLICY_TOP", path)
    concentration = matrix.get("sector_concentration", {})
    for policy in ("fixed_30d", "fixed_40d"):
        item = concentration.get(policy)
        if not item:
            add_error(errors, "MISSING_SECTOR_CONCENTRATION", path, policy)
            continue
        if item.get("max_sector_buy_share") is None:
            add_error(errors, "MISSING_MAX_SECTOR_BUY_SHARE", path, policy)

    return {
        "label": label,
        "path": repo_path(path),
        "status": "OK",
        "base_trade_rows": payload.get("summary", {}).get("base_trade_rows"),
        "exit_policy_count": len(exit_policy),
    }


def verify_report(path: Path, errors: list[dict[str, Any]]) -> dict[str, Any]:
    if not path.exists():
        add_error(errors, "MISSING_REPORT", path)
        return {"path": repo_path(path), "status": "FAILED"}
    payload = read_json(path)
    if payload.get("schema_version") != REPORT_SCHEMA:
        add_error(errors, "BAD_REPORT_SCHEMA", path, payload.get("schema_version"))
    contract = payload.get("contract", {})
    if not contract_is_research_only(payload) or contract.get("promotion_ready") is not False:
        add_error(errors, "REPORT_CONTRACT_NOT_BLOCKED_RESEARCH_ONLY", path, contract)

    decisions = payload.get("summary", {}).get("decisions", [])
    ids = {str(item.get("id")) for item in decisions}
    missing_decisions = sorted(REQUIRED_DECISIONS - ids)
    if missing_decisions:
        add_error(errors, "MISSING_DECISIONS", path, missing_decisions)
    for item in decisions:
        not_allowed = set(item.get("not_allowed") or [])
        if item.get("status") in {"PROMOTION_READY", "PRODUCTION_READY"}:
            add_error(errors, "FORBIDDEN_DECISION_STATUS", path, item)
        if "A1" in str(item.get("id")) and not {"risk_adjusted_score change", "models/latest_lgbm.pkl change"} <= not_allowed:
            add_error(errors, "A1_DECISION_LACKS_PRODUCTION_GUARD", path, item)

    completion = payload.get("summary", {}).get("completion_estimate")
    if "100%" not in str(completion):
        add_error(errors, "REPORT_NOT_MARKED_RESEARCH_FACTORY_COMPLETE", path, completion)

    return {
        "path": repo_path(path),
        "status": "OK",
        "completion_estimate": completion,
        "decision_count": len(decisions),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    errors: list[dict[str, Any]] = []
    matrix_paths = {
        label: resolve_path(template.format(date=args.date))
        for label, template in MATRIX_INPUTS.items()
    }
    matrix_results = {
        label: verify_matrix(label, path, errors)
        for label, path in matrix_paths.items()
    }
    report_result = verify_report(resolve_path(REPORT_PATH.format(date=args.date)), errors)
    status = "OK" if not errors else "FAILED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "contract": {
            "verifier_only": True,
            "model_changes": False,
            "production_changes": False,
            "promotion_ready": False,
            "does_not_replace": ["sealed_oos", "replay", "rollback", "promotion_gate"],
        },
        "matrix_results": matrix_results,
        "report_result": report_result,
        "errors": errors,
    }


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output_path = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / "fixed_share_research_factory_verification_latest.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output_path), "errors": len(payload["errors"])}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
