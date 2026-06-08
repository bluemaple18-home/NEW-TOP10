#!/usr/bin/env python3
"""驗證營運規則跨盤勢報告沒有越界。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL_SHA256 = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify operational rule validation report")
    parser.add_argument("--artifact", default="artifacts/model_experiments/operational_rule_validation_report_2026-06-02.json")
    parser.add_argument("--expected-model-sha256", default=EXPECTED_MODEL_SHA256)
    parser.add_argument("--output", default="artifacts/model_experiments/operational_rule_validation_verification_latest.json")
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


def model_sha256(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
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
    summary = payload.get("summary") or {}
    contract = payload.get("contract") or {}
    variants = payload.get("variants") or {}
    comparisons = payload.get("comparisons") or {}
    model_hash = model_sha256(PROJECT_ROOT / "models" / "latest_lgbm.pkl")

    fixed40 = variants.get("production_fixed40") or {}
    sector45 = variants.get("production_sector45") or {}
    top3 = variants.get("production_top3") or {}
    high_choppy = (fixed40.get("by_regime") or {}).get("HIGH_CHOPPY_CONTEXT") or {}
    checks = {
        "artifact_exists": bool(payload),
        "status_ok": payload.get("status") == "OK",
        "research_only": contract.get("research_only") is True,
        "no_model_changes": contract.get("model_changes") is False and model_hash == args.expected_model_sha256,
        "no_production_ranking_changes": contract.get("production_ranking_changes") is False,
        "no_promotion_evidence": contract.get("promotion_evidence") is False,
        "sector45_monitor_only": summary.get("default_candidate") == "production_fixed40_sector45_monitor",
        "sector45_tolerance_passed": summary.get("sector45_passes_tolerance") is True,
        "gross55_not_default": summary.get("gross55_is_default") is False,
        "top3_not_default": summary.get("top3_is_default") is False,
        "candidate_overlay_rejected": summary.get("candidate_model_overlay") == "rejected_for_now",
        "dynamic_family_exposure_rejected": summary.get("dynamic_family_exposure") == "rejected_for_now",
        "big_bull_present": ((fixed40.get("by_regime") or {}).get("BIG_BULL") or {}).get("daily_count", 0) >= 50,
        "high_choppy_present": high_choppy.get("daily_count", 0) >= 20,
        "sector45_delta_within_tolerance": n((comparisons.get("production_sector45") or {}).get("return_delta")) >= -0.02,
        "dynamic_family_underperforms": n((comparisons.get("production_dynamic_family_exposure") or {}).get("return_delta")) < -0.1,
        "top3_drawdown_worse": n(top3.get("max_drawdown")) < n(fixed40.get("max_drawdown")),
        "sector45_not_worse_drawdown": n(sector45.get("max_drawdown")) >= n(fixed40.get("max_drawdown")) - 0.005,
    }
    failed = [key for key, value in checks.items() if not value]
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "operational-rule-validation-verification.v1",
                "status": "OK" if not failed else "FAILED",
                "artifact": repo_path(artifact),
                "model_sha256": model_hash,
                "checks": checks,
                "failed": failed,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(json.dumps({"status": "OK" if not failed else "FAILED", "output": repo_path(output), "failed": failed}, ensure_ascii=False))
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
