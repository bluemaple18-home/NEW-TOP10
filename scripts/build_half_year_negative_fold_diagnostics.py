#!/usr/bin/env python3
"""產生 half-year negative fold 下一輪診斷計畫。

本腳本只讀既有 walk-forward artifact，將負 fold 拆成下一輪假設；
不修改原 artifact gate，不訓練模型，不產生 promotion evidence。
"""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "half-year-negative-fold-diagnostics.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build half-year negative fold diagnostics plan")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--artifact", default=None)
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


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def default_artifact(run_date: str) -> Path:
    return OUTPUT_DIR / f"half_year_walkforward_validation_{run_date}.json"


def fold_key(row: dict[str, Any]) -> str:
    return f"{row.get('validation_start')}~{row.get('validation_end')}"


def fold_metrics(row: dict[str, Any]) -> dict[str, Any]:
    topn = row.get("topn_proxy") if isinstance(row.get("topn_proxy"), dict) else {}
    return {
        "fold": row.get("fold"),
        "validation_start": row.get("validation_start"),
        "validation_end": row.get("validation_end"),
        "train_end": row.get("train_end"),
        "auc": row.get("auc"),
        "avg_topn_future_return": topn.get("avg_topn_future_return"),
        "avg_universe_future_return": topn.get("avg_universe_future_return"),
        "topn_minus_universe_return": topn.get("topn_minus_universe_return"),
        "topn_minus_universe_hit_rate": topn.get("topn_minus_universe_hit_rate"),
    }


def negative_fold_rows(payload: dict[str, Any]) -> list[dict[str, Any]]:
    negative_windows = set((payload.get("decision_diagnostics") or {}).get("negative_or_flat_folds") or [])
    variants = payload.get("variants") if isinstance(payload.get("variants"), dict) else {}
    by_window: dict[str, dict[str, Any]] = {}
    for variant_name, variant in variants.items():
        for row in variant.get("folds", []) if isinstance(variant.get("folds"), list) else []:
            key = fold_key(row)
            if key not in negative_windows:
                continue
            by_window.setdefault(key, {"window": key, "variants": {}})
            by_window[key]["variants"][variant_name] = fold_metrics(row)
    return [by_window[key] for key in sorted(by_window)]


