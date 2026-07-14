from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import run_shadow_research_campaign as runner


RUN_DATE = "2026-06-18"


class Completed:
    def __init__(self, returncode: int = 0, stdout: str = "ok", stderr: str = "") -> None:
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def configure_root(root: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(runner, "PROJECT_ROOT", root)


def normalized_payload(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.pop("generated_at", None)
    for step in payload.get("steps", []):
        step.pop("started_at", None)
        step.pop("finished_at", None)
        step.pop("ended_at", None)
    return payload


@pytest.mark.parametrize(
    ("stage_args", "command_count"),
    [
        (["a1-forward", "--date", RUN_DATE], 4),
        (["candidate-stress", "--date", RUN_DATE], 60),
        (["overnight-training", "--date", RUN_DATE, "--model-hash-before", "hash"], 23),
        (["risk-matrix-summary", "--date", RUN_DATE, "--model-hash-before", "hash"], 0),
    ],
)
def test_global_dry_run_writes_only_explicit_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stage_args: list[str],
    command_count: int,
) -> None:
    configure_root(tmp_path, monkeypatch)
    stage_output = runner.stage_output_path(runner.parse_args(stage_args))
    stage_output.parent.mkdir(parents=True, exist_ok=True)
    stage_output.write_bytes(b"existing-stage-artifact")
    steps_log = tmp_path / "artifacts/model_experiments" / f"overnight_training_steps_{RUN_DATE}_extended.tsv"
    steps_log.parent.mkdir(parents=True, exist_ok=True)
    steps_log.write_bytes(b"existing-steps-log")

    calls: list[list[str]] = []

    def forbidden(command: list[str], **_: Any) -> Completed:
        calls.append(command)
        raise AssertionError("global dry-run must not start subprocess")

    monkeypatch.setattr(runner.subprocess, "run", forbidden)
    manifest = tmp_path / "campaign-dry-run.json"
    assert runner.main(["--dry-run", "--output", str(manifest), *stage_args]) == 0
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    assert payload["dry_run"] is True
    assert payload["status"] == "SKIPPED"
    assert payload["stages"][0]["status_history"] == ["planned", "SKIPPED"]
    assert len(payload["stages"][0]["command"]) == command_count
    assert payload["stages"][0]["returncode"] is None
    assert calls == []
    assert stage_output.read_bytes() == b"existing-stage-artifact"
    assert steps_log.read_bytes() == b"existing-steps-log"

    manifest.unlink()
    assert runner.main(["--dry-run", *stage_args]) == 0
    assert list(tmp_path.rglob("shadow_research_campaign_*.json")) == []


def test_a1_valid_and_failure_preserve_payload_console_and_continue_semantics(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_root(tmp_path, monkeypatch)
    args = runner.parse_args(["a1-forward", "--date", RUN_DATE])
    paths = runner.a1_paths(args)
    write_json(paths["shadow_ranking_summary"], {"outputs": [1, 2], "inputs": {"date_count": 2}})
    write_json(paths["constrained_summary"], {"summary": {"date_count": 2, "avg_overlap_count": 7.5}})
    write_json(paths["baseline_replay"], {"summary": {"trade_count": 4}})
    write_json(
        paths["candidate_replay"],
        {
            "summary": {"trade_count": 3, "skipped_count": 1, "total_return": 0.12, "max_drawdown": -0.03},
            "skipped": [{"ranking_date": "2026-06-17", "reason": "pending"}],
        },
    )
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: Any) -> Completed:
        calls.append(command)
        return Completed(returncode=5 if len(calls) == 2 else 0, stdout=f"step-{len(calls)}")

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.main(["a1-forward", "--date", RUN_DATE]) == 1
    console = json.loads(capsys.readouterr().out)
    output = tmp_path / console["output"]
    payload = normalized_payload(output)
    assert len(calls) == 4
    assert [step["status"] for step in payload["steps"]] == ["OK", "FAILED", "OK", "OK"]
    assert payload["schema_version"] == "a1-forward-shadow-monitor.v1"
    assert payload["monitor_status"] == "READY_WITH_MATURE_OUTCOMES"
    assert payload["lane"] == {
        "id": "A1",
        "candidate": "sector_context_production_top7_shadow_fill3",
        "scenario": "top10_h5_d1_gc25",
        "entry": "D+1 open",
        "horizon_trade_days": 5,
        "group_cap": 0.25,
        "min_production_count": 7,
        "top_n": 10,
    }
    assert console == {"status": "FAILED", "monitor_status": "READY_WITH_MATURE_OUTCOMES", "output": runner.repo_path(output), **payload["summary"]}
    assert output.with_suffix(".md").read_text(encoding="utf-8") == runner.render_a1_markdown(json.loads(output.read_text(encoding="utf-8")))
    manifest = tmp_path / "artifacts/model_experiments" / f"shadow_research_campaign_{RUN_DATE}_a1-forward.json"
    assert json.loads(manifest.read_text(encoding="utf-8"))["stages"][0]["returncode"] == 1


def test_a1_reuse_existing_with_missing_artifacts_skips_all_subprocesses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_root(tmp_path, monkeypatch)
    monkeypatch.setattr(runner.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("reuse-existing started subprocess"))
    assert runner.main(["a1-forward", "--date", RUN_DATE, "--reuse-existing"]) == 0
    console = json.loads(capsys.readouterr().out)
    payload = normalized_payload(tmp_path / console["output"])
    assert payload["monitor_status"] == "PENDING_OUTCOMES"
    assert payload["steps"] == [
        {"name": "reuse_existing", "status": "OK", "returncode": 0, "command": [], "stdout": "", "stderr": ""}
    ]
    assert all(value is None for key, value in payload["summary"].items() if key not in {"shadow_ranking_count", "pending_reasons"})


@pytest.mark.parametrize("with_artifacts", [True, False], ids=["valid", "missing"])
def test_candidate_stage_dry_run_preserves_matrix_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    with_artifacts: bool,
) -> None:
    configure_root(tmp_path, monkeypatch)
    if with_artifacts:
        for scenario_index, scenario in enumerate(runner.SCENARIOS):
            for variant_index, variant in enumerate(runner.VARIANTS):
                write_json(
                    runner.stress_output_path(variant, scenario, RUN_DATE),
                    {"summary": {"total_return": 0.10 + variant_index / 100, "max_drawdown": -0.10 + scenario_index / 1000}},
                )

    monkeypatch.setattr(runner.subprocess, "run", lambda *_args, **_kwargs: pytest.fail("stage dry-run started subprocess"))
    assert runner.main(["candidate-stress", "--date", RUN_DATE, "--dry-run"]) == 0
    console = json.loads(capsys.readouterr().out)
    output = tmp_path / console["output"]
    payload = normalized_payload(output)
    assert payload["schema_version"] == "candidate-stress-matrix.v1"
    assert len(payload["rows"]) == 60
    assert payload["summary"]["candidate_rows"] == 48
    assert payload["summary"]["ready_for_shadow_monitor"] == (48 if with_artifacts else 0)
    assert all(row["decision"] == "INSUFFICIENT_DATA" for row in payload["rows"] if row["variant"] != "baseline") is (not with_artifacts)
    assert console == {"status": "OK", "output": runner.repo_path(output), **payload["summary"]}
    assert output.with_suffix(".md").read_text(encoding="utf-8") == runner.render_stress_markdown(json.loads(output.read_text(encoding="utf-8")))


