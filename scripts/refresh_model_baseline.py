#!/usr/bin/env python3
"""刷新與目前正式模型綁定的 PSI baseline。"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.model_monitor import ModelMonitor


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="刷新 models/baseline_stats.json")
    parser.add_argument("--data-dir", default=str(PROJECT_ROOT / "data" / "clean"))
    parser.add_argument("--model", default=str(PROJECT_ROOT / "models" / "latest_lgbm.pkl"))
    parser.add_argument("--baseline", default=str(PROJECT_ROOT / "models" / "baseline_stats.json"))
    parser.add_argument("--check-after", action="store_true", help="刷新後立即跑 PSI drift check")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    monitor = ModelMonitor(
        data_dir=args.data_dir,
        baseline_path=args.baseline,
        model_path=args.model,
        project_root=PROJECT_ROOT,
    )
    monitor.save_baseline()
    baseline_path = Path(args.baseline)
    metadata = json.loads(baseline_path.read_text(encoding="utf-8")).get("metadata", {})
    status = None
    if args.check_after:
        report = monitor.check_drift(days=30)
        status = report.get("status")
    print(
        "MODEL_BASELINE_REFRESH_OK features={features} samples={samples} latest={latest} status={status}".format(
            features=metadata.get("features_count"),
            samples=metadata.get("total_samples"),
            latest=metadata.get("latest_date"),
            status=status or "not_checked",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
