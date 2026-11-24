#!/usr/bin/env bash
set -euo pipefail
# 初始契約缺漏即拒絕，禁止 toolchain 走內建 fallback。
keys=(AI_CORE_DIR AI_CORE_CACHE_VOLUME AI_CORE_CACHE_VOLUME_UUID AI_CORE_CACHE_MAX_BYTES)
if [[ "${AI_CORE_CACHE_MODE:-image}" == "directory" ]]; then
  keys+=(AI_CORE_CACHE_ROOT AI_CORE_CACHE_MAX_FILES AI_CORE_CACHE_RESERVED_OTHER_BYTES)
else
  keys+=(AI_CORE_CACHE_IMAGE AI_CORE_CACHE_BACKING_VOLUME AI_CORE_CACHE_BACKING_UUID)
fi
for key in "${keys[@]}"; do
  if [[ -z "${!key:-}" ]]; then printf 'NO_GO: missing %s\n' "$key" >&2; exit 78; fi
done
source "$AI_CORE_DIR/config/toolchain_paths.sh"
cd "$(dirname "${BASH_SOURCE[0]}")/.."
export PYTHONDONTWRITEBYTECODE=1 PYTEST_DISABLE_PLUGIN_AUTOLOAD=1
unset PYTEST_ADDOPTS PYTEST_PLUGINS
exec .venv/bin/python -B - "$@" <<'PY_SHARED_ENTRY'
import json, os, resource, sys, tempfile
from pathlib import Path

NODE = "tests/test_storage_safety.py::StorageSafetyRegressionTest::test_overlapping_meter_paths_do_not_resolve_each_regular_file"
FOG_NODE = "tests/test_fog_shared_source.py::test_output_capacity_failure_denies_before_spawn"
FOG_TOPOLOGY_NODE = "tests/test_fog_inprocess_candidate.py::TestFogInprocessCandidate"
FLAGS = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW

def backing_identity(gate, backing, expected_uuid, fd, device=None):
    info = gate.mounted_identity(backing)
    pinned, current = os.fstat(fd), backing.lstat()
    if (not backing.is_mount() or backing.is_symlink()
            or info["VolumeUUID"] != expected_uuid
            or info["device"] != pinned.st_dev
            or (current.st_dev, current.st_ino) != (pinned.st_dev, pinned.st_ino)
            or (device is not None and device != pinned.st_dev)):
        raise ValueError("NO_GO: backing identity drift")
    return pinned.st_dev

CHILD = r'''
import json, os, resource, sys
from pathlib import Path
sys.path.insert(0, os.environ["AI_CORE_DIR"] + "/scripts")
import runtime_cache_capacity_gate as gate
from app.external_cache import external_environment
from app.storage_safety import _sandbox_profile
owned = Path(os.environ["TMP_ARTIFACT_ROOT"])
backing = Path(os.environ.get("AI_CORE_CACHE_BACKING_VOLUME", os.environ.get("AI_CORE_CACHE_VOLUME", "")))
device, inode = map(int, os.environ["TOP10_MANAGED_ROOT_ID"].split(":"))
flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
fd = os.open(owned, flags)
info = gate.mounted_identity(backing)
st = os.fstat(fd)
parent = (Path(os.environ["AI_CORE_CACHE_ROOT"]) / "tmp"
          if os.environ.get("AI_CORE_CACHE_MODE") == "directory" else backing)
if (owned.parent != parent or owned.resolve(strict=True) != owned
        or not backing.is_mount() or info["VolumeUUID"] != (os.environ.get("AI_CORE_CACHE_BACKING_UUID") or os.environ["AI_CORE_CACHE_VOLUME_UUID"])
        or info["device"] != device or (st.st_dev, st.st_ino) != (device, inode)):
    raise RuntimeError("NO_GO: child root identity drift")
os.mkdir("pytest", mode=0o700, dir_fd=fd)
sub = os.open("pytest", flags, dir_fd=fd)
os.mkdir("tmp", mode=0o700, dir_fd=sub)
os.close(sub)
os.close(fd)
env = {**os.environ, **external_environment(owned / "pytest")}
env["TOP10_MANAGED_PYTEST_ROOT"] = str(owned / "pytest")
env["TOP10_MANAGED_BACKING_DEVICE"] = str(device)
resource.setrlimit(resource.RLIMIT_CPU, (20, 20))
bootstrap = """
import os, runpy, sys, tempfile
from pathlib import Path
runpy.run_path(str(Path.cwd() / 'app/_storage_python/sitecustomize.py'))
root = Path(os.environ['TOP10_MANAGED_PYTEST_ROOT'])
if (tempfile.tempdir != str(root / 'tmp') or root.resolve(strict=True) != root
        or root.stat().st_dev != int(os.environ['TOP10_MANAGED_BACKING_DEVICE'])):
    raise RuntimeError('NO_GO: pytest mapping drift')
import pytest
raise SystemExit(pytest.main(sys.argv[1:]))
"""
os.execve("/usr/bin/sandbox-exec", ["sandbox-exec", "-p", _sandbox_profile(owned),
          sys.executable, "-B", "-c", bootstrap, *sys.argv[1:]], env)
'''

