#!/usr/bin/env python3
"""執行 Fog circuit recovery 前的 bounded deterministic gates。"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "fog-closed-regime-recovery-gate.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify Fog closed-regime recovery gates")
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--market-regime-history", required=True)
    parser.add_argument("--closed-regime-runtime-receipt", required=True)
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


def production_hashes() -> dict[str, str]:
    paths = {
        "model": PROJECT_ROOT / "models/latest_lgbm.pkl",
        "baseline": PROJECT_ROOT / "models/baseline_stats.json",
    }
    ranking_pattern = re.compile(r"ranking_\d{4}-\d{2}-\d{2}\.csv$")
    rankings = sorted(
        path
        for path in (PROJECT_ROOT / "artifacts").glob("ranking_*.csv")
        if ranking_pattern.fullmatch(path.name)
    )
    if not rankings:
        raise FileNotFoundError("找不到 production ranking artifact")
    paths["ranking"] = rankings[-1]
    missing = [str(path) for path in paths.values() if not path.is_file()]
    if missing:
        raise FileNotFoundError(f"production hash inputs missing: {missing}")
    return {name: sha256(path) for name, path in paths.items()}


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output)
    inventory = (
        f"artifacts/weekend_training/weekend_universe_inventory_{args.run_date}.json"
    )
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
            "closed_regime_canary",
            [
                sys.executable,
                "scripts/verify_closed_regime_runtime.py",
                "--run-date",
                args.run_date,
                "--market-regime-history",
                args.market_regime_history,
                "--output",
                args.closed_regime_runtime_receipt,
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
        hashes = production_hashes()
        steps.append(
            {
                "name": "production_hash_gate",
                "ok": True,
                "returncode": 0,
                "value": hashes,
            }
        )
    except (FileNotFoundError, OSError) as exc:
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
