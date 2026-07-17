"""每日自動化與 Daily V2 共用的核心契約。"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

DAILY_CORE_CONTRACT_VERSION = "top10.daily-core-contract.v1"
PRODUCTION_CORE_STEP_MAP = {
    "etl": "etl",
    "data.validate": "validate",
    "ranking": "rank",
    "daily.report": "report",
    "clawd.payload": "publish-ready",
}
DAILY_CORE_STEPS = tuple(PRODUCTION_CORE_STEP_MAP.values())
PRODUCTION_EQUIVALENT_PROFILE = "production-equivalent"


def has_production_equivalent_attestation(workflow_manifest: dict) -> bool:
    """只有 manifest 自身宣告且綁定共用契約時，才視為 production-equivalent。"""

    attestation = workflow_manifest.get("production_equivalence")
    if not bool(
        isinstance(attestation, dict)
        and attestation.get("profile") == PRODUCTION_EQUIVALENT_PROFILE
        and attestation.get("contract_version") == DAILY_CORE_CONTRACT_VERSION
        and attestation.get("attested") is True
        and attestation.get("issuer") == "scripts/run_daily_v2.py"
        and re.fullmatch(r"[0-9a-f]{40}", str(attestation.get("source_sha") or ""))
    ):
        return False
    runner = attestation.get("runner")
    commands = attestation.get("expanded_commands")
    if not isinstance(runner, dict) or not isinstance(commands, list) or not commands:
        return False
    runner_path = Path(str(runner.get("path") or "")).expanduser()
    if not runner_path.is_file() or runner_path.name != "run_daily_v2.py":
        return False
    runner_sha = hashlib.sha256(runner_path.read_bytes()).hexdigest()
    commands_sha = hashlib.sha256(
        json.dumps(commands, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()
    git_result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=runner_path.resolve().parents[1],
        capture_output=True,
        text=True,
        check=False,
    )
    real_shadow_command = any(
        "--dry-run" in command and "--source" in command and "real" in command
        for command in commands
        if isinstance(command, list)
    )
    return bool(
        runner_sha == runner.get("sha256")
        and commands_sha == attestation.get("expanded_commands_sha256")
        and all(isinstance(command, list) and str(runner_path) in map(str, command) for command in commands)
        and git_result.returncode == 0
        and git_result.stdout.strip() == attestation.get("source_sha")
        and real_shadow_command
    )
