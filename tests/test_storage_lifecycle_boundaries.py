"""外接 driver 內的真實 Git fixture；不建立套件環境、不複製專案資料。"""

import json
import hashlib
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

import pytest

from scripts import prepare_runtime_checkout as prepare
from scripts import storage_safety
from scripts.storage_validation import boundary, daily
from tests.test_daily_storage_validation import write_runner_source_fixture, write_representative_snapshot


@pytest.fixture
def tmp_path(tmp_path_factory):
    """仍使用 pytest basetemp；避免每個案例額外留下 numbered current symlink。"""
    return tmp_path_factory.mktemp("boundary-" + uuid.uuid4().hex, numbered=False)


def repo(path):
    path.mkdir()
    prepare.git(path, "init", "-b", "main")
    prepare.git(path, "config", "user.email", "fixture@example.invalid")
    prepare.git(path, "config", "user.name", "Fixture")
    return path


@pytest.fixture
def runtime_fixture(tmp_path):
    source = repo(tmp_path / "source")
    for name in prepare.DEPENDENCIES:
        (source / name).write_text("fixture-dependency\n")
    (source / "main.py").write_text("pass\n")
    (source / ".gitignore").write_text(".venv/\n")
    for name in prepare.EXCLUDED[:-1]:
        (source / name).mkdir()
        (source / name / "must-not-copy").write_bytes(b"fixture-data")
    prepare.git(source, "add", ".")
    prepare.git(source, "commit", "-m", "fixture")
    commit = prepare.git(source, "rev-parse", "HEAD")
    environment = source / ".venv"
    (environment / "bin").mkdir(parents=True)
    (environment / "pyvenv.cfg").write_text("fixture-only\n")
    python = environment / "bin/python"
    python.write_text("#!/bin/sh\nexit 0\n")
    python.chmod(0o700)
    return source, tmp_path / "runtime", commit, environment


def test_prepare_reuses_same_commit_without_data_or_environment_copy(runtime_fixture):
    source, runtime, commit, environment = runtime_fixture
    first = prepare.prepare_runtime(*runtime_fixture)
    second = prepare.prepare_runtime(*runtime_fixture)
    assert not first["reused"] and second["reused"]
    assert (runtime / ".venv").is_symlink()
    assert (runtime / ".venv").resolve() == environment
    assert not any((runtime / name).exists() for name in prepare.EXCLUDED[:-1])
    (runtime / ".venv").unlink()
    prepare.git(source, "worktree", "remove", str(runtime))


@pytest.mark.parametrize("case", ["dirty", "ignored", "lock", "unknown"])
def test_prepare_preserves_unknown_or_dirty_work(runtime_fixture, case):
    source, runtime, commit, environment = runtime_fixture
    if case == "unknown":
        runtime.mkdir()
        sentinel = runtime / "unique.txt"
        sentinel.write_text("keep")
    else:
        prepare.prepare_runtime(*runtime_fixture)
        if case == "dirty":
            sentinel = runtime / "main.py"
        elif case == "ignored":
            (runtime / ".gitignore").write_text("unique.txt\n")
            sentinel = runtime / "unique.txt"
        else:
            sentinel = source / "uv.lock"
        sentinel.write_text("keep")
    with pytest.raises((ValueError, RuntimeError, subprocess.SubprocessError)):
        prepare.prepare_runtime(*runtime_fixture)
    assert sentinel.read_text() == "keep"
    # 只移除本測試建立的 symlink，unique 內容由外層 fixture owner 保留至 cleanup。
    if (runtime / ".venv").is_symlink():
        (runtime / ".venv").unlink()


def test_prepare_failure_rolls_back_only_clean_created_worktree(runtime_fixture, monkeypatch):
    original = prepare.validate_prepared_runtime
    monkeypatch.setattr(prepare, "validate_prepared_runtime", lambda *a: (_ for _ in ()).throw(RuntimeError("injected")))
    with pytest.raises(RuntimeError, match="injected"):
        prepare.prepare_runtime(*runtime_fixture)
    assert not runtime_fixture[1].exists()
    monkeypatch.setattr(prepare, "validate_prepared_runtime", original)


def test_prepare_failure_keeps_unique_created_worktree(runtime_fixture, monkeypatch):
    def fail(source, runtime, *args):
        (runtime / "unique.txt").write_text("keep")
        raise RuntimeError("injected")
    monkeypatch.setattr(prepare, "validate_prepared_runtime", fail)
    with pytest.raises(RuntimeError, match="injected"):
        prepare.prepare_runtime(*runtime_fixture)
    runtime = runtime_fixture[1]
    assert (runtime / "unique.txt").read_text() == "keep"
    (runtime / ".venv").unlink()


