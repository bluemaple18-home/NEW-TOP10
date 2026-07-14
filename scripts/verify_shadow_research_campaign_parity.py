#!/usr/bin/env python3
"""以 synthetic fixture 重建 shadow research campaign old/new parity 證據。

舊入口直接從固定 baseline commit 的 Git object 載入；所有 stage subprocess
都由本 harness 攔截，不會執行 replay、ranking 或 training。
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import subprocess
import sys
import tempfile
import types
from pathlib import Path
from typing import Any, Sequence

import run_shadow_research_campaign as current


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_COMMIT = "9748b95"
RUN_DATE = "2026-06-18"
DEFAULT_OUTPUT = PROJECT_ROOT / ".work/CLEANUP-35/evidence/parity.json"
STAGES = (
    "a1-forward",
    "candidate-stress",
    "overnight-training",
    "risk-matrix-summary",
)
CASES = ("valid", "missing", "failure")
LEGACY_PATHS = {
    "a1-forward": "scripts/run_a1_forward_shadow_monitor.py",
    "candidate-stress": "scripts/run_candidate_stress_matrix.py",
    "overnight-training": "scripts/run_overnight_shadow_training.py",
    "risk-matrix-summary": "scripts/build_overnight_risk_matrix_summary.py",
}
TIMESTAMP_KEYS = {"generated_at", "started_at", "finished_at", "ended_at"}


def load_legacy_modules() -> dict[str, types.ModuleType]:
    """從固定 Git baseline 載入四支 frozen legacy entrypoint。"""
    modules: dict[str, types.ModuleType] = {}
    for index, (stage, path) in enumerate(LEGACY_PATHS.items()):
        completed = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "show", f"{BASELINE_COMMIT}:{path}"],
            check=True,
            capture_output=True,
            text=True,
        )
        name = f"_shadow_parity_legacy_{index}"
        module = types.ModuleType(name)
        module.__file__ = str(PROJECT_ROOT / path)
        sys.modules[name] = module
        exec(compile(completed.stdout, module.__file__, "exec"), module.__dict__)
        modules[stage] = module
    return modules


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def seed_a1(root: Path, valid: bool) -> None:
    if not valid:
        return
    base = root / "artifacts/backtest"
    shadow = base / f"shadow_rankings_a1_sector_context_forward_{RUN_DATE}"
    constrained = base / f"shadow_rankings_a1_sector_context_production_top7_shadow_fill3_forward_{RUN_DATE}"
    write_json(shadow / "regime_shadow_ranking.json", {"outputs": [1, 2], "inputs": {"date_count": 2}})
    write_json(constrained / "constrained_shadow_ranking.json", {"summary": {"date_count": 2, "avg_overlap_count": 7.5}})
    write_json(base / f"portfolio_a1_baseline_forward_top10_h5_d1_gc25_{RUN_DATE}.json", {"summary": {"trade_count": 4}})
    write_json(
        base / f"portfolio_a1_sector_context_production_top7_shadow_fill3_forward_top10_h5_d1_gc25_{RUN_DATE}.json",
        {
            "summary": {
                "trade_count": 3,
                "skipped_count": 1,
                "total_return": 0.12,
                "max_drawdown": -0.03,
            },
            "skipped": [{"ranking_date": "2026-06-17", "reason": "pending"}],
        },
    )


def seed_stress(root: Path, module: types.ModuleType, valid: bool) -> None:
    if not valid:
        return
    for scenario_index, scenario in enumerate(module.SCENARIOS):
        for variant_index, variant in enumerate(module.VARIANTS):
            write_json(
                root
                / "artifacts/backtest"
                / f"portfolio_stress_{variant.name}_{scenario.name}_{RUN_DATE}.json",
                {
                    "summary": {
                        "total_return": 0.10 + scenario_index / 1000 + variant_index / 100,
                        "max_drawdown": -0.10 + scenario_index / 1000 + variant_index / 200,
                    }
                },
            )


def seed_risk(root: Path, valid: bool) -> str:
    model = root / "model.pkl"
    model.parent.mkdir(parents=True, exist_ok=True)
    model.write_bytes(b"synthetic-model-fixture")
    model_hash = hashlib.sha256(model.read_bytes()).hexdigest()
    if valid:
        matrices = {
            "baseline": (0.10, -0.10, 1.0),
            "sector_context_k7": (0.12, -0.08, 2.0),
            "feature_group_k7": (0.11, -0.09, 1.8),
            "feature_group_k8": (0.09, -0.07, 1.6),
        }
        for name, (total_return, drawdown, score) in matrices.items():
            write_json(
                root / f"artifacts/backtest/strategy_matrix_{name}_half_year_dense_{RUN_DATE}.json",
                {
                    "summary": {},
                    "scenarios": [
                        {
                            "scenario_id": name,
                            "total_return": total_return,
                            "max_drawdown": drawdown,
                            "score": score,
                            "win_rate": 0.6,
                        }
                    ],
                },
            )
    return model_hash


def cli_args(stage: str, case: str, root: Path, legacy: bool, model_hash: str) -> list[str]:
    output = root / "stage-output.json"
    if stage == "a1-forward":
        args = ["--date", RUN_DATE, "--output", str(output)]
    elif stage == "candidate-stress":
        args = ["--date", RUN_DATE, "--output", str(output)]
        if case == "missing":
            args.append("--dry-run")
    elif stage == "overnight-training":
        args = [
            "--date",
            RUN_DATE,
            "--model-hash-before",
            "synthetic-hash",
            "--keeps",
            "6",
            "--output",
            str(output),
            "--steps-log",
            str(root / "steps.tsv"),
        ]
    else:
        supplied_hash = "mutated-hash" if case == "failure" else model_hash
        args = [
            "--date",
            RUN_DATE,
            "--model",
            str(root / "model.pkl"),
            "--model-hash-before",
            supplied_hash,
            "--output",
            str(output),
        ]
    return args if legacy else [stage, *args]


def failure_settings(stage: str, case: str) -> tuple[int | None, int]:
    if case == "failure":
        return {"a1-forward": 2, "candidate-stress": 2, "overnight-training": 3}.get(stage), 9
    if case == "missing" and stage == "overnight-training":
        return 1, 2
    return None, 0


def normalize(value: Any, root: Path) -> Any:
    if isinstance(value, dict):
        return {
            key: normalize(item, root)
            for key, item in value.items()
            if key not in TIMESTAMP_KEYS
        }
    if isinstance(value, list):
        return [normalize(item, root) for item in value]
    if isinstance(value, str):
        return value.replace(str(root), "<ROOT>")
    return value


def normalize_tsv(path: Path) -> list[list[str]]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        rows.append([fields[0], fields[1], fields[4]])
    return rows


def embedded_commands(payload: dict[str, Any] | None) -> list[list[str]]:
    if not payload:
        return []
    rows = payload.get("steps") or payload.get("rows") or []
    return [row["command"] for row in rows if isinstance(row, dict) and row.get("command")]


def execute_stage(
    module: types.ModuleType,
    stage: str,
    case: str,
    *,
    legacy: bool,
) -> dict[str, Any]:
    with tempfile.TemporaryDirectory(prefix=f"shadow-parity-{stage}-") as temp_dir:
        root = Path(temp_dir).resolve()
        if stage == "a1-forward":
            seed_a1(root, case != "missing")
        elif stage == "candidate-stress":
            seed_stress(root, module, case == "valid")
        model_hash = seed_risk(root, case != "missing") if stage == "risk-matrix-summary" else ""
        argv = cli_args(stage, case, root, legacy, model_hash)
        failure_index, failure_code = failure_settings(stage, case)
        calls: list[list[str]] = []

        def fake_run(command: Sequence[str], **kwargs: Any) -> types.SimpleNamespace:
            normalized_command = [str(item) for item in command]
            calls.append(normalized_command)
            returncode = failure_code if failure_index == len(calls) else 0
            if returncode and kwargs.get("check"):
                raise subprocess.CalledProcessError(returncode, normalized_command)
            return types.SimpleNamespace(
                returncode=returncode,
                stdout=f"stdout-{len(calls)}",
                stderr=f"stderr-{len(calls)}",
            )

        old_root = module.PROJECT_ROOT
        old_subprocess = getattr(module, "subprocess", None)
        module.PROJECT_ROOT = root
        if old_subprocess is not None:
            module.subprocess = types.SimpleNamespace(
                run=fake_run,
                PIPE=subprocess.PIPE,
                CalledProcessError=subprocess.CalledProcessError,
            )
        stdout = io.StringIO()
        old_argv = sys.argv
        try:
            sys.argv = [str(module.__file__), *argv]
            with contextlib.redirect_stdout(stdout):
                try:
                    exit_code = int(module.main() if legacy else module.main(argv))
                except subprocess.CalledProcessError:
                    exit_code = 1
        finally:
            sys.argv = old_argv
            module.PROJECT_ROOT = old_root
            if old_subprocess is not None:
                module.subprocess = old_subprocess

        output = root / "stage-output.json"
        payload = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
        markdown_path = output.with_suffix(".md")
        console_text = stdout.getvalue().strip()
        console = json.loads(console_text) if console_text else None
        bundle = {
            "json": normalize(payload, root),
            "markdown": markdown_path.read_text(encoding="utf-8") if markdown_path.exists() else None,
            "tsv": normalize_tsv(root / "steps.tsv"),
            "console": normalize(console, root),
            "exit_code": exit_code,
            "command_order": {
                "executed": normalize(calls, root),
                "artifact": normalize(embedded_commands(payload), root),
            },
        }
        canonical = json.dumps(bundle, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return {"bundle": bundle, "sha256": hashlib.sha256(canonical.encode()).hexdigest()}


def compare_case(old: dict[str, Any], new: dict[str, Any]) -> dict[str, Any]:
    old_bundle = old["bundle"]
    new_bundle = new["bundle"]
    comparisons = {
        "normalized_json": old_bundle["json"] == new_bundle["json"],
        "exact_markdown": old_bundle["markdown"] == new_bundle["markdown"],
        "normalized_tsv": old_bundle["tsv"] == new_bundle["tsv"],
        "console_json": old_bundle["console"] == new_bundle["console"],
        "exit_code": old_bundle["exit_code"] == new_bundle["exit_code"],
        "command_order": old_bundle["command_order"] == new_bundle["command_order"],
    }
    return {
        "status": "PASS" if all(comparisons.values()) else "FAIL",
        "comparisons": comparisons,
        "old_sha256": old["sha256"],
        "new_sha256": new["sha256"],
        "exit_code": new_bundle["exit_code"],
        "executed_command_count": len(new_bundle["command_order"]["executed"]),
        "artifact_command_count": len(new_bundle["command_order"]["artifact"]),
    }


def run_suite(
    *,
    stages: Sequence[str] = STAGES,
    cases: Sequence[str] = CASES,
    legacy_modules: dict[str, types.ModuleType] | None = None,
) -> dict[str, Any]:
    legacy_modules = legacy_modules or load_legacy_modules()
    results: dict[str, Any] = {}
    for stage in stages:
        stage_results = {}
        for case in cases:
            old = execute_stage(legacy_modules[stage], stage, case, legacy=True)
            new = execute_stage(current, stage, case, legacy=False)
            stage_results[case] = compare_case(old, new)
        results[stage] = stage_results
    passed = all(
        result["status"] == "PASS"
        for stage_results in results.values()
        for result in stage_results.values()
    )
    return {"status": "PASS" if passed else "FAIL", "stages": results}


def mutation_probe(legacy_modules: dict[str, types.ModuleType]) -> dict[str, Any]:
    """故意改動新 runner schema，證明 harness 會拒絕漂移。"""
    original = current.A1_SCHEMA_VERSION
    try:
        current.A1_SCHEMA_VERSION = f"{original}.mutation"
        result = run_suite(
            stages=("a1-forward",),
            cases=("valid",),
            legacy_modules=legacy_modules,
        )["stages"]["a1-forward"]["valid"]
    finally:
        current.A1_SCHEMA_VERSION = original
    detected = result["status"] == "FAIL" and not result["comparisons"]["normalized_json"]
    return {
        "status": "PASS" if detected else "FAIL",
        "mutation": "A1_SCHEMA_VERSION",
        "expected_parity_status": "FAIL",
        "observed_parity_status": result["status"],
        "detected_by": "normalized_json",
    }


def build_evidence() -> dict[str, Any]:
    legacy_modules = load_legacy_modules()
    suite = run_suite(legacy_modules=legacy_modules)
    mutation = mutation_probe(legacy_modules)
    status = "PASS" if suite["status"] == mutation["status"] == "PASS" else "FAIL"
    return {
        "schema_version": "shadow-research-campaign-parity.v2",
        "task_id": "CLEANUP-35-F1",
        "status": status,
        "baseline_commit": BASELINE_COMMIT,
        "method": {
            "legacy_source": f"git show {BASELINE_COMMIT}:<legacy-path>",
            "inputs": "synthetic valid/missing/failure fixtures",
            "subprocess": "mocked in-process; no replay, ranking or training command executed",
            "comparison": [
                "normalized JSON",
                "exact Markdown",
                "normalized TSV",
                "console JSON",
                "exit code",
                "executed and artifact command order",
            ],
            "real_replay_or_training_count": 0,
        },
        "stages": suite["stages"],
        "mutation_sensitivity": mutation,
    }


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify old/new shadow campaign parity")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    evidence = build_evidence()
    output = args.output if args.output.is_absolute() else PROJECT_ROOT / args.output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(evidence, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        output_label = str(output.relative_to(PROJECT_ROOT))
    except ValueError:
        output_label = str(output)
    print(json.dumps({"status": evidence["status"], "output": output_label}, ensure_ascii=False))
    return 0 if evidence["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
