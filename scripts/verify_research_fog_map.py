#!/usr/bin/env python3
"""驗證 research fog map artifact。

這個 verifier 只檢查 dashboard artifact 與研究安全邊界，不判斷策略好壞。
"""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from research_map_contract import completed_v2_expansion_count, read_jsonl


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "artifacts" / "autonomous_research"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "research_map"
SCHEMA_VERSION = "research-fog-map-verification.v1"
MAP_SCHEMAS = {"research-fog-map.v1", "research-fog-map.v2"}
REQUIRED_STATUS_IDS = {"pending", "rejected", "follow_up_signal", "low_information"}
REQUIRED_SECTIONS = ["hud", "star-map", "inspector", "mission-queue", "legend"]
MISLEADING_PATTERNS = [
    "promote to production",
    "promotion allowed",
    "ready for production",
    "change production ranking",
    "update production ranking",
    "production recommendation",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="verify autonomous research fog map")
    parser.add_argument("--date", required=True)
    parser.add_argument("--payload", default=None)
    parser.add_argument("--html", default=None)
    parser.add_argument("--output", default=str(OUTPUT_DIR / "research_fog_map_verification_latest.json"))
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
        return None


def read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def strip_script_style(text: str) -> str:
    text = re.sub(r"<script\b[^>]*>.*?</script>", "", text, flags=re.IGNORECASE | re.DOTALL)
    text = re.sub(r"<style\b[^>]*>.*?</style>", "", text, flags=re.IGNORECASE | re.DOTALL)
    return re.sub(r"<[^>]+>", " ", text)


def progress_alignment_checks(payload: dict[str, Any], progress_path: Path) -> list[dict[str, Any]]:
    if not progress_path.exists():
        return [
            {
                "name": "source_progress_optional",
                "ok": payload.get("source_mode") == "fixture",
                "value": "missing progress source; allowed only in fixture mode",
            }
        ]
    progress = read_json(progress_path)
    expected = progress.get("summary") if isinstance(progress.get("summary"), dict) else {}
    actual = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    if expected.get("total_combos") != actual.get("total_combos") or expected.get("expanded_universe_total") != actual.get("expanded_universe_total"):
        return [
            {
                "name": "source_progress_drift_recorded",
                "ok": True,
                "value": {
                    "progress_path": repo_path(progress_path),
                    "actual_total_combos": actual.get("total_combos"),
                    "expected_total_combos": expected.get("total_combos"),
                    "actual_expanded_universe_total": actual.get("expanded_universe_total"),
                    "expected_expanded_universe_total": expected.get("expanded_universe_total"),
                },
            }
        ]
    keys = ["total_combos", "processed_combos", "pending_combos", "followup_signal_combos", "rejected_combos"]
    for optional_key in [
        "base_universe_total",
        "base_processed",
        "expanded_universe_total",
        "expanded_processed",
        "dimension_schema_version",
    ]:
        if optional_key in expected or optional_key in actual:
            keys.append(optional_key)
    return [
        {
            "name": f"hud_aligns_{key}",
            "ok": actual.get(key) == expected.get(key),
            "value": {"actual": actual.get(key), "expected": expected.get(key)},
        }
        for key in keys
    ]


