"""外接 cache 的有界接線；fixture 不啟動正式 workload。"""

import json
import errno
import fcntl
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import replace
from types import ModuleType
import pytest

from app.external_cache import ExternalCache, ExternalCacheError, FIELDS, MANAGED_FIELDS, runtime_environment
from app.storage_safety import run_guarded_job, Sample, RetentionRule
from tests.test_storage_safety import fixture_global_policy, fixture_job_policy, wrapper_toolchain_fixture


ROOT = Path(__file__).resolve().parents[1]
KEYS = ("TMPDIR", "UV_CACHE_DIR", "XDG_CACHE_HOME", "MPLCONFIGDIR", "JOBLIB_TEMP_FOLDER")
RULES = (RetentionRule("runtime_workspace", "logs/storage_safety/runtime/daily", "**/*",
                       86400, 20000, 2 * 1024**3, 16),)


def single_child_unit_without_nested_profile(monkeypatch):
    """僅供明示單 child 接線案例；此處不驗 native kernel confinement。"""
    # 只排除 nested profile adapter；真 child、sitecustomize、tempfile、gate 與 cleanup 均保留。
    monkeypatch.setattr("app.storage_safety._external_cache_spawn_command",
                        lambda _root, _policy, _cache, command: list(command))


def projection_case():
    gp = replace(fixture_global_policy(), runtime_min_free_bytes=0, runtime_min_free_percent=0.1)
    jp = replace(fixture_job_policy(), max_bytes=100000, expected_growth_bytes_per_hour=1,
                 spike_window_seconds=1, stabilize_after_seconds=100000,
                 reclaim_after_seconds=3600)
    samples = [Sample(t, 100 + external, 1, 1000, 101, 1, 0,
                      external_cache={"roots": [{"path": "/external/job", "bytes": external}],
                                      "image_contract": {"image_device": 9}})
               for t, external in [(0, 0), (60, 10), (120, 20)]]
    return gp, jp, samples


def test_external_growth_is_not_projected_against_internal_free():
    from app.storage_safety import evaluate_runtime
    gp, jp, samples = projection_case()
    decision = evaluate_runtime(gp, jp, samples)
    assert not decision.triggered, decision.reasons


@pytest.mark.parametrize("case", ["internal", "internal_masked_by_cache_reclaim", "job_total", "host_reserve", "legacy"])
def test_projection_preserves_real_capacity_stops(case):
    from app.storage_safety import evaluate_runtime
    gp, jp, samples = projection_case()
    expected = "SUSTAINED_GROWTH_RATE_WILL_BREAK_BUDGET"
    if case == "internal":
        samples = [replace(s, project_bytes=s.project_bytes + i * 10) for i, s in enumerate(samples)]
    elif case == "internal_masked_by_cache_reclaim":
        samples = [replace(s, project_bytes=200 - i * 10,
                           external_cache={"roots": [{"path": "/external/job", "bytes": 100 - i * 20}],
                                           "image_contract": {"image_device": 9}})
                   for i, s in enumerate(samples)]
    elif case == "job_total":
        jp = replace(jp, max_bytes=500)
    elif case == "host_reserve":
        samples[-1] = replace(samples[-1], host_free_bytes=99)
        expected = "HOST_RUNTIME_FREE_SPACE_BELOW_THRESHOLD"
    else:
        samples = [replace(s, external_cache=None) for s in samples]
    assert expected in evaluate_runtime(gp, jp, samples).reasons


@pytest.mark.parametrize("case", ["missing", "bytes_missing", "negative", "oversized", "float", "device_drift", "root_drift", "extra_root"])
def test_projection_rejects_unknown_external_accounting(case):
    from app.storage_safety import evaluate_runtime
    gp, jp, samples = projection_case()
    cache = samples[-1].external_cache
    if case == "missing":
        samples[-1] = replace(samples[-1], external_cache=None)
    elif case == "bytes_missing":
        del cache["roots"][0]["bytes"]
    elif case in {"negative", "oversized", "float"}:
        cache["roots"][0]["bytes"] = {"negative": -1, "oversized": 121, "float": 20.0}[case]
    elif case == "device_drift":
        cache["image_contract"]["image_device"] = 10
    elif case == "root_drift":
        cache["roots"][0]["path"] = "/external/other"
    else:
        cache["roots"].append(dict(cache["roots"][0]))
    assert "EXTERNAL_CACHE_ACCOUNTING_UNAVAILABLE" in evaluate_runtime(gp, jp, samples).reasons


