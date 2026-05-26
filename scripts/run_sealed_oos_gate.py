#!/usr/bin/env python3
"""執行候選模型的封閉 OOS promotion gate。"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent_b_modeling import LightGBMTrainer
from app.modeling.sealed_oos import SCHEMA_VERSION, SealedOOSConfig, evaluate_sealed_oos_model, load_model_payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="封閉 OOS 模型 promotion gate")
    parser.add_argument("--config", default=str(PROJECT_ROOT / "config" / "automation.yaml"))
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT / "data" / "clean"))
    parser.add_argument("--model", default=str(PROJECT_ROOT / "models" / "latest_lgbm.pkl"))
    parser.add_argument("--artifact-dir", default=str(PROJECT_ROOT / "artifacts"))
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model_path = Path(args.model)
    artifact_dir = Path(args.artifact_dir)
    artifact_dir.mkdir(parents=True, exist_ok=True)
    run_date = datetime.now().astimezone().strftime("%Y-%m-%d")
    output_path = Path(args.output) if args.output else artifact_dir / f"sealed_oos_report_{run_date}.json"
    latest_path = artifact_dir / "sealed_oos_report_latest.json"

    try:
        model_payload = load_model_payload(model_path)
        model_metadata = model_payload.get("metadata", {}) if isinstance(model_payload, dict) else {}
        horizon = int(model_metadata.get("horizon") or args.horizon)
        threshold = float(model_metadata.get("threshold") or args.threshold)
        sealed_config = SealedOOSConfig.from_mapping(_sealed_config(args.config), horizon=horizon)
        if not sealed_config.enabled:
            report = {
                "schema_version": SCHEMA_VERSION,
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "status": "SKIPPED",
                "reason": "config retrain.sealed_oos.enabled=false",
            }
        else:
            trainer = LightGBMTrainer(
                data_dir=args.data_dir,
                model_dir=str(model_path.parent),
                artifact_dir=str(artifact_dir),
                horizon=horizon,
                threshold=threshold,
            )
            features = trainer.load_features()
            labeled = trainer.generate_labels(features)
            report = evaluate_sealed_oos_model(
                model_payload=model_payload,
                labeled_frame=labeled,
                config=sealed_config,
                horizon=horizon,
                threshold=threshold,
                model_path=model_path,
            )
    except Exception as exc:  # noqa: BLE001 - gate 必須把失敗寫成 artifact 供 rollback 診斷。
        report = {
            "schema_version": SCHEMA_VERSION,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": "FAILED",
            "failures": [str(exc)],
            "model": {"path": str(model_path), "exists": model_path.exists()},
        }

    _write_json(output_path, report)
    _write_json(latest_path, report)
    print(
        "SEALED_OOS_GATE_{status} output={output}".format(
            status=report.get("status", "FAILED"),
            output=output_path,
        )
    )
    return 0 if report.get("status") in {"OK", "SKIPPED"} else 1


def _sealed_config(config_path: str | Path) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        return {}
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    retrain = config.get("retrain") if isinstance(config.get("retrain"), dict) else {}
    sealed = retrain.get("sealed_oos") if isinstance(retrain.get("sealed_oos"), dict) else {}
    return sealed


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    raise SystemExit(main())
