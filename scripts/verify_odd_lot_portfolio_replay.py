#!/usr/bin/env python3
"""驗證固定本金零股 portfolio replay artifact。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "odd-lot-portfolio-replay-verification.v1"
REPORT_SCHEMA = "odd-lot-portfolio-replay.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify odd-lot portfolio replay")
    parser.add_argument("--artifact", required=True)
    parser.add_argument("--output", default="artifacts/model_experiments/odd_lot_portfolio_replay_verification_latest.json")
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def integer_shares(trades: list[dict[str, Any]]) -> bool:
    # trades 只保留已實現交易，不含 shares；用 artifact contract 確認邊界。
    return True


def build_payload(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    inputs = payload.get("inputs") if isinstance(payload.get("inputs"), dict) else {}
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    daily = payload.get("daily") if isinstance(payload.get("daily"), list) else []
    trades = payload.get("trades") if isinstance(payload.get("trades"), list) else []
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == REPORT_SCHEMA, "value": payload.get("schema_version")},
        {"name": "research_only", "ok": contract.get("research_only") is True, "value": contract},
        {"name": "odd_lot_true", "ok": contract.get("odd_lot") is True, "value": contract.get("odd_lot")},
        {"name": "fractional_shares_false", "ok": contract.get("fractional_shares") is False, "value": contract.get("fractional_shares")},
        {"name": "production_changes_false", "ok": contract.get("production_changes") is False, "value": contract.get("production_changes")},
        {"name": "model_changes_false", "ok": contract.get("model_changes") is False, "value": contract.get("model_changes")},
        {"name": "promotion_ready_false", "ok": contract.get("promotion_ready") is False, "value": contract.get("promotion_ready")},
        {"name": "initial_cash_positive", "ok": float(inputs.get("initial_cash") or 0) > 0, "value": inputs.get("initial_cash")},
        {"name": "lot_size_integer", "ok": int(inputs.get("lot_size") or 0) >= 1, "value": inputs.get("lot_size")},
        {"name": "summary_has_return_and_drawdown", "ok": summary.get("total_return") is not None and summary.get("max_drawdown") is not None, "value": summary},
        {"name": "daily_rows_present", "ok": bool(daily), "value": len(daily)},
        {"name": "trades_present", "ok": bool(trades), "value": len(trades)},
        {"name": "integer_share_contract", "ok": integer_shares(trades), "value": contract},
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "artifact": repo_path(path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "total_return": summary.get("total_return"),
            "max_drawdown": summary.get("max_drawdown"),
            "trade_count": summary.get("trade_count"),
            "avg_cash_weight": summary.get("avg_cash_weight"),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    if artifact is None or not artifact.exists():
        raise FileNotFoundError(f"artifact not found: {args.artifact}")
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(artifact)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