def test_wrapper_does_not_replace_external_environment(tmp_path):
    """執行真正 wrapper；只在 guard CLI 接縫觀測 shell 傳出的環境。"""
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/python").symlink_to(sys.executable)
    wrapper = tmp_path / "scripts/run_with_storage_guard.sh"
    shutil.copy2(ROOT / "scripts/run_with_storage_guard.sh", wrapper)
    (tmp_path / "scripts/storage_safety.py").write_text(
        "import json, os\nprint(json.dumps(dict(os.environ)))\n"
    )
    expected = {key: f"/Volumes/AICoreCache/Caches/top10-fixture/{key}" for key in KEYS}
    result = subprocess.run(
        ["/bin/bash", str(wrapper), "external-review-preflight", "/usr/bin/true"],
        env={**wrapper_toolchain_fixture(tmp_path), **expected},
        capture_output=True, text=True, check=True,
    )
    actual = json.loads(result.stdout)
    assert {key: actual[key] for key in KEYS} == expected
    assert not (tmp_path / "logs/storage_safety/runtime").exists()


def test_wrapper_loads_toolchain_even_with_volume_and_denies_incomplete_config(tmp_path):
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".venv/bin").mkdir(parents=True)
    wrapper = tmp_path / "scripts/run_with_storage_guard.sh"
    shutil.copy2(ROOT / "scripts/run_with_storage_guard.sh", wrapper)
    (tmp_path / ".venv/bin/python").symlink_to(sys.executable)
    (tmp_path / "scripts/storage_safety.py").write_text(
        "import sys\nraise SystemExit(70 if '--startup-failure' in sys.argv else 0)\n"
    )
    env = wrapper_toolchain_fixture(tmp_path)
    env["AI_CORE_CACHE_MODE"] = "image"
    env["AI_CORE_CACHE_VOLUME"] = "/Volumes/already-supplied"
    marker = tmp_path / "toolchain-loaded"
    env["TOP10_TOOLCHAIN_MARKER"] = str(marker)
    config = tmp_path / "ai-core/config"
    (config / "toolchain_paths.sh").write_text(': > "$TOP10_TOOLCHAIN_MARKER"\n')
    command = ["/bin/bash", str(wrapper), "reference", "/usr/bin/true"]
    assert subprocess.run(command, env=env, capture_output=True).returncode == 0
    assert marker.is_file()
    marker.unlink()
    (config / "ai_core_env.sh").write_text("unset AI_CORE_CACHE_IMAGE\n")
    assert subprocess.run(command, env=env, capture_output=True).returncode != 0
    assert not marker.exists()
    assert not (tmp_path / "logs/storage_safety/runtime").exists()


@pytest.fixture
def external(tmp_path, monkeypatch):
    """只替換原生 gate；環境、dirfd、guard 與單一 child 仍真實執行。"""
    volume = tmp_path / "image"
    volume.mkdir()
    monkeypatch.setenv("AI_CORE_CACHE_MODE", "image")
    for key in FIELDS:
        monkeypatch.setenv(key, str(volume) if key == "AI_CORE_CACHE_VOLUME" else "fixture")
    monkeypatch.setenv("AI_CORE_DIR", str(tmp_path / "ai-core"))
    monkeypatch.delenv("TOP10_EXTERNAL_CACHE_ROOT", raising=False)
    native_run = subprocess.run
    original_mount = Path.is_mount
    monkeypatch.setattr(Path, "is_mount", lambda p: p == volume or original_mount(p))
    calls = []

    def gate(args, **kwargs):
        if "runtime_cache_capacity_gate.py" not in " ".join(map(str, args)):
            return native_run(args, **kwargs)
        calls.append(args)
        offset = args.index("--root")
        root = Path(args[offset + 2])
        entries = list(root.rglob("*")) if root.exists() else []
        used = sum(p.lstat().st_size for p in entries if p.is_file())
        count = len(entries)
        denied = (volume / "lost").exists() or used > int(args[offset + 3]) or count > int(args[offset + 4])
        payload = {"decision": "MAPPING_VALID" if "--mapping-only" in args else "PASS",
                   "image_contract": {"image_device": volume.stat().st_dev},
                   "roots": [{"path": str(root), "bytes": used, "files": count}],
                   "free_bytes": 999999}
        return subprocess.CompletedProcess(args, 20 if denied else 0, json.dumps(payload), "")

    monkeypatch.setattr(subprocess, "run", gate)
    return volume, calls


def test_materialize_scopes_env_and_rechecks_native_identity(tmp_path, external):
    _, calls = external
    cache = ExternalCache(tmp_path, "reference", 65536, 64)
    try:
        env = cache.materialize()
        assert all(Path(env[k]).is_dir() for k in KEYS)
        assert all(Path(env[k]).is_relative_to(cache.root) for k in KEYS)
        assert "--mapping-only" not in calls[0]
        assert "--mapping-only" in calls[-1]
        assert calls[0][calls[0].index("--root") + 3:][:2] == ["65536", "64"]
        assert not (tmp_path / "logs").exists()
        cache.root.rename(cache.root.with_name("old-owned"))
        cache.root.mkdir()
        with pytest.raises(RuntimeError, match="IDENTITY_DRIFT"):
            cache.sample()
    finally:
        cache.close()


