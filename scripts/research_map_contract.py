#!/usr/bin/env python3
"""舊版 script import 的 research map contract 相容入口。

唯一實作位於 :mod:`app.research.map_contract`；本模組只保留既有
``from research_map_contract import ...`` 與 ``scripts.research_map_contract``。
"""

import sys as _sys
from pathlib import Path as _Path


_PROJECT_ROOT = _Path(__file__).resolve().parents[1]
if str(_PROJECT_ROOT) not in _sys.path:
    _sys.path.insert(0, str(_PROJECT_ROOT))

from app.research.map_contract import *  # noqa: F401,F403
from app.research.map_contract import __all__
