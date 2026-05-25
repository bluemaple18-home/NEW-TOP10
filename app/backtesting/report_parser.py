"""回測報告摘要解析。

解析既有 markdown artifact 的可讀績效欄位；格式不一致時回傳 None，
避免只讀 summary 因舊報告或人工編輯報告中斷。
"""

from __future__ import annotations

import math
import re
from pathlib import Path
from typing import Any


def parse_backtest_report_metrics(text: str, report_path: Path) -> dict[str, Any]:
    """從 markdown 回測報告解析可選績效欄位。"""

    return {
        "period": _extract_period(text),
        "threshold": _extract_threshold(text, report_path),
        "trades": _extract_trades(text),
        "win_rate": _extract_percent_metric(text, ("平均勝率", "勝率")),
        "avg_return": _extract_percent_metric(
            text,
            ("平均每次選股報酬", "平均每次報酬", "平均報酬"),
        ),
    }


def _extract_period(text: str) -> str | None:
    for line in text.splitlines():
        key, value = _split_markdown_key_value(line)
        if key and "回測期間" in key:
            return value or None
    return None


def _extract_threshold(text: str, report_path: Path) -> float | None:
    for line in text.splitlines():
        key, value = _split_markdown_key_value(line)
        if key and ("機率門檻" in key or "threshold" in key.lower()):
            return _parse_number(value)

        title_match = re.search(
            r"threshold\s*=\s*([-+]?\d+(?:\.\d+)?)",
            line,
            flags=re.IGNORECASE,
        )
        if title_match:
            return _parse_number(title_match.group(1))

    filename_match = re.search(
        r"backtest_report_([-+]?\d+(?:\.\d+)?)$",
        report_path.stem,
    )
    if filename_match:
        return _parse_number(filename_match.group(1))
    return None


def _extract_trades(text: str) -> int | None:
    for line in text.splitlines():
        key, value = _split_markdown_key_value(line)
        if key and ("總交易筆數" in key or "總交易場次" in key or "trades" in key.lower()):
            parsed = _parse_number(value)
            return int(parsed) if parsed is not None else None
    return None


def _extract_percent_metric(text: str, labels: tuple[str, ...]) -> float | None:
    for line in text.splitlines():
        key, value = _split_markdown_key_value(line)
        if key and any(label in key for label in labels):
            return _parse_number(value)
    return None


def _split_markdown_key_value(line: str) -> tuple[str | None, str]:
    cleaned = _clean_markdown(line)
    if ":" in cleaned:
        key, value = cleaned.split(":", 1)
    elif "：" in cleaned:
        key, value = cleaned.split("：", 1)
    else:
        return None, cleaned.strip()
    return key.strip(), value.strip()


def _clean_markdown(value: str) -> str:
    return value.strip().lstrip("-").replace("**", "").replace("`", "").strip()


def _parse_number(value: str) -> float | None:
    lowered = value.strip().lower()
    if "nan" in lowered or lowered in {"", "none", "null", "n/a", "na"}:
        return None

    match = re.search(r"[-+]?\d+(?:,\d{3})*(?:\.\d+)?", value)
    if not match:
        return None

    try:
        parsed = float(match.group(0).replace(",", ""))
    except ValueError:
        return None

    if math.isnan(parsed) or math.isinf(parsed):
        return None
    return parsed
