# DAILY-03：Daily Postcheck Acceptance

任務ID：`DAILY-03`

證據路徑：`artifacts/daily_postcheck_2026-05-22.json`

## 目的

把 daily 後驗收接成可選 postcheck，確認 ranking artifact、API、前端資料載入一致。

## 範圍

- 新增 `scripts/run_daily_postcheck.py`。
- 讀取 `artifacts/automation_status.json` 與 ranking artifact。
- 可選檢查本機 API weekly candidates 是否與 ranking Top1 / Top10 overlap 對齊；Top10 overlap 必須達到 `min(10, ranking top count, API candidate count)`。
- 可選呼叫既有 `scripts/verify_frontend_smoke.mjs`，驗證候補列表、個股頁、K 線 30D、交易計畫 rail badge。
- `scripts/run_automation.py` 加入 `daily.postcheck`，由 `config/automation.yaml` 預設關閉。

## 不做

- 不重跑 ETL。
- 不重跑 ranking。
- 不訓練模型。
- 不改 API 或前端產品邏輯。

## 驗收

- `scripts/run_daily_postcheck.py --skip-api` 可在只有 artifact 的情境輸出 postcheck JSON。
- dry-run status 只有 `expected_ranking_artifact` 時，預設不得被當成正式 postcheck OK；必須使用正式 `metadata.ranking_artifact` 或明確 `--ranking`。
- 本機服務開啟時，`scripts/run_daily_postcheck.py --include-frontend` 會同時核對 API 與前端 smoke。
- `run_automation daily` 預設只記錄 `daily.postcheck=SKIPPED`，不改 daily 原本成功條件。

## 驗證紀錄

- `uv run --with-requirements requirements.txt python -m py_compile scripts/run_daily_postcheck.py scripts/run_automation.py` 通過。
- `uv run --with-requirements requirements.txt python scripts/run_daily_postcheck.py --skip-api --output /private/tmp/top10_daily03_expected_reject.json` 正確失敗，dry-run `expected_ranking_artifact` 不會被當正式來源。
- `uv run --with-requirements requirements.txt python scripts/run_daily_postcheck.py --allow-expected-ranking --skip-api --output /private/tmp/top10_daily03_expected_reference.json` 通過但 status=`REFERENCE`。
- `bash scripts/verify_local_dev_health.sh` 通過。
- `uv run --with-requirements requirements.txt python scripts/run_daily_postcheck.py --ranking artifacts/ranking_2026-05-15.csv --include-frontend` 通過，輸出 `artifacts/daily_postcheck_2026-05-22.json`。
- `uv run --with-requirements requirements.txt python -m scripts.run_automation daily --dry-run` 通過，`daily.postcheck=SKIPPED`。

## 證據摘要

- ranking Top1：`3030 德律`。
- ranking source：`arg`，acceptance_mode=`official`。
- API weekly candidates Top1：`3030`。
- API / ranking Top10 overlap：`10/10`，`top10_overlap_ok=true`。
- frontend smoke：`candidateCount=10`、`selectedStockTitle=3030 德律`、`windowBars=30`、`tradeRailMarkCount=3`、`diagnostics=[]`。

## Review 結論

- `REVIEW-DAILY-03-FIX` 結論：未發現阻塞問題，可放行。
- 前次 P2 已修正：Top10 overlap 已納入 API consistency gate。
- 前次 P2 已修正：dry-run `expected_ranking_artifact` 預設不再被當成正式 postcheck OK；顯式 `--allow-expected-ranking` 只會得到 `REFERENCE`。
- 正式 evidence 使用明確 `--ranking artifacts/ranking_2026-05-15.csv`，`ranking.source=arg`、`acceptance_mode=official`、status=`OK`。

## Review 派工卡

任務ID：REVIEW-DAILY-03
卡片類型｜派工對象：Review / Ops Acceptance｜另一個 AI
請讀：`docs/tasks/2026-05-22_DAILY-03_daily_postcheck_acceptance.md`、`scripts/run_daily_postcheck.py`、`scripts/run_automation.py`、`config/automation.yaml`
任務目的：檢查 DAILY-03 是否只做可選 postcheck，且 ranking/API/frontend consistency 判定可信，沒有重跑 ETL/ranking/model
證據路徑：`artifacts/daily_postcheck_2026-05-22.json`、`artifacts/top10_ops02_frontend_smoke_2026-05-19.json`
