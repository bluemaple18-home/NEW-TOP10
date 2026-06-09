#!/usr/bin/env python3
"""重放研究用 guarded Top10 policy。

此腳本只讀既有 features 與目前模型，輸出 shadow research artifact；
不得覆蓋正式 ranking、模型或自動推播來源。
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.agent_b_ranking import StockRanker  # noqa: E402


SCHEMA_VERSION = "guarded-top10-replay.v1"
CANDIDATE_POOL_SIZE_CONTRACT = 80
CANDIDATE_POOL_RULE = "model_inference_top80_before_guard"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="replay guarded Top10 policy as research-only shadow output")
    parser.add_argument("--date", action="append", default=[], help="交易日 YYYY-MM-DD；可重複指定")
    parser.add_argument("--start-date", default=None, help="批次 replay 起日 YYYY-MM-DD")
    parser.add_argument("--end-date", default=None, help="批次 replay 迄日 YYYY-MM-DD")
    parser.add_argument("--data-dir", default="data/clean")
    parser.add_argument("--model-dir", default="models")
    parser.add_argument("--model", default="latest_lgbm.pkl")
    parser.add_argument("--config", default="config/signals.yaml")
    parser.add_argument("--output-dir", default="artifacts/research")
    parser.add_argument(
        "--candidate-pool-size",
        type=int,
        default=CANDIDATE_POOL_SIZE_CONTRACT,
        choices=[CANDIDATE_POOL_SIZE_CONTRACT],
        help="固定 Top80 candidate pool contract；非 80 會被拒絕",
    )
    parser.add_argument("--top-n", type=int, default=10)
    parser.add_argument("--max-dates", type=int, default=None)
    return parser.parse_args()


def resolve_path(value: str | Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else PROJECT_ROOT / path


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def selected_dates(args: argparse.Namespace, data_dir: Path) -> list[str]:
    dates = [normalize_date(value) for value in args.date]
    if args.start_date or args.end_date:
        if not args.start_date or not args.end_date:
            raise ValueError("--start-date 與 --end-date 需同時指定")
        dates.extend(trade_dates(data_dir, args.start_date, args.end_date))
    unique = sorted(set(dates))
    if args.max_dates is not None:
        unique = unique[: max(args.max_dates, 0)]
    if not unique:
        raise ValueError("請指定 --date，或同時指定 --start-date/--end-date")
    return unique


def normalize_date(value: str) -> str:
    return pd.to_datetime(value).strftime("%Y-%m-%d")


def trade_dates(data_dir: Path, start_date: str, end_date: str) -> list[str]:
    features_path = data_dir / "features.parquet"
    if not features_path.exists():
        raise FileNotFoundError(f"features parquet 不存在：{features_path}")
    frame = pd.read_parquet(features_path, columns=["date"])
    dates = pd.to_datetime(frame["date"], errors="coerce").dropna().dt.normalize().drop_duplicates().sort_values()
    start = pd.to_datetime(start_date).normalize()
    end = pd.to_datetime(end_date).normalize()
    return [item.strftime("%Y-%m-%d") for item in dates if start <= item <= end]


def stock_names(stock_ids: pd.Series) -> list[str]:
    try:
        from app.stock_names import get_stock_name
    except ImportError:
        from stock_names import get_stock_name
    return [get_stock_name(str(stock_id)) for stock_id in stock_ids]


def replay_date(
    ranker: StockRanker,
    date_text: str,
    candidate_pool_size: int,
    top_n: int,
    output_dir: Path,
    args: argparse.Namespace,
) -> dict[str, Any]:
    ensure_candidate_pool_contract(candidate_pool_size)
    daily_df, history_df = ranker.load_daily_data(date_text)
    if daily_df.empty:
        raise ValueError(f"{date_text} 沒有可排名資料")

    scored = ranker.calculate_scores(daily_df)
    scored = scored.reset_index(drop=True)
    scored["candidate_rank"] = range(1, len(scored) + 1)
    candidate_pool = scored.head(candidate_pool_size).copy()
    target_for_regime = daily_df["date"].max() if "date" in daily_df else pd.to_datetime(date_text)
    market_regime = ranker.market_regime_service.evaluate(history_df, target_date=target_for_regime)

    guarded_ranked = ranker.ranking_policy.apply(
        candidate_pool,
        market_regime,
        apply_selection_guards=True,
    ).copy()
    guarded_ranked = guarded_ranked.reset_index(drop=True)
    guarded_ranked["guarded_rank"] = range(1, len(guarded_ranked) + 1)
    guarded_top = guarded_ranked.head(top_n).copy()
    guarded_top = ranker.portfolio_policy.apply(guarded_top, market_regime)
    guarded_top["guarded_rank"] = range(1, len(guarded_top) + 1)
    if "stock_name" not in guarded_top.columns or guarded_top["stock_name"].isna().any():
        guarded_top["stock_name"] = stock_names(guarded_top["stock_id"])

    model_top = candidate_pool.head(top_n).copy()
    model_top_ids = stock_id_list(model_top)
    guarded_top_ids = stock_id_list(guarded_top)
    output_json = output_dir / f"guarded_top10_replay_{date_text}.json"
    output_md = output_dir / f"guarded_top10_replay_{date_text}.md"

    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "task_id": "GUARDED-TOP10-REPLAY-01",
        "ranking_date": date_text,
        "contract": {
            "research_only": True,
            "does_not_train_model": True,
            "does_not_write_models_latest_lgbm": True,
            "does_not_change_production_ranking": True,
            "does_not_change_publish_source": True,
            "candidate_pool_rule": CANDIDATE_POOL_RULE,
            "guard_policy_source": "app.trading.ranking_policy.RankingPolicy",
            "tape_guard_source": "app.trading.tape_guard.add_tape_guard_columns",
            "chase_guard_boundary": "rr_guard WAIT_PULLBACK/WAIT_CONFIRM from RankingPolicy",
        },
        "inputs": {
            "data_dir": repo_path(resolve_path(args.data_dir)),
            "model": repo_path(resolve_path(args.model_dir) / args.model),
            "config": repo_path(resolve_path(args.config)),
            "date": date_text,
            "candidate_pool_size": candidate_pool_size,
            "top_n": top_n,
        },
        "outputs": {
            "json": repo_path(output_json),
            "markdown": repo_path(output_md),
        },
        "market_regime": {
            "label": market_regime.label,
            "risk_multiplier": clean_value(market_regime.risk_multiplier),
            "breadth_ma20": clean_value(market_regime.breadth_ma20),
        },
        "summary": build_summary(
            candidate_pool=candidate_pool,
            guarded_ranked=guarded_ranked,
            guarded_top=guarded_top,
            model_top_ids=model_top_ids,
            guarded_top_ids=guarded_top_ids,
            top_n=top_n,
        ),
        "model_top10_before_guard": rows_from_frame(model_top, rank_column="candidate_rank"),
        "candidate_pool_top80": rows_from_frame(candidate_pool, rank_column="candidate_rank"),
        "shadow_guarded_top10": rows_from_frame(guarded_top, rank_column="guarded_rank"),
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    output_json.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8")
    output_md.write_text(render_markdown(payload), encoding="utf-8")
    return payload


def stock_id_list(frame: pd.DataFrame) -> list[str]:
    if "stock_id" not in frame.columns:
        return []
    return [str(value).strip().replace(".0", "").zfill(4) for value in frame["stock_id"].tolist()]


def ensure_candidate_pool_contract(candidate_pool_size: int) -> None:
    """鎖定 replay 規格，避免後續績效比較混用不同候選池。"""
    if int(candidate_pool_size) != CANDIDATE_POOL_SIZE_CONTRACT:
        raise ValueError(
            f"candidate_pool_size must be {CANDIDATE_POOL_SIZE_CONTRACT} "
            f"for guarded Top80 replay contract; got {candidate_pool_size}"
        )


def build_summary(
    candidate_pool: pd.DataFrame,
    guarded_ranked: pd.DataFrame,
    guarded_top: pd.DataFrame,
    model_top_ids: list[str],
    guarded_top_ids: list[str],
    top_n: int,
) -> dict[str, Any]:
    tape_counts = value_counts(guarded_ranked, "tape_guard_action")
    rr_counts = value_counts(guarded_ranked, "rr_guard_action")
    allowed_mask = guarded_ranked.get("tape_guard_action", pd.Series(index=guarded_ranked.index, dtype=object)).fillna("") != "EXCLUDE"
    return {
        "candidate_pool_count": int(len(candidate_pool)),
        "guarded_ranked_count": int(len(guarded_ranked)),
        "shadow_top_count": int(len(guarded_top)),
        "top_n": int(top_n),
        "max_candidate_rank_in_shadow_top10": max((int(row.get("candidate_rank") or 0) for row in rows_from_frame(guarded_top)), default=0),
        "model_top10_ids_before_guard": model_top_ids,
        "shadow_guarded_top10_ids": guarded_top_ids,
        "added_vs_model_top10": [stock_id for stock_id in guarded_top_ids if stock_id not in model_top_ids],
        "removed_vs_model_top10": [stock_id for stock_id in model_top_ids if stock_id not in guarded_top_ids],
        "tape_guard_counts_in_candidate_pool": tape_counts,
        "rr_guard_counts_in_candidate_pool": rr_counts,
        "chase_guard_count_in_candidate_pool": int(
            guarded_ranked.get("rr_guard_action", pd.Series(index=guarded_ranked.index, dtype=object))
            .fillna("")
            .isin(["WAIT_PULLBACK", "WAIT_CONFIRM"])
            .sum()
        ),
        "allowed_candidate_count": int(allowed_mask.sum()),
        "shadow_top_has_tape_exclude": bool(
            guarded_top.get("tape_guard_action", pd.Series(index=guarded_top.index, dtype=object)).fillna("").eq("EXCLUDE").any()
        ),
    }


def value_counts(frame: pd.DataFrame, column: str) -> dict[str, int]:
    if column not in frame.columns:
        return {}
    counts = frame[column].fillna("UNKNOWN").astype(str).value_counts()
    return {str(key): int(value) for key, value in counts.items()}


def rows_from_frame(frame: pd.DataFrame, rank_column: str | None = None) -> list[dict[str, Any]]:
    columns = [
        "candidate_rank",
        "guarded_rank",
        "stock_id",
        "stock_name",
        "open",
        "high",
        "low",
        "close",
        "prev_close",
        "return_pct",
        "model_prob",
        "raw_prob",
        "final_score",
        "rule_score",
        "rule_score_norm",
        "prediction_score",
        "setup_score",
        "quality_score",
        "risk_penalty",
        "risk_adjusted_score",
        "tape_guard_action",
        "limit_state",
        "tape_guard_reason",
        "risk_reward",
        "execution_risk_reward",
        "risk_reward_score",
        "rr_guard_action",
        "rr_guard_reason",
        "suggested_weight",
        "max_position_weight",
        "gross_exposure",
        "market_regime",
        "reasons",
    ]
    rows: list[dict[str, Any]] = []
    for _, row in frame.iterrows():
        item = {column: clean_value(row.get(column)) for column in columns if column in frame.columns}
        if rank_column and rank_column in item:
            item["rank"] = item[rank_column]
        if "stock_id" in item:
            item["stock_id"] = str(item["stock_id"]).strip().replace(".0", "").zfill(4)
        rows.append(item)
    return rows


def clean_value(value: Any) -> Any:
    if isinstance(value, pd.Timestamp):
        return value.strftime("%Y-%m-%d")
    if isinstance(value, dict):
        return {str(key): clean_value(val) for key, val in value.items()}
    if isinstance(value, (list, tuple)):
        return [clean_value(item) for item in value]
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        return clean_value(value.item())
    return value


def render_markdown(payload: dict[str, Any]) -> str:
    summary = payload["summary"]
    lines = [
        f"# Guarded Top10 Replay | {payload['ranking_date']}",
        "",
        f"- status: `{payload['status']}`",
        f"- research_only: `{payload['contract']['research_only']}`",
        f"- model: `{payload['inputs']['model']}`",
        f"- candidate_pool: `{summary['candidate_pool_count']}` from model Top80 before guard",
        f"- market_regime: `{payload['market_regime']['label']}` risk_multiplier={payload['market_regime']['risk_multiplier']}",
        f"- changed_vs_model_top10: added `{summary['added_vs_model_top10']}` removed `{summary['removed_vs_model_top10']}`",
        f"- tape_guard_counts: `{summary['tape_guard_counts_in_candidate_pool']}`",
        f"- rr_guard_counts: `{summary['rr_guard_counts_in_candidate_pool']}`",
        "",
        "## Shadow Guarded Top10",
        "",
        "| rank | candidate_rank | stock | model_prob | risk_adjusted | tape | rr | close |",
        "| ---: | ---: | --- | ---: | ---: | --- | --- | ---: |",
    ]
    for item in payload["shadow_guarded_top10"]:
        lines.append(
            "| {rank} | {candidate_rank} | {stock_id} {stock_name} | {model_prob} | {risk_adjusted} | {tape} | {rr} | {close} |".format(
                rank=item.get("guarded_rank") or item.get("rank"),
                candidate_rank=item.get("candidate_rank"),
                stock_id=item.get("stock_id"),
                stock_name=item.get("stock_name") or "",
                model_prob=num(item.get("model_prob")),
                risk_adjusted=num(item.get("risk_adjusted_score")),
                tape=item.get("tape_guard_action") or "",
                rr=item.get("rr_guard_action") or "",
                close=num(item.get("close")),
            )
        )
    lines.extend(
        [
            "",
            "## Contract",
            "",
            "- Output stays under `artifacts/research/`.",
            "- No production `artifacts/ranking_YYYY-MM-DD.csv` is written.",
            "- No model file or publish source is changed.",
            "",
        ]
    )
    return "\n".join(lines)


def num(value: Any) -> str:
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "--"


def build_payload(args: argparse.Namespace) -> dict[str, Any]:
    data_dir = resolve_path(args.data_dir)
    model_dir = resolve_path(args.model_dir)
    config_path = resolve_path(args.config)
    output_dir = resolve_path(args.output_dir)
    ensure_candidate_pool_contract(args.candidate_pool_size)
    dates = selected_dates(args, data_dir)
    ranker = StockRanker(
        data_dir=str(data_dir),
        model_dir=str(model_dir),
        artifact_dir=str(output_dir),
        config_path=str(config_path),
        generate_report=False,
        explain_top_n=0,
    )
    ranker.load_model(args.model)
    outputs: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for date_text in dates:
        try:
            payload = replay_date(
                ranker=ranker,
                date_text=date_text,
                candidate_pool_size=args.candidate_pool_size,
                top_n=max(1, args.top_n),
                output_dir=output_dir,
                args=args,
            )
            outputs.append(
                {
                    "date": date_text,
                    "json": payload["outputs"]["json"],
                    "markdown": payload["outputs"]["markdown"],
                    "shadow_top_count": payload["summary"]["shadow_top_count"],
                }
            )
        except Exception as exc:
            failures.append({"date": date_text, "error": str(exc)})
    return {
        "status": "OK" if not failures else "FAILED",
        "dates": dates,
        "outputs": outputs,
        "failures": failures,
    }


def main() -> int:
    args = parse_args()
    result = build_payload(args)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
