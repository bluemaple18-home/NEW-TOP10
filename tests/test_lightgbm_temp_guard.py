"""隔離暫存防護驗收：無正式目錄、無模型參數修改。"""
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import threading
from dataclasses import replace

import pytest

from app.lightgbm_temp_guard import LightGBMTempGuard, MAX_AGE_SECONDS
from app.storage_safety import GuardInterrupted, reclaim_allowlisted, run_guarded_job
from scripts.storage_safety import parse_args
from tests.test_external_cache_wiring import external, RULES
from tests.storage_safety_helpers import healthy_sample as sample
from tests.test_storage_safety import fixture_global_policy, fixture_job_policy


@pytest.fixture(autouse=True)
def persist_guard_receipts(tmp_path, record_property):
    """fixture 清理前將 guard 原始收據寫入 JUnit，避免只剩回傳碼。"""
    yield
    for path in tmp_path.rglob("*_latest.json"):
        text = path.read_text()
        record_property(str(path.relative_to(tmp_path)), text)
        print("TEMP_GUARD_RECEIPT", text)


def age(path, seconds, now):
    os.utime(path, (now - seconds, now - seconds))


@pytest.mark.parametrize("execute", [False, True])
def test_cleanup_age_pattern_and_links(tmp_path, execute):
    directory = tmp_path / "tmp"
    directory.mkdir()
    now = time.time()
    for name in ("lightgbm_tmp_old", "lightgbm_tmp_fresh", "lightgbm_tmp_boundary", "other"):
        (directory / name).write_text(name)
    age(directory / "lightgbm_tmp_old", MAX_AGE_SECONDS + 1, now)
    age(directory / "other", MAX_AGE_SECONDS + 1, now)
    age(directory / "lightgbm_tmp_boundary", MAX_AGE_SECONDS, now)
    outside = tmp_path / "outside"
    outside.write_text("keep")
    age(outside, MAX_AGE_SECONDS + 1, now)
    (directory / "lightgbm_tmp_link").symlink_to(outside)
    os.link(outside, directory / "lightgbm_tmp_hard")
    nested = directory / "subdir"
    nested.mkdir()
    (nested / "lightgbm_tmp_nested").write_text("keep")
    age(nested / "lightgbm_tmp_nested", MAX_AGE_SECONDS + 1, now)
    (directory / "lightgbm_tmp_dirlink").symlink_to(nested, target_is_directory=True)
    guard = LightGBMTempGuard(directory)
    report = guard.start(execute=execute, now=now)
    assert report["cleanup"]["candidates"] == ["lightgbm_tmp_old"]
    assert report["cleanup"]["deleted"] == (["lightgbm_tmp_old"] if execute else [])
    assert (directory / "lightgbm_tmp_old").exists() is not execute
    assert (directory / "lightgbm_tmp_boundary").exists()
    assert (directory / "lightgbm_tmp_fresh").exists()
    assert (directory / "other").exists()
    assert (nested / "lightgbm_tmp_nested").read_text() == "keep"
    assert outside.read_text() == "keep" and outside.stat().st_nlink == 2
    assert (directory / "lightgbm_tmp_link").is_symlink()
    assert (directory / "lightgbm_tmp_dirlink").is_symlink()
    assert guard.finish()["new_leftovers"]["count"] == 0


def test_new_leftovers_warning_and_first_twenty(tmp_path):
    guard = LightGBMTempGuard(tmp_path)
    guard.start()
    for n in range(25):
        (tmp_path / f"lightgbm_tmp_{n:02}").write_text("leftover")
    report = guard.finish()
    assert report["status"] == "WARNING"
    assert "LIGHTGBM_TEMP_NEW_LEFTOVERS" in report["warnings"]
    assert report["new_leftovers"] == {"count": 25, "names": [f"lightgbm_tmp_{n:02}" for n in range(20)]}
    assert report["before"]["file_count"] == 0 and report["after"]["file_count"] == 25
    assert len(report["after"]["file_names"]) == 25


