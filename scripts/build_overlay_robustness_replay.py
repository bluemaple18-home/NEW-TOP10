#!/usr/bin/env python3
"""對固定 overlay replay 執行 paired moving-block bootstrap。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "overlay-historical-robustness-replay.v1"


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def percentile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    if not ordered:
        raise ValueError("percentile 不接受空序列")
    position = (len(ordered) - 1) * probability
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    fraction = position - lower
    return ordered[lower] * (1 - fraction) + ordered[upper] * fraction


def fold_stratified_circular_block_bootstrap_means(
    fold_values: list[list[float]],
    *,
    block_length: int,
    repetitions: int,
    seed: int,
) -> list[float]:
    if not fold_values or any(not values for values in fold_values):
        raise ValueError("bootstrap 不接受空序列")
    if block_length < 1 or repetitions < 1:
        raise ValueError("block_length 與 repetitions 必須為正整數")
    rng = random.Random(seed)
    total_size = sum(len(values) for values in fold_values)
    means = []
    for _ in range(repetitions):
        combined: list[float] = []
        for values in fold_values:
            size = len(values)
            sampled: list[float] = []
            while len(sampled) < size:
                start = rng.randrange(size)
                sampled.extend(values[(start + offset) % size] for offset in range(block_length))
            combined.extend(sampled[:size])
        means.append(sum(combined) / total_size)
    return means


def candidate_result(
    *,
    label: str,
    path: Path,
    variant: str,
    block_length: int,
    repetitions: int,
    seed: int,
) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    daily = payload.get("daily")
    if not isinstance(daily, list) or not daily:
        raise ValueError(f"{label} 缺少 daily replay rows")
    comparison = next(
        (row for row in payload.get("comparisons", []) if row.get("variant") == variant),
        None,
    )
    if comparison is None:
        raise ValueError(f"{label} 找不到 comparison variant：{variant}")

    rows = []
    for row in daily:
        baseline = (row.get("baseline") or {}).get("avg_net_return")
        overlay = (row.get(variant) or {}).get("avg_net_return")
        if baseline is None or overlay is None:
            continue
        rows.append(
            {
                "ranking_date": str(row["ranking_date"]),
                "fold": int(row["fold"]),
                "return_delta": float(overlay) - float(baseline),
            }
        )
    if len(rows) != int(comparison["baseline"]["date_count"]):
        raise ValueError(f"{label} paired rows 與 comparison date_count 不一致")
    rows.sort(key=lambda row: row["ranking_date"])
    values = [row["return_delta"] for row in rows]
    folds = sorted({row["fold"] for row in rows})
    bootstrap = fold_stratified_circular_block_bootstrap_means(
        [[row["return_delta"] for row in rows if row["fold"] == fold] for fold in folds],
        block_length=block_length,
        repetitions=repetitions,
        seed=seed,
    )
    leave_one_fold_out = []
    for fold in folds:
        kept = [row["return_delta"] for row in rows if row["fold"] != fold]
        leave_one_fold_out.append(
            {
                "excluded_fold": fold,
                "date_count": len(kept),
                "mean_return_delta": sum(kept) / len(kept),
            }
        )

    ci_low = percentile(bootstrap, 0.025)
    ci_high = percentile(bootstrap, 0.975)
    probability_positive = sum(value > 0 for value in bootstrap) / len(bootstrap)
    positive_lofo = sum(row["mean_return_delta"] > 0 for row in leave_one_fold_out)
    if ci_low > 0 and positive_lofo == len(leave_one_fold_out):
        decision = "ROBUST_HISTORICAL_SUPPORT"
    elif probability_positive >= 0.80 and positive_lofo >= 4:
        decision = "HISTORICAL_SUPPORT_UNCERTAIN"
    else:
        decision = "HISTORICAL_SUPPORT_WEAK"

    return {
        "label": label,
        "variant": variant,
        "source": str(path.relative_to(PROJECT_ROOT)),
        "source_sha256": file_sha256(path),
        "date_count": len(rows),
        "date_start": rows[0]["ranking_date"],
        "date_end": rows[-1]["ranking_date"],
        "observed_mean_return_delta": sum(values) / len(values),
        "positive_day_rate": sum(value > 0 for value in values) / len(values),
        "moving_block_bootstrap": {
            "block_length": block_length,
            "repetitions": repetitions,
            "seed": seed,
            "ci_95": [ci_low, ci_high],
            "probability_mean_positive": probability_positive,
        },
        "leave_one_fold_out": leave_one_fold_out,
        "positive_leave_one_fold_out_count": positive_lofo,
        "original_comparison": {
            "return_delta": comparison["return_delta"],
            "turnover_delta": comparison["turnover_delta"],
            "avg_max_group_exposure_delta": comparison["avg_max_group_exposure_delta"],
            "positive_fold_count": comparison["positive_fold_count"],
        },
        "decision": decision,
        "promotion_allowed": False,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Overlay Historical Robustness Replay",
        "",
        f"- block length：{payload['contract']['block_length']}",
        f"- repetitions：{payload['contract']['repetitions']}",
        f"- seed：{payload['contract']['seed']}",
        "- prospective acceptance replacement：false",
        "",
        "| Candidate | Days | Mean delta | 95% block-bootstrap CI | P(mean>0) | LOFO positive | Decision |",
        "|---|---:|---:|---:|---:|---:|---|",
    ]
    for row in payload["candidates"]:
        bootstrap = row["moving_block_bootstrap"]
        low, high = bootstrap["ci_95"]
        lines.append(
            f"| {row['label']} | {row['date_count']} | {row['observed_mean_return_delta']:.6f} "
            f"| [{low:.6f}, {high:.6f}] | {bootstrap['probability_mean_positive']:.3f} "
            f"| {row['positive_leave_one_fold_out_count']}/{len(row['leave_one_fold_out'])} "
            f"| {row['decision']} |"
        )
    lines.extend(
        [
            "",
            "本結果只描述既有歷史 replay 的不確定性；不得取代 seal 後 60 個 prospective OOS 日期。",
            "",
        ]
    )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build fixed overlay historical robustness replay")
    parser.add_argument(
        "--chip",
        default="artifacts/model_experiments/chip_point_in_time_portfolio_replay_2026-07-23.json",
    )
    parser.add_argument(
        "--event",
        default="artifacts/model_experiments/event_constrained_portfolio_replay_2026-07-23.json",
    )
    parser.add_argument(
        "--output",
        default="docs/evidence/OVERLAY-ROBUSTNESS-REPLAY-01/artifact.json",
    )
    parser.add_argument("--block-length", type=int, default=10)
    parser.add_argument("--repetitions", type=int, default=10000)
    parser.add_argument("--seed", type=int, default=20260723)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    candidates = [
        candidate_result(
            label="chip_overlay_0.10",
            path=resolve_path(args.chip),
            variant="chip_0.10",
            block_length=args.block_length,
            repetitions=args.repetitions,
            seed=args.seed,
        ),
        candidate_result(
            label="event_constrained_overlay_0.10",
            path=resolve_path(args.event),
            variant="event_0.10",
            block_length=args.block_length,
            repetitions=args.repetitions,
            seed=args.seed,
        ),
    ]
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "OK",
        "contract": {
            "paired_daily_delta": True,
            "bootstrap": "fold-stratified-circular-moving-block",
            "block_length": args.block_length,
            "repetitions": args.repetitions,
            "seed": args.seed,
            "confidence_interval": 0.95,
            "prospective_acceptance_replacement": False,
            "promotion_allowed": False,
        },
        "candidates": candidates,
    }
    output = resolve_path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": str(output), "decisions": {row["label"]: row["decision"] for row in candidates}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
