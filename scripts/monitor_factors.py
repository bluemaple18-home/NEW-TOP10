"""產生 factor IC / coverage / turnover 監控報告。"""

from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from app.monitoring import FactorMonitor


def main() -> int:
    report = FactorMonitor().run()
    print(f"FACTOR_MONITOR_{report.status} factors={report.summary['factor_count']} warns={report.summary['warn_count']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
