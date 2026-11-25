"""FOG-IO-002 離線 shared-source 反例；不執行研究 workload。"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import tempfile
import uuid
from unittest import mock

import pytest
from app.external_cache import FIELDS
from scripts import storage_safety as cli
from scripts import run_external_fog_revalidation as launcher
from scripts.storage_validation import fog_research_worker as helper
from tests.test_external_fog_revalidation import tiny_source


@pytest.fixture(autouse=True)
def restore_tempfile_route(monkeypatch):
    """in-process CLI 探針結束後還原外層 lifecycle 的 tempfile 路由。"""
    monkeypatch.setattr(tempfile, "tempdir", tempfile.tempdir)


@pytest.fixture
def shared(tmp_path, monkeypatch):
    for key in (*FIELDS, *(key for key in os.environ if key.startswith("AI_CORE_CACHE_")), "TOP10_EXTERNAL_CACHE_ROOT"):
        monkeypatch.delenv(key, raising=False)
    source = tiny_source(tmp_path / "source")
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    commit = "a" * 40
    launcher.copy_project(source, sandbox, source_commit=commit)
    marker, contract = launcher.build_validation_contract(sandbox, commit, source_root=source)
    monkeypatch.setattr(cli, "PROJECT_ROOT", source)
    policy = launcher.PROJECT_ROOT / "docs/operations/top10-storage-policy.json"
    (source / "docs/operations/top10-storage-policy.json").write_bytes(policy.read_bytes())
    monkeypatch.setattr(cli, "DEFAULT_POLICY", source / "docs/operations/top10-storage-policy.json")
    return source, sandbox, marker, contract


def cli_args(shared):
    source, sandbox, marker, contract = shared
    return ["validate-run", "--job", "fog-research-worker", "--sandbox-root", str(sandbox),
            "--marker", str(marker), "--max-runtime-seconds", "1", "--source-input-root", str(source),
            "--sandbox-input-root", str(sandbox), "--sandbox-output-root", str(sandbox),
            "--entrypoint-contract", str(contract)]


def test_cli_accepts_explicit_sandbox_root():
    args = cli.parse_args(["validate-run", "--job", "fog-research-worker",
        "--sandbox-root", "/fixture", "--marker", "/fixture/marker.json",
        "--max-runtime-seconds", "1", "--source-input-root", str(cli.PROJECT_ROOT),
        "--sandbox-input-root", "/fixture", "--sandbox-output-root", "/fixture",
        "--entrypoint-contract", "/fixture/contract.json"])
    assert str(args.sandbox_root) == "/fixture"


def test_cli_passes_sandbox_to_real_trust_loader_and_guard(shared, monkeypatch):
    source, sandbox, _, _ = shared
    calls = []
    monkeypatch.setattr(cli, "run_guarded_job", lambda *args, **kw: calls.append((args, kw)) or 78)
    with mock.patch.dict(os.environ):
        assert cli.main(cli_args(shared)) == 78
    args, kwargs = calls[0]
    assert args[0] == sandbox
    assert args[2].max_bytes == 256 * 1024**2
    assert {"scripts", "validation", "validation_evidence"} <= set(args[2].meter_paths)
    assert kwargs["validation_only"] is True
    assert kwargs["trusted_validation_entrypoint"].sandbox_root == sandbox
    assert kwargs["validation_context"]["source_input_root"] == str(source)
    assert kwargs["validation_context"]["sandbox_output_root"] == str(sandbox)
    assert not (source / "logs").exists()


@pytest.mark.parametrize("case", ["job", "source", "overlap", "git", "symlink", "input", "output", "policy", "ambient", "contract"])
def test_cli_shared_boundary_rejects_before_guard(shared, monkeypatch, tmp_path, case):
    source, sandbox, marker, contract = shared
    args = cli_args(shared)
    if case == "job":
        args[args.index("--job") + 1] = "daily"
    elif case == "source":
        args[args.index("--source-input-root") + 1] = str(tmp_path)
    elif case == "overlap":
        args[args.index("--sandbox-root") + 1] = str(source)
    elif case == "git":
        (sandbox / ".git").write_text("gitdir: elsewhere")
    elif case == "symlink":
        link = tmp_path / "alias"
        link.symlink_to(sandbox, target_is_directory=True)
        args[args.index("--sandbox-root") + 1] = str(link)
    elif case in ("input", "output"):
        args[args.index(f"--sandbox-{case}-root") + 1] = str(source)
    elif case == "policy":
        args = ["--policy", str(source / "other.json"), *args]
    elif case == "ambient":
        monkeypatch.setenv("AI_CORE_CACHE_VOLUME", "/Volumes/configured")
    else:
        contract.write_text("{}")
    monkeypatch.setattr(cli, "run_guarded_job", lambda *a, **kw: pytest.fail("不得進入 guard"))
    with pytest.raises((ValueError, RuntimeError)):
        cli.main(args)
    assert not (sandbox / "logs").exists()


def test_run_cycle_uses_source_interpreter_and_cli(shared, monkeypatch):
    source, sandbox, marker, contract = shared
    monkeypatch.setattr(launcher, "PROJECT_ROOT", source)
    receipt = sandbox / "logs/storage_safety/fog-research-worker_latest.json"
    receipt.parent.mkdir(parents=True)
    receipt.write_text(json.dumps({"status": "NO-GO", "child_exit_code": None, "reasons": ["fixture"]}))
    calls = []
    # 本例只驗 child argv；容量與 ownership 另有真 lifecycle 驗證。
    def accept_fixture_root(path):
        assert path == sandbox
        return path

    native_run = subprocess.run
    def run_child(argv, **kw):
        if argv[0] != str(source / ".venv/bin/python"):
            return native_run(argv, **kw)
        calls.append((argv, kw))
        return subprocess.CompletedProcess(argv, 78, "", "")

    monkeypatch.setattr(launcher, "owned_validation_paths", accept_fixture_root)
    monkeypatch.setattr(launcher.subprocess, "run", run_child)
    code, _ = launcher.run_cycle(sandbox, marker, contract, 1)
    assert code == 78
    argv, kw = calls[0]
    assert argv[:4] == [str(source / ".venv/bin/python"), "-I", "-B", str(source / "scripts/storage_safety.py")]
    assert argv[argv.index("--sandbox-root") + 1] == str(sandbox)
    assert kw["cwd"] == sandbox


@pytest.fixture
def verified_helper(tmp_path, monkeypatch, request):
    source = tiny_source(tmp_path / "source")
    sandbox = tmp_path / "sandbox"
    sandbox.mkdir()
    representative = source / "scripts/run_fog_representative_validation.py"
    representative.write_text(
        "from pathlib import Path\ndef main(*, validation_root):\n"
        "    (validation_root/'owned-result').write_text(str(Path(__file__)))\n    return 0\n"
    )
    for key in (*FIELDS, *(key for key in os.environ if key.startswith("AI_CORE_CACHE_")), "TOP10_EXTERNAL_CACHE_ROOT"):
        monkeypatch.delenv(key, raising=False)
    if getattr(request, "param", False):
        (source / "artifacts/model_experiments/model_experiment_ledger.json").write_text("{}")
        review = source / "artifacts/external_review"
        review.mkdir()
        if request.param == "prefix":
            for name in ("a", "a-1"):
                (review / name).mkdir()
                (review / name / "external_review_summary_01.json").write_text("{}")
        else:
            (review / "external_review_summary_01.json").write_text("{}")
            (review / "external_review_summary_02.json").write_text('{"selected": true}')
    launcher.copy_project(source, sandbox, source_commit="a" * 40)
    _, contract = launcher.build_validation_contract(sandbox, "a" * 40, source_root=source)
    argv = json.loads(contract.read_text())["argv"][1:]
    monkeypatch.chdir(sandbox)
    monkeypatch.setattr(sys, "executable", str(source / ".venv/bin/python"))
    monkeypatch.setattr(sys, "prefix", str(source / ".venv"))
    monkeypatch.setattr(helper.subprocess, "check_output", lambda *a, **kw: "a" * 40)
    return source, sandbox, argv


def test_helper_executes_verified_rep_bytes_with_fixed_sandbox(verified_helper):
    source, sandbox, argv = verified_helper
    before = {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}
    with mock.patch.dict(os.environ):
        with pytest.raises(SystemExit) as stopped:
            helper.shared_source_main(argv)
    assert stopped.value.code == 0
    assert (sandbox / "owned-result").read_text() == str(source / "scripts/run_fog_representative_validation.py")
    assert before == {p.relative_to(source): p.read_bytes() for p in source.rglob("*") if p.is_file()}


@pytest.mark.parametrize("verified_helper", ["prefix"], indirect=True)
def test_helper_pins_consumer_path_order_selected_content(verified_helper):
    source, sandbox, argv = verified_helper
    review = source / "artifacts/external_review"
    # 與既有 consumer 的 sorted(Path.rglob(...)) 完全相同，不用字串排序替代。
    selected = sorted(review.rglob("external_review_summary_*.json"))[-1]
    assert selected.parent.name == "a-1"
    selected.write_text('{"changed": true}')
    with mock.patch.dict(os.environ), pytest.raises(ValueError, match="external review"):
        helper.shared_source_main(argv)
    assert not (sandbox / "owned-result").exists()


def test_helper_rejects_new_unpinned_candidate(verified_helper):
    from scripts.run_fog_representative_validation import CANDIDATE_DIR
    source, sandbox, argv = verified_helper
    (source / CANDIDATE_DIR / "new-unpinned-ranking.csv").write_text("new")
    with pytest.raises(ValueError):
        helper.shared_source_main(argv)
    assert not (sandbox / "owned-result").exists()


@pytest.mark.parametrize("case", ["deleted", "symlink", "ancestor", "ledger_appears", "review_root_appears", "review_appears", "dangling_review"])
def test_helper_rejects_membership_and_absence_drift(verified_helper, case):
    from scripts.run_fog_representative_validation import CANDIDATE_DIR
    source, sandbox, argv = verified_helper
    candidate = source / CANDIDATE_DIR
    if case == "deleted":
        (candidate / "ranking.csv").unlink()
    elif case == "symlink":
        (candidate / "alias.csv").symlink_to(candidate / "ranking.csv")
    elif case == "ancestor":
        original = source / "artifacts"
        moved = source / "moved-artifacts"
        original.rename(moved)
        original.symlink_to(moved, target_is_directory=True)
    elif case == "ledger_appears":
        (source / "artifacts/model_experiments/model_experiment_ledger.json").write_text("{}")
    elif case == "dangling_review":
        (source / "artifacts/external_review").symlink_to(source / "missing-review", target_is_directory=True)
    else:
        review = source / "artifacts/external_review"
        review.mkdir()
        if case == "review_appears":
            (review / "external_review_summary_99.json").write_text("{}")
    with pytest.raises(ValueError):
        helper.shared_source_main(argv)
    assert not (sandbox / "owned-result").exists()


@pytest.mark.parametrize("verified_helper", [True], indirect=True)
@pytest.mark.parametrize("case", ["ledger_change", "ledger_delete", "review_change", "review_delete", "new_latest", "new_earlier", "review_symlink"])
def test_helper_rejects_optional_input_drift(verified_helper, case):
    source, sandbox, argv = verified_helper
    ledger = source / "artifacts/model_experiments/model_experiment_ledger.json"
    review = source / "artifacts/external_review"
    selected = review / "external_review_summary_02.json"
    if case == "ledger_change":
        ledger.write_text('{"changed": true}')
    elif case == "ledger_delete":
        ledger.unlink()
    elif case == "review_change":
        selected.write_text('{"changed": true}')
    elif case == "review_delete":
        selected.unlink()
    elif case == "review_symlink":
        (review / "nested").symlink_to(source / "missing", target_is_directory=True)
    else:
        name = "99" if case == "new_latest" else "00"
        (review / f"external_review_summary_{name}.json").write_text("{}")
    with pytest.raises(ValueError):
        helper.shared_source_main(argv)
    assert not (sandbox / "owned-result").exists()


@pytest.mark.parametrize("verified_helper", [False, True], indirect=True)
def test_optional_presence_and_explicit_exclusions_remain_legal(verified_helper):
    source, sandbox, argv = verified_helper
    cache = source / "app/__pycache__"
    cache.mkdir()
    (cache / "ignored.pyc").write_bytes(b"fixture")
    (source / "app/ignored.pyc").write_bytes(b"fixture")
    (source / "app/.DS_Store").write_bytes(b"fixture")
    with mock.patch.dict(os.environ), pytest.raises(SystemExit) as stopped:
        helper.shared_source_main(argv)
    assert stopped.value.code == 0
    assert (sandbox / "owned-result").is_file()


@pytest.mark.parametrize("case", ["manifest", "data", "runner", "interpreter", "commit", "ambient"])
def test_helper_rejects_drift_before_execution(verified_helper, monkeypatch, case):
    source, sandbox, argv = verified_helper
    if case == "manifest":
        (sandbox / "validation/source-manifest.json").write_text("{}")
    elif case == "data":
        (source / "data/clean/features.parquet").write_text("changed")
    elif case == "runner":
        argv[argv.index("--runner-sha256") + 1] = "0" * 64
    elif case == "interpreter":
        (source / ".venv/bin/python").write_text("changed")
    elif case == "commit":
        monkeypatch.setattr(helper.subprocess, "check_output", lambda *a, **kw: "b" * 40)
    else:
        monkeypatch.setenv("AI_CORE_CACHE_VOLUME", "/Volumes/configured")
    with pytest.raises((ValueError, SystemExit)):
        helper.shared_source_main(argv)
    assert not (sandbox / "owned-result").exists()
    assert not (sandbox / "logs").exists()


def test_real_guard_shared_preflight_over_budget_no_spawn(shared, monkeypatch):
    import app.storage_safety as guard
    source, sandbox, _, _ = shared
    monkeypatch.setattr(cli, "take_sample", lambda *a, **kw: guard.Sample(time.time(), 257 * 1024**2, 0,
        10**12, 10**11, 0, 0))
    monkeypatch.setattr(guard, "_spawn_verified_process_group", lambda *a, **kw: pytest.fail("超額不得 spawn"))
    with mock.patch.dict(os.environ):
        assert cli.main(cli_args(shared)) == 78
    payload = json.loads((sandbox / "logs/storage_safety/fog-research-worker_latest.json").read_text())
    assert "PROJECT_BYTES_BUDGET_EXCEEDED" in payload["reasons"]
    assert payload["child_exit_code"] is None
    assert not (source / "logs").exists()


def test_real_guard_failure_preserves_restart_denial(shared, monkeypatch):
    import app.storage_safety as guard
    source, sandbox, _, _ = shared

    def fail_sample(*args, **kwargs):
        raise OSError("bounded fixture")

    monkeypatch.setattr(cli, "take_sample", fail_sample)
    with mock.patch.dict(os.environ):
        assert cli.main(cli_args(shared)) == 70
        receipt = sandbox / "logs/storage_safety/fog-research-worker_latest.json"
        before = receipt.read_bytes()
        assert cli.main(cli_args(shared)) == 75
        assert receipt.read_bytes() == before
    assert (sandbox / "logs/storage_safety/restart_denied/fog-research-worker.json").is_file()
    assert not (source / "logs").exists()


def test_legacy_cli_without_sandbox_flag_keeps_original_root(shared, monkeypatch):
    source, sandbox, _, _ = shared
    (sandbox / "scripts/run_fog_research_worker.sh").write_text("legacy fixture")
    marker, contract = launcher.build_validation_contract(sandbox, "a" * 40)
    monkeypatch.setattr(cli, "PROJECT_ROOT", sandbox)
    args = ["validate-run", "--job", "fog-research-worker", "--marker", str(marker),
            "--max-runtime-seconds", "1", "--source-input-root", str(source),
            "--sandbox-input-root", str(sandbox), "--sandbox-output-root", str(sandbox),
            "--entrypoint-contract", str(contract)]
    calls = []
    monkeypatch.setattr(cli, "run_guarded_job", lambda *a, **kw: calls.append((a, kw)) or 78)
    with mock.patch.dict(os.environ):
        assert cli.main(args) == 78
    assert calls[0][0][0] == sandbox
    assert calls[0][1]["validation_context"]["shared_source"] is False
    assert calls[0][1]["trusted_validation_entrypoint"].argv[0] == "--runner-sha256"


@pytest.mark.skipif(sys.platform != "darwin", reason="需要原生 Seatbelt")
def test_native_source_write_probe_single_child(tmp_path):
    import app.storage_safety as guard
    source, sandbox = tmp_path / "source", tmp_path / "sandbox"
    source.mkdir()
    sandbox.mkdir()
    target = source / "protected"
    target.write_text("original")
    output = sandbox / "owned"
    code = (
        "import pathlib,sys; pathlib.Path(sys.argv[2]).write_text('owned'); "
        "\ntry: pathlib.Path(sys.argv[1]).write_text('forbidden')"
        "\nexcept PermissionError: sys.exit(0)"
        "\nelse: sys.exit(91)"
    )
    command = guard._validation_spawn_command(sandbox, source,
        [sys.executable, "-B", "-c", code, str(target), str(output)])
    result = subprocess.run(command, capture_output=True, text=True, timeout=5)
    assert result.returncode == 0, result.stderr
    assert output.read_text() == "owned"
    assert target.read_text() == "original"


def _native_source_hashes(source):
    """逐項保存來源與 Git fixture；不追入重用環境的 symlink。"""
    return {p.relative_to(source).as_posix():
            "link:" + os.readlink(p) if p.is_symlink() else
            hashlib.sha256(p.read_bytes()).hexdigest() if p.is_file() else "directory"
            for p in sorted(source.rglob("*"))}


def _native_shared_cli_case(source, outcome):
    """僅由原 lifecycle 啟動；guard 與所有原斷言都留在真實 owned root。"""
    import signal
    import threading
    from scripts.storage_validation.boundary import owned_validation_paths

    source = Path(source)
    sandbox = Path(os.environ["TMP_ARTIFACT_ROOT"])
    assert os.environ["AI_CORE_TMP_ARTIFACT_ACTIVE"] == "1"
    # Python 完成原生啟動後才清 cache 欄位；保留 parent 的完整 ownership 身分。
    for key in (*FIELDS, *(k for k in os.environ if k.startswith("AI_CORE_CACHE_")), "TOP10_EXTERNAL_CACHE_ROOT"):
        os.environ.pop(key, None)
    assert owned_validation_paths(sandbox) == sandbox
    before = _native_source_hashes(source)
    commit = subprocess.check_output(["/usr/bin/git", "-C", str(source), "rev-parse", "HEAD"], text=True).strip()
    launcher.copy_project(source, sandbox, source_commit=commit)
    marker, contract = launcher.build_validation_contract(sandbox, commit, source_root=source)
    cli.PROJECT_ROOT = source
    cli.DEFAULT_POLICY = source / "docs/operations/top10-storage-policy.json"
    args = cli_args((source, sandbox, marker, contract))
    args[args.index("--max-runtime-seconds") + 1] = "3" if outcome == "timeout" else "8"
    cancel, sent = threading.Event(), []
    ready = sandbox / "artifacts/autonomous_research/native-probe"

    def interrupt_probe_guard():
        # ready 由真正 workload 寫出；只向本 guard process 發送訊號。
        while not cancel.wait(0.01):
            if ready.is_file():
                sent.append(True)
                os.kill(os.getpid(), signal.SIGTERM)
                return

    watcher = threading.Thread(target=interrupt_probe_guard, daemon=True) if outcome == "interrupt" else None
    evidence = sandbox / "validation_evidence"
    evidence.mkdir(exist_ok=True)
    proof = {"outcome": outcome, "owned_root": str(sandbox), "assertions_passed": False}
    try:
        if watcher is not None:
            watcher.start()
        try:
            result = cli.main(args)
        finally:
            cancel.set()
            if watcher is not None:
                watcher.join(timeout=2)
                assert not watcher.is_alive()
        receipt_path = sandbox / "logs/storage_safety/fog-research-worker_latest.json"
        receipt = json.loads(receipt_path.read_text())
        proof.update(result=result, receipt=receipt, sent=sent)
        assert result == {"complete": 0, "failure": 17, "timeout": 70, "interrupt": 70}[outcome], receipt
        assert receipt["status"] == {"complete": "OK", "failure": "CHILD_FAILED", "timeout": "STOPPED", "interrupt": "STOPPED"}[outcome]
        if outcome in {"complete", "failure"}:
            assert receipt["child_exit_code"] == (0 if outcome == "complete" else 17)
        if outcome == "interrupt":
            assert sent == [True]
        assert receipt["final_process_group_quiescent"] is True
        assert receipt["summary"]["unknown_changed_paths"] == []
        denied = sandbox / "logs/storage_safety/restart_denied/fog-research-worker.json"
        assert denied.exists() == (outcome in {"timeout", "interrupt"})
        if outcome in {"timeout", "interrupt"}:
            before_receipt = receipt_path.read_bytes()
            assert cli.main(args) == 75
            assert receipt_path.read_bytes() == before_receipt
        assert (source / "protected.txt").read_text() == "original"
        assert ready.read_text() == "source-protected"
        assert not (source / "logs").exists()
        assert not (sandbox / ".venv").exists()
        assert _native_source_hashes(source) == before
        proof.update(assertions_passed=True, source_unchanged=True)
    finally:
        proof["sent"] = sent
        payload = json.dumps(proof, ensure_ascii=False, indent=2)
        assert len(payload.encode()) < 2 * 1024**2
        (evidence / f"native-fog-{outcome}.json").write_text(payload)


@pytest.mark.skipif(sys.platform != "darwin", reason="需要原生 Seatbelt")
@pytest.mark.parametrize("outcome", ["complete", "failure", "timeout", "interrupt"])
def test_native_cli_shared_helper_preserves_source(tmp_path, outcome):
    """未受限 host 只建小型控制 fixture；真正 payload 由原 lifecycle 首次隔離。"""
    import signal
    from scripts.storage_validation.boundary import core_module

    env = core_module("cache_tool").load_environment(dict(os.environ))
    for key in ("AI_CORE_TMP_ARTIFACT_ACTIVE", "TMP_ARTIFACT_ROOT", "AI_CORE_EXTERNAL_DEV_REPO"):
        env.pop(key, None)
    for key in ("TMPDIR", "TMP", "TEMP", "TEMPDIR", "JOBLIB_TEMP_FOLDER"):
        env[key] = env["AI_CORE_CACHE_ROOT"]
    source = tiny_source(tmp_path / "source")
    # 移除 tiny_source 的兩個假環境檔，只連結既有環境，不建立 pyvenv.cfg。
    (source / ".venv/bin/python").unlink()
    (source / ".venv/lib/libpython3.12.dylib").unlink()
    for path in (source / ".venv/bin", source / ".venv/lib", source / ".venv"):
        path.rmdir()
    (source / ".venv").symlink_to(Path(sys.prefix), target_is_directory=True)
    (source / "scripts/storage_validation/fog_research_worker.py").write_bytes(Path(helper.__file__).read_bytes())
    (source / "protected.txt").write_text("original")
    (source / "scripts/run_fog_representative_validation.py").write_text(
        "from pathlib import Path\n"
        "def main(*, validation_root):\n"
        "    target = Path(__file__).parents[1] / 'protected.txt'\n"
        "    try: target.write_text('forbidden')\n"
        "    except PermissionError: pass\n"
        "    else: return 91\n"
        "    output = validation_root / 'artifacts/autonomous_research/native-probe'\n"
        "    output.parent.mkdir(parents=True, exist_ok=True)\n"
        "    output.write_text('source-protected')\n"
        + {
            # 保留一次 live sample；timeout／interrupt 仍使用十秒 workload。
            "complete": "    import time\n    time.sleep(1)\n    return 0\n",
            "failure": "    import time\n    time.sleep(1)\n    return 17\n",
            "timeout": "    import time\n    time.sleep(10)\n    return 0\n",
            "interrupt": "    import time\n    time.sleep(10)\n    return 0\n",
        }[outcome]
    )
    policy_path = source / "docs/operations/top10-storage-policy.json"
    policy_path.write_bytes((launcher.PROJECT_ROOT / "docs/operations/top10-storage-policy.json").read_bytes())
    owner = tmp_path / "owner"
    owner.mkdir()
    for root in (source, owner):
        subprocess.run(["/usr/bin/git", "init", "-q", "-b", "main", str(root)], check=True, env=env)
    subprocess.run(["/usr/bin/git", "-C", str(source), "add", "."], check=True, env=env)
    subprocess.run(["/usr/bin/git", "-C", str(source), "-c", "user.name=Fixture",
                    "-c", "user.email=fixture@example.invalid", "-c", "core.hooksPath=/dev/null",
                    "-c", "commit.gpgsign=false", "commit", "-q", "-m", "fixture"], check=True, env=env)
    before = _native_source_hashes(source)
    core = Path(env.get("AI_CORE_DIR", str(Path.home() / "ai-core")))
    exported = owner / "export"
    bootstrap = (f"import sys; sys.path.insert(0, {str(Path(__file__).resolve().parents[1])!r}); "
                 "from tests.test_fog_shared_source import _native_shared_cli_case; "
                 "_native_shared_cli_case(*sys.argv[1:])")
    command = [str(core / ".venv/bin/python"), "-B", str(core / "scripts/tmp_artifact_lifecycle.py"),
               "run", "--external-only", "--owned-root-writes-only", "--repo-root", str(owner),
               "--policy", str(core / "config/project_sandbox_symlink_fixture_policy.json"),
               "--purpose", "top10-native-fog-" + uuid.uuid4().hex,
               "--max-bytes", "268435456", "--max-file-count", "12000", "--ttl-seconds", "90",
               "--evidence-dir", str(exported), "--preserve", "validation_evidence", "--",
               sys.executable, "-B", "-c", bootstrap, str(source), outcome]
    process = subprocess.Popen(command, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stdout = stderr = ""
    timed_out = False
    try:
        stdout, stderr = process.communicate(timeout=100)
    except subprocess.TimeoutExpired:
        timed_out = True
        # 只通知本次 lifecycle；root／marker 的清理或保留仍由原 parent 裁決。
        process.send_signal(signal.SIGTERM)
        try:
            stdout, stderr = process.communicate(timeout=15)
        except subprocess.TimeoutExpired as error:
            stdout = (error.stdout or b"").decode(errors="replace")
            stderr = (error.stderr or b"").decode(errors="replace")
    after = _native_source_hashes(source)
    proof_path = exported / "validation_evidence" / f"native-fog-{outcome}.json"
    proof = json.loads(proof_path.read_text()) if proof_path.is_file() else {}
    marker = owner / ".git/.ai-core-tmp-artifact-isolation.json"
    try:
        marker_state = json.loads(marker.read_text())
    except FileNotFoundError:
        marker_state = {}
    (owner / "controller.json").write_text(json.dumps({
        "outcome": outcome, "exit_code": process.returncode, "timed_out": timed_out,
        "owned_root": proof.get("owned_root", marker_state.get("root")), "marker": marker_state,
        "proof": proof, "source_before": before, "source_after": after,
        "marker_exists": marker.exists(), "stdout": stdout[-4096:], "stderr": stderr[-4096:],
    }, ensure_ascii=False, indent=2))
    assert before == after
    assert not timed_out and process.returncode == 0, (stdout, stderr)
    assert proof["assertions_passed"] is True and proof["source_unchanged"] is True
    assert proof["outcome"] == outcome
    root = Path(proof["owned_root"])
    assert root.parent == core_module("tmp_artifact_lifecycle").MANAGED_TMP_PARENT
    assert not root.exists() and not marker.exists()
    assert sum(p.stat().st_size for p in exported.rglob("*") if p.is_file()) < 2 * 1024**2
    assert not any(p.name in {"data", ".venv"} for p in exported.rglob("*"))


def test_shared_cli_sampler_keeps_host_and_output_separate(shared, monkeypatch):
    import app.storage_safety as guard
    from collections import namedtuple
    source, sandbox, _, _ = shared
    calls = []
    measured = guard.Sample(time.time(), 100, 2, 250 * 1024**3, 13 * 1024**3, 0, 0)

    def sample(root, policy, pid, *, host_root=None):
        calls.append((root, host_root, pid))
        return measured

    disk = namedtuple("disk", "total used free")
    monkeypatch.setattr(cli, "take_sample", sample)
    # 20 GiB output image 的 free 不得取代內建 13 GiB。
    monkeypatch.setattr(cli.shutil, "disk_usage",
                        lambda root: disk(20 * 1024**3, 4 * 1024**3, 16 * 1024**3))

    def guarded(*args, **kwargs):
        assert kwargs.get("sampler") is not None
        result = kwargs["sampler"](123)
        assert result.host_free_bytes == 13 * 1024**3
        assert result.project_bytes == 100
        assert guard.evaluate_preflight(args[1], args[2], result, validation_only=True).triggered
        capacity = kwargs["validation_context"]["output_capacity_samples"][-1]
        assert capacity["free_bytes"] == 16 * 1024**3
        assert capacity["required_additional_bytes"] == args[2].max_bytes - 100
        assert capacity["decision"] == "PASS"
        return 78

    monkeypatch.setattr(cli, "run_guarded_job", guarded)
    with mock.patch.dict(os.environ):
        assert cli.main(cli_args(shared)) == 78
    assert calls == [(sandbox, source, 123)]


@pytest.mark.parametrize("separate", [False, True])
def test_take_sample_host_root_preserves_output_meter(tmp_path, monkeypatch, separate):
    import app.storage_safety as guard
    from types import SimpleNamespace
    from tests.test_storage_safety import fixture_job_policy
    output, host = tmp_path / "output", tmp_path / "host"
    calls = []
    def measure(root, paths, **kwargs):
        calls.append(("meter", root, kwargs))
        return SimpleNamespace(bytes=321, file_count=7)
    def capacity(root):
        calls.append(("capacity", root))
        return (250 * 1024**3, 13 * 1024**3, 30 * 1024**3,
                "macos_foundation_important_usage")
    monkeypatch.setattr(guard, "measure_paths", measure)
    monkeypatch.setattr(guard, "_measure_host_capacity", capacity)
    monkeypatch.setattr(guard, "process_tree_rss_snapshot", lambda pid: (0, None))
    monkeypatch.setattr(guard, "read_swap_bytes", lambda: 0)
    monkeypatch.setattr(guard, "read_memory_pressure_level", lambda: 0)
    kwargs = {"host_root": host} if separate else {}
    sample = guard.take_sample(output, fixture_job_policy(), **kwargs)
    assert calls == [
        ("meter", output, {"deadline_seconds": None}),
        ("capacity", host if separate else output),
        ("capacity", guard._BOOT_VOLUME_PATH),
    ]
    assert (sample.project_bytes, sample.project_file_count) == (321, 7)
    assert sample.host_total_bytes == 250 * 1024**3
    assert sample.host_free_bytes == 30 * 1024**3
    assert sample.host_raw_free_bytes == 13 * 1024**3
    assert sample.host_capacity_source == "macos_foundation_important_usage"
    assert sample.boot_volume_path == str(guard._BOOT_VOLUME_PATH)
    assert (sample.boot_volume_total_bytes, sample.boot_volume_raw_free_bytes, sample.boot_volume_free_bytes) == (
        250 * 1024**3, 13 * 1024**3, 30 * 1024**3)


@pytest.mark.parametrize("case", ["insufficient", "unavailable", "invalid"])
def test_output_capacity_failure_denies_before_spawn(shared, monkeypatch, case):
    import app.storage_safety as guard
    from types import SimpleNamespace
    _, sandbox, _, _ = shared
    monkeypatch.setattr(cli, "take_sample", lambda *a, **kw:
                        guard.Sample(time.time(), 100, 2, 10**12, 10**11, 0, 0))
    def disk(root):
        assert root == sandbox
        if case == "unavailable":
            raise OSError("fixture unavailable")
        return SimpleNamespace(total=20 * 1024**3, free=-1 if case == "invalid" else 10)
    monkeypatch.setattr(cli.shutil, "disk_usage", disk)
    monkeypatch.setattr(guard, "_spawn_verified_process_group",
                        lambda *a, **kw: pytest.fail("output 容量不足或未知不得 spawn"))
    with mock.patch.dict(os.environ):
        assert cli.main(cli_args(shared)) == 70
    receipt = json.loads((sandbox / "logs/storage_safety/fog-research-worker_latest.json").read_text())
    capacity = receipt["validation_context"]["output_capacity_samples"][-1]
    assert capacity["decision"] == "NO-GO"
    assert capacity["reason_code"] == ("OUTPUT_VOLUME_CAPACITY_INSUFFICIENT"
        if case == "insufficient" else "OUTPUT_VOLUME_CAPACITY_UNAVAILABLE")
    assert capacity["free_bytes"] == ({"insufficient": 10, "invalid": -1, "unavailable": None}[case])
    assert (sandbox / "logs/storage_safety/restart_denied/fog-research-worker.json").is_file()

    # 受管入口才收集真實外接寫入證據；容量故障本身仍是上述定向注入。
    if os.environ.get("TOP10_MANAGED_PYTEST_ROOT"):
        managed = Path(os.environ["TOP10_MANAGED_PYTEST_ROOT"]).resolve(strict=True)
        fixture = sandbox.parent.resolve(strict=True)
        device = int(os.environ["TOP10_MANAGED_BACKING_DEVICE"])
        assert fixture.is_relative_to(managed / "tmp")
        assert fixture.stat().st_dev == device
        files = []
        for path in sorted(fixture.rglob("*")):
            if path.is_symlink() or not path.is_file():
                continue
            resolved = path.resolve(strict=True)
            assert resolved.is_relative_to(fixture)
            with path.open("rb") as stream:
                info = os.fstat(stream.fileno())
            assert info.st_dev == device
            files.append({"resolved": str(resolved), "device": info.st_dev,
                          "size": info.st_size})
        assert files and len(files) <= 256
        assert sum(item["size"] for item in files) <= 8388608
        print(json.dumps({"root": str(fixture), "device": device, "case": case,
                          "reason_code": capacity["reason_code"],
                          "file_count": len(files), "files": files}), flush=True)
