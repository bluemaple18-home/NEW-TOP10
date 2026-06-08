#!/usr/bin/env python3
"""驗證近半年出場規則 portfolio-level report。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL_SHA256 = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify exit rule portfolio-level report")
    parser.add_argument("--artifact", default="artifacts/model_experiments/exit_rule_portfolio_level_report_2026-06-02.json")
    parser.add_argument("--expected-model-sha256", default=EXPECTED_MODEL_SHA256)
    parser.add_argument("--output", default="artifacts/model_experiments/exit_rule_portfolio_level_verification_latest.json")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def model_sha256() -> str:
    digest = hashlib.sha256()
    with (PROJECT_ROOT / "models" / "latest_lgbm.pkl").open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact)
    payload = read_json(artifact)
    contract = payload.get("contract") or {}
    summary = payload.get("summary") or {}
    rows = payload.get("rows") or {}
    comps = payload.get("comparisons_vs_h40_fixed65") or {}
    fixed = rows.get("h40_fixed65") or {}
    tp15 = rows.get("h40_tp15_fixed65") or {}
    stop_take = rows.get("h30_tp25_sl10_fixed65") or {}
    checks = {
        "artifact_exists": bool(payload),
        "status_ok": payload.get("status") == "OK",
        "research_only": contract.get("research_only") is True,
        "default_not_allowed": contract.get("production_default_allowed") is False,
        "no_model_change": contract.get("does_not_train_model") is True and model_sha256() == args.expected_model_sha256,
        "no_ranking_change": contract.get("does_not_change_production_ranking") is True,
        "primary_candidate": summary.get("primary_shadow_candidate") == "h40_tp15_fixed65",
        "defensive_candidate": summary.get("defensive_shadow_candidate") == "h30_tp25_sl10_fixed65",
        "fixed_highest_return": n(fixed.get("total_return")) > n(tp15.get("total_return"))
        and n(fixed.get("total_return")) > n(stop_take.get("total_return")),
        "tp15_drawdown_improves": n((comps.get("h40_tp15_fixed65") or {}).get("max_drawdown_delta")) > 0,
        "tp15_win_rate_improves": n((comps.get("h40_tp15_fixed65") or {}).get("win_rate_delta")) > 0,
        "stop_take_drawdown_improves": n((comps.get("h30_tp25_sl10_fixed65") or {}).get("max_drawdown_delta")) > 0,
        "event_exits_present": int((tp15.get("exit_counts") or {}).get("take_profit") or 0) > 0
        and int((stop_take.get("exit_counts") or {}).get("stop_loss") or 0) > 0,
    }
    failed = [key for key, value in checks.items() if not value]
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "exit-rule-portfolio-level-verification.v1",
                "status": "OK" if not failed else "FAILED",
                "artifact": repo_path(artifact),
                "checks": checks,
                "failed": failed,
            },
            ensure_ascii=False,
            indent=2,
            allow_nan=False,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": "OK" if not failed else "FAILED", "output": repo_path(output), "failed": failed}, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
