"""產業動能 shadow monitor。

執行 M13-06 ex-self shadow ranking 研究，並輸出一行可被 automation log 讀取的狀態。
不修改 production ranking、模型或 API。
"""

from __future__ import annotations

import json
from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts import research_industry_momentum_walkforward


def main() -> int:
    result = research_industry_momentum_walkforward.main()
    if result != 0:
        return result

    report_path = PROJECT_ROOT / "artifacts" / "industry_momentum_walkforward_shadow.json"
    payload = json.loads(report_path.read_text(encoding="utf-8"))
    decision = payload.get("recommendation", {}).get("decision", "unknown")
    walkforward = payload.get("walkforward", {})
    return_uplift = walkforward.get("return_uplift")
    hit_rate_uplift = walkforward.get("hit_rate_uplift")
    concentration = walkforward.get("shadow_top_industry_concentration")
    print(
        "INDUSTRY_MOMENTUM_MONITOR_"
        f"{str(decision).upper()} return_uplift={return_uplift} "
        f"hit_rate_uplift={hit_rate_uplift} shadow_concentration={concentration}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
