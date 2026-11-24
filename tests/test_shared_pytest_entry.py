"""薄入口的純邊界測試；不執行原生 helper、外接寫入或停止證明。"""

import os
import contextlib
import io
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock


ENTRY = Path(__file__).resolve().parents[1] / "scripts/test_with_shared_runtime.sh"
FOG_NODE = "tests/test_fog_shared_source.py::test_output_capacity_failure_denies_before_spawn"
FOG_TOPOLOGY_NODE = "tests/test_fog_inprocess_candidate.py::TestFogInprocessCandidate"


class SharedPytestEntryTest(unittest.TestCase):
    def entry(self):
        source = ENTRY.read_text().split("<<'PY_SHARED_ENTRY'\n", 1)[1].rsplit("\nPY_SHARED_ENTRY", 1)[0]
        namespace = {"__name__": "shared_entry_unit"}
        exec(compile(source, str(ENTRY), "exec"), namespace)
        return namespace

    def test_entry_exists(self):
        self.assertTrue(ENTRY.is_file(), "受管 pytest 入口尚未接線")

    def test_incomplete_environment_refuses_before_toolchain(self):
        result = subprocess.run(
            ["/bin/bash", str(ENTRY)], env={"PATH": "/usr/bin:/bin"},
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 78)
        self.assertIn("AI_CORE_DIR", result.stderr)

    def test_every_initial_field_is_required(self):
        fields = ("AI_CORE_DIR", "AI_CORE_CACHE_VOLUME", "AI_CORE_CACHE_IMAGE",
                  "AI_CORE_CACHE_BACKING_VOLUME", "AI_CORE_CACHE_BACKING_UUID",
                  "AI_CORE_CACHE_VOLUME_UUID", "AI_CORE_CACHE_MAX_BYTES")
        for missing in fields:
            with self.subTest(missing=missing):
                env = {key: "/does-not-exist" for key in fields if key != missing}
                result = subprocess.run(["/bin/bash", str(ENTRY)], env=env,
                                        capture_output=True, text=True, check=False)
                self.assertEqual(result.returncode, 78)
                self.assertIn(missing, result.stderr)

    def test_rejects_arbitrary_commands_and_pytest_overrides(self):
        entry = self.entry()
        for argv in (["echo", "hello"], ["-p", "other"], ["--basetemp=/tmp"], ["tests"],
                     [FOG_NODE, "--basetemp=/tmp"], [entry["NODE"], FOG_NODE],
                     [FOG_NODE + "[insufficient]"], [FOG_TOPOLOGY_NODE, "--basetemp=/tmp"],
                     [FOG_TOPOLOGY_NODE, FOG_NODE], [FOG_TOPOLOGY_NODE + "::unknown"]):
            with self.subTest(argv=argv), self.assertRaisesRegex(ValueError, "contracted"):
                entry["main"](argv)

    def test_missing_mount_wrong_uuid_and_device_fail_closed(self):
        entry = self.entry()
        for mount, uuid, device, inode in ((False, "UUID", 9, 1),
                                          (True, "OTHER", 9, 1),
                                          (True, "UUID", 10, 1),
                                          (True, "UUID", 9, 2)):
            with self.subTest(mount=mount, uuid=uuid, device=device, inode=inode):
                backing = mock.Mock()
                backing.is_mount.return_value = mount
                backing.is_symlink.return_value = False
                backing.lstat.return_value = SimpleNamespace(st_dev=9, st_ino=inode)
                gate = mock.Mock()
                gate.mounted_identity.return_value = {"VolumeUUID": uuid, "device": device}
                with mock.patch.object(os, "fstat", return_value=SimpleNamespace(st_dev=9, st_ino=1)):
                    with self.assertRaisesRegex(ValueError, "identity drift"):
                        entry["backing_identity"](gate, backing, "UUID", 99, 9)
        gate.mounted_identity.side_effect = FileNotFoundError("disk missing")
        with self.assertRaises(FileNotFoundError):
            entry["backing_identity"](gate, backing, "UUID", 99, 9)

    def run_fake_parent(self, drift_call=None, cleanup_result=True, code=0, argv=None):
        entry = self.entry()
        backing = ENTRY.parents[1]
        owned = backing / "tests"  # 僅借用現存目錄的 stat；不建立或清理 root。
        device = backing.stat().st_dev
        gate = mock.Mock()
        calls = 0
        def identity(_):
            nonlocal calls
            calls += 1
            return {"VolumeUUID": "WRONG" if calls == drift_call else "UUID", "device": device}
        gate.mounted_identity.side_effect = identity
        def pinned_create(*args, parent_fd, **kwargs):
            pinned, expected = os.fstat(parent_fd), backing.stat()
            self.assertEqual((pinned.st_dev, pinned.st_ino),
                             (expected.st_dev, expected.st_ino))
            return owned
        create = mock.Mock(side_effect=pinned_create)
        cleanup = mock.Mock(return_value=cleanup_result)
        lifecycle = SimpleNamespace(create_root=create, cleanup=cleanup, LifecycleError=RuntimeError)
        parsed = []
        def parse(argv):
            parsed.extend(argv)
            return SimpleNamespace(command=argv[argv.index("--"):])
        lifecycle.parser = lambda: SimpleNamespace(parse_args=parse)
        def run(args):
            self.assertEqual(tempfile.tempdir, str(backing))
            self.assertEqual(args.command[:3], [sys.executable, "-B", "-c"])
            root = lifecycle.create_root()
            self.assertEqual(os.environ["TOP10_MANAGED_ROOT_ID"], f"{device}:{owned.stat().st_ino}")
            lifecycle.cleanup(str(root), backing)
            return code
        lifecycle.command_run = run
        cache = mock.Mock()
        modules = {"runtime_cache_capacity_gate": gate, "tmp_artifact_lifecycle": lifecycle,
                   "app.external_cache": SimpleNamespace(ExternalCache=cache)}
        old_tmp, old_path = tempfile.tempdir, sys.path[:]
        try:
            with mock.patch.dict(sys.modules, modules), mock.patch.dict(os.environ, {
                "AI_CORE_DIR": str(backing), "AI_CORE_CACHE_BACKING_VOLUME": str(backing),
                "AI_CORE_CACHE_BACKING_UUID": "UUID",
            }), mock.patch.object(Path, "is_mount", return_value=True), contextlib.redirect_stdout(io.StringIO()) as output:
                if drift_call:
                    with self.assertRaisesRegex((ValueError, RuntimeError), "identity drift"):
                        entry["main"]([])
                else:
                    self.assertEqual(entry["main"]([] if argv is None else argv), code)
            self.assertIs(lifecycle.create_root, create)
            self.assertIs(lifecycle.cleanup, cleanup)
            self.assertEqual(tempfile.tempdir, old_tmp)
            return parsed, create, cleanup, output.getvalue(), cache
        finally:
            sys.path[:] = old_path

    def test_parent_budget_stop_proof_and_exit_mapping(self):
        parsed, create, cleanup, output, cache = self.run_fake_parent(code=7, cleanup_result=False)
        self.assertEqual(parsed[-1], self.entry()["NODE"])
        for key, value in (("--max-bytes", "8388608"), ("--max-file-count", "256"), ("--ttl-seconds", "30")):
            self.assertEqual(parsed[parsed.index(key) + 1], value)
        self.assertIn("--require-complete-stop-proof", parsed)
        self.assertIn("no:cacheprovider", parsed)
        self.assertIn("project_sandbox_symlink_fixture_policy.json", " ".join(parsed))
        self.assertIn('"cleanup": false', output)
        self.assertIn('"exit": 7', output)
        create.assert_called_once()
        cleanup.assert_called_once()
        cache.return_value.sample.assert_called_once()
        cache.return_value.close.assert_called_once()

    def test_fog_capacity_node_reaches_existing_child_with_same_budget(self):
        parsed, create, cleanup, _, _ = self.run_fake_parent(argv=[FOG_NODE])
        self.assertEqual(parsed[-1], FOG_NODE)
        for key, value in (("--max-bytes", "8388608"), ("--max-file-count", "256"),
                           ("--ttl-seconds", "30")):
            self.assertEqual(parsed[parsed.index(key) + 1], value)
        self.assertIn("--require-complete-stop-proof", parsed)
        create.assert_called_once()
        cleanup.assert_called_once()

    def test_fog_topology_node_uses_same_owned_root_and_stop_contract(self):
        parsed, create, cleanup, _, cache = self.run_fake_parent(argv=[FOG_TOPOLOGY_NODE])
        self.assertEqual(parsed[-1], FOG_TOPOLOGY_NODE)
        for key, value in (("--max-bytes", "8388608"), ("--max-file-count", "256"),
                           ("--ttl-seconds", "30")):
            self.assertEqual(parsed[parsed.index(key) + 1], value)
        self.assertIn("--require-complete-stop-proof", parsed)
        create.assert_called_once()
        cleanup.assert_called_once()
        cache.return_value.close.assert_called_once()

    def test_identity_drift_before_and_after_creation_and_before_cleanup(self):
        for drift in (1, 2, 3, 4):
            with self.subTest(drift=drift):
                _, create, cleanup, _, _ = self.run_fake_parent(drift_call=drift)
                self.assertEqual(create.call_count, int(drift >= 3))
                cleanup.assert_not_called()

    def test_child_execs_sandbox_without_fork_and_sets_cpu_limit(self):
        entry = self.entry()
        backing, owned = ENTRY.parents[1], ENTRY.parents[1] / "tests"
        st = owned.stat()
        env = {"AI_CORE_DIR": str(backing), "TMP_ARTIFACT_ROOT": str(owned),
               "AI_CORE_CACHE_BACKING_VOLUME": str(backing), "AI_CORE_CACHE_BACKING_UUID": "UUID",
               "TOP10_MANAGED_ROOT_ID": f"{st.st_dev}:{st.st_ino}"}
        fake_os = SimpleNamespace(environ=env, O_RDONLY=os.O_RDONLY, O_DIRECTORY=os.O_DIRECTORY,
                                  O_NOFOLLOW=os.O_NOFOLLOW, open=mock.Mock(return_value=99),
                                  fstat=mock.Mock(return_value=st), mkdir=mock.Mock(),
                                  close=mock.Mock(), execve=mock.Mock())
        mapping = mock.Mock(return_value={"TMPDIR": str(owned / "pytest/tmp")})
        profile = mock.Mock(return_value="existing-profile")
        resource = mock.Mock(RLIMIT_CPU=0)
        modules = {"os": fake_os, "resource": resource,
                   "runtime_cache_capacity_gate": SimpleNamespace(mounted_identity=lambda _: {
                       "VolumeUUID": "UUID", "device": st.st_dev}),
                   "app.external_cache": SimpleNamespace(external_environment=mapping),
                   "app.storage_safety": SimpleNamespace(_sandbox_profile=profile)}
        old_path = sys.path[:]
        try:
            with mock.patch.dict(sys.modules, modules), mock.patch.object(Path, "is_mount", return_value=True), mock.patch.object(sys, "argv", ["-c", "-p", "no:cacheprovider", entry["NODE"]]):
                exec(entry["CHILD"], {})
        finally:
            sys.path[:] = old_path
        resource.setrlimit.assert_called_once_with(0, (20, 20))
        mapping.assert_called_once_with(owned / "pytest")
        profile.assert_called_once_with(owned)
        executable, argv, child_env = fake_os.execve.call_args.args
        self.assertEqual(executable, "/usr/bin/sandbox-exec")
        self.assertEqual(argv[:6], ["sandbox-exec", "-p", "existing-profile", sys.executable, "-B", "-c"])
        self.assertIn("pytest.main(sys.argv[1:])", argv[6])
        self.assertIn("sitecustomize.py", argv[6])
        self.assertEqual(child_env["TOP10_MANAGED_BACKING_DEVICE"], str(st.st_dev))


if __name__ == "__main__":
    unittest.main()
