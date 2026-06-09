#!/usr/bin/env python3
"""把外部 reviewer 的自由回覆正規化成 external-review.v1。"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "external-review.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="normalize raw external review into external-review.v1")
    parser.add_argument("--provider", default="chatgpt", choices=["chatgpt", "gemini"])
    parser.add_argument("--date", required=True)
    parser.add_argument("--raw", required=True, type=Path)
    parser.add_argument("--packet", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    raw_text = args.raw.read_text(encoding="utf-8")
    packet = json.loads(args.packet.read_text(encoding="utf-8"))
    raw_payload = parse_raw_payload(raw_text)
    normalized = normalize_payload(
        provider=args.provider,
        review_date=args.date,
        raw_payload=raw_payload,
        raw_text=raw_text,
        packet=packet,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"EXTERNAL_REVIEW_NORMALIZE_OK json={args.out}")
    return 0


def parse_raw_payload(raw_text: str) -> dict[str, Any] | None:
    text = raw_text.strip()
    if not text:
        return None
    try:
        payload = json.loads(text)
        return payload if isinstance(payload, dict) else None
    except json.JSONDecodeError:
        pass
    candidate = extract_first_json_object(text)
    if not candidate:
        return None
    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    depth = 0
    in_string = False
    escape = False
    for index in range(start, len(text)):
        char = text[index]
        if in_string:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                in_string = False
            continue
        if char == '"':
            in_string = True
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[start : index + 1]
    return None


def normalize_payload(
    provider: str,
    review_date: str,
    raw_payload: dict[str, Any] | None,
    raw_text: str,
    packet: dict[str, Any],
) -> dict[str, Any]:
    payload = raw_payload or {}
    if payload.get("schema_version") == SCHEMA_VERSION and isinstance(payload.get("overall"), dict):
        return normalize_contract_payload(payload, provider, review_date)
    if isinstance(payload.get("trading_review_summary"), dict):
        return normalize_gemini_payload(provider, review_date, payload)
    if isinstance(payload.get("trading_review"), dict):
        return normalize_gemini_trading_review_payload(provider, review_date, payload)
    if raw_payload is None:
        return normalize_plaintext_payload(provider, review_date, raw_text, packet)

    overall_review = object_value(payload.get("overall_review"))
    recommendation_quality = object_value(payload.get("recommendation_quality"))
    sector_flow = object_value(payload.get("sector_flow_analysis"))
    worth_tracking = object_value(payload.get("worth_tracking"))
    next_notes = object_value(payload.get("next_session_notes"))
    market_context = object_value(payload.get("market_context_review"))

    summary = first_non_empty(
        overall_review.get("summary"),
        payload.get("summary"),
        raw_text[:500],
        "外部 reviewer 回覆不足，需人工檢查 raw response。",
    )
    quality_score = score_0_to_5(recommendation_quality.get("overall_score"))
    confidence = float_value(payload.get("confidence"), 0.35 if raw_payload is None else 0.65)

    observations = build_observations(payload, recommendation_quality, market_context, sector_flow)
    misses = build_misses(payload)
    themes = {
        "strong": string_list(first_non_empty(sector_flow.get("primary_flows"), worth_tracking.get("sectors"), [])),
        "weak": string_list(sector_flow.get("secondary_flows")),
        "watch": string_list(worth_tracking.get("sectors")),
    }
    tomorrow_watch = {
        "continue": string_list(worth_tracking.get("stocks")),
        "avoid_chasing": stocks_from_high_risk(payload),
        "watch_for_reversal": stocks_from_misjudgments(payload),
        "theme_candidates": themes["strong"],
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "review_date": review_date,
        "market": "TW",
        "overall": {
            "score": score_0_to_100(recommendation_quality.get("overall_score")),
            "verdict": verdict_from_score(recommendation_quality.get("overall_score")),
            "confidence": clamp(confidence, 0.0, 1.0),
            "summary": string_value(summary),
        },
        "quality": {
            "mainstream_alignment": quality_score,
            "relative_strength": quality_score,
            "risk_control": score_from_risks(payload),
            "timing_quality": score_from_timing(payload),
            "theme_fit": quality_score,
        },
        "observations": observations,
        "misses": misses,
        "themes": themes,
        "tomorrow_watch": tomorrow_watch,
        "research_hypotheses": build_hypotheses(payload, packet),
        "safety": {
            "algorithm_requested": False,
            "contains_algorithm_claim": False,
            "needs_human_review": raw_payload is None,
        },
    }


def normalize_plaintext_payload(provider: str, review_date: str, raw_text: str, packet: dict[str, Any]) -> dict[str, Any]:
    """把自由文字 reviewer 回覆轉成最小可合併的 contract payload。"""
    text = raw_text.strip()
    summary = first_meaningful_line(text) or "外部 reviewer 以自由文字回覆，需保留 raw response 供人工複核。"
    ids = unique_stock_ids(stock_ids_from_text(text))
    observations = plaintext_observations(text)
    misses = plaintext_misses(text)
    hypotheses = plaintext_hypotheses(text, packet)

    strong = []
    if "AI" in text or "人工智慧" in text:
        strong.append("AI相關")
    if "電子" in text or "零組件" in text:
        strong.append("電子零組件")
    if "高力" in text or "健策" in text:
        strong.append("高價強勢股")
    if "面板" in text:
        strong.append("面板")
    weak = ["大跌爆量誤判"] if "跌停" in text or "大跌" in text else []

    avoid = unique_stock_ids(stock_ids_from_text(" ".join(item["evidence"] for item in misses + observations if item.get("severity") == "high")))
    continue_ids = unique_stock_ids([stock_id for stock_id in ids if stock_id not in avoid])[:8]

    return {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "review_date": review_date,
        "market": "TW",
        "overall": {
            "score": plaintext_score(text),
            "verdict": verdict_from_score(plaintext_score(text)),
            "confidence": 0.55,
            "summary": summary[:500],
        },
        "quality": {
            "mainstream_alignment": 4 if "主流" in text or "熱門族群" in text else 3,
            "relative_strength": 4 if "強勢" in text or "動能" in text else 3,
            "risk_control": 2 if "跌停" in text or "追高" in text else 3,
            "timing_quality": 2 if "跌停" in text or "追高" in text else 3,
            "theme_fit": 4 if strong else 3,
        },
        "observations": observations,
        "misses": misses,
        "themes": {
            "strong": unique_stock_ids([]) + unique_strings(strong),
            "weak": weak,
            "watch": unique_strings(strong + weak),
        },
        "tomorrow_watch": {
            "continue": continue_ids,
            "avoid_chasing": avoid,
            "watch_for_reversal": avoid,
            "theme_candidates": unique_strings(strong),
        },
        "research_hypotheses": hypotheses,
        "safety": {
            "algorithm_requested": False,
            "contains_algorithm_claim": False,
            "needs_human_review": False,
        },
    }


def normalize_contract_payload(payload: dict[str, Any], provider: str, review_date: str) -> dict[str, Any]:
    normalized = json.loads(json.dumps(payload, ensure_ascii=False))
    normalized["schema_version"] = SCHEMA_VERSION
    normalized["provider"] = provider
    normalized["review_date"] = review_date
    normalized["market"] = "TW"
    safety = object_value(normalized.get("safety"))
    safety["algorithm_requested"] = bool(safety.get("algorithm_requested", False))
    safety["contains_algorithm_claim"] = bool(safety.get("contains_algorithm_claim", False))
    safety["needs_human_review"] = bool(safety.get("needs_human_review", False))
    normalized["safety"] = safety
    return normalized


def normalize_gemini_payload(provider: str, review_date: str, payload: dict[str, Any]) -> dict[str, Any]:
    summary_root = object_value(payload.get("trading_review_summary"))
    overall_eval = object_value(summary_root.get("overall_evaluation"))
    stock_quality = object_value(payload.get("stock_selection_quality"))
    sector_flow = object_value(payload.get("market_logic_and_sector_flow"))
    misjudgments = object_value(payload.get("potential_misjudgments"))
    next_points = object_value(payload.get("next_session_observation_points"))
    hypotheses_raw = object_value(payload.get("backtestable_hypotheses"))
    limitations = object_value(payload.get("data_limitations_and_manual_checks"))

    score = score_0_to_100(overall_eval.get("score_out_of_100"))
    quality_score = score_0_to_5(score)
    all_text = json.dumps(payload, ensure_ascii=False)

    observations: list[dict[str, Any]] = []
    for item in string_list(stock_quality.get("pros"))[:4]:
        observations.append(observation("strength", item, item, stock_ids_from_text(item), "medium"))
    for item in string_list(stock_quality.get("cons_and_risks"))[:4]:
        observations.append(observation("risk", item, item, stock_ids_from_text(item), "high" if "追高" in item else "medium"))

    strong_sectors = object_value(sector_flow.get("strong_sectors"))
    weak_sectors = object_value(sector_flow.get("weak_or_neutral_sectors"))
    for name, detail in list(strong_sectors.items())[:4]:
        detail_obj = object_value(detail)
        evidence = first_non_empty(detail_obj.get("logic"), name)
        observations.append(observation("strength", string_value(name), string_value(evidence), stock_ids_from_text(str(detail)), "medium"))
    for name, detail in list(weak_sectors.items())[:4]:
        detail_obj = object_value(detail)
        evidence = first_non_empty(detail_obj.get("logic"), name)
        observations.append(observation("weakness", string_value(name), string_value(evidence), stock_ids_from_text(str(detail)), "medium"))
    for item in string_list(limitations.get("limitations"))[:3]:
        observations.append(observation("risk", item, item, stock_ids_from_text(item), "medium"))

    misses = []
    for key, value in misjudgments.items():
        issue = string_value(key)
        evidence = string_value(value)
        misses.append(
            {
                "symbol": "",
                "name": "",
                "issue": issue or "potential misjudgment",
                "likely_cause": cause_from_text(f"{issue} {evidence}"),
                "evidence": evidence or issue,
            }
        )

    strong_themes = [string_value(key) for key in strong_sectors.keys() if string_value(key)]
    weak_themes = [string_value(key) for key in weak_sectors.keys() if string_value(key)]
    watch_texts = [string_value(value) for _, value in sorted(next_points.items()) if string_value(value)]
    avoid_chasing = unique_stock_ids(
        stock_ids_from_text(" ".join(string_list(stock_quality.get("cons_and_risks")) + watch_texts + list(map(str, misjudgments.values()))))
    )

    hypotheses = []
    for key, value in hypotheses_raw.items():
        item = object_value(value)
        name = string_value(item.get("name")) or string_value(key)
        description = string_value(item.get("description"))
        if not name and not description:
            continue
        hypotheses.append(
            {
                "hypothesis": f"檢驗：{name}",
                "why_it_matters": description or name,
                "candidate_signal_family": signal_family_from_text(f"{name} {description}"),
                "validation_hint": description or "以 historical replay 驗證外部 reviewer 標記條件與報酬/回撤關係。",
                "priority": "high" if "追高" in description or "止損" in description else "medium",
            }
        )
    if not hypotheses:
        hypotheses = build_hypotheses(payload, {})

    return {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "review_date": review_date,
        "market": "TW",
        "overall": {
            "score": score,
            "verdict": verdict_from_score(score),
            "confidence": confidence_from_label(overall_eval.get("confidence_level")),
            "summary": string_value(overall_eval.get("verdict")) or "Gemini reviewer provided no overall summary.",
        },
        "quality": {
            "mainstream_alignment": quality_score,
            "relative_strength": quality_score,
            "risk_control": 2 if "止損距離過寬" in all_text else 3,
            "timing_quality": 2 if "追高" in all_text or "落後" in all_text else 3,
            "theme_fit": quality_score,
        },
        "observations": observations[:12] or build_observations(payload, {}, {}, {}),
        "misses": misses[:8],
        "themes": {
            "strong": strong_themes,
            "weak": weak_themes,
            "watch": strong_themes + weak_themes,
        },
        "tomorrow_watch": {
            "continue": unique_stock_ids(stock_ids_from_text(" ".join(watch_texts))),
            "avoid_chasing": avoid_chasing,
            "watch_for_reversal": avoid_chasing,
            "theme_candidates": strong_themes,
        },
        "research_hypotheses": hypotheses[:8],
        "safety": {
            "algorithm_requested": False,
            "contains_algorithm_claim": False,
            "needs_human_review": False,
        },
    }


def normalize_gemini_trading_review_payload(provider: str, review_date: str, payload: dict[str, Any]) -> dict[str, Any]:
    review = object_value(payload.get("trading_review"))
    overall_eval = object_value(review.get("overall_evaluation"))
    stock_quality = object_value(review.get("stock_quality_analysis"))
    pros_cons = object_value(review.get("pros_and_cons"))
    market_sectors = object_value(review.get("market_sectors"))
    all_text = json.dumps(payload, ensure_ascii=False)

    observations: list[dict[str, Any]] = []
    for item in list_value(stock_quality.get("excellent_picks"))[:5]:
        if not isinstance(item, dict):
            continue
        title = f"{string_value(item.get('stock_id'))} {string_value(item.get('stock_name'))}".strip()
        evidence = string_value(item.get("reason")) or title
        observations.append(observation("strength", title or evidence, evidence, stock_ids_from_text(evidence + title), "medium"))
    for item in string_list(pros_cons.get("primary_advantages"))[:5]:
        observations.append(observation("strength", item, item, stock_ids_from_text(item), "medium"))
    for item in string_list(pros_cons.get("primary_risks"))[:5]:
        observations.append(observation("risk", item, item, stock_ids_from_text(item), "high" if "跌停" in item else "medium"))

    misses: list[dict[str, Any]] = []
    for item in list_value(stock_quality.get("problematic_picks"))[:8]:
        if not isinstance(item, dict):
            continue
        evidence = string_value(item.get("reason"))
        misses.append(
            {
                "symbol": string_value(item.get("stock_id")),
                "name": string_value(item.get("stock_name")),
                "issue": evidence[:90] or "Gemini 標記為問題選股。",
                "likely_cause": cause_from_text(evidence),
                "evidence": evidence or "Gemini 標記為問題選股。",
            }
        )

    leading = string_list(market_sectors.get("leading_sectors"))
    theme_synergy = string_value(market_sectors.get("theme_synergy"))
    watch_texts = string_list(review.get("next_session_watch_points"))
    hypotheses = []
    for item in list_value(review.get("backtest_hypotheses")):
        if not isinstance(item, dict):
            continue
        name = string_value(item.get("hypothesis_name"))
        description = string_value(item.get("description"))
        hypotheses.append(
            {
                "hypothesis": f"檢驗：{name}" if name else description,
                "why_it_matters": description or name,
                "candidate_signal_family": signal_family_from_text(f"{name} {description}"),
                "validation_hint": description or "以 historical replay 驗證外部 reviewer 標記條件。",
                "priority": "high" if "跌停" in description or "停損" in description else "medium",
            }
        )
    if not hypotheses:
        hypotheses = plaintext_hypotheses(all_text, {})

    avoid = unique_stock_ids(stock_ids_from_text(" ".join(string_list(pros_cons.get("primary_risks")) + watch_texts)))
    if "3481" in all_text and "跌停" in all_text and "3481" not in avoid:
        avoid.insert(0, "3481")
    continue_ids = unique_stock_ids(stock_ids_from_text(" ".join(json.dumps(item, ensure_ascii=False) for item in list_value(stock_quality.get("excellent_picks")))))

    score = score_0_to_100(overall_eval.get("score_out_of_100"))
    return {
        "schema_version": SCHEMA_VERSION,
        "provider": provider,
        "review_date": review_date,
        "market": "TW",
        "overall": {
            "score": score,
            "verdict": verdict_from_score(score),
            "confidence": confidence_from_label(overall_eval.get("confidence_level")),
            "summary": string_value(overall_eval.get("verdict")) or "Gemini reviewer provided no overall summary.",
        },
        "quality": {
            "mainstream_alignment": 4 if leading else 3,
            "relative_strength": 4 if continue_ids else 3,
            "risk_control": 2 if "跌停" in all_text or "停損距離過寬" in all_text else 3,
            "timing_quality": 2 if "跌停" in all_text or "追價" in all_text else 3,
            "theme_fit": 4 if theme_synergy or leading else 3,
        },
        "observations": observations[:12] or plaintext_observations(all_text),
        "misses": misses[:8],
        "themes": {
            "strong": leading[:8],
            "weak": ["極端流動性陷阱"] if "跌停" in all_text or "一字線" in all_text else [],
            "watch": unique_strings(leading + ([theme_synergy] if theme_synergy else []))[:8],
        },
        "tomorrow_watch": {
            "continue": continue_ids[:10],
            "avoid_chasing": avoid[:10],
            "watch_for_reversal": avoid[:10],
            "theme_candidates": leading[:8],
        },
        "research_hypotheses": hypotheses[:8],
        "safety": {
            "algorithm_requested": False,
            "contains_algorithm_claim": False,
            "needs_human_review": False,
        },
    }


def first_meaningful_line(text: str) -> str:
    for line in text.splitlines():
        item = line.strip(" -#*　\t")
        if len(item) >= 20 and not item.startswith(("你說了", "Gemini 說了")):
            return item
    return text[:300].strip()


def plaintext_score(text: str) -> int:
    score = 65
    if "精準" in text or "完全過關" in text:
        score += 8
    if "翻車" in text or "嚴重矛盾" in text or "跌停" in text:
        score -= 10
    if "風險提示" in text or "風控" in text:
        score += 4
    return int(clamp(score, 0, 100))


def plaintext_observations(text: str) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for line in meaningful_lines(text):
        kind = ""
        severity = "medium"
        if any(token in line for token in ["精準", "過關", "命中", "符合", "捕捉"]):
            kind = "strength"
        elif any(token in line for token in ["風險", "盲點", "誤判", "跌停", "追高", "大跌"]):
            kind = "risk"
            severity = "high" if "跌停" in line or "嚴重" in line else "medium"
        if not kind:
            continue
        observations.append(observation(kind, line, line, stock_ids_from_text(line), severity))
        if len(observations) >= 10:
            break
    if not observations:
        observations.append(observation("risk", "自由文字回覆需人工複核", "無法穩定抽取 reviewer 觀察，已保留 raw response。", [], "medium"))
    return observations


def plaintext_misses(text: str) -> list[dict[str, Any]]:
    misses: list[dict[str, Any]] = []
    if "3481" in text and "群創" in text and ("跌停" in text or "大跌" in text):
        misses.append(
            {
                "symbol": "3481",
                "name": "群創",
                "issue": "疑似把大跌或跌停造成的量能/波動放大誤讀為多方轉強。",
                "likely_cause": "market_drag",
                "evidence": extract_context(text, "群創", 280),
            }
        )
    for line in meaningful_lines(text):
        if len(misses) >= 8:
            break
        if not any(token in line for token in ["誤判", "盲點", "風險", "追高"]):
            continue
        symbols = stock_ids_from_text(line)
        misses.append(
            {
                "symbol": symbols[0] if symbols else "",
                "name": "",
                "issue": line[:80],
                "likely_cause": cause_from_text(line),
                "evidence": line,
            }
        )
    return misses[:8]


def plaintext_hypotheses(text: str, packet: dict[str, Any]) -> list[dict[str, Any]]:
    hypotheses: list[dict[str, Any]] = []
    if "跌停" in text or "大跌" in text:
        hypotheses.append(
            {
                "hypothesis": "檢驗大跌/跌停爆量是否被動能訊號誤判為多方攻擊。",
                "why_it_matters": "外部 reviewer 指出大跌造成的量能與波動可能放大錯誤選股訊號。",
                "candidate_signal_family": "risk_control",
                "validation_hint": "用 historical replay 比較跌停、大跌、長黑爆量樣本在入榜後的隔日報酬與最大不利變動。",
                "priority": "high",
            }
        )
    if "追高" in text:
        hypotheses.append(
            {
                "hypothesis": "檢驗推薦價接近當日高點時的隔日追高風險。",
                "why_it_matters": "外部 reviewer 標記強勢股可能在隔日承受獲利了結。",
                "candidate_signal_family": "timing",
                "validation_hint": "比較推薦價相對當日高低區間位置與隔日開高走低/回撤機率。",
                "priority": "high",
            }
        )
    if not hypotheses:
        hypotheses = build_hypotheses({}, packet)
    return hypotheses[:8]


def meaningful_lines(text: str) -> list[str]:
    result = []
    for line in text.splitlines():
        item = line.strip(" -#*•　\t")
        if len(item) >= 12:
            result.append(item)
    return result


def extract_context(text: str, marker: str, width: int) -> str:
    index = text.find(marker)
    if index < 0:
        return marker
    start = max(0, index - width // 2)
    end = min(len(text), index + width)
    return text[start:end].strip()


def unique_strings(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = string_value(value)
        if item and item not in result:
            result.append(item)
    return result


def observation(kind: str, title: str, evidence: str, symbols: list[str], severity: str) -> dict[str, Any]:
    return {
        "type": kind,
        "title": title[:40] or "external reviewer observation",
        "evidence": evidence or title or "外部 reviewer 觀察。",
        "affected_symbols": unique_stock_ids(symbols),
        "severity": severity,
    }


def build_observations(
    payload: dict[str, Any],
    recommendation_quality: dict[str, Any],
    market_context: dict[str, Any],
    sector_flow: dict[str, Any],
) -> list[dict[str, Any]]:
    observations: list[dict[str, Any]] = []
    for item in string_list(recommendation_quality.get("strengths"))[:4]:
        observations.append(
            {
                "type": "strength",
                "title": item[:40],
                "evidence": item,
                "affected_symbols": [],
                "severity": "medium",
            }
        )
    for item in string_list(recommendation_quality.get("weaknesses"))[:4]:
        observations.append(
            {
                "type": "risk",
                "title": item[:40],
                "evidence": item,
                "affected_symbols": [],
                "severity": "medium",
            }
        )
    for item in string_list(market_context.get("risk_notes"))[:3]:
        observations.append(
            {
                "type": "risk",
                "title": item[:40],
                "evidence": item,
                "affected_symbols": [],
                "severity": "medium",
            }
        )
    for item in string_list(sector_flow.get("comments"))[:3]:
        observations.append(
            {
                "type": "strength",
                "title": item[:40],
                "evidence": item,
                "affected_symbols": [],
                "severity": "low",
            }
        )
    if not observations:
        observations.append(
            {
                "type": "risk",
                "title": "raw response requires human review",
                "evidence": "無法從外部 reviewer 回覆中穩定抽取觀察。",
                "affected_symbols": [],
                "severity": "medium",
            }
        )
    return observations[:12]


def build_misses(payload: dict[str, Any]) -> list[dict[str, Any]]:
    misses: list[dict[str, Any]] = []
    for item in list_value(payload.get("possible_misjudgments"))[:8]:
        if not isinstance(item, dict):
            continue
        issue = string_value(item.get("issue"))
        description = string_value(item.get("description"))
        misses.append(
            {
                "symbol": "",
                "name": "",
                "issue": issue or "possible misjudgment",
                "likely_cause": cause_from_text(f"{issue} {description}"),
                "evidence": description or issue or "外部 reviewer 標記為可能誤判。",
            }
        )
    return misses


def build_hypotheses(payload: dict[str, Any], packet: dict[str, Any]) -> list[dict[str, Any]]:
    hypotheses: list[dict[str, Any]] = []
    for item in list_value(payload.get("possible_misjudgments"))[:5]:
        if not isinstance(item, dict):
            continue
        issue = string_value(item.get("issue"))
        description = string_value(item.get("description"))
        if not issue and not description:
            continue
        hypotheses.append(
            {
                "hypothesis": f"檢驗：{issue or description}",
                "why_it_matters": description or issue,
                "candidate_signal_family": signal_family_from_text(f"{issue} {description}"),
                "validation_hint": "用歷史 ranking replay 比較該風險條件下的命中率、回撤與隔日開高走低比例。",
                "priority": "high" if string_value(item.get("severity")).upper() == "HIGH" else "medium",
            }
        )
    if not hypotheses:
        top_count = object_value(packet.get("market_overview")).get("top_count")
        hypotheses.append(
            {
                "hypothesis": "檢驗外部 reviewer 標記的動能與追高風險是否影響隔日表現。",
                "why_it_matters": f"本日 packet top_count={top_count}，需要把自由 review 轉成可回測條件。",
                "candidate_signal_family": "timing",
                "validation_hint": "累積 20 個交易日 raw review 後，統計高風險標記與隔日報酬/回撤的關係。",
                "priority": "medium",
            }
        )
    return hypotheses[:8]


def stocks_from_high_risk(payload: dict[str, Any]) -> list[str]:
    result = []
    for item in list_value(payload.get("stock_level_review")):
        if not isinstance(item, dict):
            continue
        if "HIGH" in string_value(item.get("risk_level")).upper():
            stock_id = string_value(item.get("stock_id"))
            if stock_id:
                result.append(stock_id)
    return result[:10]


def stocks_from_misjudgments(payload: dict[str, Any]) -> list[str]:
    return stocks_from_high_risk(payload)[:6]


def score_from_risks(payload: dict[str, Any]) -> int:
    high_risk_count = len(stocks_from_high_risk(payload))
    if high_risk_count >= 5:
        return 2
    if high_risk_count >= 3:
        return 3
    return 4


def score_from_timing(payload: dict[str, Any]) -> int:
    texts = json.dumps(payload, ensure_ascii=False)
    if "追高" in texts or "開高走低" in texts:
        return 2
    return 3


def score_0_to_100(value: Any) -> int:
    parsed = float_value(value, 0)
    if parsed <= 10:
        parsed *= 10
    return int(round(clamp(parsed, 0, 100)))


def score_0_to_5(value: Any) -> int:
    parsed = float_value(value, 0)
    if parsed <= 10:
        parsed = parsed / 2
    else:
        parsed = parsed / 20
    return int(round(clamp(parsed, 0, 5)))


def verdict_from_score(value: Any) -> str:
    score = score_0_to_100(value)
    if score >= 85:
        return "excellent"
    if score >= 65:
        return "good"
    if score >= 45:
        return "mixed"
    return "poor"


def cause_from_text(text: str) -> str:
    if "追高" in text or "漲幅" in text or "收最高" in text:
        return "overextended"
    if "族群" in text:
        return "theme_rotation"
    if "流動性" in text or "成交" in text:
        return "liquidity_weakness"
    return "unknown"


def signal_family_from_text(text: str) -> str:
    if "族群" in text or "AI" in text or "面板" in text:
        return "theme_momentum"
    if "追高" in text or "開高走低" in text:
        return "timing"
    if "停損" in text or "風險" in text:
        return "risk_control"
    if "成交" in text or "流動性" in text:
        return "liquidity"
    return "other"


def object_value(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def list_value(value: Any) -> list[Any]:
    return value if isinstance(value, list) else []


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [string_value(item) for item in value if string_value(item)]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def string_value(value: Any) -> str:
    return "" if value is None else str(value).strip()


def stock_ids_from_text(text: str) -> list[str]:
    return re.findall(r"\b[0-9]{4}\b", text)


def unique_stock_ids(values: list[str]) -> list[str]:
    result: list[str] = []
    for value in values:
        item = string_value(value)
        if item and item not in result:
            result.append(item)
    return result


def confidence_from_label(value: Any) -> float:
    text = string_value(value).upper()
    if "HIGH" in text:
        return 0.78
    if "MEDIUM" in text:
        return 0.62
    if "LOW" in text:
        return 0.35
    return 0.65


def float_value(value: Any, default: float) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def first_non_empty(*values: Any) -> Any:
    for value in values:
        if isinstance(value, list) and value:
            return value
        if isinstance(value, str) and value.strip():
            return value
        if value not in (None, "", []):
            return value
    return ""


def clamp(value: float, minimum: float, maximum: float) -> float:
    return max(minimum, min(maximum, value))


if __name__ == "__main__":
    raise SystemExit(main())
