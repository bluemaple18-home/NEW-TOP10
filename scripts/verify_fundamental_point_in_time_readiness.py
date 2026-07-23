#!/usr/bin/env python3
"""重算並驗證 Fundamental point-in-time readiness artifact。"""

from __future__ import annotations

import json
from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.build_fundamental_point_in_time_readiness import (  # noqa: E402
    DEFAULT_OUTPUT,
    build_payload,
)


def main() -> int:
    artifact = json.loads(DEFAULT_OUTPUT.read_text(encoding="utf-8"))
    assert artifact == build_payload()
    assert artifact["decision"] == "BLOCKED_DATA_COVERAGE"
    assert artifact["promotion_allowed"] is False
    assert artifact["coverage"]["recent_252_trade_days"]["days_meeting_research_gate"] == 0
    reason_codes = {row["reason_code"] for row in artifact["warnings_and_exclusions"]}
    assert "FUNDAMENTAL_CACHE_COVERAGE_BELOW_MODEL_GATE" in reason_codes
    assert "POINT_IN_TIME_DAILY_COVERAGE_BELOW_RESEARCH_GATE" in reason_codes
    print("FUNDAMENTAL_POINT_IN_TIME_READINESS_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
