from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts import build_training_candidate_risk_review as builder


RUN_DATE = "2026-06-08"


def write_json(path: Path, payload: dict[str, object]) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def normalized_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("generated_at", None)
    return payload


def matrix_payload(return_value: float, win_rate: float, max_sector_buy_share: float) -> dict[str, object]:
    metric = {
        "trade_count": 120,
        "return_on_buy_cash": return_value,
        "win_rate": win_rate,
        "avg_mae": -0.04,
        "worst_mae": -0.12,
        "avg_giveback": -0.03,
    }
    return {
        "matrix": {
            "exit_policy": {"fixed_40d": metric},
            "regime_policy": {
                "fixed_40d::HIGH_CHOPPY_CONTEXT": metric,
                "fixed_40d::BIG_BULL": metric,
            },
            "sector_concentration": {"fixed_40d": {"max_sector_buy_share": max_sector_buy_share}},
            "rank_policy": {"top5": metric},
        }
    }


def setup_attribution_fixture(root: Path) -> None:
    base = root / "artifacts" / "model_experiments"
    candidate = base / "training_candidates" / f"current_baseline_candidate_{RUN_DATE}"
    write_json(
        base / f"candidate_vs_production_summary_{RUN_DATE}.json",
        {
            "fixed_100_shares_5_7_10_15_20_default": {
                "candidate_return_on_buy_cash": 0.12,
                "production_return_on_buy_cash": 0.08,
                "candidate_win_rate": 0.6,
                "production_win_rate": 0.5,
            },
            "best_exit_policy_matrix": {
                "candidate": {"key": "fixed_40d", "return_on_buy_cash": 0.18},
                "production": {"key": "fixed_40d", "return_on_buy_cash": 0.11},
            },
            "portfolio_40d": {
                "candidate_total_return": 0.22,
                "production_total_return": 0.14,
                "candidate_max_drawdown": -0.21,
                "production_max_drawdown": -0.18,
                "candidate_trade_count": 22,
                "production_trade_count": 20,
            },
        },
    )
    write_json(candidate / f"fixed_share_hypothesis_matrix_candidate_{RUN_DATE}.json", matrix_payload(0.18, 0.64, 0.74))
    write_json(base / f"production_fixed_share_hypothesis_matrix_{RUN_DATE}.json", matrix_payload(0.11, 0.51, 0.52))
    write_json(
        candidate / f"fixed_share_top10_candidate_{RUN_DATE}.json",
        {"variants": [{"trades": [{"ranking_date": "2026-01-03", "rank": 1, "buy_cash": 1000, "net_pnl": 120, "net_return": 0.12}]}]},
    )
    write_json(
        base / f"production_fixed_share_top10_{RUN_DATE}.json",
        {"variants": [{"trades": [{"ranking_date": "2026-01-03", "rank": 1, "buy_cash": 1000, "net_pnl": 80, "net_return": 0.08}]}]},
    )


def setup_risk_control_fixture(root: Path, *, variants: bool) -> None:
    base = root / "artifacts" / "model_experiments"
    candidate = base / "training_candidates" / f"current_baseline_candidate_{RUN_DATE}"
    write_json(base / f"production_portfolio_replay_40d_{RUN_DATE}.json", {"summary": {"total_return": 0.1, "max_drawdown": -0.2}})
    if not variants:
        return
    rows = {
        "candidate_fixed40": ("candidate_portfolio_replay_40d.json", 0.13, -0.21),
        "candidate_top5": (f"portfolio_replay_candidate_fixed40_top5_{RUN_DATE}.json", 0.16, -0.19),
        "candidate_top7": (f"portfolio_replay_candidate_fixed40_top7_{RUN_DATE}.json", 0.15, -0.205),
        "candidate_sector55": (f"portfolio_replay_candidate_fixed40_sector55_{RUN_DATE}.json", 0.125, -0.18),
        "candidate_sector65": (f"portfolio_replay_candidate_fixed40_sector65_{RUN_DATE}.json", 0.14, -0.2),
    }
    for _label, (file_name, total_return, max_drawdown) in rows.items():
        write_json(
            candidate / file_name,
            {
                "summary": {
                    "total_return": total_return,
                    "max_drawdown": max_drawdown,
                    "trade_count": 10,
                    "win_rate": 0.6,
                    "avg_gross_exposure": 0.8,
                    "max_group_exposure": 0.5,
                }
            },
        )


