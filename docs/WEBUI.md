# NEW-TOP10 Market UI 使用手冊

新版 UI 主線是 `React + KLineCharts + FastAPI`，不再維護 Streamlit。

## 快速啟動

```bash
bash scripts/start_market_ui.sh
```

啟動後開啟：

- 前端：`http://127.0.0.1:5173`
- API：`http://127.0.0.1:8001`

舊入口 `bash scripts/start_ui.sh` 仍可使用，但只會轉呼叫新版啟動腳本。

若要讓本機重開後自動啟動 Web UI，可手動安裝 launchd agent：

```bash
bash scripts/setup_webui_launchd.sh
```

## 功能

- 可拖拉、縮放的 K 線圖
- 最新 Top 10 排名與交易理由
- 個股 OHLCV 與技術指標
- 回測摘要以只讀方式呈現，不在 UI 觸發回測
- 市場狀態與風險調整分數

## 驗證

```bash
pnpm --dir web/frontend build
bash scripts/verify_local_dev_health.sh
node scripts/verify_frontend_smoke.mjs
uv run --with-requirements requirements.txt python -m app.pipeline_cli validate
```