def hypothesis_rows(source_artifact: str) -> list[dict[str, Any]]:
    return [
        {
            "id": "feature:half_year_negative_fold:planned-feature-stability",
            "type": "feature",
            "candidate": "half_year_negative_fold",
            "slug": "planned-feature-stability",
            "question": "模型訊號不穩是否來自 planned technical feature 在不同 fold 的方向漂移？",
            "hypothesis": (
                "Planned feature stability can improve half-year fold-level topn_return_delta >= 0 in the next walk-forward "
                "without reducing baseline AUC below 0.60."
            ),
            "falsification": [
                "下一輪 walk-forward 中 planned/drop-planned 對照仍出現負 topn uplift fold",
                "AUC 或 Top10 return 改善只出現在同一輪 post-hoc filter",
            ],
            "baseline": "half_year_walkforward current_baseline 2026-06-01",
            "target_metrics": ["fold_topn_uplift_delta:0.0", "baseline_auc:0.60"],
            "risk_metrics": ["negative_fold_count:0"],
            "next_experiment": "new walk-forward with pre-registered planned-feature stability lane",
            "source_artifacts": [source_artifact],
        },
        {
            "id": "training_policy:half_year_negative_fold:false-breakout-ranking-lane",
            "type": "training_policy",
            "candidate": "half_year_negative_fold",
            "slug": "false-breakout-ranking-lane",
            "question": "ranking rule 是否在負 fold 推太多假突破或高波動尾端標的？",
            "hypothesis": (
                "A pre-registered false-breakout ranking lane can improve 5D/10D topn_return_delta >= 0 "
                "on the next sealed replay without lowering hit-rate or changing production ranking."
            ),
            "falsification": [
                "Top10 hit-rate 改善但 avg return 仍輸 universe",
                "改善只依賴同輪負 fold 事後剔除",
            ],
            "baseline": "current production ranking replay on the same future sealed window",
            "target_metrics": ["topn_return_delta:0.0", "hit_rate_delta:0.0"],
            "risk_metrics": ["max_drawdown_nonworse:0.0"],
            "next_experiment": "sealed ranking replay with pre-registered false-breakout diagnostics",
            "source_artifacts": [source_artifact],
        },
        {
            "id": "training_policy:half_year_negative_fold:regime-family-routing",
            "type": "training_policy",
            "candidate": "half_year_negative_fold",
            "slug": "regime-family-routing",
            "question": "盤勢 tag 是否需要只在 ranking 層分流，而不是替換模型 gate？",
            "hypothesis": (
                "Regime-family routing can improve BIG_BULL or defensive fold Top10 return >= 0 versus global baseline "
                "in a new sealed/replay run, while model promotion remains blocked unless AUC gates also pass."
            ),
            "falsification": [
                "ranking/replay 正向但 AUC gate 仍不穩時被誤當 production promotion",
                "family tag 被新增成互斥 base regime",
            ],
            "baseline": "global baseline/current model with fixed base regime taxonomy",
            "target_metrics": ["topn_return_delta:0.0", "positive_window_ratio:0.75"],
            "risk_metrics": ["auc_delta_nonnegative_ratio:0.75"],
            "next_experiment": "new sealed/replay regime-family ranking route",
            "source_artifacts": [source_artifact],
        },
        {
            "id": "overlay:half_year_negative_fold:risk-overlay-sizing",
            "type": "overlay",
            "candidate": "half_year_negative_fold",
            "slug": "risk-overlay-sizing",
            "question": "portfolio sizing / risk overlay 是否是負 fold 的尾端風險來源？",
            "hypothesis": (
                "A pre-registered risk overlay can reduce negative-fold max_drawdown without reducing 10D total_return "
                "below the current replay baseline in the next portfolio replay."
            ),
            "falsification": [
                "max drawdown 下降但 total_return 也低於 baseline",
                "overlay 使用同輪負 fold 事後參數調整",
            ],
            "baseline": "current portfolio replay with fixed D+1 entry and fixed horizon exit",
            "target_metrics": ["max_drawdown_delta:0.0", "total_return_delta:0.0"],
            "risk_metrics": ["turnover_or_skipped_count_nonworse:0.0"],
            "next_experiment": "new portfolio replay with pre-registered risk overlay parameters",
            "source_artifacts": [source_artifact],
        },
    ]


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    artifact = resolve_path(args.artifact) or default_artifact(args.date)
    if artifact is None or not artifact.exists():
        raise FileNotFoundError(f"half-year walk-forward artifact 不存在：{artifact}")
    source = load_json(artifact)
    source_artifact = repo_path(artifact)
    negative_folds = negative_fold_rows(source)
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "source_artifact": source_artifact,
        "source_decision": source.get("decision"),
        "source_decision_rationale": source.get("decision_rationale"),
        "contract": {
            "diagnostic_only": True,
            "research_only": True,
            "does_not_modify_source_artifact": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
            "does_not_convert_monitor_only_to_promote": True,
            "new_filters_require_next_walkforward_run": True,
        },
        "negative_folds": negative_folds,
        "hypotheses": hypothesis_rows(source_artifact or ""),
        "next_research_plan": {
            "required_new_evidence": [
                "new walk-forward run",
                "new sealed OOS/replay run",
                "portfolio replay for overlay hypotheses",
                "ledger resolution only after evidence is available",
            ],
            "forbidden_shortcuts": [
                "do not edit the original half-year gate",
                "do not use diagnostic-only result as promotion evidence",
                "do not add same-run filters based on these folds",
                "do not change MONITOR_ONLY to PROMOTE_CANDIDATE",
            ],
        },
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Half-year Negative Fold Diagnostics",
        "",
        f"- status: `{payload['status']}`",
        f"- source_decision: `{payload['source_decision']}`",
        f"- production_promotion_allowed: `{payload['contract']['production_promotion_allowed']}`",
        "",
        "## Negative Folds",
    ]
    for fold in payload.get("negative_folds", []):
        lines.append(f"- `{fold['window']}`")
        current = (fold.get("variants") or {}).get("current_baseline", {})
        if current:
            lines.append(
                "  "
                f"current_baseline uplift={current.get('topn_minus_universe_return')}, "
                f"topn={current.get('avg_topn_future_return')}, auc={current.get('auc')}"
            )
    lines.extend(["", "## Hypotheses"])
    for row in payload.get("hypotheses", []):
        lines.append(f"- `{row['id']}`: {row['question']}")
    lines.append("")
    return "\n".join(lines)


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or OUTPUT_DIR / f"half_year_negative_fold_diagnostics_{args.date}.json"
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output.with_suffix(".md").write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": payload["status"],
                "output": repo_path(output),
                "negative_fold_count": len(payload["negative_folds"]),
                "hypothesis_count": len(payload["hypotheses"]),
                "production_promotion_allowed": payload["contract"]["production_promotion_allowed"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
