#!/usr/bin/env python3
"""驗證 production tactics replay artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "production-tactics-replay-verification.v1"
REPORT_SCHEMA = "production-tactics-replay.v1"
REQUIRED_VARIANTS = {
    "production_current_baseline",
    "production_trail10_exit",
    "production_hard_stop_then_trail10",
    "production_partial_take_profit_runner",
    "production_warning_only_no_forced_sell",
}
REQUIRED_FIELDS = {
    "schema_version",
    "contract",
    "inputs",
    "registry_update_proposal",
    "variants",
    "capital_policy",
    "entry_exit_policy",
    "warning_policy",
    "windows",
    "performance",
    "decision",
    "blocked_reasons",
    "next_recommended_action",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify production tactics replay")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/production_tactics_replay_verification_latest.json")
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


def paths_exist(paths: list[str]) -> bool:
    return all((resolve_path(path) or Path("__missing__")).exists() for path in paths)


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    variants = payload.get("variants") if isinstance(payload.get("variants"), dict) else {}
    performance = payload.get("performance") if isinstance(payload.get("performance"), dict) else {}
    warning = payload.get("warning_policy") if isinstance(payload.get("warning_policy"), dict) else {}
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "required_fields", "ok": REQUIRED_FIELDS.issubset(set(payload)), "value": sorted(REQUIRED_FIELDS - set(payload))},
        {
            "name": "safe_contract",
            "ok": contract.get("research_only") is True
            and contract.get("production_ranking_source_unchanged") is True
            and contract.get("no_model_training") is True
            and contract.get("changes_model") is False
            and contract.get("changes_production_ranking_score") is False
            and contract.get("changes_clawd_live_send") is False
            and contract.get("finite_capital") is True
            and contract.get("odd_lot") is True
            and contract.get("no_fixed_100_share_unlimited_capital_conclusion") is True
            and contract.get("promotion_ready") is False
            and contract.get("production_switch_ready") is False,
            "value": contract,
        },
        {"name": "required_variants", "ok": REQUIRED_VARIANTS.issubset(set(variants)), "value": sorted(REQUIRED_VARIANTS - set(variants))},
        {
            "name": "production_ranking_only",
            "ok": all((row.get("ranking_source") == "production_ranking") for row in variants.values() if isinstance(row, dict)),
            "value": {key: row.get("ranking_source") for key, row in variants.items() if isinstance(row, dict)},
        },
        {
            "name": "variant_artifacts_exist",
            "ok": paths_exist([str(row.get("artifact")) for row in variants.values() if isinstance(row, dict)]),
            "value": {key: row.get("artifact") for key, row in variants.items() if isinstance(row, dict)},
        },
        {
            "name": "performance_metrics_present",
            "ok": all(
                key in performance
                and all(metric in performance[key] for metric in ["total_return", "max_drawdown", "risk_adjusted_return", "turnover", "cash_utilization", "average_holding_days"])
                for key in REQUIRED_VARIANTS
            ),
            "value": sorted(performance),
        },
        {
            "name": "warning_lookbacks_present",
            "ok": {"lookback_5", "lookback_10", "lookback_20"}.issubset(set(warning)),
            "value": sorted(warning),
        },
        {
            "name": "warning_no_forced_sell",
            "ok": all((row.get("contract") or {}).get("does_not_force_sell") is True for row in warning.values() if isinstance(row, dict)),
            "value": {key: row.get("contract") for key, row in warning.items() if isinstance(row, dict)},
        },
        {
            "name": "warning_no_personal_sell_terms",
            "ok": all(
                "賣出" in ((row.get("contract") or {}).get("blocked_message_terms") or [])
                and (row.get("contract") or {}).get("non_personal_warning_only") is True
                for row in warning.values()
                if isinstance(row, dict)
            ),
            "value": {key: row.get("contract") for key, row in warning.items() if isinstance(row, dict)},
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(path),
        "summary": {"check_count": len(checks), "failed_count": len(failed), "decision": payload.get("decision")},
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
