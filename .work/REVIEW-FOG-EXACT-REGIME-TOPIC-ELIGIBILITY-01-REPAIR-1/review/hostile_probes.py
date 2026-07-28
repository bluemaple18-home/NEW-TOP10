#!/usr/bin/env python3
"""Repair-1 targeted re-review hostile probes；不修改candidate或live runtime。"""

from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import run_autonomous_research as research


RANKING_DATE = "2026-01-02"
RUN_DATE = "2026-01-03"
RANKING_NAME = f"ranking_{RANKING_DATE}.csv"
EXACT = {"base_regime": "BROAD_RISK_ON", "family_tags": ["BIG_BULL"]}


def _write_regular(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("rank,stock_id\n1,0001\n", encoding="utf-8")


def _selection_payload(topic: research.ResearchTopic) -> dict[str, list[str]]:
    args = SimpleNamespace(
        execute_topic_count=1,
        from_queue=False,
        topic_index=0,
        execute=True,
        rerun=False,
        include_rejected=False,
    )
    with (
        patch.object(research, "load_topic_registry", return_value={}),
        patch.object(research, "load_last_run_at_by_topic", return_value={}),
    ):
        index = research.select_topics_for_run([topic], args)
        fallback = research.select_topics_for_run([topic], args)
        args.from_queue = True
        with patch.object(
            research,
            "load_next_action_queue",
            return_value=[{"topic_id": topic.topic_id}],
        ):
            queue = research.select_topics_for_run([topic], args)
    return {
        "index": [item.topic_id for item in index],
        "fallback": [item.topic_id for item in fallback],
        "queue": [item.topic_id for item in queue],
    }


def _probe_case(
    temp_root: Path,
    *,
    name: str,
    invalid_role: str | None,
    entry_kind: str,
) -> dict[str, object]:
    case_root = temp_root / name
    repo_root = case_root / "repo"
    candidate_dir = repo_root / "artifacts/backtest/candidate"
    baseline_dir = repo_root / "artifacts/backtest/baseline"
    candidate_entry = candidate_dir / RANKING_NAME
    baseline_entry = baseline_dir / RANKING_NAME
    _write_regular(candidate_entry)
    _write_regular(baseline_entry)

    if invalid_role is not None:
        entry = {
            "candidate": candidate_entry,
            "baseline": baseline_entry,
        }[invalid_role]
        entry.unlink()
        if entry_kind == "external_symlink":
            outside = case_root / "outside" / RANKING_NAME
            _write_regular(outside)
            entry.symlink_to(outside)
        elif entry_kind == "broken_symlink":
            entry.symlink_to(case_root / "missing" / RANKING_NAME)
        elif entry_kind == "non_regular_directory":
            entry.mkdir()
        else:
            raise ValueError(f"unknown entry_kind: {entry_kind}")

    with patch.object(research, "PROJECT_ROOT", repo_root):
        direct = research.exact_regime_topic_ranking_eligibility(
            candidate_dir=str(candidate_dir),
            baseline_dir=str(baseline_dir),
            allowed_dates={RANKING_DATE},
            as_of_date=RUN_DATE,
        )
        topic = research.topic_for_dir(
            {
                "repo_path": "artifacts/backtest/candidate",
                "count": 1,
            },
            baseline_dir="artifacts/backtest/baseline",
            ledger_candidates=[],
            external_signals=[],
            evidence_sources=[],
            current_regime=EXACT,
            coverage={"evidence_gap": 1.0},
            enforce_exact_regime_ranking_dates=True,
            exact_regime_allowed_dates={RANKING_DATE},
            exact_regime_as_of_date=RUN_DATE,
        )
        if topic is None:
            raise AssertionError("topic_for_dir unexpectedly returned None")
        selection = _selection_payload(topic)

    ranking_eligibility = (
        (topic.selection_rationale or {}).get("ranking_eligibility") or {}
    )
    observed = {
        "direct": direct,
        "topic": {
            "eligible": topic.eligible,
            "reason_code": topic.reason_code,
            "inventory_role": ranking_eligibility.get("inventory_role"),
        },
        "selection": selection,
    }
    if invalid_role is None:
        passed = (
            direct.get("eligible") is True
            and topic.eligible is True
            and topic.reason_code == "ELIGIBLE"
            and selection["index"] == [topic.topic_id]
            and selection["fallback"] == [topic.topic_id]
            and selection["queue"] == [topic.topic_id]
        )
    else:
        passed = (
            direct.get("eligible") is False
            and direct.get("reason_code") == "RANKING_INVENTORY_PATH_ESCAPE"
            and direct.get("inventory_role") == invalid_role
            and topic.eligible is False
            and topic.reason_code == "RANKING_INVENTORY_PATH_ESCAPE"
            and ranking_eligibility.get("inventory_role") == invalid_role
            and selection == {"index": [], "fallback": [], "queue": []}
        )
    return {
        "name": name,
        "passed": passed,
        "entry_kind": entry_kind,
        "invalid_role": invalid_role,
        "observed": observed,
    }


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="fog-repair1-review-") as raw_tmp:
        temp_root = Path(raw_tmp)
        cases = [
            _probe_case(
                temp_root,
                name="legal_regular_control",
                invalid_role=None,
                entry_kind="regular",
            ),
            _probe_case(
                temp_root,
                name="candidate_external_file_symlink",
                invalid_role="candidate",
                entry_kind="external_symlink",
            ),
            _probe_case(
                temp_root,
                name="baseline_external_file_symlink",
                invalid_role="baseline",
                entry_kind="external_symlink",
            ),
            _probe_case(
                temp_root,
                name="candidate_broken_file_symlink",
                invalid_role="candidate",
                entry_kind="broken_symlink",
            ),
            _probe_case(
                temp_root,
                name="baseline_broken_file_symlink",
                invalid_role="baseline",
                entry_kind="broken_symlink",
            ),
            _probe_case(
                temp_root,
                name="candidate_non_regular_entry",
                invalid_role="candidate",
                entry_kind="non_regular_directory",
            ),
            _probe_case(
                temp_root,
                name="baseline_non_regular_entry",
                invalid_role="baseline",
                entry_kind="non_regular_directory",
            ),
        ]

    failed = [case["name"] for case in cases if not case["passed"]]
    print(
        json.dumps(
            {
                "schema_version": "fog-exact-regime-repair1-review-probes.v1",
                "passed": not failed,
                "probe_count": len(cases),
                "failed_probes": failed,
                "results": cases,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
