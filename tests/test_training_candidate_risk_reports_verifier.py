from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import verify_training_candidate_risk_reports as verifier


PROFILES = ("attribution", "risk_control")
DEFAULT_OUTPUTS = {
    "attribution": "artifacts/model_experiments/training_candidate_risk_attribution_verification_latest.json",
    "risk_control": "artifacts/model_experiments/training_candidate_risk_control_report_verification_latest.json",
}
CHECK_NAMES = {
    "attribution": [
        "schema",
        "status_ok",
        "research_only",
        "model_changes_false",
        "production_ranking_changes_false",
        "promotion_ready_false",
        "summary_input_exists",
        "candidate_matrix_exists",
        "production_matrix_exists",
        "return_delta_present",
        "drawdown_delta_present",
        "sector_attribution_present",
        "rank_attribution_present",
        "month_and_rank_trade_attribution_present",
        "risk_hypotheses_minimum",
        "next_experiments_minimum",
        "decision_safe",
    ],
    "risk_control": [
        "schema",
        "status_ok",
        "research_only",
        "model_changes_false",
        "production_ranking_changes_false",
        "promotion_ready_false",
        "variant_count_minimum",
        "variant_metrics_present",
        "decision_present",
        "selected_or_rejected_reason_present",
        "next_steps_present",
    ],
}


def write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def normalized(payload: dict[str, object]) -> dict[str, object]:
    result = dict(payload)
    result.pop("generated_at", None)
    return result


def attribution_payload(root: Path, valid: bool) -> dict[str, object]:
    if valid:
        for name in ("summary", "candidate_matrix", "production_matrix"):
            write_json(root / "inputs" / f"{name}.json", {"name": name})
        return {
            "schema_version": "training-candidate-risk-attribution.v1",
            "status": "OK",
            "contract": {
                "research_only": True,
                "model_changes": False,
                "production_ranking_changes": False,
                "promotion_ready": False,
            },
            "inputs": {
                "summary": "inputs/summary.json",
                "candidate_matrix": "inputs/candidate_matrix.json",
                "production_matrix": "inputs/production_matrix.json",
            },
            "headline": {
                "portfolio_40d_total_return": {"candidate": 0.18, "production": 0.1, "delta": 0.08},
                "fixed_share_default_return_on_buy_cash": {"candidate": 0.12, "production": 0.08, "delta": 0.04},
                "portfolio_40d_max_drawdown": {"candidate": -0.21, "production": -0.18, "delta": -0.03},
            },
            "matrix_attribution": {
                "sector_concentration_fixed_40d": {"max_sector_buy_share_delta": 0.15},
                "candidate_top_rank_policies": [{"rank": "top5"}],
            },
            "trade_attribution": {
                "by_month": [{"ranking_month": "2026-01"}],
                "by_rank": [{"rank": "top5"}],
            },
            "risk_hypotheses": [{"id": "H1"}, {"id": "H2"}, {"id": "H3"}],
            "next_experiments": [{"id": "E1"}, {"id": "E2"}, {"id": "E3"}],
            "decision": {"status": "KEEP_RESEARCH", "promotion_ready": False},
        }
    return {
        "schema_version": "broken.v1",
        "status": "FAILED",
        "contract": {
            "research_only": False,
            "model_changes": True,
            "production_ranking_changes": True,
            "promotion_ready": True,
        },
        "inputs": {
            "summary": "inputs/missing_summary.json",
            "candidate_matrix": "inputs/missing_candidate_matrix.json",
            "production_matrix": "inputs/missing_production_matrix.json",
        },
        "headline": {},
        "matrix_attribution": {},
        "trade_attribution": {},
        "risk_hypotheses": [{"id": "H1"}],
        "next_experiments": [],
        "decision": {"status": "PROMOTION_READY", "promotion_ready": True},
    }


