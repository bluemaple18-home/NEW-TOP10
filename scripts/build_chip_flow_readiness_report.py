#!/usr/bin/env python3
"""建立 chip-flow readiness 報告。

這份報告只做靜態盤點：確認三大法人與融資融券資料目前到哪一層，
是否已進 production ranking，以及正式化前缺哪些 evidence。
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_DATE = datetime.now().strftime("%Y-%m-%d")
SCHEMA_VERSION = "chip-flow-readiness.v1"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="build chip-flow readiness report")
    parser.add_argument(
        "--output",
        default=f"artifacts/model_experiments/chip_flow_readiness_report_{RUN_DATE}.json",
    )
    parser.add_argument("--markdown-output", default=None)
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


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def latest_file(pattern: str) -> Path | None:
    files = sorted(PROJECT_ROOT.glob(pattern))
    return files[-1] if files else None


def latest_dated_file(directory: Path, prefix: str) -> Path | None:
    pattern = re.compile(rf"{re.escape(prefix)}_\d{{4}}-\d{{2}}-\d{{2}}\.json$")
    files = sorted([path for path in directory.glob(f"{prefix}_*.json") if pattern.match(path.name)])
    return files[-1] if files else None


def latest_ranking_file() -> Path | None:
    pattern = re.compile(r"ranking_\d{4}-\d{2}-\d{2}\.csv$")
    files = sorted([path for path in (PROJECT_ROOT / "artifacts").glob("ranking_*.csv") if pattern.match(path.name)])
    return files[-1] if files else None


def csv_header(path: Path | None) -> list[str]:
    if path is None or not path.exists():
        return []
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.reader(handle)
        try:
            return next(reader)
        except StopIteration:
            return []


def load_json(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def find_gate_candidate(payload: dict[str, Any], candidate_id: str) -> dict[str, Any]:
    for candidate in payload.get("candidates", []):
        if candidate.get("id") == candidate_id:
            return candidate
    return {}


def build_payload() -> dict[str, Any]:
    fetcher_path = PROJECT_ROOT / "app" / "finmind_fetcher.py"
    integrator_path = PROJECT_ROOT / "app" / "finmind_integrator.py"
    fetch_stage_path = PROJECT_ROOT / "app" / "pipeline" / "fetch_stage.py"
    volume_path = PROJECT_ROOT / "app" / "indicators" / "mixins" / "volume.py"
    core_path = PROJECT_ROOT / "app" / "indicators" / "core.py"
    modeling_path = PROJECT_ROOT / "app" / "agent_b_modeling.py"

    fetcher = read_text(fetcher_path)
    integrator = read_text(integrator_path)
    fetch_stage = read_text(fetch_stage_path)
    volume = read_text(volume_path)
    core = read_text(core_path)
    modeling = read_text(modeling_path)

    ranking_path = latest_ranking_file()
    ranking_header = csv_header(ranking_path)
    chip_columns = [
        "foreign_buy",
        "trust_buy",
        "dealer_buy",
        "inst_buy_total",
        "inst_buy_ratio_3d",
        "inst_buy_ratio_5d",
        "inst_buy_ratio_10d",
        "trust_buy_days_3d",
        "trust_buy_days_5d",
        "trust_buy_days_10d",
    ]
    margin_columns = [
        "margin_purchase",
        "margin_balance",
        "short_sale",
        "margin_balance_change_5d",
        "margin_balance_change_20d",
    ]
    ranking_chip_columns = [col for col in chip_columns + margin_columns if col in ranking_header]

    gate_path = latest_dated_file(PROJECT_ROOT / "artifacts", "feature_experiment_gate")
    gate_payload = load_json(gate_path)
    gate_candidate = find_gate_candidate(gate_payload, "chip_flow")
    handoff_path = PROJECT_ROOT / "docs" / "tasks" / "2026-06-08_CHIP-FLOW_warning_research_handoff.md"
    contract_files = sorted((PROJECT_ROOT / "artifacts").glob("chip_data_contract_*.json"))
    coverage_path = latest_dated_file(PROJECT_ROOT / "artifacts", "chip_flow_runtime_coverage")
    coverage_payload = load_json(coverage_path)
    warning_path = latest_dated_file(PROJECT_ROOT / "artifacts" / "model_experiments", "chip_warning_shadow_report")
    warning_payload = load_json(warning_path)
    aggregate_path = latest_dated_file(PROJECT_ROOT / "artifacts" / "model_experiments", "chip_warning_replay_aggregate")
    aggregate_payload = load_json(aggregate_path)
    composite_path = latest_dated_file(PROJECT_ROOT / "artifacts" / "model_experiments", "chip_composite_warning_report")
    composite_payload = load_json(composite_path)

    institutional_fetcher_ready = "taiwan_stock_institutional_investors" in fetcher
    margin_fetcher_ready = "taiwan_stock_margin_purchase_short_sale" in fetcher
    institutional_integrated = all(token in integrator for token in ["foreign_buy", "trust_buy", "dealer_buy"])
    margin_integrated = "get_margin_purchase_short_sale" in integrator or "margin_purchase" in integrator
    fetch_stage_optional = "FinMindIntegrator" in fetch_stage and "略過此資料源" in fetch_stage
    indicator_derivation_ready = all(
        token in volume for token in ["inst_buy_total", "inst_buy_ratio_", "trust_buy_days_"]
    ) and all(token in core for token in ["foreign_buy", "trust_buy", "dealer_buy"])
    model_auto_include_risk = "select_dtypes" in modeling and "candidate_feature_columns" in modeling

    blockers: list[str] = []
    if not contract_files:
        blockers.append("missing chip_data_contract artifact")
    else:
        latest_contract = load_json(contract_files[-1])
        if latest_contract.get("status") != "OK":
            blockers.append(f"latest chip_data_contract status={latest_contract.get('status') or 'missing'}")
    if gate_candidate.get("shadow_status") != "READY_FOR_SHADOW":
        blockers.append(f"feature gate shadow_status={gate_candidate.get('shadow_status') or 'missing'}")
        for item in gate_candidate.get("blockers") or []:
            blockers.append(f"feature gate blocker: {item}")
    if ranking_chip_columns:
        blockers.append("ranking already exposes chip columns before readiness approval")
    if not institutional_integrated:
        blockers.append("institutional columns are not integrated")
    if not margin_integrated:
        blockers.append("margin purchase / short sale is fetch-only and not integrated")
    if fetch_stage_optional:
        blockers.append("FinMind failures are skipped, so absence cannot be interpreted as zero flow")
    if coverage_payload.get("status") != "OK":
        blockers.append("runtime coverage is not OK yet")
    if warning_payload.get("status") != "OK":
        blockers.append("warning-only replay is not OK yet")
    elif warning_payload.get("decision", {}).get("status") == "NOT_STABLE_ENOUGH_FOR_WARNING_CHANNEL":
        blockers.append("warning-only replay sample is not stable enough for a warning channel")
    if handoff_path.exists():
        blockers.append("mainline handoff blocks chip_flow production warning/ranking promotion")

    if margin_integrated and coverage_payload.get("status") == "OK":
        margin_read = "融資融券已接進 integrator，且已有 FinMind smoke coverage。"
    elif margin_integrated:
        margin_read = "融資融券已接進 integrator，但尚未有 runtime coverage 證據。"
    else:
        margin_read = "融資融券只有 fetch method，尚未整合。"
    contract_read = "chip_data_contract 已存在。" if contract_files else "缺 chip_data_contract。"
    if composite_payload.get("decision", {}).get("status") == "NOT_STABLE_ENOUGH_FOR_WARNING_CHANNEL":
        replay_read = "aggregate replay 已達研究監控層級，但 composite warning 尚未穩定。"
    elif aggregate_payload.get("decision", {}).get("status") == "PARTIAL_MONITOR_ONLY":
        replay_read = "aggregate replay 已達研究監控層級，但仍不足以正式化。"
    elif warning_payload.get("status") == "OK":
        replay_read = "warning-only replay 已跑，但樣本仍不足以正式化。"
    else:
        replay_read = "缺 warning-only replay。"
    decision = {
        "status": "NOT_READY_FOR_PRODUCTION",
        "shadow_status": "BLOCKED",
        "production_status": "BLOCKED",
        "primary_read": (
            "三大法人已有 fetch + partial integrate + optional indicator path；"
            f"{margin_read}{contract_read}{replay_read}"
            "目前只可保留為研究 overlay 或推薦理由輔助文字；不能把它當正式 ranking、正式 warning、"
            "賣出/減碼提醒，也不能把外資、投信、融資單獨當大盤判斷主因。主線應轉測 price/rank/volume/overheat reversal exit signal。"
        ),
        "usable_now": [
            "code-level readiness audit",
            "設計 chip data contract",
            "研究 overlay 與推薦理由輔助文字",
        ],
        "not_usable_now": [
            "production ranking score",
            "正式 RISK_ALERT",
            "個人化賣出或減碼提醒",
            "正式 warning channel",
            "大盤方向主判斷因子",
            "外資/投信/融資單獨 exit trigger",
            "把缺資料填 0 後解讀成法人未買賣",
        ],
        "first_promotable_shape": "research overlay only; not warning channel",
    }

    return {
        "schema_version": SCHEMA_VERSION,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OK",
        "contract": {
            "research_only": True,
            "static_audit_only": True,
            "changes_model": False,
            "changes_production_ranking": False,
            "changes_risk_adjusted_score": False,
            "does_not_send_push": True,
            "does_not_fetch_network_data": True,
            "no_personal_holdings": True,
        },
        "inputs": {
            "finmind_fetcher": repo_path(fetcher_path),
            "finmind_integrator": repo_path(integrator_path),
            "fetch_stage": repo_path(fetch_stage_path),
            "volume_indicators": repo_path(volume_path),
            "indicator_core": repo_path(core_path),
            "modeling": repo_path(modeling_path),
            "feature_gate": repo_path(gate_path),
            "handoff": repo_path(handoff_path),
            "runtime_coverage": repo_path(coverage_path),
            "warning_shadow_report": repo_path(warning_path),
            "warning_replay_aggregate": repo_path(aggregate_path),
            "composite_warning_report": repo_path(composite_path),
            "latest_ranking": repo_path(ranking_path),
        },
        "capability_matrix": {
            "institutional_investor_fetch": {
                "status": "PRESENT" if institutional_fetcher_ready else "MISSING",
                "fields": ["buy", "sell", "name", "date", "stock_id"],
            },
            "margin_purchase_short_sale_fetch": {
                "status": "PRESENT" if margin_fetcher_ready else "MISSING",
                "fields": "normalized by FinMindIntegrator when runtime data is available",
            },
            "institutional_integration": {
                "status": "PARTIAL" if institutional_integrated else "MISSING",
                "columns": ["foreign_buy", "trust_buy", "dealer_buy"],
                "scope": "top 200 by average traded value",
                "missing_policy": "source rows carry institutional_available=true; missing merged rows remain unavailable",
            },
            "margin_integration": {
                "status": "MISSING" if not margin_integrated else "PARTIAL",
                "columns": [
                    "margin_purchase_today_balance",
                    "margin_purchase_yesterday_balance",
                    "margin_purchase_balance_change",
                    "short_sale_today_balance",
                    "short_sale_yesterday_balance",
                    "short_sale_balance_change",
                    "margin_available",
                ] if margin_integrated else [],
            },
            "indicator_derivation": {
                "status": "PRESENT_IF_SOURCE_COLUMNS_EXIST" if indicator_derivation_ready else "MISSING",
                "columns": ["inst_buy_total", "inst_buy_ratio_3d/5d/10d", "trust_buy_days_3d/5d/10d"],
            },
            "production_ranking_exposure": {
                "status": "ABSENT" if not ranking_chip_columns else "PRESENT",
                "latest_ranking": repo_path(ranking_path),
                "chip_columns_in_latest_ranking": ranking_chip_columns,
            },
            "model_feature_risk": {
                "status": "REQUIRES_CONTRACT_GUARD",
                "reason": "numeric columns can be selected for training if they enter feature frames without metadata gating",
                "auto_numeric_selection_detected": model_auto_include_risk,
            },
        },
        "gate": {
            "path": repo_path(gate_path),
            "candidate": gate_candidate,
            "chip_data_contract_artifacts": [repo_path(path) for path in contract_files],
        },
        "blockers": blockers,
        "recommended_shadow_features": [
            {
                "name": "foreign_net_buy_5d_ratio",
                "definition": "外資近 5 日買賣超合計 / 近 5 日成交量合計",
                "purpose": "判斷法人是否仍在承接短線強勢股",
            },
            {
                "name": "trust_buy_days_5d",
                "definition": "投信近 5 日買超天數",
                "purpose": "台股波段資金續航輔助，不單獨作賣出訊號",
            },
            {
                "name": "dealer_net_buy_5d_ratio",
                "definition": "自營商近 5 日買賣超合計 / 近 5 日成交量合計",
                "purpose": "短線交易盤方向輔助",
            },
            {
                "name": "margin_balance_change_20d",
                "definition": "融資餘額 20 日變化率",
                "purpose": "辨識融資堆高但價格不跟的籌碼擁擠",
            },
            {
                "name": "margin_price_divergence",
                "definition": "融資餘額上升且 10 日報酬未同步上升",
                "purpose": "散戶接手風險，只能作 warning-only candidate",
            },
        ],
        "recommended_warning_candidates": [
            {
                "id": "price_break_after_overheat",
                "rule": "recent_return strong, then close < ma10 or ma20",
                "interpretation": "先過熱，後跌破短均，才像真的失速",
            },
            {
                "id": "rank_momentum_break",
                "rule": "top10 rank worsens repeatedly or exits top10 after strong run",
                "interpretation": "熱度排名退潮，比單看法人賣更接近產品可解釋訊號",
            },
            {
                "id": "volume_climax_reversal",
                "rule": "volume spike plus long upper shadow or bearish close",
                "interpretation": "爆量後追不上，可能是高檔換手或短線退潮",
            },
            {
                "id": "overheat_reversal_composite",
                "rule": "price/rank/volume weakening after strong 5D-20D move",
                "interpretation": "主線改測過熱後失速，chip_flow 只當輔助標籤",
            },
        ],
        "decision": decision,
        "next_steps": [
            "停止把 chip_flow 推向正式 warning channel；保留 blocked evidence。",
            "新開/接續 exit-signal 主線，優先測 price/rank/volume/overheat reversal。",
            "chip_flow 只可作研究 overlay 或推薦理由輔助，不進 production ranking score。",
            "若未來重測 chip_flow，必須先證明它在 price/rank/volume baseline 之外仍有增量；否則不再投入。",
        ],
    }


def render_markdown(payload: dict[str, Any]) -> str:
    matrix = payload["capability_matrix"]
    decision = payload["decision"]
    lines = [
        "# Chip Flow Readiness Report",
        "",
        f"- status: `{payload['status']}`",
        f"- decision: `{decision['status']}`",
        f"- shadow_status: `{decision['shadow_status']}`",
        f"- production_status: `{decision['production_status']}`",
        f"- first_promotable_shape: `{decision['first_promotable_shape']}`",
        "",
        "## 結論",
        "",
        decision["primary_read"],
        "",
        "## 能力盤點",
        "",
        "| layer | status | note |",
        "| --- | --- | --- |",
        f"| 三大法人 fetch | `{matrix['institutional_investor_fetch']['status']}` | FinMind institutional investors |",
        f"| 融資融券 fetch | `{matrix['margin_purchase_short_sale_fetch']['status']}` | runtime 有資料時由 integrator 正規化 |",
        f"| 三大法人整合 | `{matrix['institutional_integration']['status']}` | foreign/trust/dealer, top 200, 以 institutional_available 區分缺值 |",
        f"| 融資融券整合 | `{matrix['margin_integration']['status']}` | margin/short-sale balance + change, 以 margin_available 區分缺值 |",
        f"| 籌碼指標派生 | `{matrix['indicator_derivation']['status']}` | source columns 存在時可派生 inst/trust features |",
        f"| production ranking exposure | `{matrix['production_ranking_exposure']['status']}` | latest ranking chip columns: {matrix['production_ranking_exposure']['chip_columns_in_latest_ranking']} |",
        "",
        "## Blockers",
        "",
    ]
    lines.extend([f"- {item}" for item in payload["blockers"]] or ["- none"])
    lines.extend(
        [
            "",
            "## Recommended Warning Candidates",
            "",
            "| id | rule | interpretation |",
            "| --- | --- | --- |",
        ]
    )
    for item in payload["recommended_warning_candidates"]:
        lines.append(f"| `{item['id']}` | `{item['rule']}` | {item['interpretation']} |")
    lines.extend(
        [
            "",
            "## Next Steps",
            "",
        ]
    )
    lines.extend([f"- {item}" for item in payload["next_steps"]])
    return "\n".join(lines) + "\n"


def main() -> int:
    args = parse_args()
    output_path = resolve_path(args.output)
    markdown_path = (
        resolve_path(args.markdown_output)
        if args.markdown_output
        else output_path.with_suffix(".md")
    )
    payload = build_payload()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    markdown_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(render_markdown(payload), encoding="utf-8")
    print(
        json.dumps(
            {
                "status": "OK",
                "output": repo_path(output_path),
                "markdown": repo_path(markdown_path),
                "decision": payload["decision"]["status"],
                "blockers": payload["blockers"],
            },
            ensure_ascii=False,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
