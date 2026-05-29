#!/usr/bin/env python3
"""依設定檔執行 shadow-only research runs。

此 runner 只產生研究 ranking/replay/diagnostics/comparison artifacts。
它不寫 production `artifacts/ranking_YYYY-MM-DD.csv`，不訓練模型，也不改 production 設定。
"""

from __future__ import annotations

import argparse
import copy
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "research-shadow-run-manifest.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run configured research shadow rankings and replay checks")
    parser.add_argument("--config", default="config/research_shadow_runs.yaml")
    parser.add_argument("--limit", type=int, default=None, help="只跑最近 N 個 ranking 日期，用於 smoke test")
    parser.add_argument("--artifact-suffix", default=None, help="替所有輸出 artifact 加 suffix；--limit 預設自動使用 smoke_limitN")
    parser.add_argument("--skip-ranking", action="store_true", help="跳過 shadow ranking 生成，直接讀既有 ranking dirs")
    parser.add_argument("--skip-replay", action="store_true", help="跳過 replay/diagnostics，只跑 comparison/report")
    parser.add_argument("--only", default=None, help="逗號分隔 variant id，只跑指定 variants")
    parser.add_argument("--output", default=None, help="覆蓋 manifest 輸出路徑")
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def load_config(path: Path) -> dict[str, Any]:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if payload.get("schema_version") != "research-shadow-runs.v1":
        raise ValueError(f"不支援的 shadow run config schema：{payload.get('schema_version')}")
    return payload


def suffixed_path(value: str, suffix: str, *, directory: bool = False) -> str:
    path = Path(value)
    if directory or not path.suffix:
        return str(path.with_name(f"{path.name}_{suffix}"))
    return str(path.with_name(f"{path.stem}_{suffix}{path.suffix}"))


def apply_artifact_suffix(config: dict[str, Any], suffix: str | None) -> dict[str, Any]:
    if not suffix:
        return config
    result = copy.deepcopy(config)
    for variant in result.get("variants", []):
        variant["output_dir"] = suffixed_path(str(variant["output_dir"]), suffix, directory=True)
        variant["replay_output"] = suffixed_path(str(variant["replay_output"]), suffix)
        variant["diagnostics_output"] = suffixed_path(str(variant["diagnostics_output"]), suffix)
    outputs = result.get("outputs", {})
    for key, value in list(outputs.items()):
        outputs[key] = suffixed_path(str(value), suffix)
    return result


def enabled_variants(config: dict[str, Any], only: str | None) -> list[dict[str, Any]]:
    requested = {item.strip() for item in only.split(",")} if only else None
    variants = []
    for item in config.get("variants", []):
        if not item.get("enabled", True):
            continue
        if requested is not None and item.get("id") not in requested:
            continue
        variants.append(item)
    if not variants:
        raise ValueError("沒有可執行的 shadow variants")
    return variants


def run_step(name: str, command: list[str]) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    completed = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    ended = datetime.now(timezone.utc)
    return {
        "name": name,
        "status": "OK" if completed.returncode == 0 else "FAILED",
        "returncode": completed.returncode,
        "started_at": started.isoformat(),
        "ended_at": ended.isoformat(),
        "command": command,
        "stdout_tail": completed.stdout[-3000:],
        "stderr_tail": completed.stderr[-3000:],
    }


def ranking_command(config: dict[str, Any], variant: dict[str, Any], limit: int | None) -> list[str]:
    command = [
        sys.executable,
        "scripts/research_regime_shadow_ranking.py",
        "--dates-from-dir",
        config["dates_from_dir"],
        "--output-dir",
        variant["output_dir"],
        "--market-regime-history",
        config["market_regime_history"],
        "--industry-map",
        config["industry_map"],
        "--risk-profile",
        variant["risk_profile"],
    ]
    if limit:
        command.extend(["--limit", str(limit)])
    return command


def replay_command(config: dict[str, Any], variant: dict[str, Any]) -> list[str]:
    return [
        sys.executable,
        "scripts/run_backtest_replay.py",
        "--rankings-dir",
        variant["output_dir"],
        "--features",
        config["features"],
        "--top-n",
        str(config.get("top_n", 10)),
        "--output",
        variant["replay_output"],
    ]


