#!/usr/bin/env python3
"""用目前模型產生研究用歷史 ranking set。

此腳本只寫指定 output-dir，不改 production ranking，不訓練模型。
用途是替 sealed / replay / window stability 建立足夠樣本。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent_b_ranking import StockRanker


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build historical ranking replay set with current model")
    parser.add_argument("--start-date", required=True)
    parser.add_argument("--end-date", required=True)
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--config", default="config/signals.yaml")
    parser.add_argument("--output-dir", default=None)
    parser.add_argument("--stride", type=int, default=1, help="每 N 個交易日取一天")
    parser.add_argument("--max-dates", type=int, default=None)
    parser.add_argument("--manifest", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def load_trade_dates(data_dir: Path, start_date: str, end_date: str, stride: int, max_dates: int | None) -> list[str]:
    features_path = data_dir / "features.parquet"
    if not features_path.exists():
        raise FileNotFoundError(f"features parquet 不存在：{features_path}")
    frame = pd.read_parquet(features_path, columns=["date"])
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna().dt.normalize().drop_duplicates().sort_values()
    start = pd.to_datetime(start_date).normalize()
    end = pd.to_datetime(end_date).normalize()
    selected = [item.strftime("%Y-%m-%d") for item in dates if start <= item <= end]
    if stride > 1:
        selected = selected[::stride]
    if max_dates is not None:
        selected = selected[:max_dates]
    if not selected:
        raise ValueError(f"指定區間沒有交易日：{start_date}~{end_date}")
    return selected


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    data_dir = resolve_path(args.data_dir)
    model_dir = resolve_path(args.model_dir)
    config_path = resolve_path(args.config)
    assert data_dir is not None and model_dir is not None and config_path is not None

    run_date = date.today().isoformat()
    output_dir = resolve_path(args.output_dir) or PROJECT_ROOT / "artifacts" / "research_rankings" / f"current_model_{args.start_date}_{args.end_date}"
    manifest_path = resolve_path(args.manifest) or output_dir / "manifest.json"
    output_dir.mkdir(parents=True, exist_ok=True)

    dates = load_trade_dates(
        data_dir=data_dir,
        start_date=args.start_date,
        end_date=args.end_date,
        stride=max(args.stride, 1),
        max_dates=args.max_dates,
    )

    ranker = StockRanker(
        data_dir=str(data_dir),
        model_dir=str(model_dir),
        artifact_dir=str(output_dir),
        config_path=str(config_path),
        generate_report=False,
    )
    ranker.load_model()

    outputs: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for date_text in dates:
        try:
            path = ranker.run_ranking(date_text)
            outputs.append({"date": date_text, "path": repo_path(Path(path))})
        except Exception as exc:
            failures.append({"date": date_text, "error": str(exc)})

    payload = {
        "schema_version": "historical-ranking-replay-set.v1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "status": "OK" if not failures else "FAILED",
        "contract": {
            "research_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
        },
        "inputs": {
            "data_dir": repo_path(data_dir),
            "model_dir": repo_path(model_dir),
            "config": repo_path(config_path),
            "start_date": args.start_date,
            "end_date": args.end_date,
            "stride": args.stride,
            "max_dates": args.max_dates,
        },
        "outputs": {
            "output_dir": repo_path(output_dir),
            "manifest": repo_path(manifest_path),
            "ranking_count": len(outputs),
            "rankings": outputs,
        },
        "failures": failures,
    }
    manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    return payload


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output_dir": payload["outputs"]["output_dir"],
                "manifest": payload["outputs"]["manifest"],
                "ranking_count": payload["outputs"]["ranking_count"],
                "failure_count": len(payload["failures"]),
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
