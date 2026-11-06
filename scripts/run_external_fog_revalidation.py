#!/usr/bin/env python3
"""在 tmp artifact lifecycle 管理的外接碟 sandbox 執行 fog 兩週期驗證。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import uuid
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
from app.storage_safety import _existing_lexical_directory

JOB = "fog-research-worker"
EVIDENCE_DIR = "validation_evidence"
SKIP_NAMES = {"__pycache__", ".DS_Store"}
REQUIRED_DOC_AUTHORITIES = (
    Path("architecture/fog_runtime_receipt_v3.schema.json"),
    Path("operations/top10-storage-policy.json"),
)
REQUIRED_ARTIFACT_AUTHORITIES = (
    Path("artifacts/model_experiments/market_regime_history_2023-11-21_2026-05-15.json"),
    Path("artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json"),
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def copy_project(source: Path, sandbox: Path, *, source_commit: str | None = None) -> None:
    """保留舊呼叫點，只複製 pinned helper；其餘 source 只做大小／雜湊清單。"""
    from scripts.run_fog_representative_validation import CANDIDATE_DIR, BASELINE_DIR
    from scripts.storage_validation.fog_research_worker import (
        scan_source_tree, optional_source_file, external_review_selection,
    )

    source = _existing_lexical_directory(source, "source")
    sandbox = _existing_lexical_directory(sandbox, "sandbox")
    if source.is_relative_to(sandbox) or sandbox.is_relative_to(source):
        raise ValueError("source 與 sandbox 不得重疊")
    if (sandbox / ".git").exists() or (sandbox / ".git").is_symlink():
        raise ValueError("sandbox 不得含 .git")
    files = {source / relative for relative in (
        "artifacts/market_regime_history.json", "data/clean/features.parquet",
        "data/reference/stock_industry_map.csv", "config/regime_research_contract.json",
        "scripts/run_autonomous_research.py", "scripts/publish_research_batch_intent.py",
        "scripts/verify_research_spine_batch.py", "scripts/run_backtest_strategy_matrix.py",
    )}
    files.update(source / "docs" / p for p in REQUIRED_DOC_AUTHORITIES)
    files.update(source / p for p in REQUIRED_ARTIFACT_AUTHORITIES)
    scanned_trees = []
    for relative in ("app", "scripts", "config", CANDIDATE_DIR, BASELINE_DIR):
        tree = scan_source_tree(source, str(relative), sorted(SKIP_NAMES), [".pyc"])
        if not tree["exists"]:
            raise ValueError("必要 source tree 缺席")
        scanned_trees.append(tree)
        files.update(source / path for path, kind in tree["entries"].items() if kind == "file")
    rows = []
    for path in sorted(files):
        if path.is_symlink() or not path.is_file() or path.resolve() != path:
            raise ValueError("source manifest 必須是 lexical regular file")
        rows.append({"path": path.relative_to(source).as_posix(), "size": path.stat().st_size,
                     "sha256": sha256_file(path)})
    interpreter = source / ".venv/bin/python"
    resolved = interpreter.resolve(strict=True)
    manifest = {"source_root": str(source), "source_commit": source_commit, "files": rows,
                "scanned_trees": scanned_trees,
                "optional_ledger": optional_source_file(source, "artifacts/model_experiments/model_experiment_ledger.json"),
                "external_review": external_review_selection(source),
                "interpreter": {"path": str(interpreter), "resolved": str(resolved),
                                "size": resolved.stat().st_size, "sha256": sha256_file(resolved)},
                "inputs_closed": False,
                "unresolved_inputs": ["下游動態讀取與環境相依輸入尚未以 live trace 閉合",
                                      "模型路徑尚未證實為本代表性分支必要輸入，未掃描整個 models",
                                      "第三方套件／native library 完整身分尚未閉合"]}
    if len(json.dumps(manifest).encode()) > 4 * 1024**2:
        raise ValueError("source manifest 超過 4 MiB 上限")
    relative = Path("scripts/storage_validation/fog_research_worker.py")
    target = sandbox / relative
    for directory in (target.parent, sandbox / "validation"):
        if directory.resolve() != directory:
            raise ValueError("owned output 不得包含 symlink")
        directory.mkdir(parents=True, exist_ok=True)
        _existing_lexical_directory(directory, "owned output")
    manifest_target = sandbox / "validation/source-manifest.json"
    if target.exists() or target.is_symlink() or manifest_target.exists() or manifest_target.is_symlink():
        raise ValueError("shared fixture 必須是新建目標")
    shutil.copy2(source / relative, target)
    write_json(sandbox / "validation/source-manifest.json", manifest)


def build_validation_contract(sandbox: Path, source_commit: str, *, source_root: Path | None = None) -> tuple[Path, Path]:
    if source_root is not None:
        sandbox = _existing_lexical_directory(sandbox, "sandbox")
        source_root = _existing_lexical_directory(source_root, "source")
        _existing_lexical_directory(sandbox / "validation", "validation")
    runner = (source_root or sandbox) / "scripts" / "run_fog_research_worker.sh"
    entrypoint = sandbox / "scripts" / "storage_validation" / "fog_research_worker.py"
    contract = sandbox / "validation" / "fog-entrypoint-contract.json"
    marker = sandbox / "validation" / "validation-root.json"
    contract_payload = {
        "schema_version": "top10-storage-validation-entrypoint.v1",
        "job": JOB,
        "interpreter": "python-isolated",
        "entrypoint": entrypoint.relative_to(sandbox).as_posix(),
        "entrypoint_sha256": sha256_file(entrypoint),
        "argv": [
            "--runner-sha256",
            sha256_file(runner),
            "--source-commit",
            source_commit,
        ],
    }
    if source_root is not None:
        manifest = sandbox / "validation/source-manifest.json"
        contract_payload["argv"] = [
            "--shared-source", "--source-root", str(source_root.resolve()),
            "--source-commit", source_commit, "--validation-root", str(sandbox.resolve()),
            "--source-manifest", str(manifest.resolve()), "--source-manifest-sha256", sha256_file(manifest),
            "--runner-sha256", sha256_file(runner),
            "--representative-sha256", sha256_file(source_root / "scripts/run_fog_representative_validation.py"),
        ]
    write_json(contract, contract_payload)
    marker_payload = {
        "schema_version": "top10-storage-validation-root.v1",
        "jobs": [JOB],
        "sandbox_root": str(sandbox),
        "manual_only": True,
        "trusted_entrypoints": {
            JOB: {
                "contract_path": contract.relative_to(sandbox).as_posix(),
                "contract_sha256": sha256_file(contract),
            }
        },
    }
    write_json(marker, marker_payload)
    return marker, contract


def resolve_evidence_destination(value: str) -> Path:
    destination = Path(value)
    if not destination.is_absolute():
        raise RuntimeError("evidence destination 必須是絕對路徑")
    resolved_parent = destination.parent.resolve(strict=True)
    evidence_root = (PROJECT_ROOT / "docs" / "evidence").resolve(strict=True)
    if resolved_parent != evidence_root or destination.exists() or destination.is_symlink():
        raise RuntimeError("evidence destination 必須是 docs/evidence 下的新目錄")
    return destination


def publish_evidence(source: Path, destination: Path) -> None:
    """在目的磁碟建立 staging 後原子發布，支援 external sandbox 跨 volume。"""

    if destination.exists() or destination.is_symlink():
        raise FileExistsError(f"evidence destination 已存在：{destination}")
    staging = destination.parent / f".{destination.name}.staging-{uuid.uuid4().hex}"
    try:
        shutil.copytree(source, staging)
        if destination.exists() or destination.is_symlink():
            raise FileExistsError(f"evidence destination 已存在：{destination}")
        os.rename(staging, destination)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise


def run_cycle(sandbox: Path, marker: Path, contract: Path, cycle: int) -> tuple[int, dict[str, Any]]:
    artifact_root = sandbox / "artifacts" / "autonomous_research"
    artifact_patterns = (
        "autonomous_research_daily_quota_????-??-??.json",
        "validation_fixture/fog_representative_validation_????-??-??.json",
    )
    initial_artifacts = [
        path
        for pattern in artifact_patterns
        for path in artifact_root.glob(pattern)
    ]
    before_artifacts = {
        path.relative_to(sandbox).as_posix(): sha256_file(path)
        for path in initial_artifacts
    }
    command = [
        str(PROJECT_ROOT / ".venv" / "bin" / "python"),
        "-B",
        str(PROJECT_ROOT / "scripts" / "storage_safety.py"),
        "--policy",
        str(PROJECT_ROOT / "docs" / "operations" / "top10-storage-policy.json"),
        "validate-run",
        "--sandbox-root",
        str(sandbox),
        "--job",
        JOB,
        "--marker",
        str(marker),
        "--max-runtime-seconds",
        "7200",
        "--source-input-root",
        str(PROJECT_ROOT),
        "--sandbox-input-root",
        str(sandbox),
        "--sandbox-output-root",
        str(sandbox),
        "--entrypoint-contract",
        str(contract),
    ]
    completed = subprocess.run(command, cwd=sandbox, text=True, capture_output=True, check=False)
    receipt_path = sandbox / "logs" / "storage_safety" / f"{JOB}_latest.json"
    if not receipt_path.is_file():
        raise RuntimeError(f"cycle {cycle} 缺 guard receipt：{completed.stderr[-1000:]}")
    receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    observed_artifacts = [
        path
        for pattern in artifact_patterns
        for path in artifact_root.glob(pattern)
    ]
    run_artifacts = sorted(
        (
            path
            for path in observed_artifacts
            if before_artifacts.get(path.relative_to(sandbox).as_posix())
            != sha256_file(path)
        ),
        key=lambda path: path.stat().st_mtime_ns,
    )
    run_payload = (
        json.loads(run_artifacts[-1].read_text(encoding="utf-8"))
        if run_artifacts
        else {}
    )
    topic_runs = run_payload.get("topic_runs")
    representative = {
        "run_artifact": (
            run_artifacts[-1].relative_to(sandbox).as_posix()
            if run_artifacts
            else None
        ),
        "topic_run_count": len(topic_runs) if isinstance(topic_runs, list) else 0,
        "topic_ids": [
            str((row.get("topic") or {}).get("topic_id"))
            for row in (topic_runs if isinstance(topic_runs, list) else [])
            if isinstance(row, dict) and (row.get("topic") or {}).get("topic_id")
        ],
    }
    receipt["representative_workload"] = representative
    empty_reason = (
        "REPRESENTATIVE_WORKLOAD_STALE"
        if observed_artifacts and not run_artifacts
        else "REPRESENTATIVE_WORKLOAD_EMPTY"
    )
    if (
        completed.returncode == 0
        and receipt.get("status") == "OK"
        and receipt.get("child_exit_code") == 0
        and representative["topic_run_count"] == 0
    ):
        receipt["guard_status"] = "OK"
        receipt["status"] = "STOPPED"
        receipt["reasons"] = sorted(
            set([*(receipt.get("reasons") or []), empty_reason])
        )
        completed = subprocess.CompletedProcess(
            completed.args,
            70,
            completed.stdout,
            completed.stderr,
        )
    evidence = sandbox / EVIDENCE_DIR
    write_json(evidence / f"cycle-{cycle}.json", receipt)
    (evidence / f"cycle-{cycle}.stdout.log").write_text(completed.stdout[-12000:], encoding="utf-8")
    (evidence / f"cycle-{cycle}.stderr.log").write_text(completed.stderr[-12000:], encoding="utf-8")
    runtime_logs = evidence / f"cycle-{cycle}-runtime-logs"
    runtime_logs.mkdir()
    for pattern in ("fog_research_worker_*.log", "daily_research_quota_*.log", "fog_research_worker_bootstrap.log"):
        for log_path in (sandbox / "logs").glob(pattern):
            shutil.copy2(log_path, runtime_logs / log_path.name)
    return completed.returncode, receipt


def main() -> int:
    sandbox_text = os.environ.get("TMP_ARTIFACT_ROOT", "")
    external_root_text = os.environ.get("TOP10_EXTERNAL_VOLUME_ROOT", "")
    if os.environ.get("AI_CORE_TMP_ARTIFACT_ACTIVE") != "1" or not sandbox_text:
        raise SystemExit("NO_GO: 必須由 tmp_artifact_lifecycle 啟動")
    sandbox = _existing_lexical_directory(Path(sandbox_text), "sandbox_root")
    external_root = Path(external_root_text).resolve(strict=True)
    destination = resolve_evidence_destination(
        os.environ.get("TOP10_EVIDENCE_DESTINATION", "")
    )
    sandbox.relative_to(external_root)
    if (sandbox / ".git").exists():
        raise SystemExit("NO_GO: lifecycle root 不得是 git checkout")

    evidence = sandbox / EVIDENCE_DIR
    evidence.mkdir()
    source_commit = subprocess.check_output(
        ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"], text=True
    ).strip()
    summary: dict[str, Any] = {
        "schema_version": "top10-external-fog-revalidation.v1",
        "source_commit": source_commit,
        "sandbox_root": str(sandbox),
        "cycles": [],
    }
    result = 70
    try:
        copy_project(PROJECT_ROOT, sandbox, source_commit=source_commit)
        marker, contract = build_validation_contract(sandbox, source_commit, source_root=PROJECT_ROOT)
        for cycle in (1, 2):
            code, receipt = run_cycle(sandbox, marker, contract, cycle)
            summary["cycles"].append(
                {
                    "cycle": cycle,
                    "guard_exit_code": code,
                    "status": receipt.get("status"),
                    "reasons": receipt.get("reasons"),
                    "summary": receipt.get("summary"),
                }
            )
            write_json(evidence / "summary.json", summary)
            if code != 0 or receipt.get("status") != "OK" or receipt.get("child_exit_code") != 0:
                summary["verdict"] = "NO-GO"
                result = code or 70
                break
        else:
            summary["verdict"] = "PASS_CANDIDATE"
            result = 0
    except Exception as error:
        summary["verdict"] = "NO-GO"
        summary["orchestrator_error"] = f"{type(error).__name__}: {error}"
        write_json(evidence / "summary.json", summary)
    write_json(evidence / "summary.json", summary)
    publish_evidence(evidence, destination)
    return result


if __name__ == "__main__":
    raise SystemExit(main())