def main(argv):
    # 此契約只承接已列的單一離線 node，不轉送任意命令或 pytest 注入參數。
    if argv not in ([], [NODE], [FOG_NODE], [FOG_TOPOLOGY_NODE]):
        raise ValueError("NO_GO: only the contracted pytest node is accepted")
    selected_node = argv[0] if argv else NODE
    core = Path(os.environ["AI_CORE_DIR"])
    sys.path.insert(0, str(core / "scripts"))
    import runtime_cache_capacity_gate as gate
    import tmp_artifact_lifecycle as lifecycle
    from app.external_cache import ExternalCache
    cache = ExternalCache(Path.cwd(), "pytest-entry", 8388608, 256, 30)
    cache.sample()  # 真正 image 契約；不得以 backing 充當 image write root。
    backing = Path(os.environ.get("AI_CORE_CACHE_BACKING_VOLUME", os.environ.get("AI_CORE_CACHE_VOLUME", "")))
    if not backing.is_absolute() or backing.resolve(strict=True) != backing:
        raise ValueError("NO_GO: backing path must be canonical")
    fd = os.open(backing, FLAGS)
    directory_mode = os.environ.get("AI_CORE_CACHE_MODE") == "directory"
    parent = cache._managed.root / "tmp" if directory_mode else backing
    if directory_mode:
        cache._managed.materialize([parent])
    parent_fd = os.open(parent, FLAGS) if directory_mode else fd
    pinned_parent = os.fstat(parent_fd)
    original_run_child = getattr(lifecycle, "run_child", None)
    roots = {}
    original_create, original_cleanup = lifecycle.create_root, lifecycle.cleanup
    previous_tmp = tempfile.tempdir
    try:
        device = backing_identity(gate, backing, (os.environ.get("AI_CORE_CACHE_BACKING_UUID") or os.environ["AI_CORE_CACHE_VOLUME_UUID"]), fd)
        tempfile.tempdir = str(parent)  # 不呼叫 gettempdir 探測，缺卷不得 fallback。
        def check():
            try:
                backing_identity(gate, backing, (os.environ.get("AI_CORE_CACHE_BACKING_UUID") or os.environ["AI_CORE_CACHE_VOLUME_UUID"]), fd, device)
                if directory_mode:
                    cache.sample()
                    current = parent.lstat()
                    if (current.st_dev, current.st_ino) != (pinned_parent.st_dev, pinned_parent.st_ino):
                        raise ValueError("NO_GO: managed pytest parent identity drift")
            except (OSError, ValueError) as error:
                raise lifecycle.LifecycleError(str(error)) from error
        def create(*args, **kwargs):
            check()
            root = original_create(*args, parent_fd=parent_fd, **kwargs)
            check()
            st = root.lstat()
            if root.parent != parent or root.is_symlink() or st.st_dev != device:
                raise lifecycle.LifecycleError("NO_GO: owned root device drift")
            roots[str(root)] = (st.st_dev, st.st_ino)
            os.environ["TOP10_MANAGED_ROOT_ID"] = f"{st.st_dev}:{st.st_ino}"
            print(json.dumps({"root": str(root), "device": device}), flush=True)
            return root
        def cleanup(root, *args, **kwargs):
            check()
            st = Path(root).lstat()
            if Path(root).is_symlink() or (st.st_dev, st.st_ino) != roots.get(root):
                raise lifecycle.LifecycleError("NO_GO: cleanup root identity drift")
            result = original_cleanup(root, *args, **kwargs)
            check()
            print(json.dumps({"root": root, "cleanup": result}), flush=True)
            return result
        lifecycle.create_root, lifecycle.cleanup = create, cleanup
        if directory_mode:
            def run_child(command, env, controller=None, budget=None,
                          require_complete_stop_proof=False, resource_check=None):
                return original_run_child(command, env, controller, budget,
                                          require_complete_stop_proof, cache.sample)
            lifecycle.run_child = run_child
        args = lifecycle.parser().parse_args([
            "run", "--repo-root", str(Path.cwd()), "--policy",
            str(core / "config/project_sandbox_symlink_fixture_policy.json"),
            "--purpose", "top10-pytest", "--max-bytes", "8388608", "--max-file-count", "256",
            "--ttl-seconds", "30", "--require-complete-stop-proof", "--",
            sys.executable, "-B", "-c", CHILD, "-p", "no:cacheprovider", "-s", "-q", selected_node])
        args.command = args.command[1:]
        code = lifecycle.command_run(args)
        print(json.dumps({"exit": code}), flush=True)
        return code
    finally:
        lifecycle.create_root, lifecycle.cleanup = original_create, original_cleanup
        tempfile.tempdir = previous_tmp
        if directory_mode:
            lifecycle.run_child = original_run_child
            os.close(parent_fd)
        os.close(fd)
        cache.close()

if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
PY_SHARED_ENTRY
