from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from scripts import verify_odd_lot_research_suite as research_suite


PROFILES = (
    "candidate_comparison",
    "exit_horizon",
    "exit_strategy",
    "exposure_sensitivity",
    "regime_sensitivity",
    "regime_throttle",
)
FROZEN_GOLDEN = {
    "candidate_comparison": {
        "valid": {
            "exit_code": 0,
            "payload_sha256": "078b83f6f21866e3fca4122270ee68263d2ac607cbd3e1ca1b700eafe8a1caa7",
            "check_names": [
                "schema",
                "status_ok",
                "research_only",
                "fixed_capital_odd_lot",
                "model_changes_false",
                "production_ranking_changes_false",
                "promotion_ready_false",
                "capital_levels_minimum",
                "required_variants_present",
                "rows_complete",
                "peer_delta_present",
                "missing_empty",
                "decision_safe",
            ],
            "summary": {"check_count": 13, "decision": "BLOCKED_RESEARCH_ONLY", "failed_count": 0, "row_count": 12},
        },
        "invalid": {
            "exit_code": 1,
            "payload_sha256": "62d77eea1308f9873fba3d4370504d111da89d00804e21da5066ef619e6e2fca",
            "check_names": [
                "schema",
                "status_ok",
                "research_only",
                "fixed_capital_odd_lot",
                "model_changes_false",
                "production_ranking_changes_false",
                "promotion_ready_false",
                "capital_levels_minimum",
                "required_variants_present",
                "rows_complete",
                "peer_delta_present",
                "missing_empty",
                "decision_safe",
            ],
            "summary": {"check_count": 13, "decision": "BLOCKED_RESEARCH_ONLY", "failed_count": 1, "row_count": 12},
        },
    },
    "exit_horizon": {
        "valid": {
            "exit_code": 0,
            "payload_sha256": "23003f8568415817b31d3f05763043f26a05be858b3a02b3fcd8e545ca4c1439",
            "check_names": [
                "schema",
                "status_ok",
                "research_only",
                "model_changes_false",
                "production_ranking_changes_false",
                "promotion_ready_false",
                "horizons_present",
                "kinds_present",
                "missing_empty",
                "decision_safe",
            ],
            "summary": {
                "check_count": 10,
                "decision": "BLOCKED_RESEARCH_ONLY",
                "failed_count": 0,
                "row_count": 9,
                "selected_horizon": 40,
            },
        },
        "invalid": {
            "exit_code": 1,
            "payload_sha256": "b49d3e41ef75425e261d59828414b67d026d5537508721043c685722a3492c08",
            "check_names": [
                "schema",
                "status_ok",
                "research_only",
                "model_changes_false",
                "production_ranking_changes_false",
                "promotion_ready_false",
                "horizons_present",
                "kinds_present",
                "missing_empty",
                "decision_safe",
            ],
            "summary": {
                "check_count": 10,
                "decision": "BLOCKED_RESEARCH_ONLY",
                "failed_count": 1,
                "row_count": 9,
                "selected_horizon": 40,
            },
        },
    },
    "exit_strategy": {
        "valid": {
            "exit_code": 0,
            "payload_sha256": "34b58b895cc7696c5f79f3bbc538324bae8e942336be4ea03ff8d4e6d06acde6",
            "check_names": [
                "schema",
                "status_ok",
                "research_only",
                "model_changes_false",
                "production_ranking_changes_false",
                "promotion_ready_false",
                "partial_runner_contract",
                "capital_levels_minimum",
                "required_variants_present",
                "missing_empty",
                "candidate_beats_production_peer_all_capitals",
                "decision_safe",
            ],
            "summary": {
                "check_count": 12,
                "decision": "BLOCKED_RESEARCH_ONLY",
                "failed_count": 0,
                "row_count": 15,
                "selected": "candidate_ptp25_third",
            },
        },
        "invalid": {
            "exit_code": 1,
            "payload_sha256": "cd879fab9debd18cf16a1f60d5940614548b2655aea6f5c48b9ec0fef676a1c7",
            "check_names": [
                "schema",
                "status_ok",
                "research_only",
                "model_changes_false",
                "production_ranking_changes_false",
                "promotion_ready_false",
                "partial_runner_contract",
                "capital_levels_minimum",
                "required_variants_present",
                "missing_empty",
                "candidate_beats_production_peer_all_capitals",
                "decision_safe",
            ],
            "summary": {
                "check_count": 12,
                "decision": "BLOCKED_RESEARCH_ONLY",
                "failed_count": 1,
                "row_count": 15,
                "selected": "candidate_ptp25_third",
            },
        },
    },
    "exposure_sensitivity": {
        "valid": {
            "exit_code": 0,
            "payload_sha256": "465eb049c3e5dbe4ce4913ce70ebfd663c7887e012948620a8dfd2813aee56fd",
            "check_names": [
                "schema",
                "status_ok",
                "research_only",
                "fixed_capital_odd_lot",
                "model_changes_false",
                "production_ranking_changes_false",
                "promotion_ready_false",
                "capital_levels_minimum",
                "settings_minimum",
                "sides_present",
                "rows_complete",
                "missing_empty",
                "decision_safe",
            ],
            "summary": {"check_count": 13, "decision": "BLOCKED_RESEARCH_ONLY", "failed_count": 0, "row_count": 12},
        },
        "invalid": {
            "exit_code": 1,
            "payload_sha256": "7cc6f47bf26828c623a15d6e8311d6c8059084e1666fd35b18be5f1684572e2a",
            "check_names": [
                "schema",
                "status_ok",
                "research_only",
                "fixed_capital_odd_lot",
                "model_changes_false",
                "production_ranking_changes_false",
                "promotion_ready_false",
                "capital_levels_minimum",
                "settings_minimum",
                "sides_present",
                "rows_complete",
                "missing_empty",
                "decision_safe",
            ],
            "summary": {"check_count": 13, "decision": "BLOCKED_RESEARCH_ONLY", "failed_count": 1, "row_count": 12},
        },
    },
    "regime_sensitivity": {
        "valid": {
            "exit_code": 0,
            "payload_sha256": "029e9c543a510bc420f466bb2005eb508057b1f479fcb3b4aa60c6df570f3d65",
            "check_names": [
                "schema",
                "status_ok",
                "research_only",
                "fixed_capital_odd_lot",
                "model_changes_false",
                "production_ranking_changes_false",
                "promotion_ready_false",
                "capital_levels_minimum",
                "required_regimes_present",
                "summary_regimes_present",
                "missing_empty",
                "decision_safe",
            ],
            "summary": {"check_count": 12, "decision": "BLOCKED_RESEARCH_ONLY", "failed_count": 0, "row_count": 9},
        },
        "invalid": {
            "exit_code": 1,
            "payload_sha256": "ca4a39cd1a764fbd4883b0b78e066d16333640914d5e93fabd4bd8bff7aebd82",
            "check_names": [
                "schema",
                "status_ok",
                "research_only",
                "fixed_capital_odd_lot",
                "model_changes_false",
                "production_ranking_changes_false",
                "promotion_ready_false",
                "capital_levels_minimum",
                "required_regimes_present",
                "summary_regimes_present",
                "missing_empty",
                "decision_safe",
            ],
            "summary": {"check_count": 12, "decision": "BLOCKED_RESEARCH_ONLY", "failed_count": 1, "row_count": 9},
        },
    },
    "regime_throttle": {
        "valid": {
            "exit_code": 0,
            "payload_sha256": "3351bcd3cf7c02235906b7915cd07a72d9a584347032f4e3b3f17cd926b5d6d2",
            "check_names": [
                "schema",
                "status_ok",
                "research_only",
                "model_changes_false",
                "production_ranking_changes_false",
                "promotion_ready_false",
                "signal_day_regime_controls_next_entry",
                "required_variants_present",
                "missing_empty",
                "decision_safe",
            ],
            "summary": {"check_count": 10, "decision": "BLOCKED_RESEARCH_ONLY", "failed_count": 0, "row_count": 4},
        },
        "invalid": {
            "exit_code": 1,
            "payload_sha256": "9ac403cf9f182cadda8264cc5a755a41692e45db58bf01145a07eb624751f295",
            "check_names": [
                "schema",
                "status_ok",
                "research_only",
                "model_changes_false",
                "production_ranking_changes_false",
                "promotion_ready_false",
                "signal_day_regime_controls_next_entry",
                "required_variants_present",
                "missing_empty",
                "decision_safe",
            ],
            "summary": {"check_count": 10, "decision": "BLOCKED_RESEARCH_ONLY", "failed_count": 1, "row_count": 4},
        },
    },
}


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def normalized(payload: dict[str, Any]) -> dict[str, Any]:
    result = copy.deepcopy(payload)
    result.pop("generated_at", None)
    result["artifact"] = "<artifact>"
    return result


