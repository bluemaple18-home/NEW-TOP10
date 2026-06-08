#!/usr/bin/env python3
"""建立候選模型風險歸因報告。

這份報告只整理研究 artifact：候選模型相對 production 贏在哪、風險多在哪，
以及下一輪該優先測哪些控制條件。它不訓練模型，也不改正式 ranking。
"""

from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "training-candidate-risk-attribution.v1"
DEFAULT_CANDIDATE_ID = "current_baseline_candidate_{date}"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build training candidate risk attribution report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--candidate-id", default=None)
    parser.add_argument("--candidate-root", default=None)
    parser.add_argument("--summary", default="artifacts/model_experiments/candidate_vs_production_summary_{date}.json")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(str(value).format(date=date.today().isoformat())).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def candidate_root(args: argparse.Namespace) -> Path:
    if args.candidate_root:
        root = resolve_path(args.candidate_root)
        if root is None:
            raise RuntimeError("candidate root resolution failed")
        return root
    candidate_id = args.candidate_id or DEFAULT_CANDIDATE_ID.format(date=args.date)
    return PROJECT_ROOT / "artifacts" / "model_experiments" / "training_candidates" / candidate_id


def dated_path(template: str, run_date: str) -> Path:
    path = Path(template.format(date=run_date)).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def safe_int(value: Any, default: int = 0) -> int:
    try:
        if value is None:
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def metric_delta(candidate: dict[str, Any], production: dict[str, Any], key: str) -> dict[str, Any]:
    cand = candidate.get(key)
    prod = production.get(key)
    return {
        "candidate": cand,
        "production": prod,
        "delta": round(safe_float(cand) - safe_float(prod), 6),
    }


def flat_metric_delta(payload: dict[str, Any], candidate_key: str, production_key: str) -> dict[str, Any]:
    cand = payload.get(candidate_key)
    prod = payload.get(production_key)
    return {
        "candidate": cand,
        "production": prod,
        "delta": round(safe_float(cand) - safe_float(prod), 6),
    }


def top_variant(payload: dict[str, Any]) -> dict[str, Any]:
    variants = payload.get("variants")
    if isinstance(variants, list) and variants:
        return variants[0]
    return payload


