#!/usr/bin/env python3
"""合併 append-only market regime history，禁止覆寫既有日期標籤。"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "market-regime-history-append-only.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="append-only market regime history")
    parser.add_argument("--base", required=True)
    parser.add_argument("--extension", required=True)
    parser.add_argument("--output", required=True)
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_payload(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload.get("rows"), list) or not payload["rows"]:
        raise ValueError(f"regime history 缺少 rows：{path}")
    return payload


def keyed_rows(payload: dict[str, Any], source: str) -> dict[str, dict[str, Any]]:
    result = {}
    for row in payload["rows"]:
        date = str(row.get("trade_date") or "").strip()
        label = str(row.get("regime_label") or "").strip()
        if not date or not label:
            raise ValueError(f"{source} 含空 trade_date/regime_label")
        if date in result:
            raise ValueError(f"{source} 含重複 trade_date：{date}")
        result[date] = row
    return result


def merge_histories(base: dict[str, Any], extension: dict[str, Any]) -> dict[str, Any]:
    base_rows = keyed_rows(base, "base")
    extension_rows = keyed_rows(extension, "extension")
    base_end = max(base_rows)
    overlap = sorted(set(base_rows) & set(extension_rows))
    drift = [
        {
            "trade_date": date,
            "base_label": base_rows[date]["regime_label"],
            "extension_label": extension_rows[date]["regime_label"],
        }
        for date in overlap
        if base_rows[date]["regime_label"] != extension_rows[date]["regime_label"]
    ]
    appended = [extension_rows[date] for date in sorted(extension_rows) if date > base_end]
    if not appended:
        raise ValueError("extension 沒有比 base 更新的日期")
    rows = [base_rows[date] for date in sorted(base_rows)] + appended
    labels = Counter(str(row["regime_label"]) for row in rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "append_only": True,
            "overlap_uses_base": True,
            "historical_relabel_allowed": False,
            "research_only": True,
            "changes_ranking": False,
        },
        "summary": {
            "trade_days": len(rows),
            "start_date": rows[0]["trade_date"],
            "end_date": rows[-1]["trade_date"],
            "base_days": len(base_rows),
            "appended_days": len(appended),
            "overlap_days": len(overlap),
            "overlap_label_drift_days": len(drift),
            "overlap_label_drift_rate": round(len(drift) / len(overlap), 6) if overlap else 0.0,
            "regime_counts": dict(labels),
        },
        "drift_receipt": drift,
        "rows": rows,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    return "\n".join(
        [
            "# Append-only Market Regime History",
            "",
            f"- trade_days: {summary['trade_days']}",
            f"- base_days: {summary['base_days']}",
            f"- appended_days: {summary['appended_days']}",
            f"- overlap_label_drift_days: {summary['overlap_label_drift_days']}",
            f"- overlap_label_drift_rate: {summary['overlap_label_drift_rate']:.2%}",
            "- overlap policy: preserve base labels",
            "",
        ]
    )


def main() -> int:
    args = parse_args()
    base_path = resolve_path(args.base)
    extension_path = resolve_path(args.extension)
    output = resolve_path(args.output)
    payload = merge_histories(read_payload(base_path), read_payload(extension_path))
    payload["inputs"] = {"base": repo_path(base_path), "extension": repo_path(extension_path)}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK",
                "output": repo_path(output),
                "trade_days": payload["summary"]["trade_days"],
                "appended_days": payload["summary"]["appended_days"],
                "drift_days_preserved": payload["summary"]["overlap_label_drift_days"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
