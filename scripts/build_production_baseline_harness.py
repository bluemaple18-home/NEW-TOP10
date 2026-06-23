#!/usr/bin/env python3
"""建立 production baseline staging harness。

這支腳本只用正式 current-model ranking 生成契約輸出 staging baseline；
不建立 artifacts/backtest/production，不跑 replay，不改模型。
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(PROJECT_ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import build_historical_ranking_replay_set  # noqa: E402
from weekend_training_common import PRODUCTION_IMPACT, repo_path, resolve_path, write_json, write_text  # noqa: E402


SCHEMA_VERSION = "production-baseline-harness-manifest.v1"
SMOKE_SCHEMA_VERSION = "production-baseline-harness-smoke.v1"
WEEKEND_DIR = PROJECT_ROOT / "artifacts" / "weekend_training"
STAGING_ROOT = WEEKEND_DIR / "staging"
TARGET_BASELINE_PATH = PROJECT_ROOT / "artifacts" / "backtest" / "production"
REQUIRED_COLUMNS = {
    "stock_id",
    "risk_adjusted_score",
    "suggested_weight",
    "max_position_weight",
    "gross_exposure",
}
PREFERRED_COLUMNS = {
    "stock_name",
    "final_score",
    "model_prob",
    "allocated_exposure",
    "cash_weight",
    "market_regime",
    "reasons",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build production baseline harness staging artifact")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--config", default="config/signals.yaml")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--stride", type=int, default=1)
    parser.add_argument("--max-dates", type=int, default=None)
    parser.add_argument("--legacy-per-date-load", action="store_true")
    return parser.parse_args()


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def sha256(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except ValueError:
        return False


def resolve_output_dir(value: str | None, run_date: str) -> Path:
    if value:
        output_dir = resolve_path(value)
        assert output_dir is not None
    else:
        output_dir = STAGING_ROOT / f"production_baseline_harness_{run_date}"
    if not is_under(output_dir, STAGING_ROOT):
        raise ValueError(f"output-dir 必須位於 staging 底下：{repo_path(STAGING_ROOT)}")
    if output_dir.resolve() == STAGING_ROOT.resolve():
        raise ValueError("output-dir 不可直接使用 staging 根目錄")
    if output_dir.resolve() == TARGET_BASELINE_PATH.resolve() or is_under(output_dir, TARGET_BASELINE_PATH):
        raise ValueError("output-dir 不可指向 artifacts/backtest/production")
    return output_dir


def clean_output_dir(output_dir: Path) -> None:
    if output_dir.exists():
        if not is_under(output_dir, STAGING_ROOT):
            raise ValueError(f"拒絕清理非 staging output-dir：{output_dir}")
        shutil.rmtree(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)


def smoke_paths(run_date: str) -> tuple[Path, Path]:
    stem = f"production_baseline_harness_smoke_{run_date}"
    return WEEKEND_DIR / f"{stem}.json", WEEKEND_DIR / f"{stem}.md"


def ranking_files(output_dir: Path) -> list[Path]:
    return sorted(path for path in output_dir.glob("ranking_*.csv") if path.is_file())


def ranking_date(path: Path) -> str:
    return path.stem.removeprefix("ranking_")


def ranking_quality(output_dir: Path) -> dict[str, Any]:
    files = ranking_files(output_dir)
    per_file: list[dict[str, Any]] = []
    missing_by_file: dict[str, list[str]] = {}
    order_errors: list[str] = []
    stock_id_errors: list[str] = []
    row_counts: dict[str, int] = {}
    for path in files:
        frame = pd.read_csv(path, encoding="utf-8-sig", dtype={"stock_id": str})
        date_text = ranking_date(path)
        columns = list(frame.columns)
        missing = sorted(REQUIRED_COLUMNS - set(columns))
        if missing:
            missing_by_file[date_text] = missing
        row_counts[date_text] = int(len(frame))
        if frame.empty or "stock_id" not in frame.columns or frame["stock_id"].fillna("").astype(str).str.strip().eq("").any():
            stock_id_errors.append(date_text)
        if "risk_adjusted_score" in frame.columns:
            scores = pd.to_numeric(frame["risk_adjusted_score"], errors="coerce")
            if scores.isna().any() or not scores.is_monotonic_decreasing:
                order_errors.append(date_text)
        else:
            order_errors.append(date_text)
        per_file.append(
            {
                "date": date_text,
                "path": repo_path(path),
                "row_count": int(len(frame)),
                "columns": columns,
                "missing_required_columns": missing,
                "missing_preferred_columns": sorted(PREFERRED_COLUMNS - set(columns)),
            }
        )
    return {
        "ranking_file_count": len(files),
        "ranking_dates": [ranking_date(path) for path in files],
        "row_counts": row_counts,
        "per_file": per_file,
        "schema_columns_ok": not missing_by_file and bool(files),
        "stock_id_non_empty": not stock_id_errors and bool(files),
        "ranking_order_deterministic": not order_errors and bool(files),
        "missing_required_columns_by_file": missing_by_file,
        "stock_id_error_dates": stock_id_errors,
        "ranking_order_error_dates": order_errors,
    }


def date_coverage_from_features(data_dir: Path, start_date: str, end_date: str, stride: int, max_dates: int | None) -> list[str]:
    return build_historical_ranking_replay_set.load_trade_dates(
        data_dir=data_dir,
        start_date=start_date,
        end_date=end_date,
        stride=max(stride, 1),
        max_dates=max_dates,
    )


def build_internal_args(args: argparse.Namespace, output_dir: Path, manifest_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        start_date=args.start_date,
        end_date=args.end_date,
        data_dir=args.data_dir,
        model_dir=args.model_dir,
        config=args.config,
        output_dir=str(output_dir),
        stride=args.stride,
        max_dates=args.max_dates,
        legacy_per_date_load=args.legacy_per_date_load,
        manifest=str(manifest_path),
    )


def build_generator_command(args: argparse.Namespace, output_dir: Path) -> list[str]:
    command = [
        ".venv/bin/python",
        "scripts/build_production_baseline_harness.py",
        "--date",
        args.date,
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--data-dir",
        args.data_dir,
        "--model-dir",
        args.model_dir,
        "--config",
        args.config,
        "--output-dir",
        repo_path(output_dir) or str(output_dir),
        "--stride",
        str(args.stride),
    ]
    if args.max_dates is not None:
        command.extend(["--max-dates", str(args.max_dates)])
    if args.legacy_per_date_load:
        command.append("--legacy-per-date-load")
    return command


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    data_dir = resolve_path(args.data_dir)
    model_dir = resolve_path(args.model_dir)
    config_path = resolve_path(args.config)
    assert data_dir is not None and model_dir is not None and config_path is not None
    model_path = model_dir / "latest_lgbm.pkl"
    features_path = data_dir / "features.parquet"
    universe_path = data_dir / "universe.parquet"
    output_dir = resolve_output_dir(args.output_dir, args.date)
    generator_manifest_path = output_dir / "generator_manifest.json"
    manifest_path = output_dir / "manifest.json"

    blockers: list[str] = []
    if TARGET_BASELINE_PATH.exists():
        blockers.append("TARGET_PRODUCTION_BASELINE_PATH_EXISTS_BEFORE_RUN")
    clean_output_dir(output_dir)

    expected_dates: list[str] = []
    generator_payload: dict[str, Any] = {}
    try:
        expected_dates = date_coverage_from_features(data_dir, args.start_date, args.end_date, args.stride, args.max_dates)
        internal_args = build_internal_args(args, output_dir, generator_manifest_path)
        generator_payload = build_historical_ranking_replay_set.build_payload(internal_args)
    except Exception as exc:  # noqa: BLE001 - harness 要把 blocker 寫入 artifact
        blockers.append(f"GENERATOR_EXCEPTION:{exc}")

    quality = ranking_quality(output_dir)
    generated_dates = quality["ranking_dates"]
    missing_dates = sorted(set(expected_dates) - set(generated_dates))
    extra_dates = sorted(set(generated_dates) - set(expected_dates))
    generator_ok = generator_payload.get("status") == "OK" if generator_payload else False
    if not generator_ok:
        blockers.append(f"GENERATOR_STATUS:{generator_payload.get('status') if generator_payload else 'NOT_RUN'}")
    if missing_dates:
        blockers.append(f"MISSING_RANKING_DATES:{','.join(missing_dates)}")
    if extra_dates:
        blockers.append(f"EXTRA_RANKING_DATES:{','.join(extra_dates)}")
    if not quality["schema_columns_ok"]:
        blockers.append("SCHEMA_COLUMNS_NOT_OK")
    if not quality["stock_id_non_empty"]:
        blockers.append("STOCK_ID_CONTRACT_FAILED")
    if not quality["ranking_order_deterministic"]:
        blockers.append("RANKING_ORDER_NOT_DETERMINISTIC")
    if TARGET_BASELINE_PATH.exists():
        blockers.append("TARGET_PRODUCTION_BASELINE_PATH_EXISTS_AFTER_RUN")

    harness_status = "OK" if not blockers else "BLOCKED"
    generated_at = now_utc()
    command = build_generator_command(args, output_dir)
    internal_command = [
        ".venv/bin/python",
        "scripts/build_historical_ranking_replay_set.py",
        "--start-date",
        args.start_date,
        "--end-date",
        args.end_date,
        "--data-dir",
        args.data_dir,
        "--model-dir",
        args.model_dir,
        "--config",
        args.config,
        "--output-dir",
        repo_path(output_dir) or str(output_dir),
        "--manifest",
        repo_path(generator_manifest_path) or str(generator_manifest_path),
        "--stride",
        str(args.stride),
    ]
    if args.max_dates is not None:
        internal_command.extend(["--max-dates", str(args.max_dates)])
    if args.legacy_per_date_load:
        internal_command.append("--legacy-per-date-load")

    manifest = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": generated_at,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "ranking_dates": generated_dates,
        "expected_ranking_dates": expected_dates,
        "generator_command": command,
        "internal_generator_command": internal_command,
        "source_pipeline": "scripts/build_historical_ranking_replay_set.py::build_payload current_model_batch",
        "model_artifact": repo_path(model_path),
        "model_hash": sha256(model_path),
        "config": repo_path(config_path),
        "config_hash": sha256(config_path),
        "data_source": {
            "data_dir": repo_path(data_dir),
            "features": repo_path(features_path),
            "features_hash": sha256(features_path),
            "universe": repo_path(universe_path) if universe_path.exists() else None,
            "universe_hash": sha256(universe_path) if universe_path.exists() else None,
        },
        "feature_source": {
            "loader": "app.modeling.feature_contract.load_m4_feature_frame",
            "price_pattern_adapter": "scripts/build_historical_ranking_replay_set.prepare_batch_frames",
            "ranking_rows": "single target trade_date rows only",
        },
        "no_future_data_contract": {
            "ranking_row_contract": "每個 ranking file 只使用該 ranking date 的 feature rows 計分。",
            "market_regime_contract": "MarketRegimeService.evaluate 以 target_date 限定當日 regime inputs。",
            "review_required_before_production_materialization": True,
        },
        "output_dir": repo_path(output_dir),
        "production_impact": PRODUCTION_IMPACT,
        "contract": {
            "research_only": True,
            "staging_only": True,
            "does_not_create_artifacts_backtest_production": True,
            "does_not_execute_replay": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_publish_clawd": True,
            "no_promotion_ready": True,
        },
        "lineage": {
            "copied_from_candidate_source": False,
            "copied_from_subset_source": False,
            "symlinked_from_existing_ranking_dir": False,
            "generator_manifest": repo_path(generator_manifest_path),
        },
        "checks": {
            "staging_output_only": is_under(output_dir, STAGING_ROOT),
            "target_production_path_created": TARGET_BASELINE_PATH.exists(),
            "generator_status": generator_payload.get("status") if generator_payload else "NOT_RUN",
            "date_coverage_ok": bool(expected_dates) and generated_dates == expected_dates,
            "schema_columns_ok": quality["schema_columns_ok"],
            "stock_id_non_empty": quality["stock_id_non_empty"],
            "ranking_order_deterministic": quality["ranking_order_deterministic"],
            "manifest_present": True,
            "provenance_complete": all([model_path.exists(), config_path.exists(), features_path.exists(), bool(command)]),
            "copied_from_candidate_source": False,
            "production_impact": PRODUCTION_IMPACT,
            "no_promotion_ready": True,
        },
        "summary": {
            "harness_status": harness_status,
            "ranking_file_count": quality["ranking_file_count"],
            "failure_count": len(generator_payload.get("failures") or []) if generator_payload else 0,
            "missing_dates": missing_dates,
            "extra_dates": extra_dates,
            "ranking_dates": generated_dates,
            "next_action": (
                "open WEEKEND-TRAINING-15_controlled_production_baseline_materialization_review"
                if harness_status == "OK"
                else "維持 ARTIFACT_BLOCKER_PROVENANCE_GAP；修正 harness blocker，不跑 replay。"
            ),
        },
        "ranking_quality": quality,
        "generator_payload_summary": {
            "schema_version": generator_payload.get("schema_version"),
            "status": generator_payload.get("status"),
            "outputs": generator_payload.get("outputs"),
            "failures": generator_payload.get("failures"),
        }
        if generator_payload
        else {},
        "blocker_reasons": sorted(set(blockers)),
    }
    write_json(manifest_path, manifest)
    smoke_json, smoke_md = smoke_paths(args.date)
    smoke = build_smoke_payload(args, manifest, manifest_path)
    write_json(smoke_json, smoke)
    write_text(smoke_md, render_markdown(smoke))
    return smoke


def build_smoke_payload(args: argparse.Namespace, manifest: dict[str, Any], manifest_path: Path) -> dict[str, Any]:
    checks = manifest["checks"]
    summary = manifest["summary"]
    return {
        "schema_version": SMOKE_SCHEMA_VERSION,
        "generated_at": now_utc(),
        "date": args.date,
        "harness_status": summary["harness_status"],
        "production_impact": PRODUCTION_IMPACT,
        "manifest": repo_path(manifest_path),
        "staging": {
            "output_dir": manifest.get("output_dir"),
            "ranking_dates": manifest.get("ranking_dates"),
            "ranking_file_count": summary["ranking_file_count"],
        },
        "checks": {
            "staging_output_only": checks["staging_output_only"],
            "ranking_file_count": summary["ranking_file_count"],
            "manifest_present": True,
            "provenance_complete": checks["provenance_complete"],
            "target_production_path_created": checks["target_production_path_created"],
            "copied_from_candidate_source": checks["copied_from_candidate_source"],
            "production_impact": PRODUCTION_IMPACT,
            "no_promotion_ready": checks["no_promotion_ready"],
            "date_coverage_ok": checks["date_coverage_ok"],
            "schema_columns_ok": checks["schema_columns_ok"],
            "stock_id_non_empty": checks["stock_id_non_empty"],
            "ranking_order_deterministic": checks["ranking_order_deterministic"],
        },
        "summary": {
            **summary,
            "controlled_materialization_review_only": summary["harness_status"] == "OK",
            "full_replay_unlocked": False,
        },
        "blocker_reasons": manifest.get("blocker_reasons") or [],
        "contract": manifest["contract"],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    checks = payload["checks"]
    summary = payload["summary"]
    lines = [
        "# Production Baseline Harness Smoke",
        "",
        f"- harness_status: `{payload['harness_status']}`",
        f"- staging_output_only: `{checks['staging_output_only']}`",
        f"- ranking_file_count: `{checks['ranking_file_count']}`",
        f"- manifest_present: `{checks['manifest_present']}`",
        f"- provenance_complete: `{checks['provenance_complete']}`",
        f"- target_production_path_created: `{checks['target_production_path_created']}`",
        f"- copied_from_candidate_source: `{checks['copied_from_candidate_source']}`",
        f"- production_impact: `{payload['production_impact']}`",
        f"- full_replay_unlocked: `{summary['full_replay_unlocked']}`",
        f"- next_action: {summary['next_action']}",
        "",
        "## Blockers",
        "",
    ]
    blockers = payload.get("blocker_reasons") or []
    if blockers:
        lines.extend(f"- `{reason}`" for reason in blockers)
    else:
        lines.append("- none")
    lines.extend(["", "No production ranking, model, replay, or Clawd changes.", ""])
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    print(
        json.dumps(
            {
                "status": payload["harness_status"],
                "manifest": payload["manifest"],
                "output_dir": payload["staging"]["output_dir"],
                "ranking_file_count": payload["staging"]["ranking_file_count"],
                "production_impact": payload["production_impact"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
