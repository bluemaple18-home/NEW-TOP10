from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest

from scripts.verify_industry_promotion_decision import (
    DEFAULT_DECISION,
    IndustryPromotionDecisionError,
    derive_decision,
    validate_decision_file,
)


def _files(tmp_path: Path) -> tuple[Path, dict, dict]:
    decision = json.loads(DEFAULT_DECISION.read_text(encoding="utf-8"))
    source_replay = DEFAULT_DECISION.parent / decision["replay_path"]
    replay = json.loads(source_replay.read_text(encoding="utf-8"))
    replay_path = tmp_path / "replay.json"
    replay_path.write_text(json.dumps(replay), encoding="utf-8")
    decision["replay_path"] = replay_path.name
    decision["replay_sha256"] = hashlib.sha256(replay_path.read_bytes()).hexdigest()
    decision_path = tmp_path / "decision.json"
    decision_path.write_text(json.dumps(decision), encoding="utf-8")
    return decision_path, decision, replay


def test_committed_decision_is_bound_to_production_replay() -> None:
    assert validate_decision_file() == "NO_GO_INSUFFICIENT_PRODUCTION_HISTORY"


def test_replay_tamper_and_decision_flip_fail_closed(tmp_path: Path) -> None:
    decision_path, decision, replay = _files(tmp_path)
    replay["walkforward"]["return_uplift"] = 0.5
    (tmp_path / "replay.json").write_text(json.dumps(replay), encoding="utf-8")
    with pytest.raises(IndustryPromotionDecisionError, match="SHA-256 mismatch"):
        validate_decision_file(decision_path)

    decision_path, decision, _ = _files(tmp_path)
    decision["decision"] = "GO"
    decision["production_action"] = "CREATE_MINIMAL_PRODUCTION_CANDIDATE"
    decision_path.write_text(json.dumps(decision), encoding="utf-8")
    with pytest.raises(IndustryPromotionDecisionError, match="decision mismatch"):
        validate_decision_file(decision_path)


def test_path_escape_and_manifest_tamper_fail_closed(tmp_path: Path) -> None:
    decision_path, decision, replay = _files(tmp_path)
    decision["replay_path"] = "../replay.json"
    decision_path.write_text(json.dumps(decision), encoding="utf-8")
    with pytest.raises(IndustryPromotionDecisionError, match="escapes"):
        validate_decision_file(decision_path)

    decision_path, decision, replay = _files(tmp_path)
    replay["input"]["production_ranking_manifest"]["files"][0]["sha256"] = "0" * 64
    replay_path = tmp_path / "replay.json"
    replay_path.write_text(json.dumps(replay), encoding="utf-8")
    decision["replay_sha256"] = hashlib.sha256(replay_path.read_bytes()).hexdigest()
    decision_path.write_text(json.dumps(decision), encoding="utf-8")
    with pytest.raises(IndustryPromotionDecisionError, match="manifest checksum"):
        validate_decision_file(decision_path)


def test_daily_metric_tamper_fails_even_with_updated_outer_hash(tmp_path: Path) -> None:
    decision_path, decision, replay = _files(tmp_path)
    replay["walkforward"]["return_uplift"] = 0.5
    replay_path = tmp_path / "replay.json"
    replay_path.write_text(json.dumps(replay), encoding="utf-8")
    decision["replay_sha256"] = hashlib.sha256(replay_path.read_bytes()).hexdigest()
    decision_path.write_text(json.dumps(decision), encoding="utf-8")
    with pytest.raises(IndustryPromotionDecisionError, match="aggregate mismatch"):
        validate_decision_file(decision_path)


def test_only_sufficient_real_uplift_can_derive_go() -> None:
    replay = json.loads(
        (DEFAULT_DECISION.parent / "production_replay.json").read_text(encoding="utf-8")
    )
    gate = json.loads(DEFAULT_DECISION.read_text(encoding="utf-8"))["gate"]
    positive = deepcopy(replay)
    positive["walkforward"]["days"] = 60
    positive["walkforward"]["return_uplift"] = 0.006
    positive["walkforward"]["hit_rate_uplift"] = 0.001
    assert derive_decision(positive, gate) == "GO"