@pytest.mark.parametrize("working_directory", ["repo", "output"])
def test_guard_missing_temp_path_cannot_fall_back_to_internal(tmp_path, external, monkeypatch, working_directory):
    """真實 child 在失去指定 tmp 後，不得改用 /tmp 或 repo cwd。"""
    root = tmp_path / "repo"
    root.mkdir()
    (root / "artifacts").mkdir()
    code = (
        "import json,os,pathlib,tempfile; "
        "original=pathlib.Path(os.environ['TMPDIR']); moved=original.with_name('tmp-offline'); "
        "destination=pathlib.Path('artifacts/fallback.json').resolve(); "
        "original.rename(moved); "
        + ("os.chdir('artifacts'); " if working_directory == "output" else "") +
        "result={'fallback':False}; "
        "\ntry:\n"
        " with tempfile.NamedTemporaryFile() as f:\n"
        "  f.write(b'probe'); f.flush(); result={'fallback':True,'path':f.name}\n"
        "except FileNotFoundError:\n pass\n"
        "finally:\n moved.rename(original)\n"
        "destination.write_text(json.dumps(result))\n"
    )
    policy = replace(fixture_job_policy(), meter_paths=("artifacts", "logs"),
                     registered_write_paths=("artifacts", "logs"))
    # 只驗真 Python startup hook／tempfile，局部排除 nested profile；Parent kernel 仍在。
    # cwd 仍可寫，hook 若失效便能 fallback 並使原 False 斷言失敗；此例不當作 native 拒寫證明。
    monkeypatch.setattr("app.storage_safety._external_cache_spawn_command",
                        lambda _root, _policy, _cache, command: list(command))
    result = run_guarded_job(root, fixture_global_policy(), policy, RULES,
                             [sys.executable, "-B", "-c", code], sampler=lambda _: sample(),
                             max_runtime_seconds=5, external_cache_required=True)
    assert result == 0
    assert json.loads((root / "artifacts/fallback.json").read_text()) == {"fallback": False}


def test_missing_volume_and_symlink_never_materialize_internal(tmp_path, external):
    volume, _ = external
    cache = ExternalCache(tmp_path, "reference", 65536, 64)
    cache.root.parent.mkdir(parents=True)
    cache.root.symlink_to(tmp_path / "internal-fallback")
    with pytest.raises(RuntimeError, match="SYMLINK_DRIFT"):
        cache.materialize()
    assert not (tmp_path / "internal-fallback").exists()
    (volume / "lost").touch()
    with pytest.raises(RuntimeError, match="GATE_DENIED"):
        cache.materialize()
    assert not (tmp_path / "logs").exists()


def sample():
    return Sample(time.time(), 0, 0, 10000000, 9000000, 0, 0)


def test_combined_job_quota_blocks_before_child(tmp_path, external):
    root = tmp_path / "repo"
    root.mkdir()
    cache = ExternalCache(root, "daily", 100, 100)
    cache.root.mkdir(parents=True)
    (cache.root / "cache").write_bytes(b"x" * 60)
    result = run_guarded_job(root, fixture_global_policy(), fixture_job_policy(max_bytes=100), RULES,
                             ["/usr/bin/false"], sampler=lambda _: replace(sample(), project_bytes=60),
                             external_cache_required=True)
    assert result == 78
    receipt = json.loads((root / "logs/storage_safety/daily_latest.json").read_text())
    assert receipt["samples"][0]["project_bytes"] == 120
    assert "PROJECT_BYTES_BUDGET_EXCEEDED" in receipt["reasons"]
    assert not (root / "logs/storage_safety/runtime").exists()


def test_legacy_isolation_rejects_external_before_runtime(tmp_path, external, monkeypatch):
    from scripts import storage_safety as cli
    from scripts.run_isolated_daily_backfill import command_env, prepare_runtime
    from app.storage_safety import _materialize_active_runtime_workspace
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    monkeypatch.setenv("TOP10_EXTERNAL_CACHE_ROOT", str(tmp_path / "image/Caches/active"))
    for operation in (lambda: cli.configure_validation_runtime("daily"),
                      lambda: command_env(tmp_path, tmp_path / "runtime"),
                      lambda: prepare_runtime(tmp_path / "runtime"),
                      lambda: _materialize_active_runtime_workspace(tmp_path, "daily")):
        with pytest.raises(RuntimeError, match="EXTERNAL_CACHE"):
            operation()
    assert not (tmp_path / "runtime").exists()
    assert not (tmp_path / "logs").exists()


