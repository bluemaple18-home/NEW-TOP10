from __future__ import annotations

import copy
import json
import subprocess
from pathlib import Path

import pytest

from app.research.contracts import content_hash
from app.research import exact_regime_evidence_phase_closure as closure


def _actual_inputs() -> tuple[dict, dict]:
    current = json.loads((closure.PROJECT_ROOT / closure.CURRENT_RELATIVE).read_text())
    legacy = json.loads((closure.PROJECT_ROOT / closure.LEGACY_RELATIVE).read_text())
    return current, legacy


def _rehash(payload: dict, field: str) -> dict:
    payload[field] = content_hash(payload, omit={field})
    return payload


def test_actual_committed_evidence_closes_exact_h20_phase() -> None:
    payload = closure.build_closure()
    assert payload["status"] == "NO-GO_CLOSE_EXACT_H20_PHASE"
    assert payload["mainline"]["closed"] is True
    assert payload["forks"] == {
        "replay": "CLOSED_NO_GO",
        "external_backfill": "NOT_JUSTIFIED_BY_AVAILABLE_EVIDENCE",
        "scope_change": "PENDING_EXPLICIT_ARCHITECTURE_DECISION",
    }
    assert closure.validate_closure(payload) == []


def test_false_ready_current_evidence_is_blocked() -> None:
    current, legacy = _actual_inputs()
    current = copy.deepcopy(current)
    current["status"] = "READY_FOR_SCOPE_DECISION"
    current["feasible_identities"] = []
    _rehash(current, "audit_id")
    decision = closure.decide(current, legacy)
    assert decision["status"] == "BLOCKED_EVIDENCE_CONFLICT"
    assert any("FALSE_READY" in item for item in decision["reason_codes"])


def test_valid_feasible_current_evidence_authorizes_replay() -> None:
    current, legacy = _actual_inputs()
    current = copy.deepcopy(current)
    current["status"] = "READY_FOR_SCOPE_DECISION"
    current["reason_codes"] = []
    current["feasible_identities"] = ["PANIC_SELLING|"]
    _rehash(current, "audit_id")
    decision = closure.decide(current, legacy)
    assert decision["status"] == "GO_REPLAY"
    assert decision["forks"]["replay"] == "AUTHORIZED_BY_EVIDENCE"


def test_committed_reader_rejects_worktree_drift(tmp_path: Path) -> None:
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.email", "test@example.invalid"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "config", "user.name", "Test"], check=True)
    source = tmp_path / "evidence.json"
    source.write_text('{"status":"A"}\n', encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "evidence.json"], check=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "fixture"], check=True)
    payload, record = closure._committed_json(tmp_path, Path("evidence.json"))
    assert payload == {"status": "A"}
    assert record["commit_status"] == "MATCHED"
    source.write_text('{"status":"B"}\n', encoding="utf-8")
    with pytest.raises(closure.PhaseClosureError, match="EVIDENCE_WORKTREE_DRIFT"):
        closure._committed_json(tmp_path, Path("evidence.json"))


def test_validate_rejects_false_go() -> None:
    payload = {
        "schema_version": closure.SCHEMA_VERSION,
        "closure_id": "",
        "status": "GO_REPLAY",
        "current": {"feasible_identities": []},
        "legacy": {"feasible_identities": []},
        "mainline": {"closed": False},
    }
    _rehash(payload, "closure_id")
    assert "FALSE_GO" in closure.validate_closure(payload)
