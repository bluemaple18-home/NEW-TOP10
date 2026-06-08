#!/usr/bin/env python3
"""彙整候選模型風控變體 replay 報告。

只比較已產出的 portfolio replay artifacts，不重跑 ranking、不訓練模型、不改
production。用途是從候選模型變體中挑出下一輪研究主線。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SCHEMA_VERSION = "training-candidate-risk-control-report.v1"
DEFAULT_CANDIDATE_ID = "current_baseline_candidate_{date}"


VARIANT_FILES = {
    "candidate_fixed40": "candidate_portfolio_replay_40d.json",
    "candidate_top5": "portfolio_replay_candidate_fixed40_top5_{date}.json",
    "candidate_top7": "portfolio_replay_candidate_fixed40_top7_{date}.json",
    "candidate_sector55": "portfolio_replay_candidate_fixed40_sector55_{date}.json",
    "candidate_sector65": "portfolio_replay_candidate_fixed40_sector65_{date}.json",
    "candidate_sector75": "portfolio_replay_candidate_fixed40_sector75_{date}.json",
    "candidate_top5_sector65": "portfolio_replay_candidate_fixed40_top5_sector65_{date}.json",
    "candidate_top7_sector55": "portfolio_replay_candidate_fixed40_top7_sector55_{date}.json",
    "candidate_top7_sector65": "portfolio_replay_candidate_fixed40_top7_sector65_{date}.json",
    "candidate_top7_sl10_min5": "portfolio_replay_candidate_fixed40_top7_sl10_min5_{date}.json",
    "candidate_top7_sl12_min5": "portfolio_replay_candidate_fixed40_top7_sl12_min5_{date}.json",
    "candidate_top7_trail18_min5": "portfolio_replay_candidate_fixed40_top7_trail18_min5_{date}.json",
    "candidate_top7_tp35_sl12_min5": "portfolio_replay_candidate_fixed40_top7_tp35_sl12_min5_{date}.json",
}

PRODUCTION_VARIANT_FILES = {
    "candidate_top7": "artifacts/model_experiments/production_portfolio_replay_40d_top7_{date}.json",
    "candidate_top7_sector55": "artifacts/model_experiments/production_portfolio_replay_40d_top7_{date}.json",
    "candidate_top7_sector65": "artifacts/model_experiments/production_portfolio_replay_40d_top7_{date}.json",
    "candidate_top7_sl12_min5": "artifacts/model_experiments/production_portfolio_replay_40d_top7_sl12_min5_{date}.json",
    "candidate_top7_trail18_min5": "artifacts/model_experiments/production_portfolio_replay_40d_top7_trail18_min5_{date}.json",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build candidate risk control report")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--candidate-id", default=None)
    parser.add_argument("--candidate-root", default=None)
    parser.add_argument("--production", default="artifacts/model_experiments/production_portfolio_replay_40d_{date}.json")
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(str(value)).expanduser()
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


def candidate_root(args: argparse.Namespace) -> Path:
    if args.candidate_root:
        root = resolve_path(args.candidate_root)
        if root is None:
            raise RuntimeError("candidate root resolution failed")
        return root
    candidate_id = args.candidate_id or DEFAULT_CANDIDATE_ID.format(date=args.date)
    return PROJECT_ROOT / "artifacts" / "model_experiments" / "training_candidates" / candidate_id


def safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def summary_row(
    label: str,
    path: Path,
    payload: dict[str, Any],
    baseline: dict[str, Any],
    peer_path: Path | None = None,
    peer_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    base = baseline.get("summary") if isinstance(baseline.get("summary"), dict) else {}
    total_return = safe_float(summary.get("total_return"))
    max_drawdown = safe_float(summary.get("max_drawdown"))
    baseline_return = safe_float(base.get("total_return"))
    baseline_drawdown = safe_float(base.get("max_drawdown"))
    peer_summary = peer_payload.get("summary", {}) if isinstance(peer_payload, dict) else {}
    peer_return = safe_float(peer_summary.get("total_return")) if peer_summary else None
    peer_drawdown = safe_float(peer_summary.get("max_drawdown")) if peer_summary else None
    return {
        "label": label,
        "path": repo_path(path),
        "production_peer": repo_path(peer_path),
        "total_return": round(total_return, 6),
        "max_drawdown": round(max_drawdown, 6),
        "trade_count": summary.get("trade_count"),
        "win_rate": summary.get("win_rate"),
        "avg_gross_exposure": summary.get("avg_gross_exposure"),
        "max_group_exposure": summary.get("max_group_exposure"),
        "return_delta_vs_production": round(total_return - baseline_return, 6),
        "drawdown_delta_vs_production": round(max_drawdown - baseline_drawdown, 6),
        "return_delta_vs_peer": round(total_return - peer_return, 6) if peer_return is not None else None,
        "drawdown_delta_vs_peer": round(max_drawdown - peer_drawdown, 6) if peer_drawdown is not None else None,
        "return_to_drawdown": round(total_return / abs(max_drawdown), 6) if max_drawdown else None,
        "keeps_return_edge": total_return > baseline_return,
        "drawdown_worse_than_production": max_drawdown < baseline_drawdown,
    }


def rank_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    def score(row: dict[str, Any]) -> float:
        # 研究排序：先看報酬，再罰回撤惡化；不是 production gate。
        return safe_float(row.get("return_delta_vs_production")) + safe_float(row.get("drawdown_delta_vs_production")) * 0.5

    return sorted(rows, key=score, reverse=True)


def decision(rows: list[dict[str, Any]], baseline: dict[str, Any]) -> dict[str, Any]:
    baseline_summary = baseline.get("summary") if isinstance(baseline.get("summary"), dict) else {}
    acceptable = [
        row
        for row in rows
        if row["keeps_return_edge"]
        and row["return_delta_vs_production"] >= 0.02
        and row["drawdown_delta_vs_production"] >= -0.03
    ]
    ranked = rank_rows(acceptable)
    if not ranked:
        return {
            "status": "NO_RISK_CONTROL_CANDIDATE",
            "selected": None,
            "reason": "沒有變體同時保留明顯報酬優勢且控制回撤惡化。",
            "production_baseline": {
                "total_return": baseline_summary.get("total_return"),
                "max_drawdown": baseline_summary.get("max_drawdown"),
            },
        }
    selected = ranked[0]
    return {
        "status": "RISK_CONTROL_REPLAY_CANDIDATE",
        "selected": selected["label"],
        "reason": "此變體保留候選模型報酬優勢，且回撤惡化仍在研究容忍範圍內；下一步進更嚴格分盤勢與本金約束回測。",
        "selected_metrics": selected,
        "production_baseline": {
            "total_return": baseline_summary.get("total_return"),
            "max_drawdown": baseline_summary.get("max_drawdown"),
        },
    }


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    root = candidate_root(args)
    production_path = resolve_path(args.production.format(date=args.date))
    if production_path is None or not production_path.exists():
        raise FileNotFoundError(f"production replay not found: {production_path}")
    production = read_json(production_path)
    rows = []
    missing = []
    for label, template in VARIANT_FILES.items():
        path = root / template.format(date=args.date)
        if not path.exists():
            missing.append({"label": label, "path": repo_path(path)})
            continue
        peer_path = resolve_path(PRODUCTION_VARIANT_FILES[label].format(date=args.date)) if label in PRODUCTION_VARIANT_FILES else None
        peer_payload = read_json(peer_path) if peer_path is not None and peer_path.exists() else None
        rows.append(summary_row(label, path, read_json(path), production, peer_path, peer_payload))
    ranked = rank_rows(rows)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK" if rows else "FAILED",
        "contract": {
            "research_only": True,
            "model_changes": False,
            "production_ranking_changes": False,
            "risk_adjusted_score_changes": False,
            "promotion_ready": False,
        },
        "inputs": {
            "candidate_root": repo_path(root),
            "production": repo_path(production_path),
        },
        "summary": {
            "variant_count": len(rows),
            "missing_count": len(missing),
            "best_by_research_score": ranked[0]["label"] if ranked else None,
            "best_total_return": max((row["total_return"] for row in rows), default=None),
            "best_max_drawdown": max((row["max_drawdown"] for row in rows), default=None),
        },
        "decision": decision(rows, production),
        "variants_ranked": ranked,
        "missing": missing,
        "next": [
            "對 selected 變體跑 fixed capital / odd-lot portfolio replay。",
            "對 selected 變體跑 BIG_BULL / HIGH_CHOPPY_CONTEXT 分層 replay。",
            "若 selected 在分層與本金約束仍成立，才進 promotion review candidate；目前不改正式模型。",
        ],
    }


def write_markdown(payload: dict[str, Any], output_path: Path) -> None:
    decision_payload = payload["decision"]
    lines = [
        "# Training Candidate Risk Control Report",
        "",
        f"- status: {payload['status']}",
        f"- decision: {decision_payload['status']}",
        f"- selected: {decision_payload.get('selected')}",
        f"- promotion_ready: {payload['contract']['promotion_ready']}",
        "",
        "## Variants",
        "",
    ]
    for row in payload["variants_ranked"]:
        lines.append(
            "- {label}: return={total_return}, maxDD={max_drawdown}, "
            "return_delta={return_delta_vs_production}, dd_delta={drawdown_delta_vs_production}".format(**row)
        )
    output_path.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or PROJECT_ROOT / "artifacts" / "model_experiments" / f"training_candidate_risk_control_report_{args.date}.json"
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
