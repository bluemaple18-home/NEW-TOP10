#!/usr/bin/env python3
"""驗證 strategy composition isolation artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "strategy-composition-isolation-verification.v1"
REPORT_SCHEMA = "strategy-composition-isolation.v1"
ALLOWED_DECISIONS = {
    "RETAIN_CANDIDATE_FOR_PROMOTION_REVIEW",
    "KEEP_SHADOW_MONITOR",
    "NEEDS_MORE_DATA_CONTRACT",
}
REQUIRED_REGIMES = {"BIG_BULL", "HIGH_CHOPPY_CONTEXT", "NON_BIG_BULL_NON_HIGH_CHOPPY"}
REQUIRED_ISOLATION = {"trail10_same_exit", "production_proxy_same_exit"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify strategy composition isolation")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/strategy_composition_isolation_verification_latest.json")
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
    isolation = payload.get("same_exit_ranking_isolation") if isinstance(payload.get("same_exit_ranking_isolation"), dict) else {}
    regimes = payload.get("regime_normalization") if isinstance(payload.get("regime_normalization"), dict) else {}
    replay_artifacts = payload.get("replay_artifacts") if isinstance(payload.get("replay_artifacts"), dict) else {}
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {
            "name": "contract_safe",
            "ok": contract.get("research_only") is True
            and contract.get("same_exit_ranking_isolation") is True
            and contract.get("regime_gated_equity_normalization") is True
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
            "name": "decision_allowed",
            "ok": payload.get("decision") in ALLOWED_DECISIONS,
            "value": payload.get("decision"),
        },
        {
            "name": "same_exit_pairs_present",
            "ok": REQUIRED_ISOLATION.issubset(set(isolation)),
            "value": sorted(set(isolation)),
        },
        {
            "name": "ranking_delta_present",
            "ok": all(
                key in isolation
                and isinstance(isolation[key].get("ranking_delta"), dict)
                and "return_delta" in isolation[key]["ranking_delta"]
                and "risk_adjusted_delta" in isolation[key]["ranking_delta"]
                for key in REQUIRED_ISOLATION
            ),
            "value": isolation,
        },
        {
            "name": "regime_rows_present",
            "ok": REQUIRED_REGIMES.issubset(set(regimes)),
            "value": sorted(set(regimes)),
        },
        {
            "name": "normalization_metrics_present",
            "ok": all(
                family in regimes
                and isinstance(regimes[family].get("active_day"), dict)
                and isinstance(regimes[family].get("trade_level"), dict)
                and "exposure_adjusted_delta" in regimes[family]["active_day"]
                and "sample_status" in regimes[family]["trade_level"]
                for family in REQUIRED_REGIMES
            ),
            "value": regimes,
        },
        {
            "name": "replay_artifacts_exist",
            "ok": paths_exist([str(path) for path in replay_artifacts.values()]),
            "value": replay_artifacts,
        },
        {
            "name": "no_adopt_with_low_sample_high_choppy",
            "ok": not (
                ((regimes.get("HIGH_CHOPPY_CONTEXT") or {}).get("trade_level") or {}).get("sample_status") == "LOW_SAMPLE"
                and payload.get("decision") == "RETAIN_CANDIDATE_FOR_PROMOTION_REVIEW"
            ),
            "value": ((regimes.get("HIGH_CHOPPY_CONTEXT") or {}).get("trade_level") or {}).get("sample_status"),
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