def summarize_trades(trades: list[dict[str, Any]], group_key: str) -> list[dict[str, Any]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for trade in trades:
        key = str(trade.get(group_key) or "UNKNOWN")
        groups[key].append(trade)
    rows = []
    for key, items in groups.items():
        buy_cash = sum(safe_float(row.get("buy_cash")) for row in items)
        net_pnl = sum(safe_float(row.get("net_pnl")) for row in items)
        wins = sum(1 for row in items if safe_float(row.get("net_return")) > 0)
        rows.append(
            {
                group_key: key,
                "trade_count": len(items),
                "total_buy_cash": round(buy_cash, 2),
                "total_net_pnl": round(net_pnl, 2),
                "return_on_buy_cash": round(net_pnl / buy_cash, 6) if buy_cash else None,
                "win_rate": round(wins / len(items), 6) if items else None,
            }
        )
    return sorted(rows, key=lambda row: safe_float(row.get("return_on_buy_cash")), reverse=True)


def summarize_by_month(trades: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for row in summarize_trades(
        [
            {
                **trade,
                "ranking_month": str(trade.get("ranking_date") or "")[:7],
            }
            for trade in trades
        ],
        "ranking_month",
    ):
        if row["ranking_month"] != "UNKNOWN":
            rows.append(row)
    return rows


def compare_rows(
    candidate_rows: list[dict[str, Any]],
    production_rows: list[dict[str, Any]],
    key: str,
) -> list[dict[str, Any]]:
    prod_map = {str(row.get(key)): row for row in production_rows}
    result = []
    for cand in candidate_rows:
        row_key = str(cand.get(key))
        prod = prod_map.get(row_key, {})
        result.append(
            {
                key: row_key,
                "candidate": cand,
                "production": prod,
                "return_delta": round(safe_float(cand.get("return_on_buy_cash")) - safe_float(prod.get("return_on_buy_cash")), 6),
                "win_rate_delta": round(safe_float(cand.get("win_rate")) - safe_float(prod.get("win_rate")), 6),
            }
        )
    return result


def matrix_metric(payload: dict[str, Any], section: str, key: str) -> dict[str, Any]:
    value = payload.get("matrix", {}).get(section, {}).get(key, {})
    return value if isinstance(value, dict) else {}


def compare_matrix_metric(candidate: dict[str, Any], production: dict[str, Any], section: str, key: str) -> dict[str, Any]:
    cand = matrix_metric(candidate, section, key)
    prod = matrix_metric(production, section, key)
    return {
        "section": section,
        "key": key,
        "candidate": cand,
        "production": prod,
        "return_delta": round(safe_float(cand.get("return_on_buy_cash")) - safe_float(prod.get("return_on_buy_cash")), 6),
        "win_rate_delta": round(safe_float(cand.get("win_rate")) - safe_float(prod.get("win_rate")), 6),
        "avg_mae_delta": round(safe_float(cand.get("avg_mae")) - safe_float(prod.get("avg_mae")), 6),
        "worst_mae_delta": round(safe_float(cand.get("worst_mae")) - safe_float(prod.get("worst_mae")), 6),
        "giveback_delta": round(safe_float(cand.get("avg_giveback")) - safe_float(prod.get("avg_giveback")), 6),
    }


def top_by_return(payload: dict[str, Any], section: str, min_trades: int = 100, limit: int = 5) -> list[dict[str, Any]]:
    rows = []
    for key, value in payload.get("matrix", {}).get(section, {}).items():
        if safe_int(value.get("trade_count")) >= min_trades:
            rows.append({"key": key, **value})
    return sorted(rows, key=lambda row: safe_float(row.get("return_on_buy_cash")), reverse=True)[:limit]


def sector_concentration(payload: dict[str, Any], policy: str) -> dict[str, Any]:
    value = payload.get("matrix", {}).get("sector_concentration", {}).get(policy, {})
    return value if isinstance(value, dict) else {}


def build_findings(report: dict[str, Any]) -> list[dict[str, Any]]:
    headline = report["headline"]
    fixed_40d = report["matrix_attribution"]["fixed_40d"]
    sector = report["matrix_attribution"]["sector_concentration_fixed_40d"]
    rank_top = report["matrix_attribution"]["candidate_top_rank_policies"][:3]
    findings = [
        {
            "id": "RET-01",
            "status": "KEEP_RESEARCH",
            "finding": "候選模型在 40D 波段與固定 100 股回測都有明顯報酬優勢。",
            "evidence": {
                "portfolio_40d_total_return_delta": headline["portfolio_40d_total_return"]["delta"],
                "best_exit_return_delta": headline["best_exit_return_on_buy_cash"]["delta"],
                "fixed_share_default_return_delta": headline["fixed_share_default_return_on_buy_cash"]["delta"],
            },
        },
        {
            "id": "RISK-01",
            "status": "NEEDS_CONTROL",
            "finding": "候選模型的 portfolio 最大回撤比 production 深，不能直接升正式。",
            "evidence": {
                "portfolio_40d_max_drawdown_delta": headline["portfolio_40d_max_drawdown"]["delta"],
                "fixed_40d_worst_mae_delta": fixed_40d["worst_mae_delta"],
                "fixed_40d_avg_mae_delta": fixed_40d["avg_mae_delta"],
            },
        },
        {
            "id": "SECTOR-01",
            "status": "TEST_CAP",
            "finding": "候選模型更集中在科技族群，報酬多半也來自科技，下一輪要測產業曝險上限。",
            "evidence": sector,
        },
        {
            "id": "RANK-01",
            "status": "TEST_RANK_SLICE",
            "finding": "候選模型的名次段不是全部等強，下一輪要測 top7/top4_7/top5 等排名切片。",
            "evidence": rank_top,
        },
    ]
    return findings


def next_experiments() -> list[dict[str, Any]]:
    return [
        {
            "id": "CAND-RISK-01",
            "title": "sector cap / industry concentration replay",
            "purpose": "保留候選模型 alpha，但限制單一族群曝險，先測科技買入金額上限 55% / 65% / 75%。",
            "acceptance": "報酬優勢保留至少一半，max drawdown 不劣於 production 超過 1 個百分點。",
            "allowed": ["shadow replay", "research artifact"],
            "not_allowed": ["production ranking change", "model promotion"],
        },
        {
            "id": "CAND-RISK-02",
            "title": "rank slice replay",
            "purpose": "測候選模型 top7、top4_7、top5 是否比全 Top10 更穩。",
            "acceptance": "return_on_buy_cash 與 win_rate 高於 production 同切片，且 worst_mae 不惡化。",
            "allowed": ["shadow replay", "candidate ranking reuse"],
            "not_allowed": ["daily message change"],
        },
        {
            "id": "CAND-RISK-03",
            "title": "regime throttle replay",
            "purpose": "把 BIG_BULL / HIGH_CHOPPY_CONTEXT / OTHER 分開看，測高檔震盪是否需要降低持倉數或縮短持有期。",
            "acceptance": "HIGH_CHOPPY_CONTEXT 的 drawdown/giveback 降低，且 BIG_BULL 報酬不被明顯犧牲。",
            "allowed": ["stratified replay", "research artifact"],
            "not_allowed": ["hard-coded regime weight"],
        },
        {
            "id": "CAND-RISK-04",
            "title": "capital realistic odd-lot portfolio",
            "purpose": "用小白可承受本金做零股/等金額回測，不再用無上限每日 100 股當唯一判斷。",
            "acceptance": "固定本金下 total return、max drawdown、cash usage 都勝過 production 或至少風險更低。",
            "allowed": ["portfolio replay extension"],
            "not_allowed": ["recommendation wording change before evidence"],
        },
    ]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    root = candidate_root(args)
    summary_path = dated_path(args.summary, args.date)
    candidate_matrix_path = root / f"fixed_share_hypothesis_matrix_candidate_{args.date}.json"
    production_matrix_path = PROJECT_ROOT / "artifacts" / "model_experiments" / f"production_fixed_share_hypothesis_matrix_{args.date}.json"
    candidate_top10_path = root / f"fixed_share_top10_candidate_{args.date}.json"
    production_top10_path = PROJECT_ROOT / "artifacts" / "model_experiments" / f"production_fixed_share_top10_{args.date}.json"

    summary = read_json(summary_path)
    candidate_matrix = read_json(candidate_matrix_path)
    production_matrix = read_json(production_matrix_path)
    candidate_top10 = read_json(candidate_top10_path)
    production_top10 = read_json(production_top10_path)

    candidate_variant = top_variant(candidate_top10)
    production_variant = top_variant(production_top10)
    candidate_trades = candidate_variant.get("trades") if isinstance(candidate_variant.get("trades"), list) else []
    production_trades = production_variant.get("trades") if isinstance(production_variant.get("trades"), list) else []

    default_summary = summary["fixed_100_shares_5_7_10_15_20_default"]
    candidate_best = summary["best_exit_policy_matrix"]["candidate"]
    production_best = summary["best_exit_policy_matrix"]["production"]
    portfolio_summary = summary["portfolio_40d"]

    fixed_40d = compare_matrix_metric(candidate_matrix, production_matrix, "exit_policy", "fixed_40d")
    high_choppy = compare_matrix_metric(candidate_matrix, production_matrix, "regime_policy", "fixed_40d::HIGH_CHOPPY_CONTEXT")
    big_bull = compare_matrix_metric(candidate_matrix, production_matrix, "regime_policy", "fixed_40d::BIG_BULL")
    sector_candidate = sector_concentration(candidate_matrix, "fixed_40d")
    sector_production = sector_concentration(production_matrix, "fixed_40d")

    report: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "risk_adjusted_score_changes": False,
            "promotion_ready": False,
            "purpose": "risk attribution before any candidate promotion or overlay decision",
        },
        "inputs": {
            "summary": repo_path(summary_path),
            "candidate_root": repo_path(root),
            "candidate_matrix": repo_path(candidate_matrix_path),
            "production_matrix": repo_path(production_matrix_path),
            "candidate_fixed_share_top10": repo_path(candidate_top10_path),
            "production_fixed_share_top10": repo_path(production_top10_path),
        },
        "headline": {
            "fixed_share_default_return_on_buy_cash": flat_metric_delta(
                default_summary,
                "candidate_return_on_buy_cash",
                "production_return_on_buy_cash",
            ),
            "fixed_share_default_win_rate": flat_metric_delta(default_summary, "candidate_win_rate", "production_win_rate"),
            "best_exit_policy": {
                "candidate": candidate_best.get("key"),
                "production": production_best.get("key"),
            },
            "best_exit_return_on_buy_cash": metric_delta(candidate_best, production_best, "return_on_buy_cash"),
            "portfolio_40d_total_return": flat_metric_delta(
                portfolio_summary,
                "candidate_total_return",
                "production_total_return",
            ),
            "portfolio_40d_max_drawdown": flat_metric_delta(
                portfolio_summary,
                "candidate_max_drawdown",
                "production_max_drawdown",
            ),
            "portfolio_40d_trade_count": flat_metric_delta(
                portfolio_summary,
                "candidate_trade_count",
                "production_trade_count",
            ),
        },
        "trade_attribution": {
            "by_month": compare_rows(summarize_by_month(candidate_trades), summarize_by_month(production_trades), "ranking_month"),
            "by_rank": compare_rows(summarize_trades(candidate_trades, "rank"), summarize_trades(production_trades, "rank"), "rank"),
        },
        "matrix_attribution": {
            "fixed_40d": fixed_40d,
            "fixed_40d_big_bull": big_bull,
            "fixed_40d_high_choppy_context": high_choppy,
            "sector_concentration_fixed_40d": {
                "candidate": sector_candidate,
                "production": sector_production,
                "max_sector_buy_share_delta": round(
                    safe_float(sector_candidate.get("max_sector_buy_share")) - safe_float(sector_production.get("max_sector_buy_share")),
                    6,
                ),
            },
            "candidate_top_exit_policies": top_by_return(candidate_matrix, "exit_policy"),
            "production_top_exit_policies": top_by_return(production_matrix, "exit_policy"),
            "candidate_top_rank_policies": top_by_return(candidate_matrix, "rank_policy"),
            "production_top_rank_policies": top_by_return(production_matrix, "rank_policy"),
        },
        "risk_hypotheses": [],
        "next_experiments": next_experiments(),
        "decision": {
            "status": "KEEP_CANDIDATE_RESEARCH_WITH_RISK_CONTROLS",
            "promotion_ready": False,
            "plain_language": "候選模型比較會抓強股，但也更容易集中在同一族群、承受更深回撤；下一步先測風控，不直接上正式。",
        },
    }
    report["risk_hypotheses"] = build_findings(report)
    return report


