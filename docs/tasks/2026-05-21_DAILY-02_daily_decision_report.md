# DAILY-02：每日決策日報 Artifact

任務ID：`DAILY-02`
卡片類型：`Report / Decision Artifact`
證據路徑：`artifacts/daily_report_2026-05-15.md`、`artifacts/daily_report_2026-05-15.json`

## 背景

DAILY-01 已補每日流程 status / summary，但 PM 或使用者仍需要一份可以直接讀的決策日報，把 Top10、分數拆解、交易計畫、coverage、風險與缺資料摘要集中起來。這張卡只做 artifact，不重算 ranking。

## 範圍

- 新增 `scripts/generate_daily_report.py`。
- 讀取既有 `artifacts/ranking_YYYY-MM-DD.csv` 與 `artifacts/automation_status.json`。
- 產出：
  - `artifacts/daily_report_YYYY-MM-DD.json`
  - `artifacts/daily_report_YYYY-MM-DD.md`
- 報告內容包含：
  - Top10。
  - `risk_adjusted_score / prediction_score / setup_score / quality_score / risk_penalty`。
  - `suggested_weight / gross_exposure / allocated_exposure / cash_weight`。
  - 從 ranking reasons 解析的進場 / 停損 / 目標。
  - 欄位 coverage。
  - data freshness 與風險摘要。

## 非範圍

- 不改 `app/agent_b_ranking.py`。
- 不重算分數或交易計畫。
- 不觸發 API / UI / 回測。
- 不把產業動能或基本面 shadow 結果接入 production score。

## 驗證命令

```bash
uv run --with-requirements requirements.txt python -m py_compile scripts/generate_daily_report.py
uv run --with-requirements requirements.txt python scripts/generate_daily_report.py --date 2026-05-15
```

## 執行紀錄

- `uv run --with-requirements requirements.txt python -m py_compile scripts/generate_daily_report.py` 通過。
- `uv run --with-requirements requirements.txt python scripts/generate_daily_report.py --date 2026-05-15` 通過。
- 產出：
  - `artifacts/daily_report_2026-05-15.json`
  - `artifacts/daily_report_2026-05-15.md`
- JSON 檢查：
  - `schema_version=daily-decision-report.v1`
  - `ranking_date=2026-05-15`
  - `top10` 共 10 檔。
  - 第一名 `3030 德律`。
  - `gross_exposure=0.65`、`allocated_exposure=0.65`、`cash_weight=0.35`。
  - 分數欄位 coverage 皆為 `1.0`。
  - `trade_plan.source=ranking_reasons`，可解析進場 / 停損 / 目標。
- Markdown 檢查：
  - 有 Top10 表格。
  - 有 Coverage 區塊。
  - 有風險與缺資料摘要，包含 `features/events/universe` freshness。
- `REVIEW-DAILY-02` 結論：未發現阻塞問題，可放行；確認腳本只讀 ranking/status artifact，不呼叫 ranking/model/API/ETL，且 JSON/Markdown 內容符合 Top10、分數拆解、交易計畫、coverage、data freshness 與風險摘要。

## Review 交接

任務ID：REVIEW-DAILY-02
卡片類型｜派工對象：Review｜另一個 AI
請讀：`docs/tasks/2026-05-21_DAILY-02_daily_decision_report.md`、`scripts/generate_daily_report.py`、`artifacts/daily_report_2026-05-15.md`、`artifacts/daily_report_2026-05-15.json`
任務目的：review 每日決策日報是否只讀既有 ranking/status artifact，內容是否包含 Top10、分數拆解、交易計畫、coverage、風險與缺資料摘要，且沒有改 ranking/model/API。
證據路徑：`artifacts/daily_report_2026-05-15.md`、`artifacts/daily_report_2026-05-15.json`
