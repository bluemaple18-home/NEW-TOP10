#!/usr/bin/env python3
"""建立每日市場盤勢研究 artifact。

本腳本只讀既有 features / reference，不訓練模型、不改 ranking。
用途是先把市場切成多種盤勢，後續 replay 與 feature 消融都要先依盤勢分層。
"""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "market-regime-history.v1"


@dataclass(frozen=True)
class RegimeRow:
    trade_date: str
    regime_label: str
    risk_tone: str
    equal_weight_return: float | None
    value_weight_return: float | None
    breadth_ma20: float | None
    breadth_ma60: float | None
    advance_ratio: float | None
    breakout_ratio: float | None
    breakdown_ratio: float | None
    volume_spike_ratio: float | None
    long_upper_shadow_ratio: float | None
    avg_rsi: float | None
    top_sector: str | None
    top_sector_value_share: float | None
    top_strong_sector: str | None
    top_strong_sector_value_share: float | None
    notes: str


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build market regime history artifact")
    parser.add_argument("--features", default="data/clean/features.parquet")
    parser.add_argument("--industry-map", default="data/reference/stock_industry_map.csv")
    parser.add_argument("--start-date", default=None)
    parser.add_argument("--end-date", default=None)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | None) -> Path | None:
    if value is None:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def number(value: Any, digits: int = 6) -> float | None:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return None
    return round(float(parsed), digits)


def ratio(mask: pd.Series) -> float | None:
    if mask.empty:
        return None
    return number(mask.fillna(False).mean())


def weighted_mean(values: pd.Series, weights: pd.Series) -> float | None:
    data = pd.DataFrame({"value": values, "weight": weights}).dropna()
    data = data[data["weight"] > 0]
    if data.empty:
        return None
    return number((data["value"] * data["weight"]).sum() / data["weight"].sum())


def load_features(path: Path, start_date: str | None, end_date: str | None) -> pd.DataFrame:
    if not path.exists():
        raise FileNotFoundError(f"features 不存在：{path}")
    frame = pd.read_parquet(path)
    if "date" not in frame.columns:
        raise ValueError("features 缺少 date 欄位")
    frame = frame.copy()
    frame["trade_date"] = pd.to_datetime(frame["date"], errors="coerce").dt.normalize()
    frame = frame.dropna(subset=["trade_date", "stock_id"]).copy()
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip().str.zfill(4)
    if start_date:
        frame = frame[frame["trade_date"] >= pd.to_datetime(start_date).normalize()].copy()
    if end_date:
        frame = frame[frame["trade_date"] <= pd.to_datetime(end_date).normalize()].copy()
    if frame.empty:
        raise ValueError("指定日期區間沒有 features 資料")
    frame = frame.sort_values(["stock_id", "trade_date"]).copy()
    frame["daily_return"] = frame.groupby("stock_id", sort=False)["close"].pct_change()
    return frame


def load_industry_map(path: Path | None) -> pd.DataFrame:
    if path is None or not path.exists():
        return pd.DataFrame(columns=["stock_id", "sector_name", "industry_name", "market_type"])
    frame = pd.read_csv(path, dtype={"stock_id": str})
    frame["stock_id"] = frame["stock_id"].astype(str).str.strip().str.zfill(4)
    keep = [col for col in ["stock_id", "sector_name", "industry_name", "market_type"] if col in frame.columns]
    return frame[keep].drop_duplicates("stock_id")


def enrich_reference(features: pd.DataFrame, industry_map: pd.DataFrame) -> pd.DataFrame:
    if industry_map.empty:
        features["sector_name"] = "unknown"
        features["industry_name"] = "unknown"
        return features
    enriched = features.merge(industry_map, on="stock_id", how="left")
    enriched["sector_name"] = enriched["sector_name"].fillna("unknown")
    enriched["industry_name"] = enriched["industry_name"].fillna("unknown")
    return enriched


def top_value_group(day: pd.DataFrame, group_col: str, mask: pd.Series | None = None) -> tuple[str | None, float | None]:
    subset = day[mask.fillna(False)].copy() if mask is not None else day.copy()
    if subset.empty or "value" not in subset.columns:
        return None, None
    values = pd.to_numeric(subset["value"], errors="coerce").fillna(0)
    total = float(values.sum())
    if total <= 0:
        return None, None
    grouped = subset.assign(_value=values).groupby(group_col, dropna=False)["_value"].sum().sort_values(ascending=False)
    if grouped.empty:
        return None, None
    return str(grouped.index[0]), number(float(grouped.iloc[0]) / total)


