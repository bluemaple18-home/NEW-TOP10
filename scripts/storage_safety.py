#!/usr/bin/env python3
"""TOP10 容量 guard CLI；預設政策未 live 驗證時拒絕啟動。"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
from dataclasses import asdict, replace
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.storage_safety import (  # noqa: E402
    _existing_lexical_directory,
    evaluate_preflight,
    load_trusted_validation_entrypoint,
    load_policy,
    reclaim_allowlisted,
    run_guarded_job,
    take_sample,
)
from app.external_cache import reject_external_isolation  # noqa: E402


DEFAULT_POLICY = PROJECT_ROOT / "docs" / "operations" / "top10-storage-policy.json"
VALIDATION_MARKER_SCHEMA = "top10-storage-validation-root.v1"


def _effective_trigger_type(
    requested: str,
    *,
    parent_pid: int | None = None,
) -> str:
    """一般 CLI 不得把 caller 自述的 natural 直接當 scheduler origin。"""

    resolved_parent = os.getppid() if parent_pid is None else parent_pid
    if requested == "natural" and resolved_parent != 1:
        return "manual"
    return requested


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TOP10 project-scoped storage safety guard")
    parser.add_argument("--policy", type=Path, default=DEFAULT_POLICY)
    subparsers = parser.add_subparsers(dest="action", required=True)

    measure = subparsers.add_parser("measure", help="量測單一 job scope，不啟動 child")
    measure.add_argument("--job", required=True)

    reclaim = subparsers.add_parser("reclaim", help="執行或 dry-run allowlisted 回收")
    reclaim.add_argument("--job", required=True)
    reclaim.add_argument("--execute", action="store_true")

    run = subparsers.add_parser("run", help="在 guard 內執行 child command")
    run.add_argument("--job", required=True)
    run.add_argument("--lightgbm-temp-cleanup", action="store_true",
                     help="實刪本 job 暫存目錄內超過24小時的 LightGBM 檔；預設只盤點")
    run.add_argument("--startup-failure", action="store_true", help=argparse.SUPPRESS)
    run.add_argument(
        "--trigger-type",
        choices=("natural", "manual"),
        default="manual",
    )
    run.add_argument(
        "--scheduled-at",
        default=os.environ.get("TOP10_STORAGE_SCHEDULED_AT"),
    )
    run.add_argument(
        "--invocation-id",
        default=os.environ.get("TOP10_STORAGE_INVOCATION_ID"),
    )
    run.add_argument("command", nargs=argparse.REMAINDER)

    validate_run = subparsers.add_parser(
        "validate-run",
        help="只在無 .git 的隔離 sandbox 內執行未 live 驗證的人工代表性週期",
    )
    validate_run.add_argument("--job", required=True)
    validate_run.add_argument("--sandbox-root", type=Path)
    validate_run.add_argument("--marker", type=Path, required=True)
    validate_run.add_argument("--max-runtime-seconds", type=float, required=True)
    validate_run.add_argument("--source-input-root", type=Path, required=True)
    validate_run.add_argument("--sandbox-input-root", type=Path, required=True)
    validate_run.add_argument("--sandbox-output-root", type=Path, required=True)
    validate_run.add_argument("--entrypoint-contract", type=Path, required=True)
    return parser.parse_args(argv)


def resolve_policy(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def validate_isolated_root(
    marker_path: Path,
    job: str,
    *,
    root: Path = PROJECT_ROOT,
) -> dict[str, object]:
    """驗證 manual validation marker，並拒絕在 git checkout 內繞過 live gate。"""

    root = root.resolve()
    marker_candidate = marker_path if marker_path.is_absolute() else root / marker_path
    if marker_candidate.is_symlink():
        raise ValueError("validation marker 不得是 symlink")
    marker = marker_candidate.resolve()
    marker.relative_to(root)
    git_entry = root / ".git"
    if git_entry.exists() or git_entry.is_symlink():
        raise ValueError("validate-run 只能在無 .git 的隔離 sandbox 執行")
    payload = json.loads(marker.read_text(encoding="utf-8"))
    if payload.get("schema_version") != VALIDATION_MARKER_SCHEMA:
        raise ValueError("validation marker schema_version 不符")
    jobs = payload.get("jobs")
    if not isinstance(jobs, list) or job not in jobs:
        raise ValueError("validation marker jobs 不含目前 job")
    if Path(str(payload.get("sandbox_root", ""))).resolve() != root:
        raise ValueError("validation marker sandbox_root 不符")
    if payload.get("manual_only") is not True:
        raise ValueError("validation marker 必須是 manual_only")
    return payload


def _path_under_root(
    path: Path,
    field: str,
    *,
    root: Path = PROJECT_ROOT,
) -> str:
    lexical_root = Path(os.path.abspath(root))
    resolved_root = lexical_root.resolve()
    candidate = path if path.is_absolute() else lexical_root / path
    lexical = Path(os.path.abspath(candidate))
    relative = lexical.relative_to(lexical_root)
    current = lexical_root
    for part in relative.parts:
        current /= part
        if current.is_symlink():
            raise ValueError(f"{field} 不得包含 symlink")
    resolved = lexical.resolve(strict=True)
    resolved.relative_to(resolved_root)
    return str(resolved)


def configure_validation_runtime(job: str, *, root: Path | None = None) -> dict[str, str]:
    """把 validation child 的暫存與 cache 全部收斂到 sandbox meter scope。"""

    reject_external_isolation()
    runtime_root = (PROJECT_ROOT if root is None else root) / "logs" / "storage_safety" / "runtime" / job
    paths = {
        "TMPDIR": runtime_root / "tmp",
        "UV_CACHE_DIR": runtime_root / "cache" / "uv",
        "XDG_CACHE_HOME": runtime_root / "cache" / "xdg",
        "MPLCONFIGDIR": runtime_root / "cache" / "matplotlib",
        "JOBLIB_TEMP_FOLDER": runtime_root / "tmp" / "joblib",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    resolved = {key: str(path.resolve()) for key, path in paths.items()}
    os.environ.update(resolved)
    os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
    return resolved


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    guard_root = PROJECT_ROOT
    shared_source = args.action == "validate-run" and args.sandbox_root is not None
    if shared_source:
        if args.job != "fog-research-worker":
            raise ValueError("shared-source 僅允許 Fog")
        source = _existing_lexical_directory(args.source_input_root, "source_input_root")
        guard_root = _existing_lexical_directory(args.sandbox_root, "sandbox_root")
        if source != PROJECT_ROOT.resolve():
            raise ValueError("shared source 必須是此 CLI 的 PROJECT_ROOT")
        if source.is_relative_to(guard_root) or guard_root.is_relative_to(source):
            raise ValueError("source 與 sandbox 不得重疊")
        if resolve_policy(args.policy).resolve() != DEFAULT_POLICY.resolve():
            raise ValueError("shared-source 不得覆寫 source policy")
    global_policy, job_policy, rules = load_policy(resolve_policy(args.policy), args.job)
    if shared_source:
        # 此手動驗證卡只可收緊既有 job；外層 lifecycle 的較小預算仍獨立生效。
        # 把入口／manifest／匯出證據也計入，不能只計工作負載的 artifacts。
        job_policy = replace(
            job_policy,
            max_bytes=min(job_policy.max_bytes, 256 * 1024**2),
            meter_paths=tuple(dict.fromkeys((*job_policy.meter_paths,
                                            "scripts", "validation", "validation_evidence"))),
        )
    if args.action == "measure":
        sample = take_sample(PROJECT_ROOT, job_policy)
        decision = evaluate_preflight(global_policy, job_policy, sample)
        print(
            json.dumps(
                {
                    "job": args.job,
                    "sample": sample.to_dict(),
                    "decision": asdict(decision),
                    "verdict": "NO-GO" if decision.triggered else "PASS",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
        )
        return 2 if decision.triggered else 0
    if args.action == "reclaim":
        result = reclaim_allowlisted(PROJECT_ROOT, rules, execute=args.execute)
        print(json.dumps(asdict(result), ensure_ascii=False, sort_keys=True))
        return 0
    validation_only = args.action == "validate-run"
    validation_context = None
    trusted_entrypoint = None
    max_runtime_seconds = None
    if validation_only:
        reject_external_isolation(configured=True)
        marker = validate_isolated_root(args.marker, args.job, root=guard_root)
        sandbox_input = _path_under_root(args.sandbox_input_root, "sandbox_input_root", root=guard_root)
        sandbox_output = _path_under_root(args.sandbox_output_root, "sandbox_output_root", root=guard_root)
        trusted_entrypoint = load_trusted_validation_entrypoint(
            guard_root,
            args.job,
            marker,
            args.entrypoint_contract,
        )
        if shared_source:
            pinned = trusted_entrypoint.argv
            expected_flags = ("--source-root", "--source-commit", "--validation-root",
                              "--source-manifest", "--source-manifest-sha256",
                              "--runner-sha256", "--representative-sha256")
            if len(pinned) != 15 or pinned[0] != "--shared-source" or pinned[1::2] != expected_flags:
                raise ValueError("shared-source pinned argv 不符")
            values = dict(zip(pinned[1::2], pinned[2::2]))
            if values["--source-root"] != str(source) or values["--validation-root"] != str(guard_root):
                raise ValueError("shared-source pinned roots 不符")
            _path_under_root(Path(values["--source-manifest"]), "source_manifest", root=guard_root)
            helper = PROJECT_ROOT / "scripts/storage_validation/fog_research_worker.py"
            if hashlib.sha256(helper.read_bytes()).hexdigest() != trusted_entrypoint.entrypoint_sha256:
                raise ValueError("shared-source helper 必須與 source pinned helper 一致")
        runtime_environment = configure_validation_runtime(args.job, root=guard_root)
        command = list(trusted_entrypoint.command)
        validation_context = {
            "marker": marker,
            "source_input_root": str(
                _existing_lexical_directory(args.source_input_root, "source_input_root")
            ),
            "sandbox_input_root": sandbox_input,
            "sandbox_output_root": sandbox_output,
            "shared_source": shared_source,
            "runtime_environment": runtime_environment,
            "trusted_entrypoint": {
                "contract_path": str(trusted_entrypoint.contract_path),
                "contract_sha256": trusted_entrypoint.contract_sha256,
                "entrypoint_path": str(trusted_entrypoint.entrypoint_path),
                "entrypoint_sha256": trusted_entrypoint.entrypoint_sha256,
                "argv": list(trusted_entrypoint.argv),
            },
        }
        max_runtime_seconds = args.max_runtime_seconds
    else:
        command = list(args.command)
        if command and command[0] == "--":
            command = command[1:]
        if not command:
            raise SystemExit("run 需要 -- 後的 child command")
    sampler = None
    if shared_source:
        def sample_shared(pid: int | None):
            sample = take_sample(guard_root, job_policy, pid, host_root=PROJECT_ROOT)
            # output 自身只承擔剩餘 job 預算；絕不借用另一卷 free 或套用 host reserve。
            capacity = {
                "root": str(guard_root), "host_root": str(PROJECT_ROOT),
                "timestamp": sample.timestamp, "source": "shutil.disk_usage",
                "required_additional_bytes": max(0, job_policy.max_bytes - sample.project_bytes),
                "total_bytes": None, "free_bytes": None, "decision": "NO-GO",
                "reason_code": "OUTPUT_VOLUME_CAPACITY_UNAVAILABLE",
            }
            validation_context.setdefault("output_capacity_samples", []).append(capacity)
            disk = shutil.disk_usage(guard_root)
            capacity.update(total_bytes=disk.total, free_bytes=disk.free)
            if not 0 <= disk.free <= disk.total or disk.total <= 0:
                raise RuntimeError("OUTPUT_VOLUME_CAPACITY_UNAVAILABLE")
            if disk.free < capacity["required_additional_bytes"]:
                capacity["reason_code"] = "OUTPUT_VOLUME_CAPACITY_INSUFFICIENT"
                raise RuntimeError("OUTPUT_VOLUME_CAPACITY_INSUFFICIENT")
            capacity.update(decision="PASS", reason_code=None)
            return sample

        sampler = sample_shared
    return run_guarded_job(
        guard_root,
        global_policy,
        job_policy,
        rules,
        command,
        sampler=sampler,
        validation_only=validation_only,
        max_runtime_seconds=max_runtime_seconds,
        validation_context=validation_context,
        trusted_validation_entrypoint=trusted_entrypoint,
        trigger_type=(
            "validation"
            if validation_only
            else _effective_trigger_type(args.trigger_type)
        ),
        scheduled_at=(None if validation_only else args.scheduled_at),
        invocation_id=(None if validation_only else args.invocation_id),
        lightgbm_temp_cleanup=(False if validation_only else args.lightgbm_temp_cleanup),
        external_cache_required=not validation_only,
        startup_failure=(False if validation_only else args.startup_failure),
    )


if __name__ == "__main__":
    raise SystemExit(main())
