#!/usr/bin/env python3
"""以具名 profile 建立 regime conditional 研究產物。"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_high_choppy_context_overlay import load_regime_frame  # noqa: E402
from scripts.research_regime_family_training_candidates import is_big_bull  # noqa: E402


SHADOW_RANKINGS_SCHEMA_VERSION = "regime-conditional-shadow-ranking.v1"
HYBRID_REPORT_SCHEMA_VERSION = "regime-conditional-hybrid-report.v1"


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


def ranking_dates(path: Path) -> list[str]:
    return sorted(item.stem.removeprefix("ranking_") for item in path.glob("ranking_*.csv"))


def read_ranking(path: Path, top_n: int) -> pd.DataFrame:
    frame = pd.read_csv(path, encoding="utf-8-sig").head(top_n).copy()
    frame["stock_id"] = frame["stock_id"].astype(str).str.replace(r"\.0$", "", regex=True).str.zfill(4)
    return frame


def write_ranking(path: Path, frame: pd.DataFrame, source: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    output = frame.copy().reset_index(drop=True)
    output["rank"] = range(1, len(output) + 1)
    output["regime_conditional_source"] = source
    output.to_csv(path, index=False, encoding="utf-8-sig", quoting=csv.QUOTE_MINIMAL)


def active_dates(path: Path, family: str) -> set[str]:
    if family != "BIG_BULL":
        raise ValueError(f"unsupported active family: {family}")
    frame = load_regime_frame(path)
    frame["BIG_BULL"] = frame.apply(is_big_bull, axis=1)
    return {str(row.trade_date_text) for row in frame.itertuples(index=False) if bool(row.BIG_BULL)}


def build_shadow_rankings(args: argparse.Namespace) -> dict[str, Any]:
    production_dir = resolve_path(args.production_dir)
    shadow_dir = resolve_path(args.shadow_dir)
    output_dir = resolve_path(args.output_dir)
    regime_path = resolve_path(args.market_regime_history)
    if production_dir is None or shadow_dir is None or output_dir is None or regime_path is None:
        raise RuntimeError("shadow ranking path resolution failed")
    dates = sorted(set(ranking_dates(production_dir)) & set(ranking_dates(shadow_dir)))
    active = active_dates(regime_path, args.active_family)
    rows = []
    outputs = []
    for date_text in dates:
        use_shadow = date_text in active
        source_dir = shadow_dir if use_shadow else production_dir
        source = "shadow_active_family" if use_shadow else "production_inactive_family"
        frame = read_ranking(source_dir / f"ranking_{date_text}.csv", args.top_n)
        output_path = output_dir / f"ranking_{date_text}.csv"
        write_ranking(output_path, frame, source)
        outputs.append(repo_path(output_path))
        rows.append({"date": date_text, "source": source, "active_family": bool(use_shadow)})
    shadow_count = sum(1 for row in rows if row["source"] == "shadow_active_family")
    return {
        "schema_version": SHADOW_RANKINGS_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "trains_model": False,
            "modifies_production_ranking": False,
            "active_family": args.active_family,
            "inactive_family_source": "production",
        },
        "inputs": {
            "production_dir": repo_path(production_dir),
            "shadow_dir": repo_path(shadow_dir),
            "market_regime_history": repo_path(regime_path),
            "output_dir": repo_path(output_dir),
            "top_n": args.top_n,
        },
        "summary": {
            "date_count": len(rows),
            "shadow_active_family_count": shadow_count,
            "production_inactive_family_count": len(rows) - shadow_count,
        },
        "rows": rows,
        "outputs": outputs,
    }


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def hybrid_artifact_path(side: str, capital: int, run_date: str) -> Path:
    prefix = PROJECT_ROOT / "artifacts" / "model_experiments"
    k = capital // 1000
    if side == "production":
        name = f"odd_lot_portfolio_production_top7_sl12_min5_{k}k_gross75_pos12_{run_date}.json"
    elif side == "candidate_all":
        name = f"odd_lot_portfolio_candidate_top7_sl12_min5_{k}k_gross75_pos12_{run_date}.json"
    elif side == "hybrid_big_bull":
        name = f"odd_lot_portfolio_hybrid_big_bull_candidate_top7_sl12_min5_{k}k_g75_pos12_{run_date}.json"
    else:
        raise ValueError(f"unknown side: {side}")
    return prefix / name


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def hybrid_row(
    side: str,
    capital: int,
    path: Path,
    production: dict[str, Any],
    candidate_all: dict[str, Any],
) -> dict[str, Any]:
    summary = read_json(path).get("summary", {})
    total_return = safe_float(summary.get("total_return"))
    max_drawdown = safe_float(summary.get("max_drawdown"))
    return {
        "side": side,
        "capital": capital,
        "path": repo_path(path),
        "total_return": round(total_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "total_pnl": summary.get("total_pnl"),
        "trade_count": summary.get("trade_count"),
        "win_rate": summary.get("win_rate"),
        "avg_cash_weight": summary.get("avg_cash_weight"),
        "return_delta_vs_production": round(total_return - safe_float(production.get("total_return")), 6),
        "drawdown_delta_vs_production": round(max_drawdown - safe_float(production.get("max_drawdown")), 6),
        "return_delta_vs_candidate_all": round(total_return - safe_float(candidate_all.get("total_return")), 6),
        "drawdown_delta_vs_candidate_all": round(max_drawdown - safe_float(candidate_all.get("max_drawdown")), 6),
    }


def aggregate_hybrid(rows: list[dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for side in sorted({row["side"] for row in rows}):
        items = [row for row in rows if row["side"] == side]
        result[side] = {
            "capital_count": len(items),
            "avg_return": round(sum(safe_float(item["total_return"]) for item in items) / len(items), 6),
            "avg_max_drawdown": round(sum(safe_float(item["max_drawdown"]) for item in items) / len(items), 6),
            "avg_return_delta_vs_production": round(
                sum(safe_float(item["return_delta_vs_production"]) for item in items) / len(items), 6
            ),
            "avg_return_delta_vs_candidate_all": round(
                sum(safe_float(item["return_delta_vs_candidate_all"]) for item in items) / len(items), 6
            ),
        }
    return result


def hybrid_decision(summary: dict[str, Any]) -> dict[str, Any]:
    hybrid = summary.get("hybrid_big_bull", {})
    candidate = summary.get("candidate_all", {})
    if safe_float(hybrid.get("avg_return_delta_vs_production")) <= 0:
        status = "HYBRID_REJECTED"
        reason = "BIG_BULL-only hybrid 沒有勝過 production。"
    elif safe_float(hybrid.get("avg_return")) < safe_float(candidate.get("avg_return")) and safe_float(
        hybrid.get("avg_max_drawdown")
    ) > safe_float(candidate.get("avg_max_drawdown")):
        status = "HYBRID_MONITOR_ONLY"
        reason = "hybrid 勝過 production，但相對 all-candidate 報酬較低、回撤只小幅改善；先 monitor，不作主升級路線。"
    else:
        status = "HYBRID_CANDIDATE"
        reason = "hybrid 同時保留報酬優勢並改善風險，可進下一階段。"
    return {"status": status, "promotion_ready": False, "reason": reason}


def build_hybrid_report(args: argparse.Namespace) -> dict[str, Any]:
    capital_levels = [int(float(value.strip())) for value in args.capital_levels.split(",") if value.strip()]
    rows: list[dict[str, Any]] = []
    missing: list[str | None] = []
    for capital in capital_levels:
        paths = {
            side: hybrid_artifact_path(side, capital, args.date)
            for side in ("production", "candidate_all", "hybrid_big_bull")
        }
        for path in paths.values():
            if not path.exists():
                missing.append(repo_path(path))
        if any(not path.exists() for path in paths.values()):
            continue
        production = read_json(paths["production"]).get("summary", {})
        candidate = read_json(paths["candidate_all"]).get("summary", {})
        for side, path in paths.items():
            rows.append(hybrid_row(side, capital, path, production, candidate))
    summary = aggregate_hybrid(rows)
    return {
        "schema_version": HYBRID_REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if rows and not missing else "FAILED",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_ready": False,
        },
        "inputs": {
            "capital_levels": capital_levels,
            "ranking_policy": "BIG_BULL uses candidate ranking; inactive regimes use production ranking",
        },
        "summary": summary,
        "decision": hybrid_decision(summary),
        "rows": rows,
        "missing": missing,
    }


def write_hybrid_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# Regime Conditional Hybrid Report",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']['status']}",
        f"- promotion_ready: {payload['contract']['promotion_ready']}",
        "",
        "## Summary",
        "",
    ]
    for side, item in payload["summary"].items():
        lines.append(f"- {side}: avg_return={item['avg_return']}, avg_maxDD={item['avg_max_drawdown']}")
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build regime conditional suite")
    parser.add_argument("--profile", choices=("shadow_rankings", "hybrid_report"), default="shadow_rankings")
    parser.add_argument("--production-dir")
    parser.add_argument("--shadow-dir")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--active-family", default="BIG_BULL")
    parser.add_argument("--output-dir")
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--capital-levels", default="100000,300000,500000")
    parser.add_argument("--output", default=None)
    args = parser.parse_args()
    if args.profile == "shadow_rankings":
        missing = [
            flag
            for flag, value in (
                ("--production-dir", args.production_dir),
                ("--shadow-dir", args.shadow_dir),
                ("--output-dir", args.output_dir),
            )
            if value is None
        ]
        if missing:
            parser.error("the following arguments are required: " + ", ".join(missing))
    return args


def main() -> int:
    args = parse_args()
    if args.profile == "shadow_rankings":
        payload = build_shadow_rankings(args)
        output_dir = resolve_path(args.output_dir)
        if output_dir is None:
            raise RuntimeError("output resolution failed")
        summary_path = output_dir / "regime_conditional_shadow_ranking.json"
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
        )
        print(json.dumps({"status": "OK", "summary": repo_path(summary_path), **payload["summary"]}, ensure_ascii=False))
        return 0

    output = resolve_path(args.output) or (
        PROJECT_ROOT / "artifacts" / "model_experiments" / f"regime_conditional_hybrid_report_{args.date}.json"
    )
    payload = build_hybrid_report(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_hybrid_markdown(payload, output)
    print(json.dumps({"status": payload["status"], "decision": payload["decision"]["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
