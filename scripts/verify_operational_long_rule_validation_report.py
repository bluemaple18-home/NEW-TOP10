#!/usr/bin/env python3
"""驗證長區間 daily 營運規則報告的降級判斷。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL_SHA256 = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify operational long rule validation report")
    parser.add_argument("--artifact", default="artifacts/model_experiments/operational_long_rule_validation_report_2026-06-02.json")
    parser.add_argument("--expected-model-sha256", default=EXPECTED_MODEL_SHA256)
    parser.add_argument("--output", default="artifacts/model_experiments/operational_long_rule_validation_verification_latest.json")
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
    manifests = payload.get("ranking_manifests") or {}
    dense_manifest = manifests.get("dense") or {}
    stride3_manifest = manifests.get("stride3") or {}
    variants = payload.get("variants") or {}
    dense_variants = variants.get("dense") or {}
    comparisons = payload.get("comparisons") or {}
    dense_comparisons = comparisons.get("dense") or {}
    stability = payload.get("stability") or {}
    rolling = stability.get("rolling_vs_fixed40") or {}
    gross55_40d = rolling.get("gross55_40d") or {}
    gross55_80d = rolling.get("gross55_80d") or {}
    fixed40 = dense_variants.get("fixed40") or {}
    sector45 = dense_variants.get("sector45") or {}
    gross55 = dense_variants.get("gross55") or {}
    top3 = dense_variants.get("top3") or {}
    checks = {
        "artifact_exists": bool(payload),
        "status_ok": payload.get("status") == "OK",
        "research_only": contract.get("research_only") is True,
        "dense_daily_declared": contract.get("dense_daily_evidence") is True,
        "stride_sample_declared": contract.get("stride_sample") is True,
        "primary_evidence_dense": payload.get("primary_evidence") == "dense_daily",
        "no_model_changes": contract.get("model_changes") is False and model_sha256() == args.expected_model_sha256,
        "no_production_ranking_changes": contract.get("production_ranking_changes") is False,
        "dense_manifest_ok": dense_manifest.get("status") == "OK" and int(dense_manifest.get("ranking_count") or 0) >= 500,
        "dense_manifest_daily": int(dense_manifest.get("stride") or 0) == 1,
        "dense_manifest_zero_failures": int(dense_manifest.get("failure_count") or 0) == 0,
        "stride3_manifest_ok": stride3_manifest.get("status") == "OK" and int(stride3_manifest.get("ranking_count") or 0) >= 180,
        "stride3_manifest_zero_failures": int(stride3_manifest.get("failure_count") or 0) == 0,
        "sector45_rejected": summary.get("sector45_status") == "REJECT_AS_DEFAULT_ON_DENSE_LONG",
        "gross55_conservative": summary.get("gross55_status") == "CONSERVATIVE_CANDIDATE_FOR_DRAWDOWN_REDUCTION",
        "top3_rejected": summary.get("top3_status") == "REJECT_AS_AGGRESSIVE_DEFAULT_ON_DENSE_LONG",
        "sector45_return_hurt": n((dense_comparisons.get("sector45") or {}).get("return_delta")) < -0.1,
        "sector45_drawdown_not_helpful": n(sector45.get("max_drawdown")) - n(fixed40.get("max_drawdown")) < 0.01,
        "gross55_return_positive": n(gross55.get("total_return")) > 0.0,
        "gross55_drawdown_improves": n(gross55.get("max_drawdown")) > n(fixed40.get("max_drawdown")),
        "gross55_drawdown_material": n(gross55.get("max_drawdown")) - n(fixed40.get("max_drawdown")) > 0.03,
        "stability_present": bool(stability.get("periods")) and bool(rolling),
        "gross55_40d_rolling_enough": int(gross55_40d.get("count") or 0) >= 500,
        "gross55_40d_drawdown_often_improves": n(gross55_40d.get("candidate_drawdown_improves_rate")) >= 0.6,
        "gross55_80d_rolling_enough": int(gross55_80d.get("count") or 0) >= 500,
        "gross55_80d_drawdown_often_improves": n(gross55_80d.get("candidate_drawdown_improves_rate")) >= 0.6,
        "fixed40_high_drawdown": n(fixed40.get("max_drawdown")) < -0.25,
        "top3_return_lower_than_baseline": n(top3.get("total_return")) < n(fixed40.get("total_return")),
    }
    failed = [key for key, value in checks.items() if not value]
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(
            {
                "schema_version": "operational-long-rule-validation-verification.v1",
                "status": "OK" if not failed else "FAILED",
                "artifact": repo_path(artifact),
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
