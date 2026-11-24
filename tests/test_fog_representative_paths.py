"""FOG-IO-001：只驗證路徑與命令，禁止啟動真實研究 workload。"""

import json
from pathlib import Path
import subprocess

import pytest
from scripts import run_fog_representative_validation as runner


def argument(command, flag):
    return command[command.index(flag) + 1]


@pytest.fixture
def roots(tmp_path, monkeypatch):
    source = tmp_path / "source"
    output = tmp_path / "fixture"
    (source / "artifacts").mkdir(parents=True)
    history = {"rows": [{"trade_date": runner.FIXTURE_DATE, **runner.FIXTURE_IDENTITY}]}
    (source / "artifacts/market_regime_history.json").write_text(json.dumps(history))
    monkeypatch.setattr(runner, "PROJECT_ROOT", source)
    monkeypatch.setattr(runner, "FIXTURE_ROOT", output)
    monkeypatch.setenv("TOP10_STORAGE_VALIDATION_MODE", "1")
    return source, output


def test_main_routes_absolute_source_and_separate_fixture(roots, monkeypatch, capsys):
    source, output = roots
    source_before = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    calls = []

    def run(command):
        calls.append(command)
        if len(calls) == 2:
            Path(argument(command, "--output")).write_text(json.dumps({"topic_runs": [{"topic": "fixture"}]}))
        return subprocess.CompletedProcess(command, 0, "published\nsha256:dynamic-intent\n", "")

    monkeypatch.setattr(runner, "run", run)
    assert runner.main() == 0
    assert len(calls) == 3
    publish, execute, verify = calls
    for command, script in zip(calls, ("publish_research_batch_intent.py", "run_autonomous_research.py", "verify_research_spine_batch.py")):
        assert command[:2] == [str(source / ".venv/bin/python"), str(source / "scripts" / script)]
    assert argument(execute, "--research-contract") == str(source / "config/regime_research_contract.json")
    assert argument(execute, "--candidate-dir") == str(source / runner.CANDIDATE_DIR)
    assert argument(execute, "--baseline-dir") == str(source / runner.BASELINE_DIR)
    assert argument(publish, "--manager-root") == str(output)
    assert argument(publish, "--ledger") == str(output / "research_ledger.duckdb")
    assert argument(publish, "--corpus-root") == argument(verify, "--corpus-root") == str(output / "research_spine")
    assert argument(execute, "--market-regime-history") == str(output / "market_regime_history.json")
    assert argument(execute, "--research-batch-intent") == str(output / "research_spine/batch_intents/dynamic-intent.json")
    assert publish[publish.index("--") + 1:] == execute[1:-2]
    for flag, value in (("--max-topics", "12"), ("--execute-topic-count", "1"), ("--development-screen-topic-count", "1"), ("--max-ranking-files", "8"), ("--date", "2026-08-31")):
        assert argument(execute, flag) == value
    for command, flag in ((publish, "--output"), (execute, "--output"), (verify, "--run-artifact"), (verify, "--output")):
        assert Path(argument(command, flag)).is_relative_to(output)
    result = json.loads(Path(argument(execute, "--output")).read_text())
    assert result["fixture_identity"] == runner.FIXTURE_IDENTITY
    assert result["production_promotion_allowed"] is False
    assert (output / "market_regime_history.json").read_bytes() == (source / "artifacts/market_regime_history.json").read_bytes()
    assert json.loads(capsys.readouterr().out)["output"] == argument(execute, "--output")
    assert source_before == {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}


def test_command_builder_is_offline_and_preserves_batch_identity(tmp_path, monkeypatch):
    source, output = tmp_path / "uncreated-source", tmp_path / "uncreated-fixture"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("不得啟動 workload"))
    plan = runner.build_commands(source, output, "fixed-batch")
    assert not source.exists() and not output.exists()
    assert plan["source_history"] == source / "artifacts/market_regime_history.json"
    assert plan["fixture_history"] == output / "market_regime_history.json"
    assert argument(plan["publish"], "--batch-id") == "fixed-batch"
    assert argument(plan["execute"], "--research-batch-id") == "fixed-batch"
    assert argument(plan["verify"], "--batch-id") == "fixed-batch"
    assert "--research-batch-intent" not in plan["execute"]
    assert argument(plan["publish"], "--requested-research-stage") == "DEVELOPMENT_SCREEN"
    assert argument(plan["publish"], "--allowed-research-stage") == "DEVELOPMENT_SCREEN"
    assert "--closed-regime-research" in plan["execute"]
    assert "--development-screen-on-sealed-exhaustion" in plan["execute"]


