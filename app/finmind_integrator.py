"""三大法人來源整合；必要資料缺漏須明確失敗。"""
from __future__ import annotations

import logging
import re

import pandas as pd
import requests

try:
    from app.finmind_fetcher import FinMindFetcher
except ImportError as exc:
    FinMindFetcher = None
    FINMIND_IMPORT_ERROR = exc
else:
    FINMIND_IMPORT_ERROR = None

logger = logging.getLogger(__name__)
FINMIND_TOP_N = 200
FINMIND_SDK_LOGIN_COST = 1


class InstitutionalDataError(ValueError):
    """正式或離線法人資料不符合可計算契約。"""


class FinMindQuotaError(RuntimeError):
    """額度預檢或資料端點明確拒絕時的安全錯誤。"""

    def __init__(self, reason_code: str, quota: dict[str, object] | None = None):
        super().__init__(reason_code)
        self.reason_code = reason_code
        self.quota = quota or {}


def preflight_finmind_quota(token: str | None, planned_data_fetch_count: int) -> dict[str, object]:
    """逐檔抓取前只查一次 user_info；HTTP 200 不證明 token 有效，未開始視窗以 None 表示。"""
    if planned_data_fetch_count < 0:
        raise ValueError("FinMind 預估呼叫次數不可為負")
    required_fetch_count = planned_data_fetch_count + FINMIND_SDK_LOGIN_COST
    headers = {"Authorization": f"Bearer {token}"} if token else {}
    try:
        response = requests.get(
            "https://api.web.finmindtrade.com/v2/user_info",
            headers=headers,
            timeout=5,
        )
        if response.status_code == 402:
            raise FinMindQuotaError("FINMIND_QUOTA_EXHAUSTED")
        if response.status_code != 200:
            raise FinMindQuotaError("FINMIND_QUOTA_PRECHECK_UNAVAILABLE")
        payload = response.json()
    except requests.RequestException as exc:
        raise FinMindQuotaError("FINMIND_QUOTA_PRECHECK_UNAVAILABLE") from exc
    except ValueError as exc:
        raise FinMindQuotaError("FINMIND_QUOTA_PRECHECK_INVALID") from exc
    if not isinstance(payload, dict):
        raise FinMindQuotaError("FINMIND_QUOTA_PRECHECK_INVALID")
    limit = payload.get("api_request_limit_hour")
    used = payload.get("user_count")
    next_available = payload.get("next_available_time")
    if (type(limit) is not int or limit <= 0 or type(used) is not int or used < 0
            or not isinstance(next_available, str) or (used > 0 and not next_available)):
        raise FinMindQuotaError("FINMIND_QUOTA_PRECHECK_INVALID")
    if next_available == "":
        next_available = None
    if not token:
        # user_info 的 HTTP 200 不證明登入；未附 token 只能使用匿名上限。
        limit = min(limit, 300)
    remaining = max(0, limit - used)
    quota = {
        "limit": limit, "used": used, "remaining": remaining,
        "next_available_time": next_available,
        "planned_data_fetch_count": planned_data_fetch_count,
        "sdk_login_cost": FINMIND_SDK_LOGIN_COST,
        "required_fetch_count": required_fetch_count,
    }
    if remaining < required_fetch_count:
        raise FinMindQuotaError("FINMIND_QUOTA_INSUFFICIENT", quota)
    return quota


def _is_quota_exhausted(exc: BaseException) -> bool:
    """識別 HTTP 402；SDK 遺失狀態碼時比對其額度訊息。"""
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        response = getattr(current, "response", None)
        if getattr(response, "status_code", None) == 402:
            return True
        message = str(current)
        if re.search(r"Final response status:\s*402\b", message):
            return True
        if "Requests reach the upper limit" in message:
            return True
        current = current.__cause__ or current.__context__
    return False


