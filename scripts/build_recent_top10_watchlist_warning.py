#!/usr/bin/env python3
"""建立近 7 個 Top10 ranking 日的非個人化風險提醒。

此腳本只讀既有 ranking artifacts 與 features parquet，不重跑 ETL、不重排 ranking、
不發送推播。用途是把「最近曾進 Top10 的股票」整理成 Phase 1 可用的觀察清單，
避免把每日推薦訊息誤當成個人持倉提醒。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
OUTPUT_DIR = ARTIFACTS_DIR / "model_experiments"
SCHEMA_VERSION = "recent-top10-watchlist-warning.v1"
BLOCKED_MESSAGE_TERMS = ("賣出", "停損", "全賣", "出場", "減碼")
SIGNAL_LABELS = {
    "recently_dropped_from_top10": "掉出最新 Top10",
    "rank_worsened": "排名明顯退步",
    "close_below_ma20": "跌到月線下方",
    "close_below_ma10": "跌破短線均線",
    "close_below_ma5": "跌破 5 日線",
    "long_upper_shadow": "上攻後被壓回",
    "risk_penalty_elevated": "風險扣分偏高",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build recent Top10 watchlist warning artifact")
    parser.add_argument("--rankings-dir", default="artifacts", help="ranking_*.csv 所在目錄")
    parser.add_argument("--features", default="data/clean/features.parquet", help="features parquet")
    parser.add_argument("--target-date", default=None, help="目標 ranking 日期；未指定時使用最新 ranking")
    parser.add_argument("--watchlist-ranking-days", type=int, default=7, help="納入最近 N 個 ranking 日")
    parser.add_argument("--top-n", type=int, default=10, help="每份 ranking 取前 N 檔")
    parser.add_argument("--output", default=None, help="輸出 JSON")
    parser.add_argument("--markdown-output", default=None, help="輸出 Markdown")
    return parser.parse_args()


def resolve_path(value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def ranking_date(path: Path) -> str:
    match = re.match(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$", path.name)
    if not match:
        raise ValueError(f"ranking 檔名無法解析日期：{path}")
    return match.group(1)


def ranking_files(rankings_dir: Path) -> list[Path]:
    files = sorted(
        [path for path in rankings_dir.glob("ranking_*.csv") if re.match(r"ranking_\d{4}-\d{2}-\d{2}\.csv$", path.name)],
        key=lambda path: ranking_date(path),
    )
    if not files:
        raise FileNotFoundError(f"找不到 ranking_*.csv：{rankings_dir}")
    return files


def select_window(files: list[Path], target_date: str | None, days: int) -> list[Path]:
    if days < 2:
        raise ValueError("watchlist-ranking-days must be >= 2")
    if target_date is None:
        target_index = len(files) - 1
    else:
        matches = [index for index, path in enumerate(files) if ranking_date(path) == target_date]
        if not matches:
            raise FileNotFoundError(f"找不到目標 ranking 日期：{target_date}")
        target_index = matches[-1]
    start_index = max(0, target_index - days + 1)
    return files[start_index : target_index + 1]


def parse_float(value: Any) -> float | None:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return None
    return None if pd.isna(parsed) else parsed


def parse_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    text = str(value).strip().lower()
    return text in {"1", "true", "yes", "y"}


def read_ranking(path: Path, top_n: int) -> list[dict[str, Any]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    result = []
    for rank, row in enumerate(rows[:top_n], start=1):
        stock_id = str(row.get("stock_id", "")).strip().zfill(4)
        result.append(
            {
                "date": ranking_date(path),
                "rank": rank,
                "stock_id": stock_id,
                "stock_name": row.get("stock_name"),
                "risk_adjusted_score": parse_float(row.get("risk_adjusted_score")),
                "model_prob": parse_float(row.get("model_prob")),
                "quality_score": parse_float(row.get("quality_score")),
                "risk_penalty": parse_float(row.get("risk_penalty")),
                "market_regime": row.get("market_regime"),
                "close": parse_float(row.get("close")),
            }
        )
    return result


def load_latest_feature_rows(path: Path, target_date: str) -> dict[str, dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(f"features parquet 不存在：{path}")
    frame = pd.read_parquet(path)
    date_column = "trade_date" if "trade_date" in frame.columns else "date"
    if date_column not in frame.columns:
        raise RuntimeError("features parquet 缺少 date/trade_date 欄位")
    frame["stock_id"] = frame["stock_id"].astype(str).str.zfill(4)
    frame[date_column] = pd.to_datetime(frame[date_column]).dt.date
    target_value = datetime.fromisoformat(target_date).date()
    frame = frame[frame[date_column] <= target_value].sort_values(["stock_id", date_column])
    latest = frame.groupby("stock_id", sort=False).tail(1)
    return {str(row["stock_id"]).zfill(4): row.to_dict() for _, row in latest.iterrows()}


def pct(value: float | None) -> float | None:
    return None if value is None else round(float(value), 4)


def feature_float(row: dict[str, Any] | None, key: str) -> float | None:
    if not row:
        return None
    return parse_float(row.get(key))


def feature_bool(row: dict[str, Any] | None, key: str) -> bool:
    if not row:
        return False
    return parse_bool(row.get(key))


def build_stock_item(stock_id: str, history: list[dict[str, Any]], latest_by_stock: dict[str, dict[str, Any]], target_date: str) -> dict[str, Any]:
    latest_feature = latest_by_stock.get(stock_id)
    latest_ranking = next((row for row in reversed(history) if row["date"] == target_date), None)
    latest_seen = history[-1]
    first_seen = history[0]
    latest_close = feature_float(latest_feature, "close")
    if latest_close is None and latest_ranking:
        latest_close = latest_ranking.get("close")
    ma5 = feature_float(latest_feature, "ma5")
    ma10 = feature_float(latest_feature, "ma10")
    ma20 = feature_float(latest_feature, "ma20")
    risk_penalty = latest_ranking.get("risk_penalty") if latest_ranking else None
    latest_rank = latest_ranking["rank"] if latest_ranking else None
    previous_rank = history[-2]["rank"] if len(history) >= 2 and history[-2]["date"] != target_date else None
    rank_delta = previous_rank - latest_rank if previous_rank is not None and latest_rank is not None else None
    is_latest_top10 = latest_ranking is not None
    dropped_from_top10 = not is_latest_top10 and latest_seen["date"] != target_date

    signals: list[str] = []
    plain_notes: list[str] = []

    if dropped_from_top10:
        signals.append("recently_dropped_from_top10")
        plain_notes.append("最近曾入榜，但最新榜單已經沒有它，代表短線熱度退下來。")
    if rank_delta is not None and rank_delta <= -4:
        signals.append("rank_worsened")
        plain_notes.append("排名明顯往後，資金追捧力道沒有前幾天強。")
    if latest_close is not None and ma20 is not None and latest_close < ma20:
        signals.append("close_below_ma20")
        plain_notes.append("收盤跌到月線下方，走勢已經偏弱。")
    elif latest_close is not None and ma10 is not None and latest_close < ma10:
        signals.append("close_below_ma10")
        plain_notes.append("收盤跌破短線均線，短線追價要先冷靜。")
    elif latest_close is not None and ma5 is not None and latest_close < ma5:
        signals.append("close_below_ma5")
        plain_notes.append("收盤跌破 5 日線，短線動能開始降溫。")
    if feature_bool(latest_feature, "long_upper_shadow"):
        signals.append("long_upper_shadow")
        plain_notes.append("盤中上攻後被壓回，代表上方賣壓有出現。")
    if risk_penalty is not None and risk_penalty >= 0.35:
        signals.append("risk_penalty_elevated")
        plain_notes.append("最新 ranking 風險扣分偏高，追價條件不乾淨。")

    if ("close_below_ma20" in signals and dropped_from_top10) or "risk_penalty_elevated" in signals:
        level = "RISK_ALERT"
        conclusion = "⚠️ 轉弱風險升高"
    elif signals:
        level = "WEAKENING"
        conclusion = "🟡 動能降溫，先觀察"
    else:
        level = "WATCH"
        conclusion = "🟢 仍在觀察清單"

    if not plain_notes:
        plain_notes.append("最近仍有資金關注，暫時沒有明顯轉弱訊號。")

    holder_note = "未進場者先不要急著追；已持有者請檢查自己的成本與風險線。"
    if level == "WATCH":
        holder_note = "這類股票適合放在觀察清單，等價格和量能一起確認。"

    return {
        "stock_id": stock_id,
        "stock_name": latest_seen.get("stock_name"),
        "warning_level": level,
        "conclusion": conclusion,
        "latest_in_top10": is_latest_top10,
        "days_seen_in_window": len({row["date"] for row in history}),
        "first_seen_date": first_seen["date"],
        "last_seen_date": latest_seen["date"],
        "latest_rank": latest_rank,
        "previous_rank": previous_rank,
        "rank_delta": rank_delta,
        "dropped_from_top10": dropped_from_top10,
        "signals": signals,
        "plain_notes": plain_notes[:3],
        "holder_note": holder_note,
        "latest_price_context": {
            "date": str(latest_feature.get("date") or latest_feature.get("trade_date")) if latest_feature else None,
            "close": pct(latest_close),
            "ma5": pct(ma5),
            "ma10": pct(ma10),
            "ma20": pct(ma20),
            "long_upper_shadow": feature_bool(latest_feature, "long_upper_shadow"),
            "risk_penalty": pct(risk_penalty),
        },
        "history": [{"date": row["date"], "rank": row["rank"]} for row in history],
    }


def build_payload(rankings_dir: Path, features_path: Path, target_date: str | None, watchlist_days: int, top_n: int) -> dict[str, Any]:
    files = ranking_files(rankings_dir)
    window = select_window(files, target_date=target_date, days=watchlist_days)
    actual_target_date = ranking_date(window[-1])
    latest_by_stock = load_latest_feature_rows(features_path, actual_target_date)

    history_by_stock: dict[str, list[dict[str, Any]]] = {}
    all_rows: list[dict[str, Any]] = []
    for path in window:
        rows = read_ranking(path, top_n=top_n)
        all_rows.extend(rows)
        for row in rows:
            history_by_stock.setdefault(row["stock_id"], []).append(row)

    items = [
        build_stock_item(stock_id, history=history, latest_by_stock=latest_by_stock, target_date=actual_target_date)
        for stock_id, history in sorted(history_by_stock.items(), key=lambda item: (-len(item[1]), item[1][-1]["rank"], item[0]))
    ]
    level_counts = Counter(item["warning_level"] for item in items)
    market_regimes = Counter(row.get("market_regime") for row in all_rows if row.get("market_regime"))
    output_path = OUTPUT_DIR / f"recent_top10_watchlist_warning_{actual_target_date}.json"
    markdown_path = OUTPUT_DIR / f"recent_top10_watchlist_warning_{actual_target_date}.md"

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "target_date": actual_target_date,
        "watchlist_ranking_days": watchlist_days,
        "top_n": top_n,
        "source_artifacts": {
            "rankings_dir": repo_path(rankings_dir),
            "features": repo_path(features_path),
            "ranking_files": [repo_path(path) for path in window],
        },
        "contract": {
            "research_only": True,
            "uses_future_rankings": False,
            "history_scope": "ranking artifacts with date <= target_date",
            "no_personal_holdings": True,
            "non_personal_warning_only": True,
            "does_not_send_push": True,
            "does_not_change_ranking": True,
            "does_not_change_model": True,
            "blocked_message_terms": list(BLOCKED_MESSAGE_TERMS),
        },
        "summary": {
            "watchlist_size": len(items),
            "warning_level_counts": dict(level_counts),
            "market_regime_counts_in_window": dict(market_regimes),
            "latest_top10_size": sum(1 for item in items if item["latest_in_top10"]),
            "dropped_from_latest_top10": sum(1 for item in items if item["dropped_from_top10"]),
        },
        "items": items,
        "outputs": {
            "json": repo_path(output_path),
            "markdown": repo_path(markdown_path),
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"# RQ08 近 7 日 Top10 觀察清單風險提醒 - {payload['target_date']}",
        "",
        "這份報告只做非個人化觀察提醒，不知道使用者是否持有、何時買進、買了多少。",
        "它的用途是把最近曾進 Top10 的股票分成：仍可觀察、動能降溫、轉弱風險升高。",
        "",
        "## 摘要",
        "",
        f"- 觀察股票數：{summary['watchlist_size']}",
        f"- 最新 Top10 仍在榜：{summary['latest_top10_size']}",
        f"- 近榜後掉出最新 Top10：{summary['dropped_from_latest_top10']}",
        f"- 分級：WATCH={summary['warning_level_counts'].get('WATCH', 0)}，"
        f"WEAKENING={summary['warning_level_counts'].get('WEAKENING', 0)}，"
        f"RISK_ALERT={summary['warning_level_counts'].get('RISK_ALERT', 0)}",
        "",
        "## 清單",
        "",
        "| 股票 | 狀態 | 近 7 日入榜 | 最新排名 | 提醒重點 | 白話提醒 |",
        "| --- | --- | ---: | ---: | --- | --- |",
    ]
    for item in payload["items"]:
        name = f"{item['stock_id']} {item.get('stock_name') or ''}".strip()
        latest_rank = item["latest_rank"] if item["latest_rank"] is not None else "-"
        notes = "；".join(item["plain_notes"])
        signal_labels = [SIGNAL_LABELS.get(signal, signal) for signal in item["signals"]]
        lines.append(
            f"| {name} | {item['conclusion']} | {item['days_seen_in_window']} | {latest_rank} | "
            f"{'、'.join(signal_labels) or '無明顯轉弱訊號'} | {notes} {item['holder_note']} |"
        )
    lines.extend(
        [
            "",
            "## 邊界",
            "",
            "- 不接推播，不送 Clawd。",
            "- 不改 production ranking、risk_adjusted_score 或模型。",
            "- 不處理個人持倉，也不提供個人化交易指令。",
        ]
    )
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    rankings_dir = resolve_path(args.rankings_dir)
    features_path = resolve_path(args.features)
    payload = build_payload(
        rankings_dir=rankings_dir,
        features_path=features_path,
        target_date=args.target_date,
        watchlist_days=args.watchlist_ranking_days,
        top_n=args.top_n,
    )
    default_json = OUTPUT_DIR / f"recent_top10_watchlist_warning_{payload['target_date']}.json"
    default_md = OUTPUT_DIR / f"recent_top10_watchlist_warning_{payload['target_date']}.md"
    output_path = resolve_path(args.output) if args.output else default_json
    markdown_path = resolve_path(args.markdown_output) if args.markdown_output else default_md
    payload["outputs"] = {"json": repo_path(output_path), "markdown": repo_path(markdown_path)}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(json.dumps({"status": "OK", "output": str(output_path), "markdown": str(markdown_path), "items": len(payload["items"])}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
