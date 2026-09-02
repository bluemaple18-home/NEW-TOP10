---
id: REPAIR-NEW-TOP10-R13-TRUSTED-COMPLETED-TRADE-DATE-AUTHORITY
status: completed
type: implementation
---

# R13 trusted completed trade date authority 修復

## Root question

如何讓既有 forward-capture seam 從可驗證、不可自填的本機 daily completion evidence 取得 completed trade date，而不是把 `date.today()` 當成 authority？

## 已確認事實

- `data/clean/features.parquet` 與 `data/clean/universe.parquet` 已到 `2026-09-01`。
- canonical builder 可從 fresh features 建出 `market-regime-history.v2` 至 `2026-09-01`，且 `as_of_date == trade_date` 零違規。
- 兩個 producer 目前都把 `trusted_capture_trade_date = date.today().isoformat()`，因此隔日完成的 fresh daily data 永遠無法作為前一 completed trade date 的 forward capture。
- `artifacts/automation_status_2026-09-01.json` 可提供 run date、整體 OK、after-ETL freshness、雙市場 coverage 與 ranking step evidence；authority 必須綁定此類實體檔案的 hash。

## 實作邊界

- 在既有 provenance seam 內加入最小 completed-trade-date authority validator；不得建立 database、registry、scheduler、network client 或第二套 runtime。
- Forward capture 必須明示一個 repo-relative authority artifact；禁止只接受可手填日期或退回 wall clock。
- Validator 至少要求：artifact JSON 可讀、`status=OK`、`run_date` 等於 capture date、`data.freshness.after_etl=OK`、features/universe latest date 等於 capture date、features TWSE/TPEX coverage 都為 OK、ranking step OK。
- Authority artifact 必須進 strict input snapshot，hash 綁入 receipt／manifest；run 前後漂移要 fail closed。
- `REPLAY_GENERATED` 現有語意不得改變；不得放寬 outcome-free、create-only、producer-source、Top-N 或 bundle verification 契約。
- 不修改正式 data、ranking、artifact、config、workflow、scheduler、production；不 network fetch；不 merge、push、deploy。

## 允許修改

- `app/research/ranking_provenance_receipt.py`
- `scripts/build_historical_ranking_replay_set.py`
- `scripts/research_regime_shadow_ranking.py`
- 對應 `tests/` 測試
- 本任務卡與 `docs/evidence/REPAIR-NEW-TOP10-R13-TRUSTED-COMPLETED-TRADE-DATE-AUTHORITY/`

若最小安全設計需要新增一個 `app/research/` 小模組可以新增；不可擴大其他範圍。

## 驗收

- 單元測試覆蓋有效 authority、status 非 OK、日期不符、after-ETL 缺失／失敗、features/universe stale、任一市場缺失／非 OK、ranking 非 OK、authority bytes 漂移。
- 兩個 producer 的 forward path 不再使用 `date.today()` 作 trusted authority；缺 authority 必須在產生 ranking／bundle 前失敗。
- 用去識別 fixture 證明 2026-09-02 執行時可驗證 2026-09-01 completed authority，不偽造系統日期。
- 跑受影響測試與 `git diff --check`；列出 changed files、測試結果、remaining risk。
- 不執行真正 R13 capture；本卡只修 authority contract，R13 session 由 Mainline 另行驗收。

## 停損

- 若 automation status 無法提供足夠的 completed-date authority，停止並回報缺失欄位，不得改成自填日期。
- 若需要改 production daily workflow 或新增外部權限，停止並回報。

## Implementation receipt

- `candidate_commit`: recorded in worker final receipt.
- `changed_files`:
  - `app/research/ranking_provenance_receipt.py`
  - `scripts/build_historical_ranking_replay_set.py`
  - `scripts/research_regime_shadow_ranking.py`
  - `tests/test_ranking_provenance_receipt.py`
  - `tests/test_historical_ranking_replay_set_lineage.py`
  - `tests/test_regime_research_boundaries.py`
  - `docs/evidence/REPAIR-NEW-TOP10-R13-TRUSTED-COMPLETED-TRADE-DATE-AUTHORITY/verification.md`
- `verification`:
  - `uv run pytest tests/test_ranking_provenance_receipt.py tests/test_historical_ranking_replay_set_lineage.py tests/test_regime_research_boundaries.py -q`: `32 passed, 3 warnings`.
  - `git diff --check`: passed.
- `scope_guard`: no production data, ranking artifact, config, workflow, scheduler, network, push, merge, deploy, or real R13 capture executed.
