#!/usr/bin/env python3
"""A6 closure verifier：單一入口重建 A1-A5 並輸出 bridge inventory receipt。"""

from __future__ import annotations

import sys
from pathlib import Path

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.research.a6_closure import main


if __name__ == "__main__":
    raise SystemExit(main())
