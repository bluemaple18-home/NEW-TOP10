#!/usr/bin/env python3
"""建立 chip-flow data contract。

此 contract 只定義資料語意與 promotion 邊界，不抓外部資料、不改模型、
不改 production ranking。正式訊號前必須另有 shadow replay 證據。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = "2026-06-06"
SCHEMA_VERSION = "chip-data-contract.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build chip-flow data contract")
    parser.add_argument("--output", default=f"artifacts/chip_data_contract_{RUN_DATE}.json")
    parser.add_argument("--markdown-output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def code_contains(path: Path, token: str) -> bool:
    return path.exists() and token in path.read_text(encoding="utf-8")


def build_payload() -> dict[str, Any]:
    fetcher_path = PROJECT_ROOT / "app" / "finmind_fetcher.py"
    integrator_path = PROJECT_ROOT / "app" / "finmind_integrator.py"
    volume_path = PROJECT_ROOT / "app" / "indicators" / "mixins" / "volume.py"

    institutional_fetch_ready = code_contains(fetcher_path, "taiwan_stock_institutional_investors")
    margin_fetch_ready = code_contains(fetcher_path, "taiwan_stock_margin_purchase_short_sale")
    institutional_integrated = all(
        code_contains(integrator_path, token) for token in ["foreign_buy", "trust_buy", "dealer_buy", "institutional_available"]
    )
    margin_integrated = all(
        code_contains(integrator_path, token)
        for token in ["margin_purchase_today_balance", "margin_purchase_balance_change", "margin_available"]
    )
    indicator_ready = all(code_contains(volume_path, token) for token in ["inst_buy_total", "inst_buy_ratio_", "trust_buy_days_"])

    checks = {
        "institutional_fetch_ready": institutional_fetch_ready,
        "margin_fetch_ready": margin_fetch_ready,
        "institutional_integrated": institutional_integrated,
        "margin_integrated": margin_integrated,
        "institutional_indicator_ready_if_source_columns_exist": indicator_ready,
    }
    status = "OK" if all(checks.values()) else "BLOCKED"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "contract": {
            "purpose": "authorize chip-flow shadow data preparation without changing production ranking",
            "research_only": True,
            "changes_model": False,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "does_not_send_push": True,
            "network_fetch_required_for_this_artifact": False,
            "source_policy": "FinMind runtime fetch is allowed only in ETL/shadow runs with coverage logging",
            "as_of_policy": {
                "minimum_lag_trading_days_for_daily_recommendation": 1,
                "rule": "T 日推薦不得使用 T 日盤後才發布的融資融券或法人資料；若 T-1 不可用，欄位保留 missing 並標 available=false。",
            },
            "missing_value_policy": {
                "missing_is_not_zero": True,
                "zero_requires_available_flag": True,
                "institutional_available_column": "institutional_available",
                "margin_available_column": "margin_available",
            },
            "promotion_boundary": {
                "allowed_now": ["shadow feature materialization", "warning-only replay", "coverage audit"],
                "blocked_now": ["production ranking score", "production LightGBM feature", "formal sell alert"],
            },
        },
        "sources": {
            "finmind_institutional_investors": {
                "api": "taiwan_stock_institutional_investors",
                "normalized_columns": ["foreign_buy", "trust_buy", "dealer_buy", "institutional_available"],
                "code": repo_path(fetcher_path),
            },
            "finmind_margin_purchase_short_sale": {
                "api": "taiwan_stock_margin_purchase_short_sale",
                "reference_columns": [
                    "MarginPurchaseBuy",
                    "MarginPurchaseSell",
                    "MarginPurchaseCashRepayment",
                    "MarginPurchaseTodayBalance",
                    "MarginPurchaseYesterdayBalance",
                    "ShortSaleBuy",
                    "ShortSaleSell",
                    "ShortSaleCashRepayment",
                    "ShortSaleTodayBalance",
                    "ShortSaleYesterdayBalance",
                ],
                "normalized_columns": [
                    "margin_purchase_buy",
                    "margin_purchase_sell",
                    "margin_purchase_cash_repayment",
                    "margin_purchase_today_balance",
                    "margin_purchase_yesterday_balance",
                    "margin_purchase_balance_change",
                    "short_sale_buy",
                    "short_sale_sell",
                    "short_sale_cash_repayment",
                    "short_sale_today_balance",
                    "short_sale_yesterday_balance",
                    "short_sale_balance_change",
                    "margin_available",
                ],
                "code": repo_path(fetcher_path),
            },
        },
        "materialization": {
            "integrator": repo_path(integrator_path),
            "scope_default": "top 200 stocks by average traded value",
            "raw_cache_required_before_promotion": True,
            "recommended_raw_cache_paths": [
                "data/raw/chip/institutional_investors_YYYY-MM-DD.csv",
                "data/raw/chip/margin_purchase_short_sale_YYYY-MM-DD.csv",
            ],
            "coverage_metrics_required": [
                "institutional_available_rate",
                "margin_available_rate",
                "available_rate_by_stock",
                "latest_asof_date",
            ],
        },
        "shadow_feature_candidates": [
            "foreign_net_buy_5d_ratio",
            "trust_buy_days_5d",
            "dealer_net_buy_5d_ratio",
            "margin_balance_change_20d",
            "margin_price_divergence",
            "margin_forced_exit_risk",
        ],
        "checks": checks,
        "decision": {
            "status": "CONTRACT_READY_FOR_SHADOW" if status == "OK" else "CONTRACT_BLOCKED",
            "production_status": "BLOCKED",
            "primary_read": (
                "資料契約可以支援 chip-flow shadow，但不能直接解除 production gate。"
                "下一步必須跑 coverage audit 與 warning-only replay。"
            ),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Chip Data Contract",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{payload['decision']['status']}`",
        f"- production_status: `{payload['decision']['production_status']}`",
        "",
        "## Primary Read",
        "",
        payload["decision"]["primary_read"],
        "",
        "## As-Of Policy",
        "",
        f"- minimum_lag_trading_days_for_daily_recommendation: `{payload['contract']['as_of_policy']['minimum_lag_trading_days_for_daily_recommendation']}`",
        f"- rule: {payload['contract']['as_of_policy']['rule']}",
        "",
        "## Missing Value Policy",
        "",
        "- missing is not zero",
        "- zero requires matching available flag",
        "",
        "## Normalized Columns",
        "",
        "### Institutional",
    ]
    lines.extend([f"- `{col}`" for col in payload["sources"]["finmind_institutional_investors"]["normalized_columns"]])
    lines.append("")
    lines.append("### Margin / Short Sale")
    lines.extend([f"- `{col}`" for col in payload["sources"]["finmind_margin_purchase_short_sale"]["normalized_columns"]])
    lines.extend(
        [
            "",
            "## Checks",
            "",
        ]
    )
    lines.extend([f"- {name}: `{value}`" for name, value in payload["checks"].items()])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output_path = resolve_path(args.output)
    markdown_path = resolve_path(args.markdown_output) if args.markdown_output else output_path.with_suffix(".md")
    payload = build_payload()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output_path), "markdown": repo_path(markdown_path)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
