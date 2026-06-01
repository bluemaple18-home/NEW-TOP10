#!/usr/bin/env python3
"""從 ranking artifact 產出每日決策日報。

此腳本只讀既有 CSV / JSON artifact，不重新計算 ranking、不中途觸發 API 或回測。
"""

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
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.data.reference_repository import ReferenceRepository  # noqa: E402

REPORT_SCHEMA_VERSION = "daily-decision-report.v1"


def main() -> int:
    parser = argparse.ArgumentParser(description="generate daily Top10 decision report")
    parser.add_argument("--date", default=None, help="ranking 日期，格式 YYYY-MM-DD；未指定時使用 automation_status 或最新 ranking")
    parser.add_argument("--ranking", default=None, help="指定 ranking CSV 路徑")
    parser.add_argument("--status", default="artifacts/automation_status.json", help="automation status JSON")
    parser.add_argument("--artifacts-dir", default="artifacts")
    args = parser.parse_args()

    artifacts_dir = PROJECT_ROOT / args.artifacts_dir
    status = load_json(PROJECT_ROOT / args.status)
    ranking_path = resolve_ranking_path(artifacts_dir=artifacts_dir, status=status, date=args.date, ranking=args.ranking)
    ranking_date = date_from_ranking_path(ranking_path)
    frame = pd.read_csv(ranking_path)
    frame = ReferenceRepository(PROJECT_ROOT).annotate_ranking(frame)
    persistence = load_persistence(artifacts_dir / f"candidate_persistence_{ranking_date}.json")
    ledger_stats = load_latest_ledger_stats(artifacts_dir, ranking_date)
    report = build_report(
        frame=frame,
        ranking_path=ranking_path,
        ranking_date=ranking_date,
        status=status,
        persistence=persistence,
        ledger_stats=ledger_stats,
    )

    json_path = artifacts_dir / f"daily_report_{ranking_date}.json"
    md_path = artifacts_dir / f"daily_report_{ranking_date}.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(render_markdown(report), encoding="utf-8")
    print(f"DAILY_REPORT_OK json={json_path} md={md_path}")
    return 0


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def load_persistence(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return {
        str(item.get("stock_id", "")).zfill(4): item
        for item in payload.get("items", [])
        if item.get("stock_id")
    }


def load_latest_ledger_stats(artifacts_dir: Path, ranking_date: str) -> dict[str, Any]:
    model_dir = artifacts_dir / "model_experiments"
    preferred = model_dir / f"model_experiment_ledger_stats_{ranking_date}.json"
    if preferred.exists():
        return load_json(preferred)
    matches = sorted(model_dir.glob("model_experiment_ledger_stats_????-??-??.json"))
    return load_json(matches[-1]) if matches else {}


def resolve_ranking_path(artifacts_dir: Path, status: dict[str, Any], date: str | None, ranking: str | None) -> Path:
    if ranking:
        path = PROJECT_ROOT / ranking
        if path.exists():
            return path
        raise FileNotFoundError(f"指定 ranking 不存在：{path}")

    if date:
        path = artifacts_dir / f"ranking_{date}.csv"
        if path.exists():
            return path
        raise FileNotFoundError(f"指定日期 ranking 不存在：{path}")

    status_path = status.get("metadata", {}).get("ranking_artifact")
    if status_path and Path(status_path).exists():
        return Path(status_path)

    files = sorted(artifacts_dir.glob("ranking_*.csv"))
    if not files:
        raise FileNotFoundError("找不到 ranking_*.csv")
    return files[-1]


def date_from_ranking_path(path: Path) -> str:
    match = re.search(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking 檔名無法解析日期：{path}")
    return match.group(1)


def build_report(
    frame: pd.DataFrame,
    ranking_path: Path,
    ranking_date: str,
    status: dict[str, Any],
    persistence: dict[str, Any] | None = None,
    ledger_stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    top = frame.head(10).copy()
    persistence = persistence or {}
    items = [item_from_row(index + 1, row, persistence) for index, (_, row) in enumerate(top.iterrows())]
    score_columns = ["risk_adjusted_score", "prediction_score", "setup_score", "quality_score", "risk_penalty"]
    missing_columns = [column for column in score_columns if column not in frame.columns]
    coverage = coverage_summary(frame)
    risk = risk_summary(frame, status)
    ledger_summary = (ledger_stats or {}).get("summary", {})

    return {
        "schema_version": REPORT_SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "ranking_date": ranking_date,
        "ranking_artifact": str(ranking_path),
        "automation_status": {
            "status": status.get("status"),
            "run_date": status.get("run_date"),
            "skip_reason": status.get("skip_reason"),
            "data_freshness": status.get("metadata", {}).get("data_freshness"),
        },
        "summary": {
            "top_count": len(items),
            "market_regime": most_common_value(frame, "market_regime"),
            "gross_exposure": first_number(frame, "gross_exposure"),
            "allocated_exposure": first_number(frame, "allocated_exposure"),
            "cash_weight": first_number(frame, "cash_weight"),
            "missing_score_columns": missing_columns,
        },
        "coverage": coverage,
        "risk": risk,
        "persistence": {
            "available": bool(persistence),
            "source": f"candidate_persistence_{ranking_date}.json" if persistence else None,
            "scope": "decision_annotation_only",
            "model_feature": False,
        },
        "model_governance": {
            "available": bool(ledger_summary),
            "source": (ledger_stats or {}).get("ledger"),
            "pending_due_soon": ledger_summary.get("pending_due_soon", [])[:5],
            "failed_partial_since_last_run": ledger_summary.get("failed_partial_since_last_run", [])[:5],
            "blocked_promotion_reasons": ledger_summary.get("blocked_promotion_reasons", []),
        },
        "top10": items,
    }


def item_from_row(rank: int, row: pd.Series, persistence: dict[str, Any] | None = None) -> dict[str, Any]:
    reasons = clean_reason_text(row.get("reasons"))
    trade_plan = trade_plan_from_row(row)
    stock_id = str(row.get("stock_id", "")).zfill(4)
    return {
        "rank": rank,
        "stock_id": stock_id,
        "stock_name": string_value(row.get("stock_name")),
        "close": number_value(row.get("close")),
        "scores": {
            "risk_adjusted_score": number_value(row.get("risk_adjusted_score")),
            "final_score": number_value(row.get("final_score")),
            "model_prob": number_value(row.get("model_prob")),
            "rule_score": number_value(row.get("rule_score")),
            "prediction_score": number_value(row.get("prediction_score")),
            "setup_score": number_value(row.get("setup_score")),
            "quality_score": number_value(row.get("quality_score")),
            "risk_penalty": number_value(row.get("risk_penalty")),
        },
        "position": {
            "suggested_weight": number_value(row.get("suggested_weight")),
            "max_position_weight": number_value(row.get("max_position_weight")),
            "gross_exposure": number_value(row.get("gross_exposure")),
            "allocated_exposure": number_value(row.get("allocated_exposure")),
            "cash_weight": number_value(row.get("cash_weight")),
            "exposure_note": string_value(row.get("exposure_note")),
        },
        "reference": reference_from_row(row),
        "trade_plan": trade_plan,
        "persistence": persistence_item(stock_id, persistence or {}),
        "market_regime": string_value(row.get("market_regime")),
        "reasons": reasons,
    }


def persistence_item(stock_id: str, persistence: dict[str, Any]) -> dict[str, Any]:
    item = persistence.get(stock_id)
    if not item:
        return {"available": False}
    return {
        "available": True,
        "first_seen_date": item.get("first_seen_date"),
        "consecutive_ranked_days": item.get("consecutive_ranked_days"),
        "ranked_history_count": item.get("ranked_history_count"),
        "previous_rank": item.get("previous_rank"),
        "rank_delta": item.get("rank_delta"),
    }


def reference_from_row(row: pd.Series) -> dict[str, Any]:
    return {
        "industry_code": string_value(row.get("industry_code")),
        "industry_name": string_value(row.get("industry_name")),
        "sector_name": string_value(row.get("sector_name")),
        "market_type": string_value(row.get("market_type")),
        "theme_tags": split_tags(row.get("theme_tags")),
        "concept_tags": split_tags(row.get("concept_tags")),
        "major_etfs": split_tags(row.get("major_etfs")),
    }


def trade_plan_from_row(row: pd.Series) -> dict[str, Any]:
    text = string_value(row.get("reasons"))
    entry = extract_number(text, r"進場[：:]\s*([0-9]+(?:\.[0-9]+)?)")
    stop = extract_number(text, r"止損[：:]\s*([0-9]+(?:\.[0-9]+)?)")
    target = extract_number(text, r"目標[：:]\s*([0-9]+(?:\.[0-9]+)?)")
    return {
        "entry": entry,
        "stop_loss": stop,
        "target_price": target,
        "risk_reward": number_value(row.get("risk_reward")),
        "source": "ranking_reasons" if any(value is not None for value in [entry, stop, target]) else "unavailable",
    }


def coverage_summary(frame: pd.DataFrame) -> dict[str, Any]:
    fields = [
        "risk_adjusted_score",
        "model_prob",
        "prediction_score",
        "setup_score",
        "quality_score",
        "risk_penalty",
        "suggested_weight",
        "risk_reward",
        "reasons",
    ]
    return {
        "ranking_rows": int(len(frame)),
        "field_coverage": {
            field: round(float(frame[field].notna().mean()), 4) if field in frame.columns and len(frame) else 0.0
            for field in fields
        },
        "missing_fields": [field for field in fields if field not in frame.columns],
    }


def risk_summary(frame: pd.DataFrame, status: dict[str, Any]) -> dict[str, Any]:
    risk_penalty = pd.to_numeric(frame.get("risk_penalty"), errors="coerce") if "risk_penalty" in frame.columns else pd.Series(dtype=float)
    risk_reward = pd.to_numeric(frame.get("risk_reward"), errors="coerce") if "risk_reward" in frame.columns else pd.Series(dtype=float)
    freshness = status.get("metadata", {}).get("data_freshness", {})
    return {
        "market_regime": most_common_value(frame, "market_regime"),
        "max_risk_penalty": number_value(risk_penalty.max()) if len(risk_penalty) else None,
        "low_risk_reward_count": int((risk_reward < 1.5).sum()) if len(risk_reward) else None,
        "data_freshness": freshness,
        "notes": risk_notes(frame, freshness),
    }


def risk_notes(frame: pd.DataFrame, freshness: dict[str, Any]) -> list[str]:
    notes: list[str] = []
    if "risk_penalty" in frame.columns and pd.to_numeric(frame["risk_penalty"], errors="coerce").fillna(0).max() > 0:
        notes.append("Top10 內有風險扣分，需看停損與部位上限。")
    max_lag = freshness.get("max_lag_days")
    datasets = freshness.get("datasets", {})
    stale = [
        f"{name} lag={info.get('lag_days')}"
        for name, info in datasets.items()
        if max_lag is not None and info.get("lag_days", 0) > max_lag
    ]
    if stale:
        notes.append(f"資料 freshness 超過門檻：{'; '.join(stale)}")
    if not notes:
        notes.append("未偵測到額外阻塞風險；仍需依交易計畫控管部位。")
    return notes


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        f"# Daily Top10 決策日報｜{report['ranking_date']}",
        "",
        f"- 狀態：{report['automation_status'].get('status') or 'UNKNOWN'}",
        f"- Ranking artifact：`{report['ranking_artifact']}`",
        f"- 市場狀態：{summary.get('market_regime') or 'UNKNOWN'}",
        f"- 目標曝險：{pct(summary.get('gross_exposure'))}；已配置：{pct(summary.get('allocated_exposure'))}；現金：{pct(summary.get('cash_weight'))}",
        "",
        "## Top10",
        "",
        "| Rank | 股票 | 入榜 | 勝率 | 風險調整 | Setup | Quality | Risk | 權重 | 進場 / 停損 / 目標 |",
        "|---:|---|---:|---:|---:|---:|---:|---:|---:|---|",
    ]
    for item in report["top10"]:
        trade = item["trade_plan"]
        lines.append(
            "| {rank} | {stock_id} {stock_name} | {streak} | {model_prob} | {risk_adjusted} | {setup} | {quality} | {risk} | {weight} | {entry} / {stop} / {target} |".format(
                rank=item["rank"],
                stock_id=item["stock_id"],
                stock_name=item["stock_name"],
                streak=streak_label(item.get("persistence", {})),
                model_prob=pct(item["scores"].get("model_prob")),
                risk_adjusted=num(item["scores"].get("risk_adjusted_score")),
                setup=num(item["scores"].get("setup_score")),
                quality=num(item["scores"].get("quality_score")),
                risk=num(item["scores"].get("risk_penalty")),
                weight=pct(item["position"].get("suggested_weight")),
                entry=num(trade.get("entry")),
                stop=num(trade.get("stop_loss")),
                target=num(trade.get("target_price")),
            )
        )

    lines.extend(["", "## Coverage", ""])
    for field, value in report["coverage"]["field_coverage"].items():
        lines.append(f"- `{field}`：{value:.1%}")
    if report["coverage"]["missing_fields"]:
        lines.append(f"- 缺欄位：{', '.join(report['coverage']['missing_fields'])}")

    lines.extend(["", "## 風險與缺資料摘要", ""])
    for note in report["risk"]["notes"]:
        lines.append(f"- {note}")
    freshness = report["risk"].get("data_freshness", {}).get("datasets", {})
    for name, info in freshness.items():
        lines.append(f"- `{name}` latest={info.get('latest_date')} lag_days={info.get('lag_days')} rows={info.get('rows')}")
    governance = report.get("model_governance", {})
    lines.extend(["", "## Model Governance", ""])
    if not governance.get("available"):
        lines.append("- ledger stats unavailable")
    else:
        lines.append(f"- blocked promotion reasons：`{governance.get('blocked_promotion_reasons', [])}`")
        for item in governance.get("pending_due_soon", []):
            lines.append(f"- due soon：`{item.get('id')}` trigger={item.get('trigger_date')} action={item.get('next_action')}")
        for item in governance.get("failed_partial_since_last_run", []):
            lines.append(f"- {item.get('status')}：`{item.get('id')}` reason={item.get('reason')}")
    lines.append("")
    return "\n".join(lines)


def streak_label(persistence: dict[str, Any]) -> str:
    if not persistence.get("available"):
        return "--"
    days = persistence.get("consecutive_ranked_days")
    delta = persistence.get("rank_delta")
    delta_text = ""
    if delta is not None:
        delta_text = f" ({'+' if delta > 0 else ''}{delta})"
    return f"{days}天{delta_text}" if days is not None else "--"


def clean_reason_text(value: Any) -> list[str]:
    text = string_value(value)
    if not text:
        return []
    cleaned = re.sub(r"\*\*[^*]+\*\*", "", text)
    parts = [part.strip(" -•\n") for part in re.split(r"\n+| \| ", cleaned) if part.strip(" -•\n")]
    return parts[:8]


def extract_number(text: str, pattern: str) -> float | None:
    match = re.search(pattern, text)
    return float(match.group(1)) if match else None


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


def first_number(frame: pd.DataFrame, column: str) -> float | None:
    if column not in frame.columns or frame.empty:
        return None
    return number_value(frame[column].iloc[0])


def most_common_value(frame: pd.DataFrame, column: str) -> str | None:
    if column not in frame.columns or frame.empty:
        return None
    values = frame[column].dropna().astype(str)
    if values.empty:
        return None
    return values.mode().iloc[0]


def string_value(value: Any) -> str:
    if value is None or pd.isna(value):
        return ""
    return str(value).strip()


def split_tags(value: Any) -> list[str]:
    text = string_value(value)
    if not text:
        return []
    return [tag.strip() for tag in text.split("|") if tag.strip()]


def num(value: Any) -> str:
    parsed = number_value(value)
    return "--" if parsed is None else f"{parsed:.2f}"


def pct(value: Any) -> str:
    parsed = number_value(value)
    return "--" if parsed is None else f"{parsed * 100:.1f}%"


if __name__ == "__main__":
    raise SystemExit(main())