def payload_sha256(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def candidate_comparison_payload(valid: bool) -> dict[str, Any]:
    contract = {
        "research_only": True,
        "fixed_capital_odd_lot": True,
        "model_changes": False,
        "production_ranking_changes": False,
        "promotion_ready": False,
    }
    rows = [
        {
            "capital": capital,
            "variant": variant,
            "peer_variant": "production_top7",
            "return_delta_vs_peer": 0.01,
        }
        for capital in (100_000, 300_000, 500_000)
        for variant in (
            "production_top7",
            "production_top7_sl12_min5",
            "candidate_top7",
            "candidate_top7_sl12_min5",
        )
    ]
    return {
        "schema_version": "odd-lot-candidate-comparison-report.v1" if valid else "wrong-schema.v1",
        "status": "OK",
        "contract": contract,
        "inputs": {"capital_levels": [100_000, 300_000, 500_000]},
        "rows": rows,
        "missing": [],
        "decision": {"status": "BLOCKED_RESEARCH_ONLY", "promotion_ready": False},
    }


def exit_horizon_payload(valid: bool) -> dict[str, Any]:
    rows = [
        {"horizon": horizon, "kind": kind}
        for horizon in (20, 40, 60)
        for kind in ("candidate_baseline", "candidate_exit", "production_exit")
    ]
    return {
        "schema_version": "odd-lot-exit-horizon-sensitivity-report.v1" if valid else "wrong-schema.v1",
        "status": "OK",
        "contract": research_contract(),
        "rows": rows,
        "missing": [],
        "decision": {"status": "BLOCKED_RESEARCH_ONLY", "promotion_ready": False, "selected_horizon": 40},
    }


def exit_strategy_payload(valid: bool) -> dict[str, Any]:
    contract = research_contract()
    contract["partial_take_profit_runner"] = True
    rows = [
        {
            "capital": capital,
            "variant": variant,
            "return_delta_vs_production_peer": 0.01,
        }
        for capital in (100_000, 300_000, 500_000)
        for variant in (
            "production_baseline",
            "production_ptp25_third",
            "candidate_baseline",
            "candidate_ptp25_third",
            "candidate_ptp25_half",
        )
    ]
    return {
        "schema_version": "odd-lot-exit-strategy-report.v1" if valid else "wrong-schema.v1",
        "status": "OK",
        "contract": contract,
        "inputs": {"capital_levels": [100_000, 300_000, 500_000]},
        "rows": rows,
        "missing": [],
        "decision": {"status": "BLOCKED_RESEARCH_ONLY", "promotion_ready": False, "selected": "candidate_ptp25_third"},
    }


def exposure_sensitivity_payload(valid: bool) -> dict[str, Any]:
    settings = {"g85_pos15": {}, "g75_pos12": {}}
    rows = [
        {"side": side, "setting": setting, "capital": capital}
        for side in ("candidate", "production")
        for setting in settings
        for capital in (100_000, 300_000, 500_000)
    ]
    return {
        "schema_version": "odd-lot-exposure-sensitivity-report.v1" if valid else "wrong-schema.v1",
        "status": "OK",
        "contract": research_contract(),
        "inputs": {"capital_levels": [100_000, 300_000, 500_000], "settings": settings},
        "rows": rows,
        "missing": [],
        "decision": {"status": "BLOCKED_RESEARCH_ONLY", "promotion_ready": False},
    }


def regime_sensitivity_payload(valid: bool) -> dict[str, Any]:
    regimes = ("BIG_BULL", "HIGH_CHOPPY_CONTEXT", "OTHER")
    rows = [
        {"regime": regime, "capital": capital}
        for regime in regimes
        for capital in (100_000, 300_000, 500_000)
    ]
    return {
        "schema_version": "odd-lot-regime-sensitivity-report.v1" if valid else "wrong-schema.v1",
        "status": "OK",
        "contract": research_contract(),
        "inputs": {"capital_levels": [100_000, 300_000, 500_000]},
        "rows": rows,
        "summary": {regime: {"total_return": 0.1} for regime in regimes},
        "missing": [],
        "decision": {"status": "BLOCKED_RESEARCH_ONLY", "promotion_ready": False},
    }


def regime_throttle_payload(valid: bool) -> dict[str, Any]:
    contract = research_contract(fixed_capital=False)
    contract["signal_day_regime_controls_next_entry"] = True
    return {
        "schema_version": "odd-lot-regime-throttle-report.v1" if valid else "wrong-schema.v1",
        "status": "OK",
        "contract": contract,
        "rows": [{"variant": variant} for variant in ("baseline", "hc45", "hc55", "hc65")],
        "missing": [],
        "decision": {"status": "BLOCKED_RESEARCH_ONLY", "promotion_ready": False},
    }


def research_contract(fixed_capital: bool = True) -> dict[str, Any]:
    contract = {
        "research_only": True,
        "model_changes": False,
        "production_ranking_changes": False,
        "promotion_ready": False,
    }
    if fixed_capital:
        contract["fixed_capital_odd_lot"] = True
    return contract


PAYLOAD_BUILDERS = {
    "candidate_comparison": candidate_comparison_payload,
    "exit_horizon": exit_horizon_payload,
    "exit_strategy": exit_strategy_payload,
    "exposure_sensitivity": exposure_sensitivity_payload,
    "regime_sensitivity": regime_sensitivity_payload,
    "regime_throttle": regime_throttle_payload,
}
DEFAULT_OUTPUTS = {
    "candidate_comparison": "artifacts/model_experiments/odd_lot_candidate_comparison_report_verification_latest.json",
    "exit_horizon": "artifacts/model_experiments/odd_lot_exit_horizon_sensitivity_report_verification_latest.json",
    "exit_strategy": "artifacts/model_experiments/odd_lot_exit_strategy_report_verification_latest.json",
    "exposure_sensitivity": "artifacts/model_experiments/odd_lot_exposure_sensitivity_report_verification_latest.json",
    "regime_sensitivity": "artifacts/model_experiments/odd_lot_regime_sensitivity_report_verification_latest.json",
    "regime_throttle": "artifacts/model_experiments/odd_lot_regime_throttle_report_verification_latest.json",
}


def run_suite_cli(monkeypatch: pytest.MonkeyPatch, profile: str, artifact: Path, output: Path) -> int:
    monkeypatch.setattr(research_suite, "PROJECT_ROOT", artifact.parents[1])
    return research_suite.main(
        [
            "--profile",
            profile,
            "--artifact",
            str(artifact),
            "--output",
            str(output),
        ]
    )


@pytest.mark.parametrize("profile", PROFILES)
def test_profile_default_output_matches_legacy_cli_path(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
) -> None:
    artifact = tmp_path / "reports" / f"{profile}.json"
    write_json(artifact, PAYLOAD_BUILDERS[profile](True))
    monkeypatch.setattr(research_suite, "PROJECT_ROOT", tmp_path)

    exit_code = research_suite.main(["--profile", profile, "--artifact", str(artifact)])

    output = tmp_path / DEFAULT_OUTPUTS[profile]
    assert exit_code == 0
    assert output.exists()
    assert json.loads(output.read_text(encoding="utf-8"))["status"] == "OK"


@pytest.mark.parametrize("profile", tuple(PROFILES))
@pytest.mark.parametrize("valid", (True, False), ids=("valid", "invalid"))
def test_profile_matches_frozen_payload_and_exit_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    profile: str,
    valid: bool,
) -> None:
    artifact = tmp_path / "reports" / f"{profile}.json"
    suite_output = tmp_path / "suite" / "verification.json"
    write_json(artifact, PAYLOAD_BUILDERS[profile](valid))

    suite_exit_code = run_suite_cli(monkeypatch, profile, artifact, suite_output)
    payload = normalized(json.loads(suite_output.read_text(encoding="utf-8")))
    expected = FROZEN_GOLDEN[profile]["valid" if valid else "invalid"]

    assert suite_exit_code == expected["exit_code"]
    assert payload["summary"] == expected["summary"]
    assert [check["name"] for check in payload["checks"]] == expected["check_names"]
    assert payload_sha256(payload) == expected["payload_sha256"]
