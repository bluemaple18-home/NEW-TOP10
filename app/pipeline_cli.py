"""ETL pipeline CLI 相容入口。

目前 pipeline 已重構為 stage-based composition；這裡提供自動化排程可呼叫的薄 CLI。
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from app.pipeline.repair import LocalOutputRepair
from app.pipeline.validation import PipelineDataValidator


def build_pipeline(data_dir: str = "data", artifacts_dir: str = "artifacts"):
    from app.pipeline import ETLPipeline, EventStage, FetchStage, FilterStage, FundamentalStage, IndicatorStage, ReportStage

    return (
        ETLPipeline(data_dir=data_dir, artifacts_dir=artifacts_dir)
        .add_stage(FetchStage())
        .add_stage(IndicatorStage())
        .add_stage(FundamentalStage())
        .add_stage(EventStage())
        .add_stage(FilterStage())
        .add_stage(ReportStage())
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="NEW-TOP10 ETL pipeline")
    parser.add_argument("command", choices=["run", "validate", "repair-local"])
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--data-dir", default="data")
    parser.add_argument("--artifacts-dir", default=None)
    parser.add_argument("--json", action="store_true", help="以 JSON 輸出驗證報告")
    parser.add_argument("--finmind-stats-output", type=Path, default=None)
    args = parser.parse_args()

    if args.command == "validate":
        report = PipelineDataValidator(data_dir=args.data_dir).validate_outputs()
        if args.json:
            print(json.dumps(report.to_dict(), ensure_ascii=False, indent=2))
        else:
            for summary in report.summaries:
                print(f"{summary.dataset}: rows={summary.rows}, cols={summary.columns}, stocks={summary.stocks}, ok={not any(i.severity == 'ERROR' for i in summary.issues)}")
                for issue in summary.issues:
                    column = f" [{issue.column}]" if issue.column else ""
                    print(f"  {issue.severity}{column} {issue.message}")
        return 0 if report.ok else 1

    if args.command == "repair-local":
        result = LocalOutputRepair(data_dir=args.data_dir).repair()
        print(json.dumps(result.__dict__, ensure_ascii=False, indent=2))
        return 0

    artifacts_dir = args.artifacts_dir
    if artifacts_dir is None:
        artifacts_dir = "artifacts" if args.data_dir == "data" else str(Path(args.data_dir) / "artifacts")
    pipeline = build_pipeline(data_dir=args.data_dir, artifacts_dir=artifacts_dir)
    try:
        pipeline.run(start_date=args.start_date, end_date=args.end_date)
    finally:
        if args.finmind_stats_output is not None:
            # 子程序只交出 FinMind 統計，不輸出 token 或其他 context 物件。
            stats = pipeline.context.get("stats", {}).get("finmind")
            if isinstance(stats, dict):
                allowed = {
                    "status", "expected_fetch_count", "received_fetch_count",
                    "failed_fetch_count", "failed_stock_count", "by_dataset",
                    "limit", "used", "remaining", "required_fetch_count",
                    "next_available_time",
                }
                stats = {key: value for key, value in stats.items() if key in allowed}
                datasets = stats.get("by_dataset")
                if isinstance(datasets, dict):
                    count_keys = {"expected_stock_count", "received_stock_count", "failed_stock_count"}
                    stats["by_dataset"] = {
                        name: {key: value for key, value in counts.items() if key in count_keys}
                        for name, counts in datasets.items() if isinstance(counts, dict)
                    }
            args.finmind_stats_output.write_text(
                json.dumps(stats, ensure_ascii=False, allow_nan=False), encoding="utf-8"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