@pytest.mark.parametrize("phase", ["add", "link", "unique-link"])
def test_prepare_sigterm_at_side_effect_boundaries(runtime_fixture, phase):
    source, runtime, commit, environment = runtime_fixture
    script = r'''
import os, signal, sys
from pathlib import Path
from scripts import prepare_runtime_checkout as p
phase, source, runtime, commit, environment = sys.argv[1:]
original_git, original_link = p.git, Path.symlink_to
def git(root, *args):
    result = original_git(root, *args)
    if phase == "add" and args[:2] == ("worktree", "add"):
        os.kill(os.getpid(), signal.SIGTERM)
    return result
def link(self, *args, **kwargs):
    result = original_link(self, *args, **kwargs)
    if self == Path(runtime) / ".venv":
        if phase == "unique-link":
            (Path(runtime) / "unique.txt").write_text("keep")
        if phase in ("link", "unique-link"):
            os.kill(os.getpid(), signal.SIGTERM)
    return result
p.git, Path.symlink_to = git, link
raise SystemExit(p.main(["--source-root", source, "--runtime-root", runtime,
                         "--accepted-commit", commit, "--environment-root", environment]))
'''
    result = subprocess.run([sys.executable, "-B", "-c", script, phase, str(source),
                             str(runtime), commit, str(environment)], capture_output=True, text=True, timeout=30)
    assert result.returncode == 143, (result.stdout, result.stderr)
    assert '"reused"' not in result.stdout
    if phase == "unique-link":
        assert (runtime / "unique.txt").read_text() == "keep"
        assert "KEEP_UNIQUE" in result.stderr
        (runtime / ".venv").unlink()
    else:
        assert not runtime.exists(), result.stderr


def test_prepare_rejects_internal_target(runtime_fixture):
    source, _, commit, environment = runtime_fixture
    target = Path("/Users/mattkuo/TOP10new/forbidden-runtime")
    with pytest.raises(ValueError, match="外接"):
        prepare.prepare_runtime(source, target, commit, environment)
    assert not target.exists()


@pytest.mark.parametrize("limit", ["size", "count"])
def test_daily_cli_export_limit_cannot_report_ok(tmp_path, monkeypatch, capsys, limit):
    source = tmp_path / "source"
    source.mkdir()
    output = tmp_path / "output"
    def oversized(**kwargs):
        runtime = output / "logs/storage_safety/runtime/daily"
        runtime.mkdir(parents=True)
        for index in range(9 if limit == "count" else 1):
            receipt = runtime / f"daily_validation_{index}.json"
            receipt.write_text("x" * (1024 * 1024 + 1) if limit == "size" else "{}")
        return receipt
    monkeypatch.setattr(daily, "run_validation_cycle", oversized)
    assert daily.main(["--source-root", str(source), "--output-root", str(output),
                       "--run-date", "2026-11-18", "--cycle-id", "limit", "--snapshot-input", str(source / "input")]) == 1
    assert '"status": "OK"' not in capsys.readouterr().out


def test_validation_rejects_internal_and_unknown_before_write(tmp_path):
    for target in (Path("/Users/mattkuo/TOP10new/forbidden-validation-output"), Path("/Volumes/VibeCode/unknown-output"),
                   Path(os.environ["AI_CORE_EXTERNAL_DEV_REPO"])):
        existed = target.exists()
        with pytest.raises(ValueError):
            daily.run_validation_cycle(source_root=tmp_path, output_root=target,
                                       run_date="2026-11-18", cycle_id="boundary")
        assert target.exists() == existed


def test_validation_rejects_symlink_before_write(tmp_path):
    target = tmp_path / "alias"
    target.symlink_to(tmp_path, target_is_directory=True)
    try:
        with pytest.raises(ValueError, match="symlink"):
            boundary.owned_validation_paths(target / "output")
        assert not (tmp_path / "output").exists()
    finally:
        target.unlink()


@pytest.mark.parametrize("case", ["same", "child", "parent", "source-alias"])
def test_daily_rejects_source_overlap_and_alias_before_mkdir(tmp_path, case):
    source = tmp_path / "source"
    source.mkdir()
    sentinel = source / "unique.txt"
    sentinel.write_text("keep")
    output = source if case == "same" else source / "new-output" if case == "child" else tmp_path
    alias = tmp_path / "alias"
    if case == "source-alias":
        alias.symlink_to(source, target_is_directory=True)
        source = alias
        output = tmp_path / "new-output"
    try:
        with pytest.raises(ValueError, match="重疊|symlink"):
            daily.run_validation_cycle(source_root=source, output_root=output,
                                       run_date="2026-11-18", cycle_id="boundary")
        assert sentinel.read_text() == "keep"
        assert not (output / "logs").exists()
    finally:
        if alias.is_symlink():
            alias.unlink()