class FinMindIntegrator:
    """將 FinMind 三大法人股數與行情鍵對齊。"""

    def __init__(self, token: str | None = None, *, offline: bool = False):
        self.fetcher = None if offline or FinMindFetcher is None else FinMindFetcher(token=token)
        self.official_fallbacks: list[dict[str, object]] = []
        self.fetch_coverage: dict[str, dict[str, int]] = {}
        self._failed_stock_ids: set[str] = set()

    def coverage_stats(self) -> dict[str, object]:
        """回報本輪各資料集的預期、實得與失敗檔數。"""
        return {
            "expected_fetch_count": sum(item["expected_stock_count"] for item in self.fetch_coverage.values()),
            "received_fetch_count": sum(item["received_stock_count"] for item in self.fetch_coverage.values()),
            "failed_fetch_count": sum(item["failed_stock_count"] for item in self.fetch_coverage.values()),
            "failed_stock_count": len(self._failed_stock_ids),
            "by_dataset": {name: dict(item) for name, item in self.fetch_coverage.items()},
        }

    def _record_fetch(self, dataset: str, stock_id: str, *, received: bool) -> None:
        key = "received_stock_count" if received else "failed_stock_count"
        self.fetch_coverage[dataset][key] += 1
        if not received:
            self._failed_stock_ids.add(stock_id)

    def integrate_chip_data(
        self,
        df: pd.DataFrame,
        top_n: int = FINMIND_TOP_N,
        include_margin: bool = True,
        *,
        institutional_source: pd.DataFrame | None = None,
        margin_not_applicable_stock_ids: set[str] | None = None,
    ) -> pd.DataFrame:
        """只接受可追溯的真實法人來源；不把缺值當零。"""
        if df.empty:
            raise InstitutionalDataError("無行情可對齊法人資料")
        if institutional_source is None and self.fetcher is None:
            raise InstitutionalDataError(f"FinMind 不可用：{FINMIND_IMPORT_ERROR}")
        working = df.copy()
        working["date"] = pd.to_datetime(working["date"]).dt.normalize()
        working["stock_id"] = working["stock_id"].astype(str).str.strip()
        avg = working.groupby("stock_id")["volume"].mean() * working.groupby("stock_id")["close"].mean()
        top_stocks = avg.sort_values(ascending=False).head(top_n).index.astype(str).tolist()
        # 僅由呼叫端以完整窗口官方日報證實不適用的股票可跳過融資融券。
        margin_stocks = [sid for sid in top_stocks if sid not in (margin_not_applicable_stock_ids or ())]
        self.fetch_coverage = {
            "institutional": {"expected_stock_count": len(top_stocks) if institutional_source is None else 0, "received_stock_count": 0, "failed_stock_count": 0},
            "margin": {"expected_stock_count": len(margin_stocks) if include_margin and self.fetcher is not None else 0, "received_stock_count": 0, "failed_stock_count": 0},
        }
        self._failed_stock_ids = set()
        start_date = working["date"].min().strftime("%Y-%m-%d")
        end_date = working["date"].max().strftime("%Y-%m-%d")
        if institutional_source is None:
            institutional = self._load_institutional_frames(top_stocks, start_date, end_date)
        else:
            raw = institutional_source.copy()
            raw["date"] = pd.to_datetime(raw["date"]).dt.normalize()
            raw["stock_id"] = raw["stock_id"].astype(str).str.strip()
            raw = raw[raw["stock_id"].isin(top_stocks) & raw["date"].between(working["date"].min(), working["date"].max())]
            institutional = self._normalize_institutional(raw)
        if institutional.empty:
            raise InstitutionalDataError("全部必要法人資料缺失")
        if institutional[["date", "stock_id"]].duplicated().any():
            raise InstitutionalDataError("法人日期／股票鍵重複")
        expected = working.loc[working["stock_id"].isin(top_stocks), ["date", "stock_id", "market"]].drop_duplicates()
        observed = institutional[["date", "stock_id"]].drop_duplicates()
        gaps = expected.merge(observed, on=["date", "stock_id"], how="left", indicator=True)
        gaps = gaps[gaps["_merge"].eq("left_only")]
        if not gaps.empty:
            if institutional_source is not None:
                examples = [(str(x.date.date()), x.stock_id) for x in gaps.head(12).itertuples()]
                raise InstitutionalDataError(f"離線法人快照缺 {len(gaps)} 個必要行情鍵：{examples}")
            institutional = pd.concat([institutional, self._official_twse_fallback(gaps)], ignore_index=True)
        if institutional[["date", "stock_id"]].duplicated().any():
            raise InstitutionalDataError("官方補回後法人鍵重複")
        working = working.merge(institutional, on=["date", "stock_id"], how="left", validate="one_to_one")
        working["institutional_available"] = working["institutional_available"].fillna(False).astype(bool)
        if include_margin and self.fetcher is not None:
            margin = self._load_margin_frames(margin_stocks, start_date, end_date)
            if not margin.empty:
                working = working.merge(margin, on=["date", "stock_id"], how="left", validate="one_to_one")
                working["margin_available"] = working["margin_available"].fillna(False).astype(bool)
        logger.info("法人整合完成：選取 %s 檔，來源覆蓋 %s 筆，官方補回 %s 筆", len(top_stocks), len(institutional), len(self.official_fallbacks))
        return working

    def _load_institutional_frames(self, stock_ids: list[str], start_date: str, end_date: str) -> pd.DataFrame:
        frames = []
        for stock_id in stock_ids:
            try:
                raw = self.fetcher.get_institutional_investors(stock_id, start_date, end_date)
            except Exception as exc:
                logger.warning("FinMind 法人來源失敗 stock_id=%s error_type=%s", stock_id, type(exc).__name__)
                self._record_fetch("institutional", stock_id, received=False)
                if _is_quota_exhausted(exc):
                    raise FinMindQuotaError("FINMIND_QUOTA_EXHAUSTED") from exc
                raise
            if raw.empty:
                logger.warning("FinMind 法人來源為空 stock_id=%s", stock_id)
                self._record_fetch("institutional", stock_id, received=False)
                raise InstitutionalDataError(f"FinMind 法人來源為空：{stock_id} {start_date}..{end_date}")
            self._record_fetch("institutional", stock_id, received=True)
            frames.append(raw)
        return self._normalize_institutional(pd.concat(frames, ignore_index=True))

    def _normalize_institutional(self, raw: pd.DataFrame) -> pd.DataFrame:
        required = {"date", "stock_id", "buy", "sell", "name"}
        if not required.issubset(raw.columns):
            raise InstitutionalDataError(f"法人原始來源缺欄位：{sorted(required - set(raw.columns))}")
        raw = raw.copy()
        raw["date"] = pd.to_datetime(raw["date"], errors="coerce").dt.normalize()
        raw["stock_id"] = raw["stock_id"].astype(str).str.strip()
        raw["name"] = raw["name"].astype(str).str.strip()
        if raw["date"].isna().any() or raw["stock_id"].eq("").any() or raw["name"].eq("").any():
            raise InstitutionalDataError("法人原始來源日期／身分無效")
        for column in ("buy", "sell"):
            numeric = pd.to_numeric(raw[column], errors="coerce")
            if numeric.isna().any() or (numeric < 0).any() or (numeric != numeric.astype("int64")).any():
                raise InstitutionalDataError(f"法人 {column} 必須是非負整數股數")
            raw[column] = numeric.astype("int64")
        if raw[["date", "stock_id", "name"]].duplicated().any():
            raise InstitutionalDataError("法人來源日期／股票／類別重複")
        raw["net"] = raw["buy"] - raw["sell"]
        matrix = raw.pivot(index=["date", "stock_id"], columns="name", values="net")
        foreign = matrix.get("Foreign_Investor", pd.Series(index=matrix.index, dtype="float64"))
        trust = matrix.get("Investment_Trust", pd.Series(index=matrix.index, dtype="float64"))
        dealer_self = matrix.get("Dealer_self", pd.Series(index=matrix.index, dtype="float64"))
        dealer_hedge = matrix.get("Dealer_Hedging", pd.Series(index=matrix.index, dtype="float64"))
        dealer_total = matrix.get("Dealer", pd.Series(index=matrix.index, dtype="float64"))
        detail_present = dealer_self.notna() & dealer_hedge.notna()
        aggregate_present = dealer_self.isna() & dealer_hedge.isna() & dealer_total.notna()
        complete = foreign.notna() & trust.notna() & (detail_present | aggregate_present)
        if not complete.any():
            return pd.DataFrame(columns=["date", "stock_id", "foreign_buy", "trust_buy", "dealer_buy", "institutional_available"])
        dealer = (dealer_self + dealer_hedge).where(detail_present, dealer_total.where(aggregate_present))
        output = pd.DataFrame({
            "foreign_buy": foreign.loc[complete].astype("int64"),
            "trust_buy": trust.loc[complete].astype("int64"),
            "dealer_buy": dealer.loc[complete].astype("int64"),
            "institutional_available": True,
        }).reset_index()
        return output[["date", "stock_id", "foreign_buy", "trust_buy", "dealer_buy", "institutional_available"]]

    def _official_twse_fallback(self, missing: pd.DataFrame) -> pd.DataFrame:
        """只對可證實的上市缺口查官方 T86；無法證實即拒絕。"""
        from app.tskg.twse_t86 import fetch_t86_snapshot

        if len(missing) > 20 or missing["market"].str.upper().ne("TWSE").any():
            raise InstitutionalDataError(f"法人來源缺 {len(missing)} 筆；無法在受限官方補回範圍內驗證")
        rows = []
        for date, group in missing.groupby("date"):
            day = date.date().isoformat()
            official = fetch_t86_snapshot(day)
            index = {r["stock_id"]: r for r in official["records"]}
            for sid in group["stock_id"]:
                if sid not in index:
                    raise InstitutionalDataError(f"官方 T86 也缺法人值：{day} {sid}")
                r = index[sid]
                rows.append({"date": date, "stock_id": sid, "foreign_buy": r["foreign_ex_dealer_net_shares"], "trust_buy": r["investment_trust_net_shares"], "dealer_buy": r["dealer_total_net_shares"], "institutional_available": True})
                self.official_fallbacks.append({"date": day, "stock_id": sid, "source_id": official["source_id"], "source_hash": official["integrity"]["canonical_sha256"]})
        return pd.DataFrame(rows)

    def _load_margin_frames(self, stock_ids: list[str], start_date: str, end_date: str) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for index, stock_id in enumerate(stock_ids):
            if index % 100 == 0:
                logger.info("融資融券進度: %s/%s", index, len(stock_ids))
            try:
                raw = self.fetcher.get_margin_purchase_short_sale(stock_id, start_date, end_date)
            except Exception as exc:
                logger.warning("FinMind 融資融券來源失敗 stock_id=%s error_type=%s", stock_id, type(exc).__name__)
                self._record_fetch("margin", stock_id, received=False)
                if _is_quota_exhausted(exc):
                    raise FinMindQuotaError("FINMIND_QUOTA_EXHAUSTED") from exc
                continue
            if raw.empty:
                logger.warning("FinMind 融資融券來源為空 stock_id=%s", stock_id)
                self._record_fetch("margin", stock_id, received=False)
                continue
            normalized = self._normalize_margin(raw, stock_id)
            self._record_fetch("margin", stock_id, received=not normalized.empty)
            if not normalized.empty:
                frames.append(normalized)
        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        return combined.drop_duplicates(subset=["date", "stock_id"], keep="last")

    def _normalize_margin(self, raw: pd.DataFrame, stock_id: str) -> pd.DataFrame:
        if raw.empty:
            return pd.DataFrame()
        if "date" not in raw.columns:
            logger.warning("融資融券資料缺少 date stock_id=%s columns=%s", stock_id, list(raw.columns))
            return pd.DataFrame()

        frame = raw.copy()
        frame["date"] = pd.to_datetime(frame["date"])
        output = pd.DataFrame({"date": frame["date"], "stock_id": stock_id})
        source_map = {
            "margin_purchase_buy": "MarginPurchaseBuy",
            "margin_purchase_sell": "MarginPurchaseSell",
            "margin_purchase_cash_repayment": "MarginPurchaseCashRepayment",
            "margin_purchase_today_balance": "MarginPurchaseTodayBalance",
            "margin_purchase_yesterday_balance": "MarginPurchaseYesterdayBalance",
            "short_sale_buy": "ShortSaleBuy",
            "short_sale_sell": "ShortSaleSell",
            "short_sale_cash_repayment": "ShortSaleCashRepayment",
            "short_sale_today_balance": "ShortSaleTodayBalance",
            "short_sale_yesterday_balance": "ShortSaleYesterdayBalance",
        }
        for target, source in source_map.items():
            if source in frame.columns:
                output[target] = pd.to_numeric(frame[source], errors="coerce")
            else:
                output[target] = pd.NA

        output["margin_purchase_balance_change"] = (
            output["margin_purchase_today_balance"] - output["margin_purchase_yesterday_balance"]
        )
        output["short_sale_balance_change"] = output["short_sale_today_balance"] - output["short_sale_yesterday_balance"]
        output["margin_available"] = True
        return output

    def _load_daily_short_sale_balance_frames(self, stock_ids: list[str], start_date: str, end_date: str) -> pd.DataFrame:
        frames: list[pd.DataFrame] = []
        for index, stock_id in enumerate(stock_ids):
            if index % 100 == 0:
                logger.info("借券賣出餘額進度: %s/%s", index, len(stock_ids))
            raw = self.fetcher.get_daily_short_sale_balances(stock_id, start_date, end_date)
            normalized = self._normalize_daily_short_sale_balances(raw, stock_id)
            if not normalized.empty:
                frames.append(normalized)
        if not frames:
            return pd.DataFrame()
        combined = pd.concat(frames, ignore_index=True)
        return combined.drop_duplicates(subset=["date", "stock_id"], keep="last")

    def _normalize_daily_short_sale_balances(self, raw: pd.DataFrame, stock_id: str) -> pd.DataFrame:
        """正規化信用額度總量管制餘額表中的借券賣出欄位。"""

        if raw.empty:
            return pd.DataFrame()
        if "date" not in raw.columns:
            logger.warning("借券賣出餘額資料缺少 date stock_id=%s columns=%s", stock_id, list(raw.columns))
            return pd.DataFrame()

        frame = raw.copy()
        frame["date"] = pd.to_datetime(frame["date"])
        output = pd.DataFrame({"date": frame["date"], "stock_id": stock_id})
        source_map = {
            "margin_short_previous_day_balance": "MarginShortSalesPreviousDayBalance",
            "margin_short_short_sales": "MarginShortSalesShortSales",
            "margin_short_short_covering": "MarginShortSalesShortCovering",
            "margin_short_stock_redemption": "MarginShortSalesStockRedemption",
            "margin_short_current_day_balance": "MarginShortSalesCurrentDayBalance",
            "margin_short_quota": "MarginShortSalesQuota",
            "sbl_short_previous_day_balance": "SBLShortSalesPreviousDayBalance",
            "sbl_short_sales": "SBLShortSalesShortSales",
            "sbl_returns": "SBLShortSalesReturns",
            "sbl_adjustments": "SBLShortSalesAdjustments",
            "sbl_current_day_balance": "SBLShortSalesCurrentDayBalance",
            "sbl_quota": "SBLShortSalesQuota",
            "sbl_short_covering": "SBLShortSalesShortCovering",
        }
        for target, source in source_map.items():
            if source in frame.columns:
                output[target] = pd.to_numeric(frame[source], errors="coerce")
            else:
                output[target] = pd.NA

        valid_previous = output["sbl_short_previous_day_balance"].where(output["sbl_short_previous_day_balance"] >= 0)
        output["sbl_balance_change_from_source"] = output["sbl_current_day_balance"] - valid_previous
        output = output.sort_values(["stock_id", "date"]).copy()
        output["sbl_balance_change_1d"] = output.groupby("stock_id")["sbl_current_day_balance"].diff()
        output["borrow_squeeze_available"] = True
        return output