def diagnostics_command(config: dict[str, Any], variant: dict[str, Any]) -> list[str]:
    return [
        sys.executable,
        "scripts/research_replay_diagnostics.py",
        "--replay",
        variant["replay_output"],
        "--sealed-start",
        config["sealed_start"],
        "--sealed-end",
        config["sealed_end"],
        "--market-regime-history",
        config["market_regime_history"],
        "--output",
        variant["diagnostics_output"],
    ]


def replay_variant_args(config: dict[str, Any], variants: list[dict[str, Any]]) -> list[str]:
    args = ["--variant", f"{config['baseline']['id']}={config['baseline']['replay_output']}"]
    for variant in variants:
        args.extend(["--variant", f"{variant['id']}={variant['replay_output']}"])
    return args


def comparison_steps(config: dict[str, Any], variants: list[dict[str, Any]]) -> list[tuple[str, list[str]]]:
    outputs = config.get("outputs", {})
    variant_args = replay_variant_args(config, variants)
    return [
        (
            "compare_replay_variants",
            [
                sys.executable,
                "scripts/compare_replay_variants.py",
                *variant_args,
                "--output",
                outputs["replay_comparison"],
            ],
        ),
        (
            "build_replay_window_stability",
            [
                sys.executable,
                "scripts/build_replay_window_stability.py",
                *variant_args,
                "--windows",
                str(config.get("windows", 2)),
                "--output",
                outputs["window_stability"],
            ],
        ),
        (
            "build_weekend_research_decision_report",
            [
                sys.executable,
                "scripts/build_weekend_research_decision_report.py",
                "--replay-comparison",
                outputs["replay_comparison"],
                "--window-stability",
                outputs["window_stability"],
                "--output",
                outputs["decision_report"],
            ],
        ),
    ]


def build_manifest(config: dict[str, Any], variants: list[dict[str, Any]], steps: list[dict[str, Any]]) -> dict[str, Any]:
    outputs = config.get("outputs", {})
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if all(step["status"] == "OK" for step in steps) else "FAILED",
        "contract": {
            "research_only": True,
            "does_not_fetch_data": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_artifact_policy": "writes only under configured shadow output dirs and comparison artifacts",
        },
        "inputs": {
            "window_id": config.get("window_id"),
            "dates_from_dir": config.get("dates_from_dir"),
            "features": config.get("features"),
            "market_regime_history": config.get("market_regime_history"),
            "variants": [
                {
                    "id": variant.get("id"),
                    "risk_profile": variant.get("risk_profile"),
                    "output_dir": variant.get("output_dir"),
                    "replay_output": variant.get("replay_output"),
                    "diagnostics_output": variant.get("diagnostics_output"),
                }
                for variant in variants
            ],
        },
        "outputs": {
            "replay_comparison": outputs.get("replay_comparison"),
            "window_stability": outputs.get("window_stability"),
            "decision_report": outputs.get("decision_report"),
        },
        "steps": steps,
    }


def main() -> int:
    args = parse_args()
    config_path = resolve_path(args.config)
    config = load_config(config_path)
    suffix = args.artifact_suffix
    if args.limit and not suffix:
        suffix = f"smoke_limit{args.limit}"
    config = apply_artifact_suffix(config, suffix)
    variants = enabled_variants(config, args.only)
    steps: list[dict[str, Any]] = []

    if not args.skip_ranking:
        for variant in variants:
            steps.append(run_step(f"ranking.{variant['id']}", ranking_command(config, variant, args.limit)))

    if not args.skip_replay:
        for variant in variants:
            steps.append(run_step(f"replay.{variant['id']}", replay_command(config, variant)))
            steps.append(run_step(f"diagnostics.{variant['id']}", diagnostics_command(config, variant)))

    for name, command in comparison_steps(config, variants):
        steps.append(run_step(name, command))

    manifest = build_manifest(config, variants, steps)
    output_path = resolve_path(args.output or config["outputs"]["manifest"])
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "output": repo_path(output_path),
                "variants": [variant["id"] for variant in variants],
                "steps": len(steps),
            },
            ensure_ascii=False,
        )
    )
    return 0 if manifest["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
