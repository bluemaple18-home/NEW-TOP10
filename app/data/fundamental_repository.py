"""基本面 cache repository。

API 只讀本地 cache；外部 Goodinfo/MOPS 抓取流程應在離線任務中寫入 cache。
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any


class FundamentalRepository:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.cache_dir = project_root / "data" / "fundamentals"
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def cache_path(self, stock_id: str) -> Path:
        safe_id = self._safe_stock_id(stock_id)
        path = (self.cache_dir / f"{safe_id}.json").resolve()
        if self.cache_dir.resolve() not in path.parents:
            raise ValueError(f"非法基本面 cache 路徑：{stock_id}")
        return path

    @lru_cache(maxsize=512)
    def load_cached(self, stock_id: str) -> dict[str, Any] | None:
        path = self.cache_path(stock_id)
        if not path.exists():
            return None
        return json.loads(path.read_text(encoding="utf-8"))

    def write_cached(self, stock_id: str, payload: dict[str, Any]) -> Path:
        path = self.cache_path(stock_id)
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self.load_cached.cache_clear()
        return path

    def clear_cache(self) -> None:
        self.load_cached.cache_clear()

    def _safe_stock_id(self, stock_id: str) -> str:
        safe_id = str(stock_id).strip()
        if not re.fullmatch(r"[0-9A-Za-z._-]{1,20}", safe_id):
            raise ValueError(f"非法股票代號：{stock_id}")
        return safe_id