@pytest.mark.parametrize("ancestor", [False, True])
def test_symlink_directory_rejected(tmp_path, ancestor):
    target = tmp_path / "real"
    target.mkdir()
    (target / "tmp").mkdir()
    file = target / "tmp/lightgbm_tmp_old"
    file.write_text("keep")
    age(file, MAX_AGE_SECONDS + 2, time.time())
    link = tmp_path / "link"
    link.symlink_to(target if ancestor else target / "tmp", target_is_directory=True)
    guard = LightGBMTempGuard(link / "tmp" if ancestor else link)
    with pytest.raises(OSError):
        guard.start(execute=True)
    assert file.read_text() == "keep"


def test_changed_candidate_is_preserved(tmp_path, monkeypatch):
    file = tmp_path / "lightgbm_tmp_old"
    file.write_text("old")
    now = time.time()
    age(file, MAX_AGE_SECONDS + 2, now)
    import app.lightgbm_temp_guard as module
    original = module.inventory
    def changed(fd):
        entries = original(fd)
        file.write_text("new data must survive")
        return entries
    monkeypatch.setattr(module, "inventory", changed)
    guard = LightGBMTempGuard(tmp_path)
    report = guard.start(execute=True, now=now)
    assert not report["cleanup"]["deleted"]
    assert report["cleanup"]["skipped"] == [{"name": file.name, "reason": "ENTRY_CHANGED"}]
    assert file.read_text() == "new data must survive"


def test_final_directory_replacement_warns_without_following(tmp_path):
    directory = tmp_path / "tmp"
    directory.mkdir()
    guard = LightGBMTempGuard(directory)
    guard.start()
    directory.rename(tmp_path / "original")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "lightgbm_tmp_keep").write_text("keep")
    directory.symlink_to(outside, target_is_directory=True)
    report = guard.finish()
    assert "LIGHTGBM_TEMP_FINAL_SCAN_FAILED" in report["warnings"]
    assert report["after"] is None
    assert (outside / "lightgbm_tmp_keep").read_text() == "keep"


def test_general_retention_does_not_bypass_cleanup_flag(tmp_path):
    directory = tmp_path / "logs/storage_safety/runtime/daily/tmp"
    directory.mkdir(parents=True)
    path = directory / "lightgbm_tmp_old"
    path.write_text("keep")
    age(path, MAX_AGE_SECONDS + 2, time.time())
    rules = (replace(RULES[0], protect_newest=0),)
    result = reclaim_allowlisted(tmp_path, rules, execute=True)
    assert path.exists() and not result.removed_paths


def test_cli_cleanup_requires_explicit_flag(tmp_path):
    assert not parse_args(["run", "--job", "daily", "--", "true"]).lightgbm_temp_cleanup
    assert parse_args(["run", "--job", "daily", "--lightgbm-temp-cleanup", "--", "true"]).lightgbm_temp_cleanup


def test_guard_receipt_records_leftover_and_default_dry_run(tmp_path, external):
    # cache volume 與 repo 為兄弟目錄，避免 fixture 把外接寫入誤列專案未知寫入。
    tmp_path = tmp_path / "repo"
    tmp_path.mkdir()
    code = "import os,pathlib; (pathlib.Path(os.environ['TMPDIR'])/'lightgbm_tmp_left').write_text('keep')"
    policy = fixture_job_policy()
    assert run_guarded_job(tmp_path, fixture_global_policy(), policy, RULES,
                           [sys.executable, "-B", "-c", code], sampler=lambda _: sample(),
                           max_runtime_seconds=10, external_cache_required=True) == 0
    receipt = json.loads((tmp_path / "logs/storage_safety/daily_latest.json").read_text())
    report = receipt["lightgbm_temp"]
    assert "LIGHTGBM_TEMP_NEW_LEFTOVERS" in receipt["warnings"]
    assert report["new_leftovers"] == {"count": 1, "names": ["lightgbm_tmp_left"]}
    path = Path(report["directory"]) / "lightgbm_tmp_left"
    age(path, MAX_AGE_SECONDS + 2, time.time())
    assert run_guarded_job(tmp_path, fixture_global_policy(), policy, RULES,
                           [sys.executable, "-B", "-c", "pass"], sampler=lambda _: sample(),
                           max_runtime_seconds=10, external_cache_required=True) == 0
    report = json.loads((tmp_path / "logs/storage_safety/daily_latest.json").read_text())["lightgbm_temp"]
    assert path.exists() and report["cleanup"]["candidates"] == [path.name]
    assert report["cleanup"]["dry_run"] and not report["cleanup"]["deleted"]


