#!/usr/bin/env python3
"""彙整 odd-lot 曝險敏感度報告。

比較 candidate_top7_sl12_min5 在不同 gross / 單檔上限下，是否能在小本金
情境保留報酬優勢並降低回撤。只讀既有 replay artifact，不重跑 ranking。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "odd-lot-exposure-sensitivity-report.v1"
SETTINGS = {
    "g85_pos15": {"gross": 0.85, "pos": 0.15},
    "g75_pos12": {"gross": 0.75, "pos": 0.12},
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build odd-lot exposure sensitivity report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--capital-levels", default="100000,300000,500000")
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


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def artifact_path(side: str, setting: str, capital: int, run_date: str) -> Path:
    suffix = "" if setting == "g85_pos15" else "_gross75_pos12"
    name = f"odd_lot_portfolio_{side}_top7_sl12_min5_{capital // 1000}k_gross85_{run_date}.json"
    if suffix:
        name = f"odd_lot_portfolio_{side}_top7_sl12_min5_{capital // 1000}k{suffix}_{run_date}.json"
    return PROJECT_ROOT / "artifacts" / "model_experiments" / name


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def row(side: str, setting: str, capital: int, path: Path, production_summary: dict[str, Any]) -> dict[str, Any]:
    summary = read_json(path).get("summary", {})
    total_return = safe_float(summary.get("total_return"))
    max_drawdown = safe_float(summary.get("max_drawdown"))
    return {
        "side": side,
        "setting": setting,
        "capital": capital,
        "path": repo_path(path),
        "total_return": round(total_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "total_pnl": summary.get("total_pnl"),
        "trade_count": summary.get("trade_count"),
        "avg_cash_weight": summary.get("avg_cash_weight"),
        "max_gross_exposure": summary.get("max_gross_exposure"),
        "return_delta_vs_production_same_setting": round(total_return - safe_float(production_summary.get("total_return")), 6),
        "drawdown_delta_vs_production_same_setting": round(max_drawdown - safe_float(production_summary.get("max_drawdown")), 6),
    }


def aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for item in rows:
        groups.setdefault((item["side"], item["setting"]), []).append(item)
    result = {}
    for (side, setting), items in groups.items():
        key = f"{side}_{setting}"
        result[key] = {
            "capital_count": len(items),
            "avg_return": round(sum(safe_float(item["total_return"]) for item in items) / len(items), 6),
            "avg_max_drawdown": round(sum(safe_float(item["max_drawdown"]) for item in items) / len(items), 6),
            "avg_return_delta_vs_production_same_setting": round(
                sum(safe_float(item["return_delta_vs_production_same_setting"]) for item in items) / len(items),
                6,
            ),
            "worst_drawdown": min(safe_float(item["max_drawdown"]) for item in items),
            "min_return_delta_vs_production_same_setting": min(
                safe_float(item["return_delta_vs_production_same_setting"]) for item in items
            ),
        }
    return result


def decision(summary: dict[str, Any]) -> dict[str, Any]:
    candidate_keys = [key for key in summary if key.startswith("candidate_")]
    viable = {
        key: value
        for key, value in summary.items()
        if key in candidate_keys and value["min_return_delta_vs_production_same_setting"] > 0
    }
    if not viable:
        return {
            "status": "NO_EXPOSURE_SETTING_CANDIDATE",
            "selected": None,
            "promotion_ready": False,
            "reason": "沒有曝險設定能在所有本金級距勝過同設定 production。",
        }
    # 優先選回撤較低且仍有明顯報酬優勢的設定。
    selected = max(viable.items(), key=lambda item: item[1]["avg_return_delta_vs_production_same_setting"] + item[1]["avg_max_drawdown"])[0]
    return {
        "status": "EXPOSURE_SETTING_CANDIDATE",
        "selected": selected,
        "promotion_ready": False,
        "reason": "選取報酬優勢與回撤控制較均衡的 odd-lot 曝險設定；仍只作 research candidate。",
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    capital_levels = [int(float(value.strip())) for value in args.capital_levels.split(",") if value.strip()]
    rows: list[dict[str, Any]] = []
    missing: list[str | None] = []
    for setting in SETTINGS:
        for capital in capital_levels:
            production_path = artifact_path("production", setting, capital, args.date)
            candidate_path = artifact_path("candidate", setting, capital, args.date)
            if not production_path.exists():
                missing.append(repo_path(production_path))
                continue
            if not candidate_path.exists():
                missing.append(repo_path(candidate_path))
                continue
            production_summary = read_json(production_path).get("summary", {})
            rows.append(row("production", setting, capital, production_path, production_summary))
            rows.append(row("candidate", setting, capital, candidate_path, production_summary))
    summary = aggregate(rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if rows and not missing else "FAILED",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "promotion_ready": False,
            "fixed_capital_odd_lot": True,
        },
        "inputs": {
            "capital_levels": capital_levels,
            "settings": SETTINGS,
        },
        "summary": summary,
        "decision": decision(summary),
        "rows": rows,
        "missing": missing,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# Odd-Lot Exposure Sensitivity",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']['status']}",
        f"- selected: {payload['decision'].get('selected')}",
        f"- promotion_ready: {payload['contract']['promotion_ready']}",
        "",
        "## Summary",
        "",
    ]
    for key, item in payload["summary"].items():
        lines.append(f"- {key}: avg_return={item['avg_return']}, avg_maxDD={item['avg_max_drawdown']}")
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"odd_lot_exposure_sensitivity_report_{args.date}.json"
    if output is None:
        raise RuntimeError("output resolution failed")
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(payload, output)
    print(json.dumps({"status": payload["status"], "decision": payload["decision"]["status"], "output": repo_path(output)}, ensure_ascii=False))
    return 0 if payload["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
