from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from app.research.contracts import content_hash
from app.research import entry_regime_cohort_architecture_decision as decision


def _rehash(payload: dict) -> dict:
    payload["decision_id"] = content_hash(payload, omit={"decision_id"})
    return payload


def test_actual_sources_select_only_outcome_free_feasibility() -> None:
    payload = decision.build_decision()
    assert payload["status"] == decision.SELECTED_STATUS
    assert payload["successor"] == {
        "card_id": decision.SUCCESSOR_CARD,
        "authorized_action": "OUTCOME_FREE_CAPACITY_FEASIBILITY_AUDIT_ONLY",
        "only_go_status": "FEASIBLE_FOR_PREREGISTRATION",
        "no_go_status": "NO_GO_INSUFFICIENT_ENTRY_COHORT_CAPACITY",
    }
    assert payload["safety"] == {
        "research_only": True,
        "replay_ready": False,
        "promotion_ready": False,
        "production_ready": False,
        "runtime_change_allowed": False,
    }
    assert decision.validate_decision(payload) == []


def test_closure_parser_rejects_open_or_go_phase() -> None:
    closure_path = decision.PROJECT_ROOT / decision.phase_closure.EVIDENCE_RELATIVE
    closure = json.loads(closure_path.read_text(encoding="utf-8"))
    closure["status"] = "GO_REPLAY"
    closure["mainline"]["closed"] = False
    closure["current"]["feasible_identities"] = ["BIG_BULL|"]
    closure["closure_id"] = content_hash(closure, omit={"closure_id"})
    with pytest.raises(decision.ArchitectureDecisionError, match="EXACT_H20_PHASE_NOT_CLOSED"):
        decision._closure_from_bytes(json.dumps(closure).encode("utf-8"))


def test_closure_parser_rejects_invalid_closure_hash() -> None:
    closure_path = decision.PROJECT_ROOT / decision.phase_closure.EVIDENCE_RELATIVE
    closure = json.loads(closure_path.read_text(encoding="utf-8"))
    closure["closure_id"] = "sha256:" + "0" * 64
    with pytest.raises(decision.ArchitectureDecisionError, match="CLOSURE_INVALID"):
        decision._closure_from_bytes(json.dumps(closure).encode("utf-8"))


def test_committed_source_rejects_worktree_drift(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    source = tmp_path / "source.py"
    source.write_text("VALUE = 1\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "source.py"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "fixture"], check=True)
    raw, record = decision._committed_source(tmp_path, Path("source.py"))
    assert raw == b"VALUE = 1\n"
    assert record["commit_status"] == "MATCHED"
    source.write_text("VALUE = 2\n", encoding="utf-8")
    with pytest.raises(decision.ArchitectureDecisionError, match="SOURCE_WORKTREE_DRIFT"):
        decision._committed_source(tmp_path, Path("source.py"))


@pytest.mark.parametrize(
    "field",
    ["replay_ready", "promotion_ready", "production_ready", "runtime_change_allowed"],
)
def test_validation_rejects_false_readiness(field: str) -> None:
    payload = copy.deepcopy(decision.build_decision())
    payload["safety"][field] = True
    _rehash(payload)
    assert f"FALSE_READINESS:{field}" in decision.validate_decision(payload)


def test_decision_is_deterministic_and_portable() -> None:
    first = decision.build_decision()
    second = decision.build_decision()
    assert first == second
    serialized = json.dumps(first, ensure_ascii=False)
    assert "/Users/" not in serialized
    assert "generated_at" not in serialized
    assert "timestamp" not in serialized


def test_architecture_contract_contains_fail_closed_markers() -> None:
    raw = (decision.PROJECT_ROOT / decision.ARCHITECTURE_RELATIVE).read_bytes()
    assert decision._required_architecture_markers(raw) == []