def write_markdown(payload: dict[str, Any], output_path: Path) -> None:
    headline = payload["headline"]
    sector = payload["matrix_attribution"]["sector_concentration_fixed_40d"]
    lines = [
        "# Training Candidate Risk Attribution",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']['status']}",
        f"- promotion_ready: {payload['contract']['promotion_ready']}",
        f"- fixed_share_return_delta: {headline['fixed_share_default_return_on_buy_cash']['delta']}",
        f"- portfolio_40d_return_delta: {headline['portfolio_40d_total_return']['delta']}",
        f"- portfolio_40d_max_drawdown_delta: {headline['portfolio_40d_max_drawdown']['delta']}",
        f"- sector_max_buy_share_delta: {sector['max_sector_buy_share_delta']}",
        "",
        "## 白話結論",
        "",
        payload["decision"]["plain_language"],
        "",
        "## Risk Hypotheses",
        "",
    ]
    for finding in payload["risk_hypotheses"]:
        lines.append(f"- {finding['id']} {finding['status']}: {finding['finding']}")
    lines.extend(["", "## Next Experiments", ""])
    for experiment in payload["next_experiments"]:
        lines.append(f"- {experiment['id']}: {experiment['title']}")
    output_path.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"training_candidate_risk_attribution_{args.date}.json"
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(payload, output)
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
