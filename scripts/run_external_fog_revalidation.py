#!/usr/bin/env python3
"""在 tmp artifact lifecycle 管理的外接碟 sandbox 執行 fog 兩週期驗證。"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
JOB = "fog-research-worker"
EVIDENCE_DIR = "validation_evidence"
SKIP_TOP_LEVEL = {".git", ".codegraph", ".pytest_cache", "logs"}
SKIP_NAMES = {"__pycache__", ".DS_Store"}


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


def copy_ignore(directory: str, names: list[str]) -> set[str]:
    ignored = {name for name in names if name in SKIP_NAMES or name.endswith(".pyc")}
    if Path(directory).name == "artifacts":
        ignored.update(name for name in names if name == "archive")
    return ignored


def copy_project(source: Path, sandbox: Path) -> None:
    for child in source.iterdir():
        if child.name in SKIP_TOP_LEVEL:
            continue
        target = sandbox / child.name
        if child.is_dir():
            shutil.copytree(child, target, symlinks=False, ignore=copy_ignore)
        elif child.is_file():
            shutil.copy2(child, target)
    python_source = (source / ".venv" / "bin" / "python").resolve(strict=True)
    runtime_library = python_source.parents[1] / "lib" / "libpython3.12.dylib"
    shutil.copy2(runtime_library, sandbox / ".venv" / "lib" / runtime_library.name)
    links = [path for path in sandbox.rglob("*") if path.is_symlink()]
    if links:
        raise RuntimeError(f"sandbox 仍含 symlink：{links[0]}")


def build_validation_contract(sandbox: Path) -> tuple[Path, Path]:
    runner = sandbox / "scripts" / "run_fog_research_worker.sh"
    entrypoint = sandbox / "scripts" / "storage_validation" / "fog_research_worker.py"
    contract = sandbox / "validation" / "fog-entrypoint-contract.json"
    marker = sandbox / "validation" / "validation-root.json"
    contract_payload = {
        "schema_version": "top10-storage-validation-entrypoint.v1",
        "job": JOB,
        "interpreter": "python-isolated",
        "entrypoint": entrypoint.relative_to(sandbox).as_posix(),
        "entrypoint_sha256": sha256_file(entrypoint),
        "argv": ["--runner-sha256", sha256_file(runner)],
    }
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


def run_cycle(sandbox: Path, marker: Path, contract: Path, cycle: int) -> tuple[int, dict[str, Any]]:
    command = [
        str(sandbox / ".venv" / "bin" / "python"),
        str(sandbox / "scripts" / "storage_safety.py"),
        "--policy",
        str(sandbox / "docs" / "operations" / "top10-storage-policy.json"),
        "validate-run",
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
    evidence = sandbox / EVIDENCE_DIR
    shutil.copy2(receipt_path, evidence / f"cycle-{cycle}.json")
    (evidence / f"cycle-{cycle}.stdout.log").write_text(completed.stdout[-12000:], encoding="utf-8")
    (evidence / f"cycle-{cycle}.stderr.log").write_text(completed.stderr[-12000:], encoding="utf-8")
    return completed.returncode, receipt


def main() -> int:
    sandbox_text = os.environ.get("TMP_ARTIFACT_ROOT", "")
    external_root_text = os.environ.get("TOP10_EXTERNAL_VOLUME_ROOT", "")
    if os.environ.get("AI_CORE_TMP_ARTIFACT_ACTIVE") != "1" or not sandbox_text:
        raise SystemExit("NO_GO: 必須由 tmp_artifact_lifecycle 啟動")
    sandbox = Path(sandbox_text).resolve(strict=True)
    external_root = Path(external_root_text).resolve(strict=True)
    sandbox.relative_to(external_root)
    if (sandbox / ".git").exists():
        raise SystemExit("NO_GO: lifecycle root 不得是 git checkout")

    evidence = sandbox / EVIDENCE_DIR
    evidence.mkdir()
    copy_project(PROJECT_ROOT, sandbox)
    marker, contract = build_validation_contract(sandbox)
    summary: dict[str, Any] = {
        "schema_version": "top10-external-fog-revalidation.v1",
        "source_commit": subprocess.check_output(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"], text=True
        ).strip(),
        "sandbox_root": str(sandbox),
        "cycles": [],
    }
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
            write_json(evidence / "summary.json", summary)
            return code or 70
    summary["verdict"] = "PASS_CANDIDATE"
    write_json(evidence / "summary.json", summary)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
