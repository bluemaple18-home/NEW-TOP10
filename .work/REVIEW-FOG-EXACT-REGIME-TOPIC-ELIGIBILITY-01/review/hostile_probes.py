#!/usr/bin/env python3
"""Strict review hostile probes；只讀 candidate code，不操作 live runtime。"""

from __future__ import annotations

import json
import sys
import tempfile
from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

REPO_ROOT = Path(__file__).resolve().parents[3]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts import run_autonomous_research as research
from scripts import run_backtest_strategy_matrix as matrix


EXACT = {"base_regime": "BROAD_RISK_ON", "family_tags": ["BIG_BULL"]}
ALLOWED_DATE = "2026-01-02"
RUN_DATE = "2026-01-03"


def _write_ranking(directory: Path, ranking_date: str) -> Path:
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"ranking_{ranking_date}.csv"
    path.write_text("rank,stock_id\n", encoding="utf-8")
    return path


def _eligibility(
    repo_root: Path,
    candidate_dir: Path,
    baseline_dir: Path,
    *,
    allowed_dates: set[str] | None = {ALLOWED_DATE},
    as_of_date: str = RUN_DATE,
) -> dict[str, object]:
    with patch.object(research, "PROJECT_ROOT", repo_root):
        return research.exact_regime_topic_ranking_eligibility(
            candidate_dir=str(candidate_dir),
            baseline_dir=str(baseline_dir),
            allowed_dates=allowed_dates,
            as_of_date=as_of_date,
        )


def _history_rows() -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    cursor = date(2026, 1, 1)
    for episode_index in range(8):
        if episode_index:
            rows.append(
                {
                    "trade_date": cursor.isoformat(),
                    "as_of_date": cursor.isoformat(),
                    **EXACT,
                    "is_transition": True,
                }
            )
            cursor += timedelta(days=1)
        for _ in range(12):
            rows.append(
                {
                    "trade_date": cursor.isoformat(),
                    "as_of_date": cursor.isoformat(),
                    **EXACT,
                }
            )
            cursor += timedelta(days=1)
    return rows


def _ineligible_topic(topic_id: str = "review:ineligible") -> research.ResearchTopic:
    return research.ResearchTopic(
        topic_id=topic_id,
        title="ineligible",
        hypothesis="hostile probe",
        validation_plan="none",
        runner="strategy_matrix_comparison",
        candidate_dir="artifacts/backtest/candidate",
        baseline_dir="artifacts/backtest/baseline",
        score=1.0,
        reasons=[],
        evidence_sources=[],
        ranking_file_count=1,
        eligible=False,
        reason_code="NO_EXACT_REGIME_RANKING_DATE",
    )


