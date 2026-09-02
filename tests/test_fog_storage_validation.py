from __future__ import annotations

import hashlib
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENTRYPOINT = PROJECT_ROOT / "scripts" / "storage_validation" / "fog_research_worker.py"
REAL_RUNNER = PROJECT_ROOT / "scripts" / "run_fog_research_worker.sh"


class FogStorageValidationEntrypointTest(unittest.TestCase):
    def setUp(self) -> None:
        self.assertTrue(ENTRYPOINT.is_file(), "fog trusted entrypoint 尚未建立")

    def _sandbox(
        self,
        root: Path,
        *,
        real_runner_prologue: bool = False,
    ) -> tuple[Path, str]:
        sandbox = root
        scripts = sandbox / "scripts"
        validation = scripts / "storage_validation"
        python_bin = sandbox / ".venv" / "bin" / "python"
        artifacts = sandbox / "artifacts"
        validation.mkdir(parents=True)
        python_bin.parent.mkdir(parents=True)
        artifacts.mkdir()
        copied_entrypoint = validation / ENTRYPOINT.name
        copied_entrypoint.write_bytes(ENTRYPOINT.read_bytes())
        python_bin.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        python_bin.chmod(0o755)
        runner = scripts / "run_fog_research_worker.sh"
        prologue = (
            'cd "$(dirname "$0")/.."\n'
            '[[ -n "${BASH_VERSION:-}" ]] || exit 96\n'
            "if shopt -oq posix; then exit 97; fi\n"
            if real_runner_prologue
            else ""
        )
        runner_body = (
            "#!/bin/bash\n"
            "set -eu\n"
            f"{prologue}"
            "printf '%s\\n' \"$TOP10_DAILY_PYTHON\" \"$TOP10_FOG_RESEARCH_ENABLED\" "
            "\"$TOP10_FOG_RESEARCH_MAX_RETRIES\" \"$TOP10_FOG_RESEARCH_RECOVER_CIRCUIT\" "
            "\"$TOP10_REPLAY_DRAIN_ENABLED\" \"$HOME\" \"$TMPDIR\" \"$XDG_CACHE_HOME\" "
            "\"$XDG_CONFIG_HOME\" \"$XDG_DATA_HOME\" \"$XDG_STATE_HOME\" "
            "> artifacts/fog-entrypoint-env.txt\n"
            "/usr/bin/env > artifacts/fog-entrypoint-process-env.txt\n"
            "printf '%s\\n' \"$0\" \"$PWD\" > artifacts/fog-entrypoint-location.txt\n"
        )
        runner.write_text(runner_body, encoding="utf-8")
        runner.chmod(0o755)
        return copied_entrypoint, hashlib.sha256(runner.read_bytes()).hexdigest()

    def test_executes_only_digest_pinned_fog_runner_with_fixed_environment(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-fog-entrypoint-") as tmp:
            sandbox = Path(tmp)
            entrypoint, runner_digest = self._sandbox(sandbox)
            env = dict(os.environ)
            env.update(
                {
                    "TOP10_DAILY_PYTHON": "/tmp/untrusted-python",
                    "TOP10_FOG_RESEARCH_MAX_RETRIES": "99",
                    "TOP10_FOG_RESEARCH_RECOVER_CIRCUIT": "1",
                    "TOP10_REPLAY_DRAIN_ENABLED": "0",
                    "HOME": "/tmp/untrusted-home",
                    "TMPDIR": "/tmp/untrusted-tmp",
                    "XDG_CACHE_HOME": "/tmp/untrusted-cache",
                    "XDG_CONFIG_HOME": "/tmp/untrusted-config",
                    "XDG_DATA_HOME": "/tmp/untrusted-data",
                    "XDG_STATE_HOME": "/tmp/untrusted-state",
                }
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(entrypoint),
                    "--runner-sha256",
                    runner_digest,
                ],
                cwd=sandbox,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            runtime = (
                sandbox.resolve()
                / "logs"
                / "storage_safety"
                / "runtime"
                / "fog-research-worker"
            )
            self.assertEqual(
                (sandbox / "artifacts" / "fog-entrypoint-env.txt").read_text(
                    encoding="utf-8"
                ).splitlines(),
                [
                    str(sandbox.resolve() / ".venv" / "bin" / "python"),
                    "1",
                    "1",
                    "0",
                    "1",
                    str(runtime / "home"),
                    str(runtime / "tmp"),
                    str(runtime / "cache" / "xdg"),
                    str(runtime / "config" / "xdg"),
                    str(runtime / "data" / "xdg"),
                    str(runtime / "state" / "xdg"),
                ],
            )

    def test_hostile_shell_environment_cannot_swap_verified_runner(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-fog-entrypoint-hostile-") as tmp:
            sandbox = Path(tmp)
            entrypoint, runner_digest = self._sandbox(sandbox)
            runner = sandbox / "scripts" / "run_fog_research_worker.sh"
            injected = sandbox / "artifacts" / "shell-startup-injected.txt"
            swapped = sandbox / "artifacts" / "runner-swapped.txt"
            bash_env = sandbox / "hostile-bash-env.sh"
            bash_env.write_text(
                f"printf injected > {injected}\n"
                f"printf '%s\\n' '#!/bin/bash' 'printf swapped > {swapped}' > {runner}\n",
                encoding="utf-8",
            )
            env = dict(os.environ)
            env.update(
                {
                    "PATH": "/tmp/untrusted-path",
                    "LANG": "untrusted_LANG",
                    "LC_ALL": "untrusted_LC_ALL",
                    "BASH_ENV": str(bash_env),
                    "ENV": str(bash_env),
                    "SHELLOPTS": "braceexpand",
                    "BASHOPTS": "checkwinsize",
                    "CDPATH": "/tmp/untrusted-cdpath",
                    "GLOBIGNORE": "*",
                    "PROMPT_COMMAND": "printf injected",
                    "LD_TOP10_SENTINEL": "untrusted",
                    "DYLD_TOP10_SENTINEL": "untrusted",
                    "PYTHON_TOP10_SENTINEL": "untrusted",
                    "BASH_FUNC_top10_injected%%": "() { printf injected; }",
                }
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(entrypoint),
                    "--runner-sha256",
                    runner_digest,
                ],
                cwd=sandbox,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertFalse(injected.exists())
            self.assertFalse(swapped.exists())
            self.assertTrue((sandbox / "artifacts" / "fog-entrypoint-env.txt").is_file())
            child_environment = dict(
                line.split("=", 1)
                for line in (
                    sandbox / "artifacts" / "fog-entrypoint-process-env.txt"
                ).read_text(encoding="utf-8").splitlines()
                if "=" in line
            )
            self.assertEqual(child_environment["PATH"], "/usr/bin:/bin:/usr/sbin:/sbin")
            self.assertEqual(child_environment["LANG"], "C")
            self.assertEqual(child_environment["LC_ALL"], "C")
            self.assertEqual(child_environment["PYTHONDONTWRITEBYTECODE"], "1")
            for name in (
                "OMP_NUM_THREADS",
                "OPENBLAS_NUM_THREADS",
                "MKL_NUM_THREADS",
                "NUMEXPR_NUM_THREADS",
                "VECLIB_MAXIMUM_THREADS",
            ):
                self.assertEqual(child_environment[name], "1")
            forbidden_names = {
                "BASH_ENV",
                "ENV",
                "SHELLOPTS",
                "BASHOPTS",
                "CDPATH",
                "GLOBIGNORE",
                "PROMPT_COMMAND",
            }
            self.assertTrue(forbidden_names.isdisjoint(child_environment))
            self.assertFalse(
                any(
                    name.startswith(("BASH_FUNC_", "LD_", "DYLD_"))
                    or (
                        name.startswith("PYTHON")
                        and name != "PYTHONDONTWRITEBYTECODE"
                    )
                    for name in child_environment
                )
            )

    def test_fixed_bytecode_policy_blocks_source_tree_pyc_from_local_import(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-fog-entrypoint-bytecode-") as tmp:
            sandbox = Path(tmp)
            entrypoint, _runner_digest = self._sandbox(sandbox)
            scripts = sandbox / "scripts"
            python_bin = sandbox / ".venv" / "bin" / "python"
            python_bin.write_text(
                f'#!/bin/sh\nexec "{sys.executable}" "$@"\n',
                encoding="utf-8",
            )
            python_bin.chmod(0o755)
            (scripts / "probe_module.py").write_text("VALUE = 42\n", encoding="utf-8")
            (scripts / "import_probe.py").write_text(
                "import probe_module\nassert probe_module.VALUE == 42\n",
                encoding="utf-8",
            )
            runner = scripts / "run_fog_research_worker.sh"
            runner.write_text(
                "#!/bin/bash\n"
                "set -eu\n"
                '"$TOP10_DAILY_PYTHON" scripts/import_probe.py\n'
                "/usr/bin/env > artifacts/fog-entrypoint-bytecode-env.txt\n",
                encoding="utf-8",
            )
            runner_digest = hashlib.sha256(runner.read_bytes()).hexdigest()
            hostile_pycache = sandbox / "artifacts" / "hostile-pycache"
            env = dict(os.environ)
            env.update(
                {
                    "PYTHONDONTWRITEBYTECODE": "0",
                    "PYTHONPYCACHEPREFIX": str(hostile_pycache),
                    "PYTHONPATH": "/tmp/untrusted-pythonpath",
                    "PYTHONUSERBASE": "/tmp/untrusted-userbase",
                    "PYTHONINSPECT": "1",
                }
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(entrypoint),
                    "--runner-sha256",
                    runner_digest,
                ],
                cwd=sandbox,
                env=env,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            pyc_paths = sorted(
                path.relative_to(sandbox).as_posix()
                for path in scripts.rglob("*.pyc")
            )
            self.assertEqual(pyc_paths, [])
            self.assertFalse((scripts / "__pycache__").exists())
            self.assertFalse(hostile_pycache.exists())
            child_environment = dict(
                line.split("=", 1)
                for line in (
                    sandbox / "artifacts" / "fog-entrypoint-bytecode-env.txt"
                ).read_text(encoding="utf-8").splitlines()
                if "=" in line
            )
            self.assertEqual(child_environment["PYTHONDONTWRITEBYTECODE"], "1")
            self.assertTrue(
                {
                    "PYTHONPYCACHEPREFIX",
                    "PYTHONPATH",
                    "PYTHONUSERBASE",
                    "PYTHONINSPECT",
                }.isdisjoint(child_environment)
            )

    def test_verified_runner_preserves_real_runner_argv0_and_sandbox_cwd(self) -> None:
        self.assertIn(
            'cd "$(dirname "$0")/.."',
            REAL_RUNNER.read_text(encoding="utf-8"),
        )
        with tempfile.TemporaryDirectory(prefix="top10-fog-entrypoint-location-") as tmp:
            sandbox = Path(tmp)
            entrypoint, runner_digest = self._sandbox(
                sandbox,
                real_runner_prologue=True,
            )

            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(entrypoint),
                    "--runner-sha256",
                    runner_digest,
                ],
                cwd=sandbox,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertEqual(
                (sandbox / "artifacts" / "fog-entrypoint-location.txt").read_text(
                    encoding="utf-8"
                ).splitlines(),
                ["scripts/run_fog_research_worker.sh", str(sandbox.resolve())],
            )

    def test_verified_runner_stdin_is_not_pipe_limited_and_propagates_exit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-fog-entrypoint-exit-") as tmp:
            sandbox = Path(tmp)
            entrypoint, _runner_digest = self._sandbox(
                sandbox,
                real_runner_prologue=True,
            )
            runner = sandbox / "scripts" / "run_fog_research_worker.sh"
            runner.write_bytes(
                runner.read_bytes()
                + b"\n#"
                + (b"x" * (128 * 1024))
                + b"\nexit 37\n"
            )
            runner_digest = hashlib.sha256(runner.read_bytes()).hexdigest()

            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(entrypoint),
                    "--runner-sha256",
                    runner_digest,
                ],
                cwd=sandbox,
                text=True,
                capture_output=True,
                check=False,
                timeout=5,
            )

            self.assertEqual(completed.returncode, 37, completed.stderr)
            self.assertEqual(
                (sandbox / "artifacts" / "fog-entrypoint-location.txt").read_text(
                    encoding="utf-8"
                ).splitlines(),
                ["scripts/run_fog_research_worker.sh", str(sandbox.resolve())],
            )

    def test_rejects_raw_command_shape_before_runner_executes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-fog-entrypoint-raw-") as tmp:
            sandbox = Path(tmp)
            entrypoint, runner_digest = self._sandbox(sandbox)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(entrypoint),
                    "--runner-sha256",
                    runner_digest,
                    "/bin/sh",
                    "-c",
                    "true",
                ],
                cwd=sandbox,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 64)
            self.assertFalse((sandbox / "artifacts" / "fog-entrypoint-env.txt").exists())

    def test_rejects_runner_digest_mismatch_before_runner_executes(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-fog-entrypoint-digest-") as tmp:
            sandbox = Path(tmp)
            entrypoint, _runner_digest = self._sandbox(sandbox)

            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(entrypoint),
                    "--runner-sha256",
                    "0" * 64,
                ],
                cwd=sandbox,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 65)
            self.assertIn("runner digest 不符", completed.stderr)
            self.assertFalse((sandbox / "artifacts" / "fog-entrypoint-env.txt").exists())

    def test_rejects_git_scope_with_valid_runner_digest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-fog-entrypoint-git-") as tmp:
            sandbox = Path(tmp)
            entrypoint, runner_digest = self._sandbox(sandbox)
            (sandbox / ".git").mkdir()

            completed = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(entrypoint),
                    "--runner-sha256",
                    runner_digest,
                ],
                cwd=sandbox,
                text=True,
                capture_output=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 65)
            self.assertIn("git checkout", completed.stderr)
            self.assertFalse((sandbox / "artifacts" / "fog-entrypoint-env.txt").exists())


if __name__ == "__main__":
    unittest.main()
