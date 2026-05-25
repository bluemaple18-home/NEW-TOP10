"""ETL 產物資料契約驗證。

這層只檢查 pipeline 輸出是否可被模型、排名與 UI 安全使用，不觸發抓資料或訓練。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from app.data.reference_repository import ReferenceRepository


@dataclass(frozen=True)
class DatasetContract:
    name: str
    path: Path
    required_columns: tuple[str, ...]
    numeric_columns: tuple[str, ...] = ()
    event_columns: tuple[str, ...] = ()
    key_columns: tuple[str, ...] = ("date", "stock_id")
    min_rows: int = 1
    min_stocks: int = 1
    min_latest_coverage: float = 0.65


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    dataset: str
    message: str
    column: str | None = None


@dataclass
class DatasetSummary:
    dataset: str
    path: str
    exists: bool
    rows: int = 0
    columns: int = 0
    stocks: int = 0
    start_date: str | None = None
    end_date: str | None = None
    issues: list[ValidationIssue] = field(default_factory=list)


@dataclass
class ValidationReport:
    ok: bool
    summaries: list[DatasetSummary]

    @property
    def issues(self) -> list[ValidationIssue]:
        return [issue for summary in self.summaries for issue in summary.issues]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "issue_counts": {
                "ERROR": sum(issue.severity == "ERROR" for issue in self.issues),
                "WARN": sum(issue.severity == "WARN" for issue in self.issues),
            },
            "summaries": [
                {
                    **asdict(summary),
                    "issues": [asdict(issue) for issue in summary.issues],
                }
                for summary in self.summaries
            ],
        }


class PipelineDataValidator:
    """驗證既有 parquet 產物是否符合下游契約。"""

    CORE_PRICE_COLUMNS = ("date", "stock_id", "open", "high", "low", "close", "volume")
    CORE_TECH_COLUMNS = (
        "ma5",
        "ma20",
        "rsi",
        "macd",
        "macd_signal",
        "bb_middle",
        "avg_value_20d",
    )

    def __init__(self, data_dir: str | Path = "data", config_path: str | Path = "config/signals.yaml"):
        self.data_dir = Path(data_dir)
        self.clean_dir = self.data_dir / "clean"
        self.config_path = Path(config_path)

    def validate_outputs(self) -> ValidationReport:
        contracts = [
            self.features_contract(),
            self.events_contract(),
            self.universe_contract(),
        ]
        summaries = [self.validate_contract(contract) for contract in contracts]
        ok = not any(issue.severity == "ERROR" for summary in summaries for issue in summary.issues)
        return ValidationReport(ok=ok, summaries=summaries)

    def features_contract(self) -> DatasetContract:
        return DatasetContract(
            name="features",
            path=self.clean_dir / "features.parquet",
            required_columns=self.CORE_PRICE_COLUMNS + self.CORE_TECH_COLUMNS,
            numeric_columns=tuple(col for col in self.CORE_PRICE_COLUMNS + self.CORE_TECH_COLUMNS if col != "date" and col != "stock_id"),
            min_stocks=5,
        )

    def events_contract(self) -> DatasetContract:
        event_names = tuple(self._load_event_names())
        return DatasetContract(
            name="events",
            path=self.clean_dir / "events.parquet",
            required_columns=("date", "stock_id") + event_names,
            numeric_columns=event_names,
            event_columns=event_names,
            min_stocks=5,
            min_latest_coverage=0.95,
        )

    def universe_contract(self) -> DatasetContract:
        return DatasetContract(
            name="universe",
            path=self.clean_dir / "universe.parquet",
            required_columns=("date", "stock_id", "close", "avg_value_20d"),
            numeric_columns=("close", "avg_value_20d"),
            min_stocks=1,
        )

    def validate_contract(self, contract: DatasetContract) -> DatasetSummary:
        summary = DatasetSummary(dataset=contract.name, path=str(contract.path), exists=contract.path.exists())
        if not contract.path.exists():
            summary.issues.append(ValidationIssue("ERROR", contract.name, f"找不到必要產物：{contract.path}"))
            return summary

        try:
            df = pd.read_parquet(contract.path)
        except Exception as exc:
            summary.issues.append(ValidationIssue("ERROR", contract.name, f"讀取 parquet 失敗：{exc}"))
            return summary

        summary.rows = len(df)
        summary.columns = len(df.columns)
        if "stock_id" in df.columns:
            summary.stocks = int(df["stock_id"].astype(str).nunique())
        if "date" in df.columns and not df.empty:
            dates = pd.to_datetime(df["date"], errors="coerce")
            if dates.notna().any():
                summary.start_date = str(dates.min())
                summary.end_date = str(dates.max())

        self._validate_shape(df, contract, summary)
        if summary.rows:
            self._validate_keys(df, contract, summary)
            self._validate_trade_date_keys(df, contract, summary)
            self._validate_numeric_columns(df, contract, summary)
            self._validate_latest_coverage(df, contract, summary)
            self._validate_market_latest_coverage(df, contract, summary)
            self._validate_event_columns(df, contract, summary)
        return summary

    def _validate_shape(self, df: pd.DataFrame, contract: DatasetContract, summary: DatasetSummary) -> None:
        if len(df) < contract.min_rows:
            summary.issues.append(ValidationIssue("ERROR", contract.name, f"資料列數不足：{len(df)} < {contract.min_rows}"))
        missing = [col for col in contract.required_columns if col not in df.columns]
        for col in missing:
            summary.issues.append(ValidationIssue("ERROR", contract.name, "缺少必要欄位", col))
        if "stock_id" in df.columns and df["stock_id"].astype(str).nunique() < contract.min_stocks:
            summary.issues.append(
                ValidationIssue("WARN", contract.name, f"股票數偏少：{df['stock_id'].astype(str).nunique()} < {contract.min_stocks}", "stock_id")
            )

    def _validate_keys(self, df: pd.DataFrame, contract: DatasetContract, summary: DatasetSummary) -> None:
        missing_keys = [col for col in contract.key_columns if col not in df.columns]
        if missing_keys:
            return
        null_key_rows = df[list(contract.key_columns)].isna().any(axis=1).sum()
        if null_key_rows:
            summary.issues.append(ValidationIssue("ERROR", contract.name, f"主鍵欄位有空值：{null_key_rows} 列"))
        duplicate_rows = df.duplicated(list(contract.key_columns)).sum()
        if duplicate_rows:
            summary.issues.append(ValidationIssue("ERROR", contract.name, f"主鍵重複：{duplicate_rows} 列"))

    def _validate_trade_date_keys(self, df: pd.DataFrame, contract: DatasetContract, summary: DatasetSummary) -> None:
        if "date" not in df.columns or "stock_id" not in df.columns:
            return
        trade_dates = pd.to_datetime(df["date"], errors="coerce").dt.normalize()
        if trade_dates.isna().any():
            invalid_rows = int(trade_dates.isna().sum())
            summary.issues.append(ValidationIssue("ERROR", contract.name, f"date 欄位有無法轉成交易日的值：{invalid_rows} 列", "date"))
            return
        trade_keys = pd.DataFrame(
            {
                "trade_date": trade_dates,
                "stock_id": df["stock_id"].astype(str).str.strip(),
            }
        )
        duplicate_rows = int(trade_keys.duplicated(["trade_date", "stock_id"]).sum())
        if duplicate_rows:
            summary.issues.append(ValidationIssue("ERROR", contract.name, f"交易日/股票主鍵重複：{duplicate_rows} 列"))

    def _validate_numeric_columns(self, df: pd.DataFrame, contract: DatasetContract, summary: DatasetSummary) -> None:
        for col in contract.numeric_columns:
            if col not in df.columns:
                continue
            values = pd.to_numeric(df[col], errors="coerce")
            if values.notna().sum() == 0:
                summary.issues.append(ValidationIssue("ERROR", contract.name, "數值欄位全為空或不可轉數字", col))
                continue
            if col in {"open", "high", "low", "close", "volume", "avg_value_20d"} and (values.dropna() < 0).any():
                summary.issues.append(ValidationIssue("ERROR", contract.name, "價格/量能欄位不可為負", col))

    def _validate_latest_coverage(self, df: pd.DataFrame, contract: DatasetContract, summary: DatasetSummary) -> None:
        if "date" not in df.columns or not contract.required_columns:
            return
        dates = pd.to_datetime(df["date"], errors="coerce")
        if dates.notna().sum() == 0:
            summary.issues.append(ValidationIssue("ERROR", contract.name, "date 欄位無法轉成日期", "date"))
            return
        trade_dates = dates.dt.normalize()
        latest_df = df[trade_dates == trade_dates.max()]
        checked_columns = [col for col in contract.required_columns if col in latest_df.columns and col not in {"date", "stock_id"}]
        for col in checked_columns:
            coverage = latest_df[col].notna().mean()
            if coverage < contract.min_latest_coverage:
                summary.issues.append(
                    ValidationIssue(
                        "WARN",
                        contract.name,
                        f"最新日期欄位覆蓋率偏低：{coverage:.1%} < {contract.min_latest_coverage:.1%}",
                        col,
                    )
                )

    def _validate_market_latest_coverage(self, df: pd.DataFrame, contract: DatasetContract, summary: DatasetSummary) -> None:
        if contract.name != "features" or "date" not in df.columns or "stock_id" not in df.columns:
            return
        target_columns = [col for col in ("ma20", "bb_middle") if col in df.columns]
        if not target_columns:
            return
        dates = pd.to_datetime(df["date"], errors="coerce")
        if dates.notna().sum() == 0:
            return
        latest_df = df[dates.dt.normalize() == dates.dt.normalize().max()].copy()
        if latest_df.empty:
            return
        market_map = {
            item.stock_id: item.market_type
            for item in ReferenceRepository(self.data_dir.parent if self.data_dir.name == "data" else Path.cwd())
            .tradable_universe()
            .items
        }
        latest_df["market_type"] = latest_df["stock_id"].astype(str).str.strip().map(market_map)
        for market_type, group in latest_df.groupby("market_type", dropna=True):
            if group.empty:
                continue
            for col in target_columns:
                coverage = group[col].notna().mean()
                if coverage < contract.min_latest_coverage:
                    summary.issues.append(
                        ValidationIssue(
                            "WARN",
                            contract.name,
                            f"{market_type} 最新日期長週期欄位覆蓋率偏低：{coverage:.1%} < {contract.min_latest_coverage:.1%}",
                            col,
                        )
                    )

    def _validate_event_columns(self, df: pd.DataFrame, contract: DatasetContract, summary: DatasetSummary) -> None:
        for col in contract.event_columns:
            if col not in df.columns:
                continue
            values = pd.to_numeric(df[col], errors="coerce").dropna()
            invalid = values[~values.isin([0, 1])]
            if not invalid.empty:
                summary.issues.append(ValidationIssue("ERROR", contract.name, "事件欄位必須是 0/1", col))

    def _load_event_names(self) -> list[str]:
        if not self.config_path.exists():
            return []
        config = yaml.safe_load(self.config_path.read_text(encoding="utf-8")) or {}
        return [str(event["name"]) for event in config.get("events", []) if "name" in event]
