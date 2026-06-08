#!/usr/bin/env python3
"""驗證近半年出場規則決策報告。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL_SHA256 = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify exit rule half-year decision report")
    parser.add_argument("--artifact", default="artifacts/model_experiments/exit_rule_half_year_decision_report_2026-06-02.json")
    parser.add_argument("--expected-model-sha256", default=EXPECTED_MODEL_SHA256)
    parser.add_argument("--output", default="artifacts/model_experiments/exit_rule_half_year_decision_verification_latest.json")
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
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def model_sha256() -> str:
    digest = hashlib.sha256()
    with (PROJECT_ROOT / "models" / "latest_lgbm.pkl").open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    payload = read_json(artifact)
    contract = payload.get("contract") or {}
    summary = payload.get("summary") or {}
    manifest = (payload.get("inputs") or {}).get("manifest") or {}
    policies = payload.get("policies") or {}
    decision = payload.get("candidate_decision") or {}
    fixed40 = policies.get("fixed_40d") or {}
    early07 = policies.get("h40_early_tp07") or {}
    early15 = policies.get("h40_early_tp15") or {}
    stop_take = policies.get("h30_tp25_sl10") or {}
    checks = {
        "artifact_exists": bool(payload),
        "status_ok": payload.get("status") == "OK",
        "research_only": contract.get("research_only") is True,
        "default_not_allowed": contract.get("production_default_allowed") is False,
        "no_model_change": contract.get("does_not_train_model") is True and model_sha256() == args.expected_model_sha256,
        "no_ranking_change": contract.get("does_not_change_production_ranking") is True,
        "no_score_change": contract.get("does_not_change_risk_adjusted_score") is True,
        "manifest_half_year_dense": int(manifest.get("ranking_count") or 0) >= 100 and int(manifest.get("failure_count") or 0) == 0,
        "primary_candidate_expected": summary.get("primary_candidate") == "h40_early_tp15",
        "defensive_candidate_expected": summary.get("defensive_candidate") == "h30_tp25_sl10",
        "early_tp07_rejected": decision.get("reject_early_tp07") is True and "h40_early_tp07" in (summary.get("rejected") or []),
        "early_tp07_less_return_than_early15": n(early07.get("return_on_buy_cash")) < n(early15.get("return_on_buy_cash")),
        "early15_reduces_tail_risk_vs_fixed40": n(early15.get("worst_mae")) > n(fixed40.get("worst_mae"))
        and n(early15.get("p90_giveback")) < n(fixed40.get("p90_giveback")),
        "stop_take_reduces_tail_risk_vs_fixed40": n(stop_take.get("worst_mae")) > n(fixed40.get("worst_mae"))
        and n(stop_take.get("avg_mae")) > n(fixed40.get("avg_mae")),
        "fixed40_still_highest_return": n(fixed40.get("return_on_buy_cash")) > n(early15.get("return_on_buy_cash"))
        and n(fixed40.get("return_on_buy_cash")) > n(stop_take.get("return_on_buy_cash")),
    }
    failed = [key for key, value in checks.items() if not value]
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "exit-rule-half-year-decision-verification.v1",
                "status": "OK" if not failed else "FAILED",
                "artifact": repo_path(artifact),
                "checks": checks,
                "failed": failed,
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": "OK" if not failed else "FAILED", "output": repo_path(output), "failed": failed}, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