def test_guard_missing_contract_persists_denial_and_does_not_spawn(tmp_path, monkeypatch):
    for key in FIELDS:
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("AI_CORE_CACHE_VOLUME", "/Volumes/absent-top10-fixture")
    marker = tmp_path / "spawned"
    args = (tmp_path, fixture_global_policy(), fixture_job_policy(), RULES,
            [sys.executable, "-B", "-c", f"open({str(marker)!r},'w').close()"])
    assert run_guarded_job(*args, sampler=lambda _: sample(), external_cache_required=True) == 70
    assert run_guarded_job(*args, sampler=lambda _: sample(), external_cache_required=True) == 75
    assert not marker.exists()
    assert (tmp_path / "logs/storage_safety/restart_denied/daily.json").is_file()


def test_retention_expired_preserves_owned_files(tmp_path, external):
    cache = ExternalCache(tmp_path, "reference", 65536, 64)
    cache.root.mkdir(parents=True)
    old = cache.root / "expired"
    old.write_bytes(b"owned")
    os.utime(old, (time.time() - 86401, time.time() - 86401))
    with pytest.raises(RuntimeError, match="RETENTION_EXPIRED"):
        cache.sample()
    assert old.read_bytes() == b"owned"


def reclaim_under_job_lock(cache):
    lock = cache.project_root / "logs/storage_safety" / f"{cache.job}.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        try:
            return cache.reclaim_expired_before_child(exclusive_lock_fd=handle.fileno())
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def test_cache_cleanup_requires_held_job_lock(tmp_path, external):
    cache = ExternalCache(tmp_path, "daily", 65536, 64)
    cache.materialize()
    fontlist = cache.root / "cache/matplotlib/fontlist-v3.11.0.json"
    fontlist.write_text("regenerable")
    old = time.time() - 2 * 86400
    os.utime(fontlist, (old, old))
    lock = cache.project_root / "logs/storage_safety/daily.lock"
    lock.parent.mkdir(parents=True, exist_ok=True)
    with lock.open("a+") as handle:
        with pytest.raises(ExternalCacheError, match="NOT_EXCLUSIVE"):
            cache.reclaim_expired_before_child(exclusive_lock_fd=handle.fileno())
    assert fontlist.read_text() == "regenerable"
    cache.close()


def test_expired_matplotlib_fontlist_reclaimed_before_child(tmp_path, external):
    cache = ExternalCache(tmp_path, "daily", 65536, 64)
    cache.materialize()
    fontlist = cache.root / "cache/matplotlib/fontlist-v3.11.0.json"
    fontlist.write_text('{"_version": 1}')
    old = time.time() - 2 * 86400
    os.utime(fontlist, (old, old))
    with pytest.raises(ExternalCacheError, match="RETENTION_EXPIRED"):
        cache.sample()
    result = reclaim_under_job_lock(cache)
    assert result == {"files": 1, "bytes": len('{"_version": 1}')}
    assert not fontlist.exists()
    assert cache.sample()["decision"] == "MAPPING_VALID"
    assert sum("--mapping-only" not in call for call in external[1]) == 1
    cache.close()


def test_directory_mode_reclaims_only_verified_expired_fontlist(tmp_path, external, monkeypatch):
    """目錄模式沿用 job 鎖與 dirfd 刪除；共用准入在此僅以 fixture 模擬。"""
    volume, _ = external
    managed_root = volume / "Caches"

    class ManagedFixture:
        def __init__(self):
            self.volume = volume
            self.root = managed_root

        @classmethod
        def from_env(cls):
            return cls()

        def sample(self):
            return {"device": volume.stat().st_dev, "volume_uuid": "fixture", "decision": "PASS"}

        def materialize(self, paths):
            for path in paths:
                path.mkdir(parents=True, exist_ok=True)

        def close(self):
            pass

    stub = ModuleType("runtime_cache_capacity_gate")
    stub.ManagedCache = ManagedFixture
    monkeypatch.setitem(sys.modules, "runtime_cache_capacity_gate", stub)
    monkeypatch.setenv("AI_CORE_CACHE_MODE", "directory")
    for key in MANAGED_FIELDS:
        monkeypatch.setenv(key, str(volume) if key == "AI_CORE_CACHE_VOLUME" else "fixture")

    cache = ExternalCache(tmp_path, "daily", 65536, 64)
    try:
        cache.materialize()
        expired = cache.root / "cache/matplotlib/fontlist-v3.11.0.json"
        fresh = cache.root / "cache/matplotlib/fontlist-v3.12.0.json"
        expired.write_bytes(b"old")
        fresh.write_bytes(b"keep")
        old = time.time() - 2 * 86400
        os.utime(expired, (old, old))
        with pytest.raises(ExternalCacheError, match="RETENTION_EXPIRED"):
            cache.sample()
        assert reclaim_under_job_lock(cache) == {"files": 1, "bytes": 3}
        assert not expired.exists()
        assert fresh.read_bytes() == b"keep"

        unknown = cache.root / "cache/uv/unknown.dat"
        unknown.write_bytes(b"preserve")
        os.utime(unknown, (old, old))
        with pytest.raises(ExternalCacheError, match="RETENTION_UNOWNED"):
            reclaim_under_job_lock(cache)
        assert unknown.read_bytes() == b"preserve"
    finally:
        cache.close()


