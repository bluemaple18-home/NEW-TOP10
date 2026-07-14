from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_operational_rule_review as builder


RUN_DATE = "2026-06-08"


def write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def normalized_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("generated_at", None)
    return payload


def candidate_metric(return_value: float, pnl: float, win_rate: float = 0.6) -> dict[str, object]:
    return {
        "return_on_buy_cash": return_value,
        "total_net_pnl": pnl,
        "win_rate": win_rate,
        "worst_mae": -0.12,
    }


def setup_candidate_fixture(root: Path) -> dict[str, Path]:
    base = root / "fixtures" / "candidate"
    candidate_vs_production = write_json(
        base / "candidate_vs_production.json",
        {
            "comparison": {
                "rows": [
                    {"horizon": 10, "label": "production_recent60", **candidate_metric(0.08, 800)},
                    {"horizon": 10, "label": "candidate_sealed60", **candidate_metric(0.07, 700)},
                    {"horizon": 30, "label": "production_recent60", **candidate_metric(0.10, 1000)},
                    {"horizon": 30, "label": "candidate_sealed60", **candidate_metric(0.15, 1500)},
                ]
            }
        },
    )
    candidate_matrix = write_json(
        base / "candidate_matrix.json",
        {
            "summary": {
                "exit_policy_top": [{"key": "fixed_40d", "return_on_buy_cash": 0.2}],
                "rank_policy_top": [{"key": "fixed_40d::top4_7", "return_on_buy_cash": 0.18}],
                "exit_by_regime_top": {"BIG_BULL": [{"key": "fixed_40d"}]},
                "sector_concentration": {"fixed_40d": {"max_sector_buy_share": 0.7}},
            },
            "matrix": {
                "exit_policy": {
                    "fixed_30d": candidate_metric(0.10, 1000),
                    "fixed_40d": candidate_metric(0.12, 1200),
                    "h30_early_tp07": candidate_metric(0.05, 500),
                    "h30_early_tp10": candidate_metric(0.08, 800),
                    "h30_early_tp12": candidate_metric(0.09, 900),
                    "h30_early_tp15": candidate_metric(0.11, 1100),
                    "h40_early_tp07": candidate_metric(0.06, 600),
                    "h40_early_tp10": candidate_metric(0.10, 1000),
                    "h40_early_tp12": candidate_metric(0.13, 1300),
                    "h40_early_tp15": candidate_metric(0.14, 1400),
                    "h30_tp25_sl10": candidate_metric(0.09, 900),
                }
            },
        },
    )
    production_matrix = write_json(
        base / "production_matrix.json",
        {"summary": {"exit_policy_top": [{"key": "fixed_30d", "return_on_buy_cash": 0.11}]}},
    )
    constrained_shadow = write_json(
        base / "constrained_shadow.json",
        {"candidates": [{"candidate_id": "constrained_k7", "decision": "READY_FOR_SHADOW_MONITOR"}]},
    )
    sector_cap_shadow = write_json(
        base / "sector_cap_shadow.json",
        {"candidates": [{"candidate_id": "sector_cap_55", "reason": "too concentrated"}]},
    )
    return {
        "candidate_vs_production": candidate_vs_production,
        "candidate_matrix": candidate_matrix,
        "production_matrix": production_matrix,
        "constrained_shadow": constrained_shadow,
        "sector_cap_shadow": sector_cap_shadow,
    }


def experiment_matrix(fixed40_return: float, top_key: str) -> dict[str, object]:
    fixed_30d = {"return_on_buy_cash": 0.10, "worst_mae": -0.16, "trade_count": 10}
    fixed_40d = {"return_on_buy_cash": fixed40_return, "worst_mae": -0.20, "trade_count": 10}
    guarded = {"return_on_buy_cash": fixed40_return - 0.03, "worst_mae": -0.10, "trade_count": 10}
    rank_values = {
        "fixed_40d::top1_3": {"return_on_buy_cash": 0.18 if top_key == "fixed_40d::top1_3" else 0.11, "trade_count": 10},
        "fixed_40d::top4_7": {"return_on_buy_cash": 0.18 if top_key == "fixed_40d::top4_7" else 0.12, "trade_count": 10},
        "fixed_40d::top5": {"return_on_buy_cash": 0.13, "trade_count": 10},
        "fixed_40d::top7": {"return_on_buy_cash": 0.14, "trade_count": 10},
        "fixed_40d::all_top10": {"return_on_buy_cash": 0.10, "trade_count": 10},
    }
    return {
        "summary": {"sector_concentration": {"fixed_40d": {"max_sector_buy_share": 0.77}}},
        "matrix": {
            "exit_policy": {
                "fixed_30d": fixed_30d,
                "fixed_40d": fixed_40d,
                "h30_tp25_sl10": guarded,
                "h30_tp18_sl08": guarded,
                "h30_trail10": guarded,
                "h30_trail15": guarded,
                "h30_trail18": guarded,
                "h30_trail22": guarded,
                "h40_trail12": guarded,
                "h40_trail15": guarded,
                "h40_trail18": guarded,
                "h40_trail22": guarded,
                "h40_trail25": guarded,
                "h40_tp25_sl10": guarded,
                "h40_tp35_sl12": guarded,
                "h40_early_tp15": guarded,
            },
            "rank_policy": rank_values,
        },
    }


