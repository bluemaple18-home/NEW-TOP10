#!/usr/bin/env python3
"""依盤勢切分 portfolio replay 結果。

用 ranking date 的 market regime tag 歸因每筆已實現交易，專門檢查候選規則在
BIG_BULL / HIGH_CHOPPY_CONTEXT / OTHER 的表現。這是 replay attribution，不改
ranking、不訓練模型。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_high_choppy_context_overlay import load_regime_frame, rolling_high_choppy  # noqa: E402
from scripts.research_regime_family_training_candidates import is_big_bull  # noqa: E402


SCHEMA_VERSION = "portfolio-replay-regime-attribution.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build portfolio replay regime attribution")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--production-peer", default=None)
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-06-01.json")
    parser.add_argument("--label", default="candidate")
    parser.add_argument("--output", default=None)
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


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def regime_map(path: Path) -> dict[str, dict[str, Any]]:
    frame = load_regime_frame(path)
    frame["BIG_BULL"] = frame.apply(is_big_bull, axis=1)
    frame["HIGH_CHOPPY_CONTEXT"] = frame.apply(rolling_high_choppy, axis=1)
    result: dict[str, dict[str, Any]] = {}
    for row in frame.itertuples(index=False):
        date_text = str(row.trade_date_text)
        if bool(row.HIGH_CHOPPY_CONTEXT):
            family = "HIGH_CHOPPY_CONTEXT"
        elif bool(row.BIG_BULL):
            family = "BIG_BULL"
        else:
            family = "OTHER"
        result[date_text] = {
            "family": family,
            "base_regime": str(getattr(row, "regime_label", "")),
            "top_sector": getattr(row, "top_sector", None),
            "top_sector_value_share": safe_float(getattr(row, "top_sector_value_share", None), default=None),
        }
    return result


def summarize_trades(payload: dict[str, Any], regimes: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    trades = payload.get("trades") if isinstance(payload.get("trades"), list) else []
    buckets: dict[str, list[dict[str, Any]]] = {"BIG_BULL": [], "HIGH_CHOPPY_CONTEXT": [], "OTHER": [], "UNKNOWN": []}
    for trade in trades:
        ranking_date = str(trade.get("ranking_date") or "")
        family = regimes.get(ranking_date, {}).get("family", "UNKNOWN")
        buckets.setdefault(family, []).append(trade)
    result: dict[str, dict[str, Any]] = {}
    for family, items in buckets.items():
        if not items:
            result[family] = {"trade_count": 0, "avg_net_return": None, "win_rate": None, "total_net_return_proxy": None}
            continue
        returns = [safe_float(item.get("net_return")) for item in items]
        result[family] = {
            "trade_count": len(items),
            "avg_net_return": round(sum(returns) / len(returns), 6),
            "win_rate": round(sum(1 for value in returns if value > 0) / len(returns), 6),
            "total_net_return_proxy": round(sum(returns), 6),
        }
    return result


def compare(candidate: dict[str, dict[str, Any]], production: dict[str, dict[str, Any]]) -> dict[str, dict[str, Any]]:
    result = {}
    for family, cand in candidate.items():
        prod = production.get(family, {})
        result[family] = {
            "candidate": cand,
            "production": prod,
            "avg_net_return_delta": round(safe_float(cand.get("avg_net_return")) - safe_float(prod.get("avg_net_return")), 6),
            "win_rate_delta": round(safe_float(cand.get("win_rate")) - safe_float(prod.get("win_rate")), 6),
            "trade_count_delta": int(cand.get("trade_count") or 0) - int(prod.get("trade_count") or 0),
        }
    return result


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    candidate_path = resolve_path(args.candidate)
    production_path = resolve_path(args.production_peer)
    regime_path = resolve_path(args.market_regime_history)
    if candidate_path is None or not candidate_path.exists():
        raise FileNotFoundError(f"candidate replay not found: {args.candidate}")
    if regime_path is None or not regime_path.exists():
        raise FileNotFoundError(f"market regime history not found: {args.market_regime_history}")
    regimes = regime_map(regime_path)
    candidate_summary = summarize_trades(read_json(candidate_path), regimes)
    production_summary = summarize_trades(read_json(production_path), regimes) if production_path else {}
    comparison = compare(candidate_summary, production_summary) if production_summary else {}
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_ready": False,
        },
        "inputs": {
            "candidate": repo_path(candidate_path),
            "production_peer": repo_path(production_path),
            "market_regime_history": repo_path(regime_path),
        },
        "label": args.label,
        "candidate_by_regime": candidate_summary,
        "production_peer_by_regime": production_summary,
        "comparison": comparison,
        "decision": {
            "status": "REGIME_ATTRIBUTION_ONLY",
            "promotion_ready": False,
            "plain_language": "這份只看規則在不同盤勢裡的表現，不作正式升版。",
        },
    }


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"portfolio_replay_regime_attribution_{args.label}_{args.date}.json"
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": payload["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