def test_attribution_profile_preserves_default_output_console_json_and_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    setup_attribution_fixture(tmp_path)
    monkeypatch.setattr(builder, "PROJECT_ROOT", tmp_path.resolve())

    exit_code = builder.main(["--profile", "attribution", "--date", RUN_DATE])
    console = json.loads(capsys.readouterr().out)

    output = tmp_path / "artifacts/model_experiments/training_candidate_risk_attribution_2026-06-08.json"
    assert exit_code == 0
    assert console == {"status": "OK", "output": "artifacts/model_experiments/training_candidate_risk_attribution_2026-06-08.json"}
    payload = normalized_json(output)
    assert payload["schema_version"] == "training-candidate-risk-attribution.v1"
    assert payload["headline"]["fixed_share_default_return_on_buy_cash"]["delta"] == 0.04
    assert payload["headline"]["portfolio_40d_max_drawdown"]["delta"] == -0.03
    assert [row["id"] for row in payload["risk_hypotheses"]] == ["RET-01", "RISK-01", "SECTOR-01", "RANK-01"]
    assert output.with_suffix(".md").read_text(encoding="utf-8") == (
        "# Training Candidate Risk Attribution\n"
        "\n"
        "- status: OK\n"
        "- decision: KEEP_CANDIDATE_RESEARCH_WITH_RISK_CONTROLS\n"
        "- promotion_ready: False\n"
        "- fixed_share_return_delta: 0.04\n"
        "- portfolio_40d_return_delta: 0.08\n"
        "- portfolio_40d_max_drawdown_delta: -0.03\n"
        "- sector_max_buy_share_delta: 0.22\n"
        "\n"
        "## 白話結論\n"
        "\n"
        "候選模型比較會抓強股，但也更容易集中在同一族群、承受更深回撤；下一步先測風控，不直接上正式。\n"
        "\n"
        "## Risk Hypotheses\n"
        "\n"
        "- RET-01 KEEP_RESEARCH: 候選模型在 40D 波段與固定 100 股回測都有明顯報酬優勢。\n"
        "- RISK-01 NEEDS_CONTROL: 候選模型的 portfolio 最大回撤比 production 深，不能直接升正式。\n"
        "- SECTOR-01 TEST_CAP: 候選模型更集中在科技族群，報酬多半也來自科技，下一輪要測產業曝險上限。\n"
        "- RANK-01 TEST_RANK_SLICE: 候選模型的名次段不是全部等強，下一輪要測 top7/top4_7/top5 等排名切片。\n"
        "\n"
        "## Next Experiments\n"
        "\n"
        "- CAND-RISK-01: sector cap / industry concentration replay\n"
        "- CAND-RISK-02: rank slice replay\n"
        "- CAND-RISK-03: regime throttle replay\n"
        "- CAND-RISK-04: capital realistic odd-lot portfolio\n"
    )


def test_attribution_profile_preserves_missing_input_failure(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(builder, "PROJECT_ROOT", tmp_path.resolve())
    with pytest.raises(FileNotFoundError):
        builder.main(["--profile", "attribution", "--date", RUN_DATE])
    assert not (tmp_path / "artifacts/model_experiments/training_candidate_risk_attribution_2026-06-08.json").exists()


def test_risk_control_profile_preserves_default_output_console_json_markdown_and_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    setup_risk_control_fixture(tmp_path, variants=True)
    monkeypatch.setattr(builder, "PROJECT_ROOT", tmp_path.resolve())

    exit_code = builder.main(["--profile", "risk_control", "--date", RUN_DATE])
    console = json.loads(capsys.readouterr().out)

    output = tmp_path / "artifacts/model_experiments/training_candidate_risk_control_report_2026-06-08.json"
    assert exit_code == 0
    assert console == {
        "status": "OK",
        "decision": "RISK_CONTROL_REPLAY_CANDIDATE",
        "output": "artifacts/model_experiments/training_candidate_risk_control_report_2026-06-08.json",
    }
    payload = normalized_json(output)
    assert payload["schema_version"] == "training-candidate-risk-control-report.v1"
    assert payload["summary"] == {
        "variant_count": 5,
        "missing_count": 8,
        "best_by_research_score": "candidate_top5",
        "best_total_return": 0.16,
        "best_max_drawdown": -0.18,
    }
    assert payload["decision"]["selected"] == "candidate_top5"
    assert output.with_suffix(".md").read_text(encoding="utf-8") == (
        "# Training Candidate Risk Control Report\n"
        "\n"
        "- status: OK\n"
        "- decision: RISK_CONTROL_REPLAY_CANDIDATE\n"
        "- selected: candidate_top5\n"
        "- promotion_ready: False\n"
        "\n"
        "## Variants\n"
        "\n"
        "- candidate_top5: return=0.16, maxDD=-0.19, return_delta=0.06, dd_delta=0.01\n"
        "- candidate_top7: return=0.15, maxDD=-0.205, return_delta=0.05, dd_delta=-0.005\n"
        "- candidate_sector65: return=0.14, maxDD=-0.2, return_delta=0.04, dd_delta=0.0\n"
        "- candidate_sector55: return=0.125, maxDD=-0.18, return_delta=0.025, dd_delta=0.02\n"
        "- candidate_fixed40: return=0.13, maxDD=-0.21, return_delta=0.03, dd_delta=-0.01\n"
    )


def test_risk_control_profile_preserves_missing_variant_output_console_markdown_and_exit(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    setup_risk_control_fixture(tmp_path, variants=False)
    monkeypatch.setattr(builder, "PROJECT_ROOT", tmp_path.resolve())

    exit_code = builder.main(["--profile", "risk_control", "--date", RUN_DATE])
    console = json.loads(capsys.readouterr().out)

    output = tmp_path / "artifacts/model_experiments/training_candidate_risk_control_report_2026-06-08.json"
    assert exit_code == 1
    assert console == {
        "status": "FAILED",
        "decision": "NO_RISK_CONTROL_CANDIDATE",
        "output": "artifacts/model_experiments/training_candidate_risk_control_report_2026-06-08.json",
    }
    payload = normalized_json(output)
    assert payload["status"] == "FAILED"
    assert payload["summary"]["missing_count"] == 13
    assert payload["variants_ranked"] == []
    assert output.with_suffix(".md").read_text(encoding="utf-8") == (
        "# Training Candidate Risk Control Report\n"
        "\n"
        "- status: FAILED\n"
        "- decision: NO_RISK_CONTROL_CANDIDATE\n"
        "- selected: None\n"
        "- promotion_ready: False\n"
        "\n"
        "## Variants\n"
        "\n"
    )
