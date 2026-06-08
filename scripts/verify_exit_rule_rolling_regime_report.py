#!/usr/bin/env python3
"""驗證出場規則 rolling / 盤勢切片報告。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL_SHA256 = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify exit rule rolling regime report")
    parser.add_argument("--artifact", default="artifacts/model_experiments/exit_rule_rolling_regime_report_2026-06-02.json")
    parser.add_argument("--expected-model-sha256", default=EXPECTED_MODEL_SHA256)
    parser.add_argument("--output", default="artifacts/model_experiments/exit_rule_rolling_regime_verification_latest.json")
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
    rules = payload.get("contextual_rules") or {}
    rolling = payload.get("rolling_vs_h40_fixed65") or {}
    regime = payload.get("regime_vs_h40_fixed65") or {}
    high_choppy = {label: (body or {}).get("HIGH_CHOPPY_CONTEXT") or {} for label, body in regime.items()}
    risk_off = {label: (body or {}).get("RISK_OFF") or {} for label, body in regime.items()}
    checks = {
        "artifact_exists": bool(payload),
        "status_ok": payload.get("status") == "OK",
        "research_only": contract.get("research_only") is True,
        "default_not_allowed": contract.get("production_default_allowed") is False,
        "no_model_change": contract.get("does_not_train_model") is True and model_sha256() == args.expected_model_sha256,
        "no_ranking_change": contract.get("does_not_change_production_ranking") is True,
        "no_score_change": contract.get("does_not_change_risk_adjusted_score") is True,
        "big_bull_prefers_fixed": rules.get("big_bull_preference") == "h40_fixed65",
        "high_choppy_prefers_stop_take": rules.get("high_choppy_preference") == "h30_tp25_sl10_fixed65",
        "risk_off_prefers_tp15": rules.get("risk_off_preference") == "h40_tp15_fixed65",
        "tp15_rolling_drawdown_stable": n((rolling.get("h40_tp15_fixed65") or {}).get("20d", {}).get("drawdown_improves_rate")) >= 0.8
        and n((rolling.get("h40_tp15_fixed65") or {}).get("40d", {}).get("drawdown_improves_rate")) >= 0.8,
        "gross55_tp15_drawdown_always_improves": n((rolling.get("h40_tp15_gross55") or {}).get("20d", {}).get("drawdown_improves_rate")) >= 0.95
        and n((rolling.get("h40_tp15_gross55") or {}).get("40d", {}).get("drawdown_improves_rate")) >= 0.95,
        "high_choppy_sample_present": int((high_choppy.get("h30_tp25_sl10_fixed65") or {}).get("daily_count") or 0) >= 30,
        "high_choppy_stop_take_better_than_tp15": n((high_choppy.get("h30_tp25_sl10_fixed65") or {}).get("return_delta"))
        > n((high_choppy.get("h40_tp15_fixed65") or {}).get("return_delta"))
        and n((high_choppy.get("h30_tp25_sl10_fixed65") or {}).get("drawdown_delta"))
        > n((high_choppy.get("h40_tp15_fixed65") or {}).get("drawdown_delta")),
        "risk_off_tp15_drawdown_material": n((risk_off.get("h40_tp15_fixed65") or {}).get("drawdown_delta")) > 0.02,
    }
    failed = [key for key, value in checks.items() if not value]
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "exit-rule-rolling-regime-verification.v1",
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
