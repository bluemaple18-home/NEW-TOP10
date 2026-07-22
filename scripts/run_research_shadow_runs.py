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
    parser.add_argument("--feature-experiments-only", action="store_true", help="只產出 shadow feature experiment artifacts，不跑 ranking/replay")
    parser.add_argument("--feature-gate", default=None, help="feature experiment gate JSON；預設讀 config.feature_experiments.feature_gate")
    parser.add_argument("--shadow-candidates", default=None, help="逗號分隔 candidate ids；預設讀 config.feature_experiments.include_candidates")
    parser.add_argument("--exclude-candidates", default=None, help="逗號分隔本輪明確排除的 candidate ids")
    parser.add_argument("--run-date", default=None, help="artifact 日期，預設使用今天")
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


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


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


def csv_set(value: str | None) -> set[str]:
    if not value:
        return set()
    return {item.strip() for item in value.split(",") if item.strip()}


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


def build_manifest(
    config: dict[str, Any],
    variants: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    feature_experiments: list[dict[str, Any]] | None = None,
    excluded_feature_experiments: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    outputs = config.get("outputs", {})
    feature_experiments = feature_experiments or []
    excluded_feature_experiments = excluded_feature_experiments or []
    failed = any(step["status"] == "FAILED" for step in steps)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAILED" if failed else "OK",
        "contract": {
            "research_only": True,
            "does_not_fetch_data": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "production_artifact_policy": "writes only under configured shadow output dirs and comparison artifacts",
            "production_score_change_allowed": False,
            "production_promotion_allowed": False,
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
            "feature_experiments": [item.get("output") for item in feature_experiments],
            "feature_run_artifacts": [item.get("run_output") for item in feature_experiments],
        },
        "feature_experiments": feature_experiments,
        "excluded_feature_experiments": excluded_feature_experiments,
        "steps": steps,
    }


def gate_candidate_map(gate: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(item.get("id")): item for item in gate.get("candidates", []) if item.get("id")}


def candidate_list(config: dict[str, Any], args: argparse.Namespace) -> list[str]:
    configured = config.get("feature_experiments", {}).get("include_candidates", [])
    selected = [str(item) for item in configured if item]
    if args.shadow_candidates:
        selected = sorted(csv_set(args.shadow_candidates))
    if not selected:
        raise ValueError("沒有設定 shadow feature experiment candidates")
    return selected


def excluded_candidate_map(config: dict[str, Any], args: argparse.Namespace) -> dict[str, str]:
    configured = config.get("feature_experiments", {}).get("excluded_candidates", {}) or {}
    excluded = {str(key): str(value) for key, value in configured.items()}
    for candidate_id in csv_set(args.exclude_candidates):
        excluded[candidate_id] = "excluded by --exclude-candidates"
    return excluded


def resolve_feature_gate(config: dict[str, Any], args: argparse.Namespace) -> Path:
    value = args.feature_gate or config.get("feature_experiments", {}).get("feature_gate")
    if not value:
        raise ValueError("缺少 feature gate path")
    return resolve_path(value)


def feature_output_paths(config: dict[str, Any], candidate_id: str, run_date: str) -> tuple[Path, Path]:
    feature_config = config.get("feature_experiments", {})
    output_prefix = str(feature_config.get("output_prefix", "artifacts/shadow_feature_experiment"))
    run_output_prefix = str(feature_config.get("run_output_prefix", "artifacts/research_shadow_run"))
    return (
        resolve_path(f"{output_prefix}_{candidate_id}_{run_date}.json"),
        resolve_path(f"{run_output_prefix}_{candidate_id}_{run_date}.json"),
    )


def shadow_status(candidate: dict[str, Any]) -> str:
    if candidate.get("shadow_status") == "READY_FOR_SHADOW":
        return "READY_FOR_SHADOW"
    return "BLOCKED_BY_GATE"


def build_feature_experiment_payload(
    *,
    candidate_id: str,
    gate: dict[str, Any],
    gate_path: Path,
    candidate: dict[str, Any],
    output_path: Path,
    run_output_path: Path,
) -> dict[str, Any]:
    status = shadow_status(candidate)
    return {
        "schema_version": "shadow-feature-experiment.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_id": candidate_id,
        "status": status,
        "contract": {
            "research_only": True,
            "does_not_fetch_data": True,
            "does_not_train_model": True,
            "does_not_change_production_ranking": True,
            "does_not_write_production_ranking": True,
            "production_score_change_allowed": False,
            "production_promotion_allowed": False,
            "as_of_policy": "read existing feature gate and evidence artifacts; no future ranking or model feedback",
        },
        "inputs": {
            "feature_gate": repo_path(gate_path),
            "feature_gate_status": gate.get("status"),
            "source_candidate_status": candidate.get("shadow_status"),
            "source_candidate_label": candidate.get("label"),
        },
        "shadow_scope": {
            "allowed_shadow_uses": candidate.get("allowed_shadow_uses", []),
            "blocked_production_uses": candidate.get("blocked_production_uses", []),
            "promotion_requirements": candidate.get("promotion_requirements", []),
        },
        "evidence": candidate.get("evidence", {}),
        "blockers": candidate.get("blockers", []),
        "outputs": {
            "artifact": repo_path(output_path),
            "run_artifact": repo_path(run_output_path),
        },
    }


