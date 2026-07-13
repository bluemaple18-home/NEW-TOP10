#!/usr/bin/env python3
"""驗證 odd-lot research 報告的具名 profile suite。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]

PROFILE_SCHEMAS = {
    "candidate_comparison": (
        "odd-lot-candidate-comparison-report-verification.v1",
        "odd-lot-candidate-comparison-report.v1",
    ),
    "exit_horizon": (
        "odd-lot-exit-horizon-sensitivity-report-verification.v1",
        "odd-lot-exit-horizon-sensitivity-report.v1",
    ),
    "exit_strategy": (
        "odd-lot-exit-strategy-report-verification.v1",
        "odd-lot-exit-strategy-report.v1",
    ),
    "exposure_sensitivity": (
        "odd-lot-exposure-sensitivity-report-verification.v1",
        "odd-lot-exposure-sensitivity-report.v1",
    ),
    "regime_sensitivity": (
        "odd-lot-regime-sensitivity-report-verification.v1",
        "odd-lot-regime-sensitivity-report.v1",
    ),
    "regime_throttle": (
        "odd-lot-regime-throttle-report-verification.v1",
        "odd-lot-regime-throttle-report.v1",
    ),
}
DEFAULT_OUTPUTS = {
    "candidate_comparison": "artifacts/model_experiments/odd_lot_candidate_comparison_report_verification_latest.json",
    "exit_horizon": "artifacts/model_experiments/odd_lot_exit_horizon_sensitivity_report_verification_latest.json",
    "exit_strategy": "artifacts/model_experiments/odd_lot_exit_strategy_report_verification_latest.json",
    "exposure_sensitivity": "artifacts/model_experiments/odd_lot_exposure_sensitivity_report_verification_latest.json",
    "regime_sensitivity": "artifacts/model_experiments/odd_lot_regime_sensitivity_report_verification_latest.json",
    "regime_throttle": "artifacts/model_experiments/odd_lot_regime_throttle_report_verification_latest.json",
}
REQUIRED_HORIZONS = {20, 40, 60}
REQUIRED_HORIZON_KINDS = {"candidate_baseline", "candidate_exit", "production_exit"}
REQUIRED_EXIT_VARIANTS = {
    "production_baseline",
    "production_ptp25_third",
    "candidate_baseline",
    "candidate_ptp25_third",
    "candidate_ptp25_half",
}
REQUIRED_REGIMES = {"BIG_BULL", "HIGH_CHOPPY_CONTEXT", "OTHER"}
REQUIRED_THROTTLE_VARIANTS = {"baseline", "hc45", "hc55", "hc65"}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify odd-lot research report suite")
    parser.add_argument("--profile", required=True, choices=sorted(PROFILE_SCHEMAS))
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default=None)
    return parser.parse_args(argv)


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


def finish_payload(
    profile: str,
    path: Path,
    rows: list[Any],
    checks: list[dict[str, Any]],
    summary: dict[str, Any],
) -> dict[str, Any]:
    schema_version, _ = PROFILE_SCHEMAS[profile]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": schema_version,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "row_count": len(rows),
            **summary,
        },
        "checks": checks,
    }


def build_candidate_comparison(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    _, report_schema = PROFILE_SCHEMAS["candidate_comparison"]
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    capital_levels = set((payload.get("inputs") or {}).get("capital_levels") or [])
    variants = {row.get("variant") for row in rows}
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == report_schema, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "research_only", "ok": contract.get("research_only") is True, "value": contract},
        {"name": "fixed_capital_odd_lot", "ok": contract.get("fixed_capital_odd_lot") is True, "value": contract},
        {"name": "model_changes_false", "ok": contract.get("model_changes") is False, "value": contract.get("model_changes")},
        {
            "name": "production_ranking_changes_false",
            "ok": contract.get("production_ranking_changes") is False,
            "value": contract.get("production_ranking_changes"),
        },
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {"name": "capital_levels_minimum", "ok": len(capital_levels) >= 3, "value": sorted(capital_levels)},
        {
            "name": "required_variants_present",
            "ok": {"production_top7", "production_top7_sl12_min5", "candidate_top7", "candidate_top7_sl12_min5"} <= variants,
            "value": sorted(str(value) for value in variants),
        },
        {"name": "rows_complete", "ok": len(rows) >= len(capital_levels) * 4, "value": len(rows)},
        {
            "name": "peer_delta_present",
            "ok": all(row.get("return_delta_vs_peer") is not None and row.get("peer_variant") for row in rows),
            "value": rows[:3],
        },
        {"name": "missing_empty", "ok": not payload.get("missing"), "value": payload.get("missing")},
        {
            "name": "decision_safe",
            "ok": (payload.get("decision") or {}).get("promotion_ready") is False,
            "value": payload.get("decision"),
        },
    ]
    return finish_payload(
        "candidate_comparison",
        path,
        rows,
        checks,
        {"decision": (payload.get("decision") or {}).get("status")},
    )


def build_exit_horizon(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    _, report_schema = PROFILE_SCHEMAS["exit_horizon"]
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    horizons = {int(row.get("horizon")) for row in rows if row.get("horizon") is not None}
    kinds = {row.get("kind") for row in rows}
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == report_schema, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "research_only", "ok": contract.get("research_only") is True, "value": contract},
        {"name": "model_changes_false", "ok": contract.get("model_changes") is False, "value": contract.get("model_changes")},
        {
            "name": "production_ranking_changes_false",
            "ok": contract.get("production_ranking_changes") is False,
            "value": contract.get("production_ranking_changes"),
        },
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {"name": "horizons_present", "ok": REQUIRED_HORIZONS <= horizons, "value": sorted(horizons)},
        {"name": "kinds_present", "ok": REQUIRED_HORIZON_KINDS <= kinds, "value": sorted(str(item) for item in kinds)},
        {"name": "missing_empty", "ok": not payload.get("missing"), "value": payload.get("missing")},
        {"name": "decision_safe", "ok": decision.get("promotion_ready") is False, "value": decision},
    ]
    return finish_payload(
        "exit_horizon",
        path,
        rows,
        checks,
        {"decision": decision.get("status"), "selected_horizon": decision.get("selected_horizon")},
    )


def build_exit_strategy(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    _, report_schema = PROFILE_SCHEMAS["exit_strategy"]
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    variants = {row.get("variant") for row in rows}
    capital_levels = set((payload.get("inputs") or {}).get("capital_levels") or [])
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    candidate_rows = [row for row in rows if row.get("variant") == "candidate_ptp25_third"]
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == report_schema, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "research_only", "ok": contract.get("research_only") is True, "value": contract},
        {"name": "model_changes_false", "ok": contract.get("model_changes") is False, "value": contract.get("model_changes")},
        {
            "name": "production_ranking_changes_false",
            "ok": contract.get("production_ranking_changes") is False,
            "value": contract.get("production_ranking_changes"),
        },
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {"name": "partial_runner_contract", "ok": contract.get("partial_take_profit_runner") is True, "value": contract},
        {"name": "capital_levels_minimum", "ok": len(capital_levels) >= 3, "value": sorted(capital_levels)},
        {"name": "required_variants_present", "ok": REQUIRED_EXIT_VARIANTS <= variants, "value": sorted(str(item) for item in variants)},
        {"name": "missing_empty", "ok": not payload.get("missing"), "value": payload.get("missing")},
        {
            "name": "candidate_beats_production_peer_all_capitals",
            "ok": all(float(row.get("return_delta_vs_production_peer") or 0) > 0 for row in candidate_rows),
            "value": candidate_rows,
        },
        {"name": "decision_safe", "ok": decision.get("promotion_ready") is False, "value": decision},
    ]
    return finish_payload(
        "exit_strategy",
        path,
        rows,
        checks,
        {"decision": decision.get("status"), "selected": decision.get("selected")},
    )


def build_exposure_sensitivity(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    _, report_schema = PROFILE_SCHEMAS["exposure_sensitivity"]
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    capital_levels = set((payload.get("inputs") or {}).get("capital_levels") or [])
    settings = set(((payload.get("inputs") or {}).get("settings") or {}).keys())
    sides = {row.get("side") for row in rows}
    row_keys = {(row.get("side"), row.get("setting"), row.get("capital")) for row in rows}
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == report_schema, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "research_only", "ok": contract.get("research_only") is True, "value": contract},
        {"name": "fixed_capital_odd_lot", "ok": contract.get("fixed_capital_odd_lot") is True, "value": contract},
        {"name": "model_changes_false", "ok": contract.get("model_changes") is False, "value": contract.get("model_changes")},
        {
            "name": "production_ranking_changes_false",
            "ok": contract.get("production_ranking_changes") is False,
            "value": contract.get("production_ranking_changes"),
        },
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {"name": "capital_levels_minimum", "ok": len(capital_levels) >= 3, "value": sorted(capital_levels)},
        {"name": "settings_minimum", "ok": {"g85_pos15", "g75_pos12"} <= settings, "value": sorted(settings)},
        {"name": "sides_present", "ok": {"candidate", "production"} <= sides, "value": sorted(str(item) for item in sides)},
        {
            "name": "rows_complete",
            "ok": len(row_keys) >= len(capital_levels) * len(settings) * 2,
            "value": len(row_keys),
        },
        {"name": "missing_empty", "ok": not payload.get("missing"), "value": payload.get("missing")},
        {
            "name": "decision_safe",
            "ok": (payload.get("decision") or {}).get("promotion_ready") is False,
            "value": payload.get("decision"),
        },
    ]
    return finish_payload(
        "exposure_sensitivity",
        path,
        rows,
        checks,
        {"decision": (payload.get("decision") or {}).get("status")},
    )


def build_regime_sensitivity(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    _, report_schema = PROFILE_SCHEMAS["regime_sensitivity"]
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    capital_levels = set((payload.get("inputs") or {}).get("capital_levels") or [])
    regimes = {row.get("regime") for row in rows}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == report_schema, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "research_only", "ok": contract.get("research_only") is True, "value": contract},
        {"name": "fixed_capital_odd_lot", "ok": contract.get("fixed_capital_odd_lot") is True, "value": contract},
        {"name": "model_changes_false", "ok": contract.get("model_changes") is False, "value": contract.get("model_changes")},
        {
            "name": "production_ranking_changes_false",
            "ok": contract.get("production_ranking_changes") is False,
            "value": contract.get("production_ranking_changes"),
        },
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {"name": "capital_levels_minimum", "ok": len(capital_levels) >= 3, "value": sorted(capital_levels)},
        {"name": "required_regimes_present", "ok": REQUIRED_REGIMES <= regimes, "value": sorted(str(item) for item in regimes)},
        {
            "name": "summary_regimes_present",
            "ok": REQUIRED_REGIMES <= set(summary),
            "value": sorted(summary),
        },
        {"name": "missing_empty", "ok": not payload.get("missing"), "value": payload.get("missing")},
        {
            "name": "decision_safe",
            "ok": (payload.get("decision") or {}).get("promotion_ready") is False,
            "value": payload.get("decision"),
        },
    ]
    return finish_payload(
        "regime_sensitivity",
        path,
        rows,
        checks,
        {"decision": (payload.get("decision") or {}).get("status")},
    )


def build_regime_throttle(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    _, report_schema = PROFILE_SCHEMAS["regime_throttle"]
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    rows = payload.get("rows") if isinstance(payload.get("rows"), list) else []
    variants = {row.get("variant") for row in rows}
    decision = payload.get("decision") if isinstance(payload.get("decision"), dict) else {}
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == report_schema, "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "research_only", "ok": contract.get("research_only") is True, "value": contract},
        {"name": "model_changes_false", "ok": contract.get("model_changes") is False, "value": contract.get("model_changes")},
        {
            "name": "production_ranking_changes_false",
            "ok": contract.get("production_ranking_changes") is False,
            "value": contract.get("production_ranking_changes"),
        },
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {
            "name": "signal_day_regime_controls_next_entry",
            "ok": contract.get("signal_day_regime_controls_next_entry") is True,
            "value": contract.get("signal_day_regime_controls_next_entry"),
        },
        {"name": "required_variants_present", "ok": REQUIRED_THROTTLE_VARIANTS <= variants, "value": sorted(str(item) for item in variants)},
        {"name": "missing_empty", "ok": not payload.get("missing"), "value": payload.get("missing")},
        {"name": "decision_safe", "ok": decision.get("promotion_ready") is False, "value": decision},
    ]
    return finish_payload(
        "regime_throttle",
        path,
        rows,
        checks,
        {"decision": decision.get("status")},
    )


BUILDERS: dict[str, Callable[[Path], dict[str, Any]]] = {
    "candidate_comparison": build_candidate_comparison,
    "exit_horizon": build_exit_horizon,
    "exit_strategy": build_exit_strategy,
    "exposure_sensitivity": build_exposure_sensitivity,
    "regime_sensitivity": build_regime_sensitivity,
    "regime_throttle": build_regime_throttle,
}


def build_payload(profile: str, path: Path) -> dict[str, Any]:
    return BUILDERS[profile](path)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    artifact = resolve_path(args.artifact)
    if artifact is None or not artifact.exists():
        raise FileNotFoundError(f"artifact not found: {args.artifact}")
    output = resolve_path(args.output or DEFAULT_OUTPUTS[args.profile])
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args.profile, artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
