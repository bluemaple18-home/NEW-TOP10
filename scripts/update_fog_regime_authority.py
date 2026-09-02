#!/usr/bin/env python3
"""以 append-only extension 更新 fog 使用的 v2 regime authority。"""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def rows_by_date(
    payload: dict[str, Any], schema: str, *, require_as_of: bool
) -> dict[str, dict[str, Any]]:
    if payload.get("schema_version") != schema:
        raise ValueError(f"regime schema 不符：預期 {schema}")
    rows = payload.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError("regime rows 不可為空")
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        date = str(row.get("trade_date") or "")
        if (
            not date
            or (require_as_of and row.get("as_of_date") != date)
            or date in indexed
        ):
            raise ValueError("regime row 日期／as-of 不合法或重複")
        indexed[date] = row
    return indexed


def merge_append_only(
    base: dict[str, Any],
    extension: dict[str, Any],
    expected_dates: list[str],
) -> tuple[dict[str, Any], dict[str, Any]]:
    base_rows = rows_by_date(base, "market-regime-history.v2", require_as_of=True)
    extension_rows = rows_by_date(
        extension, "market-regime-history-append-only.v1", require_as_of=False
    )
    base_end = max(base_rows)
    extension_end = max(extension_rows)
    new_dates = sorted(date for date in extension_rows if date > base_end)
    required_dates = sorted(date for date in expected_dates if base_end < date <= extension_end)
    if new_dates != required_dates:
        raise ValueError("append-only extension 未完整覆蓋 features 新交易日")
    if any(extension_rows[date].get("as_of_date") != date for date in new_dates):
        raise ValueError("append-only extension 新日期缺少一致 as-of")
    merged_rows = [base_rows[date] for date in sorted(base_rows)] + [
        extension_rows[date] for date in new_dates
    ]
    payload = dict(base)
    payload["generated_at"] = datetime.now(timezone.utc).isoformat()
    payload["rows"] = merged_rows
    payload["summary"] = {
        "trade_days": len(merged_rows),
        "start_date": merged_rows[0]["trade_date"],
        "end_date": merged_rows[-1]["trade_date"],
        "regime_counts": dict(Counter(row["regime_label"] for row in merged_rows)),
    }
    payload["inputs"] = {
        **(base.get("inputs") if isinstance(base.get("inputs"), dict) else {}),
        "append_only_extension": "artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json",
    }
    contract = dict(payload.get("contract") or {})
    contract.update(
        {
            "append_only": True,
            "historical_relabel_allowed": False,
            "overlap_uses_base": True,
        }
    )
    payload["contract"] = contract
    receipt = {
        "schema_version": "fog-regime-authority-update.v1",
        "status": "APPENDED" if new_dates else "NO_NEW_REGIME_DATES",
        "base_end_before": base_end,
        "extension_end": extension_end,
        "end_after": merged_rows[-1]["trade_date"],
        "appended_days": len(new_dates),
        "historical_rows_preserved": len(base_rows),
    }
    return payload, receipt


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", default="artifacts/market_regime_history.json")
    parser.add_argument(
        "--extension",
        default="artifacts/model_experiments/market_regime_history_append_only_2026-07-22.json",
    )
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--receipt", default="artifacts/autonomous_research/fog_regime_authority_update_latest.json")
    args = parser.parse_args()
    resolve = lambda value: Path(value) if Path(value).is_absolute() else PROJECT_ROOT / value
    base_path, extension_path, features_path, receipt_path = map(
        resolve, (args.base, args.extension, args.features, args.receipt)
    )
    expected_dates = sorted(
        pd.to_datetime(pd.read_parquet(features_path, columns=["date"])["date"])
        .dt.strftime("%Y-%m-%d")
        .unique()
        .tolist()
    )
    merged, receipt = merge_append_only(
        read_json(base_path), read_json(extension_path), expected_dates
    )
    if receipt["appended_days"]:
        atomic_write(base_path, json.dumps(merged, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    atomic_write(receipt_path, json.dumps(receipt, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    print(json.dumps(receipt, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