def setup_experiment_fixture(root: Path) -> dict[str, Path]:
    base = root / "fixtures" / "experiment"
    return {
        "production_matrix": write_json(base / "production_matrix.json", experiment_matrix(0.20, "fixed_40d::top1_3")),
        "candidate_matrix": write_json(base / "candidate_matrix.json", experiment_matrix(0.22, "fixed_40d::top4_7")),
        "constrained_shadow": write_json(
            base / "constrained_shadow.json",
            {"candidates": [{"candidate_id": "constrained_k7", "decision": "READY_FOR_SHADOW_MONITOR"}]},
        ),
        "sector_cap_shadow": write_json(
            base / "sector_cap_shadow.json",
            {"summary": {"restricted_shadow_only": ["sector_cap_55"]}},
        ),
    }


def args_for(paths: dict[str, Path]) -> list[str]:
    args: list[str] = []
    for name, path in paths.items():
        args.extend([f"--{name.replace('_', '-')}", str(path)])
    return args


def test_candidate_profile_preserves_default_output_console_json_and_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = setup_candidate_fixture(tmp_path)
    monkeypatch.setattr(builder, "PROJECT_ROOT", tmp_path.resolve())

    exit_code = builder.main(["--profile", "candidate", "--date", RUN_DATE, *args_for(paths)])
    console = json.loads(capsys.readouterr().out)

    output = tmp_path / "artifacts/model_experiments/operational_rule_candidate_report_2026-06-08.json"
    assert exit_code == 0
    assert console == {
        "status": "OK",
        "output": "artifacts/model_experiments/operational_rule_candidate_report_2026-06-08.json",
        "decision": "CONTINUE_RULE_RESEARCH_NO_PROMOTION",
    }
    payload = normalized_json(output)
    assert payload["schema_version"] == "operational-rule-candidate-report.v1"
    assert payload["summary"]["candidate_decision"] == "RESEARCH_OVERLAY_ONLY"
    assert payload["candidate_vs_production"]["long_horizon_edge_count"] == 1
    assert payload["shadow_candidates"]["ready_for_shadow_monitor"] == ["constrained_k7"]
    markdown = output.with_suffix(".md").read_text(encoding="utf-8")
    assert "# Operational Rule Candidate Report" in markdown
    assert "## Candidate vs Production" in markdown
    assert "`OPRULE-04` Constrained K7 shadow monitor" in markdown


def test_candidate_profile_preserves_missing_input_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(builder, "PROJECT_ROOT", tmp_path.resolve())

    exit_code = builder.main(["--profile", "candidate", "--date", RUN_DATE])
    console = json.loads(capsys.readouterr().out)

    output = tmp_path / "artifacts/model_experiments/operational_rule_candidate_report_2026-06-08.json"
    assert exit_code == 0
    assert console["decision"] == "CONTINUE_RULE_RESEARCH_NO_PROMOTION"
    payload = normalized_json(output)
    assert payload["status"] == "OK"
    assert payload["candidate_vs_production"]["comparisons"] == []
    assert payload["candidate_vs_production"]["decision"] == "MONITOR_ONLY"
    assert output.with_suffix(".md").read_text(encoding="utf-8").startswith("# Operational Rule Candidate Report\n")


def test_experiment_profile_preserves_default_output_console_json_and_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = setup_experiment_fixture(tmp_path)
    monkeypatch.setattr(builder, "PROJECT_ROOT", tmp_path.resolve())

    exit_code = builder.main(["--profile", "experiment", "--date", RUN_DATE, *args_for(paths)])
    console = json.loads(capsys.readouterr().out)

    output = tmp_path / "artifacts/model_experiments/operational_rule_experiment_report_2026-06-08.json"
    assert exit_code == 0
    assert console == {
        "status": "OK",
        "output": "artifacts/model_experiments/operational_rule_experiment_report_2026-06-08.json",
        "overall_decision": "KEEP_RESEARCHING_NO_DEPLOYABLE_RULE_YET",
        "oprule_01": "DYNAMIC_GUARD_CANDIDATE",
        "oprule_02": "RANK_BUCKET_NOT_STABLE_ENOUGH",
        "oprule_03": "SECTOR_GUARD_REQUIRED_BUT_NOT_VALIDATED",
        "oprule_04": "READY_FOR_SHADOW_MONITOR_ONLY",
    }
    payload = normalized_json(output)
    assert payload["schema_version"] == "operational-rule-experiment-report.v1"
    assert payload["oprule_02_rank_stability"]["production_best"]["key"] == "fixed_40d::top1_3"
    assert payload["oprule_02_rank_stability"]["candidate_best"]["key"] == "fixed_40d::top4_7"
    assert payload["oprule_04_shadow_monitor"]["ready_candidates"][0]["candidate_id"] == "constrained_k7"
    markdown = output.with_suffix(".md").read_text(encoding="utf-8")
    assert "# Operational Rule Experiment Report" in markdown
    assert "## OPRULE-01 Risk Guard" in markdown
    assert "## Next Actions" in markdown


def test_experiment_profile_preserves_missing_input_contract(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(builder, "PROJECT_ROOT", tmp_path.resolve())

    exit_code = builder.main(["--profile", "experiment", "--date", RUN_DATE])
    console = json.loads(capsys.readouterr().out)

    output = tmp_path / "artifacts/model_experiments/operational_rule_experiment_report_2026-06-08.json"
    assert exit_code == 0
    assert console["overall_decision"] == "KEEP_RESEARCHING_NO_DEPLOYABLE_RULE_YET"
    payload = normalized_json(output)
    assert payload["status"] == "OK"
    assert payload["oprule_01_risk_guard"]["production"]["useful_guarded_policy_count"] == 0
    assert payload["oprule_04_shadow_monitor"]["ready_candidates"] == []
    assert output.with_suffix(".md").read_text(encoding="utf-8").startswith("# Operational Rule Experiment Report\n")
