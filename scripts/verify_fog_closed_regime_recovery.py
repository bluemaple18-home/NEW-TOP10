#!/usr/bin/env python3
"""執行 Fog circuit recovery 前的 bounded deterministic gates。"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

try:
    from fog_authority_contracts import (
        PROTECTED_CONTRACT_SCHEMA,
        PROTECTED_ROLE_PATHS,
        canonical_baseline_path,
        canonical_protected_paths,
        protected_contract_hash,
    )
except ModuleNotFoundError:  # pragma: no cover - package import path
    from scripts.fog_authority_contracts import (
        PROTECTED_CONTRACT_SCHEMA,
        PROTECTED_ROLE_PATHS,
        canonical_baseline_path,
        canonical_protected_paths,
        protected_contract_hash,
    )

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "fog-closed-regime-recovery-gate.v1"
PRODUCTION_BASELINE_SCHEMA = "fog-production-hash-baseline.v2"
PROTECTED_ROLES = set(PROTECTED_ROLE_PATHS)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify Fog closed-regime recovery gates")
    parser.add_argument("--create-production-hash-baseline", action="store_true")
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--market-regime-history")
    parser.add_argument("--closed-regime-runtime-receipt")
    parser.add_argument("--production-hash-baseline", required=True)
    parser.add_argument("--output")
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


def canonical_artifact_path(path: Path, root: Path = PROJECT_ROOT) -> str:
    resolved = path.resolve()
    try:
        return str(resolved.relative_to(root.resolve()))
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
    *,
    run_date: str,
    root: Path,
    source_identity: str,
    created_at: str,
) -> dict[str, Any]:
    date.fromisoformat(run_date)
    created = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
    if created.tzinfo is None or created.utcoffset() is None:
        raise ValueError("production baseline created_at 必須為有 timezone 的 RFC3339")
    if created.astimezone(timezone.utc).date().isoformat() != run_date:
        raise ValueError("production baseline created_at 必須與 run_date 同日")
    protected_paths = canonical_protected_paths(root, run_date)
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
        "run_date": run_date,
        "source_identity": source_identity,
        "protected_contract": {
            "schema_version": PROTECTED_CONTRACT_SCHEMA,
            "sha256": protected_contract_hash(),
        },
        "artifacts": {
            role: {
                "path": canonical_artifact_path(path, root),
                "sha256": sha256(path),
            }
            for role, path in sorted(protected_paths.items())
        },
    }


def write_production_hash_baseline_once(
    output_path: Path,
    *,
    run_date: str,
    root: Path,
    source_identity: str,
    created_at: str,
) -> dict[str, Any]:
    expected_output = canonical_baseline_path(root, run_date)
    try:
        expected_output.resolve().relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError("canonical baseline path 不得逃逸 repo root") from exc
    if output_path.resolve() != expected_output.resolve():
        raise ValueError(
            "production baseline output 必須是 canonical baseline path："
            f"{canonical_artifact_path(expected_output, root)}"
        )
    baseline = build_production_hash_baseline(
        run_date=run_date,
        root=root,
        source_identity=source_identity,
        created_at=created_at,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("x", encoding="utf-8") as handle:
        handle.write(
            json.dumps(
                baseline,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )
    return baseline


def verify_production_hash_baseline(
    baseline: dict[str, Any],
    *,
    run_date: str,
    root: Path,
    expected_source_identity: str,
) -> dict[str, Any]:
    artifacts = baseline.get("artifacts")
    artifacts = artifacts if isinstance(artifacts, dict) else {}
    current_paths = canonical_protected_paths(root, run_date)
    protected_contract = (
        baseline.get("protected_contract")
        if isinstance(baseline.get("protected_contract"), dict)
        else {}
    )
    try:
        created_at = datetime.fromisoformat(
            str(baseline.get("created_at") or "").replace("Z", "+00:00")
        )
        created_at_ok = bool(
            created_at.tzinfo is not None
            and created_at.utcoffset() is not None
            and created_at.astimezone(timezone.utc).date().isoformat()
            == run_date
        )
    except ValueError:
        created_at_ok = False
    schema_ok = (
        set(baseline)
        == {
            "schema_version",
            "created_at",
            "run_date",
            "source_identity",
            "protected_contract",
            "artifacts",
        }
        and baseline.get("schema_version") == PRODUCTION_BASELINE_SCHEMA
        and isinstance(baseline.get("created_at"), str)
        and bool(baseline.get("created_at"))
        and created_at_ok
        and baseline.get("run_date") == run_date
        and set(protected_contract) == {"schema_version", "sha256"}
        and protected_contract.get("schema_version")
        == PROTECTED_CONTRACT_SCHEMA
        and protected_contract.get("sha256") == protected_contract_hash()
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
        if canonical_artifact_path(path, root) != entry.get("path"):
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
    baseline_path = resolve_path(args.production_hash_baseline)
    canonical_path = canonical_baseline_path(PROJECT_ROOT, args.run_date)
    if baseline_path.resolve() != canonical_path.resolve():
        raise ValueError(
            "production baseline 必須使用 canonical baseline path："
            f"{canonical_artifact_path(canonical_path)}"
        )
    if args.create_production_hash_baseline:
        baseline = write_production_hash_baseline_once(
            baseline_path,
            run_date=args.run_date,
            root=PROJECT_ROOT,
            source_identity=current_source_identity(),
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        print(
            json.dumps(
                {
                    "status": "CREATED",
                    "path": canonical_artifact_path(baseline_path),
                    "sha256": sha256(baseline_path),
                    "source_identity": baseline["source_identity"],
                    "protected_contract_sha256": baseline[
                        "protected_contract"
                    ]["sha256"],
                },
                ensure_ascii=False,
            )
        )
        return 0
    if not (
        args.market_regime_history
        and args.closed_regime_runtime_receipt
        and args.output
    ):
        raise ValueError(
            "recovery verification 必須提供 market history、runtime receipt 與 output"
        )
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
    try:
        baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
        production_check = verify_production_hash_baseline(
            baseline,
            run_date=args.run_date,
            root=PROJECT_ROOT,
            expected_source_identity=current_source_identity(),
        )
        production_check["returncode"] = 0 if production_check["ok"] else 1
        production_check["baseline_receipt"] = {
            "path": canonical_artifact_path(baseline_path),
            "sha256": sha256(baseline_path),
            "source_identity": baseline.get("source_identity"),
            "created_at": baseline.get("created_at"),
            "protected_contract_sha256": (
                baseline.get("protected_contract") or {}
            ).get("sha256"),
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
