from __future__ import annotations

import hashlib
import json
import os
import plistlib
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from unittest import mock


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEDULED_JOBS = {
    "daily": "run_daily_publish.sh",
    "retrain": "daily_retrain.sh",
    "reference": "run_reference_update.sh",
    "fog-research-worker": "run_fog_research_worker.sh",
    "pm-research-harness": "run_pm_research_harness_loop.sh",
    "external-review": "run_external_review_host_runner.sh",
    "external-review-preflight": "run_external_review_provider_preflight.sh",
    "baseline-harness": "run_baseline_harness_host_runner.sh",
}

from app.storage_safety import (  # noqa: E402
    GlobalPolicy,
    JobPolicy,
    ProcessGroupIdentity,
    RetentionRule,
    RotatingLog,
    Sample,
    TrustedValidationEntrypoint,
    UntrustedValidationEntrypoint,
    VALIDATION_ENTRYPOINT_SCHEMA_VERSION,
    _existing_lexical_directory,
    capture_process_group_identity,
    evaluate_preflight,
    evaluate_runtime,
    load_trusted_validation_entrypoint,
    load_policy,
    measure_paths,
    process_group_is_quiescent,
    read_memory_pressure_level,
    reclaim_allowlisted,
    run_guarded_job,
    terminate_process_group,
    unknown_changed_paths,
)
from scripts.storage_safety import _path_under_root, validate_isolated_root  # noqa: E402


def fixture_global_policy() -> GlobalPolicy:
    return GlobalPolicy(
        start_min_free_bytes=1024,
        start_min_free_percent=0.01,
        runtime_min_free_bytes=512,
        runtime_min_free_percent=0.01,
        require_swap_metric=True,
        log_max_bytes=4096,
        log_backups=2,
    )


def fixture_job_policy(**overrides: object) -> JobPolicy:
    policy = JobPolicy(
        job="daily",
        launch_verified=True,
        verification_basis="bounded fixture",
        meter_paths=("output", "logs"),
        registered_write_paths=("output", "logs"),
        cleanup_rule_ids=(),
        max_bytes=1024 * 1024,
        max_file_count=100,
        max_process_tree_rss_bytes=1024 * 1024,
        max_swap_growth_bytes=1024 * 1024,
        expected_growth_bytes_per_hour=1024 * 1024,
        spike_window_seconds=60,
        stabilize_after_seconds=60,
        reclaim_after_seconds=3600,
        retention_days=1,
        sample_interval_seconds=1,
    )
    return replace(policy, **overrides)


