#!/usr/bin/env python3
"""產生候選模型 historical rankings 並執行 replay。

只使用 candidate model 產出 shadow ranking artifacts，不改 production ranking。
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from contextlib import redirect_stdout
from datetime import date, datetime, timezone
from io import StringIO
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
MODEL_EXPERIMENTS_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "training-candidate-replay-flow.v1"

if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent_b_ranking import StockRanker  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="run candidate ranking/replay flow")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--candidate-root", required=True)
    parser.add_argument("--rankings-dir", default=None)
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--max-dates", type=int, default=None)
    parser.add_argument("--horizons", default="1,3,5,10,20,30,40")
    parser.add_argument("--output", default=None)
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


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def ranking_window_dir(candidate_root: Path, dates: list[str], args: argparse.Namespace) -> Path:
    if args.rankings_dir:
        return resolve_path(args.rankings_dir) or candidate_root / "candidate_rankings"
    if dates:
        return candidate_root / f"candidate_rankings_{dates[0]}_{dates[-1]}"
    return candidate_root / "candidate_rankings_empty"


def trade_dates(args: argparse.Namespace) -> list[str]:
    features_path = resolve_path(args.features)
    if features_path is None or not features_path.exists():
        raise FileNotFoundError(f"features parquet 不存在：{features_path}")
    frame = pd.read_parquet(features_path, columns=["date"])
    dates = pd.to_datetime(frame["date"]).dt.normalize().drop_duplicates().sort_values()
    if args.start_date:
        dates = dates[dates >= pd.Timestamp(args.start_date)]
    if args.end_date:
        dates = dates[dates <= pd.Timestamp(args.end_date)]
    result = [value.strftime("%Y-%m-%d") for value in dates]
    return result[-args.max_dates :] if args.max_dates else result


def run_step(name: str, command: list[str]) -> dict[str, Any]:
    started = datetime.now(timezone.utc)
    completed = subprocess.run(command, cwd=PROJECT_ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {
        "name": name,
        "status": "OK" if completed.returncode == 0 else "FAILED",
        "returncode": completed.returncode,
        "started_at": started.isoformat(),
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "command": command,
        "stdout_tail": completed.stdout[-4000:],
        "stderr_tail": completed.stderr[-4000:],
    }


def generate_rankings(args: argparse.Namespace, candidate_root: Path, rankings_dir: Path, dates: list[str]) -> list[dict[str, Any]]:
    model_dir = candidate_root / "models"
    ranker = StockRanker(
        data_dir=args.data_dir,
        model_dir=str(model_dir),
        artifact_dir=str(rankings_dir),
        generate_report=False,
        explain_top_n=0,
    )
    ranker.load_model()
    rows: list[dict[str, Any]] = []
    for date_text in dates:
        try:
            captured_stdout = StringIO()
            with redirect_stdout(captured_stdout):
                path = ranker.run_ranking(date=date_text)
            rows.append(
                {
                    "date": date_text,
                    "status": "OK",
                    "ranking": repo_path(Path(path)),
                    "stdout_tail": captured_stdout.getvalue()[-1000:],
                }
            )
        except Exception as exc:  # noqa: BLE001 - replay flow 要記錄每個日期失敗原因。
            rows.append({"date": date_text, "status": "FAILED", "error": str(exc)})
    return rows


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    candidate_root = resolve_path(args.candidate_root)
    if candidate_root is None:
        raise RuntimeError("candidate root resolution failed")
    output_path = resolve_path(args.output) or candidate_root / "training_candidate_replay_flow.json"
    dates = trade_dates(args)
    rankings_dir = ranking_window_dir(candidate_root, dates, args)
    ranking_results = generate_rankings(args, candidate_root, rankings_dir, dates)
    failed_rankings = [row for row in ranking_results if row["status"] != "OK"]
    steps: list[dict[str, Any]] = []
    replay_output = candidate_root / "candidate_replay.json"
    portfolio_output = candidate_root / "candidate_portfolio_replay_40d.json"
    fixed_share_top10_output = candidate_root / f"fixed_share_top10_candidate_{args.date}.json"
    fixed_share_matrix_output = candidate_root / f"fixed_share_hypothesis_matrix_candidate_{args.date}.json"
    if not failed_rankings:
        steps.append(
            run_step(
                "candidate.replay",
                [
                    sys.executable,
                    "scripts/run_backtest_replay.py",
                    "--rankings-dir",
                    repo_path(rankings_dir) or str(rankings_dir),
                    "--features",
                    args.features,
                    "--horizons",
                    args.horizons,
                    "--output",
                    repo_path(replay_output) or str(replay_output),
                ],
            )
        )
        steps.append(
            run_step(
                "candidate.fixed_share_top10",
                [
                    sys.executable,
                    "scripts/run_fixed_share_top10_backtest.py",
                    "--variant",
                    f"candidate={repo_path(rankings_dir) or str(rankings_dir)}",
                    "--features",
                    args.features,
                    "--output",
                    repo_path(fixed_share_top10_output) or str(fixed_share_top10_output),
                ],
            )
        )
        steps.append(
            run_step(
                "candidate.fixed_share_matrix",
                [
                    sys.executable,
                    "scripts/run_fixed_share_hypothesis_matrix.py",
                    "--rankings-dir",
                    repo_path(rankings_dir) or str(rankings_dir),
                    "--features",
                    args.features,
                    "--variant-label",
                    "candidate",
                    "--output",
                    repo_path(fixed_share_matrix_output) or str(fixed_share_matrix_output),
                ],
            )
        )
        steps.append(
            run_step(
                "candidate.portfolio_replay_40d",
                [
                    sys.executable,
                    "scripts/run_portfolio_replay.py",
                    "--rankings-dir",
                    repo_path(rankings_dir) or str(rankings_dir),
                    "--features",
                    args.features,
                    "--horizon",
                    "40",
                    "--output",
                    repo_path(portfolio_output) or str(portfolio_output),
                ],
            )
        )
    errors = [f"ranking failed: {row['date']} {row.get('error')}" for row in failed_rankings]
    errors.extend(f"{step['name']} failed" for step in steps if step["status"] != "OK")
    status = "OK" if not errors else "FAILED"
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": status,
        "contract": {
            "candidate_replay_only": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
        },
        "candidate_root": repo_path(candidate_root),
        "rankings_dir": repo_path(rankings_dir),
        "date_window": {
            "start_date": dates[0] if dates else None,
            "end_date": dates[-1] if dates else None,
            "date_count": len(dates),
            "max_dates": args.max_dates,
        },
        "ranking_results": ranking_results,
        "outputs": {
            "replay": repo_path(replay_output),
            "portfolio_replay_40d": repo_path(portfolio_output),
            "fixed_share_top10": repo_path(fixed_share_top10_output),
            "fixed_share_hypothesis_matrix": repo_path(fixed_share_matrix_output),
        },
        "replay": read_json(replay_output),
        "portfolio_replay_40d": read_json(portfolio_output),
        "fixed_share_top10": read_json(fixed_share_top10_output),
        "fixed_share_hypothesis_matrix": read_json(fixed_share_matrix_output),
        "steps": steps,
        "errors": errors,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    replay = payload.get("replay") or {}
    portfolio = payload.get("portfolio_replay_40d") or {}
    lines = [
        "# Training Candidate Replay Flow",
        "",
        f"- status: `{payload['status']}`",
        f"- candidate_root: `{payload['candidate_root']}`",
        f"- rankings_dir: `{payload['rankings_dir']}`",
        f"- date_count: `{payload['date_window']['date_count']}`",
        f"- replay_status: `{replay.get('status')}`",
        f"- portfolio_status: `{portfolio.get('status')}`",
        "",
        "## Steps",
        "",
        "| Step | Status |",
        "|---|---|",
    ]
    for step in payload["steps"]:
        lines.append(f"| `{step['name']}` | `{step['status']}` |")
    lines.extend(["", "## Errors", ""])
    lines.extend([f"- {item}" for item in payload["errors"]] or ["- none"])
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    output = resolve_path(args.output) or (resolve_path(args.candidate_root) / "training_candidate_replay_flow.json")
    if output is None:
        raise RuntimeError("output path resolution failed")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "date_count": payload["date_window"]["date_count"],
                "rankings_dir": payload["rankings_dir"],
                "errors": payload["errors"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
