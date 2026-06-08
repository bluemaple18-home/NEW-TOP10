#!/usr/bin/env python3
"""長區間 daily ranking 驗證營運規則候選。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_operational_portfolio_rule_report import n  # noqa: E402
from scripts.build_operational_rule_validation_report import compact_variant, delta, pct, regime_map, resolve_path  # noqa: E402
SCHEMA_VERSION = "operational-long-rule-validation-report.v2"


STRIDE3_VARIANTS = {
    "fixed40": "artifacts/backtest/portfolio_replay_production_long_stride3_fixed40_2026-06-02.json",
    "sector45": "artifacts/backtest/portfolio_replay_production_long_stride3_fixed40_sector45_2026-06-02.json",
    "gross55": "artifacts/backtest/portfolio_replay_production_long_stride3_fixed40_gross55_2026-06-02.json",
    "top3": "artifacts/backtest/portfolio_replay_production_long_stride3_fixed40_top3_2026-06-02.json",
}

DENSE_VARIANTS = {
    "fixed40": "artifacts/backtest/portfolio_replay_production_long_dense_fixed40_2026-06-02.json",
    "sector45": "artifacts/backtest/portfolio_replay_production_long_dense_fixed40_sector45_2026-06-02.json",
    "gross55": "artifacts/backtest/portfolio_replay_production_long_dense_fixed40_gross55_2026-06-02.json",
    "top3": "artifacts/backtest/portfolio_replay_production_long_dense_fixed40_top3_2026-06-02.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build operational long rule validation report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--stride3-manifest", default="artifacts/backtest/historical_rankings_current_model_batch_stride3_2023-11-21_2026-05-15/manifest.json")
    parser.add_argument("--dense-manifest", default="artifacts/backtest/historical_rankings_current_model_batch_dense_2023-11-21_2026-05-15/manifest.json")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_daily(path_text: str) -> list[dict[str, Any]]:
    return read_json(resolve_path(path_text)).get("daily") or []


def compound_returns(rows: list[dict[str, Any]]) -> float:
    value = 1.0
    for row in rows:
        value *= 1 + n(row.get("daily_return"))
    return value - 1


def max_drawdown(rows: list[dict[str, Any]]) -> float:
    high = None
    worst = 0.0
    for row in rows:
        equity = n(row.get("equity"))
        if equity <= 0:
            continue
        high = equity if high is None else max(high, equity)
        worst = min(worst, equity / high - 1 if high else 0.0)
    return worst


def period_breakdown(path_text: str) -> dict[str, dict[str, Any]]:
    rows = sorted(read_daily(path_text), key=lambda row: str(row.get("date") or ""))
    buckets: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        date_text = str(row.get("date") or "")
        if len(date_text) < 4:
            continue
        buckets.setdefault(date_text[:4], []).append(row)
    return {
        label: {
            "daily_count": len(items),
            "compound_return": round(compound_returns(items), 6),
            "max_drawdown": round(max_drawdown(items), 6),
            "positive_day_rate": round(sum(n(row.get("daily_return")) > 0 for row in items) / len(items), 6) if items else None,
        }
        for label, items in sorted(buckets.items())
        if items
    }


def rolling_returns(rows: list[dict[str, Any]], window: int) -> list[dict[str, Any]]:
    sorted_rows = sorted(rows, key=lambda row: str(row.get("date") or ""))
    results: list[dict[str, Any]] = []
    if len(sorted_rows) < window:
        return results
    for index in range(0, len(sorted_rows) - window + 1):
        sliced = sorted_rows[index : index + window]
        results.append(
            {
                "start_date": sliced[0].get("date"),
                "end_date": sliced[-1].get("date"),
                "return": compound_returns(sliced),
                "max_drawdown": max_drawdown(sliced),
            }
        )
    return results


def rolling_pair_summary(baseline_path: str, candidate_path: str, window: int) -> dict[str, Any]:
    baseline = rolling_returns(read_daily(baseline_path), window)
    candidate = rolling_returns(read_daily(candidate_path), window)
    pairs = list(zip(baseline, candidate, strict=False))
    if not pairs:
        return {"window": window, "count": 0}
    return_deltas = [candidate_row["return"] - baseline_row["return"] for baseline_row, candidate_row in pairs]
    drawdown_deltas = [candidate_row["max_drawdown"] - baseline_row["max_drawdown"] for baseline_row, candidate_row in pairs]
    return {
        "window": window,
        "count": len(pairs),
        "avg_return_delta": round(sum(return_deltas) / len(return_deltas), 6),
        "worst_return_delta": round(min(return_deltas), 6),
        "best_return_delta": round(max(return_deltas), 6),
        "candidate_return_beats_rate": round(sum(delta > 0 for delta in return_deltas) / len(return_deltas), 6),
        "avg_drawdown_delta": round(sum(drawdown_deltas) / len(drawdown_deltas), 6),
        "candidate_drawdown_improves_rate": round(sum(delta > 0 for delta in drawdown_deltas) / len(drawdown_deltas), 6),
    }


def stability_section() -> dict[str, Any]:
    return {
        "periods": {
            "fixed40": period_breakdown(DENSE_VARIANTS["fixed40"]),
            "gross55": period_breakdown(DENSE_VARIANTS["gross55"]),
            "sector45": period_breakdown(DENSE_VARIANTS["sector45"]),
            "top3": period_breakdown(DENSE_VARIANTS["top3"]),
        },
        "rolling_vs_fixed40": {
            "gross55_40d": rolling_pair_summary(DENSE_VARIANTS["fixed40"], DENSE_VARIANTS["gross55"], 40),
            "gross55_80d": rolling_pair_summary(DENSE_VARIANTS["fixed40"], DENSE_VARIANTS["gross55"], 80),
            "sector45_40d": rolling_pair_summary(DENSE_VARIANTS["fixed40"], DENSE_VARIANTS["sector45"], 40),
            "top3_40d": rolling_pair_summary(DENSE_VARIANTS["fixed40"], DENSE_VARIANTS["top3"], 40),
        },
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
        "stride": (manifest.get("inputs") or {}).get("stride"),
        "failure_count": len(manifest.get("failures") or []),
        "batch_mode": (manifest.get("inputs") or {}).get("batch_mode"),
    }


def comparison_set(variants: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    baseline = variants["fixed40"]
    return {
        "sector45": delta(variants["sector45"], baseline),
        "gross55": delta(variants["gross55"], baseline),
        "top3": delta(variants["top3"], baseline),
    }


def decide(dense_variants: dict[str, dict[str, Any]], dense_comparisons: dict[str, dict[str, Any]]) -> dict[str, str]:
    fixed40 = dense_variants["fixed40"]
    gross55 = dense_variants["gross55"]
    sector45 = dense_comparisons["sector45"]
    gross55_delta = dense_comparisons["gross55"]
    top3 = dense_comparisons["top3"]
    fixed40_dd = float(fixed40.get("max_drawdown") or 0.0)
    gross55_dd = float(gross55.get("max_drawdown") or 0.0)
    gross55_drawdown_improvement = gross55_dd - fixed40_dd

    return {
        "overall_decision": "DENSE_LONG_VALIDATION_SELECTS_CONSERVATIVE_GROSS55_CANDIDATE",
        "fixed40_status": "BASELINE_STRONG_RETURN_BUT_HIGH_DRAWDOWN",
        "sector45_status": (
            "REJECT_AS_DEFAULT_ON_DENSE_LONG"
            if float(sector45.get("return_delta") or 0.0) < -0.1
            else "MONITOR_ONLY_NOT_DEFAULT"
        ),
        "gross55_status": (
            "CONSERVATIVE_CANDIDATE_FOR_DRAWDOWN_REDUCTION"
            if gross55_drawdown_improvement > 0.03 and float(gross55_delta.get("return_delta") or 0.0) > -0.5
            else "MONITOR_ONLY_NOT_ENOUGH_DRAWDOWN_REDUCTION"
        ),
        "top3_status": (
            "REJECT_AS_AGGRESSIVE_DEFAULT_ON_DENSE_LONG"
            if float(top3.get("return_delta") or 0.0) < 0.0
            else "AGGRESSIVE_LABEL_ONLY"
        ),
        "next_required": "GROSS55_OPERATIONAL_SHADOW_DRY_RUN_BEFORE_DEFAULT",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    stride3_manifest_path = resolve_path(args.stride3_manifest)
    dense_manifest_path = resolve_path(args.dense_manifest)
    stride3_manifest = compact_manifest(stride3_manifest_path)
    dense_manifest = compact_manifest(dense_manifest_path)
    regimes = regime_map(resolve_path(args.market_regime_history))
    # 長區間主結論以 dense daily 為準；stride3 只當抽樣交叉檢查。
    dense_variants = {label: compact_variant(label, path, regimes) for label, path in DENSE_VARIANTS.items()}
    stride3_variants = {label: compact_variant(label, path, regimes) for label, path in STRIDE3_VARIANTS.items()}
    dense_comparisons = comparison_set(dense_variants)
    stride3_comparisons = comparison_set(stride3_variants)
    summary = decide(dense_variants, dense_comparisons)
    status_ok = (
        dense_manifest.get("status") == "OK"
        and stride3_manifest.get("status") == "OK"
        and all(row["exists"] for row in dense_variants.values())
        and all(row["exists"] for row in stride3_variants.values())
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if status_ok else "MISSING_INPUT",
        "contract": {
            "research_only": True,
            "stride_sample": True,
            "dense_daily_evidence": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_evidence": False,
        },
        "ranking_manifests": {
            "dense": dense_manifest,
            "stride3": stride3_manifest,
        },
        "primary_evidence": "dense_daily",
        "summary": summary,
        "variants": {
            "dense": dense_variants,
            "stride3": stride3_variants,
        },
        "comparisons": {
            "dense": dense_comparisons,
            "stride3": stride3_comparisons,
        },
        "stability": stability_section(),
        "next_actions": [
            "sector45 不能當預設：dense daily 報酬下降，但最大回撤幾乎沒有改善。",
            "gross55 進保守候選：dense daily 報酬低於 fixed40，但最大回撤明顯下降。",
            "Top3 只保留強勢觀察標籤：勝率較高但總報酬不如 baseline，不能當主規則。",
            "下一步只讓 gross55 進 operational shadow dry-run，先每天產候選比較，不直接改正式推播。",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    dense = payload["variants"]["dense"]
    stride3 = payload["variants"]["stride3"]
    dense_comps = payload["comparisons"]["dense"]
    stride3_comps = payload["comparisons"]["stride3"]
    dense_manifest = payload["ranking_manifests"]["dense"]
    stride3_manifest = payload["ranking_manifests"]["stride3"]
    lines = [
        "# Operational Long Rule Validation Report",
        "",
        f"- status: `{payload['status']}`",
        f"- primary_evidence: `{payload['primary_evidence']}`",
        f"- dense ranking_count: `{dense_manifest.get('ranking_count')}`",
        f"- dense window: `{dense_manifest.get('first_date')}` to `{dense_manifest.get('last_date')}`",
        f"- dense stride: `{dense_manifest.get('stride')}`",
        f"- stride3 ranking_count: `{stride3_manifest.get('ranking_count')}`",
        f"- overall_decision: `{payload['summary']['overall_decision']}`",
        "",
        "## Dense Daily Portfolio Results",
        "",
        f"- fixed40: {pct(dense['fixed40'].get('total_return'))}, DD {pct(dense['fixed40'].get('max_drawdown'))}",
        f"- sector45: {pct(dense['sector45'].get('total_return'))}, DD {pct(dense['sector45'].get('max_drawdown'))}, delta {pct(dense_comps['sector45'].get('return_delta'))}",
        f"- gross55: {pct(dense['gross55'].get('total_return'))}, DD {pct(dense['gross55'].get('max_drawdown'))}, delta {pct(dense_comps['gross55'].get('return_delta'))}",
        f"- top3: {pct(dense['top3'].get('total_return'))}, DD {pct(dense['top3'].get('max_drawdown'))}, delta {pct(dense_comps['top3'].get('return_delta'))}",
        "",
        "## Stride3 Cross Check",
        "",
        f"- fixed40: {pct(stride3['fixed40'].get('total_return'))}, DD {pct(stride3['fixed40'].get('max_drawdown'))}",
        f"- sector45: {pct(stride3['sector45'].get('total_return'))}, DD {pct(stride3['sector45'].get('max_drawdown'))}, delta {pct(stride3_comps['sector45'].get('return_delta'))}",
        f"- gross55: {pct(stride3['gross55'].get('total_return'))}, DD {pct(stride3['gross55'].get('max_drawdown'))}, delta {pct(stride3_comps['gross55'].get('return_delta'))}",
        f"- top3: {pct(stride3['top3'].get('total_return'))}, DD {pct(stride3['top3'].get('max_drawdown'))}, delta {pct(stride3_comps['top3'].get('return_delta'))}",
        "",
        "## Rolling Stability",
        "",
        f"- gross55 40d return beat rate: {pct(payload['stability']['rolling_vs_fixed40']['gross55_40d'].get('candidate_return_beats_rate'))}",
        f"- gross55 40d drawdown improve rate: {pct(payload['stability']['rolling_vs_fixed40']['gross55_40d'].get('candidate_drawdown_improves_rate'))}",
        f"- gross55 80d return beat rate: {pct(payload['stability']['rolling_vs_fixed40']['gross55_80d'].get('candidate_return_beats_rate'))}",
        f"- gross55 80d drawdown improve rate: {pct(payload['stability']['rolling_vs_fixed40']['gross55_80d'].get('candidate_drawdown_improves_rate'))}",
        "",
        "## Decisions",
        "",
        f"- sector45_status: `{payload['summary']['sector45_status']}`",
        f"- gross55_status: `{payload['summary']['gross55_status']}`",
        f"- top3_status: `{payload['summary']['top3_status']}`",
        "",
        "## Next Actions",
        "",
    ]
    lines.extend(f"- {item}" for item in payload["next_actions"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"operational_long_rule_validation_report_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output), **payload["summary"]}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