def test_interrupted_lightgbm_child_then_next_start_cleanup(tmp_path, external, record_property):
    # cache volume 與 repo 為兄弟目錄，避免 fixture 把外接寫入誤列專案未知寫入。
    tmp_path = tmp_path / "repo"
    tmp_path.mkdir()
    code = ("import os,signal,pathlib; from lightgbm.basic import _TempFile\n"
            "with _TempFile() as temp:\n"
            " pathlib.Path(temp.name).write_text('interrupted child')\n"
            " os.kill(os.getpid(), signal.SIGKILL)\n")
    policy = fixture_job_policy()
    rc = run_guarded_job(tmp_path, fixture_global_policy(), policy, RULES,
                         [sys.executable, "-B", "-c", code], sampler=lambda _: sample(),
                         max_runtime_seconds=15, external_cache_required=True)
    assert rc == -signal.SIGKILL
    receipt_path = tmp_path / "logs/storage_safety/daily_latest.json"
    crashed = json.loads(receipt_path.read_text())
    report = crashed["lightgbm_temp"]
    assert report["new_leftovers"]["count"] == 1
    assert "LIGHTGBM_TEMP_NEW_LEFTOVERS" in crashed["warnings"]
    name = report["new_leftovers"]["names"][0]
    file = Path(report["directory"]) / name
    # 只調整 fixture 的 mtime；新留下的檔案須等超過24小時才具刪除資格。
    age(file, MAX_AGE_SECONDS + 2, time.time())
    assert run_guarded_job(tmp_path, fixture_global_policy(), policy, RULES,
                           [sys.executable, "-B", "-c", "pass"], sampler=lambda _: sample(),
                           max_runtime_seconds=10, external_cache_required=True,
                           lightgbm_temp_cleanup=True) == 0
    recovered = json.loads(receipt_path.read_text())
    assert recovered["lightgbm_temp"]["before"]["matching_count"] == 1
    assert recovered["lightgbm_temp"]["cleanup"]["deleted"] == [name]
    assert recovered["lightgbm_temp"]["after"]["matching_count"] == 0
    assert not file.exists()
    record_property("interrupted_child_receipt", json.dumps(crashed))
    record_property("next_start_receipt", json.dumps(recovered))


@pytest.mark.parametrize("replacement", ["file", "symlink"])
def test_replaced_after_final_stat_is_not_deleted(tmp_path, monkeypatch, replacement):
    file = tmp_path / "lightgbm_tmp_old"
    file.write_text("old")
    now = time.time()
    age(file, MAX_AGE_SECONDS + 2, now)
    outside = tmp_path / "outside"
    outside.write_text("outside untouched")
    native_rename = os.rename
    def swapped(src, dst, **kwargs):
        if src == file.name:
            file.unlink()
            if replacement == "symlink":
                file.symlink_to(outside)
            else:
                file.write_text("new file must survive")
        return native_rename(src, dst, **kwargs)
    monkeypatch.setattr(os, "rename", swapped)
    guard = LightGBMTempGuard(tmp_path)
    report = guard.start(execute=True, now=now)
    assert not report["cleanup"]["deleted"]
    assert report["cleanup"]["skipped"] == [{"name": file.name, "reason": "ENTRY_CHANGED"}]
    assert not report["cleanup"]["retained"]
    assert outside.read_text() == "outside untouched"
    if replacement == "symlink":
        assert file.is_symlink()
    else:
        assert file.read_text() == "new file must survive"
    assert not list(tmp_path.glob(".top10-tempguard-*"))


