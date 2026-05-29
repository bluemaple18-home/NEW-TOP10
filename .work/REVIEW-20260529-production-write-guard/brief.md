# REVIEW-20260529-production-write-guard

## 卡片類型
Review fix

## 任務目的
把「verify / test 類腳本不得覆寫正式 `data/clean`」變成更完整的硬防線，補齊本次 review 發現的剩餘 P2 風險。

## 背景
本次大量測試時發現 `scripts/verify_pipeline_refactor.py` 原本會把短窗口 ETL 輸出寫進正式 `data/clean`，造成 `universe.parquet` 變成 0 檔。已先補 runtime guard、production write guard、以及暫存目錄測試，但 review 仍發現兩個洞。

## Scope
- 強化 `scripts/verify_pipeline_refactor.py`：除了檔案存在，也要驗證 `universe.parquet` 非空、股票數非 0、最新日期存在。
- 強化 `scripts/verify_production_write_guard.py`：static scan 不只抓 literal `data_dir="data"` / default，也要擋 verify 腳本中 `data_dir` 為變數或不明來源的 `ETLPipeline(...)`。
- 保留 `app/pipeline/orchestrator.py` runtime guard，避免靜態掃描漏網時仍能阻擋正式資料覆寫。

## Out Of Scope
- 不重訓模型。
- 不調整 ranking score。
- 不改 daily production ETL 行為。
- 不把 production `app.pipeline_cli run` 禁掉。

## 驗收條件
- `uv run --with-requirements requirements.txt python scripts/verify_production_write_guard.py` 通過。
- `uv run --with-requirements requirements.txt python scripts/verify_pipeline_refactor.py` 通過，且正式 `data/clean` 不被污染。
- `uv run --with-requirements requirements.txt python scripts/verify_model_group_acceptance.py` 通過。
- `uv run --with-requirements requirements.txt python -m app.pipeline_cli validate --json` 仍為 `ok=true`。
- `git diff --check` 通過。

## Review Findings
- [P2] `verify_pipeline_refactor` 只驗檔案存在，沒有驗 `universe.parquet` 不是空檔。
- [P2] `verify_production_write_guard` 的 static scan 可被 `data_dir = "data"; ETLPipeline(data_dir=data_dir)` 這種變數形式繞過。
