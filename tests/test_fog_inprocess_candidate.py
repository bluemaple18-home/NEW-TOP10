"""固定同程序候選的語意測試；不宣稱真實研究或完整後代停止。"""

import json
import hashlib
import os
from pathlib import Path
import sys
import subprocess
from types import SimpleNamespace

import pytest

from scripts import run_fog_representative_validation as runner


class TestFogInprocessCandidate:
    @pytest.fixture
    def tmp_path(self, tmp_path_factory, request):
        # 固定節點只需獨立目錄；不用 pytest numbered/current symlink，保留原安全上限。
        name = "fog-" + hashlib.sha256(request.node.nodeid.encode()).hexdigest()[:16]
        root = tmp_path_factory.mktemp(name, numbered=False)
        yield root
        managed = os.environ.get("TOP10_MANAGED_PYTEST_ROOT")
        if managed:
            files = [p for p in root.rglob("*") if p.is_file()]
            device = int(os.environ["TOP10_MANAGED_BACKING_DEVICE"])
            assert root.resolve().is_relative_to(Path(managed))
            assert all(p.resolve().is_relative_to(root) and p.stat().st_dev == device for p in files)
            print(json.dumps({"fixture_root": str(root), "file_count": len(files),
                              "total_bytes": sum(p.stat().st_size for p in files), "device": device,
                              "all_files_external": True}))

    @pytest.fixture
    def phases(self, monkeypatch):
        calls = []
        research = SimpleNamespace(OUTPUT_DIR="original-output", RESEARCH_LEDGER_PATH="original-ledger",
                                   RESEARCH_SPINE_ROOT="original-spine")

        def phase(name):
            def entry(argv):
                calls.append((name, argv))
                print("sha256:fixed-intent" if name == "publish" else name)
                if name == "execute":
                    research.OUTPUT_DIR = "changed"
                    output = Path(argv[argv.index("--output") + 1])
                    output.write_text(json.dumps({"topic_runs": [{"topic": "fixture"}]}))
                return 0
            return entry

        publish = SimpleNamespace(main=phase("publish"))
        verify = SimpleNamespace(main=phase("verify"))
        research.main = phase("execute")
        monkeypatch.setitem(sys.modules, "scripts.publish_research_batch_intent", publish)
        monkeypatch.setitem(sys.modules, "scripts.verify_research_spine_batch", verify)
        monkeypatch.setitem(sys.modules, "scripts.run_autonomous_research", research)
        # from package import 必須與 sys.modules 一致，避免借用先前測試的 module。
        import scripts
        monkeypatch.setattr(scripts, "run_autonomous_research", research, raising=False)
        monkeypatch.setenv("TOP10_STORAGE_VALIDATION_MODE", "1")
        monkeypatch.setattr(runner.subprocess, "run", lambda *a, **kw: pytest.fail("不得產生 orchestration child"))
        return calls, publish, research, verify

    @pytest.fixture
    def roots(self, tmp_path, monkeypatch):
        source, output = tmp_path / "source", tmp_path / "output"
        (source / "artifacts").mkdir(parents=True)
        output.mkdir()
        (source / "artifacts/market_regime_history.json").write_text(json.dumps({
            "rows": [{"trade_date": runner.FIXTURE_DATE, **runner.FIXTURE_IDENTITY}]}))
        monkeypatch.setattr(runner, "PROJECT_ROOT", source)
        monkeypatch.setattr(runner, "FIXTURE_ROOT", Path("fixture"))
        return source, output

    def test_fixed_sequence_intent_and_owned_writes(self, roots, phases, capsys):
        source, output = roots
        calls, _, research, _ = phases
        original_argv = list(sys.argv)
        assert runner.main(validation_root=output, inprocess=True) == 0
        assert [name for name, _ in calls] == ["publish", "execute", "verify"]
        publish, execute, verify = [argv for _, argv in calls]
        assert publish[publish.index("--") + 1:] == [str(source / "scripts/run_autonomous_research.py"), *execute[:-2]]
        assert execute[-2:] == ["--research-batch-intent", str(output / "fixture/research_spine/batch_intents/fixed-intent.json")]
        assert verify[verify.index("--run-artifact") + 1] == execute[execute.index("--output") + 1]
        assert sys.argv == original_argv and research.OUTPUT_DIR == "original-output"
        result = json.loads(Path(execute[execute.index("--output") + 1]).read_text())
        assert result["production_promotion_allowed"] is False
        assert result["batch_intent_id"] == "sha256:fixed-intent"
        assert result["topic_runs"] == [{"topic": "fixture"}]
        capsys.readouterr()
        managed = os.environ.get("TOP10_MANAGED_PYTEST_ROOT")
        if managed:
            files = [p for p in output.rglob("*") if p.is_file()]
            device = int(os.environ["TOP10_MANAGED_BACKING_DEVICE"])
            assert files and all(p.resolve().is_relative_to(Path(managed)) and p.stat().st_dev == device for p in files)
            print(json.dumps({"candidate_writes": len(files), "candidate_bytes": sum(p.stat().st_size for p in files),
                              "device": device, "external_root": str(output)}))

    @pytest.mark.parametrize("name,reason,count", [
        ("publish", "BATCH_INTENT_PUBLICATION_FAILED", 1),
        ("execute", "REPRESENTATIVE_TOPIC_EXECUTION_FAILED", 2),
        ("verify", "REPRESENTATIVE_BATCH_VERIFICATION_FAILED", 3),
    ])
    def test_nonzero_closes_dispatch(self, roots, phases, monkeypatch, capsys, name, reason, count):
        calls, publish, research, verify = phases
        target = {"publish": publish, "execute": research, "verify": verify}[name]
        def fail(argv):
            calls.append((name, argv))
            print("failure", file=sys.stderr)
            return 7
        monkeypatch.setattr(target, "main", fail)
        assert runner.main(validation_root=roots[1], inprocess=True) == 1
        assert len(calls) == count
        error = json.loads(capsys.readouterr().err)
        assert error["reason_code"] == reason and error["returncode"] == 7

    def test_default_entry_keeps_original_three_commands(self, roots, phases, monkeypatch):
        calls = []
        def run(command):
            calls.append(command)
            if len(calls) == 2:
                Path(command[command.index("--output") + 1]).write_text(json.dumps({"topic_runs": [{"topic": "fixture"}]}))
            return subprocess.CompletedProcess(command, 0, "sha256:original-intent\n", "")
        monkeypatch.setattr(runner, "run", run)
        monkeypatch.setattr(runner, "run_inprocess", lambda *a: pytest.fail("預設不得接候選"))
        assert runner.main(validation_root=roots[1]) == 0
        assert len(calls) == 3 and not phases[0]
        assert [Path(c[1]).name for c in calls] == ["publish_research_batch_intent.py", "run_autonomous_research.py", "verify_research_spine_batch.py"]

    @pytest.mark.parametrize("error,expected", [(SystemExit(2), 2), (SystemExit("bad"), 1), (ValueError("bad"), 1)])
    def test_phase_failure_preserves_exit_and_restores_globals(self, roots, phases, error, expected):
        research = phases[2]
        def fail(argv):
            research.OUTPUT_DIR = "changed"
            raise error
        research.main = fail
        command = runner.build_commands(roots[0], roots[1], "batch")["execute"]
        result = runner.run_inprocess(command)
        assert result.returncode == expected
        # sys.exit(2) 本來不印訊息；字串 exit／exception 才必須保留 stderr。
        if not isinstance(error, SystemExit) or not isinstance(error.code, int):
            assert result.stderr
        assert research.OUTPUT_DIR == "original-output"

    def test_cancel_propagates_and_restores_globals(self, roots, phases):
        research = phases[2]
        def cancel(argv):
            research.RESEARCH_SPINE_ROOT = "changed"
            raise KeyboardInterrupt
        research.main = cancel
        command = runner.build_commands(roots[0], roots[1], "batch")["execute"]
        with pytest.raises(KeyboardInterrupt):
            runner.run_inprocess(command)
        assert research.RESEARCH_SPINE_ROOT == "original-spine"

    def test_unknown_script_and_mode_rejected_before_phase(self, roots, phases, monkeypatch):
        with pytest.raises(ValueError, match="FIXED_FOG_PHASE_REQUIRED"):
            runner.run_inprocess([str(roots[0] / ".venv/bin/python"), "/arbitrary.py"])
        monkeypatch.delenv("TOP10_STORAGE_VALIDATION_MODE")
        with pytest.raises(ValueError, match="VALIDATION_MODE_REQUIRED"):
            runner.run_inprocess(runner.build_commands(roots[0], roots[1], "batch")["publish"])
        assert not phases[0]

    def test_explicit_argv_reaches_real_authority_without_parent_argv(self, tmp_path, monkeypatch):
        from scripts import run_autonomous_research as research
        class AuthorityReached(Exception):
            pass
        seen = {}
        monkeypatch.setattr(research, "resolve_runner_write_set", lambda *a: SimpleNamespace(
            output=tmp_path / "out.json", manager_root=tmp_path, ledger_path=tmp_path / "ledger", spine_root=tmp_path / "spine"))
        def authority(**kwargs):
            seen.update(kwargs)
            raise AuthorityReached
        monkeypatch.setattr(research, "verify_batch_owner_authority", authority)
        for key in ("OUTPUT_DIR", "RESEARCH_LEDGER_PATH", "RESEARCH_SPINE_ROOT"):
            monkeypatch.setattr(research, key, getattr(research, key))
        argv = ["--execute", "--research-batch-id", "fixed", "--output", str(tmp_path / "out.json")]
        parent = list(sys.argv)
        with pytest.raises(AuthorityReached):
            research.main(argv)
        assert seen["runtime_argv"] == [str(Path(research.__file__).resolve()), *argv]
        assert sys.argv == parent and not (tmp_path / "out.json").exists()
