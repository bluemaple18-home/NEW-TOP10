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


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SOURCE_DIR = PROJECT_ROOT / "artifacts" / "autonomous_research"
OUTPUT_DIR = PROJECT_ROOT / "artifacts" / "research_map"
SCHEMA_VERSION = "research-fog-map-verification.v1"
MAP_SCHEMA = "research-fog-map.v1"
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
    status_ids = {item.get("id") for item in legend if isinstance(item, dict)}
    node_statuses = {item.get("status") for item in nodes if isinstance(item, dict)}
    scenario_statuses = {item.get("status") for item in scenarios if isinstance(item, dict)}
    lit_scenarios = [item for item in scenarios if isinstance(item, dict) and item.get("status") != "pending"]
    checks: list[dict[str, Any]] = [
        {"name": "payload_exists", "ok": payload_path.exists(), "value": repo_path(payload_path)},
        {"name": "html_exists", "ok": html_path.exists(), "value": repo_path(html_path)},
        {"name": "latest_payload_exists", "ok": (OUTPUT_DIR / "research_fog_map_latest.json").exists(), "value": repo_path(OUTPUT_DIR / "research_fog_map_latest.json")},
        {"name": "schema", "ok": payload.get("schema_version") == MAP_SCHEMA, "value": payload.get("schema_version")},
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
            and summary.get("expanded_processed") == summary.get("processed_combos")
            and float(summary.get("expanded_progress_pct") or 0) < float(summary.get("base_progress_pct") or summary.get("progress_pct") or 0),
            "value": {
                "base_universe_total": summary.get("base_universe_total"),
                "base_processed": summary.get("base_processed"),
                "expanded_universe_total": summary.get("expanded_universe_total"),
                "expanded_processed": summary.get("expanded_processed"),
                "base_progress_pct": summary.get("base_progress_pct"),
                "expanded_progress_pct": summary.get("expanded_progress_pct"),
            },
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
