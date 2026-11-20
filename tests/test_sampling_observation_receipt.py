"""M/R 共用診斷收據契約；由 Mainline 在兩個最小 stage 各跑一次。"""
import copy
import importlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest
from app import storage_safety as guard
from app.external_cache import ExternalCache, ExternalCacheError

PHASES = ("identity_foundation", "volume_info", "container_info", "scan", "admission_finalize")
COUNTERS = ("user_cpu_ns", "system_cpu_ns", "voluntary_context_switches",
            "involuntary_context_switches", "block_input_operations")
SECRET = "DO_NOT_PERSIST_path_argv_env_message_sampling_714a"
REASON = "EXTERNAL_CACHE_MANAGED_ADMISSION_DENIED"


def observation():
    return {"schema_version": "managed-cache-sampling-observation.v1", "clock": "monotonic_ns",
        "resource_scope": "RUSAGE_SELF", "children": "excluded",
        "phases": {name: {"status": "complete", "elapsed_ns": 10} for name in PHASES},
        "rusage": {"status": "complete", **dict.fromkeys(COUNTERS, 3)}}


@pytest.mark.parametrize("field", ["elapsed_ns", *COUNTERS])
@pytest.mark.parametrize("bad", [True, -1, 2**63, float("nan"), float("inf"), "17", 1.0])
def test_sanitizer_rejects_nonbounded_nonexact_integers(field, bad):
    value = observation()
    item = value["phases"]["scan"] if field == "elapsed_ns" else value["rusage"]
    item[field] = bad
    assert guard._sanitize_sampling_observation(value) is None


@pytest.mark.parametrize("case", ["extra", "phase_extra", "usage_extra", "unknown_schema", "unknown_clock",
    "children", "scope", "phase_status", "usage_status", "missing_phase", "skipped_zero", "skipped_identity", "mapping_subclass"])
def test_sanitizer_rejects_unknown_schema_and_strings(case):
    value = observation()
    if case == "extra": value[SECRET] = SECRET
    elif case == "phase_extra": value["phases"]["scan"][SECRET] = SECRET
    elif case == "usage_extra": value["rusage"][SECRET] = SECRET
    elif case == "unknown_schema": value["schema_version"] = SECRET
    elif case == "unknown_clock": value["clock"] = SECRET
    elif case == "children": value["children"] = SECRET
    elif case == "scope": value["resource_scope"] = "RUSAGE_CHILDREN"
    elif case == "phase_status": value["phases"]["scan"]["status"] = SECRET
    elif case == "usage_status": value["rusage"]["status"] = SECRET
    elif case == "missing_phase": del value["phases"]["scan"]
    elif case == "skipped_zero": value["phases"]["scan"] = {"status": "skipped", "elapsed_ns": 0}
    elif case == "skipped_identity": value["phases"]["identity_foundation"] = {"status": "skipped", "elapsed_ns": None}
    else:
        class Mapping(dict): pass
        value = Mapping(value)
    assert guard._sanitize_sampling_observation(value) is None


def test_sanitizer_reconstructs_valid_partial_and_unavailable_without_aliases():
    value = observation()
    value["phases"]["scan"] = {"status": "skipped", "elapsed_ns": None}
    value["phases"]["admission_finalize"] = {"status": "partial", "elapsed_ns": None}
    value["rusage"] = {"status": "unavailable", **dict.fromkeys(COUNTERS)}
    clean = guard._sanitize_sampling_observation(value)
    assert clean == value and clean is not value
    value["phases"]["volume_info"]["elapsed_ns"] = -1
    assert clean["phases"]["volume_info"]["elapsed_ns"] == 10


