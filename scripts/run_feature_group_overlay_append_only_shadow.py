#!/usr/bin/env python3
"""任意 frozen feature-group overlay 的 append-only shadow CLI。"""

from pathlib import Path
import sys


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.run_chip_overlay_append_only_shadow import main


if __name__ == "__main__":
    raise SystemExit(main())