def test_expired_cache_cleanup_rejects_root_swap_before_unlink(tmp_path, external, monkeypatch):
    cache = ExternalCache(tmp_path, "daily", 65536, 64)
    cache.materialize()
    fontlist = cache.root / "cache/matplotlib/fontlist-v3.11.0.json"
    fontlist.write_text("keep-original")
    old = time.time() - 2 * 86400
    os.utime(fontlist, (old, old))
    moved_root = cache.root.with_name(cache.root.name + "-moved")
    original_lstat = Path.lstat
    calls = 0

    def swap_root(path, *args, **kwargs):
        nonlocal calls
        if path == cache.root:
            calls += 1
            if calls == 3:
                cache.root.rename(moved_root)
                cache.root.mkdir()
        return original_lstat(path, *args, **kwargs)

    monkeypatch.setattr(Path, "lstat", swap_root)
    with pytest.raises(ExternalCacheError, match="RETENTION_RACE"):
        reclaim_under_job_lock(cache)
    assert (moved_root / "cache/matplotlib/fontlist-v3.11.0.json").read_text() == "keep-original"
    assert not (cache.root / "cache/matplotlib/fontlist-v3.11.0.json").exists()
    cache.close()


def test_expired_cache_cleanup_partial_drift_keeps_unverified_file(
    tmp_path, external, monkeypatch,
):
    cache = ExternalCache(tmp_path, "daily", 65536, 64)
    cache.materialize()
    directory = cache.root / "cache/matplotlib"
    names = ("fontlist-v3.10.0.json", "fontlist-v3.11.0.json")
    for name in names:
        item = directory / name
        item.write_text("original")
        old = time.time() - 2 * 86400
        os.utime(item, (old, old))
    original_unlink = os.unlink
    removed = []

    def drift_after_first_unlink(path, *args, **kwargs):
        original_unlink(path, *args, **kwargs)
        if path in names and not removed:
            removed.append(path)
            other = next(name for name in names if name != path)
            (directory / other).write_text("changed-after-scan")

    monkeypatch.setattr(os, "unlink", drift_after_first_unlink)
    with pytest.raises(ExternalCacheError, match="RETENTION_RACE"):
        reclaim_under_job_lock(cache)
    assert len(removed) == 1
    assert not (directory / removed[0]).exists()
    assert (directory / next(name for name in names if name != removed[0])).read_text() == "changed-after-scan"
    cache.close()


@pytest.mark.parametrize("invalid", ["unknown", "hardlink", "symlink"])
def test_expired_cache_cleanup_refuses_nonexclusive_or_unknown_files(tmp_path, external, invalid):
    cache = ExternalCache(tmp_path, "daily", 65536, 64)
    cache.materialize()
    fontlist = cache.root / "cache/matplotlib/fontlist-v3.11.0.json"
    fontlist.write_text("regenerable")
    old = time.time() - 2 * 86400
    os.utime(fontlist, (old, old))
    if invalid == "unknown":
        unknown = cache.root / "cache/matplotlib/unknown.bin"
        unknown.write_text("preserve")
        os.utime(unknown, (old, old))
    elif invalid == "hardlink":
        os.link(fontlist, cache.root / "cache/matplotlib/also-linked")
    else:
        (cache.root / "cache/matplotlib/unknown-link").symlink_to(fontlist)
    with pytest.raises(ExternalCacheError, match="UNOWNED|SYMLINK_DRIFT"):
        reclaim_under_job_lock(cache)
    assert fontlist.read_text() == "regenerable"
    cache.close()


def test_cache_caps_stay_below_larger_job_budget(tmp_path, external):
    _, calls = external
    policy = fixture_job_policy(max_bytes=6 * 1024**3, max_file_count=50000)
    assert run_guarded_job(tmp_path, fixture_global_policy(), policy, RULES, ["/usr/bin/false"],
                           sampler=lambda _: replace(sample(), project_bytes=7 * 1024**3),
                           external_cache_required=True) == 78
    args = calls[0]
    assert args[args.index("--root") + 3:][:2] == [str(2 * 1024**3), "20000"]


