from __future__ import annotations

import json
from copy import deepcopy

import pytest

from scripts.verify_industry_promotion_decision import (
    DEFAULT_DECISION,
    IndustryPromotionDecisionError,
    validate_decision,
)


def _payload() -> dict:
    return json.loads(DEFAULT_DECISION.read_text(encoding="utf-8"))


def test_committed_industry_decision_is_metric_derived_reject() -> None:
    assert validate_decision(_payload()) == "REJECT"


def test_decision_flip_and_weak_sample_fail_closed() -> None:
    flipped = deepcopy(_payload())
    flipped["decision"] = "GO"
    flipped["production_action"] = "CREATE_MINIMAL_PRODUCTION_CANDIDATE"
    with pytest.raises(IndustryPromotionDecisionError, match="decision mismatch"):
        validate_decision(flipped)

    weak = deepcopy(_payload())
    weak["sample"]["trade_days"] = 20
    with pytest.raises(IndustryPromotionDecisionError, match="acceptance floor"):
        validate_decision(weak)


def test_only_real_uplift_can_produce_go() -> None:
    positive = deepcopy(_payload())
    positive["metrics"]["return_uplift"] = 0.006
    positive["metrics"]["hit_rate_uplift"] = 0.001
    positive["decision"] = "GO"
    positive["production_action"] = "CREATE_MINIMAL_PRODUCTION_CANDIDATE"
    assert validate_decision(positive) == "GO"
