# Context Manifest

## 必讀

- `AGENTS.md`：專案規範。
- `.work/current/status.md`：目前狀態。
- `.work/current/handoff.md`：接手摘要。
- `docs/tasks/2026-05-28_MARKET-CONTEXT-01_external_dashboard_research.md`：完整研究與開發建議。

## 依需要讀

- `app/data_fetcher.py`：現有 TWSE/TPEX 日行情 ETL。
- `app/trading/market_regime.py`：現有薄版市場狀態判斷。
- `app/trading/ranking_policy.py`：正式 ranking policy，不得未回測調權重。
- `scripts/run_daily.sh`、`scripts/run_automation.py`：daily pipeline 接入點。
- `scripts/generate_daily_report.py`：日報市場背景接入點。

## 外部參考

- `https://github.com/tetsu811/tw-stock-dashboard`
- `https://tetsu811.github.io/tw-stock-dashboard/`

不要重新爬整站，除非要驗證外部 repo 是否已更新。