def validation_contract_fixture(
    sandbox: Path,
    body: str,
    *,
    argv: tuple[str, ...] = (),
    job: str = "daily",
) -> tuple[Path, dict[str, object]]:
    entrypoint = sandbox / "trusted_validation_harness.py"
    entrypoint.write_text(body, encoding="utf-8")
    entrypoint_digest = hashlib.sha256(entrypoint.read_bytes()).hexdigest()
    contract = sandbox / "trusted_validation_contract.json"
    contract.write_text(
        json.dumps(
            {
                "schema_version": VALIDATION_ENTRYPOINT_SCHEMA_VERSION,
                "job": job,
                "interpreter": "python-isolated",
                "entrypoint": entrypoint.name,
                "entrypoint_sha256": entrypoint_digest,
                "argv": list(argv),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    contract_digest = hashlib.sha256(contract.read_bytes()).hexdigest()
    marker: dict[str, object] = {
        "trusted_entrypoints": {
            job: {
                "contract_path": contract.name,
                "contract_sha256": contract_digest,
            }
        }
    }
    return contract, marker


def trusted_validation_fixture(
    sandbox: Path,
    body: str,
    *,
    argv: tuple[str, ...] = (),
    job: str = "daily",
) -> TrustedValidationEntrypoint:
    contract, marker = validation_contract_fixture(
        sandbox,
        body,
        argv=argv,
        job=job,
    )
    return load_trusted_validation_entrypoint(sandbox, job, marker, contract)


class FakeMonotonicClock:
    def __init__(self) -> None:
        self.value = 0.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


class HookedMonotonicClock(FakeMonotonicClock):
    def __init__(self) -> None:
        super().__init__()
        self._hook: Callable[[], None] | None = None
        self._skip_calls = 0

    def schedule_hook(self, hook: Callable[[], None], *, skip_calls: int = 0) -> None:
        self._hook = hook
        self._skip_calls = skip_calls

    def __call__(self) -> float:
        if self._hook is not None:
            if self._skip_calls > 0:
                self._skip_calls -= 1
            else:
                hook = self._hook
                self._hook = None
                hook()
        return self.value


class StorageSafetyRegressionTest(unittest.TestCase):
    def test_policy_contract_is_complete_and_verified_jobs_have_evidence(self) -> None:
        policy_path = PROJECT_ROOT / "docs" / "operations" / "top10-storage-policy.json"
        verified_jobs = {"daily", "external-review-preflight"}
        for job in SCHEDULED_JOBS:
            with self.subTest(job=job):
                global_policy, policy, rules = load_policy(policy_path, job)
                self.assertIs(policy.launch_verified, job in verified_jobs)
                self.assertTrue(policy.verification_basis)
                self.assertGreater(policy.max_bytes, 0)
                self.assertGreater(policy.max_file_count, 0)
                self.assertGreater(policy.max_process_tree_rss_bytes, 0)
                self.assertGreater(policy.max_swap_growth_bytes, 0)
                self.assertGreater(policy.expected_growth_bytes_per_hour, 0)
                self.assertGreater(policy.spike_window_seconds, 0)
                self.assertGreater(policy.stabilize_after_seconds, 0)
                self.assertGreater(policy.reclaim_after_seconds, 0)
                self.assertGreater(policy.retention_days, 0)
                self.assertLessEqual(policy.sample_interval_seconds, 300)
                self.assertTrue(policy.meter_paths)
                self.assertTrue(policy.registered_write_paths)
                self.assertTrue(rules)
                runtime_rule = next(rule for rule in rules if rule.rule_id == "runtime_workspace")
                self.assertEqual(
                    runtime_rule.base_path,
                    f"logs/storage_safety/runtime/{job}",
                )
                self.assertGreater(global_policy.start_min_free_bytes, global_policy.runtime_min_free_bytes)

        payload = json.loads(policy_path.read_text(encoding="utf-8"))
        _global_policy, fog_policy, _rules = load_policy(
            policy_path,
            "fog-research-worker",
        )
        self.assertIn("artifacts/host_runner", fog_policy.meter_paths)
        self.assertIn("data/research/research_ledger.duckdb", fog_policy.meter_paths)
        self.assertIn(
            "data/research/research_ledger.duckdb",
            fog_policy.registered_write_paths,
        )
        self.assertIn("data/research/research_ledger.duckdb.wal", fog_policy.meter_paths)
        self.assertIn(
            "data/research/research_ledger.duckdb.wal",
            fog_policy.registered_write_paths,
        )
        self.assertEqual(fog_policy.max_bytes, 2147483648)
        self.assertEqual(fog_policy.max_file_count, 30000)
        _global_policy, preflight_policy, _rules = load_policy(
            policy_path,
            "external-review-preflight",
        )
        self.assertTrue(preflight_policy.launch_verified)
        self.assertIn("probe_only", preflight_policy.verification_basis)
        self.assertIn("review_packet_sent=false", preflight_policy.verification_basis)
        self.assertIn("不授權安裝或啟用 LaunchAgent", preflight_policy.verification_basis)
        payload["jobs"]["daily"]["launch_verified"] = "false"
        with tempfile.TemporaryDirectory(prefix="top10-storage-policy-") as tmp:
            invalid = Path(tmp) / "invalid.json"
            invalid.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "JSON boolean"):
                load_policy(invalid, "daily")

    def test_unknown_write_detection_includes_deletions(self) -> None:
        before = {"registered/ok.txt": (1, 1), "source.py": (2, 2)}
        after = {"registered/ok.txt": (3, 3)}

        self.assertEqual(
            unknown_changed_paths(before, after, ("registered",)),
            ("source.py",),
        )

    def test_guard_stops_registered_new_and_modified_files_outside_meter(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-unmetered-") as tmp:
            fixture_root = Path(tmp).resolve()
            sandbox = fixture_root / "sandbox"
            source = fixture_root / "source"
            existing = sandbox / "artifacts" / "unmetered" / "existing.txt"
            existing.parent.mkdir(parents=True)
            existing.write_text("before\n", encoding="utf-8")
            (sandbox / "output").mkdir()
            source.mkdir()
            trusted = trusted_validation_fixture(
                sandbox,
                "from pathlib import Path\n"
                "import time\n"
                "Path('artifacts/unmetered/existing.txt').write_text('after')\n"
                "nested = Path('artifacts/unmetered/nested/new.txt')\n"
                "nested.parent.mkdir(parents=True)\n"
                "nested.write_text('new')\n"
                "time.sleep(0.1)\n",
            )
            policy = fixture_job_policy(
                launch_verified=False,
                meter_paths=(
                    "output",
                    "logs",
                    "artifacts/metered",
                    "artifacts/metered/nested",
                ),
                registered_write_paths=("output", "logs", "artifacts"),
            )
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)

            result = run_guarded_job(
                sandbox,
                fixture_global_policy(),
                policy,
                (),
                trusted.command,
                sampler=lambda _pid: replace(sample, timestamp=time.time()),
                validation_only=True,
                max_runtime_seconds=2,
                validation_context={"source_input_root": str(source)},
                trusted_validation_entrypoint=trusted,
            )
            receipt = json.loads(
                (sandbox / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(result, 70)
            self.assertIn("REGISTERED_WRITE_OUTSIDE_METER", receipt["reasons"])
            self.assertEqual(
                receipt["summary"]["registered_unmetered_changed_paths"],
                [
                    "artifacts/unmetered/existing.txt",
                    "artifacts/unmetered/nested/new.txt",
                ],
            )

    def test_overlapping_meter_paths_count_each_file_once(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-overlap-meter-") as tmp:
            root = Path(tmp)
            nested = root / "artifacts" / "metered" / "nested"
            nested.mkdir(parents=True)
            (root / "artifacts" / "metered" / "root.bin").write_bytes(b"123")
            (nested / "child.bin").write_bytes(b"4567")

            inventory = measure_paths(
                root,
                ("artifacts/metered", "artifacts/metered/nested"),
            )

            self.assertEqual(inventory.bytes, 7)
            self.assertEqual(inventory.file_count, 2)

    def test_preflight_and_runtime_stop_loss_signals_fail_closed(self) -> None:
        global_policy = fixture_global_policy()
        policy = fixture_job_policy(
            launch_verified=False,
            max_bytes=400,
            max_file_count=4,
            expected_growth_bytes_per_hour=10,
            spike_window_seconds=1,
            stabilize_after_seconds=1,
            reclaim_after_seconds=3600,
        )
        preflight = Sample(0, 401, 5, 10_000, 100, 0, None)
        preflight_decision = evaluate_preflight(global_policy, policy, preflight)
        self.assertTrue(preflight_decision.triggered)
        self.assertEqual(
            set(preflight_decision.reasons),
            {
                "POLICY_NOT_LIVE_VERIFIED",
                "PROJECT_BYTES_BUDGET_EXCEEDED",
                "PROJECT_FILE_COUNT_BUDGET_EXCEEDED",
                "HOST_START_FREE_SPACE_BELOW_THRESHOLD",
                "SWAP_METRIC_UNAVAILABLE",
            },
        )

        runtime_samples = [
            Sample(0, 10, 1, 100_000, 50_000, 10, 10),
            Sample(1, 100, 2, 100_000, 49_900, 20, 20),
            Sample(2, 300, 3, 100_000, 49_700, 30, 30),
        ]
        runtime_decision = evaluate_runtime(
            global_policy,
            policy,
            runtime_samples,
            unknown_paths=("unexpected/output.bin",),
        )
        self.assertTrue(runtime_decision.triggered)
        self.assertTrue(
            {
                "UNREGISTERED_WRITE_PATH",
                "SUSTAINED_GROWTH_RATE_WILL_BREAK_BUDGET",
                "NO_STABILIZATION_OR_RECLAIM",
                "RSS_AND_SWAP_RISING",
            }.issubset(set(runtime_decision.reasons))
        )
        hard_memory_decision = evaluate_runtime(
            global_policy,
            replace(
                policy,
                max_process_tree_rss_bytes=25,
                max_swap_growth_bytes=15,
            ),
            runtime_samples,
        )
        self.assertTrue(
            {
                "PROCESS_TREE_RSS_BUDGET_EXCEEDED",
                "MEMORY_PRESSURE_METRIC_UNAVAILABLE_SWAP_GROWTH_BUDGET_EXCEEDED",
            }.issubset(set(hard_memory_decision.reasons))
        )

        missing_rss = replace(runtime_samples[-1], rss_bytes=None)
        self.assertIn(
            "RSS_METRIC_UNAVAILABLE",
            evaluate_runtime(global_policy, policy, [missing_rss]).reasons,
        )
        critical_preflight = evaluate_preflight(
            global_policy,
            policy,
            replace(preflight, memory_pressure_level=3),
        )
        self.assertIn(
            "HOST_MEMORY_PRESSURE_CRITICAL_OR_JETSAM",
            critical_preflight.reasons,
        )

        validation_decision = evaluate_preflight(
            global_policy,
            replace(policy, max_bytes=1000, max_file_count=10),
            replace(
                preflight,
                project_bytes=1,
                project_file_count=1,
                host_free_bytes=50_000,
                swap_bytes=0,
            ),
            validation_only=True,
        )
        self.assertFalse(validation_decision.triggered)

    def test_rising_rss_and_global_swap_do_not_stop_when_memory_pressure_improves(
        self,
    ) -> None:
        samples = [
            Sample(0, 10, 1, 100_000, 50_000, 400, 10, memory_pressure_level=2),
            Sample(60, 10, 1, 100_000, 50_000, 700, 20, memory_pressure_level=2),
            Sample(120, 10, 1, 100_000, 50_000, 1000, 30, memory_pressure_level=1),
        ]

        decision = evaluate_runtime(
            fixture_global_policy(),
            fixture_job_policy(max_process_tree_rss_bytes=2000),
            samples,
        )

        self.assertNotIn("RSS_AND_SWAP_RISING", decision.reasons)

    def test_swap_growth_alone_does_not_stop_when_pressure_is_readable_and_non_critical(
        self,
    ) -> None:
        global_policy = fixture_global_policy()
        policy = fixture_job_policy(max_swap_growth_bytes=100)
        samples = [
            Sample(0, 10, 1, 100_000, 50_000, 1000, 0, memory_pressure_level=0),
            Sample(1, 10, 1, 100_000, 50_000, 1000, 150, memory_pressure_level=1),
            Sample(2, 10, 1, 100_000, 50_000, 1000, 250, memory_pressure_level=2),
        ]

        decision = evaluate_runtime(global_policy, policy, samples)

        self.assertFalse(decision.triggered)
        self.assertNotIn("SWAP_GROWTH_BUDGET_EXCEEDED", decision.reasons)

    def test_earlier_pressure_sensor_gap_does_not_poison_later_swap_growth(
        self,
    ) -> None:
        global_policy = fixture_global_policy()
        policy = fixture_job_policy(max_swap_growth_bytes=100)
        samples = [
            Sample(0, 10, 1, 100_000, 50_000, 1000, 0, memory_pressure_level=None),
            Sample(1, 10, 1, 100_000, 50_000, 1000, 50, memory_pressure_level=0),
            Sample(2, 10, 1, 100_000, 50_000, 1000, 250, memory_pressure_level=1),
        ]

        decision = evaluate_runtime(global_policy, policy, samples)

        self.assertFalse(decision.triggered)
        self.assertNotIn(
            "MEMORY_PRESSURE_METRIC_UNAVAILABLE_SWAP_GROWTH_BUDGET_EXCEEDED",
            decision.reasons,
        )

    def test_memory_pressure_runtime_stop_loss_distinguishes_emergency_and_fallback(
        self,
    ) -> None:
        global_policy = fixture_global_policy()
        policy = fixture_job_policy(max_swap_growth_bytes=100)
        single_critical = [
            Sample(0, 10, 1, 100_000, 50_000, 1000, 0, memory_pressure_level=0),
            Sample(1, 10, 1, 100_000, 50_000, 1000, 0, memory_pressure_level=3),
        ]
        two_critical = [
            Sample(0, 10, 1, 100_000, 50_000, 1000, 0, memory_pressure_level=0),
            Sample(1, 10, 1, 100_000, 50_000, 1000, 0, memory_pressure_level=3),
            Sample(2, 10, 1, 100_000, 50_000, 1000, 0, memory_pressure_level=4),
        ]
        unavailable_pressure_with_swap_growth = [
            Sample(0, 10, 1, 100_000, 50_000, 1000, 0, memory_pressure_level=None),
            Sample(1, 10, 1, 100_000, 50_000, 1000, 150, memory_pressure_level=None),
        ]

        self.assertFalse(evaluate_runtime(global_policy, policy, single_critical).triggered)
        self.assertIn(
            "MEMORY_PRESSURE_CRITICAL_OR_JETSAM",
            evaluate_runtime(global_policy, policy, two_critical).reasons,
        )
        self.assertEqual(
            evaluate_runtime(
                global_policy,
                policy,
                unavailable_pressure_with_swap_growth,
            ).reasons,
            ("MEMORY_PRESSURE_METRIC_UNAVAILABLE_SWAP_GROWTH_BUDGET_EXCEEDED",),
        )

    def test_read_memory_pressure_level_accepts_only_xnu_defined_values(self) -> None:
        def completed(stdout: str, returncode: int = 0) -> subprocess.CompletedProcess[str]:
            return subprocess.CompletedProcess(
                args=["sysctl"],
                returncode=returncode,
                stdout=stdout,
                stderr="",
            )

        with mock.patch("app.storage_safety.sys.platform", "darwin"):
            with mock.patch(
                "app.storage_safety.subprocess.run",
                return_value=completed("2\n"),
            ) as run:
                self.assertEqual(read_memory_pressure_level(), 2)
                self.assertEqual(
                    run.call_args.args[0],
                    ["/usr/sbin/sysctl", "-n", "kern.memorystatus_vm_pressure_level"],
                )
            with mock.patch(
                "app.storage_safety.subprocess.run",
                return_value=completed("5\n"),
            ):
                self.assertIsNone(read_memory_pressure_level())
            with mock.patch(
                "app.storage_safety.subprocess.run",
                return_value=completed("warning\n"),
            ):
                self.assertIsNone(read_memory_pressure_level())
            with mock.patch(
                "app.storage_safety.subprocess.run",
                return_value=completed("2\n", returncode=1),
            ):
                self.assertIsNone(read_memory_pressure_level())
            with mock.patch(
                "app.storage_safety.subprocess.run",
                side_effect=OSError,
            ):
                self.assertIsNone(read_memory_pressure_level())

        with mock.patch("app.storage_safety.sys.platform", "linux"):
            self.assertIsNone(read_memory_pressure_level())

    def test_allowlisted_reclaim_recovers_bytes_without_touching_protected_file(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-reclaim-") as tmp:
            root = Path(tmp)
            rebuildable = root / "artifacts" / "rebuildable"
            rebuildable.mkdir(parents=True)
            old_a = rebuildable / "old-a.bin"
            old_b = rebuildable / "old-b.bin"
            newest = rebuildable / "newest.bin"
            protected = root / "protected.txt"
            old_a.write_bytes(b"aaaa")
            old_b.write_bytes(b"bbbb")
            newest.write_bytes(b"new")
            protected.write_bytes(b"do-not-touch")
            os.utime(old_a, (1, 1))
            os.utime(old_b, (2, 2))
            os.utime(newest, (95, 95))
            protected_hash = protected.read_bytes()
            rule = RetentionRule(
                rule_id="fixture",
                base_path="artifacts/rebuildable",
                pattern="*",
                retention_seconds=10,
                max_files=1,
                max_bytes=4,
                protect_newest=1,
            )

            result = reclaim_allowlisted(root, (rule,), execute=True, now=100)

            self.assertLess(result.bytes_after, result.bytes_before)
            self.assertEqual(result.file_count_after, 1)
            self.assertTrue(newest.exists())
            self.assertFalse(old_a.exists())
            self.assertFalse(old_b.exists())
            self.assertEqual(protected.read_bytes(), protected_hash)

    def test_baseline_reclaim_never_matches_unlock_policy(self) -> None:
        policy_path = PROJECT_ROOT / "docs" / "operations" / "top10-storage-policy.json"
        _, _, rules = load_policy(policy_path, "baseline-harness")
        baseline_rule = next(rule for rule in rules if rule.rule_id == "baseline_outputs")
        constrained_rule = replace(
            baseline_rule,
            retention_seconds=1,
            max_files=1,
            max_bytes=1,
            protect_newest=0,
        )
        with tempfile.TemporaryDirectory(prefix="top10-storage-baseline-reclaim-") as tmp:
            root = Path(tmp)
            outputs = root / "artifacts" / "weekend_training"
            outputs.mkdir(parents=True)
            replay = outputs / "baseline_harness_medium_window_replay_2026-08-03.json"
            policy = outputs / "baseline_harness_unlock_policy_review_2026-06-21.json"
            replay.write_text("replay\n", encoding="utf-8")
            policy.write_text("policy\n", encoding="utf-8")
            os.utime(replay, (1, 1))
            os.utime(policy, (1, 1))

            result = reclaim_allowlisted(root, (constrained_rule,), execute=True, now=100)

            self.assertIn(
                "artifacts/weekend_training/baseline_harness_medium_window_replay_2026-08-03.json",
                result.removed_paths,
            )
            self.assertFalse(replay.exists())
            self.assertTrue(policy.exists())

    def test_guard_log_rotation_has_a_hard_size_and_backup_limit(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-log-") as tmp:
            log_path = Path(tmp) / "guard.log"
            rotating = RotatingLog(log_path, max_bytes=10, backups=2)
            try:
                for chunk in (b"123456", b"abcdef", b"ABCDEFGHIJKLM"):
                    rotating.write(chunk)
            finally:
                rotating.close()

            files = sorted(log_path.parent.glob("guard.log*"))
            self.assertLessEqual(len(files), 3)
            self.assertTrue(all(path.stat().st_size <= 10 for path in files))

    def test_process_group_stop_is_isolated_from_unrelated_process(self) -> None:
        protected = subprocess.Popen(["/bin/sleep", "30"], start_new_session=True)
        target = subprocess.Popen(
            ["/bin/sh", "-c", "/bin/sleep 30 & wait"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
        try:
            terminate_process_group(target, grace_seconds=1)
            self.assertIsNotNone(target.poll())
            self.assertIsNone(protected.poll())
        finally:
            if target.poll() is None:
                target.terminate()
                target.wait(timeout=2)
            if protected.poll() is None:
                protected.terminate()
                protected.wait(timeout=2)
            if target.stdout is not None:
                target.stdout.close()
            if target.stderr is not None:
                target.stderr.close()

    def test_leader_exit_does_not_leave_background_descendant(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-leader-exit-") as tmp:
            root = Path(tmp).resolve()
            (root / "output").mkdir()
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)
            background_pid: int | None = None
            try:
                result = run_guarded_job(
                    root,
                    fixture_global_policy(),
                    fixture_job_policy(),
                    (),
                    [
                        "/bin/sh",
                        "-c",
                        "/bin/sleep 30 >/dev/null 2>&1 & echo $! > output/background.pid; sleep 0.1",
                    ],
                    sampler=lambda _pid: replace(sample, timestamp=time.time()),
                )
                background_pid = int(
                    (root / "output" / "background.pid").read_text(encoding="utf-8")
                )
                receipt = json.loads(
                    (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                        encoding="utf-8"
                    )
                )

                self.assertEqual(result, 70)
                self.assertIn("PROCESS_GROUP_DESCENDANT_SURVIVED_LEADER", receipt["reasons"])
                with self.assertRaises(ProcessLookupError):
                    os.kill(background_pid, 0)
            finally:
                if background_pid is not None:
                    try:
                        os.kill(background_pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    def test_terminate_verified_group_after_leader_exit(self) -> None:
        target = subprocess.Popen(
            ["/bin/sh", "-c", "/bin/sleep 30 >/dev/null 2>&1 & sleep 0.1"],
            start_new_session=True,
        )
        identity = capture_process_group_identity(target)
        try:
            target.wait(timeout=2)
            self.assertFalse(process_group_is_quiescent(identity))

            terminate_process_group(target, grace_seconds=1, identity=identity)

            self.assertTrue(process_group_is_quiescent(identity))
        finally:
            if not process_group_is_quiescent(identity):
                try:
                    os.killpg(identity.group_id, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def test_process_group_identity_mismatch_fails_closed_without_signal(self) -> None:
        target = subprocess.Popen(["/bin/sleep", "30"], start_new_session=True)
        identity = capture_process_group_identity(target)
        mismatched = ProcessGroupIdentity(
            leader_pid=identity.leader_pid,
            group_id=identity.group_id,
            session_id=identity.session_id + 1,
            leader_start_token=identity.leader_start_token,
        )
        try:
            with self.assertRaisesRegex(RuntimeError, "identity 不符"):
                terminate_process_group(target, grace_seconds=1, identity=mismatched)
            self.assertIsNone(target.poll())
        finally:
            terminate_process_group(target, grace_seconds=1, identity=identity)

    def test_guard_stop_persists_restart_denial_without_touching_unrelated_process(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-stop-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            policy = fixture_job_policy(sample_interval_seconds=1)
            global_policy = fixture_global_policy()
            protected = subprocess.Popen(["/bin/sleep", "30"], start_new_session=True)
            sample_count = 0

            def sampler(_pid: int | None) -> Sample:
                nonlocal sample_count
                sample_count += 1
                return Sample(
                    timestamp=time.time(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000 if sample_count == 1 else 1,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            try:
                command = ["/bin/sh", "-c", "/bin/sleep 30 & wait"]
                stopped = run_guarded_job(
                    root,
                    global_policy,
                    policy,
                    (),
                    command,
                    sampler=sampler,
                )
                denied = run_guarded_job(
                    root,
                    global_policy,
                    policy,
                    (),
                    command,
                    sampler=sampler,
                )
                marker = root / "logs" / "storage_safety" / "restart_denied" / "daily.json"

                self.assertEqual(stopped, 70)
                self.assertEqual(denied, 75)
                self.assertTrue(marker.exists())
                self.assertIsNone(protected.poll())
            finally:
                if protected.poll() is None:
                    protected.terminate()
                    protected.wait(timeout=2)

    def test_guard_stops_when_latest_live_pressure_unavailable_and_swap_exceeds_budget(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-pressure-fallback-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            policy = fixture_job_policy(max_swap_growth_bytes=100, sample_interval_seconds=1)
            global_policy = fixture_global_policy()
            protected = subprocess.Popen(["/bin/sleep", "30"], start_new_session=True)
            sample_count = 0

            def sampler(_pid: int | None) -> Sample:
                nonlocal sample_count
                sample_count += 1
                is_latest_live = sample_count >= 3
                return Sample(
                    timestamp=time.time(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=250 if is_latest_live else 0,
                    memory_pressure_level=None if is_latest_live else 0,
                )

            try:
                result = run_guarded_job(
                    root,
                    global_policy,
                    policy,
                    (),
                    ["/bin/sh", "-c", "/bin/sleep 30 & wait"],
                    sampler=sampler,
                )
                receipt = json.loads(
                    (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                        encoding="utf-8"
                    )
                )
                marker = root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
                denial = json.loads(marker.read_text(encoding="utf-8"))

                self.assertEqual(result, 70)
                self.assertEqual(receipt["status"], "STOPPED")
                self.assertEqual(
                    receipt["reasons"],
                    [
                        "MEMORY_PRESSURE_METRIC_UNAVAILABLE_SWAP_GROWTH_BUDGET_EXCEEDED"
                    ],
                )
                self.assertEqual(denial["reasons"], receipt["reasons"])
                self.assertIsNone(protected.poll())
            finally:
                if protected.poll() is None:
                    protected.terminate()
                    protected.wait(timeout=2)

    def test_live_sampling_uses_monotonic_absolute_deadlines_without_drift(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-cadence-deadline-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()
            waits: list[float] = []
            live_sample_starts: list[float] = []
            sample_count = 0

            def sampler(pid: int | None) -> Sample:
                nonlocal sample_count
                sample_count += 1
                if pid is not None:
                    live_sample_starts.append(clock())
                    clock.advance(2.0)
                return Sample(
                    timestamp=1000.0 - sample_count,
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(process: subprocess.Popen[bytes], timeout: float) -> None:
                waits.append(timeout)
                if len(waits) <= 2:
                    clock.advance(timeout)
                    raise subprocess.TimeoutExpired(process.args, timeout)
                process.terminate()
                process.wait(timeout=2)

            result = run_guarded_job(
                root,
                fixture_global_policy(),
                fixture_job_policy(sample_interval_seconds=10),
                (),
                ["/bin/sleep", "30"],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(result, receipt["child_exit_code"])
            self.assertEqual(receipt["status"], "CHILD_FAILED")
            self.assertEqual(waits[:2], [7.5, 7.5])
            self.assertEqual(live_sample_starts[:3], [0.0, 9.5, 19.0])
            self.assertEqual(receipt["limits"]["sample_interval_seconds"], 10)
            self.assertNotIn("LIVE_SAMPLE_CADENCE_EXCEEDED", receipt["reasons"])

    def test_live_sampling_headroom_keeps_normal_overhead_and_lateness_within_hard_maximum(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-cadence-headroom-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()
            waits: list[float] = []
            live_completions: list[float] = []

            def sampler(pid: int | None) -> Sample:
                if pid is not None:
                    clock.advance(0.2)
                    live_completions.append(clock())
                return Sample(
                    timestamp=-clock(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(
                process: subprocess.Popen[bytes], timeout: float
            ) -> None:
                ready = root / "output" / "ready"
                ready_deadline = time.monotonic() + 2
                while not ready.exists() and time.monotonic() < ready_deadline:
                    time.sleep(0.001)
                self.assertTrue(ready.exists(), "fixture child 未完成 signal handler setup")
                waits.append(timeout)
                if len(waits) <= 2:
                    clock.advance(timeout + 0.005)
                    raise subprocess.TimeoutExpired(process.args, timeout)
                clock.advance(min(timeout / 2, 1.0))
                process.terminate()
                self.assertEqual(process.wait(timeout=2), 0)

            result = run_guarded_job(
                root,
                fixture_global_policy(),
                fixture_job_policy(sample_interval_seconds=60),
                (),
                [
                    sys.executable,
                    "-c",
                    "import signal,sys,time; from pathlib import Path; "
                    "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); "
                    "Path('output/ready').write_text('ready'); "
                    "time.sleep(30)",
                ],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial_path = (
                root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
            )
            completion_gaps = [
                later - earlier
                for earlier, later in zip(live_completions, live_completions[1:])
            ]

            self.assertEqual(
                result,
                0,
                f"completion_gaps={completion_gaps!r}, waits={waits!r}, "
                f"reasons={receipt['reasons']!r}",
            )
            self.assertEqual(receipt["status"], "OK")
            self.assertEqual(receipt["reasons"], [])
            self.assertFalse(denial_path.exists())
            self.assertEqual(len(live_completions), 3)
            self.assertEqual(len(completion_gaps), 2)
            self.assertTrue(all(gap <= 60 for gap in completion_gaps))
            self.assertAlmostEqual(completion_gaps[0], 57.005)
            self.assertAlmostEqual(completion_gaps[1], 57.0)
            self.assertEqual(len(waits), 3)
            self.assertTrue(all(timeout > 0 for timeout in waits))
            self.assertAlmostEqual(waits[0], 56.8)
            self.assertAlmostEqual(waits[1], 56.795)
            self.assertAlmostEqual(waits[2], 56.795)

    def test_live_sampling_hard_maximum_stops_true_completion_overrun(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-cadence-hard-max-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()
            waits: list[float] = []
            live_completions: list[float] = []
            target_pid: int | None = None

            def sampler(pid: int | None) -> Sample:
                nonlocal target_pid
                if pid is not None:
                    target_pid = pid
                    clock.advance(0.2)
                    live_completions.append(clock())
                return Sample(
                    timestamp=-clock(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(
                process: subprocess.Popen[bytes], timeout: float
            ) -> None:
                waits.append(timeout)
                clock.advance(timeout + 3.005)
                raise subprocess.TimeoutExpired(process.args, timeout)

            policy = fixture_job_policy(sample_interval_seconds=60)
            result = run_guarded_job(
                root,
                fixture_global_policy(),
                policy,
                (),
                ["/bin/sleep", "30"],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial_path = (
                root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
            )
            denial = json.loads(denial_path.read_text(encoding="utf-8"))
            denied = run_guarded_job(
                root,
                fixture_global_policy(),
                policy,
                (),
                ["/bin/sleep", "30"],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            completion_gap = live_completions[1] - live_completions[0]

            self.assertEqual((result, denied), (70, 75))
            self.assertEqual(receipt["status"], "STOPPED")
            self.assertEqual(receipt["reasons"], ["LIVE_SAMPLE_CADENCE_EXCEEDED"])
            self.assertEqual(
                [sample["phase"] for sample in receipt["samples"]],
                ["preflight", "live", "live"],
            )
            self.assertAlmostEqual(completion_gap, 60.005)
            self.assertEqual(len(waits), 1)
            self.assertGreater(waits[0], 0)
            self.assertAlmostEqual(waits[0], 56.8)
            self.assertEqual(denial["reasons"], ["LIVE_SAMPLE_CADENCE_EXCEEDED"])
            self.assertFalse(denial["automatic_clear_allowed"])
            self.assertIsNotNone(target_pid)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(target_pid), 0)

    def test_stale_sample_target_fails_closed_without_unbounded_no_wait_sampling(
        self,
    ) -> None:
        class StaleTargetIterationCap(RuntimeError):
            pass

        with tempfile.TemporaryDirectory(prefix="top10-storage-stale-target-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()
            waits: list[float] = []
            live_completions: list[float] = []
            target_pid: int | None = None

            def sampler(pid: int | None) -> Sample:
                nonlocal target_pid
                if pid is not None:
                    target_pid = pid
                    if len(live_completions) >= 5:
                        os.kill(pid, 0)
                        raise StaleTargetIterationCap(
                            "stale target regression 超過五次 live sample"
                        )
                    clock.advance(9.6)
                    live_completions.append(clock())
                return Sample(
                    timestamp=-clock(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(
                _process: subprocess.Popen[bytes], timeout: float
            ) -> None:
                waits.append(timeout)
                raise AssertionError("stale target 收斂前不應進入 waiter")

            policy = fixture_job_policy(sample_interval_seconds=10)
            result = run_guarded_job(
                root,
                fixture_global_policy(),
                policy,
                (),
                ["/bin/sleep", "30"],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial_path = (
                root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
            )
            denial = json.loads(denial_path.read_text(encoding="utf-8"))
            denied = run_guarded_job(
                root,
                fixture_global_policy(),
                policy,
                (),
                ["/bin/sleep", "30"],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            completion_gaps = [
                later - earlier
                for earlier, later in zip(live_completions, live_completions[1:])
            ]
            target_lags = [
                completion - (index * 9.5)
                for index, completion in enumerate(live_completions, start=1)
            ]
            red_context = (
                f"completions={live_completions!r}, gaps={completion_gaps!r}, "
                f"target_lags={target_lags!r}, waits={waits!r}, result={result!r}, "
                f"reasons={receipt['reasons']!r}"
            )

            self.assertEqual(result, 70, red_context)
            self.assertEqual(denied, 75, red_context)
            self.assertEqual(receipt["status"], "STOPPED", red_context)
            self.assertEqual(
                receipt["reasons"],
                ["LIVE_SAMPLE_SCHEDULE_OVERRUN"],
                red_context,
            )
            self.assertEqual(denial["reasons"], receipt["reasons"], red_context)
            self.assertFalse(denial["automatic_clear_allowed"])
            self.assertEqual(len(live_completions), 1, red_context)
            self.assertAlmostEqual(live_completions[0], 9.6)
            self.assertEqual(waits, [], red_context)
            self.assertIsNotNone(target_pid)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(target_pid), 0)

    def test_runtime_between_target_and_predicted_completion_preempts_sample(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-runtime-precedence-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()
            waits: list[float] = []
            live_completions: list[float] = []
            sampler_durations = [9.6, 9.6]
            target_pid: int | None = None

            def sampler(pid: int | None) -> Sample:
                nonlocal target_pid
                if pid is not None:
                    target_pid = pid
                    duration = sampler_durations[len(live_completions)]
                    clock.advance(duration)
                    live_completions.append(clock())
                return Sample(
                    timestamp=-clock(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(
                process: subprocess.Popen[bytes], timeout: float
            ) -> None:
                waits.append(timeout)
                clock.advance(timeout)
                raise subprocess.TimeoutExpired(process.args, timeout)

            policy = fixture_job_policy(sample_interval_seconds=10)
            result = run_guarded_job(
                root,
                fixture_global_policy(),
                policy,
                (),
                ["/bin/sleep", "30"],
                sampler=sampler,
                max_runtime_seconds=19.2,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial_path = (
                root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
            )
            denial = json.loads(denial_path.read_text(encoding="utf-8"))
            denied = run_guarded_job(
                root,
                fixture_global_policy(),
                policy,
                (),
                ["/bin/sleep", "30"],
                sampler=sampler,
                max_runtime_seconds=19.2,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            context = (
                f"completions={live_completions!r}, waits={waits!r}, "
                f"clock={clock()!r}, result={result!r}, "
                f"status={receipt['status']!r}, reasons={receipt['reasons']!r}"
            )

            self.assertEqual((result, denied), (70, 75), context)
            self.assertEqual(receipt["status"], "STOPPED", context)
            self.assertEqual(
                receipt["reasons"],
                ["HARD_RUNTIME_EXCEEDED"],
                context,
            )
            self.assertEqual(live_completions, [9.6], context)
            self.assertEqual(len(waits), 1, context)
            self.assertTrue(all(timeout > 0 for timeout in waits), context)
            self.assertAlmostEqual(waits[0], 9.6, msg=context)
            self.assertAlmostEqual(clock(), 19.2, msg=context)
            self.assertEqual(denial["reasons"], receipt["reasons"], context)
            self.assertFalse(denial["automatic_clear_allowed"])
            self.assertIsNotNone(target_pid)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(target_pid), 0)

    def test_first_write_cannot_bypass_wait_runtime_preemption(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-first-write-runtime-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()
            waits: list[float] = []
            live_completions: list[float] = []
            target_pid: int | None = None

            def sampler(pid: int | None) -> Sample:
                nonlocal target_pid
                if pid is not None:
                    target_pid = pid
                    clock.advance(9.6)
                    live_completions.append(clock())
                return Sample(
                    timestamp=-clock(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(
                process: subprocess.Popen[bytes], timeout: float
            ) -> None:
                waits.append(timeout)
                log_path = root / "logs" / "storage_safety" / "daily.log"
                deadline = time.monotonic() + 2
                while (
                    (not log_path.exists() or log_path.stat().st_size == 0)
                    and time.monotonic() < deadline
                ):
                    time.sleep(0.001)
                self.assertTrue(
                    log_path.exists() and log_path.stat().st_size > 0,
                    "WAIT_RUNTIME waiter 內未觀察到 first-write event",
                )
                clock.advance(timeout)
                raise subprocess.TimeoutExpired(process.args, timeout)

            policy = fixture_job_policy(sample_interval_seconds=10)
            command = [
                sys.executable,
                "-c",
                "import sys,time; "
                "sys.stdout.write('x' * 65536); sys.stdout.flush(); time.sleep(30)",
            ]
            result = run_guarded_job(
                root,
                fixture_global_policy(),
                policy,
                (),
                command,
                sampler=sampler,
                max_runtime_seconds=19.2,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial_path = (
                root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
            )
            denial = json.loads(denial_path.read_text(encoding="utf-8"))
            denied = run_guarded_job(
                root,
                fixture_global_policy(),
                policy,
                (),
                command,
                sampler=sampler,
                max_runtime_seconds=19.2,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            context = (
                f"completions={live_completions!r}, waits={waits!r}, "
                f"clock={clock()!r}, reasons={receipt['reasons']!r}"
            )

            self.assertEqual((result, denied), (70, 75), context)
            self.assertEqual(receipt["status"], "STOPPED", context)
            self.assertEqual(receipt["reasons"], ["HARD_RUNTIME_EXCEEDED"], context)
            self.assertEqual(live_completions, [9.6], context)
            self.assertEqual(waits, [9.6], context)
            self.assertTrue(all(timeout > 0 for timeout in waits), context)
            self.assertAlmostEqual(clock(), 19.2, msg=context)
            self.assertEqual(denial["reasons"], receipt["reasons"], context)
            self.assertFalse(denial["automatic_clear_allowed"])
            self.assertIsNotNone(target_pid)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(target_pid), 0)

    def test_runtime_deadline_target_and_predicted_completion_matrix(self) -> None:
        cases = (
            ("before_target", 9.4, [1.0]),
            ("equal_target", 9.5, [1.0]),
            ("after_target", 9.6, [1.0]),
            ("equal_predicted_completion", 10.5, [1.0, 10.5]),
            ("after_predicted_completion", 10.6, [1.0, 10.5]),
        )
        for name, runtime_deadline, expected_completions in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory(
                prefix=f"top10-storage-runtime-matrix-{name}-"
            ) as tmp:
                root = Path(tmp)
                (root / "output").mkdir()
                clock = FakeMonotonicClock()
                waits: list[float] = []
                live_completions: list[float] = []
                target_pid: int | None = None

                def sampler(pid: int | None) -> Sample:
                    nonlocal target_pid
                    if pid is not None:
                        target_pid = pid
                        clock.advance(1.0)
                        live_completions.append(clock())
                    return Sample(
                        timestamp=-clock(),
                        project_bytes=0,
                        project_file_count=0,
                        host_total_bytes=100_000,
                        host_free_bytes=50_000,
                        rss_bytes=1024,
                        swap_bytes=0,
                    )

                def wait_for_process(
                    process: subprocess.Popen[bytes], timeout: float
                ) -> None:
                    waits.append(timeout)
                    clock.advance(timeout)
                    raise subprocess.TimeoutExpired(process.args, timeout)

                policy = fixture_job_policy(sample_interval_seconds=10)
                result = run_guarded_job(
                    root,
                    fixture_global_policy(),
                    policy,
                    (),
                    ["/bin/sleep", "30"],
                    sampler=sampler,
                    max_runtime_seconds=runtime_deadline,
                    monotonic_clock=clock,
                    process_waiter=wait_for_process,
                )
                receipt = json.loads(
                    (
                        root / "logs" / "storage_safety" / "daily_latest.json"
                    ).read_text(encoding="utf-8")
                )
                denial = json.loads(
                    (
                        root
                        / "logs"
                        / "storage_safety"
                        / "restart_denied"
                        / "daily.json"
                    ).read_text(encoding="utf-8")
                )
                denied = run_guarded_job(
                    root,
                    fixture_global_policy(),
                    policy,
                    (),
                    ["/bin/sleep", "30"],
                    sampler=sampler,
                    max_runtime_seconds=runtime_deadline,
                    monotonic_clock=clock,
                    process_waiter=wait_for_process,
                )
                context = (
                    f"name={name!r}, runtime={runtime_deadline!r}, "
                    f"completions={live_completions!r}, waits={waits!r}, "
                    f"clock={clock()!r}, reasons={receipt['reasons']!r}"
                )

                self.assertEqual((result, denied), (70, 75), context)
                self.assertEqual(
                    receipt["reasons"],
                    ["HARD_RUNTIME_EXCEEDED"],
                    context,
                )
                self.assertEqual(live_completions, expected_completions, context)
                self.assertTrue(waits, context)
                self.assertTrue(all(timeout > 0 for timeout in waits), context)
                self.assertAlmostEqual(clock(), runtime_deadline, msg=context)
                self.assertEqual(denial["reasons"], receipt["reasons"], context)
                self.assertFalse(denial["automatic_clear_allowed"])
                self.assertIsNotNone(target_pid)
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(target_pid), 0)

    def test_runtime_deadline_sample_hard_deadline_matrix(self) -> None:
        cases = (
            ("before_sample_hard_deadline", 19.5, "HARD_RUNTIME_EXCEEDED"),
            ("equal_sample_hard_deadline", 19.6, "HARD_RUNTIME_EXCEEDED"),
            ("after_sample_hard_deadline", 19.7, "LIVE_SAMPLE_CADENCE_EXCEEDED"),
        )
        for name, runtime_deadline, expected_reason in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory(
                prefix=f"top10-storage-runtime-hard-matrix-{name}-"
            ) as tmp:
                root = Path(tmp)
                (root / "output").mkdir()
                clock = FakeMonotonicClock()
                waits: list[float] = []
                live_completions: list[float] = []
                sampler_durations = [9.6, 9.6]
                target_pid: int | None = None

                def sampler(pid: int | None) -> Sample:
                    nonlocal target_pid
                    if pid is not None:
                        target_pid = pid
                        duration = sampler_durations[len(live_completions)]
                        clock.advance(duration)
                        live_completions.append(clock())
                    return Sample(
                        timestamp=-clock(),
                        project_bytes=0,
                        project_file_count=0,
                        host_total_bytes=100_000,
                        host_free_bytes=50_000,
                        rss_bytes=1024,
                        swap_bytes=0,
                    )

                def wait_for_process(
                    process: subprocess.Popen[bytes], timeout: float
                ) -> None:
                    waits.append(timeout)
                    clock.advance(timeout)
                    raise subprocess.TimeoutExpired(process.args, timeout)

                policy = fixture_job_policy(sample_interval_seconds=10)
                result = run_guarded_job(
                    root,
                    fixture_global_policy(),
                    policy,
                    (),
                    ["/bin/sleep", "30"],
                    sampler=sampler,
                    max_runtime_seconds=runtime_deadline,
                    monotonic_clock=clock,
                    process_waiter=wait_for_process,
                )
                receipt = json.loads(
                    (
                        root / "logs" / "storage_safety" / "daily_latest.json"
                    ).read_text(encoding="utf-8")
                )
                denial = json.loads(
                    (
                        root
                        / "logs"
                        / "storage_safety"
                        / "restart_denied"
                        / "daily.json"
                    ).read_text(encoding="utf-8")
                )
                denied = run_guarded_job(
                    root,
                    fixture_global_policy(),
                    policy,
                    (),
                    ["/bin/sleep", "30"],
                    sampler=sampler,
                    max_runtime_seconds=runtime_deadline,
                    monotonic_clock=clock,
                    process_waiter=wait_for_process,
                )
                context = (
                    f"name={name!r}, runtime={runtime_deadline!r}, "
                    f"completions={live_completions!r}, waits={waits!r}, "
                    f"clock={clock()!r}, reasons={receipt['reasons']!r}"
                )

                self.assertEqual((result, denied), (70, 75), context)
                self.assertEqual(receipt["reasons"], [expected_reason], context)
                self.assertEqual(live_completions, [9.6], context)
                self.assertTrue(waits, context)
                self.assertTrue(all(timeout > 0 for timeout in waits), context)
                self.assertAlmostEqual(clock(), runtime_deadline, msg=context)
                self.assertEqual(denial["reasons"], receipt["reasons"], context)
                self.assertFalse(denial["automatic_clear_allowed"])
                self.assertIsNotNone(target_pid)
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(target_pid), 0)

    def test_actual_cadence_violation_before_runtime_keeps_cadence_reason(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-cadence-before-runtime-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()
            waits: list[float] = []
            live_completions: list[float] = []
            sampler_durations = [0.2, 0.7]
            target_pid: int | None = None

            def sampler(pid: int | None) -> Sample:
                nonlocal target_pid
                if pid is not None:
                    target_pid = pid
                    duration = sampler_durations[len(live_completions)]
                    clock.advance(duration)
                    live_completions.append(clock())
                return Sample(
                    timestamp=-clock(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(
                process: subprocess.Popen[bytes], timeout: float
            ) -> None:
                waits.append(timeout)
                clock.advance(timeout + 0.1)
                raise subprocess.TimeoutExpired(process.args, timeout)

            policy = fixture_job_policy(sample_interval_seconds=10)
            result = run_guarded_job(
                root,
                fixture_global_policy(),
                policy,
                (),
                ["/bin/sleep", "30"],
                sampler=sampler,
                max_runtime_seconds=11.0,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial = json.loads(
                (
                    root
                    / "logs"
                    / "storage_safety"
                    / "restart_denied"
                    / "daily.json"
                ).read_text(encoding="utf-8")
            )
            denied = run_guarded_job(
                root,
                fixture_global_policy(),
                policy,
                (),
                ["/bin/sleep", "30"],
                sampler=sampler,
                max_runtime_seconds=11.0,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            context = (
                f"completions={live_completions!r}, waits={waits!r}, "
                f"clock={clock()!r}, reasons={receipt['reasons']!r}"
            )

            self.assertEqual((result, denied), (70, 75), context)
            self.assertEqual(
                receipt["reasons"],
                ["LIVE_SAMPLE_CADENCE_EXCEEDED"],
                context,
            )
            self.assertEqual(len(live_completions), 2, context)
            self.assertAlmostEqual(live_completions[0], 0.2, msg=context)
            self.assertAlmostEqual(live_completions[1], 10.3, msg=context)
            self.assertLess(clock(), 11.0, context)
            self.assertEqual(waits, [9.3], context)
            self.assertEqual(denial["reasons"], receipt["reasons"], context)
            self.assertFalse(denial["automatic_clear_allowed"])
            self.assertIsNotNone(target_pid)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(target_pid), 0)

    def test_sampler_completion_orders_runtime_against_actual_cadence_deadline(
        self,
    ) -> None:
        cases = (
            ("runtime_before_actual_cadence_deadline", 9.9, "HARD_RUNTIME_EXCEEDED"),
            ("runtime_equal_actual_cadence_deadline", 10.0, "HARD_RUNTIME_EXCEEDED"),
            ("runtime_after_actual_cadence_deadline", 10.05, "LIVE_SAMPLE_CADENCE_EXCEEDED"),
        )
        for name, runtime_deadline, expected_reason in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory(
                prefix=f"top10-storage-sampler-runtime-order-{name}-"
            ) as tmp:
                root = Path(tmp)
                (root / "output").mkdir()
                clock = FakeMonotonicClock()
                live_completions: list[float] = []
                target_pid: int | None = None

                def sampler(pid: int | None) -> Sample:
                    nonlocal target_pid
                    if pid is not None:
                        target_pid = pid
                        clock.advance(10.1)
                        live_completions.append(clock())
                    return Sample(
                        timestamp=-clock(),
                        project_bytes=0,
                        project_file_count=0,
                        host_total_bytes=100_000,
                        host_free_bytes=50_000,
                        rss_bytes=1024,
                        swap_bytes=0,
                    )

                policy = fixture_job_policy(sample_interval_seconds=10)
                result = run_guarded_job(
                    root,
                    fixture_global_policy(),
                    policy,
                    (),
                    ["/bin/sleep", "30"],
                    sampler=sampler,
                    max_runtime_seconds=runtime_deadline,
                    monotonic_clock=clock,
                )
                receipt = json.loads(
                    (
                        root / "logs" / "storage_safety" / "daily_latest.json"
                    ).read_text(encoding="utf-8")
                )
                denial = json.loads(
                    (
                        root
                        / "logs"
                        / "storage_safety"
                        / "restart_denied"
                        / "daily.json"
                    ).read_text(encoding="utf-8")
                )
                denied = run_guarded_job(
                    root,
                    fixture_global_policy(),
                    policy,
                    (),
                    ["/bin/sleep", "30"],
                    sampler=sampler,
                    max_runtime_seconds=runtime_deadline,
                    monotonic_clock=clock,
                )
                context = (
                    f"name={name!r}, runtime={runtime_deadline!r}, "
                    f"completions={live_completions!r}, clock={clock()!r}, "
                    f"reasons={receipt['reasons']!r}"
                )

                self.assertEqual((result, denied), (70, 75), context)
                self.assertEqual(receipt["reasons"], [expected_reason], context)
                self.assertEqual(live_completions, [10.1], context)
                self.assertEqual(denial["reasons"], receipt["reasons"], context)
                self.assertFalse(denial["automatic_clear_allowed"])
                self.assertIsNotNone(target_pid)
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(target_pid), 0)

    def test_first_write_crossing_target_reconciles_to_positive_wait(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-first-write-target-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()
            waits: list[float] = []
            live_completions: list[float] = []
            pre_first_write_waits = 0

            def sampler(pid: int | None) -> Sample:
                if pid is not None:
                    clock.advance(9.49 if not live_completions else 0.02)
                    live_completions.append(clock())
                return Sample(
                    timestamp=-clock(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(
                process: subprocess.Popen[bytes], timeout: float
            ) -> None:
                nonlocal pre_first_write_waits
                waits.append(timeout)
                if len(live_completions) == 1:
                    pre_first_write_waits += 1
                    if pre_first_write_waits > 200:
                        raise AssertionError("first-write pump 未在 bounded waits 內就緒")
                    time.sleep(0.01)
                    return None
                clock.advance(min(timeout / 2, 1.0))
                process.terminate()
                self.assertEqual(process.wait(timeout=2), 0)

            result = run_guarded_job(
                root,
                fixture_global_policy(),
                fixture_job_policy(sample_interval_seconds=10),
                (),
                [
                    sys.executable,
                    "-c",
                    "import signal,sys,time; "
                    "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); "
                    "sys.stdout.write('x' * 65536); sys.stdout.flush(); time.sleep(30)",
                ],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial_path = (
                root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
            )

            context = (
                f"completions={live_completions!r}, wait_count={len(waits)!r}, "
                f"last_waits={waits[-3:]!r}, "
                f"status={receipt['status']!r}, reasons={receipt['reasons']!r}, "
                f"child_exit_code={receipt['child_exit_code']!r}"
            )
            self.assertEqual(result, 0, context)
            self.assertEqual(receipt["status"], "OK")
            self.assertEqual(receipt["reasons"], [])
            self.assertFalse(denial_path.exists())
            self.assertEqual(len(live_completions), 2, live_completions)
            self.assertAlmostEqual(live_completions[0], 9.49)
            self.assertAlmostEqual(live_completions[1], 9.51)
            self.assertTrue(waits)
            self.assertTrue(all(timeout > 0 for timeout in waits), waits)
            self.assertAlmostEqual(waits[-1], 9.49)

    def test_scheduled_observation_consumes_first_write_pending_from_waiter(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-first-write-coalesce-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()
            waits: list[float] = []
            live_completions: list[float] = []
            sampler_durations = [0.1, 0.1, 10.1]
            target_pid: int | None = None

            def sampler(pid: int | None) -> Sample:
                nonlocal target_pid
                if pid is not None:
                    target_pid = pid
                    duration = sampler_durations[len(live_completions)]
                    clock.advance(duration)
                    live_completions.append(clock())
                return Sample(
                    timestamp=-clock(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(
                process: subprocess.Popen[bytes], timeout: float
            ) -> None:
                waits.append(timeout)
                if len(waits) == 1:
                    (root / "output" / "emit").write_text("emit", encoding="utf-8")
                    log_path = root / "logs" / "storage_safety" / "daily.log"
                    deadline = time.monotonic() + 2
                    while (
                        (not log_path.exists() or log_path.stat().st_size == 0)
                        and time.monotonic() < deadline
                    ):
                        time.sleep(0.001)
                    self.assertTrue(
                        log_path.exists() and log_path.stat().st_size > 0,
                        "first-write event 未在首次 waiter 內完成 set",
                    )
                    clock.advance(timeout)
                    raise subprocess.TimeoutExpired(process.args, timeout)
                clock.advance(min(timeout / 2, 1.0))
                process.terminate()
                self.assertEqual(process.wait(timeout=2), 0)

            policy = fixture_job_policy(sample_interval_seconds=10)
            result = run_guarded_job(
                root,
                fixture_global_policy(),
                policy,
                (),
                [
                    sys.executable,
                    "-c",
                    "import signal,sys,time\n"
                    "from pathlib import Path\n"
                    "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n"
                    "trigger = Path('output/emit')\n"
                    "deadline = time.monotonic() + 5\n"
                    "while not trigger.exists() and time.monotonic() < deadline:\n"
                    "    time.sleep(0.001)\n"
                    "sys.stdout.write('x' * 65536)\n"
                    "sys.stdout.flush()\n"
                    "time.sleep(30)\n",
                ],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial_path = (
                root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
            )
            context = (
                f"completions={live_completions!r}, waits={waits!r}, "
                f"clock={clock()!r}, result={result!r}, "
                f"status={receipt['status']!r}, reasons={receipt['reasons']!r}"
            )

            self.assertEqual(result, 0, context)
            self.assertEqual(receipt["status"], "OK", context)
            self.assertEqual(receipt["reasons"], [], context)
            self.assertEqual(live_completions, [0.1, 9.6], context)
            self.assertEqual(len(live_completions), 2, context)
            self.assertEqual(len(waits), 2, context)
            self.assertTrue(all(timeout > 0 for timeout in waits), context)
            self.assertAlmostEqual(waits[0], 9.4, msg=context)
            self.assertAlmostEqual(waits[1], 9.4, msg=context)
            self.assertFalse(denial_path.exists(), context)
            self.assertIsNotNone(target_pid)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(target_pid), 0)

    def test_first_write_observation_ownership_window_matrix(self) -> None:
        cases = (
            ("waiter", [0.1, 9.6], [9.4, 9.4], 0.1),
            ("before_scheduled_sample", [0.1, 9.6], [9.4, 9.4], 9.5),
            ("during_scheduled_sample", [0.1, 9.6, 19.1], [9.4, 9.4, 9.4], 9.5),
            ("after_scheduled_sample", [0.1, 9.6, 19.1], [9.4, 9.4, 9.4], 9.6),
        )
        for window, expected_completions, expected_waits, expected_event_at in cases:
            with self.subTest(window=window), tempfile.TemporaryDirectory(
                prefix=f"top10-storage-first-write-{window}-"
            ) as tmp:
                root = Path(tmp)
                (root / "output").mkdir()
                clock = HookedMonotonicClock()
                waits: list[float] = []
                live_completions: list[float] = []
                event_times: list[float] = []
                target_pid: int | None = None

                def trigger_first_write() -> None:
                    if event_times:
                        return
                    event_times.append(clock.value)
                    (root / "output" / "emit").write_text("emit", encoding="utf-8")
                    log_path = root / "logs" / "storage_safety" / "daily.log"
                    deadline = time.monotonic() + 2
                    while (
                        (not log_path.exists() or log_path.stat().st_size == 0)
                        and time.monotonic() < deadline
                    ):
                        time.sleep(0.001)
                    self.assertTrue(
                        log_path.exists() and log_path.stat().st_size > 0,
                        f"{window}: first-write event 未完成 set",
                    )

                def sampler(pid: int | None) -> Sample:
                    nonlocal target_pid
                    if pid is not None:
                        target_pid = pid
                        scheduled_sample = len(live_completions) == 1
                        if window == "during_scheduled_sample" and scheduled_sample:
                            trigger_first_write()
                        clock.advance(0.1)
                        live_completions.append(clock.value)
                        sample = Sample(
                            timestamp=-clock(),
                            project_bytes=0,
                            project_file_count=0,
                            host_total_bytes=100_000,
                            host_free_bytes=50_000,
                            rss_bytes=1024,
                            swap_bytes=0,
                        )
                        if window == "after_scheduled_sample" and scheduled_sample:
                            clock.schedule_hook(trigger_first_write, skip_calls=1)
                        return sample
                    return Sample(
                        timestamp=-clock(),
                        project_bytes=0,
                        project_file_count=0,
                        host_total_bytes=100_000,
                        host_free_bytes=50_000,
                        rss_bytes=1024,
                        swap_bytes=0,
                    )

                def wait_for_process(
                    process: subprocess.Popen[bytes], timeout: float
                ) -> None:
                    waits.append(timeout)
                    if len(waits) == 1:
                        if window == "waiter":
                            trigger_first_write()
                        clock.advance(timeout)
                        if window == "before_scheduled_sample":
                            clock.schedule_hook(trigger_first_write)
                        raise subprocess.TimeoutExpired(process.args, timeout)
                    if len(waits) < len(expected_waits):
                        clock.advance(timeout)
                        raise subprocess.TimeoutExpired(process.args, timeout)
                    clock.advance(min(timeout / 2, 1.0))
                    process.terminate()
                    self.assertEqual(process.wait(timeout=2), 0)

                result = run_guarded_job(
                    root,
                    fixture_global_policy(),
                    fixture_job_policy(sample_interval_seconds=10),
                    (),
                    [
                        sys.executable,
                        "-c",
                        "import signal,sys,time\n"
                        "from pathlib import Path\n"
                        "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))\n"
                        "trigger = Path('output/emit')\n"
                        "deadline = time.monotonic() + 5\n"
                        "while not trigger.exists() and time.monotonic() < deadline:\n"
                        "    time.sleep(0.001)\n"
                        "sys.stdout.write('x' * 65536)\n"
                        "sys.stdout.flush()\n"
                        "time.sleep(30)\n",
                    ],
                    sampler=sampler,
                    monotonic_clock=clock,
                    process_waiter=wait_for_process,
                )
                receipt = json.loads(
                    (
                        root / "logs" / "storage_safety" / "daily_latest.json"
                    ).read_text(encoding="utf-8")
                )
                denial_path = (
                    root
                    / "logs"
                    / "storage_safety"
                    / "restart_denied"
                    / "daily.json"
                )
                context = (
                    f"window={window!r}, event_times={event_times!r}, "
                    f"completions={live_completions!r}, waits={waits!r}, "
                    f"status={receipt['status']!r}, reasons={receipt['reasons']!r}"
                )

                self.assertEqual(result, 0, context)
                self.assertEqual(receipt["status"], "OK", context)
                self.assertEqual(receipt["reasons"], [], context)
                self.assertEqual(len(event_times), 1, context)
                self.assertAlmostEqual(event_times[0], expected_event_at, msg=context)
                self.assertEqual(len(live_completions), len(expected_completions), context)
                for actual, expected in zip(live_completions, expected_completions):
                    self.assertAlmostEqual(actual, expected, msg=context)
                self.assertEqual(len(waits), len(expected_waits), context)
                self.assertTrue(all(timeout > 0 for timeout in waits), context)
                for actual, expected in zip(waits, expected_waits):
                    self.assertAlmostEqual(actual, expected, msg=context)
                self.assertFalse(denial_path.exists(), context)
                self.assertIsNotNone(target_pid)
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(target_pid), 0)

    def test_late_normal_return_after_sample_deadline_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-late-return-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()
            target_pid: int | None = None

            def sampler(pid: int | None) -> Sample:
                nonlocal target_pid
                if pid is not None:
                    target_pid = pid
                return Sample(
                    timestamp=-clock(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(
                process: subprocess.Popen[bytes], timeout: float
            ) -> None:
                ready = root / "output" / "ready"
                ready_deadline = time.monotonic() + 2
                while not ready.exists() and time.monotonic() < ready_deadline:
                    time.sleep(0.001)
                self.assertTrue(ready.exists(), "fixture child 未完成 signal handler setup")
                clock.advance(timeout + 1.0)
                process.terminate()
                self.assertEqual(process.wait(timeout=2), 0)

            result = run_guarded_job(
                root,
                fixture_global_policy(),
                fixture_job_policy(sample_interval_seconds=10),
                (),
                [
                    sys.executable,
                    "-c",
                    "import signal,sys,time; from pathlib import Path; "
                    "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); "
                    "Path('output/ready').write_text('ready'); "
                    "time.sleep(30)",
                ],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial_path = (
                root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
            )

            self.assertEqual(
                (
                    result,
                    receipt["status"],
                    receipt["child_exit_code"],
                    receipt["reasons"],
                    denial_path.exists(),
                    [sample["phase"] for sample in receipt["samples"]],
                ),
                (
                    70,
                    "STOPPED",
                    0,
                    ["LIVE_SAMPLE_CADENCE_EXCEEDED"],
                    True,
                    ["preflight", "live"],
                ),
            )
            denial = json.loads(denial_path.read_text(encoding="utf-8"))
            self.assertFalse(denial["automatic_clear_allowed"])
            self.assertIsNotNone(target_pid)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(target_pid), 0)

    def test_late_normal_return_preserves_hard_runtime_precedence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-late-runtime-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()

            def sampler(_pid: int | None) -> Sample:
                return Sample(
                    timestamp=-clock(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(
                process: subprocess.Popen[bytes], timeout: float
            ) -> None:
                ready = root / "output" / "ready"
                ready_deadline = time.monotonic() + 2
                while not ready.exists() and time.monotonic() < ready_deadline:
                    time.sleep(0.001)
                self.assertTrue(ready.exists(), "fixture child 未完成 signal handler setup")
                clock.advance(timeout + 1.0)
                process.terminate()
                self.assertEqual(process.wait(timeout=2), 0)

            result = run_guarded_job(
                root,
                fixture_global_policy(),
                fixture_job_policy(sample_interval_seconds=10),
                (),
                [
                    sys.executable,
                    "-c",
                    "import signal,sys,time; from pathlib import Path; "
                    "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); "
                    "Path('output/ready').write_text('ready'); "
                    "time.sleep(30)",
                ],
                sampler=sampler,
                max_runtime_seconds=5,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial = json.loads(
                (
                    root
                    / "logs"
                    / "storage_safety"
                    / "restart_denied"
                    / "daily.json"
                ).read_text(encoding="utf-8")
            )

            self.assertEqual(result, 70)
            self.assertEqual(receipt["status"], "STOPPED")
            self.assertEqual(receipt["child_exit_code"], 0)
            self.assertEqual(receipt["reasons"], ["HARD_RUNTIME_EXCEEDED"])
            self.assertEqual(denial["reasons"], ["HARD_RUNTIME_EXCEEDED"])
            self.assertFalse(denial["automatic_clear_allowed"])

    def test_on_time_normal_return_remains_ok_without_denial(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-on-time-return-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()

            def sampler(_pid: int | None) -> Sample:
                return Sample(
                    timestamp=-clock(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(
                process: subprocess.Popen[bytes], timeout: float
            ) -> None:
                ready = root / "output" / "ready"
                ready_deadline = time.monotonic() + 2
                while not ready.exists() and time.monotonic() < ready_deadline:
                    time.sleep(0.001)
                self.assertTrue(ready.exists(), "fixture child 未完成 signal handler setup")
                clock.advance(timeout - 1.0)
                process.terminate()
                self.assertEqual(process.wait(timeout=2), 0)

            result = run_guarded_job(
                root,
                fixture_global_policy(),
                fixture_job_policy(sample_interval_seconds=10),
                (),
                [
                    sys.executable,
                    "-c",
                    "import signal,sys,time; from pathlib import Path; "
                    "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); "
                    "Path('output/ready').write_text('ready'); "
                    "time.sleep(30)",
                ],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial_path = (
                root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
            )

            self.assertEqual(result, 0)
            self.assertEqual(receipt["status"], "OK")
            self.assertEqual(receipt["child_exit_code"], 0)
            self.assertEqual(receipt["reasons"], [])
            self.assertIsNotNone(receipt["process_group_identity"])
            self.assertEqual(
                receipt["process_group_identity"]["leader_pid"],
                receipt["process_group_identity"]["group_id"],
            )
            self.assertEqual(
                receipt["process_group"]["verified_identity"],
                receipt["process_group_identity"],
            )
            self.assertIs(receipt["final_process_group_quiescent"], True)
            self.assertEqual(receipt["process_group"]["final_quiescent"], True)
            self.assertIsNotNone(receipt["final_process_group_checked_at"])
            self.assertFalse(denial_path.exists())
            self.assertEqual(
                [sample["phase"] for sample in receipt["samples"]],
                ["preflight", "live", "final"],
            )

    def test_ok_receipt_requires_verified_final_process_group_quiescence(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-quiescent-required-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)

            with mock.patch(
                "app.storage_safety.process_group_is_quiescent",
                side_effect=[True, False, True, True, True],
            ):
                result = run_guarded_job(
                    root,
                    fixture_global_policy(),
                    fixture_job_policy(),
                    (),
                    ["/bin/sh", "-c", "sleep 0.1"],
                    sampler=lambda _pid: replace(sample, timestamp=time.time()),
                )

            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial = json.loads(
                (
                    root
                    / "logs"
                    / "storage_safety"
                    / "restart_denied"
                    / "daily.json"
                ).read_text(encoding="utf-8")
            )

            self.assertEqual(result, 70)
            self.assertEqual(receipt["status"], "STOPPED")
            self.assertIn(
                "PROCESS_GROUP_NOT_QUIESCENT_AT_FINAL_CHECK",
                receipt["reasons"],
            )
            self.assertEqual(denial["reasons"], receipt["reasons"])
            self.assertIs(receipt["final_process_group_quiescent"], True)
            self.assertIsNotNone(receipt["process_group_identity"])

    def test_live_sampling_cadence_overrun_stops_verified_group_and_denies_restart(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-cadence-stop-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()
            target_pid: int | None = None

            def sampler(pid: int | None) -> Sample:
                nonlocal target_pid
                if pid is not None:
                    target_pid = pid
                return Sample(
                    timestamp=-clock(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(process: subprocess.Popen[bytes], timeout: float) -> None:
                clock.advance(timeout + 1.0)
                raise subprocess.TimeoutExpired(process.args, timeout)

            result = run_guarded_job(
                root,
                fixture_global_policy(),
                fixture_job_policy(sample_interval_seconds=10),
                (),
                ["/bin/sleep", "30"],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial = json.loads(
                (
                    root
                    / "logs"
                    / "storage_safety"
                    / "restart_denied"
                    / "daily.json"
                ).read_text(encoding="utf-8")
            )
            denied = run_guarded_job(
                root,
                fixture_global_policy(),
                fixture_job_policy(sample_interval_seconds=10),
                (),
                ["/bin/sleep", "30"],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )

            self.assertEqual((result, denied), (70, 75))
            self.assertIn("LIVE_SAMPLE_CADENCE_EXCEEDED", receipt["reasons"])
            self.assertIn("LIVE_SAMPLE_CADENCE_EXCEEDED", denial["reasons"])
            self.assertFalse(denial["automatic_clear_allowed"])
            self.assertIsNotNone(target_pid)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(target_pid), 0)

    def test_live_sampler_overrun_stops_at_completion_without_another_sample(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-sampler-overrun-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()
            wait_calls = 0
            target_pid: int | None = None

            def sampler(pid: int | None) -> Sample:
                nonlocal target_pid
                if pid is not None:
                    target_pid = pid
                    clock.advance(11.0)
                return Sample(
                    timestamp=clock() * -1000,
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(_process: subprocess.Popen[bytes], _timeout: float) -> None:
                nonlocal wait_calls
                wait_calls += 1
                raise AssertionError("sampler overrun後不得再等待或啟動下一次 sample")

            result = run_guarded_job(
                root,
                fixture_global_policy(),
                fixture_job_policy(sample_interval_seconds=10),
                (),
                ["/bin/sleep", "30"],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial = json.loads(
                (
                    root
                    / "logs"
                    / "storage_safety"
                    / "restart_denied"
                    / "daily.json"
                ).read_text(encoding="utf-8")
            )

            self.assertEqual(result, 70)
            self.assertEqual(wait_calls, 0)
            self.assertEqual(
                [sample["phase"] for sample in receipt["samples"]],
                ["preflight", "live"],
            )
            self.assertIn("LIVE_SAMPLE_CADENCE_EXCEEDED", receipt["reasons"])
            self.assertIn("LIVE_SAMPLE_CADENCE_EXCEEDED", denial["reasons"])
            self.assertIsNotNone(target_pid)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(target_pid), 0)

    def test_overlong_scheduled_sample_fails_when_child_exits_during_sampling(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-sample-exit-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            clock = FakeMonotonicClock()
            live_sample_calls = 0
            target_pid: int | None = None
            target_process: subprocess.Popen[bytes] | None = None

            def sampler(pid: int | None) -> Sample:
                nonlocal live_sample_calls, target_pid
                if pid is not None:
                    live_sample_calls += 1
                    target_pid = pid
                    if live_sample_calls == 2:
                        clock.advance(11.0)
                        assert target_process is not None
                        target_process.terminate()
                        self.assertEqual(target_process.wait(timeout=2), 0)
                return Sample(
                    timestamp=clock() * -1000,
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=1024,
                    swap_bytes=0,
                )

            def wait_for_process(process: subprocess.Popen[bytes], timeout: float) -> None:
                nonlocal target_process
                target_process = process
                ready = root / "output" / "ready"
                deadline = time.monotonic() + 2
                while not ready.exists() and time.monotonic() < deadline:
                    time.sleep(0.001)
                self.assertTrue(ready.exists(), "fixture child 未完成 signal handler setup")
                clock.advance(timeout)
                raise subprocess.TimeoutExpired(process.args, timeout)

            result = run_guarded_job(
                root,
                fixture_global_policy(),
                fixture_job_policy(sample_interval_seconds=10),
                (),
                [
                    sys.executable,
                    "-c",
                    "import signal,sys,time; from pathlib import Path; "
                    "signal.signal(signal.SIGTERM, lambda *_: sys.exit(0)); "
                    "Path('output/ready').write_text('ready'); "
                    "time.sleep(30)",
                ],
                sampler=sampler,
                monotonic_clock=clock,
                process_waiter=wait_for_process,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )
            denial_path = (
                root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
            )

            self.assertEqual(result, 70)
            self.assertEqual(receipt["status"], "STOPPED")
            self.assertEqual(receipt["child_exit_code"], 0)
            self.assertEqual(
                [sample["phase"] for sample in receipt["samples"]],
                ["preflight", "live", "final"],
            )
            self.assertIn("LIVE_SAMPLE_CADENCE_EXCEEDED", receipt["reasons"])
            self.assertTrue(denial_path.exists())
            denial = json.loads(denial_path.read_text(encoding="utf-8"))
            self.assertIn("LIVE_SAMPLE_CADENCE_EXCEEDED", denial["reasons"])
            self.assertIsNotNone(target_pid)
            with self.assertRaises(ProcessLookupError):
                os.kill(int(target_pid), 0)

    def test_live_metric_gap_cannot_be_hidden_by_valid_final_sample(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-live-gap-") as tmp:
            root = Path(tmp).resolve()
            (root / "output").mkdir()
            sample_count = 0

            def sampler(_pid: int | None) -> Sample:
                nonlocal sample_count
                sample_count += 1
                return Sample(
                    timestamp=time.time(),
                    project_bytes=0,
                    project_file_count=0,
                    host_total_bytes=100_000,
                    host_free_bytes=50_000,
                    rss_bytes=None if sample_count == 2 else 1024,
                    swap_bytes=0,
                )

            result = run_guarded_job(
                root,
                fixture_global_policy(),
                fixture_job_policy(),
                (),
                ["/bin/sh", "-c", "sleep 0.1"],
                sampler=sampler,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(result, 70)
            self.assertIn("RSS_METRIC_UNAVAILABLE", receipt["reasons"])
            self.assertTrue(
                (root / "logs" / "storage_safety" / "restart_denied" / "daily.json").exists()
            )

    def test_runtime_metric_contract_uses_only_live_samples(self) -> None:
        global_policy = fixture_global_policy()
        policy = fixture_job_policy()
        base = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)

        rss_gap = evaluate_runtime(
            global_policy,
            policy,
            [
                replace(base, phase="preflight"),
                replace(base, phase="live", rss_bytes=None),
                replace(base, phase="final"),
            ],
        )
        swap_gap = evaluate_runtime(
            global_policy,
            policy,
            [
                replace(base, phase="preflight"),
                replace(base, phase="live", swap_bytes=None),
                replace(base, phase="final"),
            ],
        )
        no_live = evaluate_runtime(
            global_policy,
            policy,
            [replace(base, phase="preflight"), replace(base, phase="final", rss_bytes=0)],
        )
        valid_live = evaluate_runtime(
            global_policy,
            policy,
            [
                replace(base, phase="preflight", rss_bytes=None, swap_bytes=None),
                replace(base, phase="live"),
                replace(base, phase="final", rss_bytes=None, swap_bytes=None),
            ],
        )

        self.assertIn("RSS_METRIC_UNAVAILABLE", rss_gap.reasons)
        self.assertIn("SWAP_METRIC_UNAVAILABLE", swap_gap.reasons)
        self.assertEqual(no_live.reasons, ("MISSING_VALID_LIVE_RESOURCE_SAMPLE",))
        self.assertFalse(valid_live.triggered)

    def test_quick_child_without_live_sample_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-fast-child-") as tmp:
            root = Path(tmp).resolve()
            (root / "output").mkdir()
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)

            def sampler(pid: int | None) -> Sample:
                if pid is not None:
                    time.sleep(0.05)
                return replace(sample, timestamp=time.time())

            result = run_guarded_job(
                root,
                fixture_global_policy(),
                fixture_job_policy(),
                (),
                ["/usr/bin/true"],
                sampler=sampler,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(result, 70)
            self.assertIn("MISSING_VALID_LIVE_RESOURCE_SAMPLE", receipt["reasons"])
            phases = [sample_payload["phase"] for sample_payload in receipt["samples"]]
            self.assertEqual(phases[0], "preflight")
            self.assertNotIn("live", phases)

    def test_guard_internal_error_terminates_child_and_denies_restart(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-error-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            policy = fixture_job_policy()
            global_policy = fixture_global_policy()
            sample_count = 0
            child_pid: int | None = None
            protected = subprocess.Popen(["/bin/sleep", "30"], start_new_session=True)

            def sampler(pid: int | None) -> Sample:
                nonlocal sample_count, child_pid
                sample_count += 1
                if sample_count == 2:
                    child_pid = pid
                    raise RuntimeError("fixture monitor failure")
                return Sample(time.time(), 0, 0, 100_000, 50_000, 0, 0)

            try:
                command = ["/bin/sh", "-c", "/bin/sleep 30 & wait"]
                stopped = run_guarded_job(
                    root,
                    global_policy,
                    policy,
                    (),
                    command,
                    sampler=sampler,
                )
                denied = run_guarded_job(
                    root,
                    global_policy,
                    policy,
                    (),
                    command,
                    sampler=sampler,
                )

                self.assertEqual((stopped, denied), (70, 75))
                self.assertIsNotNone(child_pid)
                with self.assertRaises(ProcessLookupError):
                    os.kill(int(child_pid), 0)
                self.assertIsNone(protected.poll())
            finally:
                if protected.poll() is None:
                    protected.terminate()
                    protected.wait(timeout=2)

    def test_sigterm_is_converted_to_isolated_stop_and_restart_denial(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-signal-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            runner = """
import sys
from pathlib import Path
from tests.test_storage_safety import fixture_global_policy, fixture_job_policy
from app.storage_safety import Sample, run_guarded_job

root = Path(sys.argv[1])
command = [\"/bin/sh\", \"-c\", \"echo $$ > output/child.pid; exec /bin/sleep 30\"]
sampler = lambda _pid: Sample(0, 0, 0, 100_000, 50_000, 1024, 0)
raise SystemExit(
    run_guarded_job(root, fixture_global_policy(), fixture_job_policy(), (), command, sampler=sampler)
)
"""
            guard = subprocess.Popen([sys.executable, "-c", runner, str(root)])
            child_pid_path = root / "output" / "child.pid"
            try:
                deadline = time.monotonic() + 5
                while not child_pid_path.exists() and time.monotonic() < deadline:
                    time.sleep(0.05)
                self.assertTrue(child_pid_path.exists(), "fixture child 未啟動")
                child_pid = int(child_pid_path.read_text(encoding="utf-8"))

                guard.terminate()
                self.assertEqual(guard.wait(timeout=5), 70)
                marker = root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
                self.assertTrue(marker.exists())
                with self.assertRaises(ProcessLookupError):
                    os.kill(child_pid, 0)
            finally:
                if guard.poll() is None:
                    guard.kill()
                    guard.wait(timeout=2)

    def test_two_bounded_guard_cycles_write_receipt_without_restart_marker(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-cycles-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            policy = fixture_job_policy()
            global_policy = fixture_global_policy()

            def sampler(_pid: int | None) -> Sample:
                inventory = measure_paths(root, policy.meter_paths)
                return Sample(
                    timestamp=time.time(),
                    project_bytes=inventory.bytes,
                    project_file_count=inventory.file_count,
                    host_total_bytes=200 * 1024**3,
                    host_free_bytes=100 * 1024**3,
                    rss_bytes=1024,
                    swap_bytes=0,
                    memory_pressure_level=1,
                )

            command = [
                "/bin/sh",
                "-c",
                "printf x >> output/result.log; printf bounded-cycle; sleep 0.1",
            ]
            first = run_guarded_job(root, global_policy, policy, (), command, sampler=sampler)
            second = run_guarded_job(root, global_policy, policy, (), command, sampler=sampler)
            receipt = root / "logs" / "storage_safety" / "daily_latest.json"
            denied = root / "logs" / "storage_safety" / "restart_denied" / "daily.json"

            self.assertEqual((first, second), (0, 0))
            self.assertTrue(receipt.exists())
            self.assertFalse(denied.exists())
            self.assertEqual((root / "output" / "result.log").read_text(encoding="utf-8"), "xx")
            payload = json.loads(receipt.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(payload["samples"]), 3)
            self.assertTrue(
                all("memory_pressure_level" in sample for sample in payload["samples"])
            )
            self.assertEqual(payload["summary"]["peak_live_memory_pressure_level"], 1)

    def test_validation_only_cycle_records_mode_and_keeps_production_policy_unverified(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-validation-") as tmp:
            fixture_root = Path(tmp).resolve()
            root = fixture_root / "sandbox"
            source = fixture_root / "source"
            (root / "output").mkdir(parents=True)
            source.mkdir()
            trusted = trusted_validation_fixture(
                root,
                "import time\ntime.sleep(0.1)\n",
            )
            policy = fixture_job_policy(launch_verified=False)
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)
            result = run_guarded_job(
                root,
                fixture_global_policy(),
                policy,
                (),
                trusted.command,
                sampler=lambda _pid: replace(sample, timestamp=time.time()),
                validation_only=True,
                max_runtime_seconds=2,
                validation_context={
                    "manual_only": True,
                    "source_input_root": str(source),
                },
                trusted_validation_entrypoint=trusted,
            )
            receipt = json.loads(
                (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )

        self.assertEqual(result, 0)
        self.assertTrue(receipt["validation_only"])
        self.assertFalse(receipt["launch_verified"])
        self.assertEqual(receipt["max_runtime_seconds"], 2)
        self.assertEqual(
            receipt["validation_context"],
            {"manual_only": True, "source_input_root": str(source)},
        )
        self.assertEqual(
            receipt["limits"]["max_process_tree_rss_bytes"],
            policy.max_process_tree_rss_bytes,
        )

    def test_validation_child_cannot_write_outside_sandbox(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-confinement-") as tmp:
            fixture_root = Path(tmp).resolve()
            sandbox = fixture_root / "sandbox"
            protected = fixture_root / "protected"
            (sandbox / "output").mkdir(parents=True)
            protected.mkdir()
            protected_file = protected / "source.txt"
            protected_file.write_text("original\n", encoding="utf-8")
            original = protected_file.read_bytes()
            trusted = trusted_validation_fixture(
                sandbox,
                "from pathlib import Path\nimport sys\nPath(sys.argv[1]).write_text('changed')\n",
                argv=(str(protected_file),),
            )
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)

            result = run_guarded_job(
                sandbox,
                fixture_global_policy(),
                fixture_job_policy(launch_verified=False),
                (),
                trusted.command,
                sampler=lambda _pid: replace(sample, timestamp=time.time()),
                validation_only=True,
                max_runtime_seconds=2,
                validation_context={"source_input_root": str(protected)},
                trusted_validation_entrypoint=trusted,
            )
            receipt = json.loads(
                (sandbox / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertNotEqual(result, 0)
            self.assertEqual(protected_file.read_bytes(), original)
            self.assertNotEqual(receipt["status"], "OK")

    def test_validation_rejects_swallowed_outside_write_before_spawn(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-swallowed-denial-") as tmp:
            fixture_root = Path(tmp).resolve()
            sandbox = fixture_root / "sandbox"
            protected = fixture_root / "protected"
            (sandbox / "output").mkdir(parents=True)
            protected.mkdir()
            protected_file = protected / "source.txt"
            protected_file.write_text("original\n", encoding="utf-8")
            original = protected_file.read_bytes()
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)

            result = run_guarded_job(
                sandbox,
                fixture_global_policy(),
                fixture_job_policy(launch_verified=False),
                (),
                [
                    "/bin/sh",
                    "-c",
                    'printf spawned > output/spawned; printf changed > "$1" || true; sleep 0.1',
                    "validation-child",
                    str(protected_file),
                ],
                sampler=lambda _pid: replace(sample, timestamp=time.time()),
                validation_only=True,
                max_runtime_seconds=2,
                validation_context={"source_input_root": str(protected)},
            )
            receipt = json.loads(
                (sandbox / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(result, 70)
            self.assertEqual(protected_file.read_bytes(), original)
            self.assertFalse((sandbox / "output" / "spawned").exists())
            self.assertIn("UNTRUSTED_VALIDATION_ENTRYPOINT", receipt["reasons"])
            self.assertTrue(
                (sandbox / "logs" / "storage_safety" / "restart_denied" / "daily.json").exists()
            )

    def test_validation_child_can_read_source_and_write_only_sandbox(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-confinement-ok-") as tmp:
            fixture_root = Path(tmp).resolve()
            sandbox = fixture_root / "sandbox"
            source = fixture_root / "source"
            (sandbox / "output").mkdir(parents=True)
            source.mkdir()
            (source / "input.txt").write_text("readable\n", encoding="utf-8")
            trusted = trusted_validation_fixture(
                sandbox,
                "from pathlib import Path\nimport sys\nimport time\nPath('output/copied.txt').write_text((Path(sys.argv[1]) / 'input.txt').read_text())\ntime.sleep(0.1)\n",
                argv=(str(source),),
            )
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)

            result = run_guarded_job(
                sandbox,
                fixture_global_policy(),
                fixture_job_policy(launch_verified=False),
                (),
                trusted.command,
                sampler=lambda _pid: replace(sample, timestamp=time.time()),
                validation_only=True,
                max_runtime_seconds=2,
                validation_context={"source_input_root": str(source)},
                trusted_validation_entrypoint=trusted,
            )

            self.assertEqual(result, 0)
            self.assertEqual(
                (sandbox / "output" / "copied.txt").read_text(encoding="utf-8"),
                "readable\n",
            )

    def test_validation_confinement_allows_only_exact_dev_null_and_sandbox_write(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-dev-null-") as tmp:
            fixture_root = Path(tmp).resolve()
            sandbox = fixture_root / "sandbox"
            protected = fixture_root / "protected"
            (sandbox / "output").mkdir(parents=True)
            protected.mkdir()
            protected_file = protected / "outside.txt"
            protected_file.write_text("original\n", encoding="utf-8")
            trusted = trusted_validation_fixture(
                sandbox,
                "from pathlib import Path\n"
                "import sys\n"
                "import time\n"
                "Path('/dev/null').write_text('discarded', encoding='utf-8')\n"
                "Path('output/inside.txt').write_text('inside', encoding='utf-8')\n"
                "try:\n"
                "    Path(sys.argv[1]).write_text('outside', encoding='utf-8')\n"
                "except OSError:\n"
                "    pass\n"
                "else:\n"
                "    raise SystemExit(93)\n"
                "time.sleep(0.1)\n",
                argv=(str(protected_file),),
            )
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)

            result = run_guarded_job(
                sandbox,
                fixture_global_policy(),
                fixture_job_policy(launch_verified=False),
                (),
                trusted.command,
                sampler=lambda _pid: replace(sample, timestamp=time.time()),
                validation_only=True,
                max_runtime_seconds=2,
                validation_context={"source_input_root": str(protected)},
                trusted_validation_entrypoint=trusted,
            )

            self.assertEqual(result, 0)
            self.assertEqual(
                (sandbox / "output" / "inside.txt").read_text(encoding="utf-8"),
                "inside",
            )
            self.assertEqual(protected_file.read_text(encoding="utf-8"), "original\n")

    def test_validation_source_root_must_be_real_directory_without_symlinks(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-source-root-") as tmp:
            root = Path(tmp).resolve()
            missing = root / "missing"
            regular_file = root / "file.txt"
            regular_file.write_text("not a directory\n", encoding="utf-8")
            real = root / "real"
            real.mkdir()
            linked = root / "linked"
            linked.symlink_to(real, target_is_directory=True)

            with self.assertRaises((FileNotFoundError, ValueError)):
                _existing_lexical_directory(missing, "source_input_root")
            with self.assertRaisesRegex(ValueError, "必須是存在的目錄"):
                _existing_lexical_directory(regular_file, "source_input_root")
            with self.assertRaisesRegex(ValueError, "不得包含 symlink"):
                _existing_lexical_directory(linked, "source_input_root")

    def test_validation_entrypoint_contract_rejects_unregistered_and_bad_digest(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-contract-registration-") as tmp:
            sandbox = Path(tmp).resolve()
            contract, marker = validation_contract_fixture(
                sandbox,
                "import time\ntime.sleep(0.1)\n",
            )

            with self.assertRaisesRegex(
                UntrustedValidationEntrypoint,
                "未登記",
            ):
                load_trusted_validation_entrypoint(sandbox, "daily", {}, contract)

            registrations = marker["trusted_entrypoints"]
            assert isinstance(registrations, dict)
            registration = registrations["daily"]
            assert isinstance(registration, dict)
            registration["contract_sha256"] = "0" * 64
            with self.assertRaisesRegex(
                UntrustedValidationEntrypoint,
                "digest 不符",
            ):
                load_trusted_validation_entrypoint(sandbox, "daily", marker, contract)

    def test_validation_rejects_contract_changed_after_verification_before_spawn(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-contract-toctou-") as tmp:
            fixture_root = Path(tmp).resolve()
            sandbox = fixture_root / "sandbox"
            source = fixture_root / "source"
            (sandbox / "output").mkdir(parents=True)
            source.mkdir()
            trusted = trusted_validation_fixture(
                sandbox,
                "from pathlib import Path\nPath('output/spawned').write_text('spawned')\n",
            )
            trusted.contract_path.write_text(
                trusted.contract_path.read_text(encoding="utf-8") + "\n",
                encoding="utf-8",
            )
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)

            result = run_guarded_job(
                sandbox,
                fixture_global_policy(),
                fixture_job_policy(launch_verified=False),
                (),
                trusted.command,
                sampler=lambda _pid: replace(sample, timestamp=time.time()),
                validation_only=True,
                max_runtime_seconds=2,
                validation_context={"source_input_root": str(source)},
                trusted_validation_entrypoint=trusted,
            )
            receipt = json.loads(
                (sandbox / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(result, 70)
            self.assertFalse((sandbox / "output" / "spawned").exists())
            self.assertIn("UNTRUSTED_VALIDATION_ENTRYPOINT", receipt["reasons"])

    def test_validation_rejects_python_c_dynamic_command_before_spawn(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-dynamic-command-") as tmp:
            fixture_root = Path(tmp).resolve()
            sandbox = fixture_root / "sandbox"
            source = fixture_root / "source"
            (sandbox / "output").mkdir(parents=True)
            source.mkdir()
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)

            result = run_guarded_job(
                sandbox,
                fixture_global_policy(),
                fixture_job_policy(launch_verified=False),
                (),
                [
                    sys.executable,
                    "-c",
                    "from pathlib import Path; Path('output/spawned').write_text('spawned')",
                ],
                sampler=lambda _pid: replace(sample, timestamp=time.time()),
                validation_only=True,
                max_runtime_seconds=2,
                validation_context={"source_input_root": str(source)},
            )
            receipt = json.loads(
                (sandbox / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(result, 70)
            self.assertFalse((sandbox / "output" / "spawned").exists())
            self.assertIn("UNTRUSTED_VALIDATION_ENTRYPOINT", receipt["reasons"])

    def test_validation_confinement_missing_fails_closed_before_spawn(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-no-confinement-") as tmp:
            fixture_root = Path(tmp).resolve()
            sandbox = fixture_root / "sandbox"
            source = fixture_root / "source"
            (sandbox / "output").mkdir(parents=True)
            source.mkdir()
            trusted = trusted_validation_fixture(
                sandbox,
                "from pathlib import Path\nPath('output/spawned').write_text('spawned')\n",
            )
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)
            with mock.patch(
                "app.storage_safety.SANDBOX_EXECUTABLE",
                fixture_root / "missing-sandbox-exec",
            ):
                result = run_guarded_job(
                    sandbox,
                    fixture_global_policy(),
                    fixture_job_policy(launch_verified=False),
                    (),
                    trusted.command,
                    sampler=lambda _pid: replace(sample, timestamp=time.time()),
                    validation_only=True,
                    max_runtime_seconds=2,
                    validation_context={"source_input_root": str(source)},
                    trusted_validation_entrypoint=trusted,
                )
            receipt = json.loads(
                (sandbox / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(result, 70)
            self.assertFalse((sandbox / "output" / "spawned").exists())
            self.assertIn("GUARD_INTERNAL_ERROR_RuntimeError", receipt["reasons"])

    def test_validation_confinement_probe_failure_fails_closed_before_spawn(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-bad-confinement-") as tmp:
            fixture_root = Path(tmp).resolve()
            sandbox = fixture_root / "sandbox"
            source = fixture_root / "source"
            (sandbox / "output").mkdir(parents=True)
            source.mkdir()
            trusted = trusted_validation_fixture(
                sandbox,
                "from pathlib import Path\nPath('output/spawned').write_text('spawned')\n",
            )
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)
            with mock.patch(
                "app.storage_safety._sandbox_profile",
                return_value="(version 1)\n(deny default)",
            ):
                result = run_guarded_job(
                    sandbox,
                    fixture_global_policy(),
                    fixture_job_policy(launch_verified=False),
                    (),
                    trusted.command,
                    sampler=lambda _pid: replace(sample, timestamp=time.time()),
                    validation_only=True,
                    max_runtime_seconds=2,
                    validation_context={"source_input_root": str(source)},
                    trusted_validation_entrypoint=trusted,
                )
            receipt = json.loads(
                (sandbox / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(result, 70)
            self.assertFalse((sandbox / "output" / "spawned").exists())
            self.assertIn("GUARD_INTERNAL_ERROR_RuntimeError", receipt["reasons"])

    def test_protected_root_snapshot_detects_mutation_and_denies_restart(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-protected-snapshot-") as tmp:
            fixture_root = Path(tmp).resolve()
            sandbox = fixture_root / "sandbox"
            source = fixture_root / "source"
            (sandbox / "output").mkdir(parents=True)
            source.mkdir()
            protected_file = source / "protected.txt"
            protected_file.write_text("before\n", encoding="utf-8")
            trusted = trusted_validation_fixture(
                sandbox,
                "from pathlib import Path\nimport sys\nimport time\nPath(sys.argv[1]).write_text('after')\ntime.sleep(0.1)\n",
                argv=(str(protected_file),),
            )
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)
            command = list(trusted.command)

            with mock.patch(
                "app.storage_safety._validation_spawn_command",
                return_value=command,
            ):
                result = run_guarded_job(
                    sandbox,
                    fixture_global_policy(),
                    fixture_job_policy(launch_verified=False),
                    (),
                    command,
                    sampler=lambda _pid: replace(sample, timestamp=time.time()),
                    validation_only=True,
                    max_runtime_seconds=2,
                    validation_context={"source_input_root": str(source)},
                    trusted_validation_entrypoint=trusted,
                )
            receipt = json.loads(
                (sandbox / "logs" / "storage_safety" / "daily_latest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(result, 70)
            self.assertIn("PROTECTED_ROOT_MUTATED", receipt["reasons"])
            self.assertEqual(
                receipt["validation_context"]["protected_root_changed_paths"],
                ["protected.txt"],
            )
            self.assertTrue(
                (sandbox / "logs" / "storage_safety" / "restart_denied" / "daily.json").exists()
            )

    def test_validation_cli_rejects_git_checkout_even_with_manual_action(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-git-checkout-") as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            marker = root / "validation-marker.json"
            marker.write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "無 .git 的隔離 sandbox"):
                validate_isolated_root(marker, "daily", root=root)

    def test_validation_cli_rejects_dangling_git_symlink(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-git-symlink-") as tmp:
            root = Path(tmp)
            (root / ".git").symlink_to(root / "missing-gitdir")
            marker = root / "validation-marker.json"
            marker.write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "無 .git 的隔離 sandbox"):
                validate_isolated_root(marker, "daily", root=root)

    def test_validation_paths_reject_symlink_components(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-symlink-root-") as tmp:
            root = Path(tmp)
            target = root / "target"
            target.mkdir()
            linked = root / "linked"
            linked.symlink_to(target, target_is_directory=True)

            with self.assertRaisesRegex(ValueError, "不得包含 symlink"):
                _path_under_root(linked, "sandbox_output_root", root=root)
            with self.assertRaises(ValueError):
                _path_under_root(root.parent, "sandbox_output_root", root=root)

    def test_validation_hard_runtime_rejects_non_finite_value(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-nonfinite-runtime-") as tmp:
            root = Path(tmp)
            (root / "output").mkdir()
            with self.assertRaisesRegex(ValueError, "必須大於 0"):
                run_guarded_job(
                    root,
                    fixture_global_policy(),
                    fixture_job_policy(),
                    (),
                    ["/usr/bin/true"],
                    max_runtime_seconds=float("nan"),
                )

    def test_validation_hard_runtime_stops_only_target_and_denies_restart(self) -> None:
        with tempfile.TemporaryDirectory(prefix="top10-storage-runtime-limit-") as tmp:
            fixture_root = Path(tmp).resolve()
            root = fixture_root / "sandbox"
            source = fixture_root / "source"
            (root / "output").mkdir(parents=True)
            source.mkdir()
            trusted = trusted_validation_fixture(
                root,
                "import time\ntime.sleep(30)\n",
            )
            policy = fixture_job_policy(launch_verified=False, sample_interval_seconds=1)
            protected = subprocess.Popen(["/bin/sleep", "30"], start_new_session=True)
            sample = Sample(time.time(), 0, 0, 100_000, 50_000, 1024, 0)
            try:
                result = run_guarded_job(
                    root,
                    fixture_global_policy(),
                    policy,
                    (),
                    trusted.command,
                    sampler=lambda _pid: replace(sample, timestamp=time.time()),
                    validation_only=True,
                    max_runtime_seconds=0.2,
                    validation_context={"source_input_root": str(source)},
                    trusted_validation_entrypoint=trusted,
                )
                receipt = json.loads(
                    (root / "logs" / "storage_safety" / "daily_latest.json").read_text(
                        encoding="utf-8"
                    )
                )
                marker = root / "logs" / "storage_safety" / "restart_denied" / "daily.json"
                denied = run_guarded_job(
                    root,
                    fixture_global_policy(),
                    policy,
                    (),
                    trusted.command,
                    sampler=lambda _pid: replace(sample, timestamp=time.time()),
                    validation_only=True,
                    max_runtime_seconds=1,
                    validation_context={"source_input_root": str(source)},
                    trusted_validation_entrypoint=trusted,
                )

                self.assertEqual((result, denied), (70, 75))
                self.assertIn("HARD_RUNTIME_EXCEEDED", receipt["reasons"])
                self.assertTrue(marker.exists())
                self.assertIsNone(protected.poll())
            finally:
                if protected.poll() is None:
                    protected.terminate()
                    protected.wait(timeout=2)

    def test_all_scheduled_jobs_enter_through_fail_closed_storage_guard(self) -> None:
        for job, original_entrypoint in SCHEDULED_JOBS.items():
            with self.subTest(job=job):
                path = PROJECT_ROOT / "scripts" / f"com.new-top10.{job}.plist"
                payload = plistlib.loads(path.read_bytes())
                arguments = payload["ProgramArguments"]
                self.assertEqual(arguments[:3], [
                    "/bin/bash",
                    "__PROJECT_DIR__/scripts/run_with_storage_guard.sh",
                    job,
                ])
                self.assertIn(f"__PROJECT_DIR__/scripts/{original_entrypoint}", arguments)
                self.assertEqual(payload["StandardOutPath"], "/dev/null")
                self.assertEqual(payload["StandardErrorPath"], "/dev/null")
                self.assertNotIn("KeepAlive", payload)

        wrapper = (PROJECT_ROOT / "scripts" / "run_with_storage_guard.sh").read_text(encoding="utf-8")
        for variable in (
            "TMPDIR",
            "UV_CACHE_DIR",
            "XDG_CACHE_HOME",
            "MPLCONFIGDIR",
            "JOBLIB_TEMP_FOLDER",
        ):
            self.assertIn(f"export {variable}=", wrapper)
        self.assertNotIn("TOP10_DAILY_PYTHON", wrapper)

    def test_research_quota_archive_respects_hard_file_limit_across_cycles(self) -> None:
        """重跑研究週期時，封存檔不得無上限累積。"""

        with tempfile.TemporaryDirectory(prefix="top10-storage-red-") as tmp:
            fixture_root = Path(tmp)
            scripts_dir = fixture_root / "scripts"
            scripts_dir.mkdir()
            shutil.copy2(
                PROJECT_ROOT / "scripts" / "run_daily_research_quota.sh",
                scripts_dir / "run_daily_research_quota.sh",
            )
            fake_python = fixture_root / "fake-python"
            fake_python.write_text(
                """#!/bin/bash
set -e
if [[ "$*" == *"--field market_run_date"* ]]; then
  printf '2026-08-03\\n'
  exit 0
fi
output=""
while [ "$#" -gt 0 ]; do
  if [ "$1" = "--output" ] && [ "$#" -gt 1 ]; then
    output="$2"
    shift
  fi
  shift
done
if [ -n "$output" ]; then
  mkdir -p "$(dirname "$output")"
  printf '{"status":"OK"}\\n' > "$output"
  if [[ "$output" == *.json ]]; then
    printf '# fixture\\n' > "${output%.json}.md"
  fi
fi
exit 0
""",
                encoding="utf-8",
            )
            fake_python.chmod(0o755)
            context = fixture_root / "logs" / "fixture-context.json"
            context.parent.mkdir()
            context.write_text("{}\n", encoding="utf-8")
            environment = {
                **os.environ,
                "TOP10_FOG_RUN_CONTEXT": str(context),
                "TOP10_RESEARCH_PYTHON": str(fake_python),
                "TOP10_REFRESH_RESEARCH_MAP": "0",
                "TOP10_RESEARCH_RUN_ARCHIVE_MAX_FILES": "2",
            }

            for cycle in range(2):
                completed = subprocess.run(
                    ["bash", "scripts/run_daily_research_quota.sh"],
                    cwd=fixture_root,
                    env=environment,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
                if cycle == 0:
                    time.sleep(1.05)

            archived = sorted(
                (fixture_root / "artifacts" / "autonomous_research" / "run_outputs").glob("*")
            )

        self.assertLessEqual(
            len(archived),
            2,
            "兩個週期留下四份重複封存，證明現行 wrapper 沒有 max_file_count／輪替回收。",
        )


if __name__ == "__main__":
    unittest.main()