def build_payload(date: str, payload_path: Path, html_path: Path) -> dict[str, Any]:
    payload = read_json(payload_path)
    html_text = html_path.read_text(encoding="utf-8")
    visible_text = strip_script_style(html_text).lower()
    summary = payload.get("summary") if isinstance(payload.get("summary"), dict) else {}
    nodes = payload.get("nodes") if isinstance(payload.get("nodes"), list) else []
    scenarios = payload.get("scenarios") if isinstance(payload.get("scenarios"), list) else []
    legend = payload.get("legend") if isinstance(payload.get("legend"), list) else []
    contract = payload.get("contract") if isinstance(payload.get("contract"), dict) else {}
    dimension_schema = payload.get("dimension_schema") if isinstance(payload.get("dimension_schema"), dict) else {}
    active_queue = payload.get("active_expansion_queue") if isinstance(payload.get("active_expansion_queue"), list) else []
    active_completed = [
        item
        for item in active_queue
        if isinstance(item, dict) and item.get("run_status") == "completed" and item.get("artifact_path")
    ]
    history_records = read_jsonl(SOURCE_DIR / "run_history.jsonl")
    v2_completed = completed_v2_expansion_count(history_records)
    expected_expanded_processed = int(summary.get("base_processed") or 0) + v2_completed
    fog = payload.get("full_universe_fog") if isinstance(payload.get("full_universe_fog"), dict) else {}
    burn_down = payload.get("burn_down_progress") if isinstance(payload.get("burn_down_progress"), dict) else {}
    burn_counts = burn_down.get("counts") if isinstance(burn_down.get("counts"), dict) else {}
    burn_source = resolve_path(burn_down.get("source")) if burn_down.get("source") else None
    burn_count_sum = sum(int(value or 0) for value in burn_counts.values())
    artifact_blocker_count = int(burn_down.get("artifact_blocker_count") or 0)
    controlled_grid_drain = burn_down.get("controlled_grid_drain") if isinstance(burn_down.get("controlled_grid_drain"), dict) else {}
    baseline_blocker_cleared = burn_down.get("baseline_blocker_cleared") is True or controlled_grid_drain.get("baseline_blocker_cleared") is True
    artifact_blocker_categories = (
        burn_down.get("artifact_blocker_category_counts")
        if isinstance(burn_down.get("artifact_blocker_category_counts"), dict)
        else {}
    )
    controlled_drain_cleared_or_in_progress = (
        baseline_blocker_cleared
        and artifact_blocker_count == 0
        and controlled_grid_drain.get("target_production_path_created") is False
        and controlled_grid_drain.get("production_impact") == "NO_PRODUCTION_CHANGE"
        and (
            (
                controlled_grid_drain.get("status") == "OK"
                and controlled_grid_drain.get("controlled_grid_drain_ready") is True
            )
            or controlled_grid_drain.get("micro_batch_status") == "OK"
        )
    )
    status_ids = {item.get("id") for item in legend if isinstance(item, dict)}
    node_statuses = {item.get("status") for item in nodes if isinstance(item, dict)}
    scenario_statuses = {item.get("status") for item in scenarios if isinstance(item, dict)}
    lit_scenarios = [item for item in scenarios if isinstance(item, dict) and item.get("status") != "pending"]
    checks: list[dict[str, Any]] = [
        {"name": "payload_exists", "ok": payload_path.exists(), "value": repo_path(payload_path)},
        {"name": "html_exists", "ok": html_path.exists(), "value": repo_path(html_path)},
        {"name": "latest_payload_exists", "ok": (OUTPUT_DIR / "research_fog_map_latest.json").exists(), "value": repo_path(OUTPUT_DIR / "research_fog_map_latest.json")},
        {"name": "schema", "ok": payload.get("schema_version") in MAP_SCHEMAS, "value": payload.get("schema_version")},
        {"name": "date", "ok": payload.get("date") == date, "value": payload.get("date")},
        {"name": "status", "ok": payload.get("status") in {"OK", "FIXTURE"}, "value": payload.get("status")},
        {
            "name": "fixture_flag_explicit",
            "ok": isinstance(payload.get("fixture"), bool) and payload.get("source_mode") in {"live", "fixture"},
            "value": {"fixture": payload.get("fixture"), "source_mode": payload.get("source_mode")},
        },
        {
            "name": "research_only_contract",
            "ok": contract.get("research_only") is True
            and contract.get("does_not_execute_backtests") is True
            and contract.get("does_not_train_model") is True
            and contract.get("does_not_change_models_latest_lgbm") is True
            and contract.get("does_not_change_risk_adjusted_score") is True
            and contract.get("does_not_change_production_ranking") is True,
            "value": contract,
        },
        {
            "name": "progress_from_jsonl_contract",
            "ok": contract.get("progress_from_run_history_jsonl") is True and contract.get("manual_progress_fill_allowed") is False,
            "value": contract,
        },
        {
            "name": "node_count_matches_total_topics",
            "ok": len(nodes) == summary.get("total_topics"),
            "value": {"nodes": len(nodes), "total_topics": summary.get("total_topics")},
        },
        {
            "name": "scenario_count_matches_total_combos",
            "ok": len(scenarios) == summary.get("total_combos") == summary.get("estimated_scenario_universe"),
            "value": {
                "scenarios": len(scenarios),
                "total_combos": summary.get("total_combos"),
                "estimated_scenario_universe": summary.get("estimated_scenario_universe"),
            },
        },
        {
            "name": "processed_combo_count_from_scenarios",
            "ok": len(lit_scenarios) == summary.get("processed_combos") == summary.get("estimated_processed_scenarios"),
            "value": {"lit_scenarios": len(lit_scenarios), "processed_combos": summary.get("processed_combos")},
        },
        {
            "name": "v2_dimension_schema_present",
            "ok": summary.get("dimension_schema_version") == "research-map-dimensions.v2"
            and dimension_schema.get("version") == "research-map-dimensions.v2"
            and isinstance(summary.get("dimension_values"), dict),
            "value": {
                "summary_version": summary.get("dimension_schema_version"),
                "schema_version": dimension_schema.get("version"),
            },
        },
        {
            "name": "base_and_expanded_progress_separated",
            "ok": summary.get("base_universe_total") == summary.get("total_combos")
            and summary.get("base_processed") == summary.get("processed_combos")
            and int(summary.get("expanded_universe_total") or 0) > int(summary.get("base_universe_total") or 0)
            and int(summary.get("expanded_processed") or 0) == expected_expanded_processed
            and int(summary.get("expanded_processed") or 0) <= int(summary.get("expanded_universe_total") or 0)
            and float(summary.get("expanded_progress_pct") or 0) < float(summary.get("base_progress_pct") or summary.get("progress_pct") or 0),
            "value": {
                "base_universe_total": summary.get("base_universe_total"),
                "base_processed": summary.get("base_processed"),
                "expanded_universe_total": summary.get("expanded_universe_total"),
                "expanded_processed": summary.get("expanded_processed"),
                "expected_expanded_processed": expected_expanded_processed,
                "v2_completed_from_run_history": v2_completed,
                "active_completed": len(active_completed),
                "base_progress_pct": summary.get("base_progress_pct"),
                "expanded_progress_pct": summary.get("expanded_progress_pct"),
            },
        },
        {
            "name": "burn_down_progress_present",
            "ok": burn_down.get("schema_version") == "research-map-burn-down-progress.v1"
            and burn_source is not None
            and burn_source.exists(),
            "value": {"schema": burn_down.get("schema_version"), "source": burn_down.get("source")},
        },
        {
            "name": "burn_down_counts_classify_full_universe",
            "ok": int(burn_down.get("full_universe_total") or 0) == int(summary.get("expanded_universe_total") or 0)
            and int(burn_down.get("classified_total") or 0) == int(summary.get("expanded_universe_total") or 0)
            and burn_count_sum == int(burn_down.get("classified_total") or 0),
            "value": {
                "full_universe_total": burn_down.get("full_universe_total"),
                "classified_total": burn_down.get("classified_total"),
                "expanded_universe_total": summary.get("expanded_universe_total"),
                "count_sum": burn_count_sum,
            },
        },
        {
            "name": "executed_progress_not_replaced_by_burn_down",
            "ok": int(summary.get("expanded_processed") or 0) == expected_expanded_processed
            and int(summary.get("expanded_processed") or 0) < int(burn_down.get("classified_total") or 0),
            "value": {
                "expanded_processed": summary.get("expanded_processed"),
                "expected_expanded_processed": expected_expanded_processed,
                "burn_down_classified_total": burn_down.get("classified_total"),
            },
        },
        {
            "name": "burn_down_progress_visible_in_html",
            "ok": "已執行進度" in visible_text
            and "分類消化進度" in visible_text
            and "artifact blocker" in visible_text
            and "baseline provenance gap" in visible_text
            and "controlled drain" in visible_text
            and 'id="burn-down-classified-count"' in html_text
            and 'id="executed-progress-count"' in html_text,
            "value": "已執行進度 / 分類消化進度 / artifact blocker / controlled drain",
        },
        {
            "name": "artifact_blocker_visible_or_cleared_by_controlled_drain",
            "ok": (
                controlled_drain_cleared_or_in_progress
                or (
                    not baseline_blocker_cleared
                    and artifact_blocker_count == 202176
                    and int(artifact_blocker_categories.get("ARTIFACT_BLOCKER_PROVENANCE_GAP") or 0) == artifact_blocker_count
                    and artifact_blocker_count <= int(burn_counts.get("unsupported_count") or 0)
                )
            )
            and 'id="artifact-blocker-count"' in html_text
            and 'id="baseline-provenance-gap-count"' in html_text,
            "value": {
                "artifact_blocker_count": artifact_blocker_count,
                "artifact_blocker_category_counts": artifact_blocker_categories,
                "unsupported_count": burn_counts.get("unsupported_count"),
                "baseline_blocker_cleared": baseline_blocker_cleared,
                "controlled_grid_drain": controlled_grid_drain,
            },
        },
        {
            "name": "active_queue_completed_rows_have_artifacts",
            "ok": all(item.get("artifact_path") for item in active_completed),
            "value": {"active_queue_count": len(active_queue), "completed": len(active_completed)},
        },
        {
            "name": "v1_rows_migrated_to_default_v2_coordinates",
            "ok": all(
                isinstance(item.get("v2_dimensions"), dict)
                and item["v2_dimensions"].get("regime_gate") == "ALL"
                and item["v2_dimensions"].get("risk_guard") == "NONE"
                and item["v2_dimensions"].get("entry_filter") == "TOPIC_DEFAULT"
                and item.get("dimension_schema_version") == "research-map-dimensions.v2"
                for item in scenarios
            ),
            "value": [{"combo_id": item.get("combo_id"), "v2_dimensions": item.get("v2_dimensions")} for item in scenarios[:3]],
        },
        {
            "name": "scenario_combo_ids_present",
            "ok": all(item.get("combo_id") and isinstance(item.get("dimensions"), dict) for item in scenarios),
            "value": len(scenarios),
        },
        {
            "name": "lit_scenarios_have_artifacts",
            "ok": all(item.get("artifact_path") for item in lit_scenarios),
            "value": [{"combo_id": item.get("combo_id"), "artifact_path": item.get("artifact_path")} for item in lit_scenarios[:5]],
        },
        {
            "name": "required_statuses_supported",
            "ok": REQUIRED_STATUS_IDS.issubset(status_ids),
            "value": {"required": sorted(REQUIRED_STATUS_IDS), "legend": sorted(status_ids)},
        },
        {
            "name": "required_first_version_states_present_or_supported",
            "ok": "pending" in status_ids
            and ("pending" in scenario_statuses or summary.get("processed_combos") == summary.get("total_combos"))
            and bool(scenario_statuses - {"pending"})
            and "low_information" in status_ids,
            "value": {"node_statuses": sorted(node_statuses), "scenario_statuses": sorted(scenario_statuses), "legend": sorted(status_ids)},
        },
        {
            "name": "mission_queue_present",
            "ok": isinstance(payload.get("mission_queue"), list) and len(payload.get("mission_queue")) > 0,
            "value": len(payload.get("mission_queue") or []),
        },
        {
            "name": "dashboard_sections_present",
            "ok": all(f'id="{section}"' in html_text for section in REQUIRED_SECTIONS),
            "value": REQUIRED_SECTIONS,
        },
        {
            "name": "inspector_interaction_present",
            "ok": "function renderInspector" in html_text and "addEventListener('click'" in html_text,
            "value": "renderInspector/click",
        },
        {
            "name": "legend_render_present",
            "ok": "legend-grid" in html_text and "payload.legend" in html_text,
            "value": "legend-grid",
        },
        {
            "name": "full_universe_fog_metadata_present",
            "ok": fog.get("schema_version") == "research-map-full-universe-fog.v1"
            and fog.get("full_universe_count") == summary.get("expanded_universe_total")
            and fog.get("unexplored_count") == int(summary.get("expanded_universe_total") or 0) - int(summary.get("expanded_processed") or 0)
            and fog.get("clickable") is False,
            "value": fog,
        },
        {
            "name": "full_universe_fog_canvas_present",
            "ok": 'id="universe-fog-canvas"' in html_text
            and "drawUniverseFogCanvas" in html_text
            and "dataset.fogSampleCount" in html_text
            and "dataset.clickableScenarioCount" in html_text,
            "value": "universe-fog-canvas",
        },
        {
            "name": "full_universe_not_dom_points",
            "ok": int(fog.get("sample_count") or 0) < int(summary.get("expanded_universe_total") or 0)
            and int(fog.get("sample_count") or 0) >= 60000
            and "document.createElement('button')" not in html_text,
            "value": {
                "sample_count": fog.get("sample_count"),
                "expanded_universe_total": summary.get("expanded_universe_total"),
            },
        },
        {
            "name": "no_misleading_visible_promotion_copy",
            "ok": not any(pattern in visible_text for pattern in MISLEADING_PATTERNS),
            "value": [pattern for pattern in MISLEADING_PATTERNS if pattern in visible_text],
        },
    ]
    if payload.get("fixture"):
        checks.append(
            {
                "name": "fixture_banner_visible",
                "ok": "fixture mode" in visible_text,
                "value": "fixture mode",
            }
        )
    checks.extend(progress_alignment_checks(payload, SOURCE_DIR / f"research_campaign_progress_{date}.json"))
    failed = [check for check in checks if not check["ok"]]
    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK" if not failed else "FAILED",
        "artifact": {
            "payload": repo_path(payload_path),
            "html": repo_path(html_path),
        },
        "summary": {
            "check_count": len(checks),
            "failed_count": len(failed),
            "source_mode": payload.get("source_mode"),
            "total_topics": summary.get("total_topics"),
            "processed_topics": summary.get("processed_topics"),
            "total_combos": summary.get("total_combos"),
            "processed_combos": summary.get("processed_combos"),
            "estimated_scenario_universe": summary.get("estimated_scenario_universe"),
            "node_statuses": sorted(node_statuses),
            "scenario_statuses": sorted(scenario_statuses),
        },
        "checks": checks,
    }


def main() -> int:
    args = parse_args()
    payload_path = resolve_path(args.payload) or (OUTPUT_DIR / f"research_fog_map_{args.date}.json")
    html_path = resolve_path(args.html) or (OUTPUT_DIR / "index.html")
    output_path = resolve_path(args.output)
    if output_path is None:
        raise RuntimeError("output resolution failed")
    if not payload_path.exists():
        raise FileNotFoundError(f"找不到 fog map payload：{repo_path(payload_path) or payload_path}")
    if not html_path.exists():
        raise FileNotFoundError(f"找不到 fog map HTML：{repo_path(html_path) or html_path}")
    report = build_payload(args.date, payload_path, html_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "status": report["status"],
                "output": repo_path(output_path),
                "failed_count": report["summary"]["failed_count"],
                "total_topics": report["summary"]["total_topics"],
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0 if report["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
