#!/usr/bin/env python3
"""產生可外送給外部 reviewer 的每日事後檢討 packet。"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "external-review-packet.v1"
MANIFEST_SCHEMA_VERSION = "external-review-packet-manifest.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="產生 safe external review packet")
    parser.add_argument("--date", required=True, help="ranking 日期，格式 YYYY-MM-DD")
    parser.add_argument("--artifacts-dir", default="artifacts")
    parser.add_argument("--features", default="data/clean/features.parquet")
    args = parser.parse_args()

    artifacts_dir = PROJECT_ROOT / args.artifacts_dir
    packet = build_packet(
        packet_date=args.date,
        ranking_path=artifacts_dir / f"ranking_{args.date}.csv",
        daily_report_path=artifacts_dir / f"daily_report_{args.date}.json",
        daily_report_md_path=artifacts_dir / f"daily_report_{args.date}.md",
        features_path=PROJECT_ROOT / args.features,
    )

    out_dir = artifacts_dir / "external_review" / args.date
    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / f"review_packet_{args.date}.json"
    md_path = out_dir / f"review_packet_{args.date}.md"
    manifest_path = out_dir / f"review_packet_manifest_{args.date}.json"
    manifest = build_manifest(
        packet_date=args.date,
        packet_path=json_path,
        markdown_path=md_path,
        ranking_path=artifacts_dir / f"ranking_{args.date}.csv",
        daily_report_path=artifacts_dir / f"daily_report_{args.date}.json",
        daily_report_md_path=artifacts_dir / f"daily_report_{args.date}.md",
        features_path=PROJECT_ROOT / args.features,
    )
    json_path.write_text(json.dumps(packet, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(packet), encoding="utf-8")
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"EXTERNAL_REVIEW_PACKET_OK json={json_path} md={md_path} manifest={manifest_path}")
    return 0


def build_packet(
    packet_date: str,
    ranking_path: Path,
    daily_report_path: Path,
    daily_report_md_path: Path,
    features_path: Path,
) -> dict[str, Any]:
    if not ranking_path.exists():
        raise FileNotFoundError(f"ranking 不存在：{ranking_path}")
    if not daily_report_path.exists():
        raise FileNotFoundError(f"daily report JSON 不存在：{daily_report_path}")

    report = json.loads(daily_report_path.read_text(encoding="utf-8"))
    ranking = pd.read_csv(ranking_path)
    ohlc_by_stock = load_public_ohlc(features_path, packet_date)
    ranking_by_stock = {
        normalize_stock_id(row.get("stock_id")): row
        for _, row in ranking.iterrows()
        if normalize_stock_id(row.get("stock_id"))
    }

    top10 = report.get("top10") or []
    recommendations = [
        recommendation_from_item(item, ranking_by_stock.get(str(item.get("stock_id", "")).zfill(4)), ohlc_by_stock)
        for item in top10
    ]

    summary = report.get("summary", {})
    risk = report.get("risk", {})

    return {
        "schema_version": SCHEMA_VERSION,
        "sendable": True,
        "packet_date": packet_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "market": "TW",
        "purpose": "post_daily_external_review",
        "safety_boundary": {
            "allowed": [
                "公開推薦名單",
                "公開交易計畫摘要",
                "公開產業/概念標籤",
                "公開 OHLC/成交量摘要",
                "daily report 市場摘要",
            ],
            "prohibited": [
                "演算法",
                "權重",
                "feature engineering",
                "訓練資料結構",
                "模型程式碼",
                "內部 scoring formula",
                "promotion gate internals",
            ],
        },
        "market_overview": {
            "market_regime": summary.get("market_regime"),
            "top_count": summary.get("top_count"),
            "gross_exposure": summary.get("gross_exposure"),
            "allocated_exposure": summary.get("allocated_exposure"),
            "cash_weight": summary.get("cash_weight"),
            "risk_notes": risk.get("notes", []),
        },
        "outcome_status": {
            "same_day_ohlc_available": any(item.get("same_day_market") for item in recommendations),
            "next_session_outcome_available": False,
            "note": "本 packet 僅包含本地已存在的同日公開行情；若尚未有下一交易日資料，不產生事後漲跌結論。",
        },
        "recommendations": recommendations,
        "reviewer_instructions": {
            "role": "專業台股操盤手",
            "task": "只根據 packet 內容檢討今日推薦品質、風險、族群資金流與可驗證研究假設。",
            "response_contract": "external-review.v1",
            "must_not_request_algorithm": True,
        },
    }


def build_manifest(
    packet_date: str,
    packet_path: Path,
    markdown_path: Path,
    ranking_path: Path,
    daily_report_path: Path,
    daily_report_md_path: Path,
    features_path: Path,
) -> dict[str, Any]:
    return {
        "schema_version": MANIFEST_SCHEMA_VERSION,
        "packet_date": packet_date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "sendable_packet": repo_relative(packet_path),
        "sendable_markdown": repo_relative(markdown_path),
        "local_only": True,
        "lineage": {
            "ranking": repo_relative(ranking_path),
            "daily_report_json": repo_relative(daily_report_path),
            "daily_report_md": repo_relative(daily_report_md_path) if daily_report_md_path.exists() else None,
            "features_ohlc": repo_relative(features_path) if features_path.exists() else None,
        },
        "safety_boundary": {
            "sendable_packet_must_not_include_lineage": True,
            "manifest_must_stay_local": True,
        },
    }


def load_public_ohlc(features_path: Path, packet_date: str) -> dict[str, dict[str, Any]]:
    if not features_path.exists():
        return {}
    frame = pd.read_parquet(features_path)
    if "date" not in frame.columns or "stock_id" not in frame.columns:
        return {}
    dates = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    daily = frame[dates == packet_date].copy()
    if daily.empty:
        return {}
    result: dict[str, dict[str, Any]] = {}
    for _, row in daily.iterrows():
        stock_id = normalize_stock_id(row.get("stock_id"))
        if not stock_id:
            continue
        result[stock_id] = {
            "date": packet_date,
            "open": number_value(row.get("open")),
            "high": number_value(row.get("high")),
            "low": number_value(row.get("low")),
            "close": number_value(row.get("close")),
            "volume": number_value(row.get("volume")),
            "value": number_value(row.get("value")),
            "transactions": number_value(row.get("transactions")),
            "intraday_change_pct": pct_change(row.get("open"), row.get("close")),
        }
    return result


def recommendation_from_item(
    item: dict[str, Any],
    ranking_row: pd.Series | None,
    ohlc_by_stock: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    stock_id = str(item.get("stock_id", "")).zfill(4)
    reference = item.get("reference", {}) if isinstance(item.get("reference"), dict) else {}
    trade_plan = item.get("trade_plan", {}) if isinstance(item.get("trade_plan"), dict) else {}
    persistence = item.get("persistence", {}) if isinstance(item.get("persistence"), dict) else {}
    raw_reasons = item.get("reasons")
    if not raw_reasons and ranking_row is not None:
        raw_reasons = clean_reason_text(ranking_row.get("reasons"))

    return {
        "rank": item.get("rank"),
        "stock_id": stock_id,
        "stock_name": string_value(item.get("stock_name")),
        "close": number_value(item.get("close")),
        "market_regime": string_value(item.get("market_regime")),
        "reference": {
            "industry_name": string_value(reference.get("industry_name")),
            "sector_name": string_value(reference.get("sector_name")),
            "market_type": string_value(reference.get("market_type")),
            "theme_tags": string_list(reference.get("theme_tags")),
            "concept_tags": string_list(reference.get("concept_tags")),
            "major_etfs": string_list(reference.get("major_etfs")),
        },
        "trade_plan": {
            "entry": number_value(trade_plan.get("entry")),
            "stop_loss": number_value(trade_plan.get("stop_loss")),
            "target_price": number_value(trade_plan.get("target_price")),
            "risk_reward": number_value(trade_plan.get("risk_reward")),
        },
        "persistence": {
            "available": bool(persistence.get("available")),
            "consecutive_ranked_days": int_value(persistence.get("consecutive_ranked_days")),
            "previous_rank": int_value(persistence.get("previous_rank")),
            "rank_delta": int_value(persistence.get("rank_delta")),
        },
        "public_reasons": sanitize_reasons(raw_reasons),
        "same_day_market": ohlc_by_stock.get(stock_id),
        "observed_outcome": {
            "available": False,
            "horizon": "next_session",
            "note": "下一交易日結果尚未由本 slice 推導。",
        },
    }


def sanitize_reasons(value: Any) -> list[str]:
    if isinstance(value, list):
        parts = [string_value(item) for item in value]
    else:
        parts = clean_reason_text(value)
    safe: list[str] = []
    for part in parts:
        text = re.split(r"\|\s*AI\s*:", part, maxsplit=1)[0]
        text = re.sub(r"\bAI\s*:\s*.*$", "", text).strip(" -•\n")
        if not text:
            continue
        if looks_like_internal_feature(text):
            continue
        safe.append(text)
    return safe[:8]


def looks_like_internal_feature(text: str) -> bool:
    if "AI:" in text or "SHAP" in text.upper():
        return True
    if re.search(r"\b[a-z][a-z0-9]*_[a-z0-9_]+\b", text) and not re.search(r"[\u4e00-\u9fff]", text):
        return True
    return False


def clean_reason_text(value: Any) -> list[str]:
    text = string_value(value)
    if not text:
        return []
    cleaned = re.sub(r"\*\*[^*]+\*\*", "", text)
    return [part.strip(" -•\n") for part in re.split(r"\n+| \| ", cleaned) if part.strip(" -•\n")]


def render_markdown(packet: dict[str, Any]) -> str:
    overview = packet["market_overview"]
    lines = [
        f"# External Review Packet｜{packet['packet_date']}",
        "",
        "## 邊界",
        "",
        "- 只提供公開推薦名單、交易計畫摘要、產業/概念標籤與公開行情。",
        "- 不提供演算法、權重、feature engineering、模型程式碼或內部 scoring formula。",
        "- reviewer 必須回覆 `external-review.v1` JSON。",
        "",
        "## 市場摘要",
        "",
        f"- 市場狀態：{overview.get('market_regime') or 'UNKNOWN'}",
        f"- Top count：{overview.get('top_count')}",
        f"- 目標曝險：{pct_text(overview.get('gross_exposure'))}",
        f"- 已配置：{pct_text(overview.get('allocated_exposure'))}",
        f"- 現金：{pct_text(overview.get('cash_weight'))}",
        "",
        "## 推薦名單",
        "",
        "| Rank | 代號 | 股票 | 產業 | 收盤 | 進場 | 停損 | 目標 | RR | 公開理由 |",
        "|---:|---|---|---|---:|---:|---:|---:|---:|---|",
    ]
    for item in packet["recommendations"]:
        reference = item.get("reference", {})
        trade = item.get("trade_plan", {})
        reasons = "；".join(item.get("public_reasons") or [])
        lines.append(
            "| {rank} | {stock_id} | {stock_name} | {industry} | {close} | {entry} | {stop} | {target} | {rr} | {reasons} |".format(
                rank=item.get("rank"),
                stock_id=item.get("stock_id"),
                stock_name=item.get("stock_name"),
                industry=reference.get("industry_name") or "--",
                close=num_text(item.get("close")),
                entry=num_text(trade.get("entry")),
                stop=num_text(trade.get("stop_loss")),
                target=num_text(trade.get("target_price")),
                rr=num_text(trade.get("risk_reward")),
                reasons=reasons or "--",
            )
        )
    lines.extend(["", "## Outcome 狀態", "", f"- {packet['outcome_status']['note']}", ""])
    return "\n".join(lines)


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def normalize_stock_id(value: Any) -> str:
    text = string_value(value).lstrip("\ufeff")
    if not text:
        return ""
    return text.zfill(4)


def number_value(value: Any) -> float | None:
    if value is None:
        return None
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(parsed):
        return None
    return round(parsed, 4)


def int_value(value: Any) -> int | None:
    if value is None:
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed


def pct_change(start: Any, end: Any) -> float | None:
    start_num = number_value(start)
    end_num = number_value(end)
    if start_num in (None, 0) or end_num is None:
        return None
    return round((end_num - start_num) / start_num, 4)


def string_value(value: Any) -> str:
    if value is None:
        return ""
    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass
    return str(value).strip()


def string_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [string_value(item) for item in value if string_value(item)]
    text = string_value(value)
    if not text:
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def num_text(value: Any) -> str:
    parsed = number_value(value)
    return "--" if parsed is None else f"{parsed:.2f}"


def pct_text(value: Any) -> str:
    parsed = number_value(value)
    return "--" if parsed is None else f"{parsed * 100:.1f}%"


if __name__ == "__main__":
    raise SystemExit(main())
