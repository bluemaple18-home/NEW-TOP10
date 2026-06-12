#!/usr/bin/env python3
"""把舊 autonomous research artifact 回填成 research map JSONL 紀錄。

這個腳本只做格式轉換，不跑回測、不訓練模型、不改 production ranking。
可精準讀到 strategy matrix scenario 的項目會標成 scenario_exact；只能從
topic_registry 判斷已跑過的項目會標成 topic_level，避免把舊制證據說得太滿。
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_map_contract import build_combo_registry, infer_insight_level, read_jsonl


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTO_DIR = PROJECT_ROOT / "artifacts" / "autonomous_research"
RUN_HISTORY_JSONL = AUTO_DIR / "run_history.jsonl"
BACKFILL_SOURCES = {
    "research_map_legacy_strategy_matrix_backfill",
    "research_map_legacy_topic_registry_backfill",
    "research_map_linkage_smoke",
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="backfill research map run_history.jsonl from legacy artifacts")
    parser.add_argument("--date", default=datetime.now(timezone.utc).date().isoformat())
    parser.add_argument("--output", default=str(RUN_HISTORY_JSONL))
    parser.add_argument("--replace-existing", action="store_true", help="remove previous smoke/backfill rows before writing")
    return parser.parse_args()


def repo_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(PROJECT_ROOT))
    except ValueError:
        return str(path)


def resolve_path(value: str | Path | None) -> Path | None:
    if value is None:
        return None
    path = Path(value)
    return path if path.is_absolute() else PROJECT_ROOT / path


def read_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def slugify(value: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower()).strip("-")
    if not text:
        return "research-topic"
    if len(text) <= 90:
        return text
    import hashlib

    digest = hashlib.sha1(value.encode("utf-8")).hexdigest()[:8]
    return f"{text[:80]}-{digest}"


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True, allow_nan=False) for row in rows) + "\n",
        encoding="utf-8",
    )


def load_registry_topics() -> list[dict[str, Any]]:
    payload = read_json(AUTO_DIR / "topic_registry.json")
    rows = payload.get("topics") if isinstance(payload.get("topics"), list) else []
    return [row for row in rows if isinstance(row, dict) and row.get("topic_id")]


def norm_pct(value: Any) -> str:
    if value is None:
        return "none"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        text = str(value).strip()
        return text or "none"


def scenario_dimensions(row: dict[str, Any]) -> dict[str, str]:
    return {
        "horizon": str(int(row.get("horizon"))),
        "stop_loss": norm_pct(row.get("stop_loss_pct")),
        "take_profit": norm_pct(row.get("take_profit_pct")),
        "group_exposure": norm_pct(row.get("max_group_exposure")),
    }


def combo_lookup(topics: list[dict[str, Any]]) -> dict[tuple[str, str, str, str, str], dict[str, Any]]:
    lookup: dict[tuple[str, str, str, str, str], dict[str, Any]] = {}
    for combo in build_combo_registry(topics):
        dims = combo["dimensions"]
        lookup[
            (
                str(combo["topic_id"]),
                dims["horizon"],
                dims["stop_loss"],
                dims["take_profit"],
                dims["group_exposure"],
            )
        ] = combo
    return lookup


def outcome_files() -> list[Path]:
    return sorted(AUTO_DIR.glob("autonomous_research*.json")) + sorted((AUTO_DIR / "run_outputs").glob("autonomous_research*.json"))


def matrix_by_scenario(path: Path | None) -> dict[str, dict[str, Any]]:
    payload = read_json(path)
    rows = payload.get("scenarios") if isinstance(payload.get("scenarios"), list) else []
    return {str(row.get("scenario_id")): row for row in rows if isinstance(row, dict) and row.get("scenario_id")}


def classify_decision(score_delta: float, return_delta: float, drawdown_delta: float) -> tuple[str, str]:
    if return_delta > 0 and score_delta > 0 and drawdown_delta >= 0:
        return "CONFIRMED_FOR_NEXT_REPLAY", "effective"
    if return_delta > 0 and drawdown_delta < 0:
        return "PARTIAL_SCORE_ONLY", "risk_worse_return_positive"
    if score_delta > 0:
        return "PARTIAL_SCORE_ONLY", "ordinary"
    return "REJECTED_BY_STRATEGY_MATRIX", "rejected"


def safe_float(value: Any) -> float:
    try:
        if value is None:
            return 0.0
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def row_timestamp(*payloads: dict[str, Any], fallback_path: Path | None = None) -> str:
    for payload in payloads:
        text = str(payload.get("generated_at") or "").strip()
        if text:
            return text
    if fallback_path and fallback_path.exists():
        return datetime.fromtimestamp(fallback_path.stat().st_mtime, timezone.utc).isoformat()
    return datetime.now(timezone.utc).isoformat()


def exact_rows_from_topic_run(
    topic_run: dict[str, Any],
    source_file: Path,
    lookup: dict[tuple[str, str, str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    topic = topic_run.get("topic") if isinstance(topic_run.get("topic"), dict) else {}
    topic_id = str(topic.get("topic_id") or "")
    outcome = topic_run.get("outcome") if isinstance(topic_run.get("outcome"), dict) else {}
    candidate_info = outcome.get("candidate") if isinstance(outcome.get("candidate"), dict) else {}
    baseline_info = outcome.get("baseline") if isinstance(outcome.get("baseline"), dict) else {}
    candidate_path = resolve_path(candidate_info.get("path"))
    baseline_path = resolve_path(baseline_info.get("path"))
    candidate_payload = read_json(candidate_path)
    baseline_payload = read_json(baseline_path)
    candidate = matrix_by_scenario(candidate_path)
    baseline = matrix_by_scenario(baseline_path)
    if not topic_id or not candidate:
        return []

    rows: list[dict[str, Any]] = []
    for scenario_id, candidate_row in candidate.items():
        dims = scenario_dimensions(candidate_row)
        combo = lookup.get((topic_id, dims["horizon"], dims["stop_loss"], dims["take_profit"], dims["group_exposure"]))
        if not combo:
            continue
        baseline_row = baseline.get(scenario_id, {})
        return_delta = round(safe_float(candidate_row.get("total_return")) - safe_float(baseline_row.get("total_return")), 6)
        drawdown_delta = round(safe_float(candidate_row.get("max_drawdown")) - safe_float(baseline_row.get("max_drawdown")), 6)
        score_delta = round(safe_float(candidate_row.get("score")) - safe_float(baseline_row.get("score")), 6)
        decision, insight = classify_decision(score_delta, return_delta, drawdown_delta)
        rows.append(
            {
                "schema_version": "research-run-history-jsonl.v1",
                "source": "research_map_legacy_strategy_matrix_backfill",
                "evidence_level": "scenario_exact",
                "combo_id": combo["combo_id"],
                "topic_id": topic_id,
                "dimensions": combo["dimensions"],
                "status": "OK",
                "score_delta": score_delta,
                "return_delta": return_delta,
                "drawdown_delta": drawdown_delta,
                "decision": decision,
                "insight_level": insight,
                "artifact_path": repo_path(candidate_path or source_file),
                "source_artifact_path": repo_path(source_file),
                "baseline_artifact_path": repo_path(baseline_path) if baseline_path else None,
                "scenario_id": scenario_id,
                "finished_at": row_timestamp(candidate_payload, baseline_payload, outcome, fallback_path=candidate_path),
            }
        )
    return rows


def exact_rows_from_matrix_pair(
    candidate_path: Path,
    lookup: dict[tuple[str, str, str, str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    candidate_payload = read_json(candidate_path)
    candidate_dir = str((candidate_payload.get("inputs") or {}).get("rankings_dir") or "").strip()
    if not candidate_dir:
        return []
    candidate_dir_path = Path(candidate_dir)
    if candidate_dir_path.is_absolute():
        candidate_dir = repo_path(candidate_dir_path)
    topic_id = f"strategy-matrix:{slugify(candidate_dir)}"
    baseline_path = candidate_path.with_name(candidate_path.name.replace("_candidate_strategy_matrix.json", "_baseline_strategy_matrix.json"))
    baseline_payload = read_json(baseline_path)
    candidate = matrix_by_scenario(candidate_path)
    baseline = matrix_by_scenario(baseline_path)
    rows: list[dict[str, Any]] = []
    for scenario_id, candidate_row in candidate.items():
        dims = scenario_dimensions(candidate_row)
        combo = lookup.get((topic_id, dims["horizon"], dims["stop_loss"], dims["take_profit"], dims["group_exposure"]))
        if not combo:
            continue
        baseline_row = baseline.get(scenario_id, {})
        return_delta = round(safe_float(candidate_row.get("total_return")) - safe_float(baseline_row.get("total_return")), 6)
        drawdown_delta = round(safe_float(candidate_row.get("max_drawdown")) - safe_float(baseline_row.get("max_drawdown")), 6)
        score_delta = round(safe_float(candidate_row.get("score")) - safe_float(baseline_row.get("score")), 6)
        decision, insight = classify_decision(score_delta, return_delta, drawdown_delta)
        rows.append(
            {
                "schema_version": "research-run-history-jsonl.v1",
                "source": "research_map_legacy_strategy_matrix_backfill",
                "evidence_level": "scenario_exact",
                "combo_id": combo["combo_id"],
                "topic_id": topic_id,
                "dimensions": combo["dimensions"],
                "status": "OK",
                "score_delta": score_delta,
                "return_delta": return_delta,
                "drawdown_delta": drawdown_delta,
                "decision": decision,
                "insight_level": insight,
                "artifact_path": repo_path(candidate_path),
                "source_artifact_path": repo_path(candidate_path),
                "baseline_artifact_path": repo_path(baseline_path) if baseline_path.exists() else None,
                "scenario_id": scenario_id,
                "finished_at": row_timestamp(candidate_payload, baseline_payload, fallback_path=candidate_path),
            }
        )
    return rows


def topic_level_decision(topic: dict[str, Any]) -> tuple[str, str]:
    manager_status = str(topic.get("manager_status") or topic.get("status") or "")
    decision = str(topic.get("last_decision") or "")
    record = {"decision": decision}
    if manager_status == "rejected" or decision == "REJECTED_BY_STRATEGY_MATRIX":
        return "REJECTED_BY_STRATEGY_MATRIX", "rejected"
    if manager_status == "partial_needs_followup" or decision == "PARTIAL_SCORE_ONLY":
        return "PARTIAL_SCORE_ONLY", "risk_worse_return_positive"
    if decision == "CONFIRMED_FOR_NEXT_REPLAY":
        return decision, "next_stage"
    return decision or "LEGACY_TOPIC_PROCESSED", infer_insight_level(record)


def topic_level_rows(
    topics: list[dict[str, Any]],
    exact_topic_ids: set[str],
    combos_by_topic: dict[str, list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    registry_path = AUTO_DIR / "topic_registry.json"
    finished_at = row_timestamp(read_json(registry_path), fallback_path=registry_path)
    for topic in topics:
        topic_id = str(topic.get("topic_id") or "")
        if not topic_id or topic_id in exact_topic_ids:
            continue
        if int(safe_float(topic.get("run_count"))) <= 0:
            continue
        decision, insight = topic_level_decision(topic)
        for combo in combos_by_topic.get(topic_id, []):
            rows.append(
                {
                    "schema_version": "research-run-history-jsonl.v1",
                    "source": "research_map_legacy_topic_registry_backfill",
                    "evidence_level": "topic_level",
                    "combo_id": combo["combo_id"],
                    "topic_id": topic_id,
                    "dimensions": combo["dimensions"],
                    "status": "OK",
                    "score_delta": None,
                    "return_delta": None,
                    "drawdown_delta": None,
                    "decision": decision,
                    "insight_level": insight,
                    "artifact_path": repo_path(registry_path),
                    "source_artifact_path": repo_path(registry_path),
                    "finished_at": finished_at,
                }
            )
    return rows


def collect_backfill_rows(topics: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    lookup = combo_lookup(topics)
    combos_by_topic: dict[str, list[dict[str, Any]]] = {}
    for combo in build_combo_registry(topics):
        combos_by_topic.setdefault(str(combo["topic_id"]), []).append(combo)

    exact_rows_by_combo: dict[str, dict[str, Any]] = {}
    exact_topic_ids: set[str] = set()
    source_files = 0
    topic_runs_seen = 0
    for source_file in outcome_files():
        payload = read_json(source_file)
        topic_runs = payload.get("topic_runs") if isinstance(payload.get("topic_runs"), list) else []
        if not topic_runs:
            continue
        source_files += 1
        for topic_run in topic_runs:
            topic_runs_seen += 1
            rows = exact_rows_from_topic_run(topic_run, source_file, lookup)
            for row in rows:
                exact_rows_by_combo[str(row["combo_id"])] = row
                exact_topic_ids.add(str(row["topic_id"]))

    matrix_files_seen = 0
    for candidate_path in sorted(AUTO_DIR.glob("run_*/*_candidate_strategy_matrix.json")):
        matrix_files_seen += 1
        for row in exact_rows_from_matrix_pair(candidate_path, lookup):
            exact_rows_by_combo[str(row["combo_id"])] = row
            exact_topic_ids.add(str(row["topic_id"]))

    exact_rows = list(exact_rows_by_combo.values())
    fallback_rows = topic_level_rows(topics, exact_topic_ids, combos_by_topic)
    return exact_rows + fallback_rows, {
        "source_files": source_files,
        "topic_runs_seen": topic_runs_seen,
        "matrix_files_seen": matrix_files_seen,
        "scenario_exact_topics": len(exact_topic_ids),
        "scenario_exact_rows": len(exact_rows),
        "topic_level_rows": len(fallback_rows),
    }


def main() -> int:
    args = parse_args()
    output = resolve_path(args.output)
    if output is None:
        raise RuntimeError("output path resolution failed")
    topics = load_registry_topics()
    rows, summary = collect_backfill_rows(topics)
    existing = read_jsonl(output)
    if args.replace_existing:
        existing = [row for row in existing if row.get("source") not in BACKFILL_SOURCES]
    payload = existing + rows
    write_jsonl(output, payload)
    result = {
        "status": "OK",
        "output": repo_path(output),
        "topics": len(topics),
        "rows_written": len(rows),
        "total_rows": len(payload),
        **summary,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
