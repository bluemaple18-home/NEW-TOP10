#!/usr/bin/env python3
"""驗證 guarded Top10 replay artifact 的 shadow-only 契約。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
CANDIDATE_POOL_SIZE_CONTRACT = 80
CANDIDATE_POOL_RULE = "model_inference_top80_before_guard"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify guarded Top10 replay research artifact")
    parser.add_argument("--artifact", default=None, help="指定 guarded_top10_replay_YYYY-MM-DD.json")
    parser.add_argument("--artifacts-dir", default="artifacts/research")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def latest_artifact(artifacts_dir: Path) -> Path:
    files = sorted(artifacts_dir.glob("guarded_top10_replay_????-??-??.json"))
    if not files:
        raise FileNotFoundError(f"找不到 guarded_top10_replay artifact：{artifacts_dir}")
    return files[-1]


def main() -> int:
    args = parse_args()
    artifact = resolve_path(args.artifact) if args.artifact else latest_artifact(resolve_path(args.artifacts_dir))
    errors = verify(artifact)
    status = "OK" if not errors else "FAILED"
    print(json.dumps({"status": status, "artifact": repo_path(artifact), "errors": errors}, ensure_ascii=False, indent=2))
    return 0 if not errors else 1


def verify(artifact: Path) -> list[str]:
    errors: list[str] = []
    if not artifact.exists():
        return [f"artifact missing: {artifact}"]
    payload = json.loads(artifact.read_text(encoding="utf-8"))
    contract = payload.get("contract", {})
    inputs = payload.get("inputs", {})
    outputs = payload.get("outputs", {})
    summary = payload.get("summary", {})
    top10 = payload.get("shadow_guarded_top10", [])
    candidate_pool = payload.get("candidate_pool_top80", [])

    if payload.get("schema_version") != "guarded-top10-replay.v1":
        errors.append("schema_version must be guarded-top10-replay.v1")
    if payload.get("status") != "OK":
        errors.append("status must be OK")
    if not contract.get("research_only"):
        errors.append("contract.research_only must be true")
    for key in ("does_not_train_model", "does_not_write_models_latest_lgbm", "does_not_change_production_ranking", "does_not_change_publish_source"):
        if contract.get(key) is not True:
            errors.append(f"contract.{key} must be true")
    if contract.get("candidate_pool_rule") != CANDIDATE_POOL_RULE:
        errors.append(f"contract.candidate_pool_rule must be {CANDIDATE_POOL_RULE}")
    if int(inputs.get("candidate_pool_size") or 0) != CANDIDATE_POOL_SIZE_CONTRACT:
        errors.append(f"inputs.candidate_pool_size must be {CANDIDATE_POOL_SIZE_CONTRACT}")

    json_output = str(outputs.get("json") or "")
    md_output = str(outputs.get("markdown") or "")
    if not re.fullmatch(r"artifacts/research/guarded_top10_replay_\d{4}-\d{2}-\d{2}\.json", json_output):
        errors.append("json output must stay under artifacts/research/guarded_top10_replay_YYYY-MM-DD.json")
    if not re.fullmatch(r"artifacts/research/guarded_top10_replay_\d{4}-\d{2}-\d{2}\.md", md_output):
        errors.append("markdown output must stay under artifacts/research/guarded_top10_replay_YYYY-MM-DD.md")
    if Path(str(artifact)).name.startswith("ranking_"):
        errors.append("artifact path must not be a production ranking csv")
    if not (PROJECT_ROOT / md_output).exists():
        errors.append(f"markdown output missing: {md_output}")

    top_n = int(summary.get("top_n") or 10)
    if len(top10) > top_n:
        errors.append("shadow_guarded_top10 exceeds top_n")
    if int(summary.get("candidate_pool_count") or 0) != CANDIDATE_POOL_SIZE_CONTRACT:
        errors.append(f"summary.candidate_pool_count must be {CANDIDATE_POOL_SIZE_CONTRACT}")
    if len(candidate_pool) != int(summary.get("candidate_pool_count") or len(candidate_pool)):
        errors.append("candidate_pool_count does not match candidate_pool_top80 length")
    if len(candidate_pool) != CANDIDATE_POOL_SIZE_CONTRACT:
        errors.append(f"candidate_pool_top80 length must be {CANDIDATE_POOL_SIZE_CONTRACT}")
    if any(int(item.get("candidate_rank") or 999999) > CANDIDATE_POOL_SIZE_CONTRACT for item in top10):
        errors.append("shadow Top10 contains a row outside candidate Top80")

    required = {"stock_id", "candidate_rank", "risk_adjusted_score", "tape_guard_action", "rr_guard_action", "risk_reward_score"}
    for index, item in enumerate(top10, start=1):
        missing = sorted(required - set(item))
        if missing:
            errors.append(f"top10 row {index} missing fields: {missing}")
        if str(item.get("tape_guard_action") or "") == "EXCLUDE" and int(summary.get("allowed_candidate_count") or 0) >= top_n:
            errors.append(f"top10 row {index} has EXCLUDE tape despite enough allowed candidates")

    scores = [to_float(item.get("risk_adjusted_score")) for item in top10]
    comparable = [score for score in scores if score is not None]
    if comparable != sorted(comparable, reverse=True):
        errors.append("shadow_guarded_top10 must be sorted by risk_adjusted_score descending")

    if summary.get("shadow_top_has_tape_exclude") and int(summary.get("allowed_candidate_count") or 0) >= top_n:
        errors.append("summary reports tape EXCLUDE in shadow top despite enough allowed candidates")
    return errors


def to_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


if __name__ == "__main__":
    raise SystemExit(main())
