"""只驗profile字面mapping；不執行Seatbelt、不產生APFS或資源樣本。"""
from dataclasses import asdict, replace
import json
from pathlib import Path
import re
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from app import storage_safety as storage

ROOT = Path(__file__).resolve().parents[1]
LEDGER_ROOTS = (
    "data/research/research_ledger.duckdb",
    "data/research/research_ledger.duckdb.wal",
    "data/research/.research-ledger-rebuild",
)


@pytest.mark.parametrize("job,missing,expected_parent", [
    ("fog-research-worker", None, True),
    ("daily", None, False),
    ("other-job", None, False),
    *[("fog-research-worker", root, False) for root in LEDGER_ROOTS],
])
def test_only_complete_fog_ledger_roots_add_literal_parent(
    tmp_path, monkeypatch, job, missing, expected_parent,
):
    policy_path = ROOT / "docs/operations/top10-storage-policy.json"
    policy_bytes = policy_path.read_bytes()
    _, original_policy, _ = storage.load_policy(policy_path, "fog-research-worker")
    registered = tuple(p for p in original_policy.registered_write_paths if p != missing)
    policy = replace(original_policy, job=job, registered_write_paths=registered)
    before = asdict(policy)
    sandbox = tmp_path / "sandbox-exec"
    sandbox.write_text("fixture-not-executed")
    sandbox.chmod(0o700)
    monkeypatch.setattr(storage, "SANDBOX_EXECUTABLE", sandbox)
    # 只攔截profile組裝時的內建probe；沒有假造任何容量回傳值。
    runner = Mock(return_value=SimpleNamespace(returncode=0))
    monkeypatch.setattr(storage, "subprocess", SimpleNamespace(run=runner, DEVNULL=-3))
    cache = SimpleNamespace(
        root=tmp_path / "cache", directory_mode=True,
        _managed=SimpleNamespace(root=tmp_path / "managed-cache"),
        sample=Mock(return_value=None),
    )
    command = ["/bin/bash", "-c", "true"]
    emitted = storage._external_cache_spawn_command(tmp_path, policy, cache, command)
    profile = emitted[2]
    parent_literals = re.findall(
        r'^\(allow file-write-create \(literal (".*")\)\)$', profile, re.MULTILINE,
    )
    assert [json.loads(x) for x in parent_literals] == (
        [str(tmp_path / "data/research")] if expected_parent else []
    )
    # 原exact roots與cache是唯一subpath准寫；絕不加入data/research整樹。
    subpaths = re.findall(
        r'^\(allow file-write\* \(subpath (".*")\)\)$', profile, re.MULTILINE,
    )
    assert [json.loads(x) for x in subpaths] == [
        *(str(tmp_path / path) for path in registered), str(cache.root),
    ]
    assert str(tmp_path / "data/research") not in [json.loads(x) for x in subpaths]
    assert '(deny file-write*)' in profile
    assert emitted[:2] == [str(sandbox), "-p"] and emitted[3:] == command
    runner.assert_called_once()
    assert runner.call_args.args[0][2] == profile
    assert cache.sample.call_count == 2
    for ancestor in (cache._managed.root, *cache._managed.root.parents):
        assert f'(deny file-write-create (literal {json.dumps(str(ancestor))}))' in profile
    assert asdict(policy) == before
    assert policy_path.read_bytes() == policy_bytes
    assert (policy.max_bytes, policy.max_file_count, policy.max_process_tree_rss_bytes,
            policy.max_swap_growth_bytes, policy.sample_interval_seconds) == (
        2147483648, 30000, 2147483648, 2147483648, 60,
    )
