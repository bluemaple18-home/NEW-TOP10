#!/usr/bin/env python3
"""每日推薦候選的 PM 風險驗證報告。

此腳本只讀既有 half-year replay artifacts，不重訓模型、不改 production ranking。
它把 Public Equity PM 會看的幾件事系統化：報酬、回撤、族群集中、少數股票貢獻、
時間窗穩定性，避免只因單一總報酬好看就讓候選進主線。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BACKTEST_DIR = PROJECT_ROOT / "artifacts" / "backtest"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "daily-recommendation-pm-validation.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build daily recommendation PM validation report")
    parser.add_argument("--date", default="2026-06-02")
    parser.add_argument("--artifact-label", default="half_year_dense")
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


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def number(value: Any) -> float | None:
    if value is None:
        return None
    return float(value)


def portfolio_path(candidate_id: str, label: str, date_text: str) -> Path:
    return BACKTEST_DIR / f"portfolio_batch01_{candidate_id}_{label}_top10_h10_{date_text}.json"


def stability_paths(label: str, date_text: str) -> list[Path]:
    return [
        BACKTEST_DIR / f"replay_window_stability_{label}_{date_text}.json",
        BACKTEST_DIR / f"replay_window_stability_{label}_k9_{date_text}.json",
    ]


def max_drawdown_date(daily_rows: list[dict[str, Any]]) -> dict[str, Any]:
    peak = None
    worst = {"date": None, "drawdown": 0.0, "equity": None, "peak": None}
    for row in daily_rows:
        equity = number(row.get("equity"))
        if equity is None:
            continue
        peak = equity if peak is None else max(peak, equity)
        drawdown = equity / peak - 1 if peak else 0.0
        if drawdown < worst["drawdown"]:
            worst = {"date": row.get("date"), "drawdown": round(drawdown, 6), "equity": round(equity, 6), "peak": round(peak, 6)}
    return worst


def contribution_summary(trades: list[dict[str, Any]]) -> dict[str, Any]:
    by_stock: dict[str, float] = defaultdict(float)
    by_group: dict[str, float] = defaultdict(float)
    by_stock_name: dict[str, str] = {}
    total_positive = 0.0
    total_abs = 0.0
    winners = 0
    losers = 0
    for trade in trades:
        stock_id = str(trade.get("stock_id") or "")
        stock_name = str(trade.get("stock_name") or "")
        group = str(trade.get("group") or "UNKNOWN")
        pnl = float(trade.get("entry_notional") or 0.0) * float(trade.get("net_return") or 0.0)
        by_stock[stock_id] += pnl
        by_stock_name[stock_id] = stock_name
        by_group[group] += pnl
        total_abs += abs(pnl)
        if pnl > 0:
            total_positive += pnl
            winners += 1
        elif pnl < 0:
            losers += 1

    top_stocks = sorted(by_stock.items(), key=lambda item: item[1], reverse=True)[:8]
    top_groups = sorted(by_group.items(), key=lambda item: item[1], reverse=True)[:8]
    top_stock_positive_share = top_stocks[0][1] / total_positive if top_stocks and total_positive > 0 else None
    top_group_positive_share = top_groups[0][1] / total_positive if top_groups and total_positive > 0 else None
    top3_stock_positive_share = sum(max(value, 0.0) for _, value in top_stocks[:3]) / total_positive if total_positive > 0 else None

    return {
        "trade_winners": winners,
        "trade_losers": losers,
        "total_positive_pnl_proxy": round(total_positive, 6),
        "total_abs_pnl_proxy": round(total_abs, 6),
        "top_stock_positive_share": round(top_stock_positive_share, 6) if top_stock_positive_share is not None else None,
        "top3_stock_positive_share": round(top3_stock_positive_share, 6) if top3_stock_positive_share is not None else None,
        "top_group_positive_share": round(top_group_positive_share, 6) if top_group_positive_share is not None else None,
        "top_stocks": [
            {"stock_id": stock_id, "stock_name": by_stock_name.get(stock_id), "pnl_proxy": round(value, 6)}
            for stock_id, value in top_stocks
        ],
        "top_groups": [{"group": group, "pnl_proxy": round(value, 6)} for group, value in top_groups],
    }


def stability_lookup(label: str, date_text: str) -> dict[tuple[str, int], dict[str, Any]]:
    result: dict[tuple[str, int], dict[str, Any]] = {}
    for path in stability_paths(label, date_text):
        payload = read_json(path)
        for row in payload.get("summary") or []:
            variant = row.get("variant")
            horizon = row.get("horizon")
            if variant and horizon is not None:
                result[(str(variant), int(horizon))] = row
    return result


def variant_from_candidate(candidate_id: str) -> str:
    if candidate_id == "baseline":
        return "baseline"
    prefix = "sector" if candidate_id.startswith("sector_context") else "feature"
    keep = candidate_id.rsplit("_k", maxsplit=1)[-1]
    return f"{prefix}_k{keep}"


def candidate_decision(row: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    total_return_delta = row.get("total_return_delta")
    drawdown_delta = row.get("max_drawdown_delta")
    stability = row.get("stability_h10") or {}
    contribution = row.get("contribution") or {}
    top_group_share = contribution.get("top_group_positive_share")
    top3_stock_share = contribution.get("top3_stock_positive_share")

    if total_return_delta is None or drawdown_delta is None:
        return "MISSING", ["artifact missing or baseline missing"]
    if total_return_delta < 0:
        reasons.append("return below baseline")
    if drawdown_delta < -0.015:
        reasons.append("drawdown worsens by more than 1.5ppt")
    if stability.get("decision") == "UNSTABLE":
        reasons.append("10D window stability is unstable")
    if top_group_share is not None and top_group_share > 0.45:
        reasons.append("positive PnL depends too much on one industry group")
    if top3_stock_share is not None and top3_stock_share > 0.45:
        reasons.append("positive PnL depends too much on top 3 stocks")

    if not reasons:
        return "ADVANCE_TO_DAILY_SHADOW", ["return beats baseline without obvious PM risk blocker"]
    if total_return_delta >= 0.08 and drawdown_delta >= -0.015:
        return "RESEARCH_SHADOW_WITH_GUARDS", reasons
    return "MONITOR_ONLY", reasons


def build_candidate(candidate_id: str, label: str, date_text: str, baseline: dict[str, Any], stability: dict[tuple[str, int], dict[str, Any]]) -> dict[str, Any]:
    path = portfolio_path(candidate_id, label, date_text)
    payload = read_json(path)
    summary = payload.get("summary") or {}
    baseline_summary = baseline.get("summary") or {}
    row = {
        "candidate_id": candidate_id,
        "source": repo_path(path),
        "exists": path.exists(),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "win_rate": summary.get("win_rate"),
        "trade_count": summary.get("trade_count"),
        "max_group_exposure": summary.get("max_group_exposure"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "total_return_delta": (
            round(float(summary["total_return"]) - float(baseline_summary["total_return"]), 6)
            if summary.get("total_return") is not None and baseline_summary.get("total_return") is not None
            else None
        ),
        "max_drawdown_delta": (
            round(float(summary["max_drawdown"]) - float(baseline_summary["max_drawdown"]), 6)
            if summary.get("max_drawdown") is not None and baseline_summary.get("max_drawdown") is not None
            else None
        ),
        "worst_drawdown": max_drawdown_date(payload.get("daily") or []),
        "contribution": contribution_summary(payload.get("trades") or []),
        "stability_h10": stability.get((variant_from_candidate(candidate_id), 10), {}),
    }
    decision, reasons = candidate_decision(row)
    row["decision"] = decision
    row["decision_reasons"] = reasons
    return row


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    date_text = args.date
    label = args.artifact_label
    baseline = read_json(portfolio_path("baseline", label, date_text))
    stability = stability_lookup(label, date_text)
    candidates = ["baseline"]
    for keep in (6, 7, 8, 9):
        candidates.extend([f"feature_group_constrained_k{keep}", f"sector_context_constrained_k{keep}"])
    rows = [build_candidate(candidate, label, date_text, baseline, stability) for candidate in candidates]
    decisions = Counter(row["decision"] for row in rows if row["candidate_id"] != "baseline")
    ranked = sorted(
        [row for row in rows if row["candidate_id"] != "baseline" and row.get("total_return") is not None],
        key=lambda row: (
            row["decision"] == "ADVANCE_TO_DAILY_SHADOW",
            row["decision"] == "RESEARCH_SHADOW_WITH_GUARDS",
            row.get("total_return_delta") or -999,
            row.get("max_drawdown_delta") or -999,
        ),
        reverse=True,
    )
    best = ranked[0] if ranked else None
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": date_text,
        "artifact_label": label,
        "contract": {
            "research_only": True,
            "reads_existing_artifacts_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "promotion_ready": False,
            "public_equity_pm_lens": [
                "return_vs_baseline",
                "drawdown_vs_baseline",
                "window_stability",
                "industry_concentration",
                "single_stock_contribution",
            ],
        },
        "summary": {
            "candidate_count": len(rows) - 1,
            "decisions": dict(decisions),
            "best_candidate": best["candidate_id"] if best else None,
            "best_decision": best["decision"] if best else None,
            "baseline_total_return": (baseline.get("summary") or {}).get("total_return"),
            "baseline_max_drawdown": (baseline.get("summary") or {}).get("max_drawdown"),
        },
        "baseline": rows[0] if rows else {},
        "candidates": [row for row in rows if row["candidate_id"] != "baseline"],
        "errors": [] if baseline else ["baseline artifact missing"],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# RQ09 每日推薦 PM 風險驗證",
        "",
        f"- date: `{payload['date']}`",
        f"- artifact_label: `{payload['artifact_label']}`",
        f"- candidate_count: `{summary['candidate_count']}`",
        f"- best_candidate: `{summary['best_candidate']}`",
        f"- best_decision: `{summary['best_decision']}`",
        f"- baseline_return: `{pct(summary['baseline_total_return'])}`",
        f"- baseline_max_drawdown: `{pct(summary['baseline_max_drawdown'])}`",
        f"- promotion_ready: `{payload['contract']['promotion_ready']}`",
        "",
        "## 候選比較",
        "",
        "| Candidate | Decision | Return | ΔReturn | Max DD | ΔDD | Win | Top Group Share | Top3 Stock Share | H10 Stability |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["candidates"]:
        contribution = row.get("contribution") or {}
        stability = row.get("stability_h10") or {}
        lines.append(
            "| {candidate} | {decision} | {ret} | {dret} | {dd} | {ddd} | {win} | {group} | {stock} | {stable} |".format(
                candidate=row["candidate_id"],
                decision=row["decision"],
                ret=pct(row.get("total_return")),
                dret=pct(row.get("total_return_delta")),
                dd=pct(row.get("max_drawdown")),
                ddd=pct(row.get("max_drawdown_delta")),
                win=pct(row.get("win_rate")),
                group=pct(contribution.get("top_group_positive_share")),
                stock=pct(contribution.get("top3_stock_positive_share")),
                stable=stability.get("decision", "MISSING"),
            )
        )
    lines.extend(["", "## 最佳候選解讀", ""])
    best_id = summary.get("best_candidate")
    best = next((row for row in payload["candidates"] if row["candidate_id"] == best_id), None)
    if best:
        lines.extend(
            [
                f"- `{best['candidate_id']}` 半年報酬為 `{pct(best.get('total_return'))}`，比 baseline 多 `{pct(best.get('total_return_delta'))}`。",
                f"- 最大回撤為 `{pct(best.get('max_drawdown'))}`，比 baseline 差 `{pct(best.get('max_drawdown_delta'))}`。",
                f"- 判定：`{best['decision']}`。",
                "- 原因：" + "；".join(best.get("decision_reasons") or []),
            ]
        )
    lines.extend(["", "## 邊界", ""])
    lines.extend(
        [
            "- 這份報告只讀既有 artifacts。",
            "- 不訓練模型、不改 production ranking、不覆蓋 `models/latest_lgbm.pkl`。",
            "- 結論只能決定下一輪 shadow/monitor，不是正式升版。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) if args.output else OUTPUT_DIR / f"daily_recommendation_pm_validation_{args.date}.json"
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK" if not payload["errors"] else "FAILED",
                "output": repo_path(output),
                "best_candidate": payload["summary"]["best_candidate"],
                "best_decision": payload["summary"]["best_decision"],
                "errors": payload["errors"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if not payload["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
