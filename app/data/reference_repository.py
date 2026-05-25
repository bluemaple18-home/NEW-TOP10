"""本地產業與 ETF reference repository。

這層只讀 `data/reference`，不在 API request path 抓外部資料。
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
import re
from typing import Any

import pandas as pd

from app.contracts.reference import (
    StockConceptMembership,
    StockEtfExposure,
    StockIndustryClassification,
    StockReferenceResponse,
    TradableUniverseItem,
    TradableUniverseResponse,
)


STOCK_ID_PATTERN = re.compile(r"[0-9A-Za-z._-]{1,20}")
TRADABLE_STOCK_ID_PATTERN = re.compile(r"\d{4}")
MARKET_TYPES = {"twse", "tpex"}

PREFIX_INDUSTRIES = {
    "11": ("11", "水泥工業", "原物料"),
    "12": ("12", "食品工業", "民生消費"),
    "13": ("13", "塑膠工業", "原物料"),
    "14": ("14", "紡織纖維", "民生消費"),
    "15": ("15", "電機機械", "工業"),
    "16": ("16", "電器電纜", "工業"),
    "17": ("17", "化學生技醫療", "原物料"),
    "18": ("18", "玻璃陶瓷", "原物料"),
    "19": ("19", "造紙工業", "原物料"),
    "20": ("20", "鋼鐵工業", "原物料"),
    "21": ("21", "橡膠工業", "民生消費"),
    "22": ("22", "汽車工業", "民生消費"),
    "23": ("23", "電子工業", "科技"),
    "24": ("24", "電子工業", "科技"),
    "25": ("25", "建材營造", "不動產"),
    "26": ("26", "航運業", "工業"),
    "27": ("27", "觀光餐旅", "民生消費"),
    "28": ("28", "金融保險", "金融"),
    "29": ("29", "貿易百貨", "民生消費"),
    "30": ("30", "電子工業", "科技"),
}


class ReferenceRepository:
    def __init__(self, project_root: Path):
        self.project_root = project_root
        self.reference_dir = project_root / "data" / "reference"
        self.industry_path = self.reference_dir / "stock_industry_map.csv"
        self.etf_path = self.reference_dir / "stock_etf_exposure.csv"
        self.concept_path = self.reference_dir / "stock_concept_membership.csv"
        self.tradable_universe_path = self.reference_dir / "tradable_universe.csv"

    @lru_cache(maxsize=1)
    def load_tradable_universe(self) -> pd.DataFrame:
        if not self.tradable_universe_path.exists():
            return pd.DataFrame()
        df = pd.read_csv(self.tradable_universe_path, dtype={"stock_id": str})
        if df.empty:
            return df
        df["stock_id"] = df["stock_id"].astype(str).str.strip()
        if "is_etf" in df.columns:
            df["is_etf"] = df["is_etf"].map(self._bool_value).fillna(False)
        if "is_active" in df.columns:
            df["is_active"] = df["is_active"].map(self._bool_value).fillna(True)
        return df.drop_duplicates(subset=["stock_id"], keep="last")

    def tradable_universe(self, active_only: bool = True, include_etfs: bool = False) -> TradableUniverseResponse:
        df = self.load_tradable_universe()
        if df.empty:
            return TradableUniverseResponse(
                available=False,
                notes="本地 tradable_universe.csv 尚未建立；請先執行離線 universe 匯入流程。",
            )
        filtered = df.copy()
        if active_only and "is_active" in filtered.columns:
            filtered = filtered[filtered["is_active"]]
        if not include_etfs and "is_etf" in filtered.columns:
            filtered = filtered[~filtered["is_etf"]]
        items = [self._tradable_item_from_row(row) for _, row in filtered.iterrows()]
        return TradableUniverseResponse(available=bool(items), items=items)

    def tradable_universe_item(self, stock_id: str) -> TradableUniverseItem | None:
        target = self._safe_stock_id(stock_id)
        df = self.load_tradable_universe()
        if df.empty:
            return None
        match = df[df["stock_id"] == target]
        if match.empty:
            return None
        return self._tradable_item_from_row(match.iloc[-1])

    @lru_cache(maxsize=1)
    def load_industry_map(self) -> pd.DataFrame:
        if not self.industry_path.exists():
            return pd.DataFrame()
        df = pd.read_csv(self.industry_path, dtype={"stock_id": str, "industry_code": str})
        if df.empty:
            return df
        df["stock_id"] = df["stock_id"].astype(str).str.strip()
        return df.drop_duplicates(subset=["stock_id"], keep="last")

    @lru_cache(maxsize=1)
    def load_etf_exposure(self) -> pd.DataFrame:
        if not self.etf_path.exists():
            return pd.DataFrame()
        df = pd.read_csv(self.etf_path, dtype={"stock_id": str, "etf_id": str})
        if df.empty:
            return df
        df["stock_id"] = df["stock_id"].astype(str).str.strip()
        df["etf_id"] = df["etf_id"].astype(str).str.strip()
        if "weight" in df.columns:
            df["weight"] = pd.to_numeric(df["weight"], errors="coerce")
        if "is_major_holding" in df.columns:
            df["is_major_holding"] = df["is_major_holding"].map(self._bool_value).fillna(False)
        return df.drop_duplicates(subset=["stock_id", "etf_id"], keep="last")

    @lru_cache(maxsize=1)
    def load_concept_membership(self) -> pd.DataFrame:
        if not self.concept_path.exists():
            return pd.DataFrame()
        df = pd.read_csv(self.concept_path, dtype={"stock_id": str, "canonical_concept_id": str})
        if df.empty:
            return df
        df["stock_id"] = df["stock_id"].astype(str).str.strip()
        if "confidence" in df.columns:
            df["confidence"] = pd.to_numeric(df["confidence"], errors="coerce")
        return df.drop_duplicates(subset=["stock_id", "canonical_concept_id", "source"], keep="last")

    def stock_reference(self, stock_id: str) -> StockReferenceResponse:
        target = self._safe_stock_id(stock_id)
        industry = self.stock_industry(target)
        etfs = self.stock_etfs(target)
        concepts = self.stock_concepts(target)
        available = industry.available or bool(etfs) or bool(concepts)
        return StockReferenceResponse(
            available=available,
            stock_id=target,
            industry=industry,
            etfs=etfs,
            concepts=concepts,
            notes=None if available else "本地 reference mapping 尚無此股票的產業或 ETF 資料。",
        )

    def stock_industry(self, stock_id: str) -> StockIndustryClassification:
        target = self._safe_stock_id(stock_id)
        df = self.load_industry_map()
        if not df.empty:
            match = df[df["stock_id"] == target]
            if not match.empty:
                row = match.iloc[-1]
                return StockIndustryClassification(
                    stock_id=target,
                    available=True,
                    industry_code=self._str_or_none(row.get("industry_code")),
                    industry_name=self._str_or_none(row.get("industry_name")),
                    sector_name=self._str_or_none(row.get("sector_name")),
                    market_type=self._str_or_none(row.get("market_type")),
                    theme_tags=self._parse_tags(row.get("theme_tags")),
                    source=self._str_or_none(row.get("source")),
                    updated_at=self._str_or_none(row.get("updated_at")),
                )

        fallback = self._prefix_industry(target)
        if fallback is not None:
            industry_code, industry_name, sector_name = fallback
            return StockIndustryClassification(
                stock_id=target,
                available=True,
                industry_code=industry_code,
                industry_name=industry_name,
                sector_name=sector_name,
                market_type="stock",
                theme_tags=[],
                source="code_prefix_fallback",
                notes="由股票代號前綴推估；建議用完整 reference mapping 覆蓋。",
            )

        return StockIndustryClassification(
            stock_id=target,
            available=False,
            notes="本地 reference mapping 尚無此股票的產業分類。",
        )

    def stock_etfs(self, stock_id: str) -> list[StockEtfExposure]:
        target = self._safe_stock_id(stock_id)
        df = self.load_etf_exposure()
        if df.empty:
            return []
        matches = df[df["stock_id"] == target].copy()
        if matches.empty:
            return []
        matches = matches.sort_values(["is_major_holding", "weight"], ascending=[False, False], na_position="last")
        return [self._etf_from_row(target, row) for _, row in matches.iterrows()]

    def stock_concepts(self, stock_id: str, limit: int = 30) -> list[StockConceptMembership]:
        target = self._safe_stock_id(stock_id)
        df = self.load_concept_membership()
        if df.empty:
            return []
        matches = df[df["stock_id"] == target].copy()
        if matches.empty:
            return []
        if "confidence" in matches.columns:
            matches = matches.sort_values("confidence", ascending=False, na_position="last")
        return [self._concept_from_row(target, row) for _, row in matches.head(limit).iterrows()]

    def annotate_ranking(self, ranking: pd.DataFrame) -> pd.DataFrame:
        if ranking.empty or "stock_id" not in ranking.columns:
            return ranking
        result = ranking.copy()
        industries = [self.stock_industry(stock_id) for stock_id in result["stock_id"].astype(str)]
        result["industry_code"] = [item.industry_code for item in industries]
        result["industry_name"] = [item.industry_name for item in industries]
        result["sector_name"] = [item.sector_name for item in industries]
        result["market_type"] = [item.market_type for item in industries]
        result["theme_tags"] = ["|".join(item.theme_tags) for item in industries]
        result["major_etfs"] = [
            "|".join(etf.etf_id for etf in self.stock_etfs(stock_id) if etf.is_major_holding)
            for stock_id in result["stock_id"].astype(str)
        ]
        result["concept_tags"] = [
            "|".join(concept.canonical_name for concept in self.stock_concepts(stock_id, limit=8))
            for stock_id in result["stock_id"].astype(str)
        ]
        return result

    def clear_cache(self) -> None:
        self.load_tradable_universe.cache_clear()
        self.load_industry_map.cache_clear()
        self.load_etf_exposure.cache_clear()
        self.load_concept_membership.cache_clear()

    def _tradable_item_from_row(self, row: pd.Series) -> TradableUniverseItem:
        return TradableUniverseItem(
            stock_id=str(row.get("stock_id")).strip(),
            stock_name=self._str_or_none(row.get("stock_name")) or str(row.get("stock_id")).strip(),
            market_type=self._str_or_none(row.get("market_type")) or "twse",
            is_etf=bool(row.get("is_etf", False)),
            is_active=bool(row.get("is_active", True)),
            source=self._str_or_none(row.get("source")),
            updated_at=self._str_or_none(row.get("updated_at")),
        )

    def _etf_from_row(self, stock_id: str, row: pd.Series) -> StockEtfExposure:
        return StockEtfExposure(
            stock_id=stock_id,
            etf_id=str(row.get("etf_id")).strip(),
            etf_name=self._str_or_none(row.get("etf_name")),
            weight=self._float_or_none(row.get("weight")),
            is_major_holding=bool(row.get("is_major_holding", False)),
            source=self._str_or_none(row.get("source")),
            updated_at=self._str_or_none(row.get("updated_at")),
        )

    def _concept_from_row(self, stock_id: str, row: pd.Series) -> StockConceptMembership:
        return StockConceptMembership(
            stock_id=stock_id,
            canonical_concept_id=self._str_or_none(row.get("canonical_concept_id")) or "unknown",
            canonical_name=self._str_or_none(row.get("canonical_name")) or "未分類概念",
            raw_concept_name=self._str_or_none(row.get("raw_concept_name")) or "未分類概念",
            concept_type=self._str_or_none(row.get("concept_type")) or "theme",
            source=self._str_or_none(row.get("source")),
            source_url=self._str_or_none(row.get("source_url")),
            observed_at=self._str_or_none(row.get("observed_at")),
            confidence=self._float_or_none(row.get("confidence")),
            match_method=self._str_or_none(row.get("match_method")),
        )

    def _safe_stock_id(self, stock_id: str) -> str:
        target = str(stock_id).strip()
        if not STOCK_ID_PATTERN.fullmatch(target):
            raise ValueError(f"非法股票代號：{stock_id}")
        return target

    def _prefix_industry(self, stock_id: str) -> tuple[str, str, str] | None:
        if len(stock_id) < 2 or not stock_id[:2].isdigit():
            return None
        return PREFIX_INDUSTRIES.get(stock_id[:2])

    def _parse_tags(self, value: Any) -> list[str]:
        text = self._str_or_none(value)
        if text is None:
            return []
        return [tag.strip() for tag in re.split(r"[|,]", text) if tag.strip()]

    def _str_or_none(self, value: Any) -> str | None:
        if value is None or pd.isna(value):
            return None
        text = str(value).strip()
        return text or None

    def _float_or_none(self, value: Any) -> float | None:
        if value is None or pd.isna(value):
            return None
        return float(value)

    def _bool_value(self, value: Any) -> bool:
        if value is None or pd.isna(value):
            return False
        if isinstance(value, bool):
            return value
        return str(value).strip().lower() in {"1", "true", "yes", "y"}
