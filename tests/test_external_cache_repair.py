"""Repair 1 的三個有界反例；不啟動正式工作。"""

import fcntl
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys

import pytest
import app.storage_safety as guard
from app.external_cache import ExternalCache, ExternalCacheError, FIELDS, runtime_environment
from tests.test_external_cache_wiring import external, RULES, sample
from tests.test_storage_safety import fixture_global_policy, fixture_job_policy, wrapper_toolchain_fixture


def test_configured_isolation_rejected_before_writes(tmp_path, external, monkeypatch):
    from scripts import storage_safety as cli
    from scripts.run_automation import AutomationRunner
    from scripts.run_isolated_daily_backfill import command_env, prepare_runtime, run_backfill
    from scripts.storage_validation import fog_research_worker as fog
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.delenv("TOP10_EXTERNAL_CACHE_ROOT", raising=False)
    for operation in (
        lambda: cli.configure_validation_runtime("daily"),
        lambda: AutomationRunner("daily", output_root=tmp_path / "output", validation_mode=True),
        lambda: command_env(tmp_path / "output", tmp_path / "runtime"),
        lambda: prepare_runtime(tmp_path / "runtime"),
        lambda: run_backfill(None),
    ):
        with pytest.raises(ExternalCacheError, match="ISOLATION_UNSUPPORTED"):
            operation()
    monkeypatch.setattr(sys, "argv", ["fog", "--runner-sha256", "0" * 64, "--source-commit", "0" * 40])
    with pytest.raises(SystemExit) as error:
        fog.main()
    assert error.value.code == 78
    assert not (tmp_path / "runtime").exists()
    assert not (tmp_path / "output").exists()
    assert not (tmp_path / "logs").exists()


@pytest.mark.parametrize("stage", ["environment", "contract", "toolchain", "exit", "nounset"])
def test_wrapper_startup_failure_records_denial(tmp_path, stage):
    repo = Path(__file__).resolve().parents[1]
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/python").symlink_to(sys.executable)
    shutil.copy2(repo / "scripts/run_with_storage_guard.sh", tmp_path / "scripts")
    # 使用真正 CLI 與 guard，只把控制檔根與 policy 指向小型 fixture。
    (tmp_path / "scripts/storage_safety.py").write_text(
        f"import sys; sys.path.insert(0, {str(repo)!r})\n"
        "from pathlib import Path\nfrom scripts import storage_safety as cli\n"
        f"cli.PROJECT_ROOT=Path({str(tmp_path)!r})\n"
        "raise SystemExit(cli.main())\n"
    )
    env = wrapper_toolchain_fixture(tmp_path)
    config = tmp_path / "ai-core/config"
    if stage == "contract":
        (config / "ai_core_env.sh").write_text("unset AI_CORE_CACHE_IMAGE\n")
    else:
        name = "ai_core_env.sh" if stage == "environment" else "toolchain_paths.sh"
        script = {"exit": "exit 9\n", "nounset": "unset TOP10_MISSING_FIXTURE\n: \"$TOP10_MISSING_FIXTURE\"\n"}.get(stage, "return 1\n")
        (config / name).write_text(script)
    command = ["/bin/bash", str(tmp_path / "scripts/run_with_storage_guard.sh"), "reference", "/usr/bin/false"]
    first = subprocess.run(command, env=env, capture_output=True, text=True)
    assert first.returncode == 70, first.stderr
    receipt_path = tmp_path / "logs/storage_safety/reference_latest.json"
    before = receipt_path.read_bytes()
    payload = json.loads(before)
    assert payload["reasons"] == ["EXTERNAL_CACHE_STARTUP_FAILED"]
    assert payload["child_exit_code"] is None
    assert (tmp_path / "logs/storage_safety/restart_denied/reference.json").is_file()
    assert subprocess.run(command, env=env, capture_output=True).returncode == 75
    assert receipt_path.read_bytes() == before
    assert not (tmp_path / "logs/storage_safety/runtime").exists()


@pytest.mark.parametrize("broken", ["log", "cache"])
def test_cleanup_failure_restores_environment_handlers_and_unlocks(tmp_path, external, monkeypatch, broken):
    root = tmp_path / "repo"
    root.mkdir()
    keys = (*runtime_environment(root), "TOP10_EXTERNAL_CACHE_ROOT")
    prior = {k: os.environ.get(k) for k in keys}
    handlers = {s: signal.getsignal(s) for s in (signal.SIGINT, signal.SIGTERM)}
    target = guard.RotatingLog if broken == "log" else ExternalCache
    original = target.close
    closed = []
    caches = []
    materialize = ExternalCache.materialize
    cache_close = ExternalCache.close

    def track_cache(self):
        caches.append(self)
        return materialize(self)

    def fail_close(self):
        original(self)
        closed.append(self)
        raise OSError("fixture close failure")

    def reject_spawn(*args, **kwargs):
        raise ExternalCacheError("EXTERNAL_CACHE_GATE_DENIED_20")

    monkeypatch.setattr(target, "close", fail_close)
    monkeypatch.setattr(ExternalCache, "materialize", track_cache)
    # 此例不啟真 child；局部排除無關的 nested profile probe，讓原 cleanup fault 被觸發。
    monkeypatch.setattr(guard, "_external_cache_spawn_command",
                        lambda _root, _policy, _cache, command: list(command))
    monkeypatch.setattr(guard, "_spawn_verified_process_group", reject_spawn)
    try:
        with pytest.raises(OSError, match="fixture close failure"):
            guard.run_guarded_job(root, fixture_global_policy(), fixture_job_policy(), RULES,
                                  ["/usr/bin/false"], sampler=lambda _: sample(), external_cache_required=True)
        assert closed
        assert caches and all(cache.fd is None for cache in caches)
        assert {k: os.environ.get(k) for k in keys} == prior
        assert {s: signal.getsignal(s) for s in handlers} == handlers
        with (root / "logs/storage_safety/daily.lock").open("a+") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        assert (root / "logs/storage_safety/restart_denied/daily.json").is_file()
    finally:
        for cache in caches:
            cache_close(cache)
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for signum, previous in handlers.items():
            signal.signal(signum, previous)
