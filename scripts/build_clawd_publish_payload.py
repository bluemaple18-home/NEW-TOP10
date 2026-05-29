#!/usr/bin/env python3
"""從每日決策日報產出 Clawd 頻道發送 payload。

此腳本只做 artifact 轉換，不呼叫 Clawd、不發送訊息、不讀取 token。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
PAYLOAD_SCHEMA_VERSION = "clawd-publish-payload.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="build Clawd-ready Top10 publish payload")
    parser.add_argument("--date", default=None, help="日報日期，格式 YYYY-MM-DD；未指定時使用最新 daily_report")
    parser.add_argument("--report", default=None, help="指定 daily_report JSON 路徑")
    parser.add_argument("--artifacts-dir", default="artifacts")
    parser.add_argument("--channel", default=None, help="Clawd channel，例如 discord / line / slack")
    parser.add_argument("--to", default=None, help="Clawd target，例如 channel:123")
    parser.add_argument("--max-items", type=int, default=10, help="訊息內最多列出幾檔")
    args = parser.parse_args()

    artifacts_dir = PROJECT_ROOT / args.artifacts_dir
    report_path = resolve_report_path(artifacts_dir=artifacts_dir, date=args.date, report=args.report)
    report = load_json(report_path)
    payload = build_payload(
        report=report,
        report_path=report_path,
        channel=args.channel,
        to=args.to,
        max_items=args.max_items,
    )

    ranking_date = payload["ranking_date"]
    payload_path = artifacts_dir / f"clawd_publish_payload_{ranking_date}.json"
    message_path = artifacts_dir / f"clawd_publish_message_{ranking_date}.md"
    payload["artifacts"]["payload"] = str(payload_path)
    payload["artifacts"]["message"] = str(message_path)

    artifacts_dir.mkdir(parents=True, exist_ok=True)
    message_path.write_text(payload["message_markdown"], encoding="utf-8")
    payload_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"CLAWD_PUBLISH_PAYLOAD_OK json={payload_path} md={message_path} status={payload['delivery']['status']}")
    return 0


def resolve_report_path(artifacts_dir: Path, date: str | None, report: str | None) -> Path:
    if report:
        path = Path(report)
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        if path.exists():
            return path
        raise FileNotFoundError(f"指定 daily report 不存在：{path}")

    if date:
        path = artifacts_dir / f"daily_report_{date}.json"
        if path.exists():
            return path
        raise FileNotFoundError(f"指定日期 daily report 不存在：{path}")

    files = sorted(artifacts_dir.glob("daily_report_*.json"))
    if not files:
        raise FileNotFoundError("找不到 daily_report_*.json")
    return files[-1]


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_payload(
    report: dict[str, Any],
    report_path: Path,
    channel: str | None,
    to: str | None,
    max_items: int,
) -> dict[str, Any]:
    ranking_date = str(report.get("ranking_date") or date_from_report_path(report_path))
    industry_map = load_industry_map()
    concept_map = load_concept_map()
    industry_bucket_map = load_notification_industry_buckets()
    bucket_rules = load_notification_theme_buckets()
    top_items = [
        enrich_item_for_audiences(item, industry_map, concept_map)
        for item in list(report.get("top10", []))[: max(1, max_items)]
    ]
    market_overview = build_market_overview(report, top_items, industry_bucket_map, bucket_rules)
    for item in top_items:
        item["market_context"] = stock_market_context(item, market_overview, industry_bucket_map, bucket_rules)
        raw_signals = raw_signal_texts(item.get("reasons", []))
        ai_features = ai_feature_names(item.get("reasons", []))
        item["notification_summary"] = notification_summary(item, raw_signals, ai_features)
    delivery_status = "READY_FOR_CLAWD" if channel and to else "PENDING_TARGET"
    missing = []
    if not channel:
        missing.append("channel")
    if not to:
        missing.append("to")

    message = render_message(
        report=report,
        ranking_date=ranking_date,
        top_items=top_items,
        market_overview=market_overview,
    )
    return {
        "schema_version": PAYLOAD_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ranking_date": ranking_date,
        "source": {
            "daily_report": str(report_path),
            "ranking_artifact": report.get("ranking_artifact"),
            "automation_status": report.get("automation_status", {}),
        },
        "delivery": {
            "status": delivery_status,
            "mode": "artifact_only",
            "channel": channel,
            "to": to,
            "missing": missing,
            "send_attempted": False,
            "note": "payload 已可交給 Clawd；本腳本不負責實際發送。",
        },
        "summary": report.get("summary", {}),
        "market_overview": market_overview,
        "risk": report.get("risk", {}),
        "top10": top_items,
        "message_markdown": message,
        "message_stats": {
            "characters": len(message),
            "listed_items": len(top_items),
        },
        "artifacts": {
            "payload": None,
            "message": None,
        },
    }


def date_from_report_path(path: Path) -> str:
    match = re.search(r"daily_report_(\d{4}-\d{2}-\d{2})\.json$", path.name)
    if not match:
        raise ValueError(f"daily report 檔名無法解析日期：{path}")
    return match.group(1)


def render_message(
    report: dict[str, Any],
    ranking_date: str,
    top_items: list[dict[str, Any]],
    market_overview: dict[str, Any],
) -> str:
    summary = report.get("summary", {})
    automation = report.get("automation_status", {})
    risk = report.get("risk", {})
    lines = [
        f"Top10 每日選股｜{ranking_date}",
        "",
        f"狀態：{automation.get('status') or 'UNKNOWN'}｜大盤：{market_label(summary.get('market_regime'))}",
        "讀法：這是今天的觀察名單，不是叫你一次買滿。盤勢不夠強時，後段名單只當候補。",
        "",
        "今日大盤與資金",
        f"- 大盤情況：{market_overview.get('market_text')}",
        f"- 資金分布：{market_overview.get('capital_flow_text')}",
        f"- 資金重心：{market_overview.get('hot_groups_text')}",
        f"- 熱門概念：{market_overview.get('hot_concepts_text')}",
        "",
        "今日名單怎麼讀？",
        f"- {list_reading_text(summary, len(top_items))}",
    ]

    primary_count = primary_watch_count(summary, len(top_items))
    primary_items = top_items[:primary_count]
    backup_items = top_items[primary_count:]

    lines.extend(["", "主觀察"])
    for item in primary_items:
        item["list_role"] = "primary"
        lines.extend(["", *stock_message_lines(item)])

    if backup_items:
        lines.extend(
            [
                "",
                "候補觀察",
                "後面這幾檔有題材或型態，但今天盤勢沒有強到要全部一起追。",
            ]
        )
        for item in backup_items:
            item["list_role"] = "backup"
            lines.extend(["", *stock_message_lines(item)])

    notes = list(risk.get("notes", []))
    lines.extend(["", "風險提醒"])
    if notes:
        lines.extend(f"- {note}" for note in notes[:3])
    else:
        lines.append("- 未提供額外風險摘要；請依交易計畫控管部位。")

    freshness = risk.get("data_freshness", {}).get("datasets", {})
    if freshness:
        latest_dates = sorted({str(info.get("latest_date")) for info in freshness.values() if info.get("latest_date")})
        if latest_dates:
            lines.extend(["", "資料狀態", f"- 排名使用的資料更新到 {latest_dates[-1]}。"])

    lines.append("")
    return "\n".join(lines)


def primary_watch_count(summary: dict[str, Any], total_count: int) -> int:
    regime = str(summary.get("market_regime") or "UNKNOWN")
    if total_count <= 0:
        return 0
    if regime == "RISK_ON":
        return total_count
    if regime == "NEUTRAL":
        return min(5, total_count)
    return min(3, total_count)


def list_reading_text(summary: dict[str, Any], total_count: int) -> str:
    regime = str(summary.get("market_regime") or "UNKNOWN")
    primary_count = primary_watch_count(summary, total_count)
    backup_count = max(0, total_count - primary_count)
    cash_weight = number_value(summary.get("cash_weight"))
    cash_text = f"、保留現金 {pct(cash_weight)}" if cash_weight is not None and cash_weight > 0 else ""
    if regime == "RISK_ON":
        return f"大盤偏多，{total_count} 檔都可納入觀察，但仍要分批看價位{cash_text}。"
    if regime == "NEUTRAL":
        return f"大盤中性，主看前 {primary_count} 檔，後面 {backup_count} 檔先放候補{cash_text}。"
    if regime == "RISK_OFF":
        return f"大盤偏弱，最多先看前 {primary_count} 檔，其餘 {backup_count} 檔只當候補{cash_text}。"
    return f"大盤狀態不明，先保守看前 {primary_count} 檔，其餘 {backup_count} 檔不要急著動{cash_text}。"


def enrich_item_for_audiences(
    item: dict[str, Any],
    industry_map: dict[str, dict[str, str]],
    concept_map: dict[str, list[str]],
) -> dict[str, Any]:
    enriched = dict(item)
    raw_signals = raw_signal_texts(item.get("reasons", []))
    ai_features = ai_feature_names(item.get("reasons", []))
    enriched["audience_group"] = audience_group(item, industry_map, concept_map)
    enriched["notification_summary"] = notification_summary(enriched, raw_signals, ai_features)
    enriched["detail_reasons"] = detail_reasons(raw_signals, ai_features)
    enriched["raw_signals"] = raw_signals + [f"AI:{feature}" for feature in ai_features]
    return enriched


def load_industry_map() -> dict[str, dict[str, str]]:
    path = PROJECT_ROOT / "data" / "reference" / "stock_industry_map.csv"
    if not path.exists():
        return {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        return {
            str(row.get("stock_id", "")).zfill(4): row
            for row in csv.DictReader(file)
            if row.get("stock_id")
        }


def load_concept_map() -> dict[str, list[str]]:
    path = PROJECT_ROOT / "data" / "reference" / "stock_concept_membership.csv"
    if not path.exists():
        return {}
    concepts: dict[str, list[tuple[float, str]]] = {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            if row.get("concept_type") != "theme":
                continue
            stock_id = str(row.get("stock_id", "")).zfill(4)
            concept = clean_concept_name(str(row.get("canonical_name") or row.get("raw_concept_name") or ""))
            if not stock_id or not concept or is_noisy_concept(concept):
                continue
            confidence = number_value(row.get("confidence")) or 0.0
            concepts.setdefault(stock_id, []).append((confidence, concept))
    return {
        stock_id: unique_preserve_order(
            concept for _, concept in sorted(rows, key=lambda item: (-item[0], item[1]))
        )[:6]
        for stock_id, rows in concepts.items()
    }


def load_notification_theme_buckets() -> list[dict[str, Any]]:
    path = PROJECT_ROOT / "config" / "notification_theme_buckets.csv"
    if not path.exists():
        return []
    rules = []
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            bucket = str(row.get("bucket") or "").strip()
            if not bucket:
                continue
            rules.append(
                {
                    "priority": int(number_value(row.get("priority")) or 999),
                    "bucket": bucket,
                    "industry_keywords": split_keywords(row.get("industry_keywords")),
                    "concept_keywords": split_keywords(row.get("concept_keywords")),
                    "notes": str(row.get("notes") or "").strip(),
                }
            )
    return sorted(rules, key=lambda row: (row["priority"], row["bucket"]))


def load_notification_industry_buckets() -> dict[str, str]:
    path = PROJECT_ROOT / "config" / "notification_industry_buckets.csv"
    if not path.exists():
        return {}
    result = {}
    with path.open(encoding="utf-8-sig", newline="") as file:
        for row in csv.DictReader(file):
            industry = str(row.get("industry_name") or "").strip()
            bucket = str(row.get("notification_bucket") or "").strip()
            if industry and bucket:
                result[industry] = bucket
    return result


def split_keywords(value: Any) -> list[str]:
    return [part.strip() for part in str(value or "").split("|") if part.strip()]


def audience_group(
    item: dict[str, Any],
    industry_map: dict[str, dict[str, str]],
    concept_map: dict[str, list[str]],
) -> dict[str, Any]:
    stock_id = str(item.get("stock_id", "")).zfill(4)
    reference = item.get("reference")
    if isinstance(reference, dict):
        industry_name = str(reference.get("industry_name") or "").strip()
        sector_name = str(reference.get("sector_name") or "").strip()
        concepts = [
            clean_concept_name(str(value))
            for value in reference.get("concept_tags", [])
            if str(value).strip() and not is_noisy_concept(clean_concept_name(str(value)))
        ]
        if industry_name or sector_name or concepts:
            return {
                "sector": audience_sector_label(sector_name, industry_name),
                "theme": industry_name or "未分類",
                "concepts": concepts,
                "source": "daily_report_reference",
            }

    mapped = industry_map.get(stock_id)
    if mapped:
        industry_name = str(mapped.get("industry_name") or "").strip()
        sector_name = str(mapped.get("sector_name") or "").strip()
        return {
            "sector": audience_sector_label(sector_name, industry_name),
            "theme": industry_name or "未分類",
            "concepts": concept_map.get(stock_id, []),
            "source": "stock_industry_map",
        }
    fallback = STOCK_GROUP_OVERRIDES.get(
        stock_id,
        {
            "sector": "其他",
            "theme": "未分類",
            "source": "fallback",
        },
    )
    return {**fallback, "concepts": concept_map.get(stock_id, [])}


def audience_sector_label(sector_name: str, industry_name: str) -> str:
    if industry_name:
        broad = broad_group_from_industry(industry_name)
        if broad != industry_name:
            return broad
    if sector_name == "科技":
        return "電子相關"
    if sector_name == "民生消費" and any(keyword in industry_name for keyword in ["觀光", "旅遊", "餐飲"]):
        return "觀光旅遊"
    if sector_name == "工業" and any(keyword in industry_name for keyword in ["航運", "海運"]):
        return "航運"
    return sector_name or broad_group_from_industry(industry_name)


def broad_group_from_industry(industry_name: str) -> str:
    if any(keyword in industry_name for keyword in ["半導體", "記憶體", "電子", "光通訊", "電腦", "零組件", "IC", "網通", "機殼", "電池", "電源", "設備"]):
        return "電子相關"
    if any(keyword in industry_name for keyword in ["觀光", "旅遊", "餐飲"]):
        return "觀光旅遊"
    if any(keyword in industry_name for keyword in ["航運", "海運"]):
        return "航運"
    return industry_name or "其他"


def clean_concept_name(value: str) -> str:
    text = str(value).strip()
    if "/" in text:
        text = text.split("/")[-1].strip()
    return text


def is_noisy_concept(concept: str) -> bool:
    noisy_keywords = ["指數成分股", "基金", "認購", "認售", "集團股"]
    noisy_exact = {"ESG", "大陸收成股"}
    if concept in noisy_exact:
        return True
    return any(keyword in concept for keyword in noisy_keywords)


def unique_preserve_order(values: Any) -> list[str]:
    result = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result


def build_market_overview(
    report: dict[str, Any],
    top_items: list[dict[str, Any]],
    industry_bucket_map: dict[str, str],
    bucket_rules: list[dict[str, Any]],
) -> dict[str, Any]:
    summary = report.get("summary", {})
    market = market_label(summary.get("market_regime"))
    if market == "中性":
        market_text = "今天不是全面大多頭，也不是全面避開；比較像挑個股的盤，適合分散觀察。"
    elif market == "偏多":
        market_text = "今天大盤氣氛偏多，資金願意往強勢股靠，但還是不能追到忘記停損。"
    elif market == "偏弱":
        market_text = "今天大盤偏弱，先保守看待，名單有出現也要降低追價衝動。"
    else:
        market_text = f"今天大盤狀態是 {market}，先看個股有沒有真的被資金點火。"

    group_rows = group_summary(top_items)
    bucket_rows = capital_bucket_summary(top_items, industry_bucket_map, bucket_rules)
    concept_rows = concept_summary(top_items)
    return {
        "market": market,
        "market_text": market_text,
        "capital_flow": capital_flow_rows(bucket_rows, summary),
        "capital_flow_text": capital_flow_text(bucket_rows, summary),
        "hot_groups": group_rows,
        "hot_groups_text": capital_focus_text(bucket_rows, group_rows),
        "hot_concepts": concept_rows,
        "hot_concepts_text": hot_concepts_text(concept_rows),
    }


def group_summary(top_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, dict[str, Any]] = {}
    for item in top_items:
        group = item.get("audience_group", {})
        sector = str(group.get("sector") or "其他")
        theme = str(group.get("theme") or "未分類")
        weight = number_value(item.get("position", {}).get("suggested_weight")) or 0.0
        row = groups.setdefault(sector, {"sector": sector, "count": 0, "weight": 0.0, "themes": {}})
        row["count"] += 1
        row["weight"] += weight
        row["themes"][theme] = row["themes"].get(theme, 0) + 1
    result = []
    for row in groups.values():
        themes = sorted(row["themes"].items(), key=lambda value: (-value[1], value[0]))
        result.append(
            {
                "sector": row["sector"],
                "count": row["count"],
                "capital_weight": round(row["weight"], 4),
                "suggested_weight": round(row["weight"], 4),
                "themes": [theme for theme, _ in themes[:4]],
            }
        )
    return sorted(result, key=lambda row: (-row["count"], -row["suggested_weight"], row["sector"]))


def capital_bucket_summary(
    top_items: list[dict[str, Any]],
    industry_bucket_map: dict[str, str],
    bucket_rules: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    buckets: dict[str, dict[str, Any]] = {}
    for item in top_items:
        group = item.get("audience_group", {})
        theme = str(group.get("theme") or group.get("sector") or "未分類")
        sector = str(group.get("sector") or "其他")
        concepts = [str(value) for value in group.get("concepts", []) if str(value).strip()]
        bucket = capital_bucket_label(
            sector=sector,
            theme=theme,
            concepts=concepts,
            industry_bucket_map=industry_bucket_map,
            rules=bucket_rules,
        )
        weight = number_value(item.get("position", {}).get("suggested_weight")) or 0.0
        row = buckets.setdefault(
            bucket,
            {"name": bucket, "sector": sector, "count": 0, "weight": 0.0, "themes": {}},
        )
        row["count"] += 1
        row["weight"] += weight
        row["themes"][theme] = row["themes"].get(theme, 0) + 1
    return [
        {
            "name": row["name"],
            "sector": row["sector"],
            "count": row["count"],
            "capital_weight": round(row["weight"], 4),
            "themes": [
                theme
                for theme, _ in sorted(row["themes"].items(), key=lambda value: (-value[1], value[0]))[:4]
            ],
        }
        for row in sorted(buckets.values(), key=lambda value: (-value["weight"], value["name"]))
    ]


def capital_bucket_label(
    sector: str,
    theme: str,
    concepts: list[str],
    industry_bucket_map: dict[str, str],
    rules: list[dict[str, Any]],
) -> str:
    if theme in industry_bucket_map:
        return industry_bucket_map[theme]
    concept_text = " ".join(concepts)
    for rule in rules:
        industry_hit = any(keyword in theme for keyword in rule["industry_keywords"])
        concept_hit = any(keyword in concept_text for keyword in rule["concept_keywords"])
        if industry_hit or concept_hit:
            return str(rule["bucket"])
    return sector or theme or "其他"


def capital_flow_rows(bucket_rows: list[dict[str, Any]], summary: dict[str, Any]) -> list[dict[str, Any]]:
    rows = [
        {
            "name": str(row.get("name") or "其他"),
            "sector": str(row.get("sector") or "其他"),
            "weight": round(number_value(row.get("capital_weight")) or 0.0, 4),
            "count": row.get("count", 0),
            "themes": row.get("themes", []),
        }
        for row in bucket_rows
        if (number_value(row.get("capital_weight")) or 0.0) > 0
    ]
    cash_weight = number_value(summary.get("cash_weight")) or 0.0
    if cash_weight > 0:
        rows.append({"name": "保留現金", "sector": "現金", "weight": round(cash_weight, 4), "count": 0})
    return sorted(rows, key=lambda row: (-row["weight"], row["name"]))


def capital_flow_text(bucket_rows: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    stock_rows = [row for row in capital_flow_rows(bucket_rows, summary) if row.get("sector") != "現金"]
    cash_weight = number_value(summary.get("cash_weight")) or 0.0
    if not stock_rows:
        return "目前沒有足夠資料判斷資金分布，先看個股強弱。"
    stock_text = "、".join(f"{row['name']} {pct(row['weight'])}" for row in stock_rows[:8])
    if cash_weight > 0:
        return f"{stock_text}；另外保留現金 {pct(cash_weight)}，代表今天沒有把資金全壓進名單。"
    return stock_text + "。"


def capital_focus_text(bucket_rows: list[dict[str, Any]], group_rows: list[dict[str, Any]]) -> str:
    stock_rows = [row for row in capital_flow_rows(bucket_rows, {}) if row.get("sector") != "現金"]
    if not stock_rows:
        return hot_groups_text(group_rows, 0)
    lead = stock_rows[0]
    parts = [f"今天不是亂分散，主軸先看 {lead['name']}"]
    if len(stock_rows) > 1:
        parts.append("其次是 " + "、".join(row["name"] for row in stock_rows[1:4]))
    electronic = next((row for row in group_rows if row.get("sector") == "電子相關"), None)
    if electronic:
        parts.append(f"電子相關合計 {pct(electronic.get('capital_weight'))}，但已拆成不同題材看")
    return "；".join(parts) + "。"


def stock_market_context(
    item: dict[str, Any],
    market_overview: dict[str, Any],
    industry_bucket_map: dict[str, str],
    bucket_rules: list[dict[str, Any]],
) -> dict[str, Any]:
    group = item.get("audience_group", {})
    theme = str(group.get("theme") or group.get("sector") or "未分類")
    sector = str(group.get("sector") or "其他")
    concepts = [str(value) for value in group.get("concepts", []) if str(value).strip()]
    bucket = capital_bucket_label(
        sector=sector,
        theme=theme,
        concepts=concepts,
        industry_bucket_map=industry_bucket_map,
        rules=bucket_rules,
    )
    capital_rows = [row for row in market_overview.get("capital_flow", []) if row.get("sector") != "現金"]
    bucket_row = next((row for row in capital_rows if row.get("name") == bucket), None)
    lead = capital_rows[0] if capital_rows else None
    hot_concepts = [str(row.get("concept")) for row in market_overview.get("hot_concepts", []) if row.get("concept")]
    matched_concepts = [concept for concept in concepts if concept in hot_concepts]
    return {
        "bucket": bucket,
        "bucket_weight": bucket_row.get("weight") if bucket_row else None,
        "bucket_count": bucket_row.get("count") if bucket_row else 0,
        "is_lead_bucket": bool(lead and lead.get("name") == bucket),
        "lead_bucket": lead.get("name") if lead else None,
        "lead_weight": lead.get("weight") if lead else None,
        "market": market_overview.get("market"),
        "matched_hot_concepts": matched_concepts[:2],
    }


def market_context_text(item: dict[str, Any]) -> str:
    context = item.get("market_context") if isinstance(item.get("market_context"), dict) else {}
    stock_name = str(item.get("stock_name") or "這檔").strip() or "這檔"
    bucket = str(context.get("bucket") or item.get("audience_group", {}).get("theme") or "這個族群")
    weight = pct(context.get("bucket_weight")) if context.get("bucket_weight") is not None else None
    lead_bucket = str(context.get("lead_bucket") or "")
    matched = [str(value) for value in context.get("matched_hot_concepts", []) if str(value).strip()]
    if context.get("is_lead_bucket"):
        weight_text = f"（約 {weight}）" if weight else ""
        text = pick_variant(
            item,
            "market_context_lead",
            [
                f"{stock_name}落在今天資金最集中的 {bucket}{weight_text}，所以它不是孤立強，是跟著今日主軸被挑出來。",
                f"今天資金最明顯往 {bucket}{weight_text} 集中，{stock_name}剛好在這條主線上。",
                f"大盤中性時要挑主軸股，{stock_name}屬於今天資金第一順位的 {bucket}{weight_text}。",
            ],
        )
    elif bucket and lead_bucket:
        weight_text = f"（約 {weight}）" if weight else ""
        text = pick_variant(
            item,
            "market_context_side",
            [
                f"{stock_name}不在第一主軸 {lead_bucket}，但屬於今天有分到資金的 {bucket}{weight_text}，所以要看它能不能比主軸股更有續航。",
                f"今天盤面主軸是 {lead_bucket}，{stock_name}則是在支線 {bucket}{weight_text}裡轉強。",
                f"{bucket}{weight_text}不是今天最大資金池，但{stock_name}在這條支線裡有自己的強度。",
                f"資金最大方向先看 {lead_bucket}；{stock_name}屬於次主線 {bucket}{weight_text}，要更重視後續確認。",
            ],
        )
    else:
        text = f"{stock_name}不是今天最集中的族群，入選關鍵更偏向個股自己的強度。"
    if matched:
        text += f" 同時也連到熱門概念 {compact_tags(matched, 2)}。"
    return text


def hot_groups_text(group_rows: list[dict[str, Any]], total_count: int) -> str:
    if not group_rows:
        return "今天沒有明顯集中族群，名單比較分散。"
    top = group_rows[0]
    parts = [
        f"{top['sector']}最集中（10檔裡有 {top['count']} 檔）"
    ]
    if top.get("themes"):
        parts.append("細分偏 " + "、".join(top["themes"]))
    others = [row for row in group_rows[1:] if row["count"] > 0]
    if others:
        parts.append("另外還有 " + "、".join(f"{row['sector']} {row['count']} 檔" for row in others[:3]))
    return "；".join(parts) + "。"


def concept_summary(top_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts: dict[str, int] = {}
    examples: dict[str, list[str]] = {}
    for item in top_items:
        stock_label = f"{item.get('stock_id')} {item.get('stock_name')}"
        for concept in item.get("audience_group", {}).get("concepts", [])[:8]:
            counts[concept] = counts.get(concept, 0) + 1
            examples.setdefault(concept, []).append(stock_label)
    rows = [
        {"concept": concept, "count": count, "examples": examples.get(concept, [])[:3]}
        for concept, count in counts.items()
    ]
    return sorted(rows, key=lambda row: (-row["count"], row["concept"]))[:6]


def hot_concepts_text(concept_rows: list[dict[str, Any]]) -> str:
    if not concept_rows:
        return "目前沒有足夠概念資料，先看個股名單。"
    top = concept_rows[:4]
    return "、".join(f"{row['concept']}（{row['count']} 檔）" for row in top) + "。"


def notification_summary(item: dict[str, Any], raw_signals: list[str], ai_features: list[str]) -> dict[str, Any]:
    why_parts = stock_reason_bullets(item, raw_signals, ai_features)
    return {
        "conclusion": stock_conclusion(item, raw_signals),
        "why_bullets": why_parts,
        "translation": plain_translation(item, raw_signals, why_parts),
        "risk": risk_summary_text(item),
    }


def stock_message_lines(item: dict[str, Any]) -> list[str]:
    summary = item.get("notification_summary", {})
    lines = [
        f"{item.get('rank')}. {item.get('stock_id')} {item.get('stock_name')}｜{stock_tagline(item)}",
        str(summary.get("conclusion") or "💤 觀察中"),
        "",
        "跟今天盤勢的關係：",
        market_context_text(item),
        "",
        "為什麼入選：",
    ]
    for reason in summary.get("why_bullets", []):
        lines.append(f"- {reason}")
    lines.extend(
        [
            "",
            "怎麼看：",
            *action_summary_lines(item),
            "",
            "白話翻譯：",
            str(summary.get("translation") or ""),
            f"提醒：{summary.get('risk')}",
        ]
    )
    return lines


def stock_conclusion(item: dict[str, Any], raw_signals: list[str]) -> str:
    close = number_value(item.get("close"))
    if close is not None and close >= 1000:
        return "⚠️ 高價強勢股，能看但不能亂追"
    if has_signal(raw_signals, "紅三兵"):
        return "🚀 多方延續，短線仍有氣勢"
    if has_signal(raw_signals, "成交量暴增"):
        return "🔥 交易轉熱，可列入觀察"
    if has_signal(raw_signals, "MACD"):
        return "🛡 整理後轉強，先觀察能不能站穩"
    if has_signal(raw_signals, "錘子線"):
        return "🛡 拉回有人接，短線偏強"
    if has_signal(raw_signals, "突破20日") and has_signal(raw_signals, "跳空強勢收紅"):
        return "🔥 短線偏強，可觀察"
    return "💤 觀察中，等下一步確認"


def stock_reason_bullets(item: dict[str, Any], raw_signals: list[str], ai_features: list[str]) -> list[str]:
    bullets = []
    group = item.get("audience_group", {})
    concepts = [str(value) for value in group.get("concepts", []) if str(value).strip()]
    theme = stock_theme(item)
    stock_name = str(item.get("stock_name") or "這檔").strip() or "這檔"
    if has_signal(raw_signals, "突破20日"):
        bullets.append(
            pick_variant(
                item,
                "breakout",
                [
                    f"{theme}股價剛越過近期壓力，代表上方賣壓被買盤吃掉一部分。",
                    f"{stock_name}不是只在原地整理，而是往上推過最近容易卡關的位置。",
                    f"{stock_name}今天買方願意用更高價格接貨，短線氣勢比前幾天更明顯。",
                    f"{stock_name}近期壓力區被往上突破，市場接受價格正在墊高。",
                ],
            )
        )
    market_detail = market_signal_bridge(item, raw_signals)
    if market_detail:
        bullets.append(market_detail)
    if has_signal(raw_signals, "跳空強勢收紅"):
        bullets.append(
            pick_variant(
                item,
                "gap",
                [
                    f"{stock_name}早盤買氣先表態，尾盤也沒有被明顯倒貨壓回去。",
                    f"{stock_name}開高後沒有一路滑掉，代表追價資金至少守到收盤。",
                    f"{stock_name}今天不是只有盤中衝一下，收盤仍留在相對強的位置。",
                    f"{stock_name}一開盤氣勢就偏多，收盤沒有把優勢全部吐回去。",
                ],
            )
        )
    if has_signal(raw_signals, "MACD"):
        bullets.append(
            pick_variant(
                item,
                "macd",
                [
                    f"{stock_name}整理一段時間後動能開始翻正，不是只有單日硬拉價格。",
                    f"{stock_name}短線動能剛轉強，接下來重點看買盤能不能延續。",
                    f"{stock_name}價格和動能開始同方向，這比單純突破更有參考性。",
                ],
            )
        )
    if has_signal(raw_signals, "成交量暴增"):
        bullets.append(
            pick_variant(
                item,
                "volume",
                [
                    f"{stock_name}成交突然放大，代表今天有更多資金開始盯這檔。",
                    f"{stock_name}量能比平常熱，短線關注度明顯升溫。",
                    f"{theme}買賣變得更活躍，市場注意力正在靠過來。",
                    f"{stock_name}不是只有價格動，成交也跟著放大，這點比單純上漲更重要。",
                ],
            )
        )
    if has_signal(raw_signals, "紅三兵"):
        bullets.append(
            pick_variant(
                item,
                "red_three",
                [
                    f"{stock_name}股價連續幾天墊高，多方還沒有明顯退場。",
                    f"{stock_name}不是第一天轉強，前面已經有資金連續推進。",
                    f"{stock_name}短線走勢一階一階往上，買方節奏還算完整。",
                ],
            )
        )
    if has_signal(raw_signals, "錘子線"):
        bullets.append(
            pick_variant(
                item,
                "hammer",
                [
                    f"{stock_name}盤中被賣下去後有人接，低檔承接力道不差。",
                    f"{stock_name}下殺時沒有一路破底，代表低位仍有買盤願意接。",
                    f"{stock_name}賣壓出來時沒有失控，短線支撐感比前面好。",
                ],
            )
        )
    ai_bullet = ai_reason_bullet(item, ai_features)
    if ai_bullet:
        bullets.append(ai_bullet)
    if concepts:
        bullets.append(
            pick_variant(
                item,
                "theme",
                [
                    f"產業標籤偏 {compact_tags(concepts, 2)}，不是完全沒有題材支撐。",
                    f"題材線索落在 {compact_tags(concepts, 2)}，容易被同族群資金一起檢視。",
                    f"它連到 {compact_tags(concepts, 2)}，後面要一起看同題材有沒有續強。",
                    f"從族群來看，{compact_tags(concepts, 2)} 是它今天比較容易被注意的原因。",
                ],
            )
        )
    if not bullets:
        bullets.append("價格和成交狀況比前幾天更積極，先放進觀察名單。")
    return dedupe_keep_order(bullets)[:4]


def market_signal_bridge(item: dict[str, Any], raw_signals: list[str]) -> str | None:
    context = item.get("market_context") if isinstance(item.get("market_context"), dict) else {}
    stock_name = str(item.get("stock_name") or "這檔").strip() or "這檔"
    bucket = str(context.get("bucket") or "").strip()
    if not bucket:
        return None
    if context.get("is_lead_bucket") and has_signal(raw_signals, "成交量暴增"):
        return f"{bucket}是今天資金主軸，{stock_name}又同步放量，代表族群和個股都有熱度。"
    if context.get("is_lead_bucket") and has_signal(raw_signals, "跳空強勢收紅"):
        return f"{bucket}今天資金集中，{stock_name}開高後還能守住，表示它有跟上主軸節奏。"
    if not context.get("is_lead_bucket") and has_signal(raw_signals, "突破20日"):
        lead = str(context.get("lead_bucket") or "主軸族群")
        return pick_variant(
            item,
            "market_signal_side",
            [
                f"雖然今天第一主軸是 {lead}，但{stock_name}自己也突破壓力，屬於支線裡較強的一檔。",
                f"在 {lead} 吸走最多目光時，{stock_name}還能靠自己的走勢擠進名單。",
                f"它不是靠大盤全面上漲被抬進來，而是{stock_name}本身有突破動作。",
            ],
        )
    return None


def plain_translation(item: dict[str, Any], raw_signals: list[str], bullets: list[str]) -> str:
    group = item.get("audience_group", {})
    theme = str(group.get("theme") or "").strip()
    subject = f"{theme}這檔" if theme and theme != "未分類" else "這檔"
    context = item.get("market_context") if isinstance(item.get("market_context"), dict) else {}
    role = str(item.get("list_role") or "")
    prefix = ""
    if context.get("is_lead_bucket"):
        prefix = f"它在今天資金主軸 {context.get('bucket')} 裡，"
    elif context.get("lead_bucket") and role == "backup":
        prefix = f"它不是今天第一主軸 {context.get('lead_bucket')}，所以先當候補看，"
    elif context.get("lead_bucket"):
        prefix = f"它不是今天第一主軸 {context.get('lead_bucket')}，但個股訊號夠強，"
    if number_value(item.get("close")) and number_value(item.get("close")) >= 300:
        return pick_variant(
            item,
            "translation_high_price",
            [
                f"{prefix}{subject}走勢強，但單價高，買錯時壓力也大，適合小量觀察。",
                f"{prefix}{subject}有資金推升，但價格不便宜，重點是等它在觀察區間內還能不能守住。",
                f"{prefix}{subject}屬於高價強勢股，能看，但不要用一般低價股的節奏去追。",
            ],
        )
    if has_signal(raw_signals, "MACD"):
        return pick_variant(
            item,
            "translation_momentum",
            [
                f"{prefix}{subject}不是單純衝高，短線動能也有跟上；重點是後面能不能站穩。",
                f"{prefix}{subject}比較像整理後重新轉強，先看買盤能不能連續幾天守住。",
                f"{prefix}{subject}動能剛翻正，現在適合觀察續航，不適合情緒性追高。",
            ],
        )
    if has_signal(raw_signals, "紅三兵"):
        return pick_variant(
            item,
            "translation_trend",
            [
                f"{prefix}{subject}目前是多方連續推進的狀態，但連漲後更要避免追在太急的位置。",
                f"{prefix}{subject}短線氣勢還在，不過已經不是剛起漲，觀察重點是拉回有沒有人接。",
                f"{prefix}{subject}買方節奏還順，但越順的股票越要等合理位置，不要一看到強就衝。",
            ],
        )
    if has_signal(raw_signals, "錘子線"):
        return pick_variant(
            item,
            "translation_support",
            [
                f"{prefix}{subject}盤中有賣壓但被接住，代表市場還願意撐，適合先觀察。",
                f"{prefix}{subject}不是一路強攻，而是跌下去有人撐；這種要看支撐能不能再守一次。",
                f"{prefix}{subject}低檔承接變明顯，但還不到無腦追價，先看買盤是否延續。",
            ],
        )
    if has_signal(raw_signals, "成交量暴增"):
        return pick_variant(
            item,
            "translation_volume",
            [
                f"{prefix}{subject}今天有資金轉熱的味道，但熱起來也容易震盪，適合看清楚價位再動。",
                f"{prefix}{subject}今天被市場重新注意到，短線偏強；接下來要看量能會不會只是一天熱。",
                f"{prefix}{subject}不是冷門股自己飄上去，而是成交跟著放大；可以觀察，但不要追太急。",
                f"{prefix}{subject}買盤有升溫，適合放進名單追蹤，等價格回到合理區間再判斷。",
            ],
        )
    return pick_variant(
        item,
        "translation_default",
        [
            f"{prefix}{subject}今天被資金往上推，短線偏強；可以觀察，但不要看到上榜就追高。",
            f"{prefix}{subject}目前有轉強跡象，但還需要下一根確認，不急著一次做滿。",
            f"{prefix}{subject}短線表現比前幾天積極，先放觀察名單，等價格和量能一起確認。",
        ],
    )


def stock_tagline(item: dict[str, Any]) -> str:
    group = item.get("audience_group", {})
    theme = str(group.get("theme") or group.get("sector") or "未分類")
    concepts = [str(value) for value in group.get("concepts", []) if str(value).strip()]
    if concepts:
        return f"{theme}｜{compact_tags(concepts, limit=3)}"
    return theme


def stock_theme(item: dict[str, Any]) -> str:
    group = item.get("audience_group", {})
    theme = str(group.get("theme") or group.get("sector") or "").strip()
    if theme and theme != "未分類":
        return f"{theme}這檔"
    return "這檔"


def ai_reason_bullet(item: dict[str, Any], ai_features: list[str]) -> str | None:
    labels = [AI_REASON_LABELS.get(feature) for feature in ai_features]
    labels = [label for label in labels if label]
    labels = dedupe_keep_order(labels)
    if not labels:
        return None
    if len(labels) == 1:
        return pick_variant(
            item,
            "ai_single",
            [
                f"模型加分點主要來自{labels[0]}，不是只看單一突破。",
                f"除了價格表現，模型也看到{labels[0]}這個加分點。",
                f"數據面加分落在{labels[0]}，所以它不是只有型態好看。",
            ],
        )
    joined = "、".join(labels[:2])
    return pick_variant(
        item,
        "ai_combo",
        [
            f"模型加分不只看價格，也看到{joined}。",
            f"除了型態，數據面還有{joined}在加分。",
            f"這檔入選不是單靠突破，{joined}也有幫忙加分。",
            f"從模型角度看，{joined}讓它比一般轉強股更醒目。",
        ],
    )


def pick_variant(item: dict[str, Any], salt: str, variants: list[str]) -> str:
    if not variants:
        return ""
    rank = integer_value(item.get("rank"))
    if rank is not None and rank > 0:
        offset = 0
        for char in salt:
            offset = (offset * 17 + ord(char)) % len(variants)
        return variants[(rank - 1 + offset) % len(variants)]
    key = f"{item.get('stock_id','')}|{item.get('stock_name','')}|{item.get('rank','')}|{salt}"
    value = 0
    for char in key:
        value = (value * 131 + ord(char)) % 1_000_003
    index = value % len(variants)
    return variants[index]


def dedupe_keep_order(values: list[str]) -> list[str]:
    result = []
    seen = set()
    for value in values:
        text = str(value).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text)
    return result


def compact_tags(tags: list[str], limit: int) -> str:
    selected = []
    for tag in tags:
        if tag not in selected:
            selected.append(tag)
        if len(selected) >= limit:
            break
    return "、".join(selected)


def has_signal(raw_signals: list[str], keyword: str) -> bool:
    return any(keyword in signal for signal in raw_signals)


def detail_reasons(raw_signals: list[str], ai_features: list[str]) -> list[dict[str, str]]:
    details = []
    for signal in raw_signals:
        details.append(
            {
                "type": "technical_signal",
                "label": professional_signal_label(signal),
                "plain": novice_signal_label(signal),
                "raw": signal,
            }
        )
    for feature in ai_features:
        details.append(
            {
                "type": "ai_factor",
                "label": PROFESSIONAL_FEATURE_LABELS.get(feature, feature),
                "plain": NOVICE_FEATURE_LABELS.get(feature, "模型認為這個數據有加分"),
                "raw": feature,
            }
        )
    return details


def raw_signal_texts(reasons: list[Any]) -> list[str]:
    texts = []
    for reason in reasons:
        text = str(reason).strip()
        if not text:
            continue
        if text.startswith(("進場", "止損", "停損", "目標")):
            continue
        if text.startswith("AI:"):
            continue
        texts.append(text)
    return texts


def ai_feature_names(reasons: list[Any]) -> list[str]:
    for reason in reasons:
        text = str(reason).strip()
        if not text.startswith("AI:"):
            continue
        return re.findall(r"([A-Za-z0-9_]+)\([+-]?[0-9.]+\)", text)[:3]
    return []


def novice_reason_parts(raw_signals: list[str], ai_features: list[str]) -> list[str]:
    parts = []
    for signal in raw_signals:
        label = novice_signal_label(signal)
        if label and label not in parts:
            parts.append(label)
    for feature in ai_features:
        label = NOVICE_FEATURE_LABELS.get(feature)
        if label and label not in parts:
            parts.append(label)
    return parts


def novice_signal_label(signal: str) -> str:
    checks = [
        ("突破20日", "股價突破最近一段時間大家賣壓比較重的位置"),
        ("突破60日", "股價突破更長一段時間的壓力區"),
        ("跳空強勢收紅", "一開盤買盤就比較積極，收盤也沒有被打下來"),
        ("MACD", "短線動能開始轉強"),
        ("成交量暴增", "今天交易明顯變熱，市場注意力提高"),
        ("紅三兵", "股價連續幾天走強"),
        ("錘子線", "盤中被賣下去後又有人接回來"),
        ("月線支撐", "股價靠近重要支撐時有人接"),
        ("candle_bull_marubozu", "當天買方力道很強"),
        ("pattern_stop_loss", "停損距離還算可控"),
    ]
    for needle, label in checks:
        if needle in signal:
            return label
    return "股價和成交狀況比前幾天更強"


def professional_signal_label(signal: str) -> str:
    if signal in PROFESSIONAL_SIGNAL_LABELS:
        return PROFESSIONAL_SIGNAL_LABELS[signal]
    for needle, label in PROFESSIONAL_SIGNAL_CONTAINS:
        if needle in signal:
            return label
    return signal


def action_summary_lines(item: dict[str, Any]) -> list[str]:
    trade = item.get("trade_plan", {})
    entry_low, entry_high = entry_zone_values(trade)
    lines = [
        f"- 觀察區間：{num(entry_low)} ~ {num(entry_high)} 元",
        f"- 跌破 {num(trade.get('stop_loss'))} 元，代表走勢轉弱，先不要硬接。",
        f"- 上方第一壓力先看 {num(trade.get('target_price'))} 元。",
    ]
    role = str(item.get("list_role") or "")
    context = item.get("market_context") if isinstance(item.get("market_context"), dict) else {}
    if role == "backup":
        lines.append(
            "- "
            + pick_variant(
                item,
                "action_backup",
                [
                    "因為今天不是主觀察名單，除非回到觀察區間還有買盤承接，否則先等。",
                    "候補股不要急著追，先看它回到區間時量能有沒有續熱。",
                    "排名落在候補，代表可以追蹤，但要等價格和買盤一起確認。",
                    "除非主軸續強、它也守在觀察區間內，否則先放觀察就好。",
                ],
            )
        )
    elif context.get("is_lead_bucket"):
        lines.append(
            "- "
            + pick_variant(
                item,
                "action_lead",
                [
                    "它在今日資金主軸裡，強勢時可以看，但追高更要守區間。",
                    "主軸股容易被追價，最好等價格落在區間內再判斷。",
                    "族群有資金加持，但若跌破區間，代表熱度沒有延續。",
                ],
            )
        )
    else:
        lines.append(
            "- "
            + pick_variant(
                item,
                "action_side",
                [
                    "它不是今日最大主軸，重點看個股強度能不能延續。",
                    "支線股要更挑價格，站不穩觀察區間就先退一步。",
                    "如果主軸資金沒有外溢到它身上，就不要硬追。",
                ],
            )
        )
    return lines


def entry_zone_values(trade: dict[str, Any]) -> tuple[float | None, float | None]:
    zone = trade.get("entry_zone")
    if isinstance(zone, dict):
        low = number_value(zone.get("low"))
        high = number_value(zone.get("high"))
        if low is not None and high is not None:
            return min(low, high), max(low, high)

    entry = number_value(trade.get("entry"))
    if entry is None:
        return None, None
    return entry, round(entry * 1.015, 2)


def risk_summary_text(item: dict[str, Any]) -> str:
    scores = item.get("scores", {})
    position = item.get("position", {})
    trade = item.get("trade_plan", {})
    group = item.get("audience_group", {})
    concepts = [str(value) for value in group.get("concepts", []) if str(value).strip()]
    penalty = number_value(scores.get("risk_penalty"))
    if penalty is not None and penalty > 0:
        return "這檔有風險扣分，買之前要先想好停損，不能越跌越加。"

    close = number_value(item.get("close"))
    model_prob = number_value(scores.get("model_prob"))
    risk_reward = number_value(trade.get("risk_reward"))
    weight = number_value(position.get("suggested_weight"))
    why = str(item.get("notification_summary", {}).get("why") or "")

    if close is not None and close >= 300:
        return "股價單價高，漲跌一格金額感受會比較大，部位要比一般股票更小。"
    if model_prob is not None and model_prob < 0.38:
        return "這檔訊號還沒有強到可以重押，比較適合先觀察或很小部位試單。"
    if concepts and any(tag in THEME_CLUSTER_TAGS for tag in concepts):
        return f"這檔也連到 {compact_tags([tag for tag in concepts if tag in THEME_CLUSTER_TAGS], 2)}，同題材不要一次買太多檔。"
    if "交易明顯變熱" in why:
        return "市場注意力變高時，短線也容易震盪，追價要更保守。"
    if risk_reward is not None and risk_reward <= 2.0:
        return "上漲空間和停損距離約二比一，進場後要照計畫執行，不適合凹單。"
    if weight is not None and weight >= 0.065:
        return "這檔在今天名單裡相對醒目，但越醒目的股票越容易震盪，追價要保守。"
    return "這檔先當觀察名單，不要因為上榜就重壓。"


def market_label(value: Any) -> str:
    labels = {
        "RISK_ON": "偏多",
        "NEUTRAL": "中性",
        "RISK_OFF": "偏弱",
    }
    return labels.get(str(value), str(value or "未知"))


NOVICE_FEATURE_LABELS = {
    "obv": "買盤有累積進來的跡象",
    "bb_width": "股價波動開始放大，可能要走出一段行情",
    "transactions": "成交筆數增加，代表參與的人變多",
    "avg_volume_10d": "最近成交量比平常熱",
    "avg_value_20d": "最近成交金額夠大，比較不冷門",
    "volume": "成交量有放大",
    "turnover_rate": "股票換手變快，市場比較活躍",
    "rsi": "短線強弱偏正面",
    "macd": "短線動能偏正面",
    "close": "收盤價格表現偏強",
    "ma20": "價格站在近期平均成本上方",
    "pattern_stop_loss": "停損距離還算可控",
}


AI_REASON_LABELS = {
    "obv": "買盤有累積",
    "bb_width": "波動開始打開",
    "transactions": "參與的人變多",
    "avg_volume_10d": "近期量能升溫",
    "avg_value_20d": "成交金額夠大",
    "volume": "成交量放大",
    "turnover_rate": "換手變活躍",
    "rsi": "短線強弱偏正面",
    "macd": "短線動能偏正面",
    "close": "收盤價格強",
    "ma20": "價格站回近期平均成本上方",
    "ma_squeeze": "整理後準備選方向",
    "bias_5": "短線買氣升溫",
    "value": "成交金額放大",
    "pct_from_low_60d": "已從低位墊高",
    "pct_from_low_250d": "中長線位置轉強",
    "pct_from_high_60d": "離近期高點還有修復空間",
    "pct_from_high_250d": "離長期高點仍有修復空間",
    "relative_position_250d": "中長線位置偏強",
}


PROFESSIONAL_FEATURE_LABELS = {
    "obv": "OBV 量價累積",
    "bb_width": "布林帶寬度擴張",
    "transactions": "成交筆數",
    "avg_volume_10d": "10日均量",
    "avg_value_20d": "20日成交值",
    "volume": "成交量",
    "turnover_rate": "週轉率",
    "rsi": "RSI 強弱",
    "macd": "MACD 動能",
    "close": "收盤價",
    "ma20": "月線位置",
    "pattern_stop_loss": "型態停損距離",
}


PROFESSIONAL_SIGNAL_LABELS = {
    "candle_bull_marubozu": "強勢長紅 K 棒",
    "pattern_stop_loss": "型態停損距離合理",
}


PROFESSIONAL_SIGNAL_CONTAINS = [
    ("突破20日", "突破20日新高"),
    ("突破60日", "突破60日新高"),
    ("跳空強勢收紅", "跳空強勢收紅"),
    ("MACD", "MACD 黃金交叉"),
    ("成交量暴增", "成交量暴增"),
    ("紅三兵", "紅三兵"),
    ("錘子線", "錘子線"),
]


THEME_CLUSTER_TAGS = {
    "AI PC",
    "AI伺服器",
    "Apple",
    "Apple watch",
    "Google TPU",
    "HomePod",
    "低軌衛星",
    "台積電",
    "折疊手機",
    "折疊式手機",
    "新基建",
    "智慧音箱",
    "特斯拉",
    "華為",
    "蘋果200大供應商",
    "輝達AI",
    "雲伺服器",
}


STOCK_GROUP_OVERRIDES = {
    "3013": {"sector": "電子相關", "theme": "AI硬體/電腦週邊", "source": "fallback"},
    "3402": {"sector": "電子相關", "theme": "半導體/記憶體", "source": "fallback"},
    "6290": {"sector": "電子相關", "theme": "電子零組件", "source": "fallback"},
    "6442": {"sector": "電子相關", "theme": "光通訊", "source": "fallback"},
    "1618": {"sector": "電線電纜", "theme": "電線電纜", "source": "fallback"},
    "2369": {"sector": "電子相關", "theme": "半導體/記憶體", "source": "fallback"},
    "2344": {"sector": "電子相關", "theme": "半導體/記憶體", "source": "fallback"},
    "2731": {"sector": "觀光旅遊", "theme": "旅遊服務", "source": "fallback"},
    "2606": {"sector": "航運", "theme": "海運", "source": "fallback"},
    "3211": {"sector": "電子相關", "theme": "AI硬體/電腦週邊", "source": "fallback"},
}


def number_value(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return parsed


def integer_value(value: Any) -> int | None:
    parsed = number_value(value)
    if parsed is None:
        return None
    return int(parsed)


def num(value: Any) -> str:
    parsed = number_value(value)
    return "--" if parsed is None else f"{parsed:.2f}"


def pct(value: Any) -> str:
    parsed = number_value(value)
    return "--" if parsed is None else f"{parsed * 100:.1f}%"


if __name__ == "__main__":
    raise SystemExit(main())