@pytest.mark.parametrize("gate,reason", [
    ("mode", "VALIDATION_MODE_REQUIRED"), ("git-dir", "NO_GIT_VALIDATION_ROOT_REQUIRED"),
    ("git-file", "NO_GIT_VALIDATION_ROOT_REQUIRED"),
])
def test_main_gates_precede_construction_and_writes(roots, monkeypatch, capsys, gate, reason):
    source, output = roots
    if gate == "mode":
        monkeypatch.delenv("TOP10_STORAGE_VALIDATION_MODE")
    elif gate == "git-dir":
        (source / ".git").mkdir()
    else:
        (source / ".git").write_text("gitdir: elsewhere")
    monkeypatch.setattr(runner, "build_commands", lambda *a: pytest.fail("gate 前不得建構"))
    monkeypatch.setattr(runner, "run", lambda *a: pytest.fail("gate 前不得執行"))
    assert runner.main() == 1
    assert json.loads(capsys.readouterr().err)["reason_code"] == reason
    assert not output.exists()


@pytest.mark.parametrize("bad_rows", [[], [
    {"trade_date": "2026-08-31", "base_regime": "OTHER", "family_tags": ["BIG_BULL", "HIGH_CHOPPY"]}
], [{"trade_date": "2026-08-31", **runner.FIXTURE_IDENTITY}] * 2])
def test_identity_mismatch_never_publishes(roots, monkeypatch, capsys, bad_rows):
    source, _ = roots
    (source / "artifacts/market_regime_history.json").write_text(json.dumps({"rows": bad_rows}))
    monkeypatch.setattr(runner, "run", lambda *a: pytest.fail("identity 不符不得執行"))
    assert runner.main() == 1
    assert json.loads(capsys.readouterr().err)["reason_code"] == "FIXTURE_REGIME_IDENTITY_MISMATCH"


@pytest.mark.parametrize("phase,reason", [
    (1, "BATCH_INTENT_PUBLICATION_FAILED"), (2, "REPRESENTATIVE_TOPIC_EXECUTION_FAILED"),
    (3, "REPRESENTATIVE_BATCH_VERIFICATION_FAILED"),
])
def test_phase_failure_stops_following_commands(roots, monkeypatch, capsys, phase, reason):
    calls = []

    def run(command):
        calls.append(command)
        return subprocess.CompletedProcess(command, 7 if len(calls) == phase else 0, "sha256:returned-intent\n", "fixture failure")

    monkeypatch.setattr(runner, "run", run)
    assert runner.main() == 1
    assert len(calls) == phase
    payload = json.loads(capsys.readouterr().err)
    assert payload["reason_code"] == reason
    assert payload["returncode"] == 7


def test_empty_topic_runs_remain_failure(roots, monkeypatch, capsys):
    calls = []

    def run(command):
        calls.append(command)
        if len(calls) == 2:
            Path(argument(command, "--output")).write_text('{"topic_runs": []}')
        return subprocess.CompletedProcess(command, 0, "sha256:returned-intent\n", "")

    monkeypatch.setattr(runner, "run", run)
    assert runner.main() == 1
    assert len(calls) == 3
    assert json.loads(capsys.readouterr().err)["reason_code"] == "REPRESENTATIVE_WORKLOAD_EMPTY"


def test_explicit_shared_root_keeps_git_check_on_sandbox(roots, monkeypatch, capsys):
    source, sandbox = roots
    sandbox.mkdir()
    (source / ".git").mkdir()
    relative = Path("artifacts/autonomous_research/validation_fixture")
    monkeypatch.setattr(runner, "FIXTURE_ROOT", relative)
    calls = []
    monkeypatch.setattr(runner, "run", lambda command: calls.append(command) or subprocess.CompletedProcess(command, 7, "", "fixture"))
    assert runner.main() == 1
    assert json.loads(capsys.readouterr().err)["reason_code"] == "NO_GIT_VALIDATION_ROOT_REQUIRED"
    assert not calls
    assert runner.main(validation_root=sandbox) == 1
    assert json.loads(capsys.readouterr().err)["reason_code"] == "BATCH_INTENT_PUBLICATION_FAILED"
    assert (sandbox / relative / "market_regime_history.json").is_file()
    assert not (source / relative).exists()
    assert runner.main(validation_root=source) == 1
    assert json.loads(capsys.readouterr().err)["reason_code"] == "OVERLAPPING_SHARED_VALIDATION_ROOT"