def test_cli_run_requires_external_and_legacy_fixture_clears_ambient(tmp_path, external, monkeypatch):
    from scripts import storage_safety as cli
    calls = []
    monkeypatch.setattr(cli, "run_guarded_job", lambda *args, **kwargs: calls.append(kwargs) or 0)
    assert cli.main(["run", "--job", "reference", "--", "/usr/bin/true"]) == 0
    assert calls[0]["external_cache_required"] is True
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    for key in (*KEYS, "PYTHONDONTWRITEBYTECODE"):
        monkeypatch.setenv(key, os.environ.get(key, ""))
    for key in (*FIELDS, "TOP10_EXTERNAL_CACHE_ROOT", *(key for key in os.environ if key.startswith("AI_CORE_CACHE_"))):
        monkeypatch.delenv(key, raising=False)
    # CLI 本來會固定 process-global cache；單元案例結束時須還原給下一個案例。
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)
    environment = cli.configure_validation_runtime("reference")
    assert all(Path(path).is_relative_to(tmp_path) for path in environment.values())


def test_single_child_environment_and_external_write_green(tmp_path, external, monkeypatch):
    single_child_unit_without_nested_profile(monkeypatch)
    root = tmp_path / "repo"
    root.mkdir()
    code = ("import json,os,pathlib,time; "
            f"pathlib.Path(os.environ['TMPDIR'],'env.json').write_text(json.dumps({{k:os.environ[k] for k in {KEYS!r}}})); "
            "time.sleep(1.3)")
    result = run_guarded_job(root, fixture_global_policy(), fixture_job_policy(sample_interval_seconds=1),
                             RULES, [sys.executable, "-B", "-c", code], sampler=lambda _: sample(),
                             max_runtime_seconds=5, external_cache_required=True)
    assert result == 0
    cache = ExternalCache(root, "daily", 65536, 64)
    actual = json.loads((cache.root / "tmp/env.json").read_text())
    assert actual == {k: runtime_environment(cache.root)[k] for k in KEYS}
    assert not (root / "logs/storage_safety/runtime").exists()


@pytest.mark.parametrize("failure", ["capacity", "identity"])
def test_single_child_external_stop_and_restart_denial(tmp_path, external, monkeypatch, failure):
    single_child_unit_without_nested_profile(monkeypatch)
    volume, _ = external
    root = tmp_path / "repo"
    root.mkdir()
    prior = {key: os.environ.get(key) for key in (*KEYS, "TOP10_EXTERNAL_CACHE_ROOT")}
    code = (
        "import os,pathlib,time; "
        "p=pathlib.Path(os.environ['TMPDIR']); "
        + ("(p/'owned.bin').write_bytes(b'x'*70000); " if failure == "capacity" else "")
        + "time.sleep(10)"
    )
    policy = fixture_job_policy(max_bytes=65536, sample_interval_seconds=0.1)
    args = (root, fixture_global_policy(), policy, RULES, [sys.executable, "-B", "-c", code])
    def observe(pid):
        # 換掛載由 fixture parent 模擬，不要求受限 child 修改未登記的 volume 根。
        if failure == "identity" and pid is not None:
            (volume / "lost").touch()
        return sample()
    assert run_guarded_job(*args, sampler=observe, max_runtime_seconds=3,
                           external_cache_required=True) == 70
    assert run_guarded_job(*args, sampler=lambda _: sample(), max_runtime_seconds=3,
                           external_cache_required=True) == 75
    receipt = json.loads((root / "logs/storage_safety/daily_latest.json").read_text())
    assert receipt["status"] == "STOPPED"
    assert receipt["samples"][0]["external_cache"] is not None
    assert "EXTERNAL_CACHE_GATE_DENIED_20" in receipt["reasons"]
    assert receipt["final_process_group_quiescent"] is True
    assert {key: os.environ.get(key) for key in prior} == prior
    assert not (root / "logs/storage_safety/runtime").exists()


def test_external_child_can_write_only_registered_outputs_and_owned_cache(tmp_path, external):
    root = tmp_path / "repo"
    root.mkdir()
    artifacts = root / "artifacts"
    artifacts.mkdir()
    source = root / "source.py"
    source.write_text("source")
    foreign = tmp_path / "foreign"
    foreign.mkdir()
    (foreign / "sentinel").write_text("foreign")
    (artifacts / "escape").symlink_to(foreign, target_is_directory=True)
    targets = [str(source), str(root / "unregistered"), str(foreign / "sentinel"),
               str(artifacts / "escape/sentinel")]
    code = (
        "import json,os,pathlib; results=[]\n"
        f"for path in {targets!r}:\n"
        " try:\n  pathlib.Path(path).write_text('unexpected'); results.append(False)\n"
        " except PermissionError:\n  results.append(True)\n"
        "pathlib.Path(os.environ['TMPDIR'],'cache-write').write_text('owned')\n"
        "pathlib.Path('artifacts/result.json').write_text(json.dumps(results))\n"
    )
    policy = replace(fixture_job_policy(), meter_paths=("artifacts", "logs"),
                     registered_write_paths=("artifacts", "logs"))
    assert run_guarded_job(root, fixture_global_policy(), policy, RULES,
                           [sys.executable, "-B", "-c", code], sampler=lambda _: sample(),
                           external_cache_required=True) == 0
    assert json.loads((artifacts / "result.json").read_text()) == [True] * 4
    assert source.read_text() == "source"
    assert (foreign / "sentinel").read_text() == "foreign"


