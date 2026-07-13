#!/usr/bin/env python3
"""以具名 profile 驗證 exit-rule validation suite。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL_SHA256 = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"
PROFILES = ("half_year_decision", "portfolio_level", "rolling_regime")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify exit rule validation suite")
    parser.add_argument(
        "--artifact",
        default="artifacts/model_experiments/exit_rule_validation_suite_2026-06-02.json",
    )
    parser.add_argument("--profile", choices=("all", *PROFILES), default="all")
    parser.add_argument("--expected-model-sha256", default=EXPECTED_MODEL_SHA256)
    parser.add_argument(
        "--output",
        default="artifacts/model_experiments/exit_rule_validation_suite_verification_latest.json",
    )
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


def verification_result(
    schema_version: str,
    artifact: Path,
    checks: dict[str, bool],
) -> dict[str, Any]:
    failed = [key for key, value in checks.items() if not value]
    return {
        "schema_version": schema_version,
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(artifact),
        "checks": checks,
        "failed": failed,
    }


def verify_half_year(
    payload: dict[str, Any],
    artifact: Path,
    expected_model_sha256: str,
    actual_model_sha256: str,
) -> dict[str, Any]:
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
        "no_model_change": contract.get("does_not_train_model") is True
        and actual_model_sha256 == expected_model_sha256,
        "no_ranking_change": contract.get("does_not_change_production_ranking") is True,
        "no_score_change": contract.get("does_not_change_risk_adjusted_score") is True,
        "manifest_half_year_dense": int(manifest.get("ranking_count") or 0) >= 100
        and int(manifest.get("failure_count") or 0) == 0,
        "primary_candidate_expected": summary.get("primary_candidate") == "h40_early_tp15",
        "defensive_candidate_expected": summary.get("defensive_candidate") == "h30_tp25_sl10",
        "early_tp07_rejected": decision.get("reject_early_tp07") is True
        and "h40_early_tp07" in (summary.get("rejected") or []),
        "early_tp07_less_return_than_early15": n(early07.get("return_on_buy_cash"))
        < n(early15.get("return_on_buy_cash")),
        "early15_reduces_tail_risk_vs_fixed40": n(early15.get("worst_mae")) > n(fixed40.get("worst_mae"))
        and n(early15.get("p90_giveback")) < n(fixed40.get("p90_giveback")),
        "stop_take_reduces_tail_risk_vs_fixed40": n(stop_take.get("worst_mae")) > n(fixed40.get("worst_mae"))
        and n(stop_take.get("avg_mae")) > n(fixed40.get("avg_mae")),
        "fixed40_still_highest_return": n(fixed40.get("return_on_buy_cash"))
        > n(early15.get("return_on_buy_cash"))
        and n(fixed40.get("return_on_buy_cash")) > n(stop_take.get("return_on_buy_cash")),
    }
    return verification_result(
        "exit-rule-half-year-decision-verification.v1",
        artifact,
        checks,
    )


def verify_portfolio(
    payload: dict[str, Any],
    artifact: Path,
    expected_model_sha256: str,
    actual_model_sha256: str,
) -> dict[str, Any]:
    contract = payload.get("contract") or {}
    summary = payload.get("summary") or {}
    rows = payload.get("rows") or {}
    comps = payload.get("comparisons_vs_h40_fixed65") or {}
    fixed = rows.get("h40_fixed65") or {}
    tp15 = rows.get("h40_tp15_fixed65") or {}
    stop_take = rows.get("h30_tp25_sl10_fixed65") or {}
    checks = {
        "artifact_exists": bool(payload),
        "status_ok": payload.get("status") == "OK",
        "research_only": contract.get("research_only") is True,
        "default_not_allowed": contract.get("production_default_allowed") is False,
        "no_model_change": contract.get("does_not_train_model") is True
        and actual_model_sha256 == expected_model_sha256,
        "no_ranking_change": contract.get("does_not_change_production_ranking") is True,
        "primary_candidate": summary.get("primary_shadow_candidate") == "h40_tp15_fixed65",
        "defensive_candidate": summary.get("defensive_shadow_candidate") == "h30_tp25_sl10_fixed65",
        "fixed_highest_return": n(fixed.get("total_return")) > n(tp15.get("total_return"))
        and n(fixed.get("total_return")) > n(stop_take.get("total_return")),
        "tp15_drawdown_improves": n((comps.get("h40_tp15_fixed65") or {}).get("max_drawdown_delta")) > 0,
        "tp15_win_rate_improves": n((comps.get("h40_tp15_fixed65") or {}).get("win_rate_delta")) > 0,
        "stop_take_drawdown_improves": n(
            (comps.get("h30_tp25_sl10_fixed65") or {}).get("max_drawdown_delta")
        )
        > 0,
        "event_exits_present": int((tp15.get("exit_counts") or {}).get("take_profit") or 0) > 0
        and int((stop_take.get("exit_counts") or {}).get("stop_loss") or 0) > 0,
    }
    return verification_result(
        "exit-rule-portfolio-level-verification.v1",
        artifact,
        checks,
    )


def verify_rolling(
    payload: dict[str, Any],
    artifact: Path,
    expected_model_sha256: str,
    actual_model_sha256: str,
) -> dict[str, Any]:
    contract = payload.get("contract") or {}
    rules = payload.get("contextual_rules") or {}
    rolling = payload.get("rolling_vs_h40_fixed65") or {}
    regime = payload.get("regime_vs_h40_fixed65") or {}
    high_choppy = {label: (body or {}).get("HIGH_CHOPPY_CONTEXT") or {} for label, body in regime.items()}
    risk_off = {label: (body or {}).get("RISK_OFF") or {} for label, body in regime.items()}
    checks = {
        "artifact_exists": bool(payload),
        "status_ok": payload.get("status") == "OK",
        "research_only": contract.get("research_only") is True,
        "default_not_allowed": contract.get("production_default_allowed") is False,
        "no_model_change": contract.get("does_not_train_model") is True
        and actual_model_sha256 == expected_model_sha256,
        "no_ranking_change": contract.get("does_not_change_production_ranking") is True,
        "no_score_change": contract.get("does_not_change_risk_adjusted_score") is True,
        "big_bull_prefers_fixed": rules.get("big_bull_preference") == "h40_fixed65",
        "high_choppy_prefers_stop_take": rules.get("high_choppy_preference")
        == "h30_tp25_sl10_fixed65",
        "risk_off_prefers_tp15": rules.get("risk_off_preference") == "h40_tp15_fixed65",
        "tp15_rolling_drawdown_stable": n(
            (rolling.get("h40_tp15_fixed65") or {}).get("20d", {}).get("drawdown_improves_rate")
        )
        >= 0.8
        and n((rolling.get("h40_tp15_fixed65") or {}).get("40d", {}).get("drawdown_improves_rate"))
        >= 0.8,
        "gross55_tp15_drawdown_always_improves": n(
            (rolling.get("h40_tp15_gross55") or {}).get("20d", {}).get("drawdown_improves_rate")
        )
        >= 0.95
        and n((rolling.get("h40_tp15_gross55") or {}).get("40d", {}).get("drawdown_improves_rate"))
        >= 0.95,
        "high_choppy_sample_present": int(
            (high_choppy.get("h30_tp25_sl10_fixed65") or {}).get("daily_count") or 0
        )
        >= 30,
        "high_choppy_stop_take_better_than_tp15": n(
            (high_choppy.get("h30_tp25_sl10_fixed65") or {}).get("return_delta")
        )
        > n((high_choppy.get("h40_tp15_fixed65") or {}).get("return_delta"))
        and n((high_choppy.get("h30_tp25_sl10_fixed65") or {}).get("drawdown_delta"))
        > n((high_choppy.get("h40_tp15_fixed65") or {}).get("drawdown_delta")),
        "risk_off_tp15_drawdown_material": n(
            (risk_off.get("h40_tp15_fixed65") or {}).get("drawdown_delta")
        )
        > 0.02,
    }
    return verification_result(
        "exit-rule-rolling-regime-verification.v1",
        artifact,
        checks,
    )


PROFILE_VERIFIERS: dict[str, Callable[[dict[str, Any], Path, str, str], dict[str, Any]]] = {
    "half_year_decision": verify_half_year,
    "portfolio_level": verify_portfolio,
    "rolling_regime": verify_rolling,
}


def verify_profile(
    profile: str,
    payload: dict[str, Any],
    *,
    artifact: Path,
    expected_model_sha256: str,
    actual_model_sha256: str,
) -> dict[str, Any]:
    try:
        verifier = PROFILE_VERIFIERS[profile]
    except KeyError as error:
        raise ValueError(f"unsupported exit-rule profile: {profile}") from error
    return verifier(payload, artifact, expected_model_sha256, actual_model_sha256)


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    payload = read_json(artifact)
    sections = payload.get("sections") or {}
    selected = PROFILES if args.profile == "all" else (args.profile,)
    actual_hash = model_sha256()
    profiles = {
        profile: verify_profile(
            profile,
            sections.get(profile) or {},
            artifact=artifact,
            expected_model_sha256=args.expected_model_sha256,
            actual_model_sha256=actual_hash,
        )
        for profile in selected
    }
    failed_profiles = [profile for profile, result in profiles.items() if result["status"] != "OK"]
    result = {
        "schema_version": "exit-rule-validation-suite-verification.v1",
        "status": "OK" if not failed_profiles else "FAILED",
        "artifact": repo_path(artifact),
        "profiles": profiles,
        "failed_profiles": failed_profiles,
    }
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(
        json.dumps(
            {"status": result["status"], "output": repo_path(output), "failed_profiles": failed_profiles},
            ensure_ascii=False,
        )
    )
    return 0 if not failed_profiles else 1


if __name__ == "__main__":
    raise SystemExit(main())
