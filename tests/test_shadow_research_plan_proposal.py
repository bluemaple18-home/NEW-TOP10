from __future__ import annotations

import copy
import json
import subprocess
import sys
from pathlib import Path

import pytest

from app.research import shadow_plan_proposal as proposal
from app.research.contracts import canonical_json_bytes, content_hash


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_authoritative_sources_build_one_deterministic_adjacent_proposal() -> None:
    first = proposal.build_proposal()
    second = proposal.build_proposal()

    assert first == second
    assert proposal.encode_proposal(first) == proposal.encode_proposal(second)
    assert first["status"] == "PASS"
    assert first["counts"] == {"deduped": 0, "proposals": 1, "source_rows": 1}
    assert first["boundary"] == {
        "canonical_queue_write_allowed": False,
        "execution_allowed": False,
        "production_change_allowed": False,
        "scheduler_change_allowed": False,
    }
    row = first["proposals"][0]
    assert row["parameter"] == "horizon"
    assert row["direction"] == "HIGHER_LOOKS_BETTER"
    assert row["current_value"] == 10
    assert row["proposed_next_value"] == 20
    assert row["catalog_bounds"] == {"maximum": 20, "minimum": 3}
    assert row["scope"]["regime_id"] == "NARROW_LEADER|BIG_BULL"
    assert row["source"]["semantic_action_id"].startswith("sha256:")
    assert proposal.verify_proposal(first)["status"] == "PASS"


def test_proposal_identity_and_bytes_exclude_time() -> None:
    payload = proposal.build_proposal()

    assert "generated_at" not in payload
    assert payload["semantic_hash"] == content_hash(
        payload,
        omit={"proposal_set_id", "semantic_hash"},
    )
    assert proposal.encode_proposal(payload) == canonical_json_bytes(payload) + b"\n"


def test_committed_proposal_evidence_is_authoritative() -> None:
    payload = proposal.load_json(proposal.DEFAULT_OUTPUT)
    verification = proposal.load_json(proposal.DEFAULT_VERIFICATION)

    assert payload == proposal.build_proposal()
    assert verification == proposal.verify_proposal(payload)


@pytest.mark.parametrize(
    ("field", "value", "error"),
    [
        ("priority_band", "OBSERVE", "SOURCE_ROW_0:PRIORITY_NOT_HIGH"),
        ("action", "EXECUTE_RESEARCH", "SOURCE_ROW_0:ACTION_NOT_SUPPORTED"),
        ("direction", "LOWER_LOOKS_BETTER", "SOURCE_ROW_0:DIRECTION_NOT_UPWARD"),
    ],
)
def test_non_admissible_source_rows_fail_closed(
    field: str,
    value: str,
    error: str,
) -> None:
    projection = _load(proposal.DEFAULT_PROJECTION)
    projection["rows"][0][field] = value

    errors = proposal.validate_source_documents(
        projection,
        _load(proposal.DEFAULT_POLICY),
        _load(proposal.DEFAULT_CATALOG),
    )

    assert error in errors


def test_no_adjacent_value_returns_structured_no_go() -> None:
    projection = _load(proposal.DEFAULT_PROJECTION)
    catalog = _load(proposal.DEFAULT_CATALOG)
    horizon = next(row for row in catalog["dimensions"] if row["id"] == "horizon")
    horizon["coverage_values"] = [3, 5, 10, 20]

    payload = proposal._derive_proposal(
        projection,
        _load(proposal.DEFAULT_POLICY),
        catalog,
        source_receipt={"test_only": True},
    )

    assert payload["status"] == "NO-GO"
    assert payload["reason_codes"] == ["NO-GO_NO_ADJACENT_VALUE"]
    assert payload["proposals"] == []


def test_duplicate_dedupes_and_semantic_collision_fails_closed() -> None:
    row = proposal.build_proposal()["proposals"][0]
    deduped, count = proposal.dedupe_proposals([row, copy.deepcopy(row)])
    assert deduped == [row]
    assert count == 1

    collision = copy.deepcopy(row)
    collision["proposed_next_value"] = 999
    with pytest.raises(proposal.ProposalBoundaryError, match="SEMANTIC_PROPOSAL_COLLISION"):
        proposal.dedupe_proposals([row, collision])


@pytest.mark.parametrize("case", ["external", "traversal"])
def test_builder_rejects_external_or_traversal_source_before_write(
    tmp_path: Path,
    case: str,
) -> None:
    path = tmp_path / "projection.json" if case == "external" else Path("docs/../projection.json")

    with pytest.raises(proposal.ProposalBoundaryError, match="PROJECTION_NOT_COMMITTED_PATH"):
        proposal.build_proposal(projection_path=path)


@pytest.mark.parametrize(
    ("relative", "error"),
    [
        (proposal.DEFAULT_PROJECTION_RELATIVE, "PROJECTION_CONTENT_DRIFT"),
        (proposal.DEFAULT_POLICY_RELATIVE, "POLICY_CONTENT_DRIFT"),
        (proposal.DEFAULT_CATALOG_RELATIVE, "CATALOG_CONTENT_DRIFT"),
    ],
)
def test_committed_source_content_drift_fails_closed(
    tmp_path: Path,
    relative: Path,
    error: str,
) -> None:
    for source_relative, source in proposal.AUTHORITATIVE_SOURCES.items():
        target = tmp_path / source_relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(source.read_bytes())
    drifted = tmp_path / relative
    drifted.write_bytes(drifted.read_bytes() + b"\n")

    with pytest.raises(proposal.ProposalBoundaryError, match=error):
        proposal.build_proposal(
            projection_path=tmp_path / proposal.DEFAULT_PROJECTION_RELATIVE,
            policy_path=tmp_path / proposal.DEFAULT_POLICY_RELATIVE,
            catalog_path=tmp_path / proposal.DEFAULT_CATALOG_RELATIVE,
            project_root=tmp_path,
        )


def test_verifier_rejects_tampered_body_even_after_top_level_rehash() -> None:
    payload = proposal.build_proposal()
    payload["proposals"][0]["proposed_next_value"] = 999
    payload["semantic_hash"] = content_hash(
        payload,
        omit={"proposal_set_id", "semantic_hash"},
    )
    payload["proposal_set_id"] = content_hash(
        {
            "schema_version": payload["schema_version"],
            "semantic_hash": payload["semantic_hash"],
        }
    )

    report = proposal.verify_proposal(payload)

    assert report["status"] == "FAIL"
    assert "PROPOSAL_0:NEXT_VALUE_NOT_ADJACENT" in report["errors"]


def test_cli_self_test_passes() -> None:
    completed = subprocess.run(
        [sys.executable, "scripts/verify_shadow_research_plan_proposal.py", "--self-test"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert json.loads(completed.stdout)["status"] == "PASS"
