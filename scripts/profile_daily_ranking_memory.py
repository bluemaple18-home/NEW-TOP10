#!/usr/bin/env python3
"""量測 freshness parent 與代表性 ranking 子程序重疊時的 process-tree RSS。"""

from __future__ import annotations

import argparse
import gc
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from pyarrow import parquet as pq


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="量測 daily freshness/ranking RSS overlap")
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--model-dir", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--artifact-dir", type=Path, required=True)
    parser.add_argument("--freshness-mode", choices=("legacy", "projected"), required=True)
    parser.add_argument("--max-process-tree-rss-bytes", type=int, required=True)
    parser.add_argument("--receipt-path", type=Path)
    return parser.parse_args()


def read_freshness(data_dir: Path, mode: str) -> None:
    for filename in ("features.parquet", "events.parquet", "universe.parquet"):
        path = data_dir / filename
        available = set(pq.read_schema(path).names)
        date_column = "trade_date" if "trade_date" in available else "date"
        if mode == "legacy":
            frame = pd.read_parquet(path, columns=None)
        else:
            columns = [date_column]
            if filename == "features.parquet":
                columns.extend(column for column in ("stock_id", "market") if column in available)
            frame = pd.read_parquet(path, columns=columns)
        pd.to_datetime(frame[date_column], errors="coerce").max()
        del frame
    gc.collect()


def process_tree_rss(parent_pid: int, child_pid: int) -> int:
    output = subprocess.run(
        ["ps", "-o", "rss=", "-p", f"{parent_pid},{child_pid}"],
        check=False,
        capture_output=True,
        text=True,
    ).stdout
    return sum(int(value) * 1024 for value in output.split() if value.isdigit())


def main() -> int:
    args = parse_args()
    args.artifact_dir.mkdir(parents=True, exist_ok=True)
    read_freshness(args.data_dir, args.freshness_mode)

    command = [
        sys.executable,
        "-m",
        "app.agent_b_ranking",
        "--data-dir",
        str(args.data_dir),
        "--model-dir",
        str(args.model_dir),
        "--artifact-dir",
        str(args.artifact_dir),
        "--config",
        str(args.config),
    ]
    child = subprocess.Popen(command)
    peak_rss = 0
    while child.poll() is None:
        peak_rss = max(peak_rss, process_tree_rss(os.getpid(), child.pid))
        time.sleep(1)
    peak_rss = max(peak_rss, process_tree_rss(os.getpid(), child.pid))
    result = {
        "freshness_mode": args.freshness_mode,
        "peak_process_tree_rss_bytes": peak_rss,
        "ranking_exit_code": child.returncode,
        "limit_bytes": args.max_process_tree_rss_bytes,
        "status": "OK" if child.returncode == 0 and peak_rss <= args.max_process_tree_rss_bytes else "FAILED",
    }
    if args.receipt_path is not None:
        args.receipt_path.parent.mkdir(parents=True, exist_ok=True)
        args.receipt_path.write_text(
            json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0 if result["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
