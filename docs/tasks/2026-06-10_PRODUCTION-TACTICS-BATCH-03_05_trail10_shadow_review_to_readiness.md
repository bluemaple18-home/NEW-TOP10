# PRODUCTION-TACTICS-BATCH-03-05｜Trail10 Shadow Review → Publish Preview → Readiness

## Root Question

`production_trail10_exit` 已經完成回測與 default-off shadow 接入。接下來能不能一次完成「訊號品質檢查、推播預覽、上線前 readiness」三段，不再一張一張開卡？

這張是批次總卡。請依 checkpoint 連續執行，除非遇到 blocker，否則不要停下來等下一張卡。

## 前置結論

- production ranking 不動。
- `production_trail10_exit` 是目前最值得觀察的 tactics variant。
- trail10 shadow 已 default-off 接到 daily 旁路。
- shadow artifact 已能產出 `hold / trail_stop_zone / exit_triggered` 等狀態。
- 目前仍禁止改正式 Clawd live message。

## 請讀

- `docs/tasks/2026-06-10_PRODUCTION-TACTICS-01_exit_capital_warning_replay.md`
- `docs/tasks/2026-06-10_PRODUCTION-TACTICS-02_trail10_shadow_rollout.md`
- `scripts/build_production_tactics_replay.py`
- `scripts/verify_production_tactics_replay.py`
- `scripts/build_production_trail10_shadow.py`
- `scripts/verify_production_trail10_shadow.py`
- `scripts/run_daily.sh`
- `scripts/run_daily_publish.sh`

若上述 01/02 腳本尚未進 repo，請先不要猜；改讀 01/02 任務卡與現有 artifact，並在本批次 artifact 的 `input_gaps` 標示缺口。

## Batch Goal

一次做到這三個 checkpoint：

1. **03 Shadow Review**
   - 檢查 trail10 shadow 訊號是否合理。
   - 找出資料錯位、未來資料、過早 exit、狀態異常。

2. **04 Publish Preview**
   - 產生不發送的 Clawd / daily message preview。
   - 用白話說明 trail10 狀態，但不變成個人賣出指令。

3. **05 Rollout Readiness**
   - 判斷 trail10 shadow 是否可進下一階段：
     - 繼續 shadow
     - 放進 daily report
     - 做推播 dry-run
     - 仍不可出現在使用者可見訊息

## Checkpoint 03｜Shadow Review

### Scope

檢查最近可用的 trail10 shadow artifact，至少包含：

- 今天或最新交易日。
- 最近 5 個 trading days。
- 若資料可得，最近 20 個 trading days。

必檢項目：

- `run_date` 與輸入 ranking date 對齊。
- `trail_high` 不使用未來資料。
- 最低持有 5 日以前不得觸發 `exit_triggered`。
- `trail_stop_zone` 與 `exit_triggered` 有明確價格依據。
- `expired_or_removed` 不應吞掉仍在觀察期的股票。
- 同一股票同一日不得同時出現互斥狀態。

### Expected Outputs

- `artifacts/shadow/production_trail10/production_trail10_shadow_review_YYYY-MM-DD.json`
- `artifacts/shadow/production_trail10/production_trail10_shadow_review_YYYY-MM-DD.md`

### Decision

只能輸出：

- `SHADOW_SIGNAL_OK`
- `SHADOW_SIGNAL_MONITOR`
- `SHADOW_SIGNAL_BLOCKED`

## Checkpoint 04｜Publish Preview

### Scope

用 shadow review 結果產生不發送 preview。

Preview 必須拆成兩段：

1. 今日正式 Top10 推薦仍照 production ranking。
2. 近期觀察股 trail10 轉弱提醒。

允許說：

- 「進入轉弱觀察」
- 「接近 trail10 轉弱區」
- 「若已持有，請自行檢查」
- 「未進場者不要追」

禁止說：

- 「你應該賣出」
- 「賣幾成」
- 「停損價已到，立刻出場」
- 「正式持倉通知」

### Expected Outputs

- `artifacts/shadow/production_trail10/production_trail10_publish_preview_YYYY-MM-DD.json`
- `artifacts/shadow/production_trail10/production_trail10_publish_preview_YYYY-MM-DD.md`

### Decision

只能輸出：

- `PREVIEW_READY_FOR_REVIEW`
- `PREVIEW_NEEDS_COPY_FIX`
- `PREVIEW_BLOCKED`

## Checkpoint 05｜Rollout Readiness

### Scope