@pytest.mark.parametrize("error_kind", ["base", "timeout"])
@pytest.mark.parametrize("alias", ["runtime_cache_capacity_gate", "scripts.runtime_cache_capacity_gate"])
@pytest.mark.parametrize("case", ["actual", "bad_attr", "spoof_source", "spoof_class", "subclass", "other_reason", "diagnostic_failure"])
def test_receipt_loaded_core_only_redacted_and_marker_hash_inode_failclosed(tmp_path, monkeypatch, alias, case, error_kind):
    core = importlib.import_module(alias)
    managed = core.ManagedCache.__new__(core.ManagedCache)
    error_type = core.ManagedCacheTimeoutError if error_kind == "timeout" else core.ManagedCacheError
    def reject():
        error = error_type(SECRET) if error_kind == "timeout" else error_type(
            SECRET, core.EXIT_BUDGET, evidence={"private": SECRET})
        raise error from OSError(2, SECRET)
    managed._identity = reject
    with pytest.raises(core.ManagedCacheError) as caught:
        managed.sample()
    error = caught.value
    expected = copy.deepcopy(error.sampling_observation)
    expected_attempts = copy.deepcopy(error.sampling_attempts)
    assert type(expected) is dict
    if case == "bad_attr":
        error.sampling_observation = {"private": SECRET}
        error.sampling_attempts = {"private": SECRET}
    elif case == "spoof_source": monkeypatch.setattr(core, "__file__", "/" + SECRET)
    elif case == "spoof_class":
        # 名稱與 __module__ 相同也不是 loaded Core 的 class identity。
        fake = type(error_type.__name__, (ValueError,), {"__module__": alias})
        error = fake(SECRET)
        error.sampling_observation = expected
        error.sampling_attempts = expected_attempts
    elif case == "subclass":
        class Derived(error_type): pass
        error = Derived(SECRET)
        error.sampling_observation = expected
        error.sampling_attempts = expected_attempts
    elif case == "diagnostic_failure":
        def broken(_):
            raise RuntimeError(SECRET)
        monkeypatch.setattr(guard, "_sanitize_sampling_observation", broken)
        monkeypatch.setattr(guard, "_sanitize_sampling_attempts", broken)
    class Unprintable:
        def __str__(self): raise AssertionError("不可讀 str(error)")
        def __repr__(self): raise AssertionError("不可讀 repr(error)")
    error.args = (Unprintable(),)
    def fail():
        raise error
    cache = ExternalCache.__new__(ExternalCache)
    cache.directory_mode = True
    cache._managed = SimpleNamespace(sample=fail)
    def sampler(_):
        if case == "other_reason":
            raise ExternalCacheError("EXTERNAL_CACHE_RETENTION_EXPIRED") from error
        return cache.sample()
    monkeypatch.delenv("TOP10_EXTERNAL_CACHE_ROOT", raising=False)
    policy = Path(guard.__file__).resolve().parents[1] / "docs/operations/top10-storage-policy.json"
    gp, jp, rules = guard.load_policy(policy, "reference")
    assert guard.run_guarded_job(tmp_path, gp, jp, rules, ["/usr/bin/false"], sampler=sampler) == 70
    receipt = tmp_path / "logs/storage_safety/reference_latest.json"
    marker = tmp_path / "logs/storage_safety/restart_denied/reference.json"
    payload = json.loads(receipt.read_text())
    denial = json.loads(marker.read_text())
    assert payload["reasons"] == ["EXTERNAL_CACHE_RETENTION_EXPIRED" if case == "other_reason" else REASON]
    assert payload["child_exit_code"] is None
    detail = payload["internal_error"]
    assert SECRET not in json.dumps(detail)
    if case == "actual":
        assert detail["sampling_observation"] == expected
        assert detail["sampling_attempts"] == expected_attempts
        rows = detail["sampling_attempts"]["attempts"]
        assert [row["index"] for row in rows] == ([1, 2] if error_kind == "timeout" else [1])
        assert [row["status"] for row in rows] == (["TIMEOUT", "TIMEOUT"] if error_kind == "timeout" else ["FAIL"])
    else:
        assert "sampling_observation" not in detail and "sampling_attempts" not in detail
    if case in ("actual", "bad_attr", "diagnostic_failure"):
        assert detail["causes"][0]["type"] == error_type.__name__
        assert detail["causes"][0]["code"] == (23 if error_kind == "timeout" else 21)
    for cause in detail.get("causes", []):
        assert set(cause) <= {"type", "errno", "code", "frames"}
        for frame in cause.get("frames", []):
            assert set(frame) == {"filename", "function", "line"}
    assert denial["root_receipt"] == payload
    assert denial["root_receipt_sha256"] == guard._json_payload_sha256(payload)
    before = (receipt.read_bytes(), marker.read_bytes(), marker.stat().st_ino)
    def forbidden(_):
        pytest.fail("marker 已存在時不可再取樣或開 child")
    assert guard.run_guarded_job(tmp_path, gp, jp, rules, ["/usr/bin/false"], sampler=forbidden) == 75
    assert (receipt.read_bytes(), marker.read_bytes(), marker.stat().st_ino) == before