def test_restore_conflict_preserves_both_files(tmp_path, monkeypatch):
    file = tmp_path / "lightgbm_tmp_old"
    file.write_text("old")
    now = time.time()
    age(file, MAX_AGE_SECONDS + 2, now)
    native_rename = os.rename
    def changed(src, dst, **kwargs):
        if src == file.name:
            file.write_text("updated before capture")
            native_rename(src, dst, **kwargs)
            file.write_text("new public file")
            return
        return native_rename(src, dst, **kwargs)
    monkeypatch.setattr(os, "rename", changed)
    guard = LightGBMTempGuard(tmp_path)
    report = guard.start(execute=True, now=now)
    assert not report["cleanup"]["deleted"]
    assert file.read_text() == "new public file"
    retained = report["cleanup"]["retained"]
    assert len(retained) == 1
    assert (tmp_path / retained[0]["preserved_as"]).read_text() == "updated before capture"
    assert report["status"] == "WARNING"


@pytest.mark.parametrize("interrupt", ["exception", "signal"])
def test_interrupt_after_atomic_capture_preserves_replacement(tmp_path, monkeypatch, interrupt, record_property):
    file = tmp_path / "lightgbm_tmp_old"
    file.write_text("old")
    now = time.time()
    age(file, MAX_AGE_SECONDS + 2, now)
    native_rename = os.rename
    def raise_interrupt(signum=None, frame=None):
        raise GuardInterrupted("injected interruption")
    def interrupted(src, dst, **kwargs):
        if src == file.name:
            file.unlink()
            file.write_text("new file must survive interruption")
            native_rename(src, dst, **kwargs)
            if interrupt == "signal":
                os.kill(os.getpid(), signal.SIGTERM)
                return
            raise_interrupt()
        return native_rename(src, dst, **kwargs)
    monkeypatch.setattr(os, "rename", interrupted)
    previous_handler = signal.signal(signal.SIGTERM, raise_interrupt)
    before_mask = signal.pthread_sigmask(signal.SIG_BLOCK, set())
    guard = LightGBMTempGuard(tmp_path)
    stop = threading.Event()
    background = threading.Thread(target=stop.wait)
    background.start()
    try:
        with pytest.raises(GuardInterrupted):
            guard.start(execute=True, now=now)
    finally:
        stop.set()
        background.join(timeout=2)
        signal.signal(signal.SIGTERM, previous_handler)
    assert signal.pthread_sigmask(signal.SIG_BLOCK, set()) == before_mask
    record_property("interruption_receipt", json.dumps(guard.report))
    assert file.read_text() == "new file must survive interruption"
    assert not guard.report["cleanup"]["deleted"]
    assert not list(tmp_path.glob(".top10-tempguard-*")), guard.report


def test_preserved_capture_survives_general_retention_and_warns(tmp_path):
    directory = tmp_path / "logs/storage_safety/runtime/daily/tmp"
    directory.mkdir(parents=True)
    retained = directory / ".top10-tempguard-conflict"
    retained.write_text("keep captured work")
    age(retained, MAX_AGE_SECONDS + 2, time.time())
    result = reclaim_allowlisted(tmp_path, (replace(RULES[0], protect_newest=0),), execute=True)
    assert retained.read_text() == "keep captured work" and not result.removed_paths
    report = LightGBMTempGuard(directory).start(execute=True)
    assert "LIGHTGBM_TEMP_PRESERVED_ENTRIES" in report["warnings"]
    assert report["preserved_names"] == [retained.name]
    assert not report["cleanup"]["candidates"] and not report["cleanup"]["deleted"]
