"""期交所單日歷史資料：CSV 優先，HTML 僅作下載不可用時的備援。"""

from __future__ import annotations

import csv
import io
import re
from datetime import datetime
from typing import Any

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://www.taifex.com.tw/cht/3/"
CSV_FIELDS = {
    "futures": {
        "交易日期": "Date", "契約": "Contract", "到期月份(週別)": "ContractMonth(Week)",
        "收盤價": "Last", "漲跌價": "Change", "漲跌%": "%", "成交量": "Volume",
        "交易時段": "TradingSession",
    },
    "oi": {
        "日期": "Date", "商品名稱": "ContractCode", "身份別": "Item",
        "多空未平倉口數淨額": "OpenInterest(Net)",
    },
}


def is_csv_response(headers: Any) -> bool:
    """先判斷標頭才解碼；官方 CSV 實測誤標 text/html，但附 MS950 與 CSV 附件。"""
    content_type = headers.get("Content-Type", "").lower()
    mime = content_type.split(";", 1)[0].strip()
    if mime in {"text/csv", "application/csv"}:
        return True
    attachment = headers.get("Content-Disposition", "").lower()
    return (
        mime == "text/html"
        and re.search(r"charset\s*=\s*[\"']?(?:ms950|big5)\b", content_type) is not None
        and attachment.startswith("attachment;")
        and re.search(r'filename\s*=\s*"?[^;"\r\n]+\.csv(?:"|;|$)', attachment) is not None
    )


def parse_csv(content: bytes, section: str, trade_date: str) -> list[dict[str, str]]:
    """確認為 CSV 才可呼叫；Big5 或欄位損壞必須明確失敗，不轉為無資料。"""
    text = content.decode("big5", errors="strict")
    reader = csv.DictReader(io.StringIO(text))
    mapping = CSV_FIELDS[section]
    if not set(mapping).issubset(reader.fieldnames or []):
        raise ValueError(f"TAIFEX historical {section} CSV 必要欄位缺漏")
    result = []
    for row in reader:
        normalized = {target: (row.get(key) or "").strip() for key, target in mapping.items()}
        normalized["Date"] = datetime.strptime(normalized["Date"], "%Y/%m/%d").strftime("%Y-%m-%d")
        if normalized["Date"] == trade_date:
            result.append(normalized)
    return result


def parse_html(content: bytes, section: str, trade_date: str) -> list[dict[str, str]]:
    """只認報表日期，不以表單輸入日期冒充資料日期；不猜測不同版型。"""
    soup = BeautifulSoup(content.decode("utf-8", errors="strict"), "html.parser")
    if section == "futures":
        report = soup.select_one("#printhere")
        if report is None or "一般交易時段行情表" not in report.get_text():
            return []
        date_node = report.select_one("p")
    else:
        report = soup
        date_node = next((x for x in soup.select("span.right") if "日期" in x.get_text()), None)
    match = re.search(r"日期\s*[：:]?\s*(\d{4}/\d{1,2}/\d{1,2})", date_node.get_text() if date_node else "")
    if match is None or datetime.strptime(match[1], "%Y/%m/%d").strftime("%Y-%m-%d") != trade_date:
        return []
    for table in report.select("table"):
        rows = table.find_all("tr")
        result = []
        if section == "futures":
            headers = [re.sub(r"\s+", "", x.get_text()) for x in rows[0].find_all("th")] if rows else []
            required = {"契約", "到期月份(週別)", "最後成交價", "漲跌價", "漲跌%", "*一般交易時段成交量"}
            if not required.issubset(headers):
                continue
            for tr in rows[1:]:
                cells = [re.sub(r"[▲▼\s]", "", x.get_text()) for x in tr.find_all("td", recursive=False)]
                if not cells or cells[0] != "TX":
                    continue
                if len(cells) != len(headers):
                    raise ValueError("TAIFEX historical futures HTML 欄數不符")
                row = dict(zip(headers, cells))
                result.append({"Date": trade_date, "Contract": "TX", "TradingSession": "一般",
                               "ContractMonth(Week)": row["到期月份(週別)"], "Last": row["最後成交價"],
                               "Change": row["漲跌價"], "%": row["漲跌%"], "Volume": row["*一般交易時段成交量"]})
        else:
            # 官方表格依商品合併前兩格；最後兩格是未平倉多空淨額（口數／金額）。
            headings = [[re.sub(r"\s+", "", x.get_text()) for x in tr.find_all("th")] for tr in rows[:3]]
            if headings != [["", "交易口數與契約金額", "未平倉餘額"],
                            ["多方", "空方", "多空淨額", "多方", "空方", "多空淨額"],
                            ["序號", "商品名稱", "身份別"] + ["口數", "契約金額"] * 6]:
                continue
            product = None
            remaining = 0
            for tr in rows[3:]:
                cells = [x.get_text(strip=True) for x in tr.find_all("td", recursive=False)]
                if len(cells) == 15:
                    product, remaining = cells[1], 3
                    cells = cells[2:]
                if product != "臺股期貨" or remaining <= 0:
                    continue
                if len(cells) != 13:
                    raise ValueError("TAIFEX historical OI HTML 欄數不符")
                remaining -= 1
                result.append({"Date": trade_date, "ContractCode": product,
                               "Item": "外資及陸資" if cells[0] == "外資" else cells[0],
                               "OpenInterest(Net)": cells[-2]})
        if result:
            return result
    return []


