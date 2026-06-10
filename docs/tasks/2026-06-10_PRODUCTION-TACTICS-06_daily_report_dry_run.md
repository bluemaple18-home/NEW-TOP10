# PRODUCTION-TACTICS-06｜Trail10 Daily Report Dry-Run

## Root Question

`production_trail10_exit` 的 shadow 訊號品質已通過，publish preview 也沒有個人化賣出指令。下一步能不能先放進 daily report 的 dry-run 區塊，讓人每天檢查，但不進正式 Clawd live？

這張卡只做 daily report dry-run，不做正式上線。

## 前置結論

- `production_trail10_exit` 回測優於 baseline。
- trail10 shadow 已 default-off 接到 daily 旁路。
- 03/04/05 batch 結果：
  - shadow review: `SHADOW_SIGNAL_OK`
  - publish preview: `PREVIEW_READY_FOR_REVIEW`
  - rollout readiness: `ADD_TO_DAILY_REPORT_DRY_RUN`
- 仍不改正式排名、模型、Clawd live message。

## 請讀

- `docs/tasks/2026-06-10_PRODUCTION-TACTICS-01_exit_capital_warning_replay.md`
- `docs/tasks/2026-06-10_PRODUCTION-TACTICS-02_trail10_shadow_rollout.md`
- `docs/tasks/2026-06-10_PRODUCTION-TACTICS-BATCH-03_05_trail10_shadow_review_to_readiness.md`
- `scripts/build_production_trail10_shadow.py`
- `scripts/build_production_trail10_shadow_review.py`
- `scripts/build_production_trail10_publish_preview.py`
- `scripts/build_production_trail10_rollout_readiness.py`
- `scripts/verify_production_trail10_batch_03_05.py`
- `scripts/run_daily.sh`
- `scripts/run_daily_publish.sh`

若上述 03/04/05 腳本或 artifact 尚未進 repo，請不要猜；先標 `input_gaps`，並用批次卡回報結果作為前置結論。

## Scope

### A. Daily Report Dry-Run Section

新增 dry-run report section，不改正式 daily report 主內容。

建議新增 artifact：

- `artifacts/shadow/production_trail10/production_trail10_daily_report_dry_run_YYYY-MM-DD.json`
- `artifacts/shadow/production_trail10/production_trail10_daily_report_dry_run_YYYY-MM-DD.md`
- `artifacts/shadow/production_trail10/production_trail10_daily_report_dry_run_latest.json`

內容分三段：

1. **正式 Top10 仍照 production ranking**
   - 只說明本段沒有改排名。

2. **近期觀察股轉弱提醒**
   - 來自 `trail_stop_zone` / `exit_triggered`。
   - 用白話解釋原因。

3. **使用邊界**
   - 不是個人持倉賣出通知。
   - 未進場者不要追。
   - 已持有者自行檢查持倉。

### B. Copy Guard

日報 dry-run 文案要給股市小白看懂。

允許：

- 「接近轉弱區」
- 「近期走勢變弱」
- 「如果你本來就有持有，請自行檢查」
- 「還沒進場的人不要追」

禁止：

- 「你應該賣出」
- 「賣出幾成」
- 「正式停損通知」
- 「系統判定你要出場」
- 過度技術術語堆疊

### C. Daily Flow Boundary

如果接進 daily flow，必須 dry-run 且 default-off：

```bash
TOP10_ENABLE_PRODUCTION_TRAIL10_DAILY_REPORT_DRY_RUN=1
```

預設：

```bash
TOP10_ENABLE_PRODUCTION_TRAIL10_DAILY_REPORT_DRY_RUN=0
```

要求：

- dry-run 失敗不得阻斷 daily 主流程。
- dry-run 不得改 `daily_report_YYYY-MM-DD.json/md` 正式輸出。
- dry-run 不得改 Clawd payload。
- dry-run 不得 live send。
- 失敗要寫 artifact 或 log，不可靜默吞掉。

### D. Report Source Contract

dry-run 必須使用既有 shadow artifacts：

- `production_trail10_shadow_YYYY-MM-DD.json`
- `production_trail10_shadow_review_YYYY-MM-DD.json`
- `production_trail10_publish_preview_YYYY-MM-DD.json`
- `production_trail10_rollout_readiness_YYYY-MM-DD.json`

若缺任何一份：

