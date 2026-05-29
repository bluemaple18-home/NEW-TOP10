#!/usr/bin/env python3
"""比較多個 strategy matrix artifact。

只讀 `run_backtest_strategy_matrix.py` 的輸出，不跑回測、不改 ranking。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "strategy-matrix-comparison.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="compare strategy matrix artifacts")
    parser.add_argument("--variant", action="append", required=True, help="格式 label=path/to/strategy_matrix.json")
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


def load_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"strategy matrix 不存在：{path}")
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def scenario_map(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("scenario_id")): row for row in payload.get("scenarios", []) if row.get("scenario_id")}


def best_by_horizon(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    horizons = sorted({int(row["horizon"]) for row in rows if row.get("horizon") is not None})
    for horizon in horizons:
        candidates = [row for row in rows if int(row.get("horizon")) == horizon and row.get("score") is not None]
        if not candidates:
            continue
        result.append(max(candidates, key=lambda row: float(row["score"])))
    return result


def compare(variants: list[tuple[str, Path]]) -> dict[str, Any]:
    loaded = [(label, path, load_payload(path)) for label, path in variants]
    baseline_label, _, baseline_payload = loaded[0]
    baseline_rows = scenario_map(baseline_payload)
    summaries = []
    rows = []
    common_scenarios = set(baseline_rows)
    for _, _, payload in loaded[1:]:
        common_scenarios &= set(scenario_map(payload))

    for label, path, payload in loaded:
        scenarios = payload.get("scenarios", [])
        best = scenarios[0] if scenarios else {}
        summaries.append(
            {
                "variant": label,
                "path": repo_path(path),
                "scenario_count": payload.get("summary", {}).get("scenario_count"),
                "positive_return_count": payload.get("summary", {}).get("positive_return_count"),
                "negative_return_count": payload.get("summary", {}).get("negative_return_count"),
                "best_scenario_id": best.get("scenario_id"),
                "best_horizon": best.get("horizon"),
                "best_total_return": safe_float(best.get("total_return")),
                "best_max_drawdown": safe_float(best.get("max_drawdown")),
                "best_win_rate": safe_float(best.get("win_rate")),
                "best_score": safe_float(best.get("score")),
            }
        )
        current_rows = scenario_map(payload)
        for scenario_id in sorted(common_scenarios):
            row = current_rows.get(scenario_id, {})
            base = baseline_rows.get(scenario_id, {})
            rows.append(
                {
                    "variant": label,
                    "scenario_id": scenario_id,
                    "horizon": row.get("horizon"),
                    "total_return": safe_float(row.get("total_return")),
                    "max_drawdown": safe_float(row.get("max_drawdown")),
                    "win_rate": safe_float(row.get("win_rate")),
                    "score": safe_float(row.get("score")),
                    "delta_total_return": delta(row.get("total_return"), base.get("total_return")),
                    "delta_max_drawdown": delta(row.get("max_drawdown"), base.get("max_drawdown")),
                    "delta_score": delta(row.get("score"), base.get("score")),
                }
            )

    horizon_best = []
    for label, path, payload in loaded:
        for row in best_by_horizon(payload.get("scenarios", [])):
            horizon_best.append(
                {
                    "variant": label,
                    "path": repo_path(path),
                    "scenario_id": row.get("scenario_id"),
                    "horizon": row.get("horizon"),
                    "total_return": safe_float(row.get("total_return")),
                    "max_drawdown": safe_float(row.get("max_drawdown")),
                    "win_rate": safe_float(row.get("win_rate")),
                    "score": safe_float(row.get("score")),
                    "exit_reason_counts": row.get("exit_reason_counts", {}),
                }
            )

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "reads_strategy_matrix_artifacts_only": True,
            "baseline_variant": baseline_label,
        },
        "variants": [{"label": label, "path": repo_path(path)} for label, path, _ in loaded],
        "summary": summaries,
        "best_by_horizon": horizon_best,
        "common_scenario_rows": rows,
    }


def delta(value: Any, baseline: Any) -> float | None:
    left = safe_float(value)
    right = safe_float(baseline)
    if left is None or right is None:
        return None
    return round(left - right, 6)


def pct(value: Any) -> str:
    parsed = safe_float(value)
    if parsed is None:
        return "--"
    return f"{parsed:.2%}"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Strategy Matrix Comparison",
        "",
        f"- baseline：{payload['contract']['baseline_variant']}",
        f"- variants：{len(payload['variants'])}",
        "",
        "## Best Variant Summary",
        "",
        "| Variant | Best Scenario | Horizon | Return | Max DD | Win | Score |",
        "|---|---|---:|---:|---:|---:|---:|",
    ]
    for row in payload["summary"]:
        lines.append(
            "| {variant} | {scenario} | {horizon} | {ret} | {dd} | {win} | {score} |".format(
                variant=row["variant"],
                scenario=row.get("best_scenario_id"),
                horizon=row.get("best_horizon"),
                ret=pct(row.get("best_total_return")),
                dd=pct(row.get("best_max_drawdown")),
                win=pct(row.get("best_win_rate")),
                score=row.get("best_score"),
            )
        )
    lines.extend(["", "## Best By Horizon", "", "| Variant | Horizon | Scenario | Return | Max DD | Win | Score |", "|---|---:|---|---:|---:|---:|---:|"])
    for row in payload["best_by_horizon"]:
        lines.append(
            "| {variant} | {horizon} | {scenario} | {ret} | {dd} | {win} | {score} |".format(
                variant=row["variant"],
                horizon=row["horizon"],
                scenario=row["scenario_id"],
                ret=pct(row.get("total_return")),
                dd=pct(row.get("max_drawdown")),
                win=pct(row.get("win_rate")),
                score=row.get("score"),
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = compare([parse_variant(value) for value in args.variant])
    output_path = resolve_path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": repo_path(output_path), "variants": len(payload["variants"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
