#!/usr/bin/env python3
"""驗證 Fog public path 使用的 closed-regime runtime lineage。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import date
from pathlib import Path
from typing import Any

from run_autonomous_research import current_regime_context


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "closed-regime-runtime-receipt.v1"
HISTORY_SCHEMA = "market-regime-history.v2"
PRODUCTION_IMPACT = "NO_PRODUCTION_CHANGE"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify closed-regime runtime lineage")
    parser.add_argument("--run-date", default=date.today().isoformat())
    parser.add_argument("--market-regime-history", required=True)
    parser.add_argument("--research-contract", default="config/regime_research_contract.json")
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


def verify_runtime(
    run_date: str,
    history_path: Path,
    contract_path: Path,
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
    return {
        "schema_version": SCHEMA_VERSION,
        "status": "OK",
        "run_date": run_date,
        "closed_regime_research": True,
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
            "to": "READY_FOR_CLOSED_RESEARCH",
        },
        "production_impact": PRODUCTION_IMPACT,
    }


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output)
    payload = verify_runtime(
        args.run_date,
        resolve_path(args.market_regime_history),
        resolve_path(args.research_contract),
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