@pytest.mark.parametrize("shared", [False, True])
def test_validate_run_rejects_internal_before_policy_or_mkdir(monkeypatch, shared):
    internal = Path("/Users/mattkuo/TOP10new")
    monkeypatch.setattr(storage_safety, "PROJECT_ROOT", internal)
    monkeypatch.setattr(storage_safety, "load_policy", lambda *a: pytest.fail("reached policy"))
    args = ["validate-run", "--job", "fog-research-worker", "--marker", str(internal / "marker"),
            "--max-runtime-seconds", "1", "--source-input-root", str(internal),
            "--sandbox-input-root", str(internal), "--sandbox-output-root", str(internal),
            "--entrypoint-contract", str(internal / "contract")]
    if shared:
        args += ["--sandbox-root", str(internal)]
    with pytest.raises(ValueError, match="外接"):
        storage_safety.main(args)


@pytest.mark.parametrize("case", ["missing", "uuid", "capacity"])
def test_external_gate_fails_closed(tmp_path, monkeypatch, case):
    if case == "uuid":
        # 不完整契約會依 Core 規則重載本機身分；先明示完整契約再注入 UUID 漂移。
        tool = boundary.core_module("cache_tool")
        environment = tool.load_environment(dict(os.environ))
        for key in tool.CONTRACT:
            monkeypatch.setenv(key, environment[key])
        monkeypatch.setenv("AI_CORE_CACHE_VOLUME_UUID", "00000000-0000-0000-0000-000000000000")
    elif case == "missing":
        monkeypatch.setattr(Path, "is_mount", lambda p: False)
    else:
        cache_class = boundary.core_module("runtime_cache_capacity_gate").ManagedCache
        monkeypatch.setattr(cache_class, "sample", lambda self: {"effective_available_bytes": 0, "required_available_bytes": 1})
    with pytest.raises((ValueError, RuntimeError)):
        with boundary.external_paths(tmp_path / "not-created"):
            pytest.fail("writer reached")
    assert not (tmp_path / "not-created").exists()


def test_capacity_bootstrap_reports_inherited_hook_failure():
    """真實重現 validation 清 cache 契約後，舊 sensor 啟動受到 inherited hook 拒絕。"""
    core = Path(os.environ.get("AI_CORE_DIR", str(Path.home() / "ai-core")))
    env = {key: value for key, value in os.environ.items() if not key.startswith("AI_CORE_CACHE_")}
    # 單元批次不繼承 hook；本負例須明示它所驗證的實際啟動接點。
    env["PYTHONPATH"] = os.pathsep.join(filter(None, [str(core / "scripts/_storage_python"), env.get("PYTHONPATH")]))
    legacy = subprocess.run([str(core / ".venv/bin/python"), "-B", "-c", "print('BOOTSTRAP_OK')"],
                            env=env, capture_output=True, text=True, timeout=15)
    evidence = Path(os.environ["TMP_ARTIFACT_ROOT"]) / "evidence/capacity-bootstrap.json"
    evidence.write_text(json.dumps({"exit_code": legacy.returncode, "stderr": legacy.stderr,
                                    "stdout": legacy.stdout, "pythonpath": env.get("PYTHONPATH")}, indent=2))
    assert legacy.returncode == 78
    assert "CACHE_PYTHON_TEMP_DENIED" in legacy.stderr


def test_capacity_sensor_isolates_hook_without_mock_or_fallback(tmp_path, monkeypatch):
    from app.storage_safety import _measure_host_capacity

    for key in tuple(os.environ):
        if key.startswith("AI_CORE_CACHE_"):
            monkeypatch.delenv(key)
    total, raw, admission, source = _measure_host_capacity(tmp_path)
    assert 0 < raw <= admission <= total
    assert source == "macos_foundation_important_usage"
    evidence = Path(os.environ["TMP_ARTIFACT_ROOT"]) / "evidence/capacity-sensor-isolated.json"
    evidence.write_text(json.dumps({"total_bytes": total, "raw_bytes": raw,
                                    "admission_bytes": admission, "source": source}, indent=2))


