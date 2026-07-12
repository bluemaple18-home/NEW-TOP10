#!/usr/bin/env python3
"""輸出 VWAP regime-gated Top10 ranking 研究目錄。

輸入 Top50 候選 ranking CSV；只有指定盤勢套 VWAP overlay，其餘維持原始前 10 名。
此腳本只寫 research output-dir，不改 production ranking。
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import run_backtest_replay
from scripts.research_vwap_entry_quality_replay import POLICIES, load_feature_lookup, load_regime_map, score_item


PLANS: dict[str, dict[str, str]] = {
    "nl_panic_balanced": {
        "NARROW_LEADER": "balanced_cost_basis",
        "PANIC_SELLING": "balanced_cost_basis",
    },
    "nl_panic_avoid5": {
        "NARROW_LEADER": "avoid_extended_vwap_5d",
        "PANIC_SELLING": "avoid_extended_vwap_5d",
    },
    "narrow_only_balanced": {
        "NARROW_LEADER": "balanced_cost_basis",
    },
    "panic_only_balanced": {
        "PANIC_SELLING": "balanced_cost_basis",
    },
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="materialize VWAP regime-gated research rankings")
    parser.add_argument("--source-rankings-dir", default="artifacts/research_rankings/current_model_top50_long_2025-01-02_2026-05-15")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--plan", default="nl_panic_balanced", choices=sorted(PLANS))
    parser.add_argument("--candidate-pool", type=int, default=50)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--output-dir", default=None)
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


def read_rows(path: Path, candidate_pool: int) -> tuple[list[dict[str, Any]], list[str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])
    for index, row in enumerate(rows, start=1):
        row["stock_id"] = str(row.get("stock_id", "")).strip().zfill(4)
        row["_source_rank"] = index
    return rows[:candidate_pool], fieldnames


def item_for_score(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "stock_id": row.get("stock_id"),
        "risk_adjusted_score": parse_float(row.get("risk_adjusted_score")),
        "model_prob": parse_float(row.get("model_prob")),
    }


def parse_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def select_rows(
    rows: list[dict[str, Any]],
    date_text: str,
    regime: str,
    plan: str,
    feature_lookup: dict[tuple[str, str], dict[str, Any]],
    top_n: int,
) -> tuple[list[dict[str, Any]], str]:
    policy_name = PLANS[plan].get(regime, "baseline")
    if policy_name == "baseline":
        selected = rows[:top_n]
        for row in selected:
            row["_overlay_score"] = ""
        return selected, policy_name
    policy = POLICIES[policy_name]
    scored = []
    for row in rows:
        features = feature_lookup.get((date_text, str(row.get("stock_id", "")).zfill(4)))
        overlay_score, reason = score_item(item_for_score(row), features, policy)
        scored.append((overlay_score, reason, row))
    selected_rows = []
    for overlay_score, reason, row in sorted(scored, key=lambda item: item[0], reverse=True)[:top_n]:
        row["_overlay_score"] = round(float(overlay_score), 8)
        row["_overlay_reason"] = reason
        selected_rows.append(row)
    return selected_rows, policy_name


def write_ranking(path: Path, rows: list[dict[str, Any]], source_fieldnames: list[str], regime: str, plan: str, policy_name: str) -> None:
    extra_fields = ["vwap_gated_plan", "vwap_selected_policy", "vwap_source_rank", "vwap_overlay_score", "vwap_overlay_reason", "shadow_market_regime"]
    fieldnames = [field for field in source_fieldnames if not field.startswith("_")]
    for field in extra_fields:
        if field not in fieldnames:
            fieldnames.append(field)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for rank, row in enumerate(rows, start=1):
            out = dict(row)
            out["rank"] = rank
            out["vwap_gated_plan"] = plan
            out["vwap_selected_policy"] = policy_name
            out["vwap_source_rank"] = row.get("_source_rank")
            out["vwap_overlay_score"] = row.get("_overlay_score", "")
            out["vwap_overlay_reason"] = row.get("_overlay_reason", "")
            out["shadow_market_regime"] = regime
            writer.writerow(out)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    source_dir = resolve_path(args.source_rankings_dir)
    features_path = resolve_path(args.features)
    regime_path = resolve_path(args.market_regime_history)
    output_dir = resolve_path(args.output_dir) or PROJECT_ROOT / "artifacts" / "research_rankings" / f"vwap_{args.plan}_top10_{args.date}"
    assert source_dir is not None and features_path is not None and regime_path is not None and output_dir is not None
    if args.top_n < 1 or args.candidate_pool < args.top_n:
        raise ValueError("--candidate-pool 必須 >= --top-n 且 --top-n > 0")
    output_dir.mkdir(parents=True, exist_ok=True)
    feature_lookup = load_feature_lookup(features_path)
    regime_map = load_regime_map(regime_path)
    files = run_backtest_replay.ranking_files(source_dir, None)
    outputs = []
    policy_counts: dict[str, int] = {}
    regime_counts: dict[str, int] = {}
    for source_path in files:
        date_text = run_backtest_replay.ranking_date(source_path)
        regime = regime_map.get(date_text, "UNKNOWN")
        rows, fieldnames = read_rows(source_path, args.candidate_pool)
        selected, policy_name = select_rows(rows, date_text, regime, args.plan, feature_lookup, args.top_n)
        output_path = output_dir / source_path.name
        write_ranking(output_path, selected, fieldnames, regime, args.plan, policy_name)
        outputs.append({"date": date_text, "path": repo_path(output_path), "regime": regime, "policy": policy_name})
        policy_counts[policy_name] = policy_counts.get(policy_name, 0) + 1
        regime_counts[regime] = regime_counts.get(regime, 0) + 1
    manifest = {
        "schema_version": "vwap-regime-gated-rankings.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "contract": {
            "research_only": True,
            "reads_formal_features_parquet": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_ready": False,
        },
        "inputs": {
            "source_rankings_dir": repo_path(source_dir),
            "features": repo_path(features_path),
            "market_regime_history": repo_path(regime_path),
            "plan": args.plan,
            "candidate_pool": args.candidate_pool,
            "top_n": args.top_n,
        },
        "outputs": {
            "output_dir": repo_path(output_dir),
            "ranking_count": len(outputs),
            "rankings": outputs,
        },
        "summary": {"policy_counts": policy_counts, "regime_counts": regime_counts},
    }
    (output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return manifest


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    print(
        json.dumps(
            {
                "status": "OK",
                "output_dir": payload["outputs"]["output_dir"],
                "ranking_count": payload["outputs"]["ranking_count"],
                "summary": payload["summary"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