整合 03 / 04，判斷下一步。

不得直接批准 live send。

可選下一步：

- `KEEP_SHADOW_ONLY`
- `ADD_TO_DAILY_REPORT_DRY_RUN`
- `ADD_TO_PAGE_EXPLANATION_DRY_RUN`
- `ADD_TO_CLAWD_DRY_RUN_PREVIEW`
- `BLOCKED_BY_SIGNAL_QUALITY`
- `BLOCKED_BY_COPY_RISK`

### Expected Outputs

- `artifacts/shadow/production_trail10/production_trail10_rollout_readiness_YYYY-MM-DD.json`
- `artifacts/shadow/production_trail10/production_trail10_rollout_readiness_YYYY-MM-DD.md`
- `artifacts/shadow/production_trail10/production_trail10_batch_03_05_verification_latest.json`

## Suggested Scripts

可以拆三支，也可以做一支批次腳本。

建議：

- `scripts/build_production_trail10_shadow_review.py`
- `scripts/build_production_trail10_publish_preview.py`
- `scripts/build_production_trail10_rollout_readiness.py`
- `scripts/verify_production_trail10_batch_03_05.py`

若合併成一支：

- `scripts/run_production_trail10_batch_03_05.py`

Verifier 必須保留獨立腳本。

## Non-Goals

- 不改 `models/latest_lgbm.pkl`。
- 不改 production ranking score。
- 不改正式 Clawd live message。
- 不發 live message。
- 不把 preview 接成正式推播。
- 不做個人持倉管理。
- 不重新啟用 candidate ranking。
- 不測 partial take-profit runner。
- 不測 p12 / p15 capital variants。

## Acceptance Criteria

1. 03 / 04 / 05 三個 checkpoint 都有 artifact。
2. Verifier 會檢查三段 artifact 的日期、輸入、決策狀態一致。
3. Preview 沒有個人化賣出指令。
4. Shadow review 能擋未來資料與最低持有期違規。
5. Readiness 不得輸出 live production approval。
6. 即使 readiness 建議 dry-run，也只能是 dry-run，不可 live send。
7. 若 shadow 訊號品質不穩，04/05 必須降級，不得硬推 preview。

## Verification

最少要跑：

```bash
.venv/bin/python -m py_compile scripts/build_production_trail10_shadow_review.py scripts/build_production_trail10_publish_preview.py scripts/build_production_trail10_rollout_readiness.py scripts/verify_production_trail10_batch_03_05.py
.venv/bin/python scripts/build_production_trail10_shadow_review.py --date 2026-06-10
.venv/bin/python scripts/build_production_trail10_publish_preview.py --date 2026-06-10
.venv/bin/python scripts/build_production_trail10_rollout_readiness.py --date 2026-06-10
.venv/bin/python scripts/verify_production_trail10_batch_03_05.py --date 2026-06-10
git diff --check
```

如果選擇合併批次腳本，請改跑：

```bash
.venv/bin/python -m py_compile scripts/run_production_trail10_batch_03_05.py scripts/verify_production_trail10_batch_03_05.py
.venv/bin/python scripts/run_production_trail10_batch_03_05.py --date 2026-06-10
.venv/bin/python scripts/verify_production_trail10_batch_03_05.py --date 2026-06-10
git diff --check
```

## Final Report Must Answer

請用白話回答：

1. trail10 shadow 訊號品質是 OK、monitor，還是 blocked？
2. 今天哪些股票在 `trail_stop_zone` / `exit_triggered`，原因是什麼？
3. preview 文案是否能讓股市小白看懂？
4. preview 是否有誤導成個人賣出指令？
5. 下一步是繼續 shadow、進 daily report dry-run、頁面 dry-run，還是 Clawd dry-run preview？
6. 有沒有任何理由改正式排名、模型、或 live 推播？

## Dispatch Card

```text
任務ID：PRODUCTION-TACTICS-BATCH-03-05
卡片類型｜派工對象：Trail10 Shadow Review / Publish Preview / Rollout Readiness｜Codex
請讀：docs/tasks/2026-06-10_PRODUCTION-TACTICS-BATCH-03_05_trail10_shadow_review_to_readiness.md
任務目的：一次完成 trail10 shadow 訊號品質檢查、推播 dry-run preview、rollout readiness；不得改正式排名、模型或 live 推播
證據路徑：artifacts/shadow/production_trail10/production_trail10_*_2026-06-10.json、production_trail10_batch_03_05_verification_latest.json
```