@pytest.mark.parametrize("mode", ["success", "success", "failure", "signal"])
def test_daily_cli_lifecycle_cleanup_and_small_evidence(tmp_path, mode):
    owner = repo(tmp_path / "owner")
    source = tmp_path / "fixture-source"
    source.mkdir()
    write_runner_source_fixture(source)
    snapshot = write_representative_snapshot(source)
    runner = source / "scripts/run_automation.py"
    if mode == "failure":
        runner.write_text("raise RuntimeError('injected failure')\n")
    elif mode == "signal":
        runner.write_text("import os, time\nfrom pathlib import Path\n"
                          "(Path(os.environ['TMP_ARTIFACT_ROOT']) / 'daily-signal-ready').write_text('ready')\n"
                          "time.sleep(90)\n")
    evidence = owner / "receipt"
    env = boundary.core_module("cache_tool").load_environment(dict(os.environ))
    for key in ("AI_CORE_TMP_ARTIFACT_ACTIVE", "TMP_ARTIFACT_ROOT", "AI_CORE_EXTERNAL_DEV_REPO"):
        env.pop(key, None)
    controller_evidence = Path(env["TOP10_NATIVE_TEST_EVIDENCE_ROOT"])
    assert controller_evidence.is_absolute() and controller_evidence.is_dir()
    # 模擬 lifecycle 外的 bootstrap：仍指向已存在的受管外接 cache，保留 sitecustomize。
    # 進入新 lifecycle 後 helper 會重新固定為新 owned/tmp，不借用外層 root 身分。
    for key in ("TMPDIR", "TMP", "TEMP", "TEMPDIR", "JOBLIB_TEMP_FOLDER"):
        env[key] = env["AI_CORE_CACHE_ROOT"]
    command = [sys.executable, "-B", str(Path(daily.__file__)), "--source-root", str(source),
               "--run-date", "2026-08-27", "--cycle-id", mode, "--snapshot-input", str(snapshot),
               "--lifecycle-owner", str(owner), "--evidence-dir", str(evidence)]
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    marker = owner / ".git/.ai-core-tmp-artifact-isolation.json"
    root = None
    sent = False
    stdout = stderr = ""
    timed_out = False
    deadline = time.monotonic() + 45
    try:
        while time.monotonic() < deadline and process.poll() is None:
            try:
                state = json.loads(marker.read_text())
            except FileNotFoundError:
                state = {}
            if state.get("root"):
                root = Path(state["root"])
                if (mode == "signal" and state.get("status") == "active"
                        and (root / "daily-signal-ready").is_file()
                        and list(root.glob("evidence/daily-*/summary.json"))):
                    process.send_signal(signal.SIGTERM)
                    sent = True
                    break
            time.sleep(0.1)
        stdout, stderr = process.communicate(timeout=45)
    except subprocess.TimeoutExpired:
        timed_out = True
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                stdout, stderr = process.communicate(timeout=15)
            except subprocess.TimeoutExpired as error:
                timed_out = True
                stdout = (error.stdout or b"").decode(errors="replace")
                stderr = (error.stderr or b"").decode(errors="replace")
    summaries = list(evidence.glob("evidence/daily-*/summary.json"))
    summary_payloads = [json.loads(p.read_text()) for p in summaries]
    # 快速成功可能在兩次輪詢間完成；匯出的原 summary 仍保存實際 root 身分。
    if root is None and summary_payloads:
        root = Path(summary_payloads[0]["output_root"]).parent
    kept = controller_evidence / ("daily-lifecycle-" + uuid.uuid4().hex + ".json")
    kept.write_text(json.dumps({"mode": mode, "exit_code": process.returncode,
                               "owned_root": str(root), "cleanup_removed": bool(root and not root.exists()),
                               "marker_exists": marker.exists(), "sent": sent, "timed_out": timed_out,
                               "summaries": summary_payloads,
                               "stdout": stdout[-4096:], "stderr": stderr[-4096:],
                               "receipts": [json.loads(p.read_text()) for p in evidence.rglob("daily_validation_*.json")]},
                              ensure_ascii=False, indent=2))
    assert not timed_out, (stdout, stderr)
    assert (process.returncode == 0) == (mode == "success"), (stdout, stderr)
    assert root is not None and not root.exists(), (stdout, stderr)
    assert root.parent == boundary.core_module("tmp_artifact_lifecycle").MANAGED_TMP_PARENT
    assert not marker.exists()
    assert summaries, (stdout, stderr)
    assert sum(p.stat().st_size for p in evidence.rglob("*") if p.is_file()) < 2 * 1024**2
    assert not any(p.name in {"data", ".venv"} for p in evidence.rglob("*"))
    if mode == "success":
        result = json.loads(stdout.strip().splitlines()[-1])
        retained = Path(result["receipt_path"])
        assert retained.is_relative_to(evidence)
        receipt_bytes = retained.read_bytes()
        assert hashlib.sha256(receipt_bytes).hexdigest() == result["receipt_sha256"]
        assert json.loads(receipt_bytes)["status"] == "OK"
    elif mode == "failure":
        assert process.returncode == 1 and "injected failure" in stderr
        assert any(p.get("status") == "FAILED" and p.get("error") == "RuntimeError"
                   for p in summary_payloads)
    else:
        assert sent and process.returncode == 128 + signal.SIGTERM, (stdout, stderr)
