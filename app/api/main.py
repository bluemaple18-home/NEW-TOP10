"""TW Top10 新版看盤 API。"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.backtesting import create_backtesting_router
from app.api.routers.fundamentals import create_fundamentals_router
from app.api.routers.market import create_market_router
from app.api.routers.monitoring import create_monitoring_router
from app.api.routers.stock_detail import create_stock_detail_router
from app.api.routers.trading import create_trading_router
from app.api.routers.weekly import create_weekly_router
from app.data.backtest_repository import BacktestRepository
from app.data.fundamental_repository import FundamentalRepository
from app.data.market_repository import MarketRepository
from app.data.monitoring_repository import MonitoringRepository
from app.data.reference_repository import ReferenceRepository
from app.services.backtest_service import BacktestService
from app.services.fundamental_service import FundamentalService
from app.services.market_service import MarketService
from app.services.monitoring_service import MonitoringService
from app.services.stock_detail_service import StockDetailService
from app.services.weekly_decision_service import WeeklyDecisionService

PROJECT_ROOT = Path(__file__).resolve().parents[2]
reference_repository = ReferenceRepository(PROJECT_ROOT)
market_service = MarketService(MarketRepository(PROJECT_ROOT), reference_repository)
backtest_service = BacktestService(BacktestRepository(PROJECT_ROOT))
fundamental_service = FundamentalService(FundamentalRepository(PROJECT_ROOT))
monitoring_service = MonitoringService(MonitoringRepository(PROJECT_ROOT))
stock_detail_service = StockDetailService(market_service, fundamental_service, backtest_service)
weekly_decision_service = WeeklyDecisionService(market_service)

app = FastAPI(title="TW Top10 Market API", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(create_market_router(market_service))
app.include_router(create_backtesting_router(backtest_service))
app.include_router(create_trading_router(market_service))
app.include_router(create_fundamentals_router(fundamental_service))
app.include_router(create_monitoring_router(monitoring_service))
app.include_router(create_stock_detail_router(stock_detail_service))
app.include_router(create_weekly_router(weekly_decision_service))
