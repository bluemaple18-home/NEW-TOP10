#!/usr/bin/env python3
"""以隔離 temp/shadow 目錄執行每日報牌 v2，不提供 live send。"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import pickle
import sys
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.contracts.daily_v2 import DailyStep, StepSpec  # noqa: E402
from app.workflows.daily_v2 import DailyWorkflowV2, WorkflowExecutionError  # noqa: E402
from app.workflows.daily_v2_real_shadow import (  # noqa: E402
    RealShadowExecutionError,
    run_real_shadow,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="執行每日報牌 v2 shadow-only dry-run")
    parser.add_argument("--dry-run", action="store_true", help="必要安全閘門；只產 publish-ready artifact")
    parser.add_argument(
        "--source",
        choices=("fixture", "real"),
        default="fixture",
        help="fixture 跑原隔離 smoke；real 唯讀正式 features／model 並與 baseline 比較",
    )
    parser.add_argument("--run-date", required=True, help="執行日期，格式 YYYY-MM-DD")
    parser.add_argument("--run-id", help="可續跑識別碼；預設依日期固定產生")
    parser.add_argument(
        "--workspace",
        type=Path,
        default=PROJECT_ROOT / "artifacts" / "shadow" / "daily_v2",
        help="shadow run 根目錄",
    )
    parser.add_argument("--step-timeout", type=float, default=30.0, help="各子程序 timeout 秒數")
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "data" / "clean")
    parser.add_argument("--model-dir", type=Path, default=PROJECT_ROOT / "models")
    parser.add_argument("--model-filename", default="latest_lgbm.pkl")
    parser.add_argument("--baseline-ranking", type=Path)
    parser.add_argument("--config", type=Path, default=PROJECT_ROOT / "config" / "signals.yaml")
    parser.add_argument("--numeric-tolerance", type=float, default=1e-9)
    args = parser.parse_args()
    if not args.dry_run:
        parser.error("REFACTOR-01 僅允許 --dry-run；live send 尚未整合")
    if args.source == "real" and args.baseline_ranking is None:
        parser.error("--source real 必須指定 --baseline-ranking")
    return args


def fixture_stage_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(add_help=False)
    parser.add_argument("stage", choices=[step.value for step in DailyStep])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--run-date", required=True)
    parser.add_argument("--model", type=Path, required=True)
    return parser.parse_args(argv)


def run_fixture_stage(argv: list[str]) -> int:
    """提供 CLI shadow smoke 的隔離子程序；不讀寫 production artifact。"""

    args = fixture_stage_args(argv)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    if args.stage == DailyStep.ETL.value:
        write_json(args.run_dir / "features.json", {"run_date": args.run_date, "rows": 20})
    elif args.stage == DailyStep.VALIDATE.value:
        features = read_json(args.run_dir / "features.json")
        with args.model.open("rb") as handle:
            pickle.load(handle)
        write_json(
            args.run_dir / "validation.json",
            {"run_date": features.get("run_date"), "valid": True},
        )
    elif args.stage == DailyStep.RANK.value:
        validation = read_json(args.run_dir / "validation.json")
        if validation.get("valid") is not True:
            raise RuntimeError("shadow validation did not pass")
        write_ranking(args.run_dir / f"ranking_{args.run_date}.csv", args.run_date)
    elif args.stage == DailyStep.REPORT.value:
        rows = read_ranking(args.run_dir / f"ranking_{args.run_date}.csv")
        write_json(
            args.run_dir / "report.json",
            {"run_date": args.run_date, "shadow_only": True, "top10": rows},
        )
    elif args.stage == DailyStep.PUBLISH_READY.value:
        report = read_json(args.run_dir / "report.json")
        write_json(
            args.run_dir / "publish_ready.json",
            {
                "run_date": args.run_date,
                "shadow_only": True,
                "send_enabled": False,
                "publish_ready": len(report.get("top10", [])) == 10,
                "report": str(args.run_dir / "report.json"),
            },
        )
    return 0


def build_specs(run_date: str, model_path: Path, timeout_seconds: float) -> tuple[StepSpec, ...]:
    script = str(Path(__file__).resolve())

    def command(step: DailyStep) -> tuple[str, ...]:
        return (
            sys.executable,
            script,
            "_fixture-stage",
            step.value,
            "--run-dir",
            "{run_dir}",
            "--run-date",
            run_date,
            "--model",
            str(model_path),
        )

    ranking = f"ranking_{run_date}.csv"
    return (
        StepSpec(DailyStep.ETL, command(DailyStep.ETL), (), ("features.json",), timeout_seconds),
        StepSpec(
            DailyStep.VALIDATE,
            command(DailyStep.VALIDATE),
            ("features.json", str(model_path)),
            ("validation.json",),
            timeout_seconds,
        ),
        StepSpec(
            DailyStep.RANK,
            command(DailyStep.RANK),
            ("validation.json", str(model_path)),
            (ranking,),
            timeout_seconds,
        ),
        StepSpec(DailyStep.REPORT, command(DailyStep.REPORT), (ranking,), ("report.json",), timeout_seconds),
        StepSpec(
            DailyStep.PUBLISH_READY,
            command(DailyStep.PUBLISH_READY),
            (ranking, "report.json"),
            ("publish_ready.json",),
            timeout_seconds,
        ),
    )


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise RuntimeError(f"expected JSON object: {path}")
    return payload


def write_ranking(path: Path, run_date: str) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["rank", "stock_id", "score", "run_date"])
        writer.writeheader()
        for rank in range(1, 11):
            writer.writerow(
                {
                    "rank": rank,
                    "stock_id": str(1000 + rank),
                    "score": f"{1 - rank / 100:.2f}",
                    "run_date": run_date,
                }
            )


def read_ranking(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] == "_fixture-stage":
        return run_fixture_stage(sys.argv[2:])

    args = parse_args()
    run_id_suffix = "real-shadow" if args.source == "real" else "shadow"
    run_id = args.run_id or f"daily-v2-{args.run_date.replace('-', '')}-{run_id_suffix}"
    run_root = args.workspace.expanduser().resolve()
    if args.source == "real":
        try:
            result = run_real_shadow(
                run_id=run_id,
                run_date=args.run_date,
                workspace=run_root,
                data_dir=args.data_dir,
                model_dir=args.model_dir,
                baseline_ranking=args.baseline_ranking,
                model_filename=args.model_filename,
                config_path=args.config,
                numeric_tolerance=args.numeric_tolerance,
            )
        except (FileNotFoundError, ValueError, RealShadowExecutionError) as exc:
            print(f"daily v2 real shadow failed: {exc}", file=sys.stderr)
            return 1
        print(json.dumps(result, ensure_ascii=False))
        return 0 if result["status"] == "GO" else 2

    model_path = run_root / run_id / "fixture_model.pkl"
    model_path.parent.mkdir(parents=True, exist_ok=True)
    if not model_path.exists():
        with model_path.open("wb") as handle:
            pickle.dump({"model": "shadow-fixture", "feature_names": ["score"]}, handle)

    workflow = DailyWorkflowV2(
        run_id=run_id,
        run_date=args.run_date,
        run_root=run_root,
        model_path=model_path,
        steps=build_specs(args.run_date, model_path, args.step_timeout),
        working_directory=PROJECT_ROOT,
    )
    try:
        manifest = workflow.run()
    except (ValueError, WorkflowExecutionError) as exc:
        print(f"daily v2 shadow failed: {exc}", file=sys.stderr)
        return 1
    print(
        json.dumps(
            {
                "status": manifest["status"],
                "run_id": manifest["run_id"],
                "manifest": str(workflow.manifest_path),
                "publish_ready": str(workflow.run_dir / "publish_ready.json"),
                "live_send_enabled": False,
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
