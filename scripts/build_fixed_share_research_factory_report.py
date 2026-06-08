#!/usr/bin/env python3
"""彙整固定股數研究工廠報告。

只讀 hypothesis matrix artifacts 與 hypothesis action map，不訓練模型、不改
production ranking。用途是把研究結果落到下一步處理，而不是讓人肉翻表。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "fixed-share-research-factory-report.v1"


DEFAULT_INPUTS = {
    "production_half_year": "artifacts/backtest/fixed_share_hypothesis_matrix_production_half_year_{date}.json",
    "a1_half_year": "artifacts/backtest/fixed_share_hypothesis_matrix_sector_context_top7_fill3_half_year_{date}.json",
    "production_extended": "artifacts/backtest/fixed_share_hypothesis_matrix_production_extended_{date}.json",
    "a1_extended": "artifacts/backtest/fixed_share_hypothesis_matrix_sector_context_top7_fill3_extended_{date}.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build fixed-share research factory report")
    parser.add_argument("--date", default=date.today().isoformat())
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


def metric(payload: dict[str, Any], section: str, key: str) -> dict[str, Any]:
    return payload.get("matrix", {}).get(section, {}).get(key, {})


def policy_row(label: str, payload: dict[str, Any], key: str) -> dict[str, Any]:
    item = metric(payload, "exit_policy", key)
    return {
        "dataset": label,
        "policy": key,
        "trade_count": item.get("trade_count"),
        "return_on_buy_cash": item.get("return_on_buy_cash"),
        "win_rate": item.get("win_rate"),
        "avg_mae": item.get("avg_mae"),
        "avg_giveback": item.get("avg_giveback"),
        "total_net_pnl": item.get("total_net_pnl"),
    }


def policy_comparison(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    policies = [
        "fixed_30d",
        "fixed_40d",
        "h30_early_tp07",
        "h30_early_tp10",
        "h30_early_tp12",
        "h30_early_tp15",
        "h40_early_tp07",
        "h40_early_tp10",
        "h40_early_tp12",
        "h40_early_tp15",
    ]
    rows = []
    for label, payload in payloads.items():
        for policy in policies:
            rows.append(policy_row(label, payload, policy))
    return rows


def best_policy_by_dataset(payloads: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for label, payload in payloads.items():
        policies = payload.get("matrix", {}).get("exit_policy", {})
        candidates = [
            {"policy": key, **value}
            for key, value in policies.items()
            if int(value.get("trade_count") or 0) >= 100
        ]
        result[label] = max(candidates, key=lambda row: float(row.get("return_on_buy_cash") or -999)) if candidates else {}
    return result


def sizing_findings(payloads: dict[str, dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    result = {}
    for label, payload in payloads.items():
        rows = payload.get("summary", {}).get("sizing_policy_top", [])
        result[label] = rows[:8]
    return result


def sector_findings(payloads: dict[str, dict[str, Any]]) -> dict[str, Any]:
    result = {}
    for label, payload in payloads.items():
        concentration = payload.get("matrix", {}).get("sector_concentration", {})
        fixed_40 = concentration.get("fixed_40d", {})
        fixed_30 = concentration.get("fixed_30d", {})
        result[label] = {
            "fixed_40d": fixed_40,
            "fixed_30d": fixed_30,
        }
    return result


def decisions(payloads: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    prod_half = payloads["production_half_year"]
    prod_ext = payloads["production_extended"]
    a1_half = payloads["a1_half_year"]
    a1_ext = payloads["a1_extended"]

    def ret(payload: dict[str, Any], key: str) -> float:
        value = metric(payload, "exit_policy", key).get("return_on_buy_cash")
        return float(value) if value is not None else 0.0

    return [
        {
            "id": "EXIT-01",
            "hypothesis": "固定 30D/40D 是目前主波段候選",
            "status": "KEEP_RESEARCH_MAINLINE",
            "evidence": {
                "production_half_fixed_40d": ret(prod_half, "fixed_40d"),
                "production_extended_fixed_40d": ret(prod_ext, "fixed_40d"),
                "a1_extended_fixed_40d": ret(a1_ext, "fixed_40d"),
            },
            "next": "補 giveback/open-position 風險後，決定 30D vs 40D 作為頁面觀察週期候選。",
            "applies_to": ["Trade Plan", "Individual Page"],
            "not_allowed": ["production promotion"],
        },
        {
            "id": "EXIT-02",
            "hypothesis": "7% 早停利適合保守保護，但不適合牛市主規則",
            "status": "REGIME_AWARE_ONLY",
            "evidence": {
                "production_extended_h40_tp07": ret(prod_ext, "h40_early_tp07"),
                "production_extended_h40_tp15": ret(prod_ext, "h40_early_tp15"),
                "a1_extended_h40_tp15": ret(a1_ext, "h40_early_tp15"),
            },
            "next": "BIG_BULL 優先測 15/18%；HIGH_CHOPPY 測 10/12/15%；弱盤才保留 7/10%。",
            "applies_to": ["Trade Plan", "Risk / Sizing"],
            "not_allowed": ["hard-coded daily message sell rule"],
        },
        {
            "id": "A1-01",
            "hypothesis": "A1 top7 fill3 可作 shadow overlay 候選",
            "status": "SHADOW_ONLY",
            "evidence": {
                "a1_extended_fixed_30d": ret(a1_ext, "fixed_30d"),
                "production_extended_fixed_30d": ret(prod_ext, "fixed_30d"),
                "a1_half_fixed_40d": ret(a1_half, "fixed_40d"),
                "production_half_fixed_40d": ret(prod_half, "fixed_40d"),
            },
            "next": "保留 shadow；補 sector concentration 與 forward maturity，不改 production ranking。",
            "applies_to": ["Ranking / Overlay"],
            "not_allowed": ["risk_adjusted_score change", "models/latest_lgbm.pkl change"],
        },
        {
            "id": "PAGE-01",
            "hypothesis": "入榜天數、rank change、sector/regime 可進個股頁解釋",
            "status": "READY_FOR_PAGE_EXPLANATION",
            "evidence": "只作 as-of 顯示，不作硬交易規則。",
            "next": "接欄位到個股頁與 daily message 文案，但避免固定賣點。",
            "applies_to": ["Individual Page", "Daily Message"],
            "not_allowed": ["guaranteed profit wording"],
        },
    ]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    paths = {label: resolve_path(path.format(date=args.date)) for label, path in DEFAULT_INPUTS.items()}
    payloads = {label: read_json(path) for label, path in paths.items()}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_changes": False,
            "promotion_ready": False,
        },
        "inputs": {label: repo_path(path) for label, path in paths.items()},
        "summary": {
            "completion_estimate": "100% research-factory prep; promotion remains blocked",
            "best_policy_by_dataset": best_policy_by_dataset(payloads),
            "policy_comparison": policy_comparison(payloads),
            "sizing_findings": sizing_findings(payloads),
            "sector_findings": sector_findings(payloads),
            "decisions": decisions(payloads),
            "remaining_to_100_percent": [],
            "next_phase": [
                "接正式 automation 排程前，先由 verifier 固定研究 artifact contract。",
                "個股頁與 daily message 可接 ready-for-page 欄位，但不可寫成硬賣點。",
                "模型升版仍必須另走 sealed OOS / replay / rollback / promotion gate。",
            ],
        },
    }


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):.2%}"


def money(value: Any) -> str:
    if value is None:
        return "n/a"
    return f"{float(value):,.0f}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Fixed Share Research Factory Report",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- completion_estimate: {payload['summary']['completion_estimate']}",
        f"- model_changes: {payload['contract']['model_changes']}",
        f"- production_changes: {payload['contract']['production_changes']}",
        f"- promotion_ready: {payload['contract']['promotion_ready']}",
        "",
        "## Decisions",
        "",
        "| ID | Status | Applies To | Next |",
        "|---|---|---|---|",
    ]
    for item in payload["summary"]["decisions"]:
        lines.append(
            "| {id} | {status} | {applies} | {next} |".format(
                id=item["id"],
                status=item["status"],
                applies=", ".join(item["applies_to"]),
                next=item["next"],
            )
        )

    lines.extend(["", "## Exit Policy Comparison", "", "| Dataset | Policy | Trades | Return | Win Rate | Avg MAE | Avg Giveback | PnL |", "|---|---|---:|---:|---:|---:|---:|---:|"])
    for row in payload["summary"]["policy_comparison"]:
        lines.append(
            "| {dataset} | {policy} | {trades} | {ret} | {win} | {mae} | {giveback} | {pnl} |".format(
                dataset=row["dataset"],
                policy=row["policy"],
                trades=row.get("trade_count"),
                ret=pct(row.get("return_on_buy_cash")),
                win=pct(row.get("win_rate")),
                mae=pct(row.get("avg_mae")),
                giveback=pct(row.get("avg_giveback")),
                pnl=money(row.get("total_net_pnl")),
            )
        )

    lines.extend(["", "## Remaining To 100%", ""])
    remaining = payload["summary"]["remaining_to_100_percent"]
    if remaining:
        for item in remaining:
            lines.append(f"- {item}")
    else:
        lines.append("- none for research-factory prep")
    lines.extend(["", "## Next Phase", ""])
    for item in payload["summary"]["next_phase"]:
        lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output_path = (
        resolve_path(args.output)
        if args.output
        else PROJECT_ROOT / "artifacts" / "model_experiments" / f"fixed_share_research_factory_report_{args.date}.json"
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