def test_candidate_subprocess_failure_is_fail_fast_and_records_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    configure_root(tmp_path, monkeypatch)
    calls = 0

    def fail_second(command: list[str], **_: Any) -> Completed:
        nonlocal calls
        calls += 1
        if calls == 2:
            raise subprocess.CalledProcessError(7, command)
        return Completed()

    monkeypatch.setattr(runner.subprocess, "run", fail_second)
    with pytest.raises(subprocess.CalledProcessError) as error:
        runner.main(["candidate-stress", "--date", RUN_DATE])
    assert error.value.returncode == 7
    assert calls == 2
    assert not (tmp_path / "artifacts/model_experiments" / f"candidate_stress_matrix_{RUN_DATE}.json").exists()
    manifest = tmp_path / "artifacts/model_experiments" / f"shadow_research_campaign_{RUN_DATE}_candidate-stress.json"
    stage = json.loads(manifest.read_text(encoding="utf-8"))["stages"][0]
    assert stage["status"] == "FAILED"
    assert stage["returncode"] == 1


def test_overnight_failure_continues_and_preserves_tsv_and_tail_contract(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_root(tmp_path, monkeypatch)
    calls: list[list[str]] = []

    def fake_run(command: list[str], **_: Any) -> Completed:
        calls.append(command)
        return Completed(returncode=9 if len(calls) == 3 else 0, stdout="x" * 3500, stderr="y" * 3500)

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    assert runner.main(["overnight-training", "--date", RUN_DATE, "--model-hash-before", "hash", "--keeps", "6"]) == 1
    console = json.loads(capsys.readouterr().out)
    payload = normalized_payload(tmp_path / console["output"])
    assert len(calls) == 11
    assert calls[-1][1] == "scripts/build_overnight_training_summary.py"
    assert [step["status"] for step in payload["steps"]].count("FAILED") == 1
    assert all(len(step["stdout_tail"]) == 3000 for step in payload["steps"])
    assert all(len(step["stderr_tail"]) == 3000 for step in payload["steps"])
    steps_log = tmp_path / console["steps_log"]
    rows = steps_log.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 11
    assert rows[2].split("\t")[:2] == ["feature_group.shadow_ranking", "FAILED"]


@pytest.mark.parametrize(
    ("baseline_exists", "matching_hash", "expected_status", "expected_exit"),
    [(True, True, "OK", 0), (False, True, "FAILED", 1), (True, False, "FAILED", 1)],
    ids=["valid", "missing", "hash-failure"],
)
def test_risk_matrix_valid_missing_and_hash_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    baseline_exists: bool,
    matching_hash: bool,
    expected_status: str,
    expected_exit: int,
) -> None:
    configure_root(tmp_path, monkeypatch)
    model = tmp_path / "model.pkl"
    model.write_bytes(b"model-fixture")
    model_hash = hashlib.sha256(model.read_bytes()).hexdigest()
    baseline = {"summary": {}, "scenarios": [{"scenario_id": "base", "total_return": 0.1, "max_drawdown": -0.1, "score": 1.0, "win_rate": 0.5}]}
    if baseline_exists:
        write_json(tmp_path / f"artifacts/backtest/strategy_matrix_baseline_half_year_dense_{RUN_DATE}.json", baseline)
    for candidate in ("sector_context_k7", "feature_group_k7", "feature_group_k8"):
        write_json(
            tmp_path / f"artifacts/backtest/strategy_matrix_{candidate}_half_year_dense_{RUN_DATE}.json",
            {"summary": {}, "scenarios": [{"scenario_id": candidate, "total_return": 0.2, "max_drawdown": -0.05, "score": 2.0, "win_rate": 0.6}]},
        )
    supplied_hash = model_hash if matching_hash else "wrong"
    assert runner.main(["risk-matrix-summary", "--date", RUN_DATE, "--model", str(model), "--model-hash-before", supplied_hash]) == expected_exit
    console = json.loads(capsys.readouterr().out)
    output = tmp_path / console["output"]
    payload = normalized_payload(output)
    assert payload["status"] == expected_status
    assert console == {"status": expected_status, "output": runner.repo_path(output), "errors": payload["errors"]}
    assert output.with_suffix(".md").read_text(encoding="utf-8") == runner.render_risk_markdown(json.loads(output.read_text(encoding="utf-8")))
