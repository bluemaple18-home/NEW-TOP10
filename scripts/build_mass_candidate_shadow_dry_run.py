#!/usr/bin/env python3
"""產出 BATCH-01 survivor shadow dry-run 比較報告。"""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "mass-candidate-shadow-dry-run.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build mass candidate shadow dry-run report")
    parser.add_argument("--date", required=True)
    parser.add_argument("--production-dir", default="artifacts/backtest/historical_rankings_current_model")
    parser.add_argument("--industry-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument("--survivor-extension", default="artifacts/model_experiments/mass_candidate_survivor_replay_extension_2026-06-02.json")
    parser.add_argument("--high-choppy-context", default="artifacts/model_experiments/high_choppy_context_overlay_2026-06-01.json")
    parser.add_argument("--training-readiness", default="artifacts/training_automation_readiness_2026-06-02.json")
    parser.add_argument("--model", default="models/latest_lgbm.pkl")
    parser.add_argument("--model-hash-before", required=True)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument(
        "--candidate-set",
        choices=["survivor", "sector_cap"],
        default="survivor",
        help="survivor 使用第一輪 shadow dir；sector_cap 使用同族群 cap 後 shadow dir",
    )
    parser.add_argument("--concentration-column", default="sector_name", help="集中度檢查欄位；sector_cap 建議用 industry_name")
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


def read_json(path: str | Path) -> dict[str, Any]:
    resolved = resolve_path(path)
    if not resolved.exists():
        return {}
    return json.loads(resolved.read_text(encoding="utf-8"))


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
    keep = [col for col in ["stock_id", "industry_name", "sector_name"] if col in frame.columns]
    return frame[keep].drop_duplicates("stock_id")


def attach_sector(frame: pd.DataFrame, industry: pd.DataFrame) -> pd.DataFrame:
    result = frame.merge(industry, on="stock_id", how="left")
    result["sector_name"] = result.get("sector_name", "未分類").fillna("未分類")
    result["industry_name"] = result.get("industry_name", "未分類").fillna("未分類")
    return result


def concentration(frame: pd.DataFrame, column: str = "sector_name") -> dict[str, Any]:
    if frame.empty:
        return {"group_column": column, "max_group": None, "max_share": None, "group_counts": {}}
    group_values = frame[column] if column in frame.columns else frame.get("sector_name", pd.Series(["未分類"] * len(frame)))
    counts = group_values.fillna("未分類").value_counts().to_dict()
    max_group, max_count = max(counts.items(), key=lambda item: item[1])
    return {
        "group_column": column,
        "max_group": str(max_group),
        "max_share": round(max_count / len(frame), 6),
        "group_counts": {str(key): int(value) for key, value in counts.items()},
    }


def top_rows(frame: pd.DataFrame) -> list[dict[str, Any]]:
    cols = ["rank", "stock_id", "stock_name", "risk_adjusted_score", "model_prob", "sector_name", "industry_name"]
    rows = []
    for row in frame[[col for col in cols if col in frame.columns]].to_dict("records"):
        normalized = {}
        for key, value in row.items():
            if pd.isna(value):
                normalized[key] = None
            elif isinstance(value, float):
                normalized[key] = round(value, 6)
            else:
                normalized[key] = value
        rows.append(normalized)
    return rows


def high_choppy_sets(payload: dict[str, Any]) -> dict[str, set[str]]:
    dates = payload.get("dates") if isinstance(payload.get("dates"), dict) else {}
    return {key: set(value or []) for key, value in dates.items()}


def high_choppy_context(date_text: str, high_choppy: dict[str, set[str]]) -> dict[str, bool]:
    return {
        "strict": date_text in high_choppy.get("strict", set()),
        "rolling_context": date_text in high_choppy.get("rolling_context", set()),
        "new": date_text in high_choppy.get("new", set()),
        "overlap": date_text in high_choppy.get("overlap", set()),
    }


def compare_date(
    date_text: str,
    production: pd.DataFrame,
    shadow: pd.DataFrame,
    *,
    previous_production_ids: set[str] | None,
    previous_shadow_ids: set[str] | None,
    high_choppy: dict[str, set[str]],
    concentration_column: str,
) -> dict[str, Any]:
    production_ids = list(production["stock_id"])
    shadow_ids = list(shadow["stock_id"])
    production_set = set(production_ids)
    shadow_set = set(shadow_ids)
    overlap = sorted(production_set & shadow_set)
    added = [stock_id for stock_id in shadow_ids if stock_id not in production_set]
    removed = [stock_id for stock_id in production_ids if stock_id not in shadow_set]
    return {
        "date": date_text,
        "high_choppy_context": high_choppy_context(date_text, high_choppy),
        "shadow_top10": top_rows(shadow),
        "production_top10": top_rows(production),
        "comparison": {
            "overlap_count": len(overlap),
            "overlap_ratio": round(len(overlap) / max(len(shadow_set), 1), 6),
            "added_vs_production": added,
            "removed_vs_production": removed,
        },
        "sector_concentration": {
            "shadow": concentration(shadow, concentration_column),
            "production": concentration(production, concentration_column),
        },
        "turnover": {
            "shadow_new_names_vs_previous_shadow": None if previous_shadow_ids is None else len(shadow_set - previous_shadow_ids),
            "production_new_names_vs_previous_production": None if previous_production_ids is None else len(production_set - previous_production_ids),
            "shadow_added_vs_production": len(added),
            "shadow_removed_vs_production": len(removed),
        },
    }


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {}
    overlap = [row["comparison"]["overlap_count"] for row in rows]
    added = [row["turnover"]["shadow_added_vs_production"] for row in rows]
    turnover = [
        row["turnover"]["shadow_new_names_vs_previous_shadow"]
        for row in rows
        if row["turnover"]["shadow_new_names_vs_previous_shadow"] is not None
    ]
    max_shadow_sector = max((row["sector_concentration"]["shadow"]["max_share"] or 0 for row in rows), default=None)
    return {
        "date_count": len(rows),
        "start_date": rows[0]["date"],
        "end_date": rows[-1]["date"],
        "avg_overlap_count": round(sum(overlap) / len(overlap), 6),
        "min_overlap_count": min(overlap),
        "avg_shadow_added_vs_production": round(sum(added) / len(added), 6),
        "avg_shadow_turnover_vs_previous": round(sum(turnover) / len(turnover), 6) if turnover else None,
        "max_shadow_sector_share": max_shadow_sector,
    }


def summarize_high_choppy(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups = {"rolling_context": [], "strict": [], "non_high_choppy": []}
    for row in rows:
        context = row["high_choppy_context"]
        key = "non_high_choppy"
        if context["rolling_context"]:
            key = "rolling_context"
        if context["strict"]:
            key = "strict"
        groups[key].append(row)
    result = {}
    for key, items in groups.items():
        result[key] = {
            "date_count": len(items),
            "avg_overlap_count": round(sum(item["comparison"]["overlap_count"] for item in items) / len(items), 6) if items else None,
            "avg_shadow_added_vs_production": round(sum(item["turnover"]["shadow_added_vs_production"] for item in items) / len(items), 6) if items else None,
            "dates": [item["date"] for item in items],
        }
    return result


def candidate_dirs(candidate_set: str) -> dict[str, str]:
    if candidate_set == "sector_cap":
        return {
            "feature_group_ablation_by_regime_sector_cap": "artifacts/backtest/shadow_rankings_batch01_feature_group_sector_cap",
            "sector_industry_context_sector_cap": "artifacts/backtest/shadow_rankings_batch01_sector_context_sector_cap",
        }
    return {
        "feature_group_ablation_by_regime": "artifacts/backtest/shadow_rankings_regime_overlay_recent",
        "sector_industry_context": "artifacts/backtest/shadow_rankings_regime_guard_balanced_recent",
    }


def build_candidate(
    candidate_id: str,
    shadow_dir: Path,
    production_dir: Path,
    industry: pd.DataFrame,
    high_choppy: dict[str, set[str]],
    top_n: int,
    extension: dict[str, Any],
    concentration_column: str,
) -> dict[str, Any]:
    common_dates = sorted(set(ranking_dates(production_dir)) & set(ranking_dates(shadow_dir)))
    rows: list[dict[str, Any]] = []
    previous_production_ids: set[str] | None = None
    previous_shadow_ids: set[str] | None = None
    for date_text in common_dates:
        production = attach_sector(read_ranking(production_dir / f"ranking_{date_text}.csv", top_n), industry)
        shadow = attach_sector(read_ranking(shadow_dir / f"ranking_{date_text}.csv", top_n), industry)
        rows.append(
            compare_date(
                date_text,
                production,
                shadow,
                previous_production_ids=previous_production_ids,
                previous_shadow_ids=previous_shadow_ids,
                high_choppy=high_choppy,
                concentration_column=concentration_column,
            )
        )
        previous_production_ids = set(production["stock_id"])
        previous_shadow_ids = set(shadow["stock_id"])

    extension_candidate = next(
        (row for row in extension.get("candidates", []) if row.get("candidate_id") == candidate_id),
        {},
    )
    summary = summarize_rows(rows)
    max_sector_share = float(summary.get("max_shadow_sector_share") or 0)
    avg_overlap = float(summary.get("avg_overlap_count") or 0)
    allowed_extension_decisions = {"SURVIVED_FOR_SHADOW_DRY_RUN", "SURVIVED_FOR_SHADOW_MONITOR"}
    if extension_candidate.get("decision") not in allowed_extension_decisions:
        decision = "BLOCKED_CONTRACT"
        next_gate = "BLOCKED"
        reason = "Survivor replay extension did not allow shadow dry-run."
    elif max_sector_share > 0.75:
        decision = "RESTRICTED_SHADOW_ONLY"
        next_gate = "RESTRICTED_SHADOW_ONLY"
        reason = "Shadow dry-run passed replay extension but sector concentration is too high for overlay."
    elif avg_overlap < 1.0:
        decision = "RESTRICTED_SHADOW_ONLY"
        next_gate = "RESTRICTED_SHADOW_ONLY"
        reason = "Shadow pool is materially different from production; keep restricted monitor before overlay."
    else:
        decision = "READY_FOR_SHADOW_MONITOR"
        next_gate = "READY_FOR_SHADOW_MONITOR"
        reason = "Shadow dry-run guard passed; candidate can enter monitor."
    return {
        "candidate_id": candidate_id,
        "shadow_dir": repo_path(shadow_dir),
        "shadow_status": decision,
        "next_gate": next_gate,
        "reason": reason,
        "shadow_dates": {"date_count": len(rows), "dates": [row["date"] for row in rows]},
        "overlap_summary": summary,
        "sector_concentration": {
            "max_shadow_sector_share": summary.get("max_shadow_sector_share"),
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
                "avg_shadow_added_vs_production": summary.get("avg_shadow_added_vs_production"),
                "avg_shadow_turnover_vs_previous": summary.get("avg_shadow_turnover_vs_previous"),
            },
            "per_date": [{"date": row["date"], **row["turnover"]} for row in rows],
        },
        "high_choppy_stratified": summarize_high_choppy(rows),
        "extension_evidence": {
            "decision": extension_candidate.get("decision"),
            "replay_compounded_delta": extension_candidate.get("replay_compounded_delta"),
            "top10_portfolio_delta": ((extension_candidate.get("topn_portfolio") or {}).get("top10") or {}).get("total_return_delta"),
        },
        "per_date": rows,
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    production_dir = resolve_path(args.production_dir)
    industry_path = resolve_path(args.industry_map)
    model_path = resolve_path(args.model)
    extension_path = resolve_path(args.survivor_extension)
    high_choppy_path = resolve_path(args.high_choppy_context)
    readiness_path = resolve_path(args.training_readiness)
    required = {
        "production_dir": production_dir.exists(),
        "industry_map": industry_path.exists(),
        "model": model_path.exists(),
        "survivor_extension": extension_path.exists(),
        "high_choppy_context": high_choppy_path.exists(),
        "training_readiness": readiness_path.exists(),
    }
    missing = [name for name, ok in required.items() if not ok]
    if missing:
        return base_payload(args, "FAILED", errors=[f"missing required input: {name}" for name in missing], required=required)

    production_digest_before = directory_digest(production_dir)
    model_hash_seen = sha256(model_path)
    extension = read_json(extension_path)
    high_choppy = high_choppy_sets(read_json(high_choppy_path))
    readiness = read_json(readiness_path)
    readiness_body = readiness.get("readiness") if isinstance(readiness.get("readiness"), dict) else readiness
    industry = read_industry_map(industry_path)
    candidates = []
    errors = []
    for candidate_id, shadow_dir_text in candidate_dirs(args.candidate_set).items():
        shadow_dir = resolve_path(shadow_dir_text)
        if not shadow_dir.exists():
            errors.append(f"missing shadow dir for {candidate_id}: {shadow_dir_text}")
            continue
        candidates.append(
            build_candidate(
                candidate_id,
                shadow_dir,
                production_dir,
                industry,
                high_choppy,
                args.top_n,
                extension,
                args.concentration_column,
            )
        )

    production_digest_after = directory_digest(production_dir)
    model_hash_after = sha256(model_path)
    promotion_ready = bool(readiness_body.get("promotion_ready")) if readiness_body.get("promotion_ready") is not None else False
    guard = {
        "production_ranking_changed": production_digest_before != production_digest_after,
        "risk_adjusted_score_changed": production_digest_before != production_digest_after,
        "models_latest_changed": args.model_hash_before != model_hash_after or model_hash_seen != model_hash_after,
        "model_hash_before_arg": args.model_hash_before,
        "model_hash_seen": model_hash_seen,
        "model_hash_after": model_hash_after,
        "formal_clawd_message_created": False,
        "promotion_ready": promotion_ready,
    }
    if any(guard[key] for key in ["production_ranking_changed", "risk_adjusted_score_changed", "models_latest_changed", "promotion_ready"]):
        errors.append("production guard failed")
    counts: dict[str, int] = {}
    for item in candidates:
        counts[item["shadow_status"]] = counts.get(item["shadow_status"], 0) + 1
    return {
        **base_payload(args, "OK" if not errors else "FAILED", errors=errors, required=required),
        "checkpoint": "BATCH_SURVIVOR_SHADOW_DRY_RUN",
        "summary": {
            "candidates_tested": len(candidates),
            "status_counts": counts,
            "ready_for_shadow_monitor": counts.get("READY_FOR_SHADOW_MONITOR", 0),
            "restricted_shadow_only": counts.get("RESTRICTED_SHADOW_ONLY", 0),
            "best_next_step": "READY candidates can enter shadow monitor; restricted candidates remain monitor-only.",
        },
        "candidates": candidates,
        "guard_status": guard,
        "production_ranking_changed": guard["production_ranking_changed"],
        "risk_adjusted_score_changed": guard["risk_adjusted_score_changed"],
        "models_latest_changed": guard["models_latest_changed"],
        "promotion_ready": guard["promotion_ready"],
        "next_gate": "SHADOW_MONITOR_FOR_READY_ONLY" if counts.get("READY_FOR_SHADOW_MONITOR", 0) else "RESTRICTED_OR_MONITOR_ONLY",
    }


def base_payload(args: argparse.Namespace, status: str, *, errors: list[str], required: dict[str, bool]) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "contract": {
            "shadow_dry_run_only": True,
            "does_not_write_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_create_formal_clawd_message": True,
            "does_not_output_promotion_ready": True,
            "candidate_set": args.candidate_set,
            "concentration_column": args.concentration_column,
        },
        "required_inputs": required,
        "errors": errors,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# BATCH-01 Survivor Shadow Dry Run",
        "",
        f"- status: {payload.get('status')}",
        f"- checkpoint: {payload.get('checkpoint')}",
        f"- candidates_tested: {payload.get('summary', {}).get('candidates_tested')}",
        f"- ready_for_shadow_monitor: {payload.get('summary', {}).get('ready_for_shadow_monitor')}",
        f"- restricted_shadow_only: {payload.get('summary', {}).get('restricted_shadow_only')}",
        f"- production_ranking_changed: {payload.get('production_ranking_changed')}",
        f"- risk_adjusted_score_changed: {payload.get('risk_adjusted_score_changed')}",
        f"- models_latest_changed: {payload.get('models_latest_changed')}",
        f"- promotion_ready: {payload.get('promotion_ready')}",
        f"- next_gate: {payload.get('next_gate')}",
        "",
        "## Candidates",
        "",
        "| Candidate | Status | Dates | Avg Overlap | Max Sector | Replay Delta | Top10 Portfolio Delta |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for item in payload.get("candidates", []):
        ext = item.get("extension_evidence", {})
        lines.append(
            "| {candidate_id} | {status} | {dates} | {overlap} | {sector} | {replay_delta:.2%} | {portfolio_delta:.2%} |".format(
                candidate_id=item.get("candidate_id"),
                status=item.get("shadow_status"),
                dates=item.get("shadow_dates", {}).get("date_count"),
                overlap=item.get("overlap_summary", {}).get("avg_overlap_count"),
                sector=(item.get("overlap_summary", {}).get("max_shadow_sector_share") or 0),
                replay_delta=float(ext.get("replay_compounded_delta") or 0),
                portfolio_delta=float(ext.get("top10_portfolio_delta") or 0),
            )
        )
    lines.extend(["", "## Reasons", ""])
    for item in payload.get("candidates", []):
        lines.append(f"- {item.get('candidate_id')}: {item.get('reason')}")
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- {item}" for item in payload.get("errors", [])])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / "model_experiments" / f"mass_candidate_shadow_dry_run_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload.get("status"), "output": repo_path(output), "next_gate": payload.get("next_gate")}, ensure_ascii=False, sort_keys=True))
    return 0 if payload.get("status") == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
