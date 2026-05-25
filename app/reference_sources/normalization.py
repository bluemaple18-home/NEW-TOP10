"""概念股標籤標準化。

這裡先用可追溯的 deterministic rules；未來若接 AI 判斷，應只輸出候選
decision/confidence，不直接覆蓋 raw source label。
"""

from __future__ import annotations

import re
import unicodedata


ALIASES: dict[str, tuple[str, str, str | None]] = {
    "ai": ("ai", "人工智慧 AI", "digital_cloud"),
    "ai人工智慧": ("ai", "人工智慧 AI", "digital_cloud"),
    "人工智慧": ("ai", "人工智慧 AI", "digital_cloud"),
    "人工智慧ai": ("ai", "人工智慧 AI", "digital_cloud"),
    "ai伺服器": ("ai_server", "AI 伺服器", "ai"),
    "生成式ai": ("generative_ai", "生成式 AI", "ai"),
    "hpc": ("hpc", "高效能運算 HPC", "digital_cloud"),
    "大數據": ("big_data", "大數據", "digital_cloud"),
    "雲端產業": ("cloud", "雲端產業", "digital_cloud"),
    "雲端運算": ("cloud", "雲端產業", "digital_cloud"),
    "半導體": ("semiconductor", "半導體", "technology"),
    "半導體設備": ("semiconductor_equipment", "半導體設備", "semiconductor"),
    "先進封裝": ("advanced_packaging", "先進封裝", "semiconductor"),
    "矽智財ip": ("silicon_ip", "矽智財 IP", "semiconductor"),
    "ic設計": ("ic_design", "IC 設計", "semiconductor"),
    "台積電": ("tsmc_supply_chain", "台積電供應鏈", "semiconductor"),
    "tesla": ("tesla", "Tesla 特斯拉", "ev"),
    "特斯拉": ("tesla", "Tesla 特斯拉", "ev"),
    "電動車": ("ev", "電動車", "mobility"),
    "油電車": ("ev", "電動車", "mobility"),
    "電動車油電車": ("ev", "電動車", "mobility"),
    "機器人": ("robotics_general", "機器人", "automation"),
    "智慧型機器人": ("intelligent_robotics", "智慧型機器人", "automation"),
    "機器人智慧機械": ("robotics_smart_machinery", "機器人 / 智慧機械", "automation"),
    "特斯拉人形機器人": ("tesla_humanoid_robotics", "特斯拉人形機器人", "robotics_general"),
    "智慧機械": ("smart_machinery", "智慧機械", "automation"),
    "工業4.0": ("industry_4_0", "工業 4.0", "automation"),
    "低軌衛星": ("leo_satellite", "低軌衛星", "communications"),
    "衛星低軌衛星": ("leo_satellite", "低軌衛星", "communications"),
    "風力發電離岸風電": ("offshore_wind", "風力發電 / 離岸風電", "green_energy"),
    "離岸風電": ("offshore_wind", "風力發電 / 離岸風電", "green_energy"),
    "綠能": ("green_energy", "綠能環保", None),
    "環保綠能": ("green_energy", "綠能環保", None),
    "儲能": ("energy_storage", "儲能", "green_energy"),
    "儲能系統": ("energy_storage", "儲能", "green_energy"),
    "太陽能": ("solar", "太陽能", "green_energy"),
}


PARENT_CONCEPTS: dict[str, tuple[str, str | None]] = {
    "technology": ("科技", None),
    "digital_cloud": ("數位雲端", "technology"),
    "semiconductor": ("半導體", "technology"),
    "mobility": ("智慧移動", None),
    "automation": ("自動化", "technology"),
    "communications": ("通信網路", "technology"),
    "green_energy": ("綠能環保", None),
}


def normalize_label(raw_name: str) -> str:
    text = unicodedata.normalize("NFKC", str(raw_name or "")).strip().lower()
    text = text.replace("＋", "+").replace("／", "/")
    text = re.sub(r"\s+", "", text)
    text = re.sub(r"[()（）\-_/、+&|·．.]", "", text)
    return text


def canonicalize(raw_name: str, merge_aliases: bool = True) -> tuple[str, str, str | None, str, float]:
    normalized = normalize_label(raw_name)
    if merge_aliases and normalized in ALIASES:
        concept_id, canonical_name, parent_id = ALIASES[normalized]
        return concept_id, canonical_name, parent_id, "alias", 0.95

    concept_id = slugify(normalized or raw_name)
    canonical_name = str(raw_name).strip() or concept_id
    method = "alias" if normalized in ALIASES else "normalized_text"
    confidence = 0.9 if normalized in ALIASES else 0.65
    return concept_id, canonical_name, None, method, confidence


def slugify(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or "")).strip().lower()
    text = re.sub(r"[^0-9a-zA-Z\u4e00-\u9fff]+", "_", text)
    text = text.strip("_")
    if not text:
        return "unknown"
    if re.search(r"[\u4e00-\u9fff]", text):
        return "concept_" + str(abs(hash(text)) % 10_000_000)
    return text
