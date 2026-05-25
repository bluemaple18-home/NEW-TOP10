# TW Top10 Market API

這是舊路徑相容說明；新版 API 入口已移到 `app/api/main.py`。

## 啟動

```bash
uv run --with fastapi --with uvicorn --with pandas --with pyarrow \
  uvicorn app.api.main:app --reload --host 127.0.0.1 --port 8000
```

## 端點

- `GET /api/health`
- `GET /api/rankings/latest?limit=10`
- `GET /api/stocks/{stock_id}/ohlcv?limit=240`
- `POST /api/cache/clear`
