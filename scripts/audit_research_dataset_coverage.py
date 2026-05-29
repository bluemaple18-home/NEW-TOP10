#!/usr/bin/env python3
"""週末大量測試前的資料覆蓋 audit。

此腳本只讀既有資料與 artifact，不抓資料、不訓練、不修改 ranking。
用途：判斷每個研究維度目前可否進測試矩陣，避免用大量缺值做假結論。
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "research-dataset-coverage.v1"
READY_LATEST_COVERAGE = 0.80
READY_REFERENCE_COVERAGE = 0.95
MODEL_MIN_COVERAGE = 0.70

PRICE_VOLUME_COLUMNS = ["open", "high", "low", "close", "volume", "value", "avg_volume_20d", "avg_value_20d"]
TECHNICAL_COLUMNS = [
    "ma5",
    "ma10",
    "ma20",
    "ma60",
    "macd",
    "macd_signal",
    "rsi",
    "k",
    "d",
    "bb_width",
    "pct_from_high_60d",
    "pct_from_low_60d",
]
PATTERN_PREFIXES = ("candle_", "td_", "pattern_")
EVENT_COLUMNS = [
    "break_20d_high",
    "ma5_cross_ma20_up",
    "macd_bullish_cross",
    "volume_spike_1.5x",
    "gap_up_close_strong",
]
REVENUE_COLUMNS = ["revenue_yoy", "revenue_mom"]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="audit research dataset coverage")
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--reference-dir", default="data/reference")
    parser.add_argument("--artifacts-dir", default="artifacts")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def date_text(value: Any) -> str | None:
    if value is None or pd.isna(value):
        return None
    return pd.to_datetime(value).date().isoformat()


def normalize_stock_ids(values: pd.Series) -> set[str]:
    return set(values.astype(str).str.strip().str.zfill(4).dropna())


def coverage_status(latest_coverage: float, overall_coverage: float | None = None, ready_threshold: float = READY_LATEST_COVERAGE) -> str:
    overall = latest_coverage if overall_coverage is None else overall_coverage
    if latest_coverage >= ready_threshold and overall >= 0.60:
        return "READY"
    if latest_coverage >= 0.50 and overall >= 0.30:
        return "WATCH"
    return "BLOCKED_DATA"


def can_enter_model(status: str, latest_coverage: float) -> bool:
    return status == "READY" and latest_coverage >= MODEL_MIN_COVERAGE


def load_parquet(path: Path) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"資料不存在：{path}")
    return pd.read_parquet(path)


def date_column(frame: pd.DataFrame) -> str:
    if "trade_date" in frame.columns:
        return "trade_date"
    if "date" in frame.columns:
        return "date"
    raise ValueError("資料缺少 date/trade_date 欄位")


def latest_slice(frame: pd.DataFrame, date_col: str) -> pd.DataFrame:
    if frame.empty:
        return frame
    normalized = pd.to_datetime(frame[date_col], errors="coerce").dt.normalize()
    latest = normalized.max()
    return frame[normalized == latest].copy()


def column_group_row(
    *,
    dimension_id: str,
    label: str,
    frame: pd.DataFrame,
    columns: list[str],
    category: str,
    ready_threshold: float = READY_LATEST_COVERAGE,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    date_col = date_column(frame)
    existing = [col for col in columns if col in frame.columns]
    missing = [col for col in columns if col not in frame.columns]
    if not existing:
        latest_coverage = 0.0
        overall_coverage = 0.0
    else:
        overall_coverage = float(frame[existing].notna().mean().mean())
        latest = latest_slice(frame, date_col)
        latest_coverage = float(latest[existing].notna().mean().mean()) if not latest.empty else 0.0
    status = coverage_status(latest_coverage, overall_coverage, ready_threshold)
    note_values = list(notes or [])
    if missing:
        note_values.append("缺欄位：" + ",".join(missing))
    return {
        "dimension_id": dimension_id,
        "label": label,
        "category": category,
        "status": status,
        "can_enter_weekend_matrix": status in {"READY", "WATCH"},
        "can_enter_model": can_enter_model(status, latest_coverage),
        "overall_coverage": round(overall_coverage, 6),
        "latest_coverage": round(latest_coverage, 6),
        "column_count": len(existing),
        "missing_columns": missing,
        "notes": note_values,
    }


def reference_row(
    *,
    dimension_id: str,
    label: str,
    path: Path,
    latest_universe_ids: set[str],
    stock_column: str = "stock_id",
    category: str = "reference",
    model_eligible: bool = False,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    if not path.exists():
        return {
            "dimension_id": dimension_id,
            "label": label,
            "category": category,
            "status": "BLOCKED_DATA",
            "can_enter_weekend_matrix": False,
            "can_enter_model": False,
            "latest_stock_coverage": 0.0,
            "row_count": 0,
            "path": repo_path(path),
            "notes": ["檔案不存在"],
        }
    frame = pd.read_csv(path, dtype={stock_column: str})
    ids = normalize_stock_ids(frame[stock_column]) if stock_column in frame.columns else set()
    overlap = latest_universe_ids.intersection(ids)
    coverage = len(overlap) / len(latest_universe_ids) if latest_universe_ids else 0.0
    status = coverage_status(coverage, coverage, READY_REFERENCE_COVERAGE)
    return {
        "dimension_id": dimension_id,
        "label": label,
        "category": category,
        "status": status,
        "can_enter_weekend_matrix": status in {"READY", "WATCH"},
        "can_enter_model": model_eligible and can_enter_model(status, coverage),
        "latest_stock_coverage": round(coverage, 6),
        "covered_stocks": len(overlap),
        "universe_stocks": len(latest_universe_ids),
        "row_count": int(len(frame)),
        "path": repo_path(path),
        "notes": list(notes or []),
    }


def fundamental_row(fundamentals_dir: Path, latest_universe_ids: set[str], artifacts_dir: Path) -> dict[str, Any]:
    files = sorted(fundamentals_dir.glob("*.json")) if fundamentals_dir.exists() else []
    cache_ids = {path.stem.zfill(4) for path in files}
    cache_overlap = latest_universe_ids.intersection(cache_ids)
    cache_coverage = len(cache_overlap) / len(latest_universe_ids) if latest_universe_ids else 0.0
    score_coverage = cache_coverage
    score_available = None
    report_path = artifacts_dir / "fundamental_shadow_report.json"
    notes = ["Goodinfo cache 已存在，但目前未達模型接入門檻。"]
    if report_path.exists():
        report = json.loads(report_path.read_text(encoding="utf-8"))
        summary = report.get("summary", {})
        evaluation = report.get("evaluation", {})
        score_coverage = float(evaluation.get("latest_score_coverage") or summary.get("score_coverage") or cache_coverage)
        score_available = summary.get("available")
        notes.append(f"fundamental shadow IC={evaluation.get('ic')} top_bottom_spread={evaluation.get('top_bottom_spread')}")
    status = coverage_status(score_coverage, cache_coverage, MODEL_MIN_COVERAGE)
    if score_coverage < MODEL_MIN_COVERAGE:
        status = "BLOCKED_DATA"
    return {
        "dimension_id": "fundamentals_goodinfo",
        "label": "基本面 Goodinfo 年財報",
        "category": "fundamental",
        "status": status,
        "can_enter_weekend_matrix": status in {"READY", "WATCH"},
        "can_enter_model": False,
        "latest_stock_coverage": round(score_coverage, 6),
        "cache_stock_coverage": round(cache_coverage, 6),
        "cached_files": len(files),
        "covered_stocks": len(cache_overlap),
        "scored_stocks": score_available,
        "universe_stocks": len(latest_universe_ids),
        "path": repo_path(fundamentals_dir),
        "notes": notes,
    }


def market_regime_row(path: Path, latest_date: str | None) -> dict[str, Any]:
    if not path.exists():
        return blocked_artifact_row("market_regime_history", "大盤盤勢分類", "market", path, "market regime artifact 不存在")
    payload = json.loads(path.read_text(encoding="utf-8"))
    rows = payload.get("rows", [])
    latest_row = rows[-1] if rows else {}
    artifact_latest = str(latest_row.get("trade_date") or "")
    status = "READY" if rows and artifact_latest == latest_date else "WATCH" if rows else "BLOCKED_DATA"
    return {
        "dimension_id": "market_regime_history",
        "label": "大盤盤勢分類",
        "category": "market",
        "status": status,
        "can_enter_weekend_matrix": status in {"READY", "WATCH"},
        "can_enter_model": False,
        "row_count": len(rows),
        "latest_artifact_date": artifact_latest or None,
        "latest_expected_date": latest_date,
        "latest_regime": latest_row.get("regime_label"),
        "path": repo_path(path),
        "notes": ["可作 replay 分層與 shadow overlay；正式模型仍需更長跨盤勢歷史。"],
    }


def market_context_row(artifacts_dir: Path, latest_date: str | None) -> dict[str, Any]:
    path = artifacts_dir / f"market_context_{latest_date}.json" if latest_date else artifacts_dir / "market_context_latest.json"
    if not path.exists():
        return blocked_artifact_row("market_context", "大盤資金/三大法人 context", "market", path, "latest market_context artifact 不存在")
    payload = json.loads(path.read_text(encoding="utf-8"))
    sections = ["taiex", "breadth", "institutional", "futures"]
    present = 0
    total = 0
    for section in sections:
        values = payload.get(section, {})
        if isinstance(values, dict):
            for value in values.values():
                total += 1
                present += int(value is not None)
    completeness = present / total if total else 0.0
    status = "READY" if completeness >= 0.70 else "WATCH" if completeness >= 0.30 else "BLOCKED_DATA"
    return {
        "dimension_id": "market_context",
        "label": "大盤資金/三大法人 context",
        "category": "market",
        "status": status,
        "can_enter_weekend_matrix": status in {"READY", "WATCH"},
        "can_enter_model": False,
        "latest_coverage": round(completeness, 6),
        "present_fields": present,
        "total_fields": total,
        "path": repo_path(path),
        "notes": ["適合通知/盤勢解釋；若要進模型需另做 as-of 特徵化。"],
    }


def blocked_artifact_row(dimension_id: str, label: str, category: str, path: Path, note: str) -> dict[str, Any]:
    return {
        "dimension_id": dimension_id,
        "label": label,
        "category": category,
        "status": "BLOCKED_DATA",
        "can_enter_weekend_matrix": False,
        "can_enter_model": False,
        "path": repo_path(path),
        "notes": [note],
    }


def build_audit(args: argparse.Namespace) -> dict[str, Any]:
    data_dir = resolve_path(args.data_dir)
    reference_dir = resolve_path(args.reference_dir)
    artifacts_dir = resolve_path(args.artifacts_dir)
    features = load_parquet(data_dir / "features.parquet")
    universe = load_parquet(data_dir / "universe.parquet")
    features_date_col = date_column(features)
    universe_date_col = date_column(universe)
    latest_features = latest_slice(features, features_date_col)
    latest_universe = latest_slice(universe, universe_date_col)
    latest_date = date_text(latest_features[features_date_col].max()) if not latest_features.empty else None
    latest_universe_ids = normalize_stock_ids(latest_universe["stock_id"]) if "stock_id" in latest_universe.columns else set()

    pattern_columns = [col for col in features.columns if col.startswith(PATTERN_PREFIXES)]
    rows = [
        column_group_row(
            dimension_id="price_volume",
            label="價量/流動性",
            frame=features,
            columns=PRICE_VOLUME_COLUMNS,
            category="price",
        ),
        column_group_row(
            dimension_id="technical_momentum",
            label="技術/趨勢動能",
            frame=features,
            columns=TECHNICAL_COLUMNS,
            category="technical",
        ),
        column_group_row(
            dimension_id="pattern_signals",
            label="K 線/型態訊號",
            frame=features,
            columns=pattern_columns,
            category="pattern",
            notes=[f"pattern column count={len(pattern_columns)}"],
        ),
        column_group_row(
            dimension_id="event_signals",
            label="事件/突破訊號",
            frame=features,
            columns=EVENT_COLUMNS,
            category="event",
        ),
        column_group_row(
            dimension_id="monthly_revenue",
            label="月營收 YoY/MoM",
            frame=features,
            columns=REVENUE_COLUMNS,
            category="fundamental",
            ready_threshold=MODEL_MIN_COVERAGE,
            notes=["目前 features 有欄位，但若 coverage 太低不可進測試矩陣。"],
        ),
        reference_row(
            dimension_id="industry_reference",
            label="產業分類",
            path=reference_dir / "stock_industry_map.csv",
            latest_universe_ids=latest_universe_ids,
            model_eligible=False,
            notes=["可用於產業強度、族群集中度與通知解釋。"],
        ),
        reference_row(
            dimension_id="concept_reference",
            label="概念/題材 membership",
            path=reference_dir / "stock_concept_membership.csv",
            latest_universe_ids=latest_universe_ids,
            model_eligible=False,
            notes=["可用於題材標籤與族群敘事；進模型前需再做去噪。"],
        ),
        fundamental_row(PROJECT_ROOT / "data" / "fundamentals", latest_universe_ids, artifacts_dir),
        market_regime_row(artifacts_dir / f"market_regime_history_{latest_date}.json", latest_date),
        market_context_row(artifacts_dir, latest_date),
        blocked_artifact_row(
            "per_stock_chip_flow",
            "個股籌碼/法人買賣超",
            "chip",
            PROJECT_ROOT / "data" / "chip",
            "尚未找到可覆蓋 universe 的個股籌碼日頻資料。",
        ),
    ]
    status_counts: dict[str, int] = {}
    for row in rows:
        status_counts[row["status"]] = status_counts.get(row["status"], 0) + 1
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "does_not_fetch_data": True,
            "does_not_train_model": True,
            "does_not_change_ranking": True,
            "ready_latest_coverage": READY_LATEST_COVERAGE,
            "ready_reference_coverage": READY_REFERENCE_COVERAGE,
            "model_min_coverage": MODEL_MIN_COVERAGE,
        },
        "inputs": {
            "data_dir": repo_path(data_dir),
            "reference_dir": repo_path(reference_dir),
            "artifacts_dir": repo_path(artifacts_dir),
            "latest_date": latest_date,
            "feature_rows": int(len(features)),
            "feature_stocks": int(features["stock_id"].astype(str).nunique()) if "stock_id" in features.columns else 0,
            "latest_universe_stocks": len(latest_universe_ids),
        },
        "summary": {
            "status_counts": status_counts,
            "ready_dimensions": [row["dimension_id"] for row in rows if row["status"] == "READY"],
            "watch_dimensions": [row["dimension_id"] for row in rows if row["status"] == "WATCH"],
            "blocked_dimensions": [row["dimension_id"] for row in rows if row["status"] == "BLOCKED_DATA"],
            "weekend_matrix_dimensions": [
                row["dimension_id"]
                for row in rows
                if row.get("can_enter_weekend_matrix")
            ],
            "model_candidate_dimensions": [
                row["dimension_id"]
                for row in rows
                if row.get("can_enter_model")
            ],
        },
        "dimensions": rows,
    }


def pct(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.1%}"
    except (TypeError, ValueError):
        return "n/a"


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Research Dataset Coverage",
        "",
        f"- generated_at：{payload['generated_at']}",
        f"- latest_date：{payload['inputs']['latest_date']}",
        f"- latest_universe_stocks：{payload['inputs']['latest_universe_stocks']}",
        f"- status_counts：{payload['summary']['status_counts']}",
        "",
        "| Dimension | Status | Weekend Matrix | Model | Latest Coverage | Notes |",
        "|---|---|---:|---:|---:|---|",
    ]
    for row in payload["dimensions"]:
        latest = row.get("latest_coverage", row.get("latest_stock_coverage"))
        notes = "；".join(str(note) for note in row.get("notes", []))
        lines.append(
            "| {label} | {status} | {weekend} | {model} | {latest} | {notes} |".format(
                label=row["label"],
                status=row["status"],
                weekend="Y" if row.get("can_enter_weekend_matrix") else "N",
                model="Y" if row.get("can_enter_model") else "N",
                latest=pct(latest),
                notes=notes,
            )
        )
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    payload = build_audit(args)
    latest_date = payload["inputs"]["latest_date"] or datetime.now().strftime("%Y-%m-%d")
    output_path = resolve_path(args.output) if args.output else PROJECT_ROOT / "artifacts" / f"research_dataset_coverage_{latest_date}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK",
                "output": repo_path(output_path),
                "ready": payload["summary"]["ready_dimensions"],
                "watch": payload["summary"]["watch_dimensions"],
                "blocked": payload["summary"]["blocked_dimensions"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
