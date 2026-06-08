#!/usr/bin/env python3
"""驗證候選模型 replay 與固定股數研究 artifact。

這個 verifier 只檢查研究輸出是否完整與安全，不把結果升級成 promotion 證據。
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_EXPERIMENTS_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "training-candidate-replay-flow-verification.v1"
PRODUCTION_MODEL = PROJECT_ROOT / "models" / "latest_lgbm.pkl"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify training candidate replay flow")
    parser.add_argument("--artifact", default=None)
    parser.add_argument("--fixed-share-top10", default=None)
    parser.add_argument("--fixed-share-matrix", default=None)
    parser.add_argument("--expected-model-sha256", default=None)
    parser.add_argument(
        "--output",
        default="artifacts/model_experiments/training_candidate_replay_flow_verification_latest.json",
    )
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


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def latest_artifact() -> Path | None:
    matches = sorted(MODEL_EXPERIMENTS_DIR.glob("training_candidates/*/training_candidate_replay_flow.json"))
    return matches[-1] if matches else None


def sha256(path: Path) -> str | None:
    if not path.exists():
        return None
    import hashlib

    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def ranking_file_dates(rankings_dir: Path | None) -> list[str]:
    if rankings_dir is None or not rankings_dir.exists():
        return []
    dates: list[str] = []
    for path in sorted(rankings_dir.glob("ranking_*.csv")):
        match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
        if match:
            dates.append(match.group(1))
    return dates


def default_side_artifacts(flow_path: Path, payload: dict[str, Any]) -> tuple[Path, Path]:
    candidate_root = resolve_path(payload.get("candidate_root")) or flow_path.parent
    run_date = str(payload.get("date") or date_from_flow_path(flow_path))
    return (
        candidate_root / f"fixed_share_top10_candidate_{run_date}.json",
        candidate_root / f"fixed_share_hypothesis_matrix_candidate_{run_date}.json",
    )


def date_from_flow_path(path: Path) -> str:
    return datetime.now(timezone.utc).date().isoformat()


def build_payload(
    flow_path: Path,
    fixed_share_top10_path: Path | None,
    fixed_share_matrix_path: Path | None,
    expected_model_sha256: str | None,
) -> dict[str, Any]:
    payload = read_json(flow_path)
    default_top10, default_matrix = default_side_artifacts(flow_path, payload)
    fixed_share_top10_path = fixed_share_top10_path or default_top10
    fixed_share_matrix_path = fixed_share_matrix_path or default_matrix
    top10 = read_json(fixed_share_top10_path)
    matrix = read_json(fixed_share_matrix_path)

    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    date_window = payload.get("date_window") if isinstance(payload.get("date_window"), dict) else {}
    ranking_results = payload.get("ranking_results") if isinstance(payload.get("ranking_results"), list) else []
    outputs = payload.get("outputs") if isinstance(payload.get("outputs"), dict) else {}
    rankings_dir = resolve_path(payload.get("rankings_dir"))
    expected_ranking_dates = [str(row.get("date")) for row in ranking_results if row.get("status") == "OK"]
    actual_ranking_dates = ranking_file_dates(rankings_dir)
    steps = payload.get("steps") if isinstance(payload.get("steps"), list) else []
    replay = payload.get("replay") if isinstance(payload.get("replay"), dict) else {}
    portfolio = payload.get("portfolio_replay_40d") if isinstance(payload.get("portfolio_replay_40d"), dict) else {}
    top10_contract = top10.get("contract") if isinstance(top10.get("contract"), dict) else {}
    matrix_contract = matrix.get("contract") if isinstance(matrix.get("contract"), dict) else {}
    matrix_summary = matrix.get("summary") if isinstance(matrix.get("summary"), dict) else {}

    production_sha = sha256(PRODUCTION_MODEL)
    checks = [
        {"name": "schema", "ok": payload.get("schema_version") == "training-candidate-replay-flow.v1", "value": payload.get("schema_version")},
        {"name": "status_ok", "ok": payload.get("status") == "OK", "value": payload.get("status")},
        {"name": "candidate_replay_only", "ok": contract.get("candidate_replay_only") is True, "value": contract.get("candidate_replay_only")},
        {
            "name": "production_promotion_blocked",
            "ok": contract.get("production_promotion_allowed") is False,
            "value": contract.get("production_promotion_allowed"),
        },
        {"name": "date_count_positive", "ok": int(date_window.get("date_count") or 0) > 0, "value": date_window.get("date_count")},
        {
            "name": "ranking_results_all_ok",
            "ok": bool(ranking_results) and all(row.get("status") == "OK" for row in ranking_results),
            "value": {"count": len(ranking_results), "failed": [row for row in ranking_results if row.get("status") != "OK"][:5]},
        },
        {
            "name": "ranking_dir_matches_window",
            "ok": actual_ranking_dates == expected_ranking_dates,
            "value": {
                "rankings_dir": repo_path(rankings_dir),
                "expected_count": len(expected_ranking_dates),
                "actual_count": len(actual_ranking_dates),
                "extra_dates": sorted(set(actual_ranking_dates) - set(expected_ranking_dates)),
                "missing_dates": sorted(set(expected_ranking_dates) - set(actual_ranking_dates)),
            },
        },
        {"name": "steps_all_ok", "ok": all(step.get("status") == "OK" for step in steps), "value": [(step.get("name"), step.get("status")) for step in steps]},
        {"name": "replay_output_exists", "ok": bool(resolve_path(outputs.get("replay")) and resolve_path(outputs.get("replay")).exists()), "value": outputs.get("replay")},
        {
            "name": "portfolio_output_exists",
            "ok": bool(resolve_path(outputs.get("portfolio_replay_40d")) and resolve_path(outputs.get("portfolio_replay_40d")).exists()),
            "value": outputs.get("portfolio_replay_40d"),
        },
        {
            "name": "replay_has_trades",
            "ok": int((replay.get("summary") or {}).get("trade_count") or 0) > 0,
            "value": (replay.get("summary") or {}).get("trade_count"),
        },
        {
            "name": "portfolio_has_trades",
            "ok": int((portfolio.get("summary") or {}).get("trade_count") or 0) > 0,
            "value": (portfolio.get("summary") or {}).get("trade_count"),
        },
        {"name": "fixed_share_top10_exists", "ok": fixed_share_top10_path.exists(), "value": repo_path(fixed_share_top10_path)},
        {
            "name": "fixed_share_top10_contract_safe",
            "ok": top10_contract.get("production_changes") is False and top10_contract.get("model_changes") is False,
            "value": top10_contract,
        },
        {"name": "fixed_share_matrix_exists", "ok": fixed_share_matrix_path.exists(), "value": repo_path(fixed_share_matrix_path)},
        {
            "name": "fixed_share_matrix_contract_safe",
            "ok": matrix_contract.get("research_only") is True
            and matrix_contract.get("production_changes") is False
            and matrix_contract.get("model_changes") is False,
            "value": matrix_contract,
        },
        {
            "name": "fixed_share_matrix_has_exit_policies",
            "ok": bool(matrix_summary.get("exit_policy_top")),
            "value": len(matrix_summary.get("exit_policy_top") or []),
        },
        {"name": "errors_empty", "ok": not payload.get("errors"), "value": payload.get("errors")},
        {
            "name": "production_model_hash_expected",
            "ok": expected_model_sha256 is None or production_sha == expected_model_sha256,
            "value": {"actual": production_sha, "expected": expected_model_sha256},
        },
    ]
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "input": repo_path(flow_path),
        "fixed_share_top10": repo_path(fixed_share_top10_path),
        "fixed_share_matrix": repo_path(fixed_share_matrix_path),
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "date_count": date_window.get("date_count"),
            "fixed_share_best_exit_policy": ((matrix_summary.get("exit_policy_top") or [{}])[0]).get("key"),
            "fixed_share_best_return_on_buy_cash": ((matrix_summary.get("exit_policy_top") or [{}])[0]).get("return_on_buy_cash"),
            "portfolio_40d_total_return": (portfolio.get("summary") or {}).get("total_return"),
            "portfolio_40d_max_drawdown": (portfolio.get("summary") or {}).get("max_drawdown"),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    flow_path = resolve_path(args.artifact) or latest_artifact()
    if flow_path is None:
        raise FileNotFoundError("找不到 training_candidates/*/training_candidate_replay_flow.json")
    report = build_payload(
        flow_path=flow_path,
        fixed_share_top10_path=resolve_path(args.fixed_share_top10),
        fixed_share_matrix_path=resolve_path(args.fixed_share_matrix),
        expected_model_sha256=args.expected_model_sha256,
    )
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output path resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(json.dumps({"status": report["status"], "output": repo_path(output), **report["summary"]}, ensure_ascii=False))
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
