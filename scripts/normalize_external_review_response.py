#!/usr/bin/env python3
"""嚴格驗證外部研究回覆；缺少可核對證據時整份拒收。"""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from external_review_provider_contract import MIN_RAW_CHARS, has_smoke_marker
from verify_external_review_contract import validate as validate_legacy_contract

SCHEMA_VERSION = "external-review.v1"


class ContractError(ValueError):
    """攜帶明確欄位位置的收件失敗。"""


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="validate raw external review into external-review.v1")
    parser.add_argument("--provider", required=True, choices=["chatgpt", "gemini"])
    parser.add_argument("--date", required=True)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_text = args.raw.read_text(encoding="utf-8")
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    result = normalize_payload(
        provider=args.provider,
        review_date=args.date,
        raw_payload=parse_raw_payload(raw_text),
        raw_text=raw_text,
        packet=packet,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    if result["status"] == "REJECTED":
        print(f"EXTERNAL_REVIEW_REJECTED provider={args.provider} reason={result['reason']}")
        return 1
    print(f"EXTERNAL_REVIEW_NORMALIZE_OK json={args.out}")
    return 0


def parse_raw_payload(raw_text: str) -> dict[str, Any] | None:
    """只接受單一 JSON 物件或單一完整 JSON code block。"""
    text = raw_text.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) < 3 or lines[0].strip().lower() not in {"```", "```json"} or lines[-1].strip() != "```":
            return None
        text = "\n".join(lines[1:-1]).strip()
    try:
        value = json.loads(text)
    except json.JSONDecodeError:
        return None
    return value if isinstance(value, dict) else None


def normalize_payload(
    provider: str,
    review_date: str,
    raw_payload: dict[str, Any] | None,
    raw_text: str,
    packet: dict[str, Any],
) -> dict[str, Any]:
    try:
        validate_raw_review(provider, review_date, raw_payload, raw_text, packet)
    except ContractError as exc:
        return {
            "provider": provider,
            "status": "REJECTED",
            "reason": str(exc),
            "safety": {"needs_human_review": True},
        }
    # 驗證完成後只保留 reviewer 實際寫出的欄位，不補摘要、分數或研究假設。
    result = dict(raw_payload)
    result["status"] = "ACCEPTED"
    return result


def validate_raw_review(
    provider: str,
    review_date: str,
    raw_payload: dict[str, Any] | None,
    raw_text: str,
    packet: dict[str, Any],
) -> None:
    text = raw_text.strip()
    if len(text) < MIN_RAW_CHARS:
        raise ContractError(f"raw: too short ({len(text)}<{MIN_RAW_CHARS})")
    if has_smoke_marker(text):
        raise ContractError("raw: smoke marker detected")
    if raw_payload is None:
        raise ContractError("raw: expected one complete JSON object")
    if raw_payload.get("schema_version") != SCHEMA_VERSION:
        raise ContractError("schema_version: must be external-review.v1")
    if raw_payload.get("provider") != provider:
        raise ContractError("provider: does not match requested provider")
    if raw_payload.get("review_date") != review_date:
        raise ContractError("review_date: does not match requested date")
    if ("status" in raw_payload and raw_payload["status"] != "ACCEPTED") or "error" in raw_payload:
        raise ContractError("status: provider error response")
    reject_nonfinite(raw_payload)
    recommendations = packet_recommendations(packet, review_date)
    validate_grounding(raw_payload.get("grounding_proof"), recommendations)
    validate_commentary(raw_payload.get("per_stock_commentary"), recommendations)
    validate_opinion(raw_payload.get("structured_opinion"), recommendations)
    safety = raw_payload.get("safety")
    if isinstance(safety, dict) and safety.get("manual_review_required") and safety.get("needs_human_review") is not True:
        raise ContractError("safety.manual_review_required: cannot clear human review")
    try:
        errors = validate_legacy_contract(raw_payload)
    except (TypeError, ValueError, KeyError) as exc:
        raise ContractError("existing_contract: malformed field type") from exc
    if errors:
        raise ContractError(f"existing_contract.{errors[0]}")


