"""外部概念股/產業 reference collectors。

Collectors are intentionally conservative:
- keep raw HTML snapshots for audit;
- parse only stock ids that are visible in fetched pages;
- return failed source status instead of raising for a whole run.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import re
import time
from typing import Any
from urllib.parse import quote, unquote, urljoin, urlparse, parse_qs

import requests
from bs4 import BeautifulSoup

from app.reference_sources.normalization import canonicalize


SUFFIXED_STOCK_ID_RE = re.compile(r"(?<![A-Za-z0-9])([0-9]{4,6})\.(?:TW|TWO)(?![A-Za-z0-9])", re.IGNORECASE)
TEXT_STOCK_NAME_RE = re.compile(
    r"(?<![0-9])([1-9][0-9]{3}|00[5-9][0-9]|00[0-9]{3,4})(?:\s|\u3000)+"
    r"(?!(?:年|月|日|點|億|萬|家|種|檔|間|美元|請登入|財報狗))"
    r"[\u4e00-\u9fffA-Za-z]"
)


class SourceBlockedError(RuntimeError):
    """來源站台暫時拒絕請求，不能把回應寫成有效 raw snapshot。"""


class NonJsonResponseError(RuntimeError):
    """API 回傳不是 JSON，通常代表被擋或前端 endpoint 變更。"""


@dataclass
class ConceptMembership:
    stock_id: str
    raw_concept_name: str
    concept_type: str
    source: str
    source_url: str
    observed_at: str
    canonical_concept_id: str
    canonical_name: str
    parent_concept_id: str | None
    confidence: float
    match_method: str


@dataclass
class CollectorResult:
    source: str
    status: str
    fetched_pages: int = 0
    row_count: int = 0
    memberships: list[ConceptMembership] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class HttpClient:
    def __init__(
        self,
        project_root: Path,
        timeout: int = 20,
        sleep_seconds: float = 0.5,
        retry_count: int = 1,
        retry_sleep_seconds: float = 3.0,
    ):
        self.project_root = project_root
        self.timeout = timeout
        self.sleep_seconds = sleep_seconds
        self.retry_count = retry_count
        self.retry_sleep_seconds = retry_sleep_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
                ),
                "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
            }
        )

    def fetch(self, source: str, url: str, raw_dir: Path | None = None) -> tuple[str, str | None, int]:
        response = self._get(url)
        self._raise_if_blocked(response, url)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        text = response.text
        raw_path = None
        if raw_dir is not None:
            raw_path = self._write_raw(source=source, url=url, html=text, raw_dir=raw_dir)
        if self.sleep_seconds > 0:
            time.sleep(self.sleep_seconds)
        return text, raw_path, response.status_code

    def fetch_json(self, source: str, url: str, raw_dir: Path | None = None) -> tuple[dict[str, Any], str | None, int]:
        response = self._get(url)
        self._raise_if_blocked(response, url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        if "json" not in content_type.lower():
            raise NonJsonResponseError(f"non-json response status={response.status_code} content_type={content_type} url={url}")
        payload = response.json()
        raw_path = None
        if raw_dir is not None:
            raw_path = self._write_raw(
                source=source,
                url=url,
                html=json.dumps(payload, ensure_ascii=False, indent=2),
                raw_dir=raw_dir,
            )
        if self.sleep_seconds > 0:
            time.sleep(self.sleep_seconds)
        return payload, raw_path, response.status_code

    def post(self, source: str, url: str, data: dict[str, str], raw_dir: Path | None = None) -> tuple[str, str | None, int]:
        response = self.session.post(url, data=data, timeout=self.timeout)
        self._raise_if_blocked(response, url)
        response.raise_for_status()
        response.encoding = response.apparent_encoding or response.encoding
        text = response.text
        raw_path = None
        if raw_dir is not None:
            raw_path = self._write_raw(source=source, url=url, html=text, raw_dir=raw_dir)
        if self.sleep_seconds > 0:
            time.sleep(self.sleep_seconds)
        return text, raw_path, response.status_code

    def _write_raw(self, source: str, url: str, html: str, raw_dir: Path) -> str:
        source_dir = raw_dir / source
        source_dir.mkdir(parents=True, exist_ok=True)
        digest = hashlib.sha1(url.encode("utf-8")).hexdigest()[:12]
        path = source_dir / f"{digest}.html"
        path.write_text(html, encoding="utf-8")
        return str(path)

    def _get(self, url: str) -> requests.Response:
        last_response: requests.Response | None = None
        for attempt in range(self.retry_count + 1):
            response = self.session.get(url, timeout=self.timeout)
            last_response = response
            if not self._is_blocked_response(response):
                return response
            if attempt < self.retry_count:
                time.sleep(self.retry_sleep_seconds * (attempt + 1))
        assert last_response is not None
        return last_response

    def _raise_if_blocked(self, response: requests.Response, url: str) -> None:
        if self._is_blocked_response(response):
            snippet = response.text[:80].replace("\n", " ")
            raise SourceBlockedError(f"blocked status={response.status_code} snippet={snippet!r} url={url}")

    @staticmethod
    def _is_blocked_response(response: requests.Response) -> bool:
        text = response.text[:200].lower()
        return response.status_code == 999 or "request denied" in text


class BaseCollector:
    source = "base"
    concept_type = "theme"

    def __init__(self, client: HttpClient, config: dict[str, Any], raw_dir: Path | None = None):
        self.client = client
        self.config = config
        self.raw_dir = raw_dir
        self.merge_aliases = bool(config.get("merge_aliases", False))

    def collect(self, probe_only: bool = False) -> CollectorResult:
        result = CollectorResult(source=self.source, status="OK")
        stop_on_blocked = bool(self.config.get("stop_on_blocked", True))
        try:
            pages = self.target_pages(probe_only=probe_only)
            if not pages:
                result.status = "SKIPPED"
                result.errors.append("no target pages configured")
                return result

            for raw_concept_name, url in pages:
                try:
                    html, raw_path, _ = self.client.fetch(self.source, url, raw_dir=self.raw_dir)
                    result.fetched_pages += 1
                    memberships = self.parse_memberships(raw_concept_name, url, html)
                    result.memberships.extend(memberships)
                    if raw_path:
                        result.metadata.setdefault("raw_paths", []).append(raw_path)
                    if not memberships:
                        result.errors.append(f"parsed no stock ids: {url}")
                except Exception as exc:
                    result.errors.append(f"{url} => {type(exc).__name__}: {exc}")
        except Exception as exc:
            result.errors.append(f"{type(exc).__name__}: {exc}")
        result.row_count = len(result.memberships)
        if result.row_count > 0 and result.errors:
            result.status = "WARN"
        elif result.row_count == 0 and result.errors:
            result.status = "FAILED" if result.fetched_pages == 0 else "WARN"
        elif result.row_count == 0:
            result.status = "WARN"
            result.errors.append("fetched pages but parsed no stock ids")
        return result

    def target_pages(self, probe_only: bool = False) -> list[tuple[str, str]]:
        return []

    def parse_memberships(self, raw_concept_name: str, url: str, html: str) -> list[ConceptMembership]:
        stock_ids = sorted(extract_stock_ids(html, allow_text_fallback=False))
        return [self._membership(stock_id, raw_concept_name, url) for stock_id in stock_ids]

    def _membership(
        self,
        stock_id: str,
        raw_concept_name: str,
        url: str,
        concept_type: str | None = None,
    ) -> ConceptMembership:
        concept_id, canonical_name, parent_id, method, confidence = canonicalize(
            raw_concept_name,
            merge_aliases=self.merge_aliases,
        )
        return ConceptMembership(
            stock_id=stock_id,
            raw_concept_name=raw_concept_name,
            concept_type=concept_type or self.concept_type,
            source=self.source,
            source_url=url,
            observed_at=datetime.now(timezone.utc).isoformat(),
            canonical_concept_id=concept_id,
            canonical_name=canonical_name,
            parent_concept_id=parent_id,
            confidence=confidence,
            match_method=method,
        )


class YahooCollector(BaseCollector):
    source = "yahoo"
    discovery_url = "https://tw.stock.yahoo.com/class"
    quotes_api_url = "https://tw.stock.yahoo.com/_td-stock/api/resource/StockServices.getClassQuotes"

    def collect(self, probe_only: bool = False) -> CollectorResult:
        result = CollectorResult(source=self.source, status="OK")
        try:
            pages = self.target_pages(probe_only=probe_only)
            if not pages:
                result.status = "SKIPPED"
                result.errors.append("no target pages configured")
                return result

            for raw_concept_name, url in pages:
                try:
                    raw_paths: list[str] = []
                    fetched_pages = 0
                    try:
                        memberships, raw_paths, fetched_pages = self._fetch_api_memberships(raw_concept_name, url)
                    except SourceBlockedError:
                        raise
                    except Exception as exc:
                        memberships = []
                        result.errors.append(f"api fallback {url} => {type(exc).__name__}: {exc}")
                    if not memberships:
                        html, raw_path, _ = self.client.fetch(self.source, url, raw_dir=self.raw_dir)
                        fetched_pages += 1
                        memberships = self.parse_memberships(raw_concept_name, url, html)
                        if raw_path:
                            raw_paths.append(raw_path)
                    result.fetched_pages += fetched_pages
                    result.memberships.extend(memberships)
                    if raw_paths:
                        result.metadata.setdefault("raw_paths", []).extend(raw_paths)
                    if not memberships:
                        result.errors.append(f"parsed no stock ids: {url}")
                except SourceBlockedError as exc:
                    result.errors.append(f"{url} => SourceBlockedError: {exc}")
                    if stop_on_blocked:
                        result.metadata["stopped_on_blocked"] = True
                        break
                except Exception as exc:
                    result.errors.append(f"{url} => {type(exc).__name__}: {exc}")
        except Exception as exc:
            result.errors.append(f"{type(exc).__name__}: {exc}")
        result.row_count = len(result.memberships)
        if result.row_count > 0 and result.errors:
            result.status = "WARN"
        elif result.row_count == 0 and result.errors:
            result.status = "FAILED" if result.fetched_pages == 0 else "WARN"
        elif result.row_count == 0:
            result.status = "WARN"
            result.errors.append("fetched pages but parsed no stock ids")
        return result

    def target_pages(self, probe_only: bool = False) -> list[tuple[str, str]]:
        if self.config.get("discover_all", True):
            pages = self._discover_class_quote_pages()
        else:
            concepts = self.config.get("concepts", ["AI人工智慧", "台積電", "半導體設備", "Tesla"])
            pages = [
                (
                    f"概念股 / {concept}",
                    "https://tw.stock.yahoo.com/class-quote?"
                    f"category={quote(concept)}&categoryLabel={quote('概念股')}",
                )
                for concept in concepts
            ]
        configured_pages = self.config.get("pages") or []
        pages.extend((str(page["name"]), str(page["url"])) for page in configured_pages)
        if probe_only:
            pages = pages[: min(8, len(pages))]
        return dedupe_pages(pages)

    def parse_memberships(self, raw_concept_name: str, url: str, html: str) -> list[ConceptMembership]:
        stock_ids = sorted(extract_yahoo_result_stock_ids(html))
        concept_type = yahoo_concept_type(raw_concept_name)
        return [self._membership(stock_id, raw_concept_name, url, concept_type=concept_type) for stock_id in stock_ids]

    def _discover_class_quote_pages(self) -> list[tuple[str, str]]:
        html, _, _ = self.client.fetch(self.source, self.discovery_url, raw_dir=self.raw_dir)
        soup = BeautifulSoup(html, "html.parser")
        pages: list[tuple[str, str]] = []
        current_section: str | None = None
        for element in soup.find_all(["h2", "h3", "a"]):
            if element.name in {"h2", "h3"}:
                section = element.get_text(" ", strip=True)
                current_section = section or current_section
                continue
            href = str(element.get("href") or "")
            if "class-quote" not in href:
                continue
            label = element.get_text(" ", strip=True)
            if not label:
                continue
            absolute_url = urljoin(self.discovery_url, href)
            params = parse_qs(urlparse(absolute_url).query)
            parent = unquote(params.get("categoryLabel", [""])[0]).strip() or current_section
            raw_name = f"{parent} / {label}" if parent and parent != label else label
            pages.append((raw_name, absolute_url))
        return pages

    def _fetch_api_memberships(self, raw_concept_name: str, url: str) -> tuple[list[ConceptMembership], list[str], int]:
        params = yahoo_api_params(raw_concept_name, url, offset=0)
        memberships: list[ConceptMembership] = []
        raw_paths: list[str] = []
        fetched_pages = 0
        seen_offsets: set[int] = set()
        concept_type = yahoo_concept_type(raw_concept_name)

        while True:
            offset = int(params.get("offset", "0"))
            if offset in seen_offsets:
                break
            seen_offsets.add(offset)
            api_url = yahoo_quotes_api_url(self.quotes_api_url, params)
            payload, raw_path, _ = self.client.fetch_json(self.source, api_url, raw_dir=self.raw_dir)
            fetched_pages += 1
            if raw_path:
                raw_paths.append(raw_path)
            for item in payload.get("list", []) or []:
                stock_id = str(item.get("systexId") or item.get("symbol") or "").split(".")[0].strip()
                if is_reasonable_tw_stock_id(stock_id):
                    memberships.append(self._membership(stock_id, raw_concept_name, url, concept_type=concept_type))
            next_offset = (payload.get("pagination") or {}).get("nextOffset")
            if next_offset in (None, "", 0, "0"):
                break
            params["offset"] = str(next_offset)
        return memberships, raw_paths, fetched_pages


class GoodinfoCollector(BaseCollector):
    source = "goodinfo"

    def target_pages(self, probe_only: bool = False) -> list[tuple[str, str]]:
        concepts = self.config.get("concepts", ["大數據", "人工智慧", "半導體設備"])
        if probe_only:
            concepts = concepts[: min(2, len(concepts))]
        return [
            (
                concept,
                "https://goodinfo.tw/StockInfo/StockList.asp?"
                f"INDUSTRY_CAT={quote(concept)}&MARKET_CAT={quote('概念股')}",
            )
            for concept in concepts
        ]


class StatementdogCollector(BaseCollector):
    source = "statementdog"

    def target_pages(self, probe_only: bool = False) -> list[tuple[str, str]]:
        tags = self.config.get(
            "tags",
            [
                {"id": "1477", "name": "5G"},
                {"id": "2207", "name": "機器人"},
                {"id": "1169", "name": "電子商務"},
            ],
        )
        if probe_only:
            tags = tags[: min(2, len(tags))]
        return [(str(tag["name"]), f"https://statementdog.com/tags/{tag['id']}") for tag in tags]


class WantgooCollector(BaseCollector):
    source = "wantgoo"

    def target_pages(self, probe_only: bool = False) -> list[tuple[str, str]]:
        pages = self.config.get(
            "pages",
            [
                {"name": "宅經濟", "url": "https://www.wantgoo.com/index/%5E128/stocks"},
                {"name": "工業4.0", "url": "https://www.wantgoo.com/index/%255E458/stocks"},
                {"name": "3D列印", "url": "https://www.wantgoo.com/index/%5E415/stocks"},
            ],
        )
        if probe_only:
            pages = pages[: min(2, len(pages))]
        return [(str(page["name"]), str(page["url"])) for page in pages]


class MoneydjCollector(BaseCollector):
    source = "moneydj"
    discovery_url = "https://www.moneydj.com/z/zg/zge_EH001106_30.djhtm"

    def target_pages(self, probe_only: bool = False) -> list[tuple[str, str]]:
        if self.config.get("discover_all", True):
            concepts = self._discover_concepts()
        else:
            concepts = self.config.get(
                "concepts",
                [
                    {"code": "EH001173", "name": "人工智慧AI"},
                    {"code": "EH000118", "name": "台積電"},
                    {"code": "EH000056", "name": "電動車"},
                    {"code": "EH000189", "name": "機器人"},
                ],
            )
        if probe_only:
            concepts = concepts[: min(3, len(concepts))]
        return [
            (
                str(concept["name"]),
                f"https://www.moneydj.com/z/zg/zge_{concept['code']}_30.djhtm",
            )
            for concept in concepts
        ]

    def _discover_concepts(self) -> list[dict[str, str]]:
        html, _, _ = self.client.fetch(self.source, self.discovery_url, raw_dir=self.raw_dir)
        soup = BeautifulSoup(html, "html.parser")
        concepts = []
        for option in soup.find_all("option"):
            code = str(option.get("value") or "").strip()
            name = option.get_text(" ", strip=True).replace("概念股", "").strip()
            if code.startswith("EH") and name:
                concepts.append({"code": code, "name": name})
        return concepts

    def parse_memberships(self, raw_concept_name: str, url: str, html: str) -> list[ConceptMembership]:
        stock_ids = sorted(
            {
                match.group(1)
                for match in re.finditer(r"GenLink2stk\('AS([0-9]{4})'\s*,\s*'[^']+'\)", html)
                if is_reasonable_tw_stock_id(match.group(1))
            }
        )
        return [self._membership(stock_id, raw_concept_name, url) for stock_id in stock_ids]


class PchomeCollector(BaseCollector):
    source = "pchome"

    def collect(self, probe_only: bool = False) -> CollectorResult:
        result = CollectorResult(source=self.source, status="OK")
        pages = self.target_pages(probe_only=probe_only)
        if not pages:
            result.status = "SKIPPED"
            result.errors.append("no target pages configured")
            return result
        for raw_concept_name, url in pages:
            try:
                html, raw_path, _ = self.client.post(self.source, url, data={"is_check": "1"}, raw_dir=self.raw_dir)
                result.fetched_pages += 1
                memberships = self.parse_memberships(raw_concept_name, url, html)
                result.memberships.extend(memberships)
                if raw_path:
                    result.metadata.setdefault("raw_paths", []).append(raw_path)
                if not memberships:
                    result.errors.append(f"parsed no stock ids: {url}")
            except Exception as exc:
                result.errors.append(f"{url} => {type(exc).__name__}: {exc}")
        result.row_count = len(result.memberships)
        if result.row_count > 0 and result.errors:
            result.status = "WARN"
        elif result.row_count == 0 and result.errors:
            result.status = "WARN" if result.fetched_pages > 0 else "FAILED"
        elif result.row_count == 0:
            result.status = "WARN"
            result.errors.append("fetched pages but parsed no stock ids")
        return result

    def target_pages(self, probe_only: bool = False) -> list[tuple[str, str]]:
        pages = self.config.get(
            "pages",
            [
                {"name": "AI人工智慧", "url": "https://pchome.megatime.com.tw/group/mkt4/cidA201.html"},
                {"name": "機器人", "url": "https://pchome.megatime.com.tw/group/mkt4/cidA180.html"},
                {"name": "電動車", "url": "https://pchome.megatime.com.tw/group/mkt4/cidA127.html"},
            ],
        )
        if probe_only:
            pages = pages[: min(2, len(pages))]
        return [(str(page["name"]), str(page["url"])) for page in pages]

    def parse_memberships(self, raw_concept_name: str, url: str, html: str) -> list[ConceptMembership]:
        soup = BeautifulSoup(html, "html.parser")
        title = soup.find("title")
        concept_name = raw_concept_name
        if title:
            concept_name = title.get_text(" ", strip=True).split("－")[0].replace("概念股", "").strip() or raw_concept_name
        stock_ids = set()
        for link in soup.find_all("a", href=True):
            href = str(link["href"])
            text = link.get_text(" ", strip=True)
            match = re.fullmatch(r"/stock/sid([0-9]{4,6})\.html", href)
            if match and f"({match.group(1)})" in text:
                stock_id = match.group(1)
                if is_reasonable_tw_stock_id(stock_id):
                    stock_ids.add(stock_id)
        return [self._membership(stock_id, concept_name, url) for stock_id in sorted(stock_ids)]


class TpexValueChainCollector(BaseCollector):
    source = "tpex_value_chain"
    concept_type = "supply_chain"

    def target_pages(self, probe_only: bool = False) -> list[tuple[str, str]]:
        pages = self.config.get(
            "pages",
            [
                {
                    "name": "產業價值鏈平台說明",
                    "url": "https://nweb.tpex.org.tw/TPEX224/news_1.html",
                }
            ],
        )
        if probe_only:
            pages = pages[:1]
        return [(str(page["name"]), str(page["url"])) for page in pages]


COLLECTOR_TYPES = {
    "yahoo": YahooCollector,
    "goodinfo": GoodinfoCollector,
    "statementdog": StatementdogCollector,
    "wantgoo": WantgooCollector,
    "moneydj": MoneydjCollector,
    "pchome": PchomeCollector,
    "tpex_value_chain": TpexValueChainCollector,
}


def build_collectors(
    project_root: Path,
    config: dict[str, Any],
    raw_dir: Path | None = None,
) -> list[BaseCollector]:
    client = HttpClient(
        project_root=project_root,
        timeout=int(config.get("timeout_seconds", 20)),
        sleep_seconds=float(config.get("sleep_seconds", 0.5)),
        retry_count=int(config.get("retry_count", 1)),
        retry_sleep_seconds=float(config.get("retry_sleep_seconds", 3.0)),
    )
    enabled = config.get("enabled_sources") or list(COLLECTOR_TYPES)
    collectors: list[BaseCollector] = []
    source_configs = config.get("sources", {})
    for source in enabled:
        collector_type = COLLECTOR_TYPES.get(source)
        if collector_type is None:
            continue
        collector_config = dict(source_configs.get(source, {}))
        collector_config.setdefault("merge_aliases", bool(config.get("merge_aliases", False)))
        collectors.append(collector_type(client, collector_config, raw_dir=raw_dir))
    return collectors


def extract_stock_ids(html: str, allow_text_fallback: bool = True) -> set[str]:
    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text(" ", strip=True)
    ids = set()
    for match in SUFFIXED_STOCK_ID_RE.finditer(html + " " + text):
        stock_id = match.group(1).strip()
        if is_reasonable_tw_stock_id(stock_id):
            ids.add(stock_id)
    if not allow_text_fallback:
        return ids
    for match in TEXT_STOCK_NAME_RE.finditer(text):
        stock_id = match.group(1).strip()
        if is_reasonable_tw_stock_id(stock_id):
            ids.add(stock_id)
    return ids


def extract_yahoo_result_stock_ids(html: str) -> set[str]:
    """只讀 Yahoo 類股報價結果表，避開頁首熱門股與頁尾新聞推薦。"""
    json_ids = {
        match.group(1).strip()
        for match in re.finditer(r'"systexId"\s*:\s*"([0-9]{4,6})"', html)
        if is_reasonable_tw_stock_id(match.group(1).strip())
    }
    if json_ids:
        return json_ids

    scoped_html = html
    html_start = scoped_html.find("股票名稱/代號")
    if html_start >= 0:
        scoped_html = scoped_html[html_start:]
    html_end_candidates = [scoped_html.find(marker) for marker in ("我的自選股", "最多人瀏覽", "Yahoo Finance")]
    html_end_candidates = [index for index in html_end_candidates if index > 0]
    if html_end_candidates:
        scoped_html = scoped_html[: min(html_end_candidates)]
    html_ids = {
        match.group(1).strip()
        for match in SUFFIXED_STOCK_ID_RE.finditer(scoped_html)
        if is_reasonable_tw_stock_id(match.group(1).strip())
    }
    if html_start >= 0 and html_ids:
        return html_ids

    soup = BeautifulSoup(html, "html.parser")
    text = soup.get_text("\n", strip=True)
    table_text = text
    start = table_text.find("股票名稱/代號")
    if start >= 0:
        table_text = table_text[start:]
    end_candidates = [table_text.find(marker) for marker in ("我的自選股", "最多人瀏覽", "Yahoo Finance")]
    end_candidates = [index for index in end_candidates if index > 0]
    if end_candidates:
        table_text = table_text[: min(end_candidates)]

    ids = {
        match.group(1).strip()
        for match in SUFFIXED_STOCK_ID_RE.finditer(table_text)
        if is_reasonable_tw_stock_id(match.group(1).strip())
    }
    if ids:
        return ids
    return extract_stock_ids(html, allow_text_fallback=False)


def yahoo_concept_type(raw_concept_name: str) -> str:
    label = str(raw_concept_name)
    if "ETF" in label or "ETN" in label or "認購" in label or "認售" in label or "牛證" in label or "熊證" in label:
        return "asset_class"
    if label.startswith(("上市類股 /", "上櫃類股 /", "電子產業 /")):
        return "industry"
    return "theme"


def yahoo_api_params(raw_concept_name: str, url: str, offset: int) -> dict[str, str]:
    parsed = urlparse(url)
    query = parse_qs(parsed.query)
    params: dict[str, str] = {}
    for key in ("sectorId", "exchange", "category", "categoryLabel"):
        value = query.get(key, [None])[0]
        if value not in (None, ""):
            params[key] = unquote(str(value))
    category = params.get("category")
    if category:
        params.setdefault("categoryName", category)
    else:
        params.setdefault("categoryName", str(raw_concept_name).split("/")[-1].strip())
    params["offset"] = str(offset)
    return params


def yahoo_quotes_api_url(base_url: str, params: dict[str, str]) -> str:
    encoded = "".join(f";{key}={quote(str(value), safe='')}" for key, value in params.items())
    return f"{base_url}{encoded}"


def dedupe_pages(pages: list[tuple[str, str]]) -> list[tuple[str, str]]:
    deduped: dict[str, tuple[str, str]] = {}
    for raw_name, url in pages:
        deduped.setdefault(url, (raw_name, url))
    return list(deduped.values())


def is_reasonable_tw_stock_id(stock_id: str) -> bool:
    if not stock_id.isdigit():
        return False
    if len(stock_id) == 4:
        if stock_id.startswith("00"):
            return int(stock_id) >= 50
        return stock_id[0] in "123456789"
    if len(stock_id) in {5, 6} and stock_id.startswith("00"):
        return True
    return False


def discover_yahoo_concepts(html: str) -> list[str]:
    soup = BeautifulSoup(html, "html.parser")
    concepts = []
    for link in soup.find_all("a", href=True):
        href = str(link["href"])
        if "class-quote" not in href:
            continue
        params = parse_qs(urlparse(href).query)
        category = params.get("category", [None])[0]
        if category:
            concepts.append(unquote(category))
    return sorted(set(concepts))