def risk_control_payload(valid: bool) -> dict[str, object]:
    if valid:
        return {
            "schema_version": "training-candidate-risk-control-report.v1",
            "status": "OK",
            "contract": {
                "research_only": True,
                "model_changes": False,
                "production_ranking_changes": False,
                "promotion_ready": False,
            },
            "variants_ranked": [
                {"label": f"variant_{index}", "total_return": 0.10 + index / 100, "max_drawdown": -0.2 + index / 100}
                for index in range(5)
            ],
            "decision": {
                "status": "RISK_CONTROL_REPLAY_CANDIDATE",
                "selected": "variant_4",
                "reason": "保留報酬優勢且回撤仍在研究容忍範圍。",
            },
            "next": ["fixed capital replay", "regime replay"],
        }
    return {
        "schema_version": "broken.v1",
        "status": "FAILED",
        "contract": {
            "research_only": False,
            "model_changes": True,
            "production_ranking_changes": True,
            "promotion_ready": True,
        },
        "variants_ranked": [
            {"label": "variant_0", "total_return": 0.1, "max_drawdown": -0.2},
            {"label": "variant_1", "total_return": 0.2},
        ],
        "decision": {"status": "PROMOTION_READY", "selected": "variant_1", "reason": ""},
        "next": ["promotion review"],
    }


def artifact_for(profile: str, root: Path, valid: bool) -> Path:
    if profile == "attribution":
        payload = attribution_payload(root, valid)
    elif profile == "risk_control":
        payload = risk_control_payload(valid)
    else:
        raise ValueError(profile)
    return write_json(root / "reports" / f"{profile}.json", payload)


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("valid", (True, False), ids=("valid", "invalid"))
def test_profile_payload_preserves_legacy_checks_summary_and_status(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, profile: str, valid: bool
) -> None:
    artifact = artifact_for(profile, tmp_path, valid)
    monkeypatch.setattr(verifier, "PROJECT_ROOT", tmp_path.resolve())

    payload = normalized(verifier.build_payload(profile, artifact))

    assert payload["status"] == ("OK" if valid else "FAILED")
    assert payload["artifact"] == f"reports/{profile}.json"
    assert [check["name"] for check in payload["checks"]] == CHECK_NAMES[profile]
    assert [check["ok"] for check in payload["checks"]] == ([True] * len(CHECK_NAMES[profile]) if valid else [False] * len(CHECK_NAMES[profile]))

    if profile == "attribution":
        assert payload["schema_version"] == "training-candidate-risk-attribution-verification.v1"
        assert payload["summary"] == {
            "check_count": 17,
            "failed_count": 0 if valid else 17,
            "risk_hypothesis_count": 3 if valid else 1,
            "next_experiment_count": 3 if valid else 0,
            "decision": "KEEP_RESEARCH" if valid else "PROMOTION_READY",
        }
    else:
        assert payload["schema_version"] == "training-candidate-risk-control-report-verification.v1"
        assert payload["summary"] == {
            "check_count": 11,
            "failed_count": 0 if valid else 11,
            "variant_count": 5 if valid else 2,
            "decision": "RISK_CONTROL_REPLAY_CANDIDATE" if valid else "PROMOTION_READY",
            "selected": "variant_4" if valid else "variant_1",
        }


@pytest.mark.parametrize("profile", PROFILES)
@pytest.mark.parametrize("valid", (True, False), ids=("valid", "invalid"))
def test_profile_cli_preserves_default_output_console_and_exit_code(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    profile: str,
    valid: bool,
) -> None:
    artifact = artifact_for(profile, tmp_path, valid)
    monkeypatch.setattr(verifier, "PROJECT_ROOT", tmp_path.resolve())

    exit_code = verifier.main(["--profile", profile, "--artifact", str(artifact)])
    console = json.loads(capsys.readouterr().out)

    expected_status = "OK" if valid else "FAILED"
    assert exit_code == (0 if valid else 1)
    assert console == {"status": expected_status, "output": DEFAULT_OUTPUTS[profile]}
    assert (tmp_path / DEFAULT_OUTPUTS[profile]).exists()
