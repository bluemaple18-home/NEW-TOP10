#!/usr/bin/env python3
"""執行 Fog circuit recovery 前的 bounded deterministic gates。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "fog-closed-regime-recovery-gate.v1"
PRODUCTION_BASELINE_SCHEMA = "fog-production-hash-baseline.v1"
PROTECTED_ROLES = {"model", "baseline", "ranking", "weights", "promotion"}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify Fog closed-regime recovery gates")
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--market-regime-history", required=True)
    parser.add_argument("--closed-regime-runtime-receipt", required=True)
    parser.add_argument("--production-hash-baseline", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_step(name: str, command: list[str]) -> dict[str, Any]:
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    return {
        "name": name,
        "ok": completed.returncode == 0,
        "returncode": completed.returncode,
        "command": command,
        "stdout_tail": completed.stdout[-2000:],
        "stderr_tail": completed.stderr[-2000:],
    }


def runtime_daily_artifact(receipt_path: Path) -> str:
    try:
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return "__missing_runtime_daily_artifact__"
    daily = receipt.get("daily_research_artifact")
    if not isinstance(daily, dict):
        return "__missing_runtime_daily_artifact__"
    return str(daily.get("path") or "__missing_runtime_daily_artifact__")


def canonical_artifact_path(path: Path) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(PROJECT_ROOT))
    except ValueError:
        return str(resolved)


def current_source_identity() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    identity = completed.stdout.strip()
    if completed.returncode != 0 or len(identity) != 40:
        raise RuntimeError("無法取得可信 git source identity")
    return identity


def build_production_hash_baseline(
    protected_paths: dict[str, Path],
    *,
    source_identity: str,
    created_at: str,
) -> dict[str, Any]:
    if set(protected_paths) != PROTECTED_ROLES:
        raise ValueError(
            f"protected roles 必須完整且固定：{sorted(PROTECTED_ROLES)}"
        )
    missing = [
        f"{role}:{path}"
        for role, path in protected_paths.items()
        if not path.is_file()
    ]
    if missing:
        raise FileNotFoundError(f"production baseline inputs missing: {missing}")
    return {
        "schema_version": PRODUCTION_BASELINE_SCHEMA,
        "created_at": created_at,
        "source_identity": source_identity,
        "artifacts": {
            role: {
                "path": canonical_artifact_path(path),
                "sha256": sha256(path),
            }
            for role, path in sorted(protected_paths.items())
        },
    }


def _baseline_paths(baseline: dict[str, Any]) -> dict[str, Path]:
    artifacts = baseline.get("artifacts")
    if not isinstance(artifacts, dict):
        return {}
    return {
        str(role): resolve_path(str(entry.get("path") or ""))
        for role, entry in artifacts.items()
        if isinstance(entry, dict)
    }


def verify_production_hash_baseline(
    baseline: dict[str, Any],
    protected_paths: dict[str, Path] | None = None,
    *,
    expected_source_identity: str,
) -> dict[str, Any]:
    artifacts = baseline.get("artifacts")
    artifacts = artifacts if isinstance(artifacts, dict) else {}
    current_paths = protected_paths or _baseline_paths(baseline)
    schema_ok = (
        set(baseline)
        == {"schema_version", "created_at", "source_identity", "artifacts"}
        and baseline.get("schema_version") == PRODUCTION_BASELINE_SCHEMA
        and isinstance(baseline.get("created_at"), str)
        and bool(baseline.get("created_at"))
    )
    source_identity_ok = baseline.get("source_identity") == expected_source_identity
    role_set_ok = set(artifacts) == PROTECTED_ROLES == set(current_paths)
    missing: list[str] = []
    path_drift: list[str] = []
    hash_drift: list[str] = []
    current_hashes: dict[str, str] = {}
    for role in sorted(PROTECTED_ROLES):
        entry = artifacts.get(role)
        path = current_paths.get(role)
        if not isinstance(entry, dict) or path is None or not path.is_file():
            missing.append(role)
            continue
        if set(entry) != {"path", "sha256"}:
            path_drift.append(role)
            continue
        if canonical_artifact_path(path) != entry.get("path"):
            path_drift.append(role)
        digest = sha256(path)
        current_hashes[role] = digest
        if digest != entry.get("sha256"):
            hash_drift.append(role)
    return {
        "name": "production_hash_gate",
        "ok": schema_ok
        and source_identity_ok
        and role_set_ok
        and not missing
        and not path_drift
        and not hash_drift,
        "schema_ok": schema_ok,
        "source_identity_ok": source_identity_ok,
        "role_set_ok": role_set_ok,
        "missing": missing,
        "path_drift": path_drift,
        "hash_drift": hash_drift,
        "baseline_hashes": {
            role: entry.get("sha256")
            for role, entry in artifacts.items()
            if isinstance(entry, dict)
        },
        "current_hashes": current_hashes,
    }


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output)
    inventory = (
        f"artifacts/weekend_training/weekend_universe_inventory_{args.run_date}.json"
    )
    runtime_receipt_path = resolve_path(args.closed_regime_runtime_receipt)
    daily_artifact = runtime_daily_artifact(runtime_receipt_path)
    steps = [
        run_step(
            "processed_id_authority",
            [
                sys.executable,
                "scripts/verify_processed_id_authority.py",
                "--weekend-inventory",
                inventory,
                "--output",
                f"{output}.processed_ids.json",
            ],
        ),
        run_step(
            "research_map_verifier",
            [
                sys.executable,
                "scripts/verify_research_fog_map.py",
                "--date",
                args.run_date,
            ],
        ),
        run_step(
            "weekend_inventory_verifier",
            [
                sys.executable,
                "scripts/verify_weekend_universe_inventory.py",
                "--date",
                args.run_date,
                "--output",
                f"{output}.inventory.json",
            ],
        ),
        run_step(
            "closed_regime_runtime_receipt",
            [
                sys.executable,
                "scripts/verify_daily_research_quota.py",
                "--artifact",
                daily_artifact,
                "--closed-regime-runtime-receipt",
                args.closed_regime_runtime_receipt,
                "--output",
                f"{output}.daily_receipt.json",
            ],
        ),
        run_step(
            "targeted_python_tests",
            [
                sys.executable,
                "-m",
                "pytest",
                "-q",
                "tests/test_weekend_universe_inventory_snapshot.py",
                "tests/test_controlled_grid_host_runner_order.py",
                "tests/test_daily_research_quota_verifier.py",
                "tests/test_fog_closed_regime_runtime.py",
                "tests/test_regime_research_autonomy.py",
            ],
        ),
        run_step(
            "queue_ownership",
            ["bash", "tests/test_research_lock_contention.sh"],
        ),
    ]
    baseline_path = resolve_path(args.production_hash_baseline)
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        production_check = verify_production_hash_baseline(
            baseline,
            expected_source_identity=current_source_identity(),
        )
        production_check["returncode"] = 0 if production_check["ok"] else 1
        production_check["baseline_receipt"] = {
            "path": canonical_artifact_path(baseline_path),
            "sha256": sha256(baseline_path),
            "source_identity": baseline.get("source_identity"),
            "created_at": baseline.get("created_at"),
        }
        hashes = production_check["current_hashes"]
        steps.append(production_check)
    except (FileNotFoundError, OSError, json.JSONDecodeError, ValueError) as exc:
        hashes = {}
        steps.append(
            {
                "name": "production_hash_gate",
                "ok": False,
                "returncode": 1,
                "error": str(exc),
            }
        )
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": args.run_date,
        "status": "OK" if all(step["ok"] for step in steps) else "FAILED",
        "checks": steps,
        "production_hashes": hashes,
        "production_impact": "NO_PRODUCTION_CHANGE",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"status": payload["status"], "output": str(output)},
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
