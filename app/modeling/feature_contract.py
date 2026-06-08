"""M4 訓練特徵資料契約。

這個模組只組裝既有日頻技術資料、事件訊號與本地基本面 cache，
不觸發外部資料抓取，也不訓練模型。
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

from app.data.fundamental_repository import FundamentalRepository
from app.fundamentals import compute_financial_metrics
from app.fundamentals.metrics import FinancialYearMetrics
from app.modeling.factor_registry import trainable_factor_columns


KEY_COLUMNS = ("trade_date", "stock_id")
RAW_KEY_COLUMNS = ("date", "stock_id")
NON_FEATURE_COLUMNS = {
    "date",
    "trade_date",
    "stock_id",
    "symbol",
    "stock_name",
    "target",
    "entry_price",
    "exit_price",
    "future_close",
    "future_return",
    "return_long",
    "return_5d",
}

FUNDAMENTAL_METRIC_NAMES = (
    "roe",
    "gross_margin",
    "debt_ratio",
    "operating_margin",
    "net_margin",
    "current_ratio",
    "roa",
    "free_cash_flow",
    "eps",
)
FUNDAMENTAL_FEATURE_COLUMNS = tuple(f"fundamental_{name}" for name in FUNDAMENTAL_METRIC_NAMES)
PATTERN_FEATURE_PREFIXES = ("candle_", "td_", "pattern_")
MIN_FUNDAMENTAL_FEATURE_COVERAGE = 0.80


@dataclass(frozen=True)
class FeatureGroupMetadata:
    columns: list[str]
    coverage: dict[str, float]
    missing_ratio: dict[str, float]


@dataclass(frozen=True)
class FeatureFrameMetadata:
    feature_groups: dict[str, FeatureGroupMetadata]
    rows: int
    stocks: int
    start_date: str | None
    end_date: str | None
    fundamental_cache_coverage: float
    notes: list[str]

    def to_dict(self) -> dict[str, Any]:
        return {
            **asdict(self),
            "feature_groups": {
                name: asdict(group)
                for name, group in self.feature_groups.items()
            },
        }


def load_m4_feature_frame(
    data_dir: str | Path = "data/clean",
    project_root: str | Path = ".",
    config_path: str | Path = "config/signals.yaml",
) -> tuple[pd.DataFrame, FeatureFrameMetadata]:
    """從標準 pipeline 產物載入 M4 合併訓練 frame。"""

    data_path = Path(data_dir)
    features = pd.read_parquet(data_path / "features.parquet")
    events_path = data_path / "events.parquet"
    events = pd.read_parquet(events_path) if events_path.exists() else None
    repository = FundamentalRepository(Path(project_root))
    return build_m4_feature_frame(features=features, events=events, fundamental_repository=repository, config_path=config_path)


def build_m4_feature_frame(
    features: pd.DataFrame,
    events: pd.DataFrame | None = None,
    fundamental_repository: FundamentalRepository | None = None,
    config_path: str | Path = "config/signals.yaml",
) -> tuple[pd.DataFrame, FeatureFrameMetadata]:
    """組裝技術、事件、型態、基本面四組特徵。

    基本面採 as-of join：每筆財務指標只會套用到其可取得日之後的交易日。
    若 cache 缺漏，輸出仍保留固定 `fundamental_*` 欄位並以缺值呈現。
    """

    frame = _normalize_source_frame(features, "features")
    _ensure_unique_trade_keys(frame, "features")

    notes: list[str] = []
    event_names = _configured_event_names(config_path)
    pattern_columns = _pattern_columns(frame)
    technical_columns = _technical_columns(frame, event_names=event_names, pattern_columns=set(pattern_columns))

    event_columns: list[str] = []
    if events is not None and not events.empty:
        event_frame = _normalize_source_frame(events, "events")
        _ensure_unique_trade_keys(event_frame, "events")
        event_frame, event_columns = _prepare_event_frame(event_frame)
        frame = frame.merge(event_frame, on=list(KEY_COLUMNS), how="left", validate="one_to_one")
        frame[event_columns] = frame[event_columns].fillna(0)
    else:
        notes.append("找不到 events.parquet，事件特徵群為空。")

    frame, fundamental_cache_coverage = _join_fundamentals(frame, fundamental_repository)
    _coerce_feature_group_dtypes(frame, event_columns)
    if fundamental_cache_coverage == 0:
        notes.append("找不到可用基本面 cache，fundamental_* 欄位會維持缺值。")
    elif fundamental_cache_coverage < MIN_FUNDAMENTAL_FEATURE_COVERAGE:
        notes.append(
            "基本面 cache 覆蓋率未達模型接入門檻 "
            f"{MIN_FUNDAMENTAL_FEATURE_COVERAGE:.0%}，fundamental_* 欄位只保留 metadata，不進候選特徵。"
        )

    _ensure_unique_trade_keys(frame, "m4_feature_frame")
    metadata = _metadata(
        frame=frame,
        technical_columns=technical_columns,
        event_columns=event_columns,
        pattern_columns=pattern_columns,
        fundamental_columns=list(FUNDAMENTAL_FEATURE_COLUMNS),
        fundamental_cache_coverage=fundamental_cache_coverage,
        notes=notes,
    )
    return frame, metadata


def candidate_feature_columns(frame: pd.DataFrame, metadata: FeatureFrameMetadata) -> list[str]:
    """回傳可交給 LightGBM 的數值候選特徵欄位。"""

    grouped_columns: list[str] = []
    for group in ("technical", "event", "pattern", "fundamental"):
        if group == "fundamental" and metadata.fundamental_cache_coverage < MIN_FUNDAMENTAL_FEATURE_COVERAGE:
            continue
        if group in metadata.feature_groups:
            grouped_columns.extend(metadata.feature_groups[group].columns)
    trainable_columns = set(trainable_factor_columns(frame, metadata))
    return [
        col
        for col in grouped_columns
        if col in trainable_columns and col not in NON_FEATURE_COLUMNS
    ]


def _normalize_source_frame(df: pd.DataFrame, dataset_name: str) -> pd.DataFrame:
    missing = [col for col in RAW_KEY_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"{dataset_name} 缺少必要鍵欄位：{missing}")
    result = df.copy()
    result["date"] = pd.to_datetime(result["date"], errors="coerce")
    if result["date"].isna().any():
        raise ValueError(f"{dataset_name} date 欄位含不可解析日期")
    result["trade_date"] = result["date"].dt.normalize()
    result["stock_id"] = result["stock_id"].astype(str).str.strip()
    return result.sort_values(["trade_date", "stock_id"]).copy()


def _technical_columns(
    frame: pd.DataFrame,
    event_names: set[str] | None = None,
    pattern_columns: set[str] | None = None,
) -> list[str]:
    event_names = event_names or set()
    pattern_columns = pattern_columns or set()
    return [
        col
        for col in frame.columns
        if col not in NON_FEATURE_COLUMNS
        and col not in event_names
        and col not in pattern_columns
        and pd.api.types.is_numeric_dtype(frame[col])
    ]


def _pattern_columns(frame: pd.DataFrame) -> list[str]:
    return [
        col
        for col in frame.columns
        if col.startswith(PATTERN_FEATURE_PREFIXES)
        and col not in NON_FEATURE_COLUMNS
        and pd.api.types.is_numeric_dtype(frame[col])
    ]


def _configured_event_names(config_path: str | Path) -> set[str]:
    path = Path(config_path)
    if not path.exists():
        return set()
    config = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    names = {str(event["name"]) for event in config.get("events", []) if isinstance(event, dict) and event.get("name")}
    weights = config.get("scoring", {}).get("weights", {})
    if isinstance(weights, dict):
        names.update(str(name) for name in weights)
    return names


def _prepare_event_frame(events: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    rename_map = {
        col: f"event_{col}"
        for col in events.columns
        if col not in {"date", "trade_date", "stock_id"}
    }
    event_frame = events[["trade_date", "stock_id", *rename_map.keys()]].rename(columns=rename_map)
    event_columns = list(rename_map.values())
    return event_frame, event_columns


def _coerce_feature_group_dtypes(frame: pd.DataFrame, event_columns: list[str]) -> None:
    for col in event_columns:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce").fillna(0)
    for col in FUNDAMENTAL_FEATURE_COLUMNS:
        if col in frame.columns:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")


def _join_fundamentals(
    frame: pd.DataFrame,
    repository: FundamentalRepository | None,
) -> tuple[pd.DataFrame, float]:
    result = frame.copy()
    for col in FUNDAMENTAL_FEATURE_COLUMNS:
        if col not in result.columns:
            result[col] = pd.NA
    if repository is None or result.empty:
        return _coerce_fundamental_columns(result), 0.0

    stock_ids = sorted(result["stock_id"].dropna().astype(str).unique())
    fundamental_rows: list[dict[str, Any]] = []
    cached_stock_count = 0
    for stock_id in stock_ids:
        payload = repository.load_cached(stock_id)
        if not payload:
            continue
        rows = _fundamental_rows_for_stock(stock_id, payload)
        if rows:
            cached_stock_count += 1
            fundamental_rows.extend(rows)

    cache_coverage = round(cached_stock_count / len(stock_ids), 4) if stock_ids else 0.0
    if not fundamental_rows:
        return _coerce_fundamental_columns(result), cache_coverage

    fundamentals = pd.DataFrame(fundamental_rows)
    fundamentals["stock_id"] = fundamentals["stock_id"].astype(str)
    fundamentals["fundamental_available_from"] = pd.to_datetime(fundamentals["fundamental_available_from"]).dt.normalize()
    fundamentals = fundamentals.sort_values(["stock_id", "fundamental_available_from"])

    joined_parts: list[pd.DataFrame] = []
    for stock_id, stock_frame in result.sort_values(["stock_id", "trade_date"]).groupby("stock_id", sort=False):
        stock_fundamentals = fundamentals[fundamentals["stock_id"] == stock_id]
        if stock_fundamentals.empty:
            joined_parts.append(stock_frame)
            continue
        base = stock_frame.drop(columns=list(FUNDAMENTAL_FEATURE_COLUMNS), errors="ignore").sort_values("trade_date")
        joined = pd.merge_asof(
            base,
            stock_fundamentals.drop(columns=["stock_id"]).sort_values("fundamental_available_from"),
            left_on="trade_date",
            right_on="fundamental_available_from",
            direction="backward",
        )
        joined["stock_id"] = stock_id
        joined_parts.append(joined)

    result = pd.concat(joined_parts, ignore_index=True).sort_values(["trade_date", "stock_id"]).copy()
    for col in FUNDAMENTAL_FEATURE_COLUMNS:
        if col not in result.columns:
            result[col] = pd.NA
    return _coerce_fundamental_columns(result), cache_coverage


def _coerce_fundamental_columns(frame: pd.DataFrame) -> pd.DataFrame:
    result = frame.copy()
    for col in FUNDAMENTAL_FEATURE_COLUMNS:
        if col not in result.columns:
            result[col] = pd.NA
        result[col] = pd.to_numeric(result[col], errors="coerce").astype("Float64")
    return result


def _fundamental_rows_for_stock(stock_id: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
    metrics = _metrics_from_payload(payload)
    rows: list[dict[str, Any]] = []
    for metric in metrics:
        raw = metric.to_dict() if isinstance(metric, FinancialYearMetrics) else dict(metric)
        available_from = _available_from(raw, payload)
        if available_from is None:
            continue
        row: dict[str, Any] = {
            "stock_id": str(stock_id),
            "fundamental_available_from": available_from,
        }
        for name in FUNDAMENTAL_METRIC_NAMES:
            row[f"fundamental_{name}"] = raw.get(name)
        rows.append(row)
    return rows


def _metrics_from_payload(payload: dict[str, Any]) -> list[FinancialYearMetrics | dict[str, Any]]:
    if payload.get("metrics"):
        return list(payload["metrics"])
    financials = payload.get("financials_by_year") or {}
    return list(compute_financial_metrics(financials))


def _available_from(metric: dict[str, Any], payload: dict[str, Any]) -> pd.Timestamp | None:
    for key in ("available_from", "published_at", "as_of_date"):
        value = metric.get(key) or payload.get(key)
        if value:
            parsed = pd.to_datetime(value, errors="coerce")
            if pd.notna(parsed):
                return pd.Timestamp(parsed).normalize()

    year_value = metric.get("year")
    if year_value is None:
        return None
    try:
        year = int(str(year_value)[:4])
    except ValueError:
        return None

    quarter = metric.get("quarter") or metric.get("fiscal_quarter")
    if quarter:
        try:
            q = int(str(quarter).replace("Q", "").replace("q", ""))
        except ValueError:
            q = 0
        quarter_end_month = {1: 3, 2: 6, 3: 9, 4: 12}.get(q)
        if quarter_end_month:
            quarter_end = pd.Timestamp(year=year, month=quarter_end_month, day=1) + pd.offsets.MonthEnd(0)
            return pd.Timestamp(quarter_end + pd.Timedelta(days=45)).normalize()

    # 年報未提供發布日時，保守視為次年 4/1 才可被模型使用。
    return pd.Timestamp(year=year + 1, month=4, day=1)


def _metadata(
    frame: pd.DataFrame,
    technical_columns: list[str],
    event_columns: list[str],
    pattern_columns: list[str],
    fundamental_columns: list[str],
    fundamental_cache_coverage: float,
    notes: list[str],
) -> FeatureFrameMetadata:
    groups = {
        "technical": _group_metadata(frame, technical_columns),
        "event": _group_metadata(frame, event_columns),
        "pattern": _group_metadata(frame, pattern_columns),
        "fundamental": _group_metadata(frame, fundamental_columns),
    }
    if frame.empty:
        start_date = end_date = None
    else:
        start_date = str(pd.to_datetime(frame["trade_date"]).min().date())
        end_date = str(pd.to_datetime(frame["trade_date"]).max().date())
    return FeatureFrameMetadata(
        feature_groups=groups,
        rows=len(frame),
        stocks=int(frame["stock_id"].nunique()) if "stock_id" in frame.columns else 0,
        start_date=start_date,
        end_date=end_date,
        fundamental_cache_coverage=fundamental_cache_coverage,
        notes=notes,
    )


def _group_metadata(frame: pd.DataFrame, columns: list[str]) -> FeatureGroupMetadata:
    coverage: dict[str, float] = {}
    missing_ratio: dict[str, float] = {}
    for col in columns:
        if col not in frame.columns or len(frame) == 0:
            coverage[col] = 0.0
            missing_ratio[col] = 1.0
            continue
        col_coverage = float(frame[col].notna().mean())
        coverage[col] = round(col_coverage, 4)
        missing_ratio[col] = round(1 - col_coverage, 4)
    return FeatureGroupMetadata(columns=columns, coverage=coverage, missing_ratio=missing_ratio)


def _ensure_unique_trade_keys(df: pd.DataFrame, dataset_name: str) -> None:
    if df.empty or not set(KEY_COLUMNS).issubset(df.columns):
        return
    duplicate_mask = df.duplicated(list(KEY_COLUMNS), keep=False)
    if not duplicate_mask.any():
        return
    sample = (
        df.loc[duplicate_mask, list(KEY_COLUMNS)]
        .drop_duplicates()
        .head(5)
        .assign(trade_date=lambda x: x["trade_date"].dt.strftime("%Y-%m-%d"))
        .to_dict("records")
    )
    raise ValueError(f"{dataset_name} 含同股同交易日多筆資料，請先聚合成日頻資料: {sample}")
