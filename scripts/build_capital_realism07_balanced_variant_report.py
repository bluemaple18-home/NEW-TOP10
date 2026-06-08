#!/usr/bin/env python3
"""彙整 CAPITAL-REALISM-07 balanced sizing 對 ranking 變體的 replay。"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "capital-realism07-balanced-variant-report.v1"
RUN_DATE = "2026-06-05"
VARIANTS = ("current", "feature_k9", "sector_k9")
CASH_LEVELS = (300_000, 500_000, 1_000_000)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build CAPITAL-REALISM-07 balanced variant report")
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/capital_realism07_balanced_variant_report_{RUN_DATE}.json",
    )
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
        raise FileNotFoundError(f"artifact missing: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def number(value: Any) -> float:
    return 0.0 if value is None else float(value)


def load_run(variant: str, cash: int) -> dict[str, Any]:
    path = PROJECT_ROOT / "artifacts" / "backtest" / f"capital_realism07_balanced_{variant}_{cash}_{RUN_DATE}.json"
    payload = read_json(path)
    contract = payload.get("contract", {})
    inputs = payload.get("inputs", {})
    summary = payload.get("summary", {})
    return {
        "id": f"{variant}_{cash}",
        "path": repo_path(path),
        "variant": variant,
        "research_only": contract.get("research_only"),
        "changes_model": contract.get("changes_model"),
        "changes_ranking_score": contract.get("changes_ranking_score"),
        "buy_lot_size": contract.get("buy_lot_size"),
        "sell_lot_size": contract.get("sell_lot_size"),
        "rankings_dir": inputs.get("rankings_dir"),
        "initial_cash": cash,
        "max_position_pct": inputs.get("max_position_pct"),
        "max_open_positions": inputs.get("max_open_positions"),
        "max_new_positions_per_day": inputs.get("max_new_positions_per_day"),
        "total_return": summary.get("total_return"),
        "max_drawdown": summary.get("max_drawdown"),
        "trade_count": summary.get("trade_count"),
        "avg_cash_ratio": summary.get("avg_cash_ratio"),
    }


def summarize_variant(rows: list[dict[str, Any]]) -> dict[str, Any]:
    avg_return = sum(number(row["total_return"]) for row in rows) / len(rows)
    avg_drawdown = sum(number(row["max_drawdown"]) for row in rows) / len(rows)
    return {
        "avg_return": round(avg_return, 6),
        "avg_drawdown": round(avg_drawdown, 6),
        "min_return": round(min(number(row["total_return"]) for row in rows), 6),
        "worst_drawdown": round(min(number(row["max_drawdown"]) for row in rows), 6),
        "avg_cash_ratio": round(sum(number(row["avg_cash_ratio"]) for row in rows) / len(rows), 6),
        "avg_trade_count": round(sum(number(row["trade_count"]) for row in rows) / len(rows), 2),
        "risk_adjusted_return": round(avg_return / abs(avg_drawdown), 6) if avg_drawdown else None,
    }


def build_payload(_: argparse.Namespace) -> dict[str, Any]:
    runs = {f"{variant}_{cash}": load_run(variant, cash) for variant in VARIANTS for cash in CASH_LEVELS}
    by_variant = {
        variant: summarize_variant([row for row in runs.values() if row["variant"] == variant])
        for variant in VARIANTS
    }
    best_return = max(by_variant.items(), key=lambda item: item[1]["avg_return"])
    best_risk_adjusted = max(by_variant.items(), key=lambda item: item[1]["risk_adjusted_return"] or 0)
    current = by_variant["current"]
    deltas_vs_current = {
        variant: {
            "avg_return_delta": round(row["avg_return"] - current["avg_return"], 6),
            "avg_drawdown_delta": round(row["avg_drawdown"] - current["avg_drawdown"], 6),
            "risk_adjusted_delta": round((row["risk_adjusted_return"] or 0) - (current["risk_adjusted_return"] or 0), 6),
        }
        for variant, row in by_variant.items()
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "research_only": True,
            "changes_model": False,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "finite_capital": True,
            "odd_lot_default": True,
            "run_count": len(runs),
            "sizing_policy": "p12_open8_new2",
        },
        "runs": runs,
        "summary": {
            "by_variant": by_variant,
            "deltas_vs_current": deltas_vs_current,
            "best_return": {"variant": best_return[0], **best_return[1]},
            "best_risk_adjusted": {"variant": best_risk_adjusted[0], **best_risk_adjusted[1]},
        },
        "decision": {
            "status": "BALANCED_SIZING_ROBUST_RANKING_VARIANT_NOT_PROMOTED",
            "sizing_policy_candidate": "p12_open8_new2",
            "ranking_variant_promotion": False,
            "production_change": False,
            "primary_read": (
                "balanced sizing 套到 current / feature_k9 / sector_k9 都接近，表示資金規則本身穩；"
                "但 K9 變體沒有明顯贏過 current，所以本卡不支持 ranking variant 升版。"
            ),
            "next_experiments": [
                "把 p12_open8_new2 轉成每日推薦訊息的白話資金規則草案。",
                "保留 current ranking 作比較組，K9 只做 shadow evidence，不因本卡升版。",
            ],
        },
    }


def pct(value: Any) -> str:
    if value is None:
        return "--"
    return f"{float(value):.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# CAPITAL-REALISM-07 Balanced Variant Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- sizing_policy_candidate: `{payload['decision']['sizing_policy_candidate']}`",
        "",
        "## By Variant",
        "",
        "| variant | avg return | avg DD | risk-adjusted | avg cash | avg trades |",
        "| --- | ---: | ---: | ---: | ---: | ---: |",
    ]
    for variant, row in sorted(payload["summary"]["by_variant"].items()):
        lines.append(
            f"| {variant} | {pct(row['avg_return'])} | {pct(row['avg_drawdown'])} | "
            f"{row['risk_adjusted_return']} | {pct(row['avg_cash_ratio'])} | {row['avg_trade_count']} |"
        )
    lines.extend(
        [
            "",
            "## Decision",
            "",
            "```json",
            json.dumps(payload["decision"], ensure_ascii=False, indent=2),
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {"status": payload["status"], "output": repo_path(output), "decision": payload["decision"]["status"]},
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
