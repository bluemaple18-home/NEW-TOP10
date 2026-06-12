#!/usr/bin/env python3
"""產生 5913 combo research result review artifact。

這支腳本只審核既有 autonomous research 結果，不重跑 replay、不訓練模型、
不修改 production ranking。
"""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_HISTORY_PATH = PROJECT_ROOT / "artifacts" / "autonomous_research" / "run_history.jsonl"
PROGRESS_PATH = PROJECT_ROOT / "artifacts" / "autonomous_research" / "research_campaign_progress_2026-06-11.json"
FOG_MAP_PATH = PROJECT_ROOT / "artifacts" / "research_map" / "research_fog_map_latest.json"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "research_reviews"
SCHEMA_VERSION = "5913-combo-effectiveness-review.v1"
PRODUCTION_IMPACT = "NO_PRODUCTION_CHANGE"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build 5913 combo effectiveness review")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--output-dir", default=str(OUTPUT_DIR))
    return parser.parse_args()


def repo_path(path: Path | None) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            value = {"line_number": line_number, "status": "INVALID_JSON"}
        if isinstance(value, dict):
            rows.append(value)
    return rows


def write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def load_matrix_cache(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    cache: dict[str, dict[str, Any]] = {}
    for row in rows:
        artifact_path = str(row.get("artifact_path") or "")
        if not artifact_path or artifact_path in cache:
            continue
        path = PROJECT_ROOT / artifact_path
        if not path.exists():
            cache[artifact_path] = {}
            continue
        try:
            cache[artifact_path] = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            cache[artifact_path] = {}
    return cache


def scenario_metrics(row: dict[str, Any], matrix_cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    matrix = matrix_cache.get(str(row.get("artifact_path") or ""), {})
    scenarios = matrix.get("scenarios") if isinstance(matrix.get("scenarios"), list) else []
    scenario_id = str(row.get("scenario_id") or "")
    scenario = next((item for item in scenarios if isinstance(item, dict) and item.get("scenario_id") == scenario_id), {})
    return {
        "trade_count": scenario.get("trade_count"),
        "win_rate": scenario.get("win_rate"),
        "total_return": scenario.get("total_return"),
        "max_drawdown": scenario.get("max_drawdown"),
        "max_gross_exposure": scenario.get("max_gross_exposure"),
        "max_group_exposure_observed": scenario.get("max_group_exposure_observed"),
        "exit_reason_counts": scenario.get("exit_reason_counts") or {},
    }


def dimension_text(dimensions: dict[str, Any]) -> str:
    return (
        f"h{dimensions.get('horizon')}, stop={dimensions.get('stop_loss')}, "
        f"tp={dimensions.get('take_profit')}, group={dimensions.get('group_exposure')}"
    )


def infer_rules(row: dict[str, Any], node: dict[str, Any]) -> dict[str, str]:
    candidate_dir = str(row.get("candidate_dir") or node.get("candidate_dir") or "")
    text = candidate_dir.lower()
    dimensions = row.get("dimensions") if isinstance(row.get("dimensions"), dict) else {}
    if "liquidity_quality" in text:
        liquidity_rule = "liquidity_quality_candidate_universe"
    elif "volume" in text or "turnover" in text:
        liquidity_rule = "volume_or_turnover_filter"
    else:
        liquidity_rule = "not_explicit"

    if "regime_guard" in text:
        regime_gate = "regime_guard"
    elif "regime_overlay" in text:
        regime_gate = "regime_overlay"
    elif "big_bull" in text:
        regime_gate = "big_bull_context"
    else:
        regime_gate = "not_explicit"

    if "sector_cap" in text:
        sector_rule = "sector_cap"
    elif "sector_context" in text or "feature_group" in text:
        sector_rule = "sector_or_feature_group_context"
    else:
        sector_rule = "not_explicit"

    if "candidate_subset" in text:
        entry_filter = "candidate_subset"
    elif "no_setup" in text:
        entry_filter = "no_setup"
    elif "stop_smo" in text:
        entry_filter = "liquidity_stop_smoothing"
    elif "smoke_20" in text:
        entry_filter = "liquidity_smoke_20"
    else:
        entry_filter = "ranking_variant"

    return {
        "ranking_source": candidate_dir,
        "entry_filter": entry_filter,
        "exit_rule": f"horizon={dimensions.get('horizon')}; stop_loss={dimensions.get('stop_loss')}; take_profit={dimensions.get('take_profit')}",
        "capital_rule": f"group_exposure={dimensions.get('group_exposure')}",
        "regime_gate": regime_gate,
        "sector_concentration_rule": sector_rule,
        "liquidity_rule": liquidity_rule,
        "tape_rr_chase_guard": "not_available_in_run_history",
        "outcome_horizon": str(dimensions.get("horizon") or ""),
    }


def classify_row(row: dict[str, Any], topic_stats: dict[str, dict[str, Any]]) -> str:
    insight = str(row.get("insight_level") or "")
    score_delta = safe_float(row.get("score_delta"))
    return_delta = safe_float(row.get("return_delta"))
    drawdown_delta = safe_float(row.get("drawdown_delta"))
    stats = topic_stats.get(str(row.get("topic_id") or ""), {})
    stable_topic = int(stats.get("effective_count") or 0) >= 6
    if insight == "effective" and stable_topic and score_delta >= 0.08 and return_delta > 0 and drawdown_delta >= 0:
        return "KEEP_FOR_NEXT_REPLAY"
    if insight in {"effective", "risk_worse_return_positive"}:
        return "MONITOR_ONLY"
    if insight == "ordinary":
        return "LOW_INFORMATION"
    return "REJECTED_OR_DO_NOT_PROMOTE"


def row_summary(row: dict[str, Any], node: dict[str, Any], matrix_cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    dimensions = row.get("dimensions") if isinstance(row.get("dimensions"), dict) else {}
    return {
        "combo_id": row.get("combo_id"),
        "topic_id": row.get("topic_id"),
        "family": node.get("family"),
        "family_label": node.get("family_label"),
        "candidate_dir": row.get("candidate_dir") or node.get("candidate_dir"),
        "dimensions": dimensions,
        "dimension_summary": dimension_text(dimensions),
        "insight_level": row.get("insight_level"),
        "decision": row.get("decision"),
        "return_delta": row.get("return_delta"),
        "drawdown_delta": row.get("drawdown_delta"),
        "score_delta": row.get("score_delta"),
        "sample_size": {
            "ranking_file_count": node.get("ranking_file_count"),
            "trade_count": scenario_metrics(row, matrix_cache).get("trade_count"),
            "evidence_level": row.get("evidence_level"),
        },
        "risk": {
            "max_gross_exposure": scenario_metrics(row, matrix_cache).get("max_gross_exposure"),
            "max_group_exposure_observed": scenario_metrics(row, matrix_cache).get("max_group_exposure_observed"),
            "win_rate": scenario_metrics(row, matrix_cache).get("win_rate"),
            "exit_reason_counts": scenario_metrics(row, matrix_cache).get("exit_reason_counts"),
        },
        "rules": infer_rules(row, node),
        "artifact_path": row.get("artifact_path"),
        "review_note": review_note(row),
    }


def review_note(row: dict[str, Any]) -> str:
    insight = str(row.get("insight_level") or "")
    return_delta = safe_float(row.get("return_delta"))
    drawdown_delta = safe_float(row.get("drawdown_delta"))
    score_delta = safe_float(row.get("score_delta"))
    if insight == "risk_worse_return_positive":
        return "報酬改善伴隨 drawdown 惡化，只能觀察，不可直接採用。"
    if insight == "ordinary":
        return "資訊量不足或 score 改善無法轉成可解釋 edge。"
    if insight == "rejected":
        if return_delta > 0 and drawdown_delta < 0:
            return "單看報酬容易誤導，風險調整後已被 strategy matrix 淘汰。"
        return "相對 baseline 缺乏可用 edge，列入不可升級清單。"
    if score_delta >= 0.08 and drawdown_delta >= 0:
        return "具備正向 score、return、drawdown 組合，值得進下一輪嚴格 replay。"
    return "有效訊號偏弱或不夠穩定，暫列 monitor。"


def build_topic_stats(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row.get("topic_id") or "")].append(row)
    stats: dict[str, dict[str, Any]] = {}
    for topic_id, items in grouped.items():
        effective = [row for row in items if row.get("insight_level") == "effective"]
        followup = [row for row in items if row.get("insight_level") == "risk_worse_return_positive"]
        rejected = [row for row in items if row.get("insight_level") == "rejected"]
        stats[topic_id] = {
            "total": len(items),
            "effective_count": len(effective),
            "followup_count": len(followup),
            "rejected_count": len(rejected),
            "avg_effective_score_delta": round(sum(safe_float(row.get("score_delta")) for row in effective) / len(effective), 6) if effective else 0,
            "max_score_delta": max((safe_float(row.get("score_delta")) for row in items), default=0),
            "avg_return_delta": round(sum(safe_float(row.get("return_delta")) for row in items) / len(items), 6) if items else 0,
            "avg_drawdown_delta": round(sum(safe_float(row.get("drawdown_delta")) for row in items) / len(items), 6) if items else 0,
        }
    return stats


def aggregate_topic_components(
    rows: list[dict[str, Any]],
    nodes: dict[str, dict[str, Any]],
    classifications: dict[str, str],
) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        if classifications.get(str(row.get("combo_id"))) == "KEEP_FOR_NEXT_REPLAY":
            grouped[str(row.get("topic_id") or "")].append(row)
    components: list[dict[str, Any]] = []
    for topic_id, items in grouped.items():
        node = nodes.get(topic_id, {})
        best = max(items, key=lambda row: safe_float(row.get("score_delta")))
        dimensions = [row.get("dimensions") for row in items if isinstance(row.get("dimensions"), dict)]
        components.append(
            {
                "topic_id": topic_id,
                "family": node.get("family"),
                "family_label": node.get("family_label"),
                "candidate_dir": node.get("candidate_dir") or best.get("candidate_dir"),
                "kept_combo_count": len(items),
                "best_score_delta": best.get("score_delta"),
                "best_return_delta": best.get("return_delta"),
                "best_drawdown_delta": best.get("drawdown_delta"),
                "dominant_horizons": dict(Counter(str(dim.get("horizon")) for dim in dimensions).most_common()),
                "dominant_take_profit": dict(Counter(str(dim.get("take_profit")) for dim in dimensions).most_common()),
                "component_hypothesis": component_hypothesis(node.get("candidate_dir") or best.get("candidate_dir") or ""),
                "required_next_test": "same exit/capital/cost/exposure/regime-normalized replay before any strategy registry use",
            }
        )
    return sorted(components, key=lambda item: (int(item["kept_combo_count"]), safe_float(item["best_score_delta"])), reverse=True)


def component_hypothesis(candidate_dir: str) -> str:
    text = candidate_dir.lower()
    if "liquidity_quality" in text:
        return "流動性品質 universe 可能改善短週期候選品質，但需驗證交易成本與樣本外穩定性。"
    if "regime_overlay" in text:
        return "regime overlay 可能在部分情境提高排序品質，但需拆出 market-state normalization。"
    if "regime_guard" in text:
        return "regime guard 可能降低錯誤進場，但訊號較弱，需監控。"
    if "sector" in text or "feature_group" in text:
        return "產業/feature group 約束可能降低集中風險，但須確認不是 window-specific。"
    return "ranking source 有局部正向訊號，需在嚴格 replay 中確認可複用性。"


def summarize_by_dimension(rows: list[dict[str, Any]], classifications: dict[str, str]) -> dict[str, Any]:
    output: dict[str, Any] = {}
    for key in ["horizon", "stop_loss", "take_profit", "group_exposure"]:
        counter: dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            dimensions = row.get("dimensions") if isinstance(row.get("dimensions"), dict) else {}
            counter[str(dimensions.get(key))][classifications.get(str(row.get("combo_id")), "UNKNOWN")] += 1
        output[key] = {value: dict(counts) for value, counts in sorted(counter.items())}
    return output


def build_markdown(payload: dict[str, Any]) -> str:
    summary = payload["executive_summary"]
    top_components = payload["strategy_component_candidates"][:5]
    misleading = payload["do_not_promote"][:5]
    queue = payload["next_replay_queue"][:12]
    lines = [
        "# 5913 組合有效性審核",
        "",
        "## Executive Summary",
        "",
        f"- Review status: `{payload['status']}`",
        f"- Input: {payload['input_processed_combos']} / {payload['input_total_combos']} combos processed",
        f"- Effective 原始數量: {summary['raw_effective_count']}；保留進 next replay: {summary['effective_kept_for_next_replay']}",
        f"- Follow-up 原始數量: {summary['raw_followup_count']}；全部列入 monitor，不視為可升級訊號",
        f"- 明確淘汰 / do-not-promote: {summary['rejected_or_do_not_promote_count']}",
        f"- Production impact: `{payload['production_impact']}`",
        "",
        "結論：5913 組已完成地圖與批次回填，但只能產生研究審核結論。`effective_insight` 代表值得看，不代表可直接上線；本報告沒有提出任何 production ranking、模型或 live push 變更。",
        "",
        "## Top Useful Findings",
        "",
    ]
    for index, item in enumerate(top_components, start=1):
        lines.append(
            f"{index}. `{item['topic_id']}`：保留 {item['kept_combo_count']} 組，"
            f"best score_delta={item['best_score_delta']}, return_delta={item['best_return_delta']}, "
            f"drawdown_delta={item['best_drawdown_delta']}。{item['component_hypothesis']}"
        )
    lines.extend(["", "## Rejected / Misleading Findings", ""])
    for index, item in enumerate(misleading, start=1):
        lines.append(
            f"{index}. `{item['combo_id']}`：{item['review_note']} "
            f"return_delta={item['return_delta']}, drawdown_delta={item['drawdown_delta']}, score_delta={item['score_delta']}."
        )
    lines.extend(["", "## Next Replay Queue", ""])
    for index, item in enumerate(queue, start=1):
        lines.append(
            f"{index}. `{item['topic_id']}` / {item['dimension_summary']}："
            f"score_delta={item['score_delta']}, return_delta={item['return_delta']}, "
            f"drawdown_delta={item['drawdown_delta']}；next test = same exit/capital/cost/exposure/regime-normalized replay."
        )
    lines.extend(
        [
            "",
            "## Strategy Component Candidates",
            "",
        ]
    )
    for index, item in enumerate(top_components, start=1):
        lines.append(
            f"{index}. `{item['candidate_dir']}`：{item['component_hypothesis']} "
            f"限制：{item['required_next_test']}."
        )
    lines.extend(
        [
            "",
            "## Production Impact",
            "",
            f"`{payload['production_impact']}`",
            "",
            "不改 `models/latest_lgbm.pkl`、不改 production ranking、不改 `risk_adjusted_score`、不改 Clawd live push。",
            "",
            "## Open Risks",
            "",
        ]
    )
    for risk in payload["open_risks"]:
        lines.append(f"- {risk}")
    lines.extend(
        [
            "",
            "## Classification Counts",
            "",
            "| Classification | Count |",
            "| --- | ---: |",
        ]
    )
    for key, value in payload["classification_counts"].items():
        lines.append(f"| `{key}` | {value} |")
    lines.append("")
    return "\n".join(lines)


def build_payload(date: str) -> dict[str, Any]:
    rows = read_jsonl(RUN_HISTORY_PATH)
    progress = read_json(PROGRESS_PATH)
    fog_map = read_json(FOG_MAP_PATH)
    nodes = {str(node.get("topic_id")): node for node in fog_map.get("nodes", []) if isinstance(node, dict)}
    topic_stats = build_topic_stats(rows)
    matrix_cache = load_matrix_cache(rows)
    classifications = {str(row.get("combo_id")): classify_row(row, topic_stats) for row in rows}
    classification_counts = Counter(classifications.values())
    raw_counts = Counter(str(row.get("insight_level") or "") for row in rows)

    top_candidates = [
        row_summary(row, nodes.get(str(row.get("topic_id")), {}), matrix_cache)
        for row in sorted(
            [row for row in rows if classifications.get(str(row.get("combo_id"))) == "KEEP_FOR_NEXT_REPLAY"],
            key=lambda item: (safe_float(item.get("score_delta")), safe_float(item.get("return_delta")), safe_float(item.get("drawdown_delta"))),
            reverse=True,
        )[:30]
    ]
    monitor_only = [
        row_summary(row, nodes.get(str(row.get("topic_id")), {}), matrix_cache)
        for row in sorted(
            [row for row in rows if classifications.get(str(row.get("combo_id"))) == "MONITOR_ONLY"],
            key=lambda item: (safe_float(item.get("score_delta")), safe_float(item.get("return_delta"))),
            reverse=True,
        )[:30]
    ]
    do_not_promote_rows = [
        row_summary(row, nodes.get(str(row.get("topic_id")), {}), matrix_cache)
        for row in sorted(
            [
                row
                for row in rows
                if classifications.get(str(row.get("combo_id"))) == "REJECTED_OR_DO_NOT_PROMOTE"
                or (row.get("insight_level") == "risk_worse_return_positive" and safe_float(row.get("drawdown_delta")) < 0)
            ],
            key=lambda item: (safe_float(item.get("score_delta")), safe_float(item.get("return_delta"))),
            reverse=True,
        )[:40]
    ]
    components = aggregate_topic_components(rows, nodes, classifications)
    next_replay_queue = top_candidates[:20]
    family_counts: dict[str, Counter[str]] = defaultdict(Counter)
    for row in rows:
        node = nodes.get(str(row.get("topic_id")), {})
        family_counts[str(node.get("family") or "unknown")][classifications.get(str(row.get("combo_id")), "UNKNOWN")] += 1

    input_summary = progress.get("summary") if isinstance(progress.get("summary"), dict) else {}
    payload = {
        "schema_version": SCHEMA_VERSION,
        "status": "OK",
        "review_date": date,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "inputs": {
            "run_history": repo_path(RUN_HISTORY_PATH),
            "progress": repo_path(PROGRESS_PATH),
            "fog_map": repo_path(FOG_MAP_PATH),
        },
        "input_total_combos": input_summary.get("total_combos", len(rows)),
        "input_processed_combos": input_summary.get("processed_combos", len(rows)),
        "raw_insight_counts": {
            "effective": raw_counts.get("effective", 0),
            "follow_up_signal": raw_counts.get("risk_worse_return_positive", 0),
            "rejected": raw_counts.get("rejected", 0),
            "low_information": raw_counts.get("ordinary", 0),
        },
        "classification_counts": {
            "KEEP_FOR_NEXT_REPLAY": classification_counts.get("KEEP_FOR_NEXT_REPLAY", 0),
            "MONITOR_ONLY": classification_counts.get("MONITOR_ONLY", 0),
            "LOW_INFORMATION": classification_counts.get("LOW_INFORMATION", 0),
            "REJECTED_OR_DO_NOT_PROMOTE": classification_counts.get("REJECTED_OR_DO_NOT_PROMOTE", 0),
        },
        "executive_summary": {
            "raw_effective_count": raw_counts.get("effective", 0),
            "effective_kept_for_next_replay": classification_counts.get("KEEP_FOR_NEXT_REPLAY", 0),
            "raw_followup_count": raw_counts.get("risk_worse_return_positive", 0),
            "followup_kept_for_monitor": raw_counts.get("risk_worse_return_positive", 0),
            "rejected_or_do_not_promote_count": classification_counts.get("REJECTED_OR_DO_NOT_PROMOTE", 0),
            "low_information_count": classification_counts.get("LOW_INFORMATION", 0),
            "production_conclusion": PRODUCTION_IMPACT,
        },
        "family_classification_counts": {family: dict(counts) for family, counts in sorted(family_counts.items())},
        "dimension_classification_counts": summarize_by_dimension(rows, classifications),
        "top_candidates": top_candidates,
        "next_replay_queue": next_replay_queue,
        "monitor_only": monitor_only,
        "strategy_component_candidates": components[:20],
        "do_not_promote": do_not_promote_rows,
        "production_impact": PRODUCTION_IMPACT,
        "open_risks": [
            "run_history 是 legacy strategy matrix backfill，仍需下一輪同 exit、同資金、同成本、同 exposure 的 replay 才能比較。",
            "部分 top score 來自同一候選 artifact 的多個 scenario，可能不是獨立訊號。",
            "目前缺少完整交易成本、滑價、換手與 regime-normalized attribution。",
            "trade_count 與 ranking_file_count 偏小的候選只能做研究排序，不能直接視為穩定策略。",
            "follow-up signal 的共同特徵是 return 改善但 drawdown 惡化，容易被單看報酬誤用。",
        ],
        "generated_artifacts": {
            "json": f"artifacts/research_reviews/5913_combo_effectiveness_review_{date}.json",
            "markdown": f"artifacts/research_reviews/5913_combo_effectiveness_review_{date}.md",
        },
        "errors": [],
    }
    return payload


def main() -> int:
    args = parse_args()
    output_dir = Path(args.output_dir).expanduser()
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir
    payload = build_payload(args.date)
    json_path = output_dir / f"5913_combo_effectiveness_review_{args.date}.json"
    md_path = output_dir / f"5913_combo_effectiveness_review_{args.date}.md"
    payload["generated_artifacts"] = {"json": repo_path(json_path), "markdown": repo_path(md_path)}
    write_json(json_path, payload)
    write_text(md_path, build_markdown(payload))
    print(json.dumps({"status": "OK", "json": repo_path(json_path), "markdown": repo_path(md_path)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