@pytest.mark.parametrize("failure", ["unavailable", "probe", "symlink-output"])
def test_external_confinement_failure_denies_before_workload(tmp_path, external, monkeypatch, failure):
    import app.storage_safety as guard
    root = tmp_path / "repo"
    root.mkdir()
    if failure == "unavailable":
        monkeypatch.setattr(guard, "SANDBOX_EXECUTABLE", tmp_path / "absent")
    elif failure == "probe":
        native_run = subprocess.run
        def reject_probe(args, **kwargs):
            if args[0] == str(guard.SANDBOX_EXECUTABLE):
                return subprocess.CompletedProcess(args, 91)
            return native_run(args, **kwargs)
        monkeypatch.setattr(subprocess, "run", reject_probe)
    else:
        (root / "output").symlink_to(tmp_path / "foreign")
    marker = root / "must-not-spawn"
    command = [sys.executable, "-B", "-c", f"open({str(marker)!r},'w').close()"]
    args = (root, fixture_global_policy(), fixture_job_policy(), RULES, command)
    assert run_guarded_job(*args, sampler=lambda _: sample(), external_cache_required=True) == 70
    assert run_guarded_job(*args, sampler=lambda _: sample(), external_cache_required=True) == 75
    assert not marker.exists()
    receipt = json.loads((root / "logs/storage_safety/daily_latest.json").read_text())
    expected = {"unavailable": "EXTERNAL_CACHE_CONFINEMENT_UNAVAILABLE",
                "probe": "EXTERNAL_CACHE_CONFINEMENT_PROBE_FAILED",
                "symlink-output": "GUARD_INTERNAL_ERROR_ValueError"}[failure]
    assert expected in receipt["reasons"]


@pytest.mark.parametrize("flags", [["-I"], ["-E"], ["-S"], ["-IS"], ["-X", "dev", "-I"]])
def test_external_python_cannot_disable_tempfile_startup(tmp_path, external, flags):
    marker = tmp_path / "must-not-run"
    args = (tmp_path, fixture_global_policy(), fixture_job_policy(), RULES,
            [sys.executable, *flags, "-c", f"open({str(marker)!r},'w').close()"])
    assert run_guarded_job(*args, sampler=lambda _: sample(), external_cache_required=True) == 70
    assert not marker.exists()
    receipt = json.loads((tmp_path / "logs/storage_safety/daily_latest.json").read_text())
    assert "EXTERNAL_CACHE_PYTHON_ISOLATION_UNSUPPORTED" in receipt["reasons"]


def test_external_python_mapping_is_scoped_and_restored(tmp_path, external, monkeypatch):
    single_child_unit_without_nested_profile(monkeypatch)
    monkeypatch.setenv("PYTHONPATH", "/fixture/caller-python-path")
    code = (
        "import os,tempfile; "
        "assert tempfile.tempdir == os.environ['TMPDIR']; "
        "assert os.environ['PYTHONPATH'].endswith('/fixture/caller-python-path')"
    )
    assert run_guarded_job(tmp_path, fixture_global_policy(), fixture_job_policy(), RULES,
                           [sys.executable, "-B", "-c", code], sampler=lambda _: sample(),
                           external_cache_required=True) == 0
    assert os.environ["PYTHONPATH"] == "/fixture/caller-python-path"


def test_real_lightgbm_consumer_fails_closed_with_missing_temp_in_output_cwd(tmp_path, external, monkeypatch):
    single_child_unit_without_nested_profile(monkeypatch)
    root = tmp_path / "repo"
    root.mkdir()
    (root / "artifacts").mkdir()
    code = (
        "import os,pathlib; from lightgbm.basic import _TempFile; "
        "original=pathlib.Path(os.environ['TMPDIR']); moved=original.with_name('tmp-offline'); "
        "original.rename(moved); os.chdir('artifacts'); blocked=False\n"
        "try:\n with _TempFile(): pass\n"
        "except FileNotFoundError:\n blocked=True\n"
        "finally:\n moved.rename(original)\n"
        "assert blocked\n"
        "assert not list(pathlib.Path.cwd().glob('lightgbm_tmp_*'))\n"
    )
    policy = replace(fixture_job_policy(), meter_paths=("artifacts", "logs"),
                     registered_write_paths=("artifacts", "logs"))
    assert run_guarded_job(root, fixture_global_policy(), policy, RULES,
                           [sys.executable, "-B", "-c", code], sampler=lambda _: sample(),
                           max_runtime_seconds=10, external_cache_required=True) == 0