- 不得 fallback 到猜測。
- 輸出 `DRY_RUN_BLOCKED_INPUT_MISSING`。
- 明確列出缺哪份。

## Non-Goals

- 不改 `models/latest_lgbm.pkl`。
- 不改 production ranking score。
- 不改正式 daily report。
- 不改正式 Clawd payload。
- 不發 live message。
- 不把 dry-run 文案接到使用者可見正式訊息。
- 不做個人持倉管理。
- 不重新啟用 candidate ranking。

## Expected Outputs

建議新增：

- `scripts/build_production_trail10_daily_report_dry_run.py`
- `scripts/verify_production_trail10_daily_report_dry_run.py`

若接 daily flow，可小心修改：

- `scripts/run_daily.sh`

建議輸出：

- `artifacts/shadow/production_trail10/production_trail10_daily_report_dry_run_YYYY-MM-DD.json`
- `artifacts/shadow/production_trail10/production_trail10_daily_report_dry_run_YYYY-MM-DD.md`
- `artifacts/shadow/production_trail10/production_trail10_daily_report_dry_run_verification_latest.json`

Artifact 至少包含：

- `schema_version`
- `run_date`
- `contract`
- `inputs`
- `report_sections`
- `copy_guard`
- `trail10_summary`
- `blocked_reasons`
- `decision`
- `next_recommended_action`

## Decision States

只能輸出：

- `DAILY_REPORT_DRY_RUN_READY`
- `DAILY_REPORT_DRY_RUN_NEEDS_COPY_FIX`
- `DRY_RUN_BLOCKED_INPUT_MISSING`
- `DRY_RUN_BLOCKED_SIGNAL_QUALITY`

## Acceptance Criteria

1. dry-run artifact 可重跑、可驗證。
2. 不改正式 daily report。
3. 不改 Clawd payload / live message。
4. 文案沒有個人化賣出指令。
5. 缺 input 時 fail loud，不猜、不 fallback 舊資料。
6. 若接 `run_daily.sh`，預設 off，且失敗不阻斷 daily 主流程。
7. report 明確標示「這是 trail10 shadow dry-run，不是正式持倉通知」。

## Verification

最少要跑：

```bash
.venv/bin/python -m py_compile scripts/build_production_trail10_daily_report_dry_run.py scripts/verify_production_trail10_daily_report_dry_run.py
.venv/bin/python scripts/build_production_trail10_daily_report_dry_run.py --date 2026-06-10
.venv/bin/python scripts/verify_production_trail10_daily_report_dry_run.py --artifact artifacts/shadow/production_trail10/production_trail10_daily_report_dry_run_2026-06-10.json
git diff --check
```

若修改 `scripts/run_daily.sh`，還要跑：

```bash
bash -n scripts/run_daily.sh
TOP10_ENABLE_PRODUCTION_TRAIL10_DAILY_REPORT_DRY_RUN=0 bash scripts/run_daily.sh
TOP10_ENABLE_PRODUCTION_TRAIL10_DAILY_REPORT_DRY_RUN=1 bash scripts/run_daily.sh
```

若完整 daily 會重跑 ETL 或成本太高，可以用 fixture/smoke 取代，但必須在結果中明確說明沒有跑完整 daily。

Verifier 必須擋：

- `changes_official_daily_report=true`
- `changes_clawd_payload=true`
- `changes_clawd_live_message=true`
- `changes_production_ranking=true`
- `personalized_sell_instruction=true`
- `uses_stale_fallback=true`

## Final Report Must Answer

請用白話回答：

1. daily report dry-run 有沒有產出？
2. 它有沒有改正式 daily report？
3. 它有沒有改 Clawd payload / live message？
4. 文案是否小白看得懂？
5. 有沒有任何句子像個人賣出指令？
6. 下一步是繼續 dry-run、進正式 daily report、還是 Clawd dry-run preview？

## Dispatch Card

```text
任務ID：PRODUCTION-TACTICS-06
卡片類型｜派工對象：Trail10 Daily Report Dry-Run｜Codex
請讀：docs/tasks/2026-06-10_PRODUCTION-TACTICS-06_daily_report_dry_run.md
任務目的：把 trail10 shadow 狀態加入 daily report dry-run artifact，不改正式日報、不改 Clawd payload、不 live send
證據路徑：artifacts/shadow/production_trail10/production_trail10_daily_report_dry_run_*.json、production_trail10_daily_report_dry_run_verification_latest.json
```