def test_existing_external_cache_success_forwards_measured_observation(tmp_path, monkeypatch):
    cache = ExternalCache.__new__(ExternalCache)
    cache.directory_mode = True
    cache.root = tmp_path / "job"
    cache.root.mkdir()
    cache.volume = tmp_path
    cache.device = None
    cache.root_identity = None
    cache.max_bytes, cache.max_files, cache.retention_seconds = 1024, 10, 60
    observed = observation()
    cache._managed = SimpleNamespace(sample=lambda: {"device": tmp_path.stat().st_dev,
        "volume_uuid": "fixture", "sampling_observation": observed, "sampling_attempts": attempts()})
    monkeypatch.setattr(Path, "is_mount", lambda _: True)
    payload = cache.sample()
    assert payload["sampling_observation"] == observed
    assert payload["sampling_attempts"] == attempts()


def attempts():
    return {"schema_version": "managed-cache-sampling-attempts.v1",
        "operation_budget_ns": 10_000_000_000, "attempt_budget_ns": 5_000_000_000,
        "attempts": [{"index": 1, "status": "TIMEOUT", "code": 23, "elapsed_ns": 5_000_000_000,
                      "sampling_observation": observation()},
                     {"index": 2, "status": "PASS", "code": 0, "elapsed_ns": 9,
                      "sampling_observation": observation()}]}


def test_attempts_sanitizer_copies_fixed_policy_and_original_observation_vocabulary():
    value = attempts()
    clean = guard._sanitize_sampling_attempts(value)
    assert clean == value and clean is not value
    assert clean["attempts"][0] is not value["attempts"][0]
    value["attempts"][0]["sampling_observation"]["phases"]["scan"]["elapsed_ns"] = -1
    assert clean["attempts"][0]["sampling_observation"]["phases"]["scan"]["elapsed_ns"] == 10
    value = attempts()
    value["attempts"][1]["sampling_observation"] = None
    assert guard._sanitize_sampling_attempts(value) == value


@pytest.mark.parametrize("field", ["index", "code", "elapsed_ns"])
@pytest.mark.parametrize("bad", [True, -1, 2**63, float("nan"), float("inf"), "17", 1.0])
def test_attempts_reject_bool_nan_and_unbounded_values(field, bad):
    value = attempts()
    value["attempts"][0][field] = bad
    assert guard._sanitize_sampling_attempts(value) is None


@pytest.mark.parametrize("case", ["extra", "item_extra", "empty", "third", "unknown_policy",
    "bool_policy", "float_policy", "nan_policy", "unknown_status", "status_subclass", "bad_code", "bad_index",
    "non_timeout_prefix", "private_observation", "observation_extra", "mapping_subclass", "list_subclass"])
def test_attempts_reject_pollution_and_limit_violations(case):
    value = attempts()
    if case == "extra": value[SECRET] = SECRET
    elif case == "item_extra": value["attempts"][0][SECRET] = SECRET
    elif case == "empty": value["attempts"] = []
    elif case == "third": value["attempts"].append(copy.deepcopy(value["attempts"][1]))
    elif case == "unknown_policy": value["attempt_budget_ns"] = 15_000_000_000
    elif case == "bool_policy": value["operation_budget_ns"] = True
    elif case == "float_policy": value["operation_budget_ns"] = 10_000_000_000.0
    elif case == "nan_policy": value["operation_budget_ns"] = float("nan")
    elif case == "unknown_status": value["attempts"][0]["status"] = SECRET
    elif case == "status_subclass":
        class Status(str): pass
        value["attempts"][0]["status"] = Status("TIMEOUT")
    elif case == "bad_code": value["attempts"][0]["code"] = 20
    elif case == "bad_index": value["attempts"][1]["index"] = 1
    elif case == "non_timeout_prefix": value["attempts"][0].update(status="FAIL", code=20)
    elif case == "private_observation": value["attempts"][0]["sampling_observation"] = {SECRET: SECRET}
    elif case == "observation_extra": value["attempts"][0]["sampling_observation"][SECRET] = SECRET
    elif case == "mapping_subclass":
        class Mapping(dict): pass
        value = Mapping(value)
    else:
        class Sequence(list): pass
        value["attempts"] = Sequence(value["attempts"])
    assert guard._sanitize_sampling_attempts(value) is None