def main() -> int:
    results: list[dict[str, object]] = []

    def record(name: str, passed: bool, observed: object) -> None:
        results.append({"name": name, "passed": bool(passed), "observed": observed})

    with tempfile.TemporaryDirectory(prefix="fog-review-") as raw_tmp:
        temp_root = Path(raw_tmp)
        repo_root = temp_root / "repo"
        repo_root.mkdir()

        candidate = repo_root / "artifacts/backtest/candidate"
        baseline = repo_root / "artifacts/backtest/baseline"

        _write_ranking(candidate, ALLOWED_DATE)
        _write_ranking(baseline, "2025-01-02")
        observed = _eligibility(repo_root, candidate, baseline)
        record(
            "candidate_legal_baseline_zero_intersection",
            observed.get("eligible") is False
            and observed.get("reason_code") == "NO_EXACT_REGIME_RANKING_DATE"
            and observed.get("inventory_role") == "baseline",
            observed,
        )

        for path in baseline.iterdir():
            path.unlink()
        for path in candidate.iterdir():
            path.unlink()
        _write_ranking(candidate, "2025-01-02")
        _write_ranking(baseline, ALLOWED_DATE)
        observed = _eligibility(repo_root, candidate, baseline)
        record(
            "baseline_legal_candidate_zero_intersection",
            observed.get("eligible") is False
            and observed.get("reason_code") == "NO_EXACT_REGIME_RANKING_DATE"
            and observed.get("inventory_role") == "candidate",
            observed,
        )

        for path in candidate.iterdir():
            path.unlink()
        _write_ranking(candidate, ALLOWED_DATE)
        observed = _eligibility(repo_root, candidate, baseline)
        record(
            "both_legal_control",
            observed.get("eligible") is True
            and observed.get("candidate_exact_date_count") == 1
            and observed.get("baseline_exact_date_count") == 1,
            observed,
        )

        for path in candidate.iterdir():
            path.unlink()
        (candidate / "ranking_not-a-date.csv").write_text(
            "rank,stock_id\n",
            encoding="utf-8",
        )
        observed = _eligibility(repo_root, candidate, baseline)
        record(
            "malformed_iso_date",
            observed.get("eligible") is False
            and observed.get("reason_code") == "MALFORMED_RANKING_DATE",
            observed,
        )

        for path in candidate.iterdir():
            path.unlink()
        _write_ranking(candidate, "2026-02-30")
        observed = _eligibility(repo_root, candidate, baseline)
        record(
            "impossible_iso_date",
            observed.get("eligible") is False
            and observed.get("reason_code") == "MALFORMED_RANKING_DATE",
            observed,
        )

        for path in candidate.iterdir():
            path.unlink()
        _write_ranking(candidate, "2026-02-01")
        observed = _eligibility(repo_root, candidate, baseline)
        record(
            "future_only_inventory",
            observed.get("eligible") is False
            and observed.get("reason_code") == "FUTURE_ONLY_RANKING_DATE"
            and observed.get("inventory_role") == "candidate",
            observed,
        )

        outside_dir = temp_root / "outside"
        _write_ranking(outside_dir, ALLOWED_DATE)
        observed = _eligibility(repo_root, outside_dir, baseline)
        record(
            "absolute_path_escape",
            observed.get("eligible") is False
            and observed.get("reason_code") == "RANKING_INVENTORY_PATH_ESCAPE",
            observed,
        )

        symlink_dir = repo_root / "artifacts/backtest/symlink-dir"
        symlink_dir.symlink_to(outside_dir, target_is_directory=True)
        observed = _eligibility(repo_root, symlink_dir, baseline)
        record(
            "symlink_directory_escape",
            observed.get("eligible") is False
            and observed.get("reason_code") == "RANKING_INVENTORY_PATH_ESCAPE",
            observed,
        )

        symlink_file_dir = repo_root / "artifacts/backtest/symlink-file"
        symlink_file_dir.mkdir()
        outside_file = outside_dir / f"ranking_{ALLOWED_DATE}.csv"
        outside_file.write_text(
            "rank,stock_id\n1,9999\n",
            encoding="utf-8",
        )
        (symlink_file_dir / outside_file.name).symlink_to(outside_file)
        eligibility_observed = _eligibility(
            repo_root,
            symlink_file_dir,
            baseline,
        )
        with matrix.exact_ranking_file_scope({ALLOWED_DATE}):
            selected_paths = (
                matrix.run_portfolio_replay.run_backtest_replay.ranking_files(
                    symlink_file_dir,
                    None,
                )
            )
        matrix_rows = (
            matrix.run_portfolio_replay.run_backtest_replay.read_ranking(
                selected_paths[0],
                10,
            )
        )
        observed = {
            "eligibility": eligibility_observed,
            "matrix_selected_symlink": selected_paths[0].is_symlink(),
            "matrix_read_stock_id": matrix_rows[0]["stock_id"],
        }
        record(
            "symlink_file_escape",
            eligibility_observed.get("eligible") is False
            and eligibility_observed.get("reason_code")
            == "RANKING_INVENTORY_PATH_ESCAPE",
            observed,
        )

        observed = _eligibility(
            repo_root,
            candidate,
            baseline,
            allowed_dates=None,
        )
        record(
            "missing_canonical_authority",
            observed.get("eligible") is False
            and observed.get("reason_code") == "MISSING_EXACT_REGIME_AUTHORITY",
            observed,
        )

        for label, row in (
            (
                "current_transition",
                {
                    "trade_date": RUN_DATE,
                    "as_of_date": RUN_DATE,
                    **EXACT,
                    "is_transition": True,
                },
            ),
            (
                "current_unknown",
                {
                    "trade_date": RUN_DATE,
                    "as_of_date": RUN_DATE,
                    "base_regime": "UNKNOWN",
                    "family_tags": [],
                },
            ),
        ):
            history_path = repo_root / f"{label}.json"
            history_path.write_text(
                json.dumps({"rows": [row]}),
                encoding="utf-8",
            )
            try:
                research.current_regime_context(history_path, RUN_DATE)
            except ValueError as error:
                record(label, True, str(error))
            else:
                record(label, False, "accepted")

        topic = _ineligible_topic()
        selection_args = SimpleNamespace(
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
            index_selection = research.select_topics_for_run([topic], selection_args)
            fallback_selection = research.select_topics_for_run(
                [_ineligible_topic("review:other"), topic],
                selection_args,
            )
            selection_args.from_queue = True
            with patch.object(
                research,
                "load_next_action_queue",
                return_value=[{"topic_id": topic.topic_id}],
            ):
                queue_selection = research.select_topics_for_run(
                    [topic],
                    selection_args,
                )
        observed = {
            "index": [item.topic_id for item in index_selection],
            "fallback": [item.topic_id for item in fallback_selection],
            "queue": [item.topic_id for item in queue_selection],
        }
        record(
            "index_fallback_queue_exclude_ineligible",
            observed == {"index": [], "fallback": [], "queue": []},
            observed,
        )

        lineage = {
            "schema_version": "fog-daily-source-lineage.v1",
            "features_path": "data/clean/features.parquet",
            "features_sha256": "a" * 64,
            "daily_source_date": "2026-01-02",
        }
        payload_args = SimpleNamespace(
            execute=True,
            date=RUN_DATE,
            features="data/clean/features.parquet",
            baseline_dir="artifacts/backtest/baseline",
            candidate_dir=None,
            topic_index=0,
            execute_topic_count=1,
            from_queue=True,
            rerun=False,
            include_rejected=False,
            max_ranking_files=1,
            horizons="3",
            stop_loss_pcts="none",
            take_profit_pcts="none",
            max_group_exposures="none",
            no_manager_update=True,
            closed_regime_research=True,
            market_regime_history="artifacts/market_regime_history.json",
            research_contract="config/regime_research_contract.json",
            coverage_map=None,
        )
        no_work_payload = research.build_payload(
            payload_args,
            topics=[],
            selected_topics_for_run=[],
            topic_runs=[],
            steps=[],
            outcome={"decision": "NO_EXECUTABLE_TOPIC", "promotion_allowed": False},
            outputs={},
            source_lineage=lineage,
        )
        record(
            "no_executable_topic_keeps_daily_lineage",
            no_work_payload.get("outcome", {}).get("decision")
            == "NO_EXECUTABLE_TOPIC"
            and no_work_payload.get("source_lineage") == lineage,
            {
                "decision": no_work_payload.get("outcome", {}).get("decision"),
                "source_lineage": no_work_payload.get("source_lineage"),
            },
        )

        legacy_topic = research.topic_for_dir(
            {"repo_path": "artifacts/backtest/legacy", "count": 1},
            baseline_dir="artifacts/backtest/baseline",
            ledger_candidates=[],
            external_signals=[],
            evidence_sources=[],
        )
        record(
            "legacy_non_closed_mode",
            legacy_topic is not None
            and legacy_topic.eligible is True
            and legacy_topic.reason_code == "LEGACY_TOPIC",
            (
                {
                    "eligible": legacy_topic.eligible,
                    "reason_code": legacy_topic.reason_code,
                }
                if legacy_topic
                else None
            ),
        )

        contract = json.loads(
            (
                REPO_ROOT / "config/regime_research_contract.json"
            ).read_text(encoding="utf-8")
        )
        rows = _history_rows()
        allowed = research.canonical_exact_regime_allowed_dates(
            rows=rows,
            contract=contract,
            regime_identity=EXACT,
            horizons="3,5,10",
            as_of_date=str(rows[-1]["trade_date"]),
        )
        lineage_authority = research.statistical_lineage_authority(
            rows=rows,
            contract=contract,
            regime_id=research.regime_identity_id(EXACT),
            horizons=[3, 5, 10],
        )
        matrix_development_dates = {
            str(trade_date)
            for episode in lineage_authority["split_artifact"]["development"]
            for trade_date in episode["trade_dates"]
        }
        record(
            "scheduler_dates_match_matrix_development_split",
            allowed == matrix_development_dates,
            {
                "scheduler_date_count": len(allowed),
                "matrix_development_date_count": len(matrix_development_dates),
            },
        )

    failed = [item["name"] for item in results if not item["passed"]]
    print(
        json.dumps(
            {
                "schema_version": "fog-exact-regime-review-hostile-probes.v1",
                "passed": not failed,
                "probe_count": len(results),
                "failed_probes": failed,
                "results": results,
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if not failed else 1


if __name__ == "__main__":
    raise SystemExit(main())
