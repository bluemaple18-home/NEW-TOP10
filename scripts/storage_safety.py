#!/usr/bin/env python3
"""TOP10 容量 guard CLI；預設政策未 live 驗證時拒絕啟動。"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict
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


DEFAULT_POLICY = PROJECT_ROOT / "docs" / "operations" / "top10-storage-policy.json"
VALIDATION_MARKER_SCHEMA = "top10-storage-validation-root.v1"


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
    run.add_argument("command", nargs=argparse.REMAINDER)

    validate_run = subparsers.add_parser(
        "validate-run",
        help="只在無 .git 的隔離 sandbox 內執行未 live 驗證的人工代表性週期",
    )
    validate_run.add_argument("--job", required=True)
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


def configure_validation_runtime(job: str) -> dict[str, str]:
    """把 validation child 的暫存與 cache 全部收斂到 sandbox meter scope。"""

    runtime_root = PROJECT_ROOT / "logs" / "storage_safety" / "runtime" / job
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
    global_policy, job_policy, rules = load_policy(resolve_policy(args.policy), args.job)
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
        marker = validate_isolated_root(args.marker, args.job)
        runtime_environment = configure_validation_runtime(args.job)
        trusted_entrypoint = load_trusted_validation_entrypoint(
            PROJECT_ROOT,
            args.job,
            marker,
            args.entrypoint_contract,
        )
        command = list(trusted_entrypoint.command)
        validation_context = {
            "marker": marker,
            "source_input_root": str(
                _existing_lexical_directory(args.source_input_root, "source_input_root")
            ),
            "sandbox_input_root": _path_under_root(
                args.sandbox_input_root,
                "sandbox_input_root",
            ),
            "sandbox_output_root": _path_under_root(
                args.sandbox_output_root,
                "sandbox_output_root",
            ),
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
    return run_guarded_job(
        PROJECT_ROOT,
        global_policy,
        job_policy,
        rules,
        command,
        validation_only=validation_only,
        max_runtime_seconds=max_runtime_seconds,
        validation_context=validation_context,
        trusted_validation_entrypoint=trusted_entrypoint,
    )


if __name__ == "__main__":
    raise SystemExit(main())