def classify(metrics: dict[str, float | str | None]) -> tuple[str, str, str]:
    breadth = metrics.get("breadth_ma20")
    breadth60 = metrics.get("breadth_ma60")
    ew_return = metrics.get("equal_weight_return")
    breakout = metrics.get("breakout_ratio")
    breakdown = metrics.get("breakdown_ratio")
    avg_rsi = metrics.get("avg_rsi")
    upper_shadow = metrics.get("long_upper_shadow_ratio")
    strong_share = metrics.get("top_strong_sector_value_share")
    volume_spike = metrics.get("volume_spike_ratio")

    if breadth is None or ew_return is None:
        return "UNKNOWN", "defensive", "資料不足，不能判斷盤勢"

    if (ew_return <= -0.025 and breadth <= 0.32) or (breadth <= 0.28 and (avg_rsi or 50) <= 43):
        return "PANIC_SELLING", "defensive", "急跌或市場廣度明顯失守，先看風險"

    if breadth <= 0.38 or ((avg_rsi or 50) < 47 and ew_return < 0):
        return "RISK_OFF", "defensive", "多數股票在弱勢區，追價訊號要打折"

    if breadth >= 0.62 and (avg_rsi is None or avg_rsi >= 52) and ew_return >= 0:
        return "BROAD_RISK_ON", "aggressive", "多數股票同步轉強，順勢訊號可信度較高"

    if (
        0.42 <= breadth <= 0.62
        and (strong_share is not None and strong_share >= 0.32)
        and (breakout is None or breakout >= 0.035)
    ):
        return "NARROW_LEADER", "selective", "指數不一定全面強，但資金集中在少數主流族群"

    if (
        0.36 <= breadth <= 0.58
        and ew_return > 0
        and (avg_rsi is None or avg_rsi < 52)
        and (volume_spike is not None and volume_spike >= 0.08)
        and (breakdown is None or breakdown < 0.25)
    ):
        return "EARLY_REVERSAL", "selective", "低位階開始有人承接，但還不是全面多頭"

    if (
        abs(ew_return) <= 0.008
        and 0.40 <= breadth <= 0.60
        and (upper_shadow is None or upper_shadow >= 0.04)
        and (breadth60 is None or 0.35 <= breadth60 <= 0.65)
    ):
        return "CHOPPY_RANGE", "neutral", "盤勢震盪，突破訊號容易被洗掉"

    return "MIXED_NEUTRAL", "neutral", "盤勢沒有明確單邊方向，先做中性觀察"


def build_rows(frame: pd.DataFrame) -> list[RegimeRow]:
    rows: list[RegimeRow] = []
    for trade_date, day in frame.groupby("trade_date", sort=True):
        close = pd.to_numeric(day.get("close"), errors="coerce")
        ma20 = pd.to_numeric(day.get("ma20"), errors="coerce")
        ma60 = pd.to_numeric(day.get("ma60"), errors="coerce")
        daily_return = pd.to_numeric(day.get("daily_return"), errors="coerce")
        value = pd.to_numeric(day.get("value"), errors="coerce")
        strong_mask = (daily_return > 0) & (close > ma20)
        top_sector, top_sector_share = top_value_group(day, "sector_name")
        top_strong_sector, top_strong_share = top_value_group(day, "sector_name", strong_mask)

        metrics: dict[str, float | str | None] = {
            "equal_weight_return": number(daily_return.mean()),
            "value_weight_return": weighted_mean(daily_return, value),
            "breadth_ma20": ratio(close > ma20),
            "breadth_ma60": ratio(close > ma60),
            "advance_ratio": ratio(daily_return > 0),
            "breakout_ratio": event_ratio(day, ["break_20d_high", "breakout_flag"]),
            "breakdown_ratio": event_ratio(day, ["close_below_bb_mid", "ma5_cross_ma20_down"]),
            "volume_spike_ratio": event_ratio(day, ["volume_spike", "volume_spike_1.5x"]),
            "long_upper_shadow_ratio": event_ratio(day, ["long_upper_shadow"]),
            "avg_rsi": number(pd.to_numeric(day.get("rsi"), errors="coerce").mean()),
            "top_sector": top_sector,
            "top_sector_value_share": top_sector_share,
            "top_strong_sector": top_strong_sector,
            "top_strong_sector_value_share": top_strong_share,
        }
        label, tone, notes = classify(metrics)
        rows.append(
            RegimeRow(
                trade_date=pd.Timestamp(trade_date).date().isoformat(),
                regime_label=label,
                risk_tone=tone,
                equal_weight_return=metrics["equal_weight_return"],  # type: ignore[arg-type]
                value_weight_return=metrics["value_weight_return"],  # type: ignore[arg-type]
                breadth_ma20=metrics["breadth_ma20"],  # type: ignore[arg-type]
                breadth_ma60=metrics["breadth_ma60"],  # type: ignore[arg-type]
                advance_ratio=metrics["advance_ratio"],  # type: ignore[arg-type]
                breakout_ratio=metrics["breakout_ratio"],  # type: ignore[arg-type]
                breakdown_ratio=metrics["breakdown_ratio"],  # type: ignore[arg-type]
                volume_spike_ratio=metrics["volume_spike_ratio"],  # type: ignore[arg-type]
                long_upper_shadow_ratio=metrics["long_upper_shadow_ratio"],  # type: ignore[arg-type]
                avg_rsi=metrics["avg_rsi"],  # type: ignore[arg-type]
                top_sector=top_sector,
                top_sector_value_share=top_sector_share,
                top_strong_sector=top_strong_sector,
                top_strong_sector_value_share=top_strong_share,
                notes=notes,
            )
        )
    return rows


