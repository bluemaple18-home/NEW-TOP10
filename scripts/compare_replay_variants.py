#!/usr/bin/env python3
"""比較多個 replay JSON 的 horizon 與投組摘要。

此腳本只讀既有 replay artifact，方便把 current / shadow variants 放在同一張表檢查。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "replay-variant-comparison.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="compare replay JSON variants")
    parser.add_argument(
        "--variant",
        action="append",
        required=True,
        help="格式 label=path/to/replay.json；可重複指定",
    )
    parser.add_argument("--output", required=True, help="輸出 JSON")
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def parse_variant(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise ValueError("--variant 需使用 label=path 格式")
    label, path_text = value.split("=", 1)
    label = label.strip()
    if not label:
        raise ValueError("variant label 不可空白")
    return label, resolve_path(path_text.strip())


def load_summary(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"replay JSON 不存在：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("summary", {})


def metric_delta(value: float | None, baseline: float | None) -> float | None:
    if value is None or baseline is None:
        return None
    return round(float(value) - float(baseline), 6)


def numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def compare(variants: list[tuple[str, Path]]) -> dict[str, Any]:
    loaded = [(label, path, load_summary(path)) for label, path in variants]
    baseline = loaded[0][2]
    horizons = sorted(
        {
            str(horizon)
            for _, _, summary in loaded
            for group_name in ["by_horizon", "portfolio_by_horizon"]
            for horizon in summary.get(group_name, {})
        },
        key=lambda value: int(value),
    )

    rows = []
    for label, path, summary in loaded:
        for horizon in horizons:
            trade = summary.get("by_horizon", {}).get(horizon, {})
            portfolio = summary.get("portfolio_by_horizon", {}).get(horizon, {})
            base_trade = baseline.get("by_horizon", {}).get(horizon, {})
            base_portfolio = baseline.get("portfolio_by_horizon", {}).get(horizon, {})
            rows.append(
                {
                    "variant": label,
                    "path": repo_path(path),
                    "horizon": int(horizon),
                    "trade_avg_net_return": numeric(trade.get("avg_net_return")),
                    "trade_hit_rate": numeric(trade.get("hit_rate")),
                    "trade_avg_mae": numeric(trade.get("avg_mae")),
                    "portfolio_avg_return": numeric(portfolio.get("avg_portfolio_return")),
                    "portfolio_hit_rate": numeric(portfolio.get("hit_rate")),
                    "portfolio_total_return": numeric(portfolio.get("total_compounded_return")),
                    "portfolio_max_drawdown": numeric(portfolio.get("max_drawdown")),
                    "delta_trade_avg_net_return": metric_delta(
                        numeric(trade.get("avg_net_return")),
                        numeric(base_trade.get("avg_net_return")),
                    ),
                    "delta_portfolio_avg_return": metric_delta(
                        numeric(portfolio.get("avg_portfolio_return")),
                        numeric(base_portfolio.get("avg_portfolio_return")),
                    ),
                    "delta_portfolio_max_drawdown": metric_delta(
                        numeric(portfolio.get("max_drawdown")),
                        numeric(base_portfolio.get("max_drawdown")),
                    ),
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "reads_replay_artifacts_only": True,
            "baseline_variant": loaded[0][0],
        },
        "variants": [{"label": label, "path": repo_path(path)} for label, path, _ in loaded],
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Replay Variant Comparison",
        "",
        f"- baseline：{payload['contract']['baseline_variant']}",
        f"- variants：{len(payload['variants'])}",
        "",
        "| Variant | Horizon | Trade Avg | Trade Hit | Portfolio Avg | Portfolio Hit | Total | Max DD | Δ Avg | Δ Max DD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {variant} | {horizon} | {trade_avg_net_return:.2%} | {trade_hit_rate:.2%} | "
            "{portfolio_avg_return:.2%} | {portfolio_hit_rate:.2%} | {portfolio_total_return:.2%} | "
            "{portfolio_max_drawdown:.2%} | {delta_portfolio_avg_return:.2%} | {delta_portfolio_max_drawdown:.2%} |".format(
                **row
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    variants = [parse_variant(value) for value in args.variant]
    payload = compare(variants)
    output_path = resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output_path), "rows": len(payload["rows"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
