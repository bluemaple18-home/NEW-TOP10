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
    build_pipeline(data_dir=args.data_dir, artifacts_dir=artifacts_dir).run(start_date=args.start_date, end_date=args.end_date)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
