#!/usr/bin/env python3
"""產出 BIG_BULL ranking-only shadow dry-run 比較報告。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "big-bull-ranking-only-shadow-dry-run.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build BIG_BULL ranking-only shadow dry-run report")
    parser.add_argument("--date", required=True)
    parser.add_argument("--production-dir", default="artifacts/backtest/historical_rankings_current_model")
    parser.add_argument("--shadow-dir", default="artifacts/backtest/shadow_rankings_big_bull")
    parser.add_argument("--industry-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument("--high-choppy-context", default="artifacts/model_experiments/high_choppy_context_overlay_2026-06-01.json")
    parser.add_argument("--auto13-decision", default="artifacts/model_experiments/big_bull_sealed_split_policy_ranking_only_decision_2026-06-01.json")
    parser.add_argument("--promotion-review", default="artifacts/model_experiments/model_promotion_review_big_bull_auto13_2026-06-01.json")
    parser.add_argument("--training-readiness", default="artifacts/training_automation_readiness_2026-06-01.json")
    parser.add_argument("--model", default="models/latest_lgbm.pkl")
    parser.add_argument("--model-hash-before", required=True)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--output", default=None)
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
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def directory_digest(path: Path, pattern: str = "ranking_*.csv") -> str:
    digest = hashlib.sha256()
    for item in sorted(path.glob(pattern)):
        digest.update(str(item.relative_to(path)).encode("utf-8"))
        digest.update(item.read_bytes())
    return digest.hexdigest()


def ranking_dates(path: Path) -> list[str]:
    return sorted(item.stem.removeprefix("ranking_") for item in path.glob("ranking_*.csv"))


def read_ranking(path: Path, top_n: int) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig").head(top_n).copy()
    frame["stock_id"] = frame["stock_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    frame["rank"] = range(1, len(frame) + 1)
    return frame


def read_industry_map(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=["stock_id", "industry_name", "sector_name"])
    frame = pd.read_csv(path, dtype={"stock_id": str})
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    return frame[["stock_id", "industry_name", "sector_name"]].drop_duplicates("stock_id")


def attach_sector(frame: pd.DataFrame, industry: pd.DataFrame) -> pd.DataFrame:
    result = frame.merge(industry, on="stock_id", how="left")
    result["sector_name"] = result["sector_name"].fillna("未分類")
    result["industry_name"] = result["industry_name"].fillna("未分類")
    return result


def top10_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    cols = ["rank", "stock_id", "stock_name", "risk_adjusted_score", "model_prob", "sector_name", "industry_name"]
    rows = []
    for row in frame[[col for col in cols if col in frame.columns]].to_dict("records"):
        rows.append({key: normalize_value(value) for key, value in row.items()})
    return rows


def normalize_value(value: Any) -> Any:
    if pd.isna(value):
        return None
    if isinstance(value, float):
        return round(value, 6)
    return value


def concentration(frame: pd.DataFrame) -> dict[str, Any]:
    if frame.empty:
        return {"max_sector": None, "max_share": None, "sector_counts": {}}
    counts = frame["sector_name"].fillna("未分類").value_counts().to_dict()
    max_sector, max_count = max(counts.items(), key=lambda item: item[1])
    return {
        "max_sector": max_sector,
        "max_share": round(max_count / len(frame), 6),
        "sector_counts": {str(key): int(value) for key, value in counts.items()},
    }


def compare_rankings(
    date_text: str,
    production: pd.DataFrame,
    shadow: pd.DataFrame,
    *,
    previous_production_ids: set[str] | None,
    previous_shadow_ids: set[str] | None,
    high_choppy: dict[str, set[str]],
) -> dict[str, Any]:
    production_ids = list(production["stock_id"])
    shadow_ids = list(shadow["stock_id"])
    production_set = set(production_ids)
    shadow_set = set(shadow_ids)
    overlap = sorted(production_set & shadow_set)
    added = [stock_id for stock_id in shadow_ids if stock_id not in production_set]
    removed = [stock_id for stock_id in production_ids if stock_id not in shadow_set]
    rank_changes = []
    prod_rank = dict(zip(production["stock_id"], production["rank"], strict=False))
    shadow_rank = dict(zip(shadow["stock_id"], shadow["rank"], strict=False))
    for stock_id in overlap:
        rank_changes.append(
            {
                "stock_id": stock_id,
                "production_rank": int(prod_rank[stock_id]),
                "shadow_rank": int(shadow_rank[stock_id]),
                "rank_delta_shadow_minus_production": int(shadow_rank[stock_id] - prod_rank[stock_id]),
            }
        )
    shadow_turnover = None if previous_shadow_ids is None else len(shadow_set - previous_shadow_ids)
    production_turnover = None if previous_production_ids is None else len(production_set - previous_production_ids)
    context = high_choppy_context_for_date(date_text, high_choppy)
    return {
        "date": date_text,
        "high_choppy_context": context,
        "shadow_top10": top10_rows(shadow),
        "production_top10": top10_rows(production),
        "comparison": {
            "overlap_count": len(overlap),
            "overlap_ratio": round(len(overlap) / max(len(shadow_set), 1), 6),
            "added_vs_production": added,
            "removed_vs_production": removed,
            "rank_changes": rank_changes,
        },
        "sector_concentration": {
            "shadow": concentration(shadow),
            "production": concentration(production),
        },
        "turnover": {
            "shadow_new_names_vs_previous_shadow": shadow_turnover,
            "production_new_names_vs_previous_production": production_turnover,
            "shadow_added_vs_production": len(added),
            "shadow_removed_vs_production": len(removed),
        },
    }


def high_choppy_context_for_date(date_text: str, high_choppy: dict[str, set[str]]) -> dict[str, bool]:
    return {
        "strict": date_text in high_choppy.get("strict", set()),
        "rolling_context": date_text in high_choppy.get("rolling_context", set()),
        "new": date_text in high_choppy.get("new", set()),
        "overlap": date_text in high_choppy.get("overlap", set()),
    }


def high_choppy_sets(payload: dict[str, Any]) -> dict[str, set[str]]:
    dates = payload.get("dates") if isinstance(payload.get("dates"), dict) else {}
    return {key: set(value or []) for key, value in dates.items()}


def summarize_dates(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    overlap = [row["comparison"]["overlap_count"] for row in rows]
    added = [row["turnover"]["shadow_added_vs_production"] for row in rows]
    shadow_turnover = [
        row["turnover"]["shadow_new_names_vs_previous_shadow"]
        for row in rows
        if row["turnover"]["shadow_new_names_vs_previous_shadow"] is not None
    ]
    return {
        "date_count": len(rows),
        "start_date": rows[0]["date"],
        "end_date": rows[-1]["date"],
        "avg_overlap_count": round(sum(overlap) / len(overlap), 6),
        "min_overlap_count": min(overlap),
        "avg_shadow_added_vs_production": round(sum(added) / len(added), 6),
        "avg_shadow_turnover_vs_previous": round(sum(shadow_turnover) / len(shadow_turnover), 6) if shadow_turnover else None,
    }


def summarize_high_choppy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups = {
        "rolling_context": [],
        "strict": [],
        "non_high_choppy": [],
    }
    for row in rows:
        context = row["high_choppy_context"]
        target = "non_high_choppy"
        if context["rolling_context"]:
            target = "rolling_context"
        if context["strict"]:
            target = "strict"
        groups[target].append(row)
    result = {}
    for key, items in groups.items():
        result[key] = {
            "date_count": len(items),
            "avg_overlap_count": round(sum(item["comparison"]["overlap_count"] for item in items) / len(items), 6) if items else None,
            "avg_shadow_added_vs_production": round(sum(item["turnover"]["shadow_added_vs_production"] for item in items) / len(items), 6) if items else None,
            "dates": [item["date"] for item in items],
        }
    return result


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    production_dir = resolve_path(args.production_dir)
    shadow_dir = resolve_path(args.shadow_dir)
    industry_path = resolve_path(args.industry_map)
    high_choppy_path = resolve_path(args.high_choppy_context)
    auto13_path = resolve_path(args.auto13_decision)
    promotion_path = resolve_path(args.promotion_review)
    readiness_path = resolve_path(args.training_readiness)
    model_path = resolve_path(args.model)
    required = {
        "production_dir": production_dir.exists(),
        "shadow_dir": shadow_dir.exists(),
        "industry_map": industry_path.exists(),
        "high_choppy_context": high_choppy_path.exists(),
        "auto13_decision": auto13_path.exists(),
        "promotion_review": promotion_path.exists(),
        "training_readiness": readiness_path.exists(),
        "model": model_path.exists(),
    }
    if not all(required.values()):
        missing = [name for name, ok in required.items() if not ok]
        return base_payload(args, "FAILED", errors=[f"missing required input: {name}"], required=required)

    production_digest_before = directory_digest(production_dir)
    model_hash_before_seen = sha256(model_path)
    auto13 = read_json(auto13_path)
    promotion = read_json(promotion_path)
    readiness = read_json(readiness_path)
    readiness_body = readiness.get("readiness") if isinstance(readiness.get("readiness"), dict) else readiness
    high_choppy = high_choppy_sets(read_json(high_choppy_path))
    industry = read_industry_map(industry_path)
    common_dates = sorted(set(ranking_dates(production_dir)) & set(ranking_dates(shadow_dir)))
    rows: list[dict[str, Any]] = []
    previous_production_ids: set[str] | None = None
    previous_shadow_ids: set[str] | None = None
    for date_text in common_dates:
        production = attach_sector(read_ranking(production_dir / f"ranking_{date_text}.csv", args.top_n), industry)
        shadow = attach_sector(read_ranking(shadow_dir / f"ranking_{date_text}.csv", args.top_n), industry)
        rows.append(
            compare_rankings(
                date_text,
                production,
                shadow,
                previous_production_ids=previous_production_ids,
                previous_shadow_ids=previous_shadow_ids,
                high_choppy=high_choppy,
            )
        )
        previous_production_ids = set(production["stock_id"])
        previous_shadow_ids = set(shadow["stock_id"])

    production_digest_after = directory_digest(production_dir)
    model_hash_after = sha256(model_path)
    production_changed = production_digest_before != production_digest_after
    model_changed = args.model_hash_before != model_hash_after or model_hash_before_seen != model_hash_after
    promotion_ready = bool(readiness_body.get("promotion_ready")) if readiness_body.get("promotion_ready") is not None else False
    ranking_only_ok = auto13.get("big_bull_family_only_decision") == "RANKING_ONLY_CANDIDATE" and auto13.get("ranking_only_allowed") is True
    guard = {
        "production_ranking_changed": production_changed,
        "risk_adjusted_score_changed": production_changed,
        "models_latest_changed": model_changed,
        "promotion_ready": promotion_ready,
        "production_message_changed": False,
        "formal_clawd_message_created": False,
        "promotion_adapter_status": promotion.get("status"),
        "auto13_ranking_only_allowed": ranking_only_ok,
    }
    errors = []
    if not rows:
        errors.append("no overlapping production/shadow ranking dates")
    if any(guard[key] for key in ["production_ranking_changed", "risk_adjusted_score_changed", "models_latest_changed", "promotion_ready"]):
        errors.append("production-adjacent guard failed")
    if promotion.get("status") != "LEDGER_EVIDENCE_BLOCKED":
        errors.append("promotion adapter is not blocked")
    if not ranking_only_ok:
        errors.append("AUTO13 does not allow ranking-only path")

    shadow_summary = summarize_dates(rows)
    high_choppy_summary = summarize_high_choppy(rows)
    checkpoint_a_passed = not errors
    return {
        **base_payload(args, "OK" if checkpoint_a_passed else "FAILED", errors=errors, required=required),
        "checkpoint": "A_SHADOW_DRY_RUN",
        "shadow_status": "READY_FOR_SHADOW_MONITOR" if checkpoint_a_passed else "FAILED",
        "shadow_dates": {
            "date_count": len(rows),
            "dates": [row["date"] for row in rows],
        },
        "production_comparison": {
            "production_dir": repo_path(production_dir),
            "shadow_dir": repo_path(shadow_dir),
            "summary": shadow_summary,
            "per_date": rows,
        },
        "overlap_summary": shadow_summary,
        "sector_concentration": {
            "max_shadow_sector_share": max((row["sector_concentration"]["shadow"]["max_share"] or 0 for row in rows), default=None),
            "max_production_sector_share": max((row["sector_concentration"]["production"]["max_share"] or 0 for row in rows), default=None),
            "per_date": [
                {
                    "date": row["date"],
                    "shadow": row["sector_concentration"]["shadow"],
                    "production": row["sector_concentration"]["production"],
                }
                for row in rows
            ],
        },
        "turnover": {
            "summary": {
                "avg_shadow_added_vs_production": shadow_summary.get("avg_shadow_added_vs_production"),
                "avg_shadow_turnover_vs_previous": shadow_summary.get("avg_shadow_turnover_vs_previous"),
            },
            "per_date": [{"date": row["date"], **row["turnover"]} for row in rows],
        },
        "high_choppy_stratified": high_choppy_summary,
        "guard_status": guard,
        "production_ranking_changed": guard["production_ranking_changed"],
        "risk_adjusted_score_changed": guard["risk_adjusted_score_changed"],
        "models_latest_changed": guard["models_latest_changed"],
        "promotion_ready": guard["promotion_ready"],
        "next_gate": "READY_FOR_SHADOW_MONITOR" if checkpoint_a_passed else "FAILED",
        "checkpoint_b": {
            "status": "NOT_STARTED",
            "entry_allowed": checkpoint_a_passed,
            "reason": "Checkpoint A must pass before continuous shadow monitor starts.",
        },
        "checkpoint_c": {
            "status": "NOT_STARTED",
            "entry_allowed": False,
            "reason": "Checkpoint B must pass before overlay proposal is review-ready.",
        },
        "hashes": {
            "production_ranking_before": production_digest_before,
            "production_ranking_after": production_digest_after,
            "model_hash_before_arg": args.model_hash_before,
            "model_hash_before_seen": model_hash_before_seen,
            "model_hash_after": model_hash_after,
        },
    }


def base_payload(args: argparse.Namespace, status: str, *, errors: list[str], required: dict[str, bool]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "contract": {
            "ranking_only_shadow_path": True,
            "does_not_write_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_create_formal_clawd_message": True,
            "does_not_output_promotion_ready": True,
            "checkpoint_a_required_before_b": True,
            "checkpoint_b_required_before_c": True,
            "checkpoint_c_proposal_only": True,
        },
        "required_inputs": required,
        "errors": errors,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# AUTO-TRAINING-14 BIG_BULL Ranking-Only Shadow Dry Run",
            "",
            f"- status: {payload.get('status')}",
            f"- checkpoint: {payload.get('checkpoint')}",
            f"- shadow_status: {payload.get('shadow_status')}",
            f"- shadow_dates: {payload.get('shadow_dates', {}).get('date_count')}",
            f"- avg_overlap_count: {payload.get('overlap_summary', {}).get('avg_overlap_count')}",
            f"- production_ranking_changed: {payload.get('production_ranking_changed')}",
            f"- risk_adjusted_score_changed: {payload.get('risk_adjusted_score_changed')}",
            f"- models_latest_changed: {payload.get('models_latest_changed')}",
            f"- promotion_ready: {payload.get('promotion_ready')}",
            f"- next_gate: {payload.get('next_gate')}",
            "",
            "## Errors",
            "",
            *[f"- {item}" for item in payload.get("errors", [])],
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"big_bull_ranking_only_shadow_dry_run_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload.get("status"), "output": repo_path(output), "next_gate": payload.get("next_gate")}, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
