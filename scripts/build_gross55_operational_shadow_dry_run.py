#!/usr/bin/env python3
"""產出 gross55 營運規則 shadow dry-run 報告。

此報告只讀既有 ranking / portfolio replay / long validation artifact，不重訓、
不重排榜，也不修改正式推播。gross55 的語意是 portfolio 層總曝險上限 55%，
不是改變 Top10 入選名單。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "gross55-operational-shadow-dry-run.v1"
EXPECTED_MODEL_SHA256 = "76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build gross55 operational shadow dry-run report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--long-report", default="artifacts/model_experiments/operational_long_rule_validation_report_2026-06-02.json")
    parser.add_argument("--long-verification", default="artifacts/model_experiments/operational_long_rule_validation_verification_latest.json")
    parser.add_argument("--rankings-dir", default="artifacts/backtest/historical_rankings_current_model_batch_dense_2023-11-21_2026-05-15")
    parser.add_argument("--production-replay", default="artifacts/backtest/portfolio_replay_production_long_dense_fixed40_2026-06-02.json")
    parser.add_argument("--gross55-replay", default="artifacts/backtest/portfolio_replay_production_long_dense_fixed40_gross55_2026-06-02.json")
    parser.add_argument("--model", default="models/latest_lgbm.pkl")
    parser.add_argument("--expected-model-sha256", default=EXPECTED_MODEL_SHA256)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--production-default-gross", type=float, default=0.65)
    parser.add_argument("--shadow-gross", type=float, default=0.55)
    parser.add_argument("--max-position-weight", type=float, default=0.2)
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


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def n(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def pct(value: Any) -> str:
    return f"{n(value):.2%}"


def latest_ranking_file(rankings_dir: Path) -> Path | None:
    files = sorted(rankings_dir.glob("ranking_*.csv"))
    return files[-1] if files else None


def read_ranking(path: Path, top_n: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result: list[dict[str, Any]] = []
    for rank, row in enumerate(rows[:top_n], start=1):
        result.append(
            {
                "rank": rank,
                "stock_id": str(row.get("stock_id") or "").strip().zfill(4),
                "stock_name": row.get("stock_name"),
                "risk_adjusted_score": n(row.get("risk_adjusted_score"), None),
                "suggested_weight": n(row.get("suggested_weight"), None),
                "max_position_weight": n(row.get("max_position_weight"), None),
                "gross_exposure": n(row.get("gross_exposure"), None),
                "allocated_exposure": n(row.get("allocated_exposure"), None),
                "cash_weight": n(row.get("cash_weight"), None),
                "market_regime": row.get("market_regime"),
                "exposure_note": row.get("exposure_note"),
            }
        )
    return result


def portfolio_weights(items: list[dict[str, Any]], default_gross: float, max_position_weight: float) -> dict[str, float]:
    raw: dict[str, float] = {}
    for item in items:
        suggested = item.get("suggested_weight")
        weight = suggested if suggested is not None and suggested > 0 else 1 / len(items) if items else 0.0
        row_cap = item.get("max_position_weight")
        caps = [max_position_weight]
        if row_cap is not None and row_cap > 0:
            caps.append(float(row_cap))
        raw[item["stock_id"]] = min(float(weight), min(caps))
    total = sum(raw.values())
    if total <= 0:
        return {stock_id: 0.0 for stock_id in raw}
    row_gross = next((item.get("gross_exposure") for item in items if item.get("gross_exposure") is not None), None)
    gross = float(row_gross) if row_gross is not None and row_gross > 0 else float(default_gross)
    target_total = min(gross, total)
    scale = target_total / total
    return {stock_id: round(weight * scale, 6) for stock_id, weight in raw.items()}


def cap_total_weight(weights: dict[str, float], cap: float) -> dict[str, float]:
    total = sum(weights.values())
    if total <= 0 or total <= cap:
        return weights
    scale = cap / total
    return {stock_id: round(weight * scale, 6) for stock_id, weight in weights.items()}


def allocation_snapshot(path: Path | None, top_n: int, production_default: float, shadow_gross: float, max_position: float) -> dict[str, Any]:
    if path is None:
        return {"exists": False}
    rows = read_ranking(path, top_n)
    requested = portfolio_weights(rows, production_default, max_position)
    production = cap_total_weight(requested, production_default)
    shadow = cap_total_weight(requested, shadow_gross)
    items = []
    for row in rows:
        stock_id = row["stock_id"]
        items.append(
            {
                "rank": row["rank"],
                "stock_id": stock_id,
                "stock_name": row.get("stock_name"),
                "production_weight": production.get(stock_id, 0.0),
                "gross55_shadow_weight": shadow.get(stock_id, 0.0),
                "weight_delta": round(shadow.get(stock_id, 0.0) - production.get(stock_id, 0.0), 6),
                "market_regime": row.get("market_regime"),
            }
        )
    production_total = round(sum(production.values()), 6)
    shadow_total = round(sum(shadow.values()), 6)
    requested_total = round(sum(requested.values()), 6)
    return {
        "exists": True,
        "ranking_path": repo_path(path),
        "ranking_date": path.stem.replace("ranking_", ""),
        "top_n": top_n,
        "same_top10": True,
        "ranking_requested_gross": requested_total,
        "production_target_gross_from_latest_ranking": production_total,
        "gross55_shadow_target_gross_from_latest_ranking": shadow_total,
        "entry_weight_changed_on_latest_ranking": shadow_total != production_total,
        "latest_market_regime": rows[0].get("market_regime") if rows else None,
        "latest_exposure_note": rows[0].get("exposure_note") if rows else None,
        "items": items,
    }


def summarize_replay(path: Path) -> dict[str, Any]:
    payload = read_json(path)
    summary = payload.get("summary") or {}
    return {
        "path": repo_path(path),
        "exists": bool(payload),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "trade_count": summary.get("trade_count"),
        "win_rate": summary.get("win_rate"),
        "avg_trade_return": summary.get("avg_trade_return"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "max_gross_exposure": summary.get("max_gross_exposure"),
        "max_group_exposure": summary.get("max_group_exposure"),
    }


def daily_control(production_path: Path, gross55_path: Path) -> dict[str, Any]:
    production = read_json(production_path).get("daily") or []
    gross55 = read_json(gross55_path).get("daily") or []
    pairs = list(zip(production, gross55, strict=False))
    if not pairs:
        return {"count": 0}
    exposure_deltas = [n(gross.get("gross_exposure")) - n(prod.get("gross_exposure")) for prod, gross in pairs]
    return_deltas = [n(gross.get("daily_return")) - n(prod.get("daily_return")) for prod, gross in pairs]
    gross_deleverage = sum(int(gross.get("deleverage_count") or 0) for _, gross in pairs)
    prod_deleverage = sum(int(prod.get("deleverage_count") or 0) for prod, _ in pairs)
    return {
        "count": len(pairs),
        "avg_gross_exposure_delta": round(sum(exposure_deltas) / len(exposure_deltas), 6),
        "gross55_lower_exposure_day_rate": round(sum(delta < 0 for delta in exposure_deltas) / len(exposure_deltas), 6),
        "avg_daily_return_delta": round(sum(return_deltas) / len(return_deltas), 6),
        "worst_daily_return_delta": round(min(return_deltas), 6),
        "production_deleverage_count": prod_deleverage,
        "gross55_deleverage_count": gross_deleverage,
        "deleverage_count_delta": gross_deleverage - prod_deleverage,
    }


def regime_delta(long_report: dict[str, Any]) -> dict[str, Any]:
    dense = (long_report.get("variants") or {}).get("dense") or {}
    fixed = (dense.get("fixed40") or {}).get("by_regime") or {}
    gross = (dense.get("gross55") or {}).get("by_regime") or {}
    result: dict[str, Any] = {}
    for label in sorted(set(fixed) | set(gross)):
        left = fixed.get(label) or {}
        right = gross.get(label) or {}
        result[label] = {
            "daily_count": right.get("daily_count") or left.get("daily_count"),
            "gross55_compound_return": right.get("compound_return"),
            "fixed40_compound_return": left.get("compound_return"),
            "compound_return_delta": round(n(right.get("compound_return")) - n(left.get("compound_return")), 6),
            "gross55_worst_daily_return": right.get("worst_daily_return"),
            "fixed40_worst_daily_return": left.get("worst_daily_return"),
            "worst_daily_return_delta": round(n(right.get("worst_daily_return")) - n(left.get("worst_daily_return")), 6),
        }
    return result


def decide(long_report: dict[str, Any], verification: dict[str, Any], production: dict[str, Any], gross55: dict[str, Any]) -> tuple[str, list[str]]:
    reasons: list[str] = []
    summary = long_report.get("summary") or {}
    if verification.get("status") != "OK":
        reasons.append("long rule validation verifier is not OK")
    if summary.get("gross55_status") != "CONSERVATIVE_CANDIDATE_FOR_DRAWDOWN_REDUCTION":
        reasons.append("gross55 is not marked as conservative drawdown candidate")
    if n(gross55.get("max_drawdown")) <= n(production.get("max_drawdown")):
        reasons.append("gross55 does not improve max drawdown")
    if n(gross55.get("total_return")) <= 0:
        reasons.append("gross55 total return is not positive")
    if reasons:
        return "BLOCKED", reasons
    return "READY_FOR_OPERATIONAL_SHADOW_MONITOR", []


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    long_report_path = resolve_path(args.long_report)
    verification_path = resolve_path(args.long_verification)
    rankings_dir = resolve_path(args.rankings_dir)
    production_path = resolve_path(args.production_replay)
    gross55_path = resolve_path(args.gross55_replay)
    model_path = resolve_path(args.model)
    long_report = read_json(long_report_path)
    verification = read_json(verification_path)
    production = summarize_replay(production_path)
    gross55 = summarize_replay(gross55_path)
    model_hash = sha256(model_path) if model_path.exists() else None
    shadow_status, blocked_reasons = decide(long_report, verification, production, gross55)
    allocation = allocation_snapshot(
        latest_ranking_file(rankings_dir),
        args.top_n,
        args.production_default_gross,
        args.shadow_gross,
        args.max_position_weight,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if shadow_status != "BLOCKED" else "BLOCKED",
        "shadow_status": shadow_status,
        "blocked_reasons": blocked_reasons,
        "contract": {
            "research_only": True,
            "operational_shadow_only": True,
            "changes_top10_membership": False,
            "changes_risk_adjusted_score": False,
            "changes_production_ranking": False,
            "changes_model": False,
            "changes_clawd_message": False,
            "promotion_evidence": False,
            "default_allowed": False,
        },
        "inputs": {
            "long_report": repo_path(long_report_path),
            "long_verification": repo_path(verification_path),
            "rankings_dir": repo_path(rankings_dir),
            "production_replay": repo_path(production_path),
            "gross55_replay": repo_path(gross55_path),
            "model": repo_path(model_path),
            "expected_model_sha256": args.expected_model_sha256,
            "actual_model_sha256": model_hash,
        },
        "summary": {
            "decision": shadow_status,
            "next_gate": "DAILY_SHADOW_MONITOR_COMPARE_WITH_PRODUCTION" if shadow_status != "BLOCKED" else "FIX_BLOCKERS",
            "operator_meaning": "gross55 不改選股，只限制重疊持倉時的總曝險；行情強時可能少賺，行情回撤時目標是少受傷。",
            "latest_ranking_note": "若 ranking 本身已因盤勢給低曝險，gross55 不會再硬砍 entry weights；主要影響是後續重疊持倉的 portfolio cap。",
        },
        "portfolio_comparison": {
            "production_fixed40": production,
            "gross55_shadow": gross55,
            "deltas": {
                "total_return_delta": round(n(gross55.get("total_return")) - n(production.get("total_return")), 6),
                "max_drawdown_delta": round(n(gross55.get("max_drawdown")) - n(production.get("max_drawdown")), 6),
                "avg_gross_exposure_delta": round(n(gross55.get("avg_gross_exposure")) - n(production.get("avg_gross_exposure")), 6),
            },
        },
        "daily_control": daily_control(production_path, gross55_path),
        "rolling_stability": (long_report.get("stability") or {}).get("rolling_vs_fixed40") or {},
        "regime_delta": regime_delta(long_report),
        "latest_allocation_shadow": allocation,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    comparison = payload["portfolio_comparison"]
    prod = comparison["production_fixed40"]
    gross = comparison["gross55_shadow"]
    deltas = comparison["deltas"]
    allocation = payload["latest_allocation_shadow"]
    rolling = payload["rolling_stability"]
    lines = [
        "# Gross55 Operational Shadow Dry-Run",
        "",
        f"- status: `{payload['status']}`",
        f"- shadow_status: `{payload['shadow_status']}`",
        f"- next_gate: `{payload['summary']['next_gate']}`",
        f"- latest_ranking: `{allocation.get('ranking_date')}`",
        f"- model_changed: `{payload['contract']['changes_model']}`",
        f"- production_ranking_changed: `{payload['contract']['changes_production_ranking']}`",
        "",
        "## Portfolio Comparison",
        "",
        f"- production fixed40: total {pct(prod.get('total_return'))}, DD {pct(prod.get('max_drawdown'))}",
        f"- gross55 shadow: total {pct(gross.get('total_return'))}, DD {pct(gross.get('max_drawdown'))}",
        f"- delta: return {pct(deltas.get('total_return_delta'))}, DD {pct(deltas.get('max_drawdown_delta'))}",
        "",
        "## Rolling Stability",
        "",
        f"- gross55 40D drawdown improve rate: {pct((rolling.get('gross55_40d') or {}).get('candidate_drawdown_improves_rate'))}",
        f"- gross55 80D drawdown improve rate: {pct((rolling.get('gross55_80d') or {}).get('candidate_drawdown_improves_rate'))}",
        f"- gross55 40D return beat rate: {pct((rolling.get('gross55_40d') or {}).get('candidate_return_beats_rate'))}",
        "",
        "## Latest Allocation",
        "",
        f"- latest market regime: `{allocation.get('latest_market_regime')}`",
        f"- entry weight changed on latest ranking: `{allocation.get('entry_weight_changed_on_latest_ranking')}`",
        f"- production target gross from latest ranking: {pct(allocation.get('production_target_gross_from_latest_ranking'))}",
        f"- gross55 target gross from latest ranking: {pct(allocation.get('gross55_shadow_target_gross_from_latest_ranking'))}",
        "",
        "## Boundary",
        "",
        "- 不改 Top10 名單。",
        "- 不改 `risk_adjusted_score`。",
        "- 不改正式推播。",
        "- 不覆蓋模型。",
        "",
    ]
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"gross55_operational_shadow_dry_run_{args.date}.json"
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "shadow_status": payload["shadow_status"],
                "output": repo_path(output),
                "next_gate": payload["summary"]["next_gate"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
