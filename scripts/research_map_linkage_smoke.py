#!/usr/bin/env python3
"""產生 3 筆 research map 連動 smoke 記錄。

只寫 artifact contract，不跑訓練、不跑回測、不改 production ranking。
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from research_map_contract import build_combo_registry, now_utc, write_jsonl


PROJECT_ROOT = Path(__file__).resolve().parents[1]
AUTO_DIR = PROJECT_ROOT / "artifacts" / "autonomous_research"
EVIDENCE_DIR = PROJECT_ROOT / "artifacts" / "research_map" / "evidence"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="write research map linkage smoke JSONL rows")
    parser.add_argument("--date", required=True)
    parser.add_argument("--count", type=int, default=3)
    parser.add_argument("--replace-smoke", action="store_true")
    return parser.parse_args()


def repo_path(path: Path) -> str:
    return str(path.resolve().relative_to(PROJECT_ROOT))


def load_autonomous_module() -> Any:
    path = PROJECT_ROOT / "scripts" / "run_autonomous_research.py"
    spec = importlib.util.spec_from_file_location("run_autonomous_research", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("無法載入 run_autonomous_research.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def load_topics(max_topics: int = 10000) -> list[dict[str, Any]]:
    module = load_autonomous_module()
    topic_args = SimpleNamespace(
        candidate_dir=None,
        baseline_dir="artifacts/backtest/historical_rankings_current_model",
        min_ranking_files=3,
        max_topics=max_topics,
    )
    topics = [module.topic_to_json(topic) for topic in module.generate_topics(topic_args)]
    registry_path = AUTO_DIR / "topic_registry.json"
    if registry_path.exists():
        registry = json.loads(registry_path.read_text(encoding="utf-8"))
        by_id = {row.get("topic_id"): row for row in registry.get("topics", []) if row.get("topic_id")}
        topics = [{**topic, **by_id.get(topic.get("topic_id"), {})} for topic in topics]
    return topics


def smoke_rows(date: str, count: int) -> list[dict[str, Any]]:
    topics = load_topics()
    combos = build_combo_registry(topics)
    if len(combos) < count:
        raise RuntimeError(f"combo registry too small: {len(combos)}")
    decisions = [
        ("CONFIRMED_FOR_NEXT_REPLAY", "effective", 0.12, 0.08, 0.01),
        ("PARTIAL_SCORE_ONLY", "risk_worse_return_positive", 0.04, 0.05, -0.03),
        ("REJECTED_BY_STRATEGY_MATRIX", "rejected", -0.08, -0.02, -0.05),
    ]
    rows = []
    EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
    for index, combo in enumerate(combos[:count]):
        decision, insight_level, score_delta, return_delta, drawdown_delta = decisions[index % len(decisions)]
        artifact_path = EVIDENCE_DIR / f"research_map_linkage_smoke_{index + 1:02d}.json"
        artifact_payload = {
            "schema_version": "research-map-linkage-smoke-artifact.v1",
            "date": date,
            "combo_id": combo["combo_id"],
            "dimensions": combo["dimensions"],
            "decision": decision,
            "insight_level": insight_level,
            "contract": {
                "research_only": True,
                "does_not_train_model": True,
                "does_not_change_production_ranking": True,
            },
        }
        artifact_path.write_text(json.dumps(artifact_payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        rows.append(
            {
                "schema_version": "research-run-history-jsonl.v1",
                "source": "research_map_linkage_smoke",
                "combo_id": combo["combo_id"],
                "topic_id": combo["topic_id"],
                "dimensions": combo["dimensions"],
                "status": "OK",
                "score_delta": score_delta,
                "return_delta": return_delta,
                "drawdown_delta": drawdown_delta,
                "decision": decision,
                "insight_level": insight_level,
                "artifact_path": repo_path(artifact_path),
                "finished_at": now_utc(),
            }
        )
    return rows


def main() -> int:
    args = parse_args()
    rows = smoke_rows(args.date, args.count)
    output = AUTO_DIR / "run_history.jsonl"
    write_jsonl(output, rows, replace_smoke=args.replace_smoke)
    print(json.dumps({"status": "OK", "rows": len(rows), "output": repo_path(output)}, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