def fetch_historical(section: str, trade_date: str, *, headers: dict[str, str]) -> tuple[list[dict[str, str]], dict[str, Any]]:
    """每次每入口最多一個請求；不跟隨轉址、不以鄰日代替目標日。"""
    date = datetime.strptime(trade_date, "%Y-%m-%d").strftime("%Y/%m/%d")
    endpoint = "futDataDown" if section == "futures" else "futContractsDateDown"
    params = {"queryStartDate": date, "queryEndDate": date}
    params.update({"down_type": "1", "commodity_id": "TX", "commodity_id2": ""} if section == "futures" else {"commodityId": ""})
    response = requests.post(BASE_URL + endpoint, data=params, headers=headers, timeout=20, allow_redirects=False)
    info = {"source": "taifex_historical", "data_date": None, "status": "unavailable_historical",
            "fallback_used": False, "csv_endpoint": endpoint, "content_type": response.headers.get("Content-Type", ""),
            "http_status": response.status_code, "csv_confirmed": is_csv_response(response.headers)}
    if info["csv_confirmed"]:
        response.raise_for_status()
        rows = parse_csv(response.content, section, trade_date) if response.status_code == 200 else []
        info["format"] = "csv_big5"
    else:
        # 非 CSV 絕不進 Big5 解碼；HTML 無目標日報表時保留可辨識 unavailable。
        endpoint = "futDailyMarketReport" if section == "futures" else "futContractsDate"
        params = {"queryDate": date}
        params.update({"queryType": "2", "marketCode": "0", "commodity_id": "TX", "commodity_id2": ""} if section == "futures" else {"queryType": "1", "commodityId": ""})
        response = requests.post(BASE_URL + endpoint, data=params, headers=headers, timeout=20, allow_redirects=False)
        info.update(fallback_used=True, html_endpoint=endpoint, html_http_status=response.status_code,
                    html_content_type=response.headers.get("Content-Type", ""), format="html")
        if response.status_code == 200 and "text/html" in response.headers.get("Content-Type", "").lower():
            try:
                rows = parse_html(response.content, section, trade_date)
            except UnicodeDecodeError:
                rows = []
                info["reason_code"] = "html_encoding_unavailable"
        else:
            rows = []
    if rows:
        info.update(status="ok", data_date=trade_date)
    return rows, info