def event_ratio(day: pd.DataFrame, candidates: list[str]) -> float | None:
    for col in candidates:
        if col in day.columns:
            data = pd.to_numeric(day[col], errors="coerce")
            if data.notna().any():
                return ratio(data > 0)
    return None


def summarize(rows: list[RegimeRow]) -> dict[str, Any]:
    frame = pd.DataFrame([asdict(row) for row in rows])
    latest = rows[-1] if rows else None
    counts = frame["regime_label"].value_counts().to_dict() if not frame.empty else {}
    return {
        "trade_days": len(rows),
        "start_date": rows[0].trade_date if rows else None,
        "end_date": rows[-1].trade_date if rows else None,
        "latest": asdict(latest) if latest else None,
        "regime_counts": {str(key): int(value) for key, value in counts.items()},
    }


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        "# Market Regime History",
        "",
        f"- generated_at: {payload['generated_at']}",
        f"- date_range: {summary['start_date']} ~ {summary['end_date']}",
        f"- trade_days: {summary['trade_days']}",
        "",
        "## Regime Counts",
        "",
        "| Regime | Days |",
        "|---|---:|",
    ]
    for label, count in sorted(summary["regime_counts"].items(), key=lambda item: (-item[1], item[0])):
        lines.append(f"| {label} | {count} |")
    latest = summary.get("latest") or {}
    lines.extend(
        [
            "",
            "## Latest",
            "",
            f"- date: {latest.get('trade_date')}",
            f"- regime: {latest.get('regime_label')}",
            f"- breadth_ma20: {fmt_pct(latest.get('breadth_ma20'))}",
            f"- advance_ratio: {fmt_pct(latest.get('advance_ratio'))}",
            f"- top_strong_sector: {latest.get('top_strong_sector')} ({fmt_pct(latest.get('top_strong_sector_value_share'))})",
            f"- notes: {latest.get('notes')}",
            "",
            "## Recent 20 Days",
            "",
            "| Date | Regime | EW Return | Breadth MA20 | Advance | Strong Sector | Notes |",
            "|---|---|---:|---:|---:|---|---|",
        ]
    )
    for row in payload["rows"][-20:]:
        lines.append(
            "| {date} | {regime} | {ret} | {breadth} | {adv} | {sector} | {notes} |".format(
                date=row["trade_date"],
                regime=row["regime_label"],
                ret=fmt_pct(row["equal_weight_return"]),
                breadth=fmt_pct(row["breadth_ma20"]),
                adv=fmt_pct(row["advance_ratio"]),
                sector=row.get("top_strong_sector") or "--",
                notes=row["notes"],
            )
        )
    return "\n".join(lines) + "\n"


def fmt_pct(value: Any) -> str:
    parsed = pd.to_numeric(pd.Series([value]), errors="coerce").iloc[0]
    if pd.isna(parsed):
        return "--"
    return f"{float(parsed):.2%}"


def main() -> int:
    args = parse_args()
    features_path = resolve_path(args.features)
    industry_path = resolve_path(args.industry_map)
    assert features_path is not None
    features = load_features(features_path, args.start_date, args.end_date)
    industry_map = load_industry_map(industry_path)
    frame = enrich_reference(features, industry_map)
    rows = build_rows(frame)
    output_path = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "market_regime_history_latest.json"
    assert output_path is not None
    output_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "contract": {
            "research_only": True,
            "trains_model": False,
            "changes_ranking": False,
            "regime_labels": [
                "BROAD_RISK_ON",
                "NARROW_LEADER",
                "CHOPPY_RANGE",
                "RISK_OFF",
                "PANIC_SELLING",
                "EARLY_REVERSAL",
                "MIXED_NEUTRAL",
                "UNKNOWN",
            ],
        },
        "inputs": {
            "features": str(features_path),
            "industry_map": str(industry_path) if industry_path else None,
            "start_date": args.start_date,
            "end_date": args.end_date,
        },
        "summary": summarize(rows),
        "rows": [asdict(row) for row in rows],
    }
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_path.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK",
                "output": str(output_path),
                "markdown": str(output_path.with_suffix(".md")),
                "latest": payload["summary"]["latest"],
                "regime_counts": payload["summary"]["regime_counts"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
