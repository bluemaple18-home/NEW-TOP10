# PRODUCTION-TACTICS-07｜Trail10 Daily Report Dry-Run Review Loop

## Root Question

`production_trail10_daily_report_dry_run` 已經可產出且 verifier 通過。下一步要建立一個連續 review loop，判斷它是否穩定到可以進正式 daily report。

這張卡不是正式上線卡。它只建立 review loop 與升級判定。

## 前置結論

- `production_trail10_exit` 回測優於 baseline。
- trail10 shadow 訊號品質：`SHADOW_SIGNAL_OK`。
- publish preview：`PREVIEW_READY_FOR_REVIEW`。
- rollout readiness：`ADD_TO_DAILY_REPORT_DRY_RUN`。
- daily report dry-run：`DAILY_REPORT_DRY_RUN_READY`。
- 仍不改正式 daily report、Clawd payload、Clawd live message、production ranking、模型。

## 請讀

- `docs/tasks/2026-06-10_PRODUCTION-TACTICS-06_daily_report_dry_run.md`
- `docs/tasks/2026-06-10_PRODUCTION-TACTICS-BATCH-03_05_trail10_shadow_review_to_readiness.md`
- `scripts/build_production_trail10_daily_report_dry_run.py`
- `scripts/verify_production_trail10_daily_report_dry_run.py`
- `scripts/build_production_trail10_shadow.py`
- `scripts/verify_production_trail10_shadow.py`
- `scripts/run_daily.sh`
- `scripts/run_daily_publish.sh`

若 06 腳本或 artifact 尚未進 repo，請不要猜；標 `input_gaps`，並使用任務回報中的 06 結論作為前置狀態。

## Scope

### A. Review Loop Artifact

新增 review loop artifact，整理最近可用 dry-run 結果。

建議輸出：

- `artifacts/shadow/production_trail10/production_trail10_daily_report_review_loop_YYYY-MM-DD.json`
- `artifacts/shadow/production_trail10/production_trail10_daily_report_review_loop_YYYY-MM-DD.md`
- `artifacts/shadow/production_trail10/production_trail10_daily_report_review_loop_latest.json`

Artifact 至少包含：

- `schema_version`
- `run_date`
- `contract`
- `input_artifacts`
- `review_window`
- `daily_results`
- `signal_quality_summary`
- `copy_quality_summary`
- `user_visible_risk_summary`
- `decision`
- `blocked_reasons`
- `next_recommended_action`

### B. Review Window

優先使用最近可得 trading days。

建議規格：

- minimum useful window：3 trading days。
- preferred window：5 trading days。
- extended window：20 trading days。

如果目前只有 1 天資料：

- 不得硬判定可正式上線。
- decision 應為 `CONTINUE_DRY_RUN_REVIEW_LOOP`。
- artifact 要明確寫 `insufficient_review_days`。

### C. Review Checks

每天至少檢查：

- dry-run artifact 是否存在。
- shadow review 是否 `SHADOW_SIGNAL_OK` 或可接受 monitor。
- copy guard 是否通過。
- 是否有個人化賣出指令。
- 是否誤導成正式持倉通知。
- 是否改到正式 daily report。
- 是否改到 Clawd payload / live message。
- `trail_stop_zone` / `exit_triggered` 是否有清楚原因。
- 文字是否能給股市小白理解。

### D. Decision States

只能輸出：

- `CONTINUE_DRY_RUN_REVIEW_LOOP`
- `READY_FOR_OFFICIAL_DAILY_REPORT_REVIEW`
- `BLOCKED_BY_COPY_RISK`
- `BLOCKED_BY_SIGNAL_QUALITY`
- `BLOCKED_BY_INPUT_GAPS`

不得輸出 live send approval。

### E. Promotion Criteria

只有同時滿足以下條件，才能輸出 `READY_FOR_OFFICIAL_DAILY_REPORT_REVIEW`：

- 至少 3 個可檢查 trading days。
- 每天 copy guard 通過。
- 沒有個人化賣出指令。
- 沒有改正式 daily report。
- 沒有改 Clawd payload / live message。
- shadow review 無 blocker。
- 所有 `trail_stop_zone` / `exit_triggered` 都有價格或規則依據。

即使達成，也只能進「正式 daily report review」，不能直接正式上線。

## Non-Goals

- 不改 `models/latest_lgbm.pkl`。
- 不改 production ranking score。
- 不改正式 daily report。
- 不改 Clawd payload / live message。
- 不 live send。
- 不做個人持倉管理。
- 不把 review loop 結果直接寫入正式日報。

## Expected Outputs

建議新增：

- `scripts/build_production_trail10_daily_report_review_loop.py`
- `scripts/verify_production_trail10_daily_report_review_loop.py`

建議輸出：

- `artifacts/shadow/production_trail10/production_trail10_daily_report_review_loop_YYYY-MM-DD.json`
- `artifacts/shadow/production_trail10/production_trail10_daily_report_review_loop_YYYY-MM-DD.md`
- `artifacts/shadow/production_trail10/production_trail10_daily_report_review_loop_verification_latest.json`

## Acceptance Criteria

1. Review loop artifact 可重跑、可驗證。
2. 不改正式 daily report。
3. 不改 Clawd payload / live message。
4. 不輸出 live send approval。
5. 不足 3 天資料時，不得宣稱 ready。
6. Verifier 會擋個人化賣出指令與 stale fallback。
7. Verifier 會擋 `changes_official_daily_report=true`。
8. Verifier 會擋 `changes_clawd_payload=true` / `changes_clawd_live_message=true`。

## Verification

最少要跑：

```bash
.venv/bin/python -m py_compile scripts/build_production_trail10_daily_report_review_loop.py scripts/verify_production_trail10_daily_report_review_loop.py
.venv/bin/python scripts/build_production_trail10_daily_report_review_loop.py --date 2026-06-10
.venv/bin/python scripts/verify_production_trail10_daily_report_review_loop.py --artifact artifacts/shadow/production_trail10/production_trail10_daily_report_review_loop_2026-06-10.json
git diff --check
```

Verifier 必須擋：

- `ready` with fewer than 3 review days
- `personalized_sell_instruction=true`
- `changes_official_daily_report=true`
- `changes_clawd_payload=true`
- `changes_clawd_live_message=true`
- `uses_stale_fallback=true`
- `live_send_approved=true`

## Final Report Must Answer

請用白話回答：

1. review loop 看了幾天？
2. 目前是繼續 dry-run，還是可進正式 daily report review？
3. 有沒有任何文案像個人賣出指令？
4. 有沒有任何訊號品質 blocker？
5. 有沒有改正式 daily report 或 Clawd？
6. 下一步是繼續累積，還是開正式 daily report review 卡？

## Dispatch Card

```text
任務ID：PRODUCTION-TACTICS-07
卡片類型｜派工對象：Trail10 Daily Report Dry-Run Review Loop｜Codex
請讀：docs/tasks/2026-06-10_PRODUCTION-TACTICS-07_daily_report_dry_run_review_loop.md
任務目的：建立 trail10 daily report dry-run 連續 review loop 與升級判定；不足 3 天不得進正式 review，不得 live send
證據路徑：artifacts/shadow/production_trail10/production_trail10_daily_report_review_loop_*.json、production_trail10_daily_report_review_loop_verification_latest.json
```
