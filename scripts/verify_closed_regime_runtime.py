#!/usr/bin/env python3
"""驗證 Fog public path 使用的 closed-regime runtime lineage。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from run_autonomous_research import current_regime_context


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "closed-regime-runtime-receipt.v2"
HISTORY_SCHEMA = "market-regime-history.v2"
DAILY_SCHEMA = "autonomous-research-run.v1"
PRODUCTION_IMPACT = "NO_PRODUCTION_CHANGE"
QUEUE_OWNER = "fog_worker"
RUNNER_IDENTITY = "scripts/run_daily_research_quota.sh"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify closed-regime runtime lineage")
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--market-regime-history", required=True)
    parser.add_argument("--research-contract", default="config/regime_research_contract.json")
    parser.add_argument("--daily-research-artifact", default=None)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical_json_hash(value: Any) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def topic_run_lineage(payload: dict[str, Any]) -> list[dict[str, str | None]]:
    rows = payload.get("topic_runs")
    rows = rows if isinstance(rows, list) else []
    return [
        {
            "topic_id": str((row.get("topic") or {}).get("topic_id") or ""),
            "status": str(row.get("status") or ""),
            "decision": (row.get("outcome") or {}).get("decision"),
        }
        for row in rows
        if isinstance(row, dict)
    ]


def verify_runtime(
    run_date: str,
    history_path: Path,
    contract_path: Path,
    daily_artifact_path: Path | None = None,
) -> dict[str, Any]:
    if not history_path.is_file():
        raise FileNotFoundError(f"market regime history 不存在：{history_path}")
    if not contract_path.is_file():
        raise FileNotFoundError(f"research contract 不存在：{contract_path}")
    history = json.loads(history_path.read_text(encoding="utf-8"))
    if history.get("schema_version") != HISTORY_SCHEMA:
        raise ValueError(
            f"market regime history schema 必須為 {HISTORY_SCHEMA}："
            f"{history.get('schema_version')}"
        )
    context = current_regime_context(history_path, run_date)
    identity = context["identity"]
    daily_artifact: dict[str, Any] | None = None
    topic_runs: list[dict[str, str | None]] = []
    if daily_artifact_path is not None:
        if not daily_artifact_path.is_file():
            raise FileNotFoundError(f"daily research artifact 不存在：{daily_artifact_path}")
        daily_artifact = json.loads(daily_artifact_path.read_text(encoding="utf-8"))
        inputs = (
            daily_artifact.get("inputs")
            if isinstance(daily_artifact.get("inputs"), dict)
            else {}
        )
        if daily_artifact.get("schema_version") != DAILY_SCHEMA:
            raise ValueError(f"daily research artifact schema 必須為 {DAILY_SCHEMA}")
        if daily_artifact.get("date") != run_date:
            raise ValueError("daily research artifact date 與 run date 不一致")
        if inputs.get("closed_regime_research") is not True:
            raise ValueError("daily research artifact 未啟用 closed-regime research")
        if resolve_path(str(inputs.get("market_regime_history") or "")).resolve() != history_path.resolve():
            raise ValueError("daily research artifact history path 與已驗證 history 不一致")
        if resolve_path(str(inputs.get("research_contract") or "")).resolve() != contract_path.resolve():
            raise ValueError("daily research artifact contract path 與已驗證 contract 不一致")
        topic_runs = topic_run_lineage(daily_artifact)
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "OK" if daily_artifact is not None else "READY",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "closed_regime_research": True,
        "queue_owner": QUEUE_OWNER,
        "runner_identity": RUNNER_IDENTITY,
        "market_regime_history": {
            "path": repo_path(history_path),
            "schema_version": HISTORY_SCHEMA,
            "sha256": sha256(history_path),
            "source_trade_date": context["source_trade_date"],
        },
        "research_contract": {
            "path": repo_path(contract_path),
            "sha256": sha256(contract_path),
        },
        "exact_regime": {
            "base_regime": identity["base_regime"],
            "family_tags": identity["family_tags"],
            "identity_id": context["identity_id"],
        },
        "state_transition": {
            "from": "VERIFIED_HISTORY",
            "to": (
                "CLOSED_RESEARCH_COMPLETED"
                if daily_artifact is not None
                else "READY_FOR_CLOSED_RESEARCH"
            ),
        },
        "daily_research_artifact": (
            {
                "path": repo_path(daily_artifact_path),
                "schema_version": DAILY_SCHEMA,
                "sha256": sha256(daily_artifact_path),
                "run_date": run_date,
            }
            if daily_artifact_path is not None
            else None
        ),
        "topic_runs": topic_runs,
        "topic_runs_sha256": canonical_json_hash(topic_runs),
        "production_impact": PRODUCTION_IMPACT,
    }


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output)
    payload = verify_runtime(
        args.run_date,
        resolve_path(args.market_regime_history),
        resolve_path(args.research_contract),
        resolve_path(args.daily_research_artifact)
        if args.daily_research_artifact
        else None,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "closed_regime_research": True,
                "exact_regime": payload["exact_regime"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
