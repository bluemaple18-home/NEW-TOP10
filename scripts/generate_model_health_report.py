#!/usr/bin/env python3
"""產出模型健康總覽報告。

這支腳本只讀既有模型、ranking 與 monitor artifacts，不重新訓練模型、
不重跑 ranking，也不修改 production score。它的目標是把 M11 監控從分散
artifact 收斂成一份可給 automation / PM / reviewer 判讀的狀態。
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import pickle
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
ARTIFACTS_DIR = PROJECT_ROOT / "artifacts"
RANKING_RE = re.compile(r"ranking_(\d{4}-\d{2}-\d{2})\.csv$")
SCHEMA_VERSION = "model-health-report.v1"


@dataclass(frozen=True)
class RankingOutcome:
    ranking_date: str
    path: str
    row_count: int
    top1_stock_id: str | None
    top1_stock_name: str | None
    evaluated_count: int
    pending_count: int
    missing_count: int
    hit_rate: float | None
    average_return: float | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="產出模型健康總覽報告")
    parser.add_argument("--horizon", type=int, default=10, help="持有期；需對齊 LabelGenerator horizon")
    parser.add_argument("--threshold", type=float, default=0.05, help="命中門檻；需對齊 LabelGenerator threshold")
    parser.add_argument("--min-evaluated", type=int, default=10, help="近期績效警示需要的最小已成熟樣本數")
    parser.add_argument("--min-hit-rate", type=float, default=0.5, help="近期 Top10 已成熟樣本 hit rate 低於此值時標 WARN")
    parser.add_argument("--ranking-limit", type=int, default=12, help="最多納入最近幾份 ranking artifact")
    parser.add_argument("--run-date", default=None, help="報告日期；未指定使用 Asia/Taipei 今日")
    parser.add_argument("--output", default=None, help="輸出 JSON；未指定使用 artifacts/model_health_report_YYYY-MM-DD.json")
    parser.add_argument("--fail-on-critical", action="store_true", help="整體狀態 CRITICAL 時以 exit 1 結束")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_date = args.run_date or datetime.now().astimezone().strftime("%Y-%m-%d")
    output_path = Path(args.output) if args.output else ARTIFACTS_DIR / f"model_health_report_{run_date}.json"

    model = model_snapshot(PROJECT_ROOT / "models" / "latest_lgbm.pkl")
    rankings = evaluate_rankings(
        ranking_paths=latest_ranking_paths(args.ranking_limit),
        horizon=args.horizon,
        threshold=args.threshold,
    )
    monitors = monitor_summary()
    checks = build_checks(
        model=model,
        rankings=rankings,
        monitors=monitors,
        min_evaluated=args.min_evaluated,
        min_hit_rate=args.min_hit_rate,
    )
    overall_status = worst_status([check["status"] for check in checks])
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "run_date": run_date,
        "status": overall_status,
        "model": model,
        "ranking_outcomes": [asdict(outcome) for outcome in rankings],
        "monitors": monitors,
        "checks": checks,
        "notes": [
            "只讀既有 artifacts；不訓練模型、不重跑 ranking、不改 production score。",
            "latest ranking 若尚未滿足 horizon，會列為 pending，不當作失敗。",
        ],
    }
    write_json(output_path, payload)
    write_json(ARTIFACTS_DIR / "model_health_report_latest.json", payload)

    latest_ranking = rankings[-1].ranking_date if rankings else "none"
    evaluated = sum(outcome.evaluated_count for outcome in rankings)
    print(f"MODEL_HEALTH_REPORT_{overall_status} latest_ranking={latest_ranking} evaluated={evaluated} output={output_path}")
    return 1 if args.fail_on_critical and overall_status == "CRITICAL" else 0


def latest_ranking_paths(limit: int) -> list[Path]:
    dated: list[tuple[str, Path]] = []
    for path in ARTIFACTS_DIR.glob("ranking_*.csv"):
        match = RANKING_RE.match(path.name)
        if match:
            dated.append((match.group(1), path))
    return [path for _, path in sorted(dated)[-limit:]]


def model_snapshot(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"path": str(path), "exists": False, "status": "CRITICAL", "reason": "missing model"}

    snapshot: dict[str, Any] = {
        "path": str(path),
        "exists": True,
        "size_bytes": path.stat().st_size,
        "mtime": datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat(),
        "sha256": sha256(path),
        "status": "OK",
    }
    try:
        with path.open("rb") as handle:
            payload = pickle.load(handle)
        snapshot["payload_type"] = type(payload).__name__
        if isinstance(payload, dict):
            model = payload.get("model")
            feature_names = payload.get("feature_names")
            if not feature_names and hasattr(model, "feature_name"):
                feature_names = model.feature_name()
            snapshot["feature_count"] = len(feature_names or [])
            snapshot["has_metadata"] = payload.get("metadata") is not None
            snapshot["has_calibrator"] = payload.get("calibrator") is not None
            if not snapshot["has_metadata"]:
                snapshot["status"] = "WARN"
                snapshot["reason"] = "model metadata missing"
        else:
            snapshot["status"] = "WARN"
            snapshot["reason"] = "legacy non-dict model payload"
    except Exception as exc:  # noqa: BLE001 - health report should preserve diagnostic context.
        snapshot["status"] = "CRITICAL"
        snapshot["reason"] = f"model unreadable: {exc}"
    return snapshot


def evaluate_rankings(ranking_paths: list[Path], horizon: int, threshold: float) -> list[RankingOutcome]:
    if not ranking_paths:
        return []
    features_path = PROJECT_ROOT / "data" / "clean" / "features.parquet"
    if not features_path.exists():
        return [empty_outcome(path, "features.parquet missing") for path in ranking_paths]

    features = pd.read_parquet(features_path, columns=["date", "stock_id", "open", "close"])
    features["trade_date"] = pd.to_datetime(features["date"]).dt.normalize()
    features["stock_id"] = features["stock_id"].astype(str).str.strip()
    features = features.sort_values(["stock_id", "trade_date"])
    by_stock = {stock_id: group.reset_index(drop=True) for stock_id, group in features.groupby("stock_id")}

    outcomes: list[RankingOutcome] = []
    for path in ranking_paths:
        ranking_date = ranking_date_from_path(path)
        rows = read_ranking_rows(path)
        returns: list[float] = []
        pending = 0
        missing = 0
        signal_day = pd.Timestamp(ranking_date).normalize()
        for row in rows[:10]:
            stock_id = str(row.get("stock_id", "")).strip()
            group = by_stock.get(stock_id)
            if group is None:
                missing += 1
                continue
            matches = group.index[group["trade_date"] == signal_day].tolist()
            if not matches:
                missing += 1
                continue
            signal_idx = matches[0]
            entry_idx = signal_idx + 1
            exit_idx = signal_idx + horizon
            if exit_idx >= len(group) or entry_idx >= len(group):
                pending += 1
                continue
            entry = float(group.loc[entry_idx, "open"])
            exit_price = float(group.loc[exit_idx, "close"])
            if entry <= 0:
                missing += 1
                continue
            returns.append((exit_price - entry) / entry)
        hit_rate = round(sum(value > threshold for value in returns) / len(returns), 4) if returns else None
        average_return = round(sum(returns) / len(returns), 4) if returns else None
        outcomes.append(
            RankingOutcome(
                ranking_date=ranking_date,
                path=str(path),
                row_count=len(rows),
                top1_stock_id=str(rows[0].get("stock_id", "")).strip() if rows else None,
                top1_stock_name=str(rows[0].get("stock_name", "")).strip() if rows else None,
                evaluated_count=len(returns),
                pending_count=pending,
                missing_count=missing,
                hit_rate=hit_rate,
                average_return=average_return,
            )
        )
    return outcomes


def empty_outcome(path: Path, reason: str) -> RankingOutcome:
    return RankingOutcome(
        ranking_date=ranking_date_from_path(path),
        path=str(path),
        row_count=0,
        top1_stock_id=None,
        top1_stock_name=None,
        evaluated_count=0,
        pending_count=0,
        missing_count=10,
        hit_rate=None,
        average_return=None,
    )


def monitor_summary() -> dict[str, Any]:
    psi = read_json(ARTIFACTS_DIR / "psi_report.json")
    factor = read_json(ARTIFACTS_DIR / "factor_monitor_report.json")
    industry = read_json(ARTIFACTS_DIR / "industry_momentum_walkforward_shadow.json")
    return {
        "psi": {
            "available": bool(psi),
            "status": str(psi.get("status", "MISSING")).upper() if psi else "MISSING",
            "avg_psi": psi.get("avg_psi"),
            "warning_features": psi.get("warning_features"),
            "critical_features": psi.get("critical_features"),
            "timestamp": psi.get("timestamp"),
        },
        "factor": {
            "available": bool(factor),
            "status": str(factor.get("status", "MISSING")).upper() if factor else "MISSING",
            "generated_at": factor.get("generated_at"),
            "factor_count": (factor.get("summary") or {}).get("factor_count") if factor else None,
            "warn_count": (factor.get("summary") or {}).get("warn_count") if factor else None,
        },
        "industry_momentum": {
            "available": bool(industry),
            "status": str(industry.get("status", "MISSING")).upper() if industry else "MISSING",
            "generated_at": industry.get("generated_at"),
            "decision": (industry.get("recommendation") or {}).get("decision") if industry else None,
        },
    }


def build_checks(
    model: dict[str, Any],
    rankings: list[RankingOutcome],
    monitors: dict[str, Any],
    min_evaluated: int,
    min_hit_rate: float,
) -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    checks.append({"name": "model.exists", "status": "OK" if model.get("exists") else "CRITICAL", "message": model.get("path")})
    checks.append({"name": "model.payload", "status": model.get("status", "CRITICAL"), "message": model.get("reason")})
    latest_ranking = rankings[-1] if rankings else None
    checks.append(
        {
            "name": "ranking.latest",
            "status": "OK" if latest_ranking and latest_ranking.row_count >= 10 else "CRITICAL",
            "message": f"{latest_ranking.ranking_date} rows={latest_ranking.row_count}" if latest_ranking else "missing ranking artifact",
        }
    )
    psi_status = monitors["psi"]["status"]
    checks.append({"name": "monitor.psi", "status": "CRITICAL" if psi_status == "CRITICAL" else "OK" if psi_status == "OK" else "WARN", "message": psi_status})
    factor_status = monitors["factor"]["status"]
    checks.append({"name": "monitor.factor", "status": "WARN" if factor_status == "WARN" else "OK" if factor_status == "OK" else "CRITICAL", "message": factor_status})
    industry_status = monitors["industry_momentum"]["status"]
    checks.append(
        {
            "name": "monitor.industry_momentum",
            "status": "OK" if industry_status == "OK" else "WARN",
            "message": f"{industry_status} decision={monitors['industry_momentum'].get('decision')}",
        }
    )

    evaluated_outcomes = [outcome for outcome in rankings if outcome.evaluated_count > 0]
    evaluated_count = sum(outcome.evaluated_count for outcome in evaluated_outcomes)
    if evaluated_count < min_evaluated:
        checks.append(
            {
                "name": "ranking.realized_outcome",
                "status": "WARN",
                "message": f"matured samples={evaluated_count} < min_evaluated={min_evaluated}",
            }
        )
    else:
        weighted_hits = sum((outcome.hit_rate or 0) * outcome.evaluated_count for outcome in evaluated_outcomes)
        hit_rate = weighted_hits / evaluated_count
        checks.append(
            {
                "name": "ranking.realized_outcome",
                "status": "WARN" if hit_rate < min_hit_rate else "OK",
                "message": f"hit_rate={hit_rate:.4f} evaluated={evaluated_count}",
            }
        )
    return checks


def worst_status(statuses: list[str]) -> str:
    order = {"OK": 0, "WARN": 1, "CRITICAL": 2, "FAILED": 2}
    normalized = [status.upper() for status in statuses]
    return max(normalized, key=lambda status: order.get(status, 2)) if normalized else "CRITICAL"


def read_ranking_rows(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def ranking_date_from_path(path: Path) -> str:
    match = RANKING_RE.match(path.name)
    if not match:
        raise ValueError(f"不是 ranking artifact 檔名：{path}")
    return match.group(1)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


if __name__ == "__main__":
    raise SystemExit(main())
