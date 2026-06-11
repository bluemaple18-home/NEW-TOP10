#!/usr/bin/env python3
"""驗證 strategy composition replay artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "strategy-composition-replay-verification.v1"
REPORT_SCHEMA = "strategy-composition-replay.v1"

REQUIRED_VARIANTS = {
    "production_baseline",
    "candidate_trail10_global",
    "candidate_trail10_big_bull_only",
    "candidate_trail10_regime_conditional",
}
ALLOWED_DECISIONS = {
    "ADOPT_CONDITIONAL_SWITCH",
    "KEEP_SHADOW_MONITOR",
    "REJECT_COMPOSITION",
    "NEEDS_MORE_DATA_CONTRACT",
}
REQUIRED_REGIMES = {
    "ALL",
    "BIG_BULL",
    "HIGH_CHOPPY_CONTEXT",
    "NON_BIG_BULL_NON_HIGH_CHOPPY",
}
FORBIDDEN_COMPONENT_STATUSES = {"REFERENCE_AVAILABLE", "DIAGNOSTIC_ONLY", "REJECTED", "DATA_UNAVAILABLE"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify strategy composition replay")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/strategy_composition_replay_verification_latest.json")
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


def n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def evidence_exists(items: list[str]) -> bool:
    for item in items:
        path = resolve_path(item)
        if path is None or not path.exists():
            return False
    return True


def candidate_components_are_allowed(variants: dict[str, Any]) -> bool:
    for name, variant in variants.items():
        if name == "production_baseline":
            continue
        statuses = variant.get("component_statuses") if isinstance(variant.get("component_statuses"), dict) else {}
        for component_id, status in statuses.items():
            if component_id in {"candidate_ranking", "trail10", "market_regime_history"}:
                continue
            if str(status) in FORBIDDEN_COMPONENT_STATUSES:
                return False
    return True


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    variants = payload.get("variants") if isinstance(payload.get("variants"), dict) else {}
    performance = payload.get("performance") if isinstance(payload.get("performance"), dict) else {}
    windows = payload.get("windows") if isinstance(payload.get("windows"), dict) else {}
    regimes = payload.get("regime_slices") if isinstance(payload.get("regime_slices"), dict) else {}
    variant_ids = set(variants)
    artifact_paths = [str(row.get("artifact")) for row in variants.values() if isinstance(row, dict)]
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {
            "name": "contract_no_production_mutation",
            "ok": contract.get("research_only") is True
            and contract.get("no_new_data_fetch") is True
            and contract.get("no_model_training") is True
            and contract.get("changes_production_ranking") is False
            and contract.get("changes_risk_adjusted_score") is False
            and contract.get("changes_clawd_message") is False
            and contract.get("promotion_ready") is False
            and contract.get("production_switch_ready") is False,
            "value": contract,
        },
        {
            "name": "no_future_regime_data",
            "ok": contract.get("no_future_regime_data") is True,
            "value": contract.get("no_future_regime_data"),
        },
        {
            "name": "required_variants",
            "ok": REQUIRED_VARIANTS.issubset(variant_ids),
            "value": sorted(REQUIRED_VARIANTS - variant_ids),
        },
        {
            "name": "variant_artifacts_exist",
            "ok": evidence_exists(artifact_paths),
            "value": artifact_paths,
        },
        {
            "name": "decision_allowed",
            "ok": payload.get("decision") in ALLOWED_DECISIONS,
            "value": payload.get("decision"),
        },
        {
            "name": "candidate_components_allowed",
            "ok": candidate_components_are_allowed(variants),
            "value": {name: row.get("component_statuses") for name, row in variants.items() if isinstance(row, dict)},
        },
        {
            "name": "overlap_first_not_used",
            "ok": all("overlap_first" not in json.dumps(row, ensure_ascii=False) for row in variants.values()),
            "value": variants,
        },
        {
            "name": "performance_metrics_present",
            "ok": all(
                name in performance
                and all(key in performance[name] for key in ["total_return", "max_drawdown", "risk_adjusted_return", "turnover", "hit_rate", "average_holding_days", "cash_utilization", "sector_concentration"])
                for name in REQUIRED_VARIANTS
            ),
            "value": sorted(performance),
        },
        {
            "name": "window_metrics_present",
            "ok": all(
                name in windows and {"long_window", "recent_100", "recent_6m"}.issubset(set(windows[name]))
                for name in REQUIRED_VARIANTS
            ),
            "value": {name: sorted(rows) for name, rows in windows.items() if isinstance(rows, dict)},
        },
        {
            "name": "regime_slices_present",
            "ok": all(
                name in regimes and REQUIRED_REGIMES.issubset(set(regimes[name]))
                for name in REQUIRED_VARIANTS
            ),
            "value": {name: sorted(rows) for name, rows in regimes.items() if isinstance(rows, dict)},
        },
        {
            "name": "recent_underperformance_blocked",
            "ok": not (
                n(((windows.get("candidate_trail10_global") or {}).get("recent_100") or {}).get("return_delta_vs_production")) < 0
                or n(((windows.get("candidate_trail10_global") or {}).get("recent_6m") or {}).get("return_delta_vs_production")) < 0
            )
            or payload.get("decision") != "ADOPT_CONDITIONAL_SWITCH",
            "value": {
                "recent_100": ((windows.get("candidate_trail10_global") or {}).get("recent_100") or {}).get("return_delta_vs_production"),
                "recent_6m": ((windows.get("candidate_trail10_global") or {}).get("recent_6m") or {}).get("return_delta_vs_production"),
                "decision": payload.get("decision"),
            },
        },
        {
            "name": "required_schema_fields",
            "ok": all(key in payload for key in ["contract", "inputs", "variants", "windows", "regime_slices", "capital_policy", "entry_exit_policy", "performance", "decision", "blocked_reasons", "next_recommended_action"]),
            "value": sorted(payload),
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
            "decision": payload.get("decision"),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    if artifact is None or not artifact.exists():
        raise FileNotFoundError(f"找不到 artifact：{args.artifact}")
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
