# 2026-05-12 模型底座與資料契約換手交接

## Root Question

請 code review 最近兩階段重構：

1. 資料契約、自動化、Agent B 排名與訓練標籤修補。
2. 模型 registry 與 M2 基本面品質模型底座。

重點不是 UI，而是確認模型/資料邊界是否乾淨、回測與外部抓資料是否仍隔離。

## 目前狀態

已完成：

- 新增資料契約 validator：`app.pipeline_cli validate`
- 新增本地衍生產物修復：`app.pipeline_cli repair-local`
- 修復正式 `data/clean` 缺 `avg_value_20d/events/universe` 的問題
- Agent B 排名會合併 `events.parquet`，規則分數恢復生效
- Agent B 輸出檔名改用資料交易日
- 修正 `signals.yaml` 的 `losw_20d_low -> lose_20d_low`
- 訓練 label 尾端無未來報酬樣本不再被標成 `target=0`
- 自動化 `daily` 在 ETL 後新增資料契約閘門
- `status` 模式會實際檢查資料健康
- 建立 11 個模型的 registry 與 roadmap
- 建立 M2 基本面底座：Goodinfo 欄位正規化、metrics、sanity check、cache repository、service、API、離線 import CLI

## 主要改動檔案

資料契約與 pipeline：

- `app/pipeline/validation.py`
- `app/pipeline/repair.py`
- `app/pipeline_cli.py`
- `scripts/verify_data_contracts.py`
- `scripts/run_automation.py`

Agent B / 模型訓練：

- `app/agent_b_ranking.py`
- `app/agent_b_modeling.py`
- `app/labels.py`
- `config/signals.yaml`
- `requirements.txt`

模型底座：

- `app/modeling/contracts.py`
- `app/modeling/registry.py`
- `scripts/verify_model_foundation.py`
- `docs/architecture/MODEL_ROADMAP.md`

M2 基本面：

- `app/fundamentals/goodinfo.py`
- `app/fundamentals/goodinfo_client.py`
- `app/fundamentals/metrics.py`
- `app/fundamentals/sanity.py`
- `app/contracts/fundamental.py`
- `app/data/fundamental_repository.py`
- `app/services/fundamental_service.py`
- `app/api/routers/fundamentals.py`
- `scripts/import_goodinfo_fundamentals.py`

UI 退役相關：

- `requirements.txt` 移除 `streamlit`
- `scripts/start_ui.sh` 改成轉呼叫 `scripts/start_market_ui.sh`
- `app/ui/` 已刪除
- `docs/WEBUI.md` 改成 React/FastAPI/KLineCharts 主線

## 設計決策

資料契約：

- `features.parquet`、`events.parquet`、`universe.parquet` 是正式下游契約。
- 缺欄位、主鍵重複、事件非 0/1、最新日覆蓋率不足都要被 validator 揭露。
- `repair-local` 只用既有 `features.parquet` 補衍生產物，不抓外部 API。

回測隔離：

- 仍維持 API/UI 只讀回測 artifacts。
- 本輪沒有讓基本面或 ranking 觸發回測。

基本面隔離：

- `/api/stocks/{stock_id}/fundamentals` 只讀 `data/fundamentals/{stock_id}.json` cache。
- API 與 ranking 不會即時呼叫 Goodinfo。
- `scripts/import_goodinfo_fundamentals.py` 是離線匯入入口。

模型底座：

- `app/modeling/registry.py` 只是 registry，不直接訓練或推論。
- 11 個模型先定義 input/output/status，後面逐一落實。

## Reviewer 建議優先看

1. `app/labels.py` 與 `app/agent_b_modeling.py`
   - 確認無未來資料樣本標成 `NaN` 並在訓練前 drop，不會污染 target。

2. `app/agent_b_ranking.py`
   - 確認 `events.parquet` merge 不會造成日期/股票 key 對不齊。
   - 確認 date normalize 邏輯能處理含時間戳的交易日。
   - 確認正向理由與風險提醒拆分合理。

3. `app/pipeline/validation.py`
   - 確認 validator 不會過度嚴格或放太鬆。
   - 確認 `avg_value_20d/events/universe` 作為正式契約是否合理。

4. `app/fundamentals/goodinfo_client.py`
   - 確認 Goodinfo HTML parser 夠保守。
   - 確認它只用於 CLI，沒有被 API/import path 不小心觸發外部網站。

5. `app/services/fundamental_service.py`
   - 確認 cache payload 到 metrics 的流程安全。
   - 確認 available=false 行為對 UI 友善。

6. `scripts/run_automation.py`
   - 確認 `daily` 先 ETL、validate、再 ranking。
   - 確認 `status` 執行 validate 會正確 fail fast。

## 已驗證

已跑過：

```bash
uv run --with-requirements requirements.txt python -m app.pipeline_cli validate
uv run --with-requirements requirements.txt python scripts/verify_data_contracts.py
uv run --with-requirements requirements.txt python scripts/verify_model_foundation.py
uv run --with-requirements requirements.txt python -m scripts.run_automation daily --dry-run
uv run --with-requirements requirements.txt python -m app.agent_b_ranking
uv run --with-requirements requirements.txt python -c "from fastapi.testclient import TestClient; from app.api.main import app; c=TestClient(app); print(c.get('/api/health').status_code, c.get('/api/rankings/latest').status_code, c.get('/api/stocks/1101/fundamentals').status_code)"
pnpm --dir web/frontend build
```

最後已知結果：

- `app.pipeline_cli validate`：features/events/universe 全 OK
- `verify_model_foundation.py`：`MODEL_FOUNDATION_OK specs=11`
- 基本面 API：`/api/stocks/1101/fundamentals` 回 `200`，無 cache 時 `available=false`
- ranking smoke 可產 `artifacts/ranking_2026-01-20.csv`
- 前端 build 通過

## 尚未做

- 尚未實際打 Goodinfo 網站。
- 尚未建立 `data/fundamentals/*.json` 真實 cache。
- 尚未把基本面特徵放入 ranking 權重。
- 尚未做 factor IC / coverage / turnover 監控。
- 尚未跑真實模型重訓。
- 尚未跑真實外部 ETL。

## Known Risks

- `GoodinfoClient` 的 HTML table parser 需用真實網站驗證，Goodinfo 結構變動風險高。
- 目前 `repair-local` 會改寫 `data/clean/features.parquet` 以補欄位，reviewer 可評估是否要改成輸出新檔或 require confirmation。
- `app.agent_b_ranking` 仍有舊式 class 與新的 trading service 混在一起，後續可再拆薄。
- `models/latest_lgbm.pkl` 目前不存在，ranking smoke 會 fallback `model_prob=0.5`。
- `.venv` 目前不可靠，實際執行應以 `uv run --with-requirements requirements.txt ...` 為準。

## 下一步建議

1. Code review 本 handoff 列出的檔案。
2. 若 reviewer 同意，下一階段做 M11：factor IC / coverage / turnover 監控。
3. 之後再手動挑 1-3 檔跑 Goodinfo import，確認 parser 與 cache schema。
4. 基本面穩定前，不要讓 M2 進 ranking 權重。
