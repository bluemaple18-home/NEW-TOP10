#!/usr/bin/env python3
"""建立 production/candidate 共識優先的推播 Top10 ranking。"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "consensus-publish-top10.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="建立共識優先的推播 Top10 ranking")
    parser.add_argument("--date", default=None)
    parser.add_argument("--production-ranking", required=True)
    parser.add_argument("--candidate-ranking", required=True)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--output-dir", default="artifacts/publish_rankings/consensus")
    parser.add_argument("--comparison-output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def date_from_path(path: Path) -> str:
    match = re.search(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking 檔名無法解析日期：{path}")
    return match.group(1)


def normalize_stock_id(value: Any) -> str:
    text = str(value or "").strip().replace(".0", "")
    return text.zfill(4)


def read_ranking(path: Path, top_n: int) -> tuple[list[str], list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = list(reader.fieldnames or [])
        rows: list[dict[str, Any]] = []
        for rank, row in enumerate(reader, start=1):
            if rank > top_n:
                break
            normalized = dict(row)
            normalized["stock_id"] = normalize_stock_id(normalized.get("stock_id"))
            normalized["_source_rank"] = rank
            rows.append(normalized)
    return fieldnames, rows


def row_key(row: dict[str, Any]) -> str:
    return normalize_stock_id(row.get("stock_id"))


def numeric(value: Any, default: float = 0.0) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def public_row(
    row: dict[str, Any],
    *,
    publish_rank: int,
    publish_source: str,
    production_rank: int | None,
    candidate_rank: int | None,
    candidate_row: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = {key: value for key, value in row.items() if not key.startswith("_")}
    result["publish_rank"] = publish_rank
    result["publish_source"] = publish_source
    result["publish_row_source"] = "production" if publish_source in {"overlap", "production_fallback"} else "candidate"
    result["production_rank"] = production_rank or ""
    result["candidate_rank"] = candidate_rank or ""
    result["consensus_rank_sum"] = (production_rank or 99) + (candidate_rank or 99)
    if candidate_row is not None and publish_source == "overlap":
        result["candidate_risk_adjusted_score"] = candidate_row.get("risk_adjusted_score", "")
        result["candidate_suggested_weight"] = candidate_row.get("suggested_weight", "")
        result["candidate_reasons"] = candidate_row.get("reasons", "")
    return result


def compact_row(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "stock_id": row.get("stock_id"),
        "stock_name": row.get("stock_name"),
        "publish_rank": row.get("publish_rank"),
        "publish_source": row.get("publish_source"),
        "production_rank": row.get("production_rank"),
        "candidate_rank": row.get("candidate_rank"),
        "risk_adjusted_score": numeric(row.get("risk_adjusted_score")),
        "model_prob": numeric(row.get("model_prob")),
        "market_regime": row.get("market_regime"),
    }


def build_publish_rows(
    production_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    top_n: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    production_by_id = {row_key(row): row for row in production_rows}
    candidate_by_id = {row_key(row): row for row in candidate_rows}
    overlap_ids = set(production_by_id) & set(candidate_by_id)
    candidate_only_ids = [row_key(row) for row in candidate_rows if row_key(row) not in overlap_ids]
    production_only_ids = [row_key(row) for row in production_rows if row_key(row) not in overlap_ids]

    ordered_overlap = sorted(
        overlap_ids,
        key=lambda stock_id: (
            int(production_by_id[stock_id]["_source_rank"]) + int(candidate_by_id[stock_id]["_source_rank"]),
            int(candidate_by_id[stock_id]["_source_rank"]),
            int(production_by_id[stock_id]["_source_rank"]),
        ),
    )
    selected: list[tuple[str, str]] = [("overlap", stock_id) for stock_id in ordered_overlap]
    selected.extend(("candidate_only", stock_id) for stock_id in candidate_only_ids)
    if len(selected) < top_n:
        selected.extend(("production_fallback", stock_id) for stock_id in production_only_ids)
    selected = selected[:top_n]

    publish_rows: list[dict[str, Any]] = []
    for publish_rank, (source, stock_id) in enumerate(selected, start=1):
        if source == "overlap":
            base = production_by_id[stock_id]
            candidate_row = candidate_by_id[stock_id]
        elif source == "candidate_only":
            base = candidate_by_id[stock_id]
            candidate_row = None
        else:
            base = production_by_id[stock_id]
            candidate_row = None
        publish_rows.append(
            public_row(
                base,
                publish_rank=publish_rank,
                publish_source=source,
                production_rank=int(production_by_id[stock_id]["_source_rank"]) if stock_id in production_by_id else None,
                candidate_rank=int(candidate_by_id[stock_id]["_source_rank"]) if stock_id in candidate_by_id else None,
                candidate_row=candidate_row,
            )
        )

    comparison = {
        "overlap_count": len(overlap_ids),
        "candidate_only_count": len(candidate_only_ids),
        "production_only_count": len(production_only_ids),
        "publish_source_counts": {
            source: sum(1 for row in publish_rows if row["publish_source"] == source)
            for source in ("overlap", "candidate_only", "production_fallback")
        },
        "overlap_stock_ids": ordered_overlap,
        "candidate_only_stock_ids": candidate_only_ids,
        "production_only_stock_ids": production_only_ids,
    }
    return publish_rows, comparison


def merged_fieldnames(production_fields: list[str], candidate_fields: list[str]) -> list[str]:
    result: list[str] = []
    for field in [*candidate_fields, *production_fields]:
        if field and field not in result:
            result.append(field)
    for field in [
        "publish_rank",
        "publish_source",
        "publish_row_source",
        "production_rank",
        "candidate_rank",
        "consensus_rank_sum",
        "candidate_risk_adjusted_score",
        "candidate_suggested_weight",
        "candidate_reasons",
    ]:
        if field not in result:
            result.append(field)
    return result


def write_ranking(path: Path, fieldnames: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    production_path = resolve_path(args.production_ranking)
    candidate_path = resolve_path(args.candidate_ranking)
    if production_path is None or not production_path.exists():
        raise FileNotFoundError(f"找不到 production ranking：{args.production_ranking}")
    if candidate_path is None or not candidate_path.exists():
        raise FileNotFoundError(f"找不到 candidate ranking：{args.candidate_ranking}")
    ranking_date = args.date or date_from_path(candidate_path)
    if date_from_path(production_path) != ranking_date or date_from_path(candidate_path) != ranking_date:
        raise ValueError("production/candidate ranking date mismatch")
    production_fields, production_rows = read_ranking(production_path, args.top_n)
    candidate_fields, candidate_rows = read_ranking(candidate_path, args.top_n)
    publish_rows, comparison = build_publish_rows(production_rows, candidate_rows, args.top_n)

    output_dir = resolve_path(args.output_dir)
    if output_dir is None:
        raise RuntimeError("output dir 路徑解析失敗")
    ranking_output = output_dir / f"ranking_{ranking_date}.csv"
    comparison_output = resolve_path(args.comparison_output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"consensus_publish_top10_{ranking_date}.json"
    write_ranking(ranking_output, merged_fieldnames(production_fields, candidate_fields), publish_rows)

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": ranking_date,
        "status": "OK" if len(publish_rows) == min(args.top_n, max(len(production_rows), len(candidate_rows))) else "FAILED",
        "contract": {
            "research_to_publish_adapter": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "clawd_send_attempted": False,
            "promotion_ready": False,
        },
        "inputs": {
            "production_ranking": repo_path(production_path),
            "candidate_ranking": repo_path(candidate_path),
            "top_n": args.top_n,
        },
        "outputs": {
            "publish_ranking": repo_path(ranking_output),
            "comparison": repo_path(comparison_output),
        },
        "policy": {
            "name": "consensus_first_candidate_fill",
            "steps": [
                "production/candidate overlap 先依合計排名排序；overlap row body 使用 production 欄位",
                "candidate-only 用 candidate row body 補滿剩餘名額",
                "production-only 只在 publish list 少於 top_n 時作 fallback",
            ],
        },
        "comparison": comparison,
        "publish_top10": [compact_row(row) for row in publish_rows],
    }
    comparison_output.parent.mkdir(parents=True, exist_ok=True)
    comparison_output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return payload


def main() -> int:
    args = parse_args()
    payload = build_payload(args)
    print(
        json.dumps(
            {
                "status": payload["status"],
                "publish_ranking": payload["outputs"]["publish_ranking"],
                "comparison": payload["outputs"]["comparison"],
                "overlap_count": payload["comparison"]["overlap_count"],
            },
            ensure_ascii=False,
        )
    )
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