def reject_nonfinite(value: Any, path: str = "raw") -> None:
    """Python JSON parser 可讀取 NaN／Infinity；拒收所有非有限數字。"""
    if isinstance(value, float) and not math.isfinite(value):
        raise ContractError(f"{path}: non-finite number")
    if isinstance(value, dict):
        for key, item in value.items():
            reject_nonfinite(item, f"{path}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            reject_nonfinite(item, f"{path}[{index}]")


def packet_recommendations(packet: dict[str, Any], review_date: str) -> dict[str, dict[str, Any]]:
    if not isinstance(packet, dict) or packet.get("packet_date") != review_date:
        raise ContractError("packet.packet_date: does not match requested date")
    rows = packet.get("recommendations")
    if not isinstance(rows, list) or len(rows) < 10:
        raise ContractError("packet.recommendations: expected at least 10 entries")
    result: dict[str, dict[str, Any]] = {}
    ranks: set[int] = set()
    for index, row in enumerate(rows[:10]):
        if not isinstance(row, dict):
            raise ContractError(f"packet.recommendations[{index}]: must be object")
        stock_id, rank = row.get("stock_id"), row.get("rank")
        if not isinstance(stock_id, str) or not stock_id or stock_id in result:
            raise ContractError(f"packet.recommendations[{index}].stock_id: invalid or duplicate")
        if type(rank) is not int or rank in ranks or not 1 <= rank <= 10:
            raise ContractError(f"packet.recommendations[{index}].rank: invalid or duplicate")
        result[stock_id] = row
        ranks.add(rank)
    return result


def require_stock_id(value: Any, rows: dict[str, dict[str, Any]], path: str) -> str:
    if not isinstance(value, str) or value not in rows:
        raise ContractError(f"{path}: stock_id not in input ranking")
    return value


def validate_grounding(value: Any, rows: dict[str, dict[str, Any]]) -> None:
    if not isinstance(value, dict):
        raise ContractError("grounding_proof: must be object")
    ids = value.get("cited_stock_ids")
    if not isinstance(ids, list) or len(ids) < 3 or len(set(map(str, ids))) != len(ids):
        raise ContractError("grounding_proof.cited_stock_ids: expected at least 3 unique stock IDs")
    for index, stock_id in enumerate(ids):
        require_stock_id(stock_id, rows, f"grounding_proof.cited_stock_ids[{index}]")

    ranks = value.get("cited_rank")
    if not isinstance(ranks, list) or len(ranks) < 2:
        raise ContractError("grounding_proof.cited_rank: expected at least 2 entries")
    ranked_ids: set[str] = set()
    for index, item in enumerate(ranks):
        if not isinstance(item, dict):
            raise ContractError(f"grounding_proof.cited_rank[{index}]: must be object")
        stock_id = require_stock_id(item.get("stock_id"), rows, f"grounding_proof.cited_rank[{index}].stock_id")
        if stock_id in ranked_ids or type(item.get("rank")) is not int or item["rank"] != rows[stock_id]["rank"]:
            raise ContractError(f"grounding_proof.cited_rank[{index}].rank: duplicate or input mismatch")
        ranked_ids.add(stock_id)

    has_close = "cited_close" in value
    has_industry = "cited_industry" in value
    if not (has_close or has_industry):
        raise ContractError("grounding_proof: cited_close or cited_industry required")
    if has_close:
        item = value["cited_close"]
        if not isinstance(item, dict):
            raise ContractError("grounding_proof.cited_close: must be object")
        stock_id = require_stock_id(item.get("stock_id"), rows, "grounding_proof.cited_close.stock_id")
        close, actual = item.get("close"), rows[stock_id].get("close")
        if not finite_number(close) or not finite_number(actual) or abs(close - actual) >= 0.01:
            raise ContractError("grounding_proof.cited_close.close: input mismatch")
    if has_industry:
        item = value["cited_industry"]
        if not isinstance(item, dict):
            raise ContractError("grounding_proof.cited_industry: must be object")
        stock_id = require_stock_id(item.get("stock_id"), rows, "grounding_proof.cited_industry.stock_id")
        reference = rows[stock_id].get("reference")
        actual = reference.get("industry_name") if isinstance(reference, dict) else None
        if not isinstance(item.get("industry"), str) or not actual or item["industry"] != actual:
            raise ContractError("grounding_proof.cited_industry.industry: input mismatch")


def finite_number(value: Any) -> bool:
    return type(value) in {int, float} and math.isfinite(value)


def validate_commentary(value: Any, rows: dict[str, dict[str, Any]]) -> None:
    if not isinstance(value, dict):
        raise ContractError("per_stock_commentary: must be object")
    if len(value) < 7:
        raise ContractError("per_stock_commentary: expected at least 7 of top 10")
    for stock_id, entry in value.items():
        require_stock_id(stock_id, rows, f"per_stock_commentary.{stock_id}")
        if not isinstance(entry, dict):
            raise ContractError(f"per_stock_commentary.{stock_id}: must be object")
        assessment = entry.get("assessment")
        if not isinstance(assessment, str) or len(assessment.strip()) < 30:
            raise ContractError(f"per_stock_commentary.{stock_id}.assessment: expected at least 30 characters")
        citation = entry.get("cites_input_attr")
        row = rows[stock_id]
        reference = row.get("reference")
        industry = reference.get("industry_name") if isinstance(reference, dict) else None
        allowed = {str(row["rank"]), f"rank={row['rank']}"}
        if finite_number(row.get("close")):
            allowed.update({str(row["close"]), f"close={row['close']}"})
        if isinstance(industry, str) and industry:
            allowed.update({industry, f"industry={industry}"})
        if not isinstance(citation, str) or citation.strip() not in allowed:
            raise ContractError(f"per_stock_commentary.{stock_id}.cites_input_attr: input mismatch")


def validate_opinion(value: Any, rows: dict[str, dict[str, Any]]) -> None:
    if not isinstance(value, dict):
        raise ContractError("structured_opinion: must be object")
    if type(value.get("agreement_with_top3")) is not bool:
        raise ContractError("structured_opinion.agreement_with_top3: must be boolean")
    for key, enum_field, allowed in (
        ("concerns", "severity", {"low", "med", "high"}),
        ("divergent_picks", "direction", {"pass", "caution", "strong"}),
    ):
        items = value.get(key)
        if not isinstance(items, list):
            raise ContractError(f"structured_opinion.{key}: must be list")
        for index, item in enumerate(items):
            path = f"structured_opinion.{key}[{index}]"
            if not isinstance(item, dict):
                raise ContractError(f"{path}: must be object")
            require_stock_id(item.get("stock_id"), rows, f"{path}.stock_id")
            if key == "concerns" and (not isinstance(item.get("concern_type"), str) or not item["concern_type"].strip()):
                raise ContractError(f"{path}.concern_type: must be nonempty string")
            if not isinstance(item.get(enum_field), str) or item[enum_field] not in allowed:
                raise ContractError(f"{path}.{enum_field}: invalid enum")


if __name__ == "__main__":
    raise SystemExit(main())
