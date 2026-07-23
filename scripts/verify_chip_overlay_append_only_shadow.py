#!/usr/bin/env python3
"""驗證 chip overlay append-only shadow 的不可變契約。"""

from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_chip_overlay_append_only_shadow import (  # noqa: E402
    empty_ledger,
    merge_append_only,
    regime_anchor,
    summarize,
    validate_config,
    validate_ledger,
)


CONFIG_PATH = PROJECT_ROOT / "config" / "chip_liquidity_overlay_shadow_v1.json"


def config() -> dict:
    return json.loads(CONFIG_PATH.read_text(encoding="utf-8"))


def observation(day: int, delta: float = 0.001) -> dict:
    date_text = f"2026-{8 + (day - 1) // 28:02d}-{1 + (day - 1) % 28:02d}"
    baseline_ids = [f"{index:04d}" for index in range(1, 11)]
    overlay_ids = [f"{index:04d}" for index in range(2, 12)]
    bucket = {
        "valid_trade_count": 10,
        "avg_net_return": 0.01,
        "hit_rate": 0.6,
        "max_group_exposure": 0.3,
        "trades": [],
    }
    return {
        "ranking_date": date_text,
        "regime_label": "RISK_OFF",
        "baseline": {**bucket, "stock_ids": baseline_ids},
        "overlay": {**bucket, "stock_ids": overlay_ids, "avg_net_return": 0.01 + delta},
        "return_delta": delta,
    }


def verify_append_only() -> None:
    candidate = config()
    ledger = empty_ledger(candidate, CONFIG_PATH)
    first = observation(1)
    appended, _ = merge_append_only(ledger, [first], [])
    assert appended == 1
    original = deepcopy(ledger["observations"][0])
    replacement = observation(1, delta=-0.5)
    appended, _ = merge_append_only(ledger, [replacement], [])
    assert appended == 0
    assert ledger["observations"][0] == original


def verify_config_drift_fails() -> None:
    candidate = config()
    ledger = empty_ledger(candidate, CONFIG_PATH)
    changed = deepcopy(candidate)
    changed["portfolio"]["chip_overlay_weight"] = 0.2
    try:
        validate_ledger(ledger, changed)
    except ValueError as exc:
        assert "config" in str(exc)
    else:
        raise AssertionError("config drift 應拒絕沿用 ledger")


def verify_first_sixty_are_sealed() -> None:
    candidate = config()
    ledger = empty_ledger(candidate, CONFIG_PATH)
    ledger["observations"] = [observation(day) for day in range(1, 61)]
    first = summarize(ledger, candidate)
    assert first["status"] == "READY_FOR_INDEPENDENT_REVIEW"
    ledger["observations"].append(observation(61, delta=-0.9))
    after = summarize(ledger, candidate)
    assert after["status"] == first["status"]
    assert after["metrics"] == first["metrics"]
    assert after["acceptance_end"] == first["acceptance_end"]


def verify_regime_anchor_detects_drift() -> None:
    payload = {
        "rows": [
            {"trade_date": "2026-07-07", "regime_label": "RISK_OFF"},
            {"trade_date": "2026-07-08", "regime_label": "MIXED_NEUTRAL"},
            {"trade_date": "2026-07-09", "regime_label": "NARROW_LEADER"},
        ]
    }
    count, digest = regime_anchor(payload, "2026-07-08")
    payload["rows"][0]["regime_label"] = "NARROW_LEADER"
    changed_count, changed_digest = regime_anchor(payload, "2026-07-08")
    assert count == changed_count == 2
    assert digest != changed_digest


def main() -> int:
    candidate = config()
    validate_config(candidate)
    verify_append_only()
    verify_config_drift_fails()
    verify_first_sixty_are_sealed()
    verify_regime_anchor_detects_drift()
    print("CHIP_OVERLAY_APPEND_ONLY_SHADOW_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
