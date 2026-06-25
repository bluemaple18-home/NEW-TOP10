#!/usr/bin/env python3
"""External review API provider adapter.

正式模式會呼叫 OpenAI / Gemini 官方 API；測試模式只產生合法 raw reviewer JSON，
用來驗證 host runner、normalizer、summary 與 harness event 是否已打通。
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "external-review.v1"
PROVIDERS = ("chatgpt", "gemini")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run external review through official provider APIs.")
    parser.add_argument("--provider", required=True, choices=PROVIDERS)
    parser.add_argument("--date", required=True)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--artifacts-dir", default=Path("artifacts/external_review"), type=Path)
    parser.add_argument("--dry-run", action="store_true", help="不呼叫外部 API，產生可驗證 reviewer fixture")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    packet_path = resolve_project_path(args.packet)
    artifacts_dir = resolve_project_path(args.artifacts_dir)
    packet = json.loads(packet_path.read_text(encoding="utf-8"))
    review_dir = artifacts_dir / args.date
    review_dir.mkdir(parents=True, exist_ok=True)

    raw_path = review_dir / f"{args.provider}_raw_{args.date}.txt"
    status_path = review_dir / f"{args.provider}_collect_status_{args.date}.json"
    full_response_path = review_dir / f"{args.provider}_api_response_{args.date}.json"

    started_at = datetime.now(timezone.utc).isoformat()
    status: dict[str, Any] = {
        "schema_version": "external-review-api-provider-status.v1",
        "generated_at": started_at,
        "provider": args.provider,
        "review_date": args.date,
        "provider_mode": "api",
        "dry_run": bool(args.dry_run),
        "packet_path": repo_relative(packet_path),
        "raw_path": repo_relative(raw_path),
        "full_response_path": repo_relative(full_response_path),
        "status": "RUNNING",
        "errors": [],
    }
    write_json(status_path, status)

    try:
        if args.dry_run:
            output_text = json.dumps(build_dry_run_review(args.provider, args.date, packet), ensure_ascii=False, indent=2)
            full_response = {"dry_run": True, "output_text": output_text}
        elif args.provider == "chatgpt":
            output_text, full_response = call_openai(args.date, packet)
        else:
            output_text, full_response = call_gemini(args.date, packet)

        raw_path.write_text(output_text.strip() + "\n", encoding="utf-8")
        write_json(full_response_path, full_response)
        status.update(
            {
                "status": "OK",
                "completed_at": datetime.now(timezone.utc).isoformat(),
                "output_chars": len(output_text),
            }
        )
        write_json(status_path, status)
        print(f"EXTERNAL_REVIEW_API_PROVIDER_OK provider={args.provider} raw={raw_path} status={status_path}")
        return 0
    except Exception as exc:
        status["status"] = "FAILED"
        status["completed_at"] = datetime.now(timezone.utc).isoformat()
        status["errors"].append(str(exc))
        write_json(status_path, status)
        print(f"EXTERNAL_REVIEW_API_PROVIDER_FAILED provider={args.provider} status={status_path}", file=sys.stderr)
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


def call_openai(review_date: str, packet: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    api_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY missing")
    model = os.environ.get("TOP10_OPENAI_REVIEW_MODEL", "gpt-4.1-mini").strip()
    payload = {
        "model": model,
        "instructions": reviewer_instructions("chatgpt", review_date),
        "input": review_input(packet),
        "text": {
            "format": {
                "type": "json_schema",
                "name": "external_review_v1",
                "schema": external_review_json_schema(),
                "strict": True,
            }
        },
    }
    response = post_json(
        "https://api.openai.com/v1/responses",
        payload,
        headers={"Authorization": f"Bearer {api_key}"},
    )
    return extract_openai_output_text(response), response


def call_gemini(review_date: str, packet: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    api_key = os.environ.get("GEMINI_API_KEY", "").strip() or os.environ.get("GOOGLE_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY or GOOGLE_API_KEY missing")
    model = os.environ.get("TOP10_GEMINI_REVIEW_MODEL", "gemini-3.5-flash").strip()
    payload = {
        "model": model,
        "input": reviewer_instructions("gemini", review_date) + "\n\n" + review_input(packet),
        "response_format": {
            "type": "text",
            "mime_type": "application/json",
            "schema": external_review_json_schema(),
        },
    }
    response = post_json(
        "https://generativelanguage.googleapis.com/v1beta/interactions",
        payload,
        headers={"x-goog-api-key": api_key},
    )
    return extract_gemini_output_text(response), response


def post_json(url: str, payload: dict[str, Any], *, headers: dict[str, str]) -> dict[str, Any]:
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=int(os.environ.get("TOP10_EXTERNAL_REVIEW_API_TIMEOUT", "90"))) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"api_http_error status={exc.code} body={detail[:1200]}") from exc


def extract_openai_output_text(response: dict[str, Any]) -> str:
    texts: list[str] = []
    for item in list_value(response.get("output")):
        if not isinstance(item, dict):
            continue
        for content in list_value(item.get("content")):
            if isinstance(content, dict) and isinstance(content.get("text"), str):
                texts.append(content["text"])
    output_text = "\n".join(texts).strip()
    if not output_text and isinstance(response.get("output_text"), str):
        output_text = response["output_text"].strip()
    if not output_text:
        raise RuntimeError("openai_output_text_missing")
    return output_text


def extract_gemini_output_text(response: dict[str, Any]) -> str:
    for key in ("output_text", "text"):
        if isinstance(response.get(key), str) and response[key].strip():
            return response[key].strip()
    candidates = list_value(response.get("candidates"))
    parts: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        content = candidate.get("content")
        for part in list_value(object_value(content).get("parts")):
            if isinstance(part, dict) and isinstance(part.get("text"), str):
                parts.append(part["text"])
    output_text = "\n".join(parts).strip()
    if not output_text:
        raise RuntimeError("gemini_output_text_missing")
    return output_text


def reviewer_instructions(provider: str, review_date: str) -> str:
    return (
        "你是一位專業台股操盤手。你不知道也不需要知道系統演算法。"
        "請只根據推薦名單、公開市場資訊、盤面邏輯、族群資金流與風險控管角度做事後檢討。"
        "禁止要求或推測內部演算法、權重、feature engineering、訓練資料結構、模型程式碼或任何未公開策略參數。"
        f"請輸出單一 JSON object，必須符合 external-review.v1；provider={provider}，review_date={review_date}，market=TW。"
    )


def review_input(packet: dict[str, Any]) -> str:
    sendable_packet = {
        "packet_date": packet.get("packet_date"),
        "market": packet.get("market"),
        "market_overview": packet.get("market_overview"),
        "outcome_status": packet.get("outcome_status"),
        "recommendations": packet.get("recommendations"),
    }
    return "以下是已通過本地安全驗證的 review_packet 摘要：\n" + json.dumps(
        sendable_packet,
        ensure_ascii=False,
        separators=(",", ":"),
    )


def build_dry_run_review(provider: str, review_date: str, packet: dict[str, Any]) -> dict[str, Any]:
    recommendations = list_value(packet.get("recommendations"))
    symbols = [string_value(item.get("stock_id")) for item in recommendations if isinstance(item, dict)]
    symbols = [symbol for symbol in symbols if symbol][:10]
    first_symbol = symbols[0] if symbols else ""
    provider_bias = "API dry-run fixture" if provider == "chatgpt" else "Gemini API dry-run fixture"
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "review_date": review_date,
        "market": "TW",
        "overall": {
            "score": 78 if provider == "chatgpt" else 74,
            "verdict": "good",
            "confidence": 0.72,
            "summary": f"{provider_bias}：推薦名單可檢討，未接觸內部演算法。",
        },
        "quality": {
            "mainstream_alignment": 4,
            "relative_strength": 4,
            "risk_control": 3,
            "timing_quality": 3,
            "theme_fit": 4,
        },
        "observations": [
            {
                "type": "strength",
                "title": "族群與相對強度需要持續追蹤",
                "evidence": "根據外送 packet 的推薦名單與公開摘要，候選標的仍需用隔日量價確認。",
                "affected_symbols": symbols[:3],
                "severity": "medium",
            }
        ],
        "misses": [
            {
                "symbol": first_symbol,
                "name": "",
                "issue": "dry-run reviewer 保留一個待人工核對的風險點。",
                "likely_cause": "unknown",
                "evidence": "此為 API adapter 打通測試，不作為投資判斷。",
            }
        ],
        "themes": {
            "strong": ["相對強勢股"],
            "weak": ["追價風險"],
            "watch": ["隔日量價確認"],
        },
        "tomorrow_watch": {
            "continue": symbols[:5],
            "avoid_chasing": symbols[:1],
            "watch_for_reversal": symbols[:1],
            "theme_candidates": ["相對強勢股"],
        },
        "research_hypotheses": [
            {
                "hypothesis": "檢驗外部 reviewer 標記追價風險後的隔日回撤率",
                "why_it_matters": "可把 reviewer disagreement 轉成 replay 研究題目，而不是直接改 ranking。",
                "candidate_signal_family": "risk_control",
                "validation_hint": "用 historical replay 比較被標記風險與未標記樣本的隔日最大回撤。",
                "priority": "medium",
            }
        ],
        "safety": {
            "algorithm_requested": False,
            "contains_algorithm_claim": False,
            "needs_human_review": False,
        },
    }


def external_review_json_schema() -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "provider",
            "review_date",
            "market",
            "overall",
            "quality",
            "observations",
            "misses",
            "themes",
            "tomorrow_watch",
            "research_hypotheses",
            "safety",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": SCHEMA_VERSION},
            "provider": {"type": "string", "enum": list(PROVIDERS)},
            "review_date": {"type": "string"},
            "market": {"type": "string", "const": "TW"},
            "overall": {
                "type": "object",
                "additionalProperties": False,
                "required": ["score", "verdict", "confidence", "summary"],
                "properties": {
                    "score": {"type": "integer", "minimum": 0, "maximum": 100},
                    "verdict": {"type": "string", "enum": ["excellent", "good", "mixed", "poor"]},
                    "confidence": {"type": "number", "minimum": 0, "maximum": 1},
                    "summary": {"type": "string"},
                },
            },
            "quality": {
                "type": "object",
                "additionalProperties": False,
                "required": ["mainstream_alignment", "relative_strength", "risk_control", "timing_quality", "theme_fit"],
                "properties": {
                    key: {"type": "integer", "minimum": 0, "maximum": 5}
                    for key in ["mainstream_alignment", "relative_strength", "risk_control", "timing_quality", "theme_fit"]
                },
            },
            "observations": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["type", "title", "evidence", "affected_symbols", "severity"],
                    "properties": {
                        "type": {"type": "string", "enum": ["strength", "weakness", "risk", "missed_opportunity"]},
                        "title": {"type": "string"},
                        "evidence": {"type": "string"},
                        "affected_symbols": {"type": "array", "items": {"type": "string"}},
                        "severity": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                },
            },
            "misses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["symbol", "name", "issue", "likely_cause", "evidence"],
                    "properties": {
                        "symbol": {"type": "string"},
                        "name": {"type": "string"},
                        "issue": {"type": "string"},
                        "likely_cause": {
                            "type": "string",
                            "enum": ["market_drag", "theme_rotation", "overextended", "liquidity_weakness", "news_risk", "unknown"],
                        },
                        "evidence": {"type": "string"},
                    },
                },
            },
            "themes": string_list_object_schema(["strong", "weak", "watch"]),
            "tomorrow_watch": string_list_object_schema(["continue", "avoid_chasing", "watch_for_reversal", "theme_candidates"]),
            "research_hypotheses": {
                "type": "array",
                "items": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["hypothesis", "why_it_matters", "candidate_signal_family", "validation_hint", "priority"],
                    "properties": {
                        "hypothesis": {"type": "string"},
                        "why_it_matters": {"type": "string"},
                        "candidate_signal_family": {
                            "type": "string",
                            "enum": ["theme_momentum", "relative_strength", "risk_control", "liquidity", "timing", "other"],
                        },
                        "validation_hint": {"type": "string"},
                        "priority": {"type": "string", "enum": ["low", "medium", "high"]},
                    },
                },
            },
            "safety": {
                "type": "object",
                "additionalProperties": False,
                "required": ["algorithm_requested", "contains_algorithm_claim", "needs_human_review"],
                "properties": {
                    "algorithm_requested": {"type": "boolean"},
                    "contains_algorithm_claim": {"type": "boolean"},
                    "needs_human_review": {"type": "boolean"},
                },
            },
        },
    }


def string_list_object_schema(keys: list[str]) -> dict[str, Any]:
    return {
        "type": "object",
        "additionalProperties": False,
        "required": keys,
        "properties": {key: {"type": "array", "items": {"type": "string"}} for key in keys},
    }


def resolve_project_path(path: Path) -> Path:
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def object_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def string_value(value: Any) -> str:
    return str(value).strip() if value is not None else ""


if __name__ == "__main__":
    raise SystemExit(main())
