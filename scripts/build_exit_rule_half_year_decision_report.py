#!/usr/bin/env python3
"""整理近半年固定 100 股出場規則決策報告。

目標是把「每天 Top10、每檔買 100 股」的半年度結果轉成操作層候選。
此報告只讀既有 fixed-share hypothesis matrix，不訓練模型、不改 ranking。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "exit-rule-half-year-decision-report.v1"
MODEL_SHA256 = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


WATCH_POLICIES = [
    "fixed_20d",
    "fixed_30d",
    "fixed_40d",
    "h30_early_tp07",
    "h40_early_tp07",
    "h30_early_tp12",
    "h40_early_tp12",
    "h30_early_tp15",
    "h40_early_tp15",
    "h30_tp18_sl08",
    "h30_tp25_sl10",
    "h30_trail10",
    "h40_trail12",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build exit rule half-year decision report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--matrix", default="artifacts/backtest/fixed_share_hypothesis_matrix_production_half_year_2026-06-02.json")
    parser.add_argument("--manifest", default="artifacts/backtest/historical_rankings_current_model_half_year_dense_2025-11-17_2026-05-15/manifest.json")
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
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def pct(value: Any) -> str:
    return f"{n(value):.2%}"


def compact_policy(label: str, row: dict[str, Any]) -> dict[str, Any]:
    return {
        "policy": label,
        "trade_count": row.get("trade_count"),
        "ranking_day_count": row.get("ranking_day_count"),
        "return_on_buy_cash": row.get("return_on_buy_cash"),
        "win_rate": row.get("win_rate"),
        "avg_trade_net_return": row.get("avg_trade_net_return"),
        "median_trade_net_return": row.get("median_trade_net_return"),
        "avg_mae": row.get("avg_mae"),
        "worst_mae": row.get("worst_mae"),
        "avg_mfe": row.get("avg_mfe"),
        "avg_giveback": row.get("avg_giveback"),
        "p90_giveback": row.get("p90_giveback"),
    }


def deltas(row: dict[str, Any], baseline: dict[str, Any]) -> dict[str, Any]:
    return {
        "return_delta": round(n(row.get("return_on_buy_cash")) - n(baseline.get("return_on_buy_cash")), 6),
        "win_rate_delta": round(n(row.get("win_rate")) - n(baseline.get("win_rate")), 6),
        "avg_mae_delta": round(n(row.get("avg_mae")) - n(baseline.get("avg_mae")), 6),
        "worst_mae_delta": round(n(row.get("worst_mae")) - n(baseline.get("worst_mae")), 6),
        "p90_giveback_delta": round(n(row.get("p90_giveback")) - n(baseline.get("p90_giveback")), 6),
    }


def score_policy(row: dict[str, Any]) -> float:
    # 這是排序用的透明綜合分數，不是 production 權重。
    return (
        n(row.get("return_on_buy_cash")) * 1.0
        + n(row.get("win_rate")) * 0.08
        + n(row.get("worst_mae")) * 0.35
        - n(row.get("p90_giveback")) * 0.18
    )


def choose_candidates(policies: dict[str, dict[str, Any]]) -> dict[str, Any]:
    fixed40 = policies["fixed_40d"]
    early_tp07 = policies["h40_early_tp07"]
    early_tp15 = policies["h40_early_tp15"]
    stop_take = policies["h30_tp25_sl10"]
    candidates = [policies[key] for key in policies if key not in {"fixed_20d", "fixed_30d", "fixed_40d"}]
    ranked = sorted(candidates, key=score_policy, reverse=True)
    return {
        "highest_return_baseline": "fixed_40d",
        "primary_balanced_candidate": "h40_early_tp15",
        "defensive_candidate": "h30_tp25_sl10",
        "reject_early_tp07": True,
        "reject_reason_early_tp07": "7% 早停利勝率很高，但在近半年牛市太早把波段砍掉。",
        "baseline_warning": (
            "fixed_40d 報酬最高，但 worst MAE 與 p90 giveback 太大，不符合小白使用者的風險感受。"
            if n(fixed40.get("worst_mae")) < -0.5
            else "fixed_40d 可保留為高風險參考。"
        ),
        "early_tp07_vs_early_tp15": deltas(early_tp07, early_tp15),
        "early_tp15_vs_fixed40": deltas(early_tp15, fixed40),
        "stop_take_vs_fixed40": deltas(stop_take, fixed40),
        "ranked_candidates": [{"policy": row["policy"], "score": round(score_policy(row), 6)} for row in ranked[:8]],
    }


def compact_manifest(path: Path) -> dict[str, Any]:
    manifest = read_json(path)
    rankings = (manifest.get("outputs") or {}).get("rankings") or [{}]
    return {
        "path": repo_path(path),
        "status": manifest.get("status"),
        "ranking_count": (manifest.get("outputs") or {}).get("ranking_count"),
        "first_date": rankings[0].get("date"),
        "last_date": rankings[-1].get("date"),
        "failure_count": len(manifest.get("failures") or []),
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    matrix_path = resolve_path(args.matrix)
    manifest_path = resolve_path(args.manifest)
    matrix = read_json(matrix_path)
    exit_policy = (matrix.get("matrix") or {}).get("exit_policy") or {}
    policies = {key: compact_policy(key, exit_policy.get(key) or {}) for key in WATCH_POLICIES}
    fixed40 = policies["fixed_40d"]
    comparisons = {key: deltas(row, fixed40) for key, row in policies.items() if key != "fixed_40d"}
    missing = [key for key, row in policies.items() if not row.get("trade_count")]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if not missing else "MISSING_INPUT",
        "contract": {
            "research_only": True,
            "fixed_100_share_backtest": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_clawd_message": True,
            "production_default_allowed": False,
            "model_sha256": MODEL_SHA256,
        },
        "inputs": {
            "matrix": repo_path(matrix_path),
            "manifest": compact_manifest(manifest_path),
            "source_matrix_contract": matrix.get("contract") or {},
        },
        "summary": {
            "decision": "EXIT_RULE_RESEARCH_SELECTS_BALANCED_CANDIDATE",
            "primary_candidate": "h40_early_tp15",
            "defensive_candidate": "h30_tp25_sl10",
            "rejected": ["h30_early_tp07", "h40_early_tp07"],
            "next_gate": "PORTFOLIO_LEVEL_REPLAY_FOR_H40_EARLY_TP15_AND_H30_TP25_SL10",
        },
        "candidate_decision": choose_candidates(policies),
        "policies": policies,
        "comparisons_vs_fixed40": comparisons,
        "missing": missing,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    policies = payload["policies"]
    comparisons = payload["comparisons_vs_fixed40"]
    lines = [
        "# Exit Rule Half-Year Decision Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['summary']['decision']}`",
        f"- primary_candidate: `{payload['summary']['primary_candidate']}`",
        f"- defensive_candidate: `{payload['summary']['defensive_candidate']}`",
        f"- next_gate: `{payload['summary']['next_gate']}`",
        "",
        "## Key Policies",
        "",
        "| Policy | Return | Win | Avg MAE | Worst MAE | P90 Giveback | Δ Return vs fixed40 | Δ Worst MAE |",
        "|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for key in ["fixed_40d", "h40_early_tp07", "h40_early_tp15", "h30_tp25_sl10", "h30_tp18_sl08", "h40_trail12"]:
        row = policies[key]
        comp = comparisons.get(key) or {}
        lines.append(
            "| {policy} | {ret} | {win} | {mae} | {worst} | {giveback} | {dret} | {dworst} |".format(
                policy=key,
                ret=pct(row.get("return_on_buy_cash")),
                win=pct(row.get("win_rate")),
                mae=pct(row.get("avg_mae")),
                worst=pct(row.get("worst_mae")),
                giveback=pct(row.get("p90_giveback")),
                dret=pct(comp.get("return_delta")) if comp else "--",
                dworst=pct(comp.get("worst_mae_delta")) if comp else "--",
            )
        )
    lines.extend(
        [
            "",
            "## Decision Notes",
            "",
            f"- {payload['candidate_decision']['baseline_warning']}",
            f"- {payload['candidate_decision']['reject_reason_early_tp07']}",
            "- `h40_early_tp15` 是主要候選：保留較多牛市波段，同時降低回吐與極端 MAE。",
            "- `h30_tp25_sl10` 是防守候選：犧牲勝率，但把 worst MAE 壓得更低。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"exit_rule_half_year_decision_report_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
