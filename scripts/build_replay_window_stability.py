#!/usr/bin/env python3
"""檢查 replay variant 在不同日期窗口是否穩定。

只讀 `run_backtest_replay.py` 的 JSON，不重新回測、不改 ranking。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "replay-window-stability.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build replay window stability report")
    parser.add_argument("--variant", action="append", required=True, help="格式 label=path/to/replay.json")
    parser.add_argument("--windows", type=int, default=2)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
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


def load_replay(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"replay JSON 不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def split_dates(dates: list[str], windows: int) -> dict[str, set[str]]:
    if windows < 1:
        raise ValueError("--windows 必須 >= 1")
    ordered = sorted(set(dates))
    if not ordered:
        return {}
    result: dict[str, set[str]] = {}
    for index in range(windows):
        start = round(index * len(ordered) / windows)
        end = round((index + 1) * len(ordered) / windows)
        chunk = ordered[start:end]
        if not chunk:
            continue
        result[f"w{index + 1}_{chunk[0]}_{chunk[-1]}"] = set(chunk)
    return result


def safe_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def max_drawdown(returns: list[float]) -> float:
    equity = 1.0
    peak = 1.0
    worst = 0.0
    for value in returns:
        equity *= 1 + float(value)
        peak = max(peak, equity)
        worst = min(worst, equity / peak - 1)
    return round(worst, 6)


def summarize_returns(values: list[float]) -> dict[str, Any]:
    if not values:
        return {
            "count": 0,
            "avg_return": None,
            "hit_rate": None,
            "total_compounded_return": None,
            "max_drawdown": None,
        }
    total = 1.0
    for value in values:
        total *= 1 + value
    return {
        "count": len(values),
        "avg_return": round(sum(values) / len(values), 6),
        "hit_rate": round(sum(value > 0 for value in values) / len(values), 6),
        "total_compounded_return": round(total - 1, 6),
        "max_drawdown": max_drawdown(values),
    }


def window_rows(label: str, replay: dict[str, Any], windows: dict[str, set[str]]) -> list[dict[str, Any]]:
    trades = replay.get("trades", [])
    portfolio = replay.get("portfolio", {}).get("observations", [])
    horizons = sorted({int(item.get("horizon")) for item in trades if item.get("horizon") is not None})
    rows = []
    for window_label, date_set in windows.items():
        for horizon in horizons:
            trade_values = [
                safe_float(item.get("net_return"))
                for item in trades
                if item.get("ranking_date") in date_set and int(item.get("horizon") or 0) == horizon
            ]
            trade_values = [value for value in trade_values if value is not None]
            portfolio_values = [
                safe_float(item.get("portfolio_return"))
                for item in portfolio
                if item.get("ranking_date") in date_set and int(item.get("horizon") or 0) == horizon
            ]
            portfolio_values = [value for value in portfolio_values if value is not None]
            rows.append(
                {
                    "variant": label,
                    "window": window_label,
                    "horizon": horizon,
                    "trade": summarize_returns(trade_values),
                    "portfolio": summarize_returns(portfolio_values),
                }
            )
    return rows


def add_baseline_deltas(rows: list[dict[str, Any]], baseline_variant: str) -> None:
    baseline = {
        (row["window"], row["horizon"]): row
        for row in rows
        if row["variant"] == baseline_variant
    }
    for row in rows:
        base = baseline.get((row["window"], row["horizon"]))
        if not base:
            continue
        row["delta_vs_baseline"] = {
            "trade_avg_return": delta(row["trade"].get("avg_return"), base["trade"].get("avg_return")),
            "portfolio_avg_return": delta(row["portfolio"].get("avg_return"), base["portfolio"].get("avg_return")),
            "portfolio_max_drawdown": delta(row["portfolio"].get("max_drawdown"), base["portfolio"].get("max_drawdown")),
        }


def delta(value: Any, baseline: Any) -> float | None:
    left = safe_float(value)
    right = safe_float(baseline)
    if left is None or right is None:
        return None
    return round(left - right, 6)


def stability_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    variants = sorted({row["variant"] for row in rows if row["variant"] != "current"})
    horizons = sorted({row["horizon"] for row in rows})
    for variant in variants:
        for horizon in horizons:
            matches = [row for row in rows if row["variant"] == variant and row["horizon"] == horizon]
            deltas = [
                safe_float((row.get("delta_vs_baseline") or {}).get("portfolio_avg_return"))
                for row in matches
            ]
            deltas = [value for value in deltas if value is not None]
            dd_deltas = [
                safe_float((row.get("delta_vs_baseline") or {}).get("portfolio_max_drawdown"))
                for row in matches
            ]
            dd_deltas = [value for value in dd_deltas if value is not None]
            if not deltas:
                continue
            result.append(
                {
                    "variant": variant,
                    "horizon": horizon,
                    "windows": len(deltas),
                    "positive_avg_return_windows": sum(value > 0 for value in deltas),
                    "improved_drawdown_windows": sum(value > 0 for value in dd_deltas),
                    "min_portfolio_avg_return_delta": round(min(deltas), 6),
                    "avg_portfolio_avg_return_delta": round(sum(deltas) / len(deltas), 6),
                    "decision": stability_decision(deltas, dd_deltas),
                }
            )
    return result


def stability_decision(return_deltas: list[float], dd_deltas: list[float]) -> str:
    if return_deltas and all(value > 0 for value in return_deltas) and dd_deltas and all(value > 0 for value in dd_deltas):
        return "STABLE_SHADOW_CANDIDATE"
    if sum(value > 0 for value in return_deltas) >= max(1, len(return_deltas) - 1):
        return "PARTIAL_STABILITY"
    return "UNSTABLE"


def build_report(variants: list[tuple[str, Path]], windows_count: int) -> dict[str, Any]:
    loaded = [(label, path, load_replay(path)) for label, path in variants]
    all_dates = [
        str(item.get("ranking_date"))
        for _, _, replay in loaded
        for item in replay.get("trades", [])
        if item.get("ranking_date")
    ]
    windows = split_dates(all_dates, windows_count)
    rows: list[dict[str, Any]] = []
    for label, path, replay in loaded:
        rows.extend(window_rows(label, replay, windows))
    add_baseline_deltas(rows, baseline_variant=loaded[0][0])
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "reads_replay_artifacts_only": True,
            "baseline_variant": loaded[0][0],
            "window_policy": "equal sized ranking_date windows",
        },
        "variants": [{"label": label, "path": repo_path(path)} for label, path, _ in loaded],
        "windows": {label: sorted(values) for label, values in windows.items()},
        "summary": stability_summary(rows),
        "rows": rows,
    }


def pct(value: Any) -> str:
    parsed = safe_float(value)
    if parsed is None:
        return "--"
    return f"{parsed:.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Replay Window Stability",
        "",
        f"- baseline：{payload['contract']['baseline_variant']}",
        f"- windows：{len(payload['windows'])}",
        "",
        "## Summary",
        "",
        "| Variant | Horizon | Decision | Positive Windows | Drawdown Windows | Min Δ Avg | Avg Δ Avg |",
        "|---|---:|---|---:|---:|---:|---:|",
    ]
    for row in payload["summary"]:
        lines.append(
            "| {variant} | {horizon} | {decision} | {pos}/{windows} | {dd}/{windows} | {min_delta} | {avg_delta} |".format(
                variant=row["variant"],
                horizon=row["horizon"],
                decision=row["decision"],
                pos=row["positive_avg_return_windows"],
                dd=row["improved_drawdown_windows"],
                windows=row["windows"],
                min_delta=pct(row["min_portfolio_avg_return_delta"]),
                avg_delta=pct(row["avg_portfolio_avg_return_delta"]),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_report([parse_variant(value) for value in args.variant], args.windows)
    output_path = resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output_path), "rows": len(payload["rows"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
