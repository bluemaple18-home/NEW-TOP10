#!/usr/bin/env python3
"""Regime family 訓練候選的 research-only sealed replay。

本腳本只在記憶體中訓練候選模型，用固定 sealed 視窗做確認；
不保存模型、不覆蓋 models/latest_lgbm.pkl、不修改 production ranking。
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import lightgbm as lgb
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import research_regime_family_training_candidates as candidates  # noqa: E402


OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "model_experiments"
SCHEMA_VERSION = "regime-family-sealed-replay.v1"
DECISION_PASS = "SEALED_REPLAY_PASS"
DECISION_MONITOR = "MONITOR_ONLY"
DECISION_REJECTED = "REJECTED"
VARIANTS = ["global_baseline", "family_only_training", "family_weighted_training"]


@dataclass(frozen=True)
class SplitDates:
    train_dates: list[pd.Timestamp]
    embargo_dates: list[pd.Timestamp]
    sealed_dates: list[pd.Timestamp]

    @property
    def train_start(self) -> str | None:
        return date_text(self.train_dates[0]) if self.train_dates else None

    @property
    def train_end(self) -> str | None:
        return date_text(self.train_dates[-1]) if self.train_dates else None

    @property
    def sealed_start(self) -> str | None:
        return date_text(self.sealed_dates[0]) if self.sealed_dates else None

    @property
    def sealed_end(self) -> str | None:
        return date_text(self.sealed_dates[-1]) if self.sealed_dates else None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="research regime family sealed replay")
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--market-regime-history", default="artifacts/market_regime_history_2026-05-31.json")
    parser.add_argument("--candidate-artifact", default=None)
    parser.add_argument("--families", default=None, help="逗號分隔；未指定時使用 candidate artifact 內 PROMOTE_CANDIDATE family")
    parser.add_argument("--horizon", type=int, default=10)
    parser.add_argument("--threshold", type=float, default=0.05)
    parser.add_argument("--embargo-trade-days", type=int, default=10)
    parser.add_argument("--sealed-trade-days", type=int, default=60)
    parser.add_argument("--min-train-trade-days", type=int, default=180)
    parser.add_argument("--min-sealed-family-dates", type=int, default=20)
    parser.add_argument("--min-sealed-samples", type=int, default=500)
    parser.add_argument("--min-positive-labels", type=int, default=20)
    parser.add_argument("--min-negative-labels", type=int, default=20)
    parser.add_argument("--min-auc", type=float, default=0.58)
    parser.add_argument("--min-topn-uplift", type=float, default=0.0)
    parser.add_argument("--min-candidate-topn-return", type=float, default=0.0)
    parser.add_argument("--min-delta-auc", type=float, default=0.001)
    parser.add_argument("--min-delta-topn-return", type=float, default=0.002)
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--num-boost-round", type=int, default=120)
    parser.add_argument("--family-weight", type=float, default=2.0)
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


def date_text(value: Any) -> str:
    return pd.Timestamp(value).date().isoformat()


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def latest_candidate_artifact() -> Path | None:
    matches = sorted(OUTPUT_DIR.glob("regime_family_training_candidates_????-??-??.json"))
    return matches[-1] if matches else None


def requested_families(args: argparse.Namespace, candidate_payload: dict[str, Any]) -> list[str]:
    if args.families:
        requested = [item.strip().upper() for item in args.families.split(",") if item.strip()]
        unknown = sorted(set(requested) - set(candidates.REGIME_FAMILY_TAGS))
        if unknown:
            raise ValueError(f"未知 regime family tag：{unknown}；允許清單={candidates.REGIME_FAMILY_TAGS}")
        return requested
    families = []
    for row in candidate_payload.get("families", []):
        if row.get("decision") == candidates.DECISION_PROMOTE:
            families.append(str(row.get("family")).upper())
    return families or ["BIG_BULL"]


def candidate_family_by_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {str(row.get("family")).upper(): row for row in payload.get("families", []) if row.get("family")}


def build_split(frame: pd.DataFrame, args: argparse.Namespace) -> SplitDates:
    dates = sorted(pd.to_datetime(frame["trade_date"]).drop_duplicates().tolist())
    required = args.min_train_trade_days + args.embargo_trade_days + args.sealed_trade_days
    if len(dates) < required:
        raise ValueError(
            "sealed replay 交易日不足："
            f"available={len(dates)} required={required} "
            f"(train={args.min_train_trade_days}, embargo={args.embargo_trade_days}, sealed={args.sealed_trade_days})"
        )
    sealed_start_index = len(dates) - args.sealed_trade_days
    train_end_index = sealed_start_index - args.embargo_trade_days - 1
    train_dates = dates[: train_end_index + 1]
    if len(train_dates) < args.min_train_trade_days:
        raise ValueError(f"train 視窗不足：train_days={len(train_dates)} min={args.min_train_trade_days}")
    embargo_dates = dates[train_end_index + 1 : sealed_start_index]
    sealed_dates = dates[sealed_start_index:]
    return SplitDates(train_dates=train_dates, embargo_dates=embargo_dates, sealed_dates=sealed_dates)


def train_frame_for_variant(frame: pd.DataFrame, family: str, split: SplitDates, variant: str) -> pd.DataFrame:
    train = frame[frame["trade_date"].isin(split.train_dates)].copy()
    if variant == "family_only_training":
        train = train[train[f"family_{family}"]].copy()
    return train


def score_variant(
    *,
    frame: pd.DataFrame,
    features: list[str],
    family: str,
    split: SplitDates,
    variant: str,
    args: argparse.Namespace,
) -> dict[str, Any]:
    train = train_frame_for_variant(frame, family, split, variant)
    sealed = frame[frame["trade_date"].isin(split.sealed_dates) & frame[f"family_{family}"]].copy()
    if sealed.empty:
        return {"status": "SKIPPED", "reason": "no sealed family rows"}
    if train.empty or train["target"].nunique() < 2:
        return {
            "status": "SKIPPED",
            "reason": "insufficient train classes or rows",
            "train_rows": int(len(train)),
            "sealed_rows": int(len(sealed)),
        }
    if sealed["target"].nunique() < 2:
        return {
            "status": "SKIPPED",
            "reason": "insufficient sealed classes",
            "train_rows": int(len(train)),
            "sealed_rows": int(len(sealed)),
        }
    weights = candidates.sample_weights(train, family, variant, args.family_weight)
    model = lgb.train(
        candidates.model_params(),
        lgb.Dataset(train[features], label=train["target"], weight=weights, feature_name=features),
        num_boost_round=args.num_boost_round,
    )
    sealed["pred_prob"] = model.predict(sealed[features])
    topn = candidates.topn_proxy(sealed, args.top_n)
    return {
        "status": "OK",
        "variant": variant,
        "train_rows": int(len(train)),
        "train_dates": int(pd.to_datetime(train["trade_date"]).nunique()),
        "sealed_rows": int(len(sealed)),
        "sealed_family_dates": int(pd.to_datetime(sealed["trade_date"]).nunique()),
        "positive_labels": int(pd.to_numeric(sealed["target"], errors="coerce").fillna(0).sum()),
        "negative_labels": int(len(sealed) - pd.to_numeric(sealed["target"], errors="coerce").fillna(0).sum()),
        "auc": candidates.safe_auc(sealed["target"].astype(int), sealed["pred_prob"]),
        "logloss": candidates.safe_logloss(sealed["target"].astype(int), sealed["pred_prob"]),
        "topn_proxy": topn,
    }


def metric_delta(candidate: dict[str, Any], baseline: dict[str, Any]) -> dict[str, float | None]:
    candidate_topn = candidate.get("topn_proxy", {}) if isinstance(candidate.get("topn_proxy"), dict) else {}
    baseline_topn = baseline.get("topn_proxy", {}) if isinstance(baseline.get("topn_proxy"), dict) else {}
    return {
        "auc_delta_vs_global": candidates.delta(candidate.get("auc"), baseline.get("auc")),
        "topn_return_delta_vs_global": candidates.delta(
            candidate_topn.get("avg_topn_future_return"),
            baseline_topn.get("avg_topn_future_return"),
        ),
        "topn_uplift": candidate_topn.get("topn_minus_universe_return"),
        "topn_return": candidate_topn.get("avg_topn_future_return"),
    }


def family_decision(
    *,
    family_result: dict[str, Any],
    selected_variant: str,
    baseline: dict[str, Any],
    selected: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    deltas = metric_delta(selected, baseline)
    failures: list[str] = []
    if selected.get("status") != "OK":
        failures.append(f"selected_variant_not_ok:{selected.get('reason')}")
    if int(selected.get("sealed_family_dates") or 0) < args.min_sealed_family_dates:
        failures.append(f"sealed_family_dates<{args.min_sealed_family_dates}")
    if int(selected.get("sealed_rows") or 0) < args.min_sealed_samples:
        failures.append(f"sealed_rows<{args.min_sealed_samples}")
    if int(selected.get("positive_labels") or 0) < args.min_positive_labels:
        failures.append(f"positive_labels<{args.min_positive_labels}")
    if int(selected.get("negative_labels") or 0) < args.min_negative_labels:
        failures.append(f"negative_labels<{args.min_negative_labels}")
    if selected.get("auc") is None or float(selected.get("auc")) < args.min_auc:
        failures.append(f"auc<{args.min_auc}")
    if deltas["topn_uplift"] is None or float(deltas["topn_uplift"]) <= args.min_topn_uplift:
        failures.append(f"topn_uplift<={args.min_topn_uplift}")
    if deltas["topn_return"] is None or float(deltas["topn_return"]) <= args.min_candidate_topn_return:
        failures.append(f"topn_return<={args.min_candidate_topn_return}")
    if deltas["auc_delta_vs_global"] is None or float(deltas["auc_delta_vs_global"]) < args.min_delta_auc:
        failures.append(f"auc_delta<{args.min_delta_auc}")
    if deltas["topn_return_delta_vs_global"] is None or float(deltas["topn_return_delta_vs_global"]) < args.min_delta_topn_return:
        failures.append(f"topn_return_delta<{args.min_delta_topn_return}")

    source_decision = family_result.get("decision")
    if source_decision != candidates.DECISION_PROMOTE:
        failures.append(f"source_candidate_not_promote:{source_decision}")

    if failures:
        decision = DECISION_MONITOR if selected.get("status") == "OK" else DECISION_REJECTED
        rationale = "sealed replay 尚未通過 gate：" + ", ".join(failures)
    else:
        decision = DECISION_PASS
        rationale = "候選在固定 sealed replay 視窗相對 global baseline 仍有正向增益；可進下一階段模型實驗 review。"
    return {
        "decision": decision,
        "decision_rationale": rationale,
        "selected_candidate_variant": selected_variant,
        "diagnostics": deltas,
        "failures": failures,
    }


def build_family_result(
    *,
    family: str,
    frame: pd.DataFrame,
    features: list[str],
    split: SplitDates,
    candidate_family: dict[str, Any],
    args: argparse.Namespace,
) -> dict[str, Any]:
    selected_variant = str(candidate_family.get("selected_candidate_variant") or "family_only_training")
    variants = {
        variant: score_variant(
            frame=frame,
            features=features,
            family=family,
            split=split,
            variant=variant,
            args=args,
        )
        for variant in VARIANTS
    }
    baseline = variants["global_baseline"]
    selected = variants.get(selected_variant, variants["family_only_training"])
    result = {
        "family": family,
        "source_candidate_decision": candidate_family.get("decision"),
        "source_candidate_variant": selected_variant,
        "sealed_family_date_count": int(
            frame[frame["trade_date"].isin(split.sealed_dates) & frame[f"family_{family}"]]["trade_date"].nunique()
        ),
        "sealed_family_dates": [
            date_text(value)
            for value in sorted(
                frame[frame["trade_date"].isin(split.sealed_dates) & frame[f"family_{family}"]]["trade_date"].drop_duplicates()
            )
        ],
        "variants": variants,
    }
    result.update(
        family_decision(
            family_result=candidate_family,
            selected_variant=selected_variant,
            baseline=baseline,
            selected=selected,
            args=args,
        )
    )
    return result


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    candidate_path = resolve_path(args.candidate_artifact) or latest_candidate_artifact()
    if candidate_path is None:
        raise FileNotFoundError("找不到 regime_family_training_candidates_YYYY-MM-DD.json")
    candidate_payload = load_json(candidate_path)
    requested = requested_families(args, candidate_payload)
    frame_args = argparse.Namespace(
        data_dir=args.data_dir,
        market_regime_history=args.market_regime_history,
        horizon=args.horizon,
        threshold=args.threshold,
    )
    frame, features, _regimes = candidates.labeled_frame(frame_args, requested)
    split = build_split(frame, args)
    family_lookup = candidate_family_by_id(candidate_payload)
    families = [
        build_family_result(
            family=family,
            frame=frame,
            features=features,
            split=split,
            candidate_family=family_lookup.get(family, {}),
            args=args,
        )
        for family in requested
    ]
    passed = [row for row in families if row.get("decision") == DECISION_PASS]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "date": args.date,
        "status": "OK",
        "decision": DECISION_PASS if passed else DECISION_MONITOR,
        "decision_rationale": "本 artifact 只確認 regime family 候選是否可進下一階段模型實驗 review；不允許 production promotion。",
        "layer": "model",
        "pre_registered": True,
        "contract": {
            "research_only": True,
            "in_memory_models_only": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_risk_adjusted_score": True,
            "does_not_change_production_ranking": True,
            "production_promotion_allowed": False,
            "promotion_requires_manual_review": True,
            "taxonomy": {
                "base_regime_labels": candidates.BASE_REGIME_LABELS,
                "base_regime_mutually_exclusive": True,
                "regime_family_tags": candidates.REGIME_FAMILY_TAGS,
                "requested_family_tags": requested,
                "family_tags_are_not_base_regimes": True,
                "family_tags_are_not_mutually_exclusive": True,
                "do_not_add_family_tag_without_contract_change": True,
            },
            "no_hindsight_policy": {
                "uses_fixed_candidate_artifact": True,
                "family_definitions_pre_registered": True,
                "sealed_split_fixed_before_scoring": True,
                "train_dates_end_before_sealed_start": True,
                "embargo_trade_days": args.embargo_trade_days,
                "diagnostic_failures_cannot_define_same_run_filters": True,
                "passing_this_gate_does_not_allow_production_promotion": True,
            },
        },
        "decision_policy": {
            "sealed_trade_days": args.sealed_trade_days,
            "min_train_trade_days": args.min_train_trade_days,
            "min_sealed_family_dates": args.min_sealed_family_dates,
            "min_sealed_samples": args.min_sealed_samples,
            "min_positive_labels": args.min_positive_labels,
            "min_negative_labels": args.min_negative_labels,
            "min_auc": args.min_auc,
            "min_topn_uplift": args.min_topn_uplift,
            "min_candidate_topn_return": args.min_candidate_topn_return,
            "min_delta_auc": args.min_delta_auc,
            "min_delta_topn_return": args.min_delta_topn_return,
        },
        "split": {
            "train_start_date": split.train_start,
            "train_end_date": split.train_end,
            "train_trade_days": len(split.train_dates),
            "embargo_start_date": date_text(split.embargo_dates[0]) if split.embargo_dates else None,
            "embargo_end_date": date_text(split.embargo_dates[-1]) if split.embargo_dates else None,
            "embargo_trade_days": len(split.embargo_dates),
            "sealed_start_date": split.sealed_start,
            "sealed_end_date": split.sealed_end,
            "sealed_trade_days": len(split.sealed_dates),
        },
        "inputs": {
            "candidate_artifact": repo_path(candidate_path),
            "data_dir": repo_path(resolve_path(args.data_dir)),
            "market_regime_history": repo_path(resolve_path(args.market_regime_history)),
            "families": requested,
            "horizon": args.horizon,
            "threshold": args.threshold,
            "top_n": args.top_n,
            "num_boost_round": args.num_boost_round,
            "family_weight": args.family_weight,
        },
        "summary": {
            "rows": int(len(frame)),
            "stocks": int(frame["stock_id"].nunique()),
            "dates": int(frame["trade_date"].nunique()),
            "feature_count": len(features),
            "families": {
                row["family"]: {
                    "decision": row["decision"],
                    "sealed_family_date_count": row["sealed_family_date_count"],
                    "selected_candidate_variant": row["selected_candidate_variant"],
                    "auc_delta_vs_global": row["diagnostics"]["auc_delta_vs_global"],
                    "topn_return_delta_vs_global": row["diagnostics"]["topn_return_delta_vs_global"],
                    "topn_uplift": row["diagnostics"]["topn_uplift"],
                }
                for row in families
            },
        },
        "families": families,
    }


def write_markdown(payload: dict[str, Any], output: Path) -> None:
    lines = [
        "# Regime Family Sealed Replay",
        "",
        f"- status: {payload['status']}",
        f"- decision: {payload['decision']}",
        f"- candidate_artifact: {payload['inputs']['candidate_artifact']}",
        f"- sealed: {payload['split']['sealed_start_date']} ~ {payload['split']['sealed_end_date']}",
        f"- train_end: {payload['split']['train_end_date']}",
        "",
        "## Families",
    ]
    for family in payload.get("families", []):
        diag = family.get("diagnostics", {})
        lines.extend(
            [
                "",
                f"### {family['family']}",
                f"- decision: {family['decision']}",
                f"- selected_variant: {family['selected_candidate_variant']}",
                f"- sealed_family_dates: {family['sealed_family_date_count']}",
                f"- auc_delta_vs_global: {diag.get('auc_delta_vs_global')}",
                f"- topn_return_delta_vs_global: {diag.get('topn_return_delta_vs_global')}",
                f"- topn_uplift: {diag.get('topn_uplift')}",
                f"- rationale: {family['decision_rationale']}",
            ]
        )
    output.with_suffix(".md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output) or OUTPUT_DIR / f"regime_family_sealed_replay_{args.date}.json"
    payload = build_payload(args)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    write_markdown(payload, output)
    print(json.dumps({"status": payload["status"], "decision": payload["decision"], "output": repo_path(output), "summary": payload["summary"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