def test_configured_missing_disk_rejects_isolated_entrypoints_before_mkdir(tmp_path, monkeypatch):
    from scripts import storage_safety as cli
    from scripts.run_isolated_daily_backfill import command_env, prepare_runtime
    for key in FIELDS:
        monkeypatch.setenv(key, str(tmp_path / "missing-volume") if key == "AI_CORE_CACHE_VOLUME" else "fixture")
    monkeypatch.delenv("TOP10_EXTERNAL_CACHE_ROOT", raising=False)
    monkeypatch.setattr(cli, "PROJECT_ROOT", tmp_path)
    runtime = tmp_path / "internal-runtime"
    for operation in (lambda: prepare_runtime(runtime), lambda: command_env(tmp_path, runtime),
                      lambda: cli.configure_validation_runtime("daily")):
        with pytest.raises(RuntimeError, match="EXTERNAL_CACHE_ISOLATION_UNSUPPORTED"):
            operation()
    assert not runtime.exists()
    assert not (tmp_path / "logs").exists()


def test_real_wrapper_startup_failure_persists_denial_after_toolchain_recovers(tmp_path):
    from tests.test_storage_safety import wrapper_toolchain_fixture
    (tmp_path / "scripts").mkdir()
    (tmp_path / ".venv/bin").mkdir(parents=True)
    (tmp_path / ".venv/bin/python").symlink_to(sys.executable)
    for name in ("run_with_storage_guard.sh", "storage_safety.py"):
        shutil.copy2(ROOT / "scripts" / name, tmp_path / "scripts" / name)
    (tmp_path / "docs/operations").mkdir(parents=True)
    shutil.copy2(ROOT / "docs/operations/top10-storage-policy.json",
                 tmp_path / "docs/operations/top10-storage-policy.json")
    env = wrapper_toolchain_fixture(tmp_path)
    env["PYTHONPATH"] = str(ROOT)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    toolchain = tmp_path / "ai-core/config/toolchain_paths.sh"
    toolchain.write_text("return 1\n")
    marker = tmp_path / "child-must-not-run"
    command = ["/bin/bash", str(tmp_path / "scripts/run_with_storage_guard.sh"), "daily",
               sys.executable, "-B", "-c", f"open({str(marker)!r}, 'w').close()"]
    first = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
    assert first.returncode == 70, first.stderr
    receipt = json.loads((tmp_path / "logs/storage_safety/daily_latest.json").read_text())
    assert "EXTERNAL_CACHE_STARTUP_FAILED" in receipt["reasons"]
    assert (tmp_path / "logs/storage_safety/restart_denied/daily.json").exists()
    toolchain.write_text("return 0\n")
    second = subprocess.run(command, env=env, capture_output=True, text=True, timeout=10)
    assert second.returncode == 75, second.stderr
    assert not marker.exists()
    assert not (tmp_path / "logs/storage_safety/runtime").exists()


def test_cleanup_close_error_still_restores_environment_handlers_and_cache(tmp_path, external, monkeypatch):
    single_child_unit_without_nested_profile(monkeypatch)
    import app.storage_safety as guard
    from app.external_cache import ExternalCacheError
    root = tmp_path / "repo"
    root.mkdir()
    keys = (*runtime_environment(root), "TOP10_EXTERNAL_CACHE_ROOT")
    prior = {key: os.environ.get(key) for key in keys}
    handlers = {sig: signal.getsignal(sig) for sig in (signal.SIGINT, signal.SIGTERM)}
    opened = []
    original_materialize = ExternalCache.materialize
    original_close = guard.RotatingLog.close

    def materialize(cache):
        opened.append(cache)
        return original_materialize(cache)

    def fail_close(log):
        original_close(log)
        raise OSError(errno.ENOSPC, "fixture close failure")

    def fail_live(pid):
        if pid is not None:
            raise ExternalCacheError("EXTERNAL_CACHE_GATE_DENIED_20")
        return sample()

    monkeypatch.setattr(ExternalCache, "materialize", materialize)
    monkeypatch.setattr(guard.RotatingLog, "close", fail_close)
    try:
        with pytest.raises(OSError, match="fixture close failure"):
            run_guarded_job(root, fixture_global_policy(), fixture_job_policy(), RULES,
                            ["/bin/sleep", "5"], sampler=fail_live, external_cache_required=True)
        assert {key: os.environ.get(key) for key in keys} == prior
        assert {sig: signal.getsignal(sig) for sig in handlers} == handlers
        assert opened[0].fd is None
        receipt = json.loads((root / "logs/storage_safety/daily_latest.json").read_text())
        assert receipt["status"] == "STOPPED"
        assert "EXTERNAL_CACHE_GATE_DENIED_20" in receipt["reasons"]
    finally:
        for cache in opened:
            cache.close()
        for key, value in prior.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        for sig, handler in handlers.items():
            signal.signal(sig, handler)
