"""由本地 concept industry membership 產生正式 stock_industry_map。

資料來源只使用 `data/reference/stock_concept_membership.csv` 與
`data/reference/tradable_universe.csv`，不在執行時抓外部資料。
"""

from __future__ import annotations

from datetime import date, datetime, timezone
import json
from pathlib import Path
import re
import sys

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


OUTPUT_COLUMNS = [
    "stock_id",
    "industry_code",
    "industry_name",
    "sector_name",
    "market_type",
    "theme_tags",
    "source",
    "updated_at",
]

SECTOR_BY_KEYWORD = {
    "半導體": "科技",
    "IC": "科技",
    "電子": "科技",
    "機殼": "科技",
    "光電": "科技",
    "電腦": "科技",
    "通訊": "科技",
    "資訊": "科技",
    "網通": "科技",
    "設備": "科技",
    "廠務": "科技",
    "電池": "科技",
    "電源": "科技",
    "電子連接": "科技",
    "PCB": "科技",
    "LED": "科技",
    "軟體": "科技",
    "系統整合": "科技",
    "金融": "金融",
    "生技": "醫療保健",
    "醫療": "醫療保健",
    "食品": "民生消費",
    "觀光": "民生消費",
    "餐旅": "民生消費",
    "貿易百貨": "民生消費",
    "居家生活": "民生消費",
    "運動休閒": "民生消費",
    "紡織": "民生消費",
    "汽車": "民生消費",
    "橡膠": "民生消費",
    "水泥": "原物料",
    "塑膠": "原物料",
    "化學": "原物料",
    "鋼鐵": "原物料",
    "玻璃": "原物料",
    "造紙": "原物料",
    "油電燃氣": "公用事業",
    "綠能環保": "公用事業",
    "電機": "工業",
    "電器電纜": "工業",
    "航運": "工業",
    "營建": "不動產",
}


def main() -> int:
    reference_dir = PROJECT_ROOT / "data" / "reference"
    universe_path = reference_dir / "tradable_universe.csv"
    concept_path = reference_dir / "stock_concept_membership.csv"
    output_path = reference_dir / "stock_industry_map.csv"
    summary_path = PROJECT_ROOT / "artifacts" / "stock_industry_map_build_summary.json"

    universe = pd.read_csv(universe_path, dtype=str).fillna("")
    concepts = pd.read_csv(concept_path, dtype=str).fillna("")
    active = universe[(universe["is_active"].str.lower() == "true") & (universe["is_etf"].str.lower() != "true")].copy()
    active["stock_id"] = active["stock_id"].astype(str).str.strip()

    industry_concepts = concepts[concepts["concept_type"].eq("industry")].copy()
    industry_concepts["stock_id"] = industry_concepts["stock_id"].astype(str).str.strip()
    industry_concepts = industry_concepts[industry_concepts["stock_id"].isin(set(active["stock_id"]))]
    if industry_concepts.empty:
        raise ValueError("找不到可用的 concept_type=industry membership")

    preferred = (
        industry_concepts.assign(priority=industry_concepts["raw_concept_name"].map(_priority))
        .sort_values(["stock_id", "priority", "confidence"], ascending=[True, False, False])
        .drop_duplicates("stock_id", keep="first")
    )
    rows = []
    universe_by_stock = active.set_index("stock_id").to_dict(orient="index")
    for _, row in preferred.iterrows():
        stock_id = str(row["stock_id"]).strip()
        industry_name = _normalize_industry_name(row["raw_concept_name"] or row["canonical_name"])
        parent_name = _parent_name(row["raw_concept_name"] or row["canonical_name"])
        rows.append(
            {
                "stock_id": stock_id,
                "industry_code": str(row["canonical_concept_id"]).strip(),
                "industry_name": industry_name,
                "sector_name": _sector_name(industry_name),
                "market_type": universe_by_stock.get(stock_id, {}).get("market_type", ""),
                "theme_tags": _theme_tags(industry_name, parent_name),
                "source": f"concept_industry_{str(row['source']).strip() or 'local'}",
                "updated_at": date.today().isoformat(),
            }
        )

    result = pd.DataFrame(rows, columns=OUTPUT_COLUMNS).sort_values("stock_id")
    missing_stocks = sorted(set(active["stock_id"]) - set(result["stock_id"]))
    result.to_csv(output_path, index=False)

    summary = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "output": str(output_path),
        "active_stock_count": int(len(active)),
        "industry_map_rows": int(len(result)),
        "coverage": round(float(len(result) / len(active)), 6) if len(active) else 0,
        "missing_stock_count": len(missing_stocks),
        "missing_stock_sample": missing_stocks[:20],
        "industry_count": int(result["industry_name"].nunique()),
        "sector_count": int(result["sector_name"].nunique()),
        "source_counts": result["source"].value_counts().to_dict(),
    }
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"STOCK_INDUSTRY_MAP_BUILD_OK rows={len(result)} coverage={summary['coverage']:.2%} summary={summary_path}")
    return 0


def _priority(raw_name: str) -> int:
    text = str(raw_name)
    if text.startswith("電子產業 /"):
        return 30
    if text.startswith("上市類股 /") or text.startswith("上櫃類股 /"):
        return 20
    return 10


def _normalize_industry_name(raw_name: str) -> str:
    text = str(raw_name).strip()
    if "/" in text:
        text = text.split("/")[-1].strip()
    text = re.sub(r"^櫃", "", text)
    return text or "未分類"


def _parent_name(raw_name: str) -> str:
    text = str(raw_name).strip()
    if "/" not in text:
        return ""
    return text.split("/", 1)[0].strip()


def _sector_name(industry_name: str) -> str:
    for keyword, sector in SECTOR_BY_KEYWORD.items():
        if keyword in industry_name:
            return sector
    return "其他"


def _theme_tags(industry_name: str, parent_name: str) -> str:
    tags = [industry_name]
    if parent_name:
        tags.append(parent_name)
    return "|".join(dict.fromkeys(tag for tag in tags if tag))


if __name__ == "__main__":
    raise SystemExit(main())
