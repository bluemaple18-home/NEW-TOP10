"""每日報牌 v2 正式資料 shadow 排名比較契約。"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
from pathlib import Path
from typing import Any

import pandas as pd


RANKING_COMPARISON_SCHEMA_VERSION = "top10.daily-v2.ranking-comparison.v1"
REAL_SHADOW_MANIFEST_SCHEMA_VERSION = "top10.daily-v2.real-shadow-manifest.v1"
CORE_NUMERIC_COLUMNS = (
    "risk_adjusted_score",
    "final_score",
    "prediction_score",
    "model_prob",
    "rule_score",
    "setup_score",
    "quality_score",
    "risk_penalty",
    "score",
)
ALLOWED_ADDITIVE_SHADOW_COLUMNS = frozenset(
    {
        "strategy_route_regime",
        "strategy_route_production",
        "strategy_route_shadow",
        "strategy_route_report_only",
        "strategy_route_blocked",
        "strategy_route_mutates_production_score",
    }
)


@dataclass(frozen=True)
class RankingComparisonPolicy:
    """排名比較的數值容忍值與核心分數欄位。"""

    numeric_tolerance: float = 1e-9
    core_numeric_columns: tuple[str, ...] = CORE_NUMERIC_COLUMNS

    def __post_init__(self) -> None:
        if not math.isfinite(self.numeric_tolerance) or self.numeric_tolerance < 0:
            raise ValueError("numeric_tolerance must be a finite non-negative number")


def build_ranking_comparison(
    *,
    baseline_path: Path,
    shadow_path: Path,
    input_snapshots: dict[str, dict[str, Any]],
    numeric_tolerance: float = 1e-9,
    runtime_versions: dict[str, str] | None = None,
    model_compatibility: dict[str, Any] | None = None,
    run_date: str | None = None,
) -> dict[str, Any]:
    """比較 baseline 與 shadow Top10，回傳可序列化的 deterministic 證據。"""

    policy = RankingComparisonPolicy(numeric_tolerance=numeric_tolerance)
    baseline = _read_ranking(baseline_path)
    shadow = _read_ranking(shadow_path)

    baseline_columns = list(baseline.columns)
    shadow_columns = list(shadow.columns)
    missing_in_shadow = [column for column in baseline_columns if column not in shadow_columns]
    extra_in_shadow = [column for column in shadow_columns if column not in baseline_columns]
    allowed_additive_in_shadow = [
        column for column in extra_in_shadow if column in ALLOWED_ADDITIVE_SHADOW_COLUMNS
    ]
    unexpected_extra_in_shadow = [
        column for column in extra_in_shadow if column not in ALLOWED_ADDITIVE_SHADOW_COLUMNS
    ]
    schema_blocking = bool(missing_in_shadow or unexpected_extra_in_shadow)
    rank_source = "position" if "rank" not in baseline and "rank" not in shadow else "rank"

    baseline_errors, baseline_ids = _validate_top10(baseline, "baseline", rank_source)
    shadow_errors, shadow_ids = _validate_top10(shadow, "shadow", rank_source)
    overlap_count = len(set(baseline_ids) & set(shadow_ids))
    same_order = baseline_ids == shadow_ids and len(baseline_ids) == 10
    rank_changes = _rank_changes(baseline, shadow)
    numeric_differences = _numeric_differences(baseline, shadow, policy)

    reasons: list[str] = []
    if schema_blocking:
        reasons.append("baseline 與 shadow schema 欄位不一致")
    reasons.extend(baseline_errors)
    reasons.extend(shadow_errors)
    if overlap_count != 10:
        reasons.append(f"Top10 overlap 必須為 10，實際為 {overlap_count}")
    if not same_order:
        reasons.append("Top10 股票順序不一致")
    if not numeric_differences["core_columns"]:
        reasons.append("沒有可比較的共同核心分數欄位")
    elif not numeric_differences["core_within_tolerance"]:
        reasons.append("共同核心分數欄位超出 tolerance")

    status = "GO" if not reasons else "NO-GO"
    compatibility = _normalize_model_compatibility(model_compatibility)
    production_reasons = list(reasons)
    if compatibility["version_mismatch"]:
        production_reasons.append("模型 pickle 與 runtime package 版本不一致")
    production_status = "GO" if not production_reasons else "NO-GO"

    return {
        "schema_version": RANKING_COMPARISON_SCHEMA_VERSION,
        "run_date": run_date,
        "status": status,
        "inputs": input_snapshots,
        "outputs": {
            "baseline": _file_snapshot(baseline_path),
            "shadow": _file_snapshot(shadow_path),
        },
        "runtime_versions": dict(runtime_versions or {}),
        "model_compatibility": compatibility,
        "schema": {
            "baseline_columns": baseline_columns,
            "shadow_columns": shadow_columns,
            "missing_in_shadow": missing_in_shadow,
            "extra_in_shadow": extra_in_shadow,
            "allowed_additive_in_shadow": allowed_additive_in_shadow,
            "unexpected_extra_in_shadow": unexpected_extra_in_shadow,
            "column_order_equal": baseline_columns == shadow_columns,
            "blocking": schema_blocking,
        },
        "top10": {
            "baseline_count": len(baseline),
            "shadow_count": len(shadow),
            "baseline_stock_ids": baseline_ids,
            "shadow_stock_ids": shadow_ids,
            "overlap_count": overlap_count,
            "same_order": same_order,
            "rank_source": rank_source,
            "baseline_errors": baseline_errors,
            "shadow_errors": shadow_errors,
        },
        "rank_changes": rank_changes,
        "numeric_differences": numeric_differences,
        "conclusion": {
            "status": status,
            "reasons": reasons,
        },
        "production_switch": {
            "status": production_status,
            "executed": False,
            "reasons": production_reasons,
        },
    }


def _file_snapshot(path: Path) -> dict[str, Any]:
    path = Path(path).expanduser().resolve()
    return {
        "path": str(path),
        "exists": path.is_file(),
        "size_bytes": path.stat().st_size,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
    }


def _read_ranking(path: Path) -> pd.DataFrame:
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"ranking file not found: {path}")
    return pd.read_csv(path, encoding="utf-8-sig", dtype={"stock_id": "string"})


def _validate_top10(
    frame: pd.DataFrame,
    label: str,
    rank_source: str,
) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    if "stock_id" not in frame.columns:
        return [f"{label} 缺少 stock_id 欄位"], []

    stock_ids = frame["stock_id"].fillna("").astype(str).str.strip().tolist()
    if len(frame) != 10:
        errors.append(f"{label} 必須正好 10 筆，實際為 {len(frame)}")
    if any(not stock_id for stock_id in stock_ids):
        errors.append(f"{label} stock_id 不得為空")
    if len(set(stock_ids)) != len(stock_ids):
        errors.append(f"{label} stock_id 不得重複")
    if "rank" not in frame.columns and rank_source != "position":
        errors.append(f"{label} 缺少 rank 欄位")
    elif rank_source != "position":
        ranks = pd.to_numeric(frame["rank"], errors="coerce")
        if ranks.isna().any() or ranks.tolist() != list(range(1, 11)):
            errors.append(f"{label} rank 必須依序為 1..10")
    return errors, stock_ids


def _rank_changes(baseline: pd.DataFrame, shadow: pd.DataFrame) -> list[dict[str, Any]]:
    baseline_ranks = _rank_map(baseline)
    shadow_ranks = _rank_map(shadow)
    stock_ids = list(baseline_ranks)
    stock_ids.extend(stock_id for stock_id in shadow_ranks if stock_id not in baseline_ranks)
    result: list[dict[str, Any]] = []
    for stock_id in stock_ids:
        baseline_rank = baseline_ranks.get(stock_id)
        shadow_rank = shadow_ranks.get(stock_id)
        if baseline_rank is None:
            status = "added"
        elif shadow_rank is None:
            status = "removed"
        elif baseline_rank == shadow_rank:
            status = "unchanged"
        else:
            status = "moved"
        result.append(
            {
                "stock_id": stock_id,
                "baseline_rank": baseline_rank,
                "shadow_rank": shadow_rank,
                "rank_delta": (
                    shadow_rank - baseline_rank
                    if baseline_rank is not None and shadow_rank is not None
                    else None
                ),
                "status": status,
            }
        )
    return result


def _rank_map(frame: pd.DataFrame) -> dict[str, int]:
    if "stock_id" not in frame.columns:
        return {}
    result: dict[str, int] = {}
    for position, (_, row) in enumerate(frame.iterrows(), start=1):
        raw_stock_id = row.get("stock_id")
        stock_id = "" if pd.isna(raw_stock_id) else str(raw_stock_id).strip()
        if not stock_id or stock_id in result:
            continue
        rank_value = pd.to_numeric(pd.Series([row.get("rank")]), errors="coerce").iloc[0]
        result[stock_id] = int(rank_value) if pd.notna(rank_value) else position
    return result


def _numeric_differences(
    baseline: pd.DataFrame,
    shadow: pd.DataFrame,
    policy: RankingComparisonPolicy,
) -> dict[str, Any]:
    common_columns = [
        column
        for column in baseline.columns
        if column in shadow.columns and column not in {"rank", "stock_id"}
    ]
    numeric_columns = [
        column
        for column in common_columns
        if _is_numeric_column(baseline[column]) and _is_numeric_column(shadow[column])
    ]
    baseline_indexed = _index_by_stock_id(baseline)
    shadow_indexed = _index_by_stock_id(shadow)
    common_ids = [stock_id for stock_id in baseline_indexed.index if stock_id in shadow_indexed.index]

    column_results: dict[str, Any] = {}
    for column in numeric_columns:
        rows: list[dict[str, Any]] = []
        finite_differences: list[float] = []
        for stock_id in common_ids:
            baseline_value = _finite_number(baseline_indexed.at[stock_id, column])
            shadow_value = _finite_number(shadow_indexed.at[stock_id, column])
            if baseline_value is None and shadow_value is None:
                difference = None
                within_tolerance = True
            elif baseline_value is None or shadow_value is None:
                difference = None
                within_tolerance = False
            else:
                difference = abs(shadow_value - baseline_value)
                finite_differences.append(difference)
                within_tolerance = difference <= policy.numeric_tolerance
            rows.append(
                {
                    "stock_id": stock_id,
                    "baseline": baseline_value,
                    "shadow": shadow_value,
                    "absolute_difference": difference,
                    "within_tolerance": within_tolerance,
                }
            )
        column_results[column] = {
            "compared_count": len(rows),
            "max_absolute_difference": max(finite_differences, default=None),
            "within_tolerance": bool(rows) and all(row["within_tolerance"] for row in rows),
            "rows": rows,
        }

    core_columns = [column for column in policy.core_numeric_columns if column in column_results]
    core_within_tolerance = bool(core_columns) and all(
        column_results[column]["within_tolerance"] for column in core_columns
    )
    return {
        "tolerance": policy.numeric_tolerance,
        "common_numeric_columns": numeric_columns,
        "core_columns": core_columns,
        "core_within_tolerance": core_within_tolerance,
        "all_within_tolerance": bool(column_results)
        and all(result["within_tolerance"] for result in column_results.values()),
        "columns": column_results,
    }


def _is_numeric_column(series: pd.Series) -> bool:
    present = series.notna() & series.astype(str).str.strip().ne("")
    if not present.any():
        return False
    converted = pd.to_numeric(series[present], errors="coerce")
    return converted.notna().all()


def _index_by_stock_id(frame: pd.DataFrame) -> pd.DataFrame:
    if "stock_id" not in frame.columns:
        return pd.DataFrame()
    result = frame.copy()
    result["stock_id"] = result["stock_id"].fillna("").astype(str).str.strip()
    return result.drop_duplicates("stock_id", keep="first").set_index("stock_id")


def _finite_number(value: Any) -> float | None:
    if pd.isna(value):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _normalize_model_compatibility(payload: dict[str, Any] | None) -> dict[str, Any]:
    source = payload or {}
    return {
        "status": str(source.get("status") or "OK"),
        "version_mismatch": source.get("version_mismatch") is True,
        "warnings": list(source.get("warnings") or []),
    }
