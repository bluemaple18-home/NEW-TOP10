#!/usr/bin/env python3
"""比較多個 overlap portfolio replay JSON。

這個工具只讀 `run_portfolio_replay.py` 已產出的 artifact，用來避免用肉眼
比較多份 md 摘要時漏掉回撤、曝險或交易數差異。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "portfolio-replay-variant-comparison.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="compare overlap portfolio replay variants")
    parser.add_argument(
        "--variant",
        action="append",
        required=True,
        help="格式 label=path/to/portfolio_replay.json；可重複指定，第一個當 baseline",
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
        raise FileNotFoundError(f"portfolio replay JSON 不存在：{path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("summary", {})


def numeric(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def delta(value: Any, baseline: Any) -> float | None:
    left = numeric(value)
    right = numeric(baseline)
    if left is None or right is None:
        return None
    return round(left - right, 6)


def compare(variants: list[tuple[str, Path]]) -> dict[str, Any]:
    loaded = [(label, path, load_summary(path)) for label, path in variants]
    baseline_label, _, baseline = loaded[0]
    rows = []
    for label, path, summary in loaded:
        rows.append(
            {
                "variant": label,
                "path": repo_path(path),
                "final_equity": numeric(summary.get("final_equity")),
                "total_return": numeric(summary.get("total_return")),
                "max_drawdown": numeric(summary.get("max_drawdown")),
                "win_rate": numeric(summary.get("win_rate")),
                "avg_trade_return": numeric(summary.get("avg_trade_return")),
                "trade_count": int(summary.get("trade_count") or 0),
                "skipped_count": int(summary.get("skipped_count") or 0),
                "avg_gross_exposure": numeric(summary.get("avg_gross_exposure")),
                "max_gross_exposure": numeric(summary.get("max_gross_exposure")),
                "delta_total_return": delta(summary.get("total_return"), baseline.get("total_return")),
                "delta_max_drawdown": delta(summary.get("max_drawdown"), baseline.get("max_drawdown")),
                "delta_avg_trade_return": delta(summary.get("avg_trade_return"), baseline.get("avg_trade_return")),
            }
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "reads_portfolio_replay_artifacts_only": True,
            "baseline_variant": baseline_label,
        },
        "variants": [{"label": label, "path": repo_path(path)} for label, path, _ in loaded],
        "rows": rows,
    }


def pct(value: float | None) -> str:
    if value is None:
        return "--"
    return f"{value:.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Portfolio Replay Variant Comparison",
        "",
        f"- baseline：{payload['contract']['baseline_variant']}",
        f"- variants：{len(payload['variants'])}",
        "",
        "| Variant | Total | Max DD | Win | Avg Trade | Trades | Skipped | Avg Exp | Δ Total | Δ DD |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for row in payload["rows"]:
        lines.append(
            "| {variant} | {total} | {dd} | {win} | {avg_trade} | {trades} | {skipped} | {avg_exp} | {delta_total} | {delta_dd} |".format(
                variant=row["variant"],
                total=pct(row["total_return"]),
                dd=pct(row["max_drawdown"]),
                win=pct(row["win_rate"]),
                avg_trade=pct(row["avg_trade_return"]),
                trades=row["trade_count"],
                skipped=row["skipped_count"],
                avg_exp=pct(row["avg_gross_exposure"]),
                delta_total=pct(row["delta_total_return"]),
                delta_dd=pct(row["delta_max_drawdown"]),
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