def build_feature_run_payload(experiment: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": "research-shadow-run.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate_id": experiment["candidate_id"],
        "status": experiment["status"],
        "contract": experiment["contract"],
        "inputs": experiment["inputs"],
        "outputs": {"shadow_feature_experiment": experiment["outputs"]["artifact"]},
        "steps": [
            {"name": "read_feature_gate", "status": "OK"},
            {
                "name": "write_shadow_feature_experiment",
                "status": "OK" if experiment["status"] == "READY_FOR_SHADOW" else "BLOCKED",
            },
        ],
        "blockers": experiment.get("blockers", []),
    }


def write_feature_experiments(config: dict[str, Any], args: argparse.Namespace) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    run_date = args.run_date or datetime.now().strftime("%Y-%m-%d")
    gate_path = resolve_feature_gate(config, args)
    gate = load_json(gate_path)
    if gate.get("schema_version") != "feature-experiment-gate.v1":
        raise ValueError(f"不支援的 feature gate schema：{gate.get('schema_version')}")
    candidates = gate_candidate_map(gate)
    excluded = excluded_candidate_map(config, args)
    results: list[dict[str, Any]] = []
    excluded_results: list[dict[str, Any]] = []
    for candidate_id, reason in sorted(excluded.items()):
        source = candidates.get(candidate_id, {})
        excluded_results.append(
            {
                "candidate_id": candidate_id,
                "reason": reason,
                "source_candidate_status": source.get("shadow_status"),
            }
        )
    for candidate_id in candidate_list(config, args):
        if candidate_id in excluded:
            continue
        candidate = candidates.get(candidate_id)
        if candidate is None:
            raise ValueError(f"feature gate 缺少 candidate：{candidate_id}")
        output_path, run_output_path = feature_output_paths(config, candidate_id, run_date)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        run_output_path.parent.mkdir(parents=True, exist_ok=True)
        experiment = build_feature_experiment_payload(
            candidate_id=candidate_id,
            gate=gate,
            gate_path=gate_path,
            candidate=candidate,
            output_path=output_path,
            run_output_path=run_output_path,
        )
        run_payload = build_feature_run_payload(experiment)
        output_path.write_text(json.dumps(experiment, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        output_path.with_suffix(".md").write_text(render_feature_markdown(experiment), encoding="utf-8")
        run_output_path.write_text(json.dumps(run_payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        results.append(
            {
                "candidate_id": candidate_id,
                "status": experiment["status"],
                "source_candidate_status": candidate.get("shadow_status"),
                "output": repo_path(output_path),
                "run_output": repo_path(run_output_path),
                "blocker_count": len(experiment.get("blockers", [])),
            }
        )
    return results, excluded_results


def render_feature_markdown(payload: dict[str, Any]) -> str:
    lines = [
        f"# Shadow Feature Experiment: {payload['candidate_id']}",
        "",
        f"- status：`{payload['status']}`",
        f"- feature_gate：`{payload['inputs']['feature_gate']}`",
        f"- source_candidate_status：`{payload['inputs']['source_candidate_status']}`",
        "- production_score_change_allowed：`false`",
        "- does_not_train_model：`true`",
        "",
        "## Allowed Shadow Uses",
        "",
    ]
    for item in payload["shadow_scope"].get("allowed_shadow_uses", []):
        lines.append(f"- {item}")
    lines.extend(["", "## Blocked Production Uses", ""])
    for item in payload["shadow_scope"].get("blocked_production_uses", []):
        lines.append(f"- {item}")
    if payload.get("blockers"):
        lines.extend(["", "## Blockers", ""])
        for item in payload["blockers"]:
            lines.append(f"- {item}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    config_path = resolve_path(args.config)
    config = load_config(config_path)
    suffix = args.artifact_suffix
    if args.limit and not suffix:
        suffix = f"smoke_limit{args.limit}"
    config = apply_artifact_suffix(config, suffix)
    if args.feature_experiments_only:
        feature_results, excluded_feature_results = write_feature_experiments(config, args)
        manifest = build_manifest(
            config,
            variants=[],
            steps=[],
            feature_experiments=feature_results,
            excluded_feature_experiments=excluded_feature_results,
        )
        output_path = resolve_path(args.output or config["outputs"]["manifest"])
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
        print(
            json.dumps(
                {
                    "status": manifest["status"],
                    "output": repo_path(output_path),
                    "feature_experiments": [item["candidate_id"] for item in feature_results],
                    "excluded": [item["candidate_id"] for item in excluded_feature_results],
                },
                ensure_ascii=False,
            )
        )
        return 0 if manifest["status"] == "OK" else 1

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
