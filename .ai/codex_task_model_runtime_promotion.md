---
id: MODEL-PROMOTE-07
status: completed
type: production-promotion
priority: P0
model: gpt-5.6-sol
---

# sklearn runtime migration candidate 原子 promotion

## 目標

建立可測試、可回滾的薄 promotion 工具。主線整合後，才把已通過等價與真資料 shadow gate 的 runtime migration candidate 原子替換為 `models/latest_lgbm.pkl`，並證明現行每日報牌仍可載入、排名結果不變。

## 已鎖定前提

- source model SHA-256：`76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675`。
- candidate SHA-256：`ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`。
- `artifacts/shadow/model_runtime_migration/verdict.json` 為 `GO`，candidate reload 無 sklearn version warning。
- `artifacts/shadow/daily_v2/daily-v2-20260709-candidate-v3/comparison.json` 為 `GO`，production-switch gate 為 `GO`。
- Top10 10／10、順序完全一致，8 個核心分數最大 absolute difference 均為 `0.0`。

## 本派工實作範圍

- 新增 `app/modeling/model_runtime_promotion.py` 或等價最小模組。
- 新增 `scripts/promote_model_runtime_candidate.py` 薄 CLI。
- 新增 fixture tests。
- 只回寫本卡結果。

worktree 不得建立真 candidate 或替換正式模型；只做工具與 fixture tests。主線整合後負責唯一一次真 promotion。

## promotion 契約

- 預設只接受 `artifacts/shadow/model_runtime_migration/` 下的 candidate 與 verdict。
- promotion 前必須重驗 verdict `GO`、source/candidate SHA、`shadow_only=true`、candidate warning count=0、所有 equivalence flags 與 calibrator tolerance。
- 正式模型當下 SHA 必須仍等於 verdict 的 source SHA；stale source 一律 fail-loud。
- 先備份正式模型到 `models/backup/`，驗證 backup SHA 與 source 相同。
- candidate 先複製到 `models/` 同 filesystem 的 temporary file，flush／fsync 後以 `os.replace` 原子替換，再驗證正式檔 SHA、可載入且無 `InconsistentVersionWarning`。
- 任一替換後驗證失敗，必須以 backup 原子 rollback，驗證正式 SHA 已恢復；exit code 非 0。
- 產出 promotion JSON，至少記錄 before／candidate／backup／after／rollback snapshots、verdict 與 executed 狀態。
- 已存在的 backup 或 report 不得靜默覆寫；不得修改 `models/baseline_stats.json`，因本次模型內容、features、metadata 均等價。

## 必跑 fixture tests

- 正常 promotion：backup 正確、正式 SHA 變成 candidate、report 為 `GO`。
- stale source、壞 candidate hash、非 GO verdict、warning／equivalence gate 失敗時，正式模型不變。
- 模擬替換後驗證失敗：自動 rollback，正式 SHA 恢復，report 明示 `ROLLED_BACK`。
- 輸出路徑逃逸、覆寫既有 backup／report必須被拒絕。
- `git diff --check` 與 diff 範圍檢查。

## 主線真實驗收

- 整合後才執行真 promotion；不 reload launchd、不改 daily scripts/config/plist、不發送通知。
- 使用 production model path 重跑 2026-07-09 real shadow，輸出新的獨立 run id。
- comparison 與 production-switch gate 必須都是 `GO`；Top10、順序、核心分數保持完全一致，model warning 為 0。
- 跑現有 `.venv/bin/python -m unittest discover -s tests -p 'test_*.py'`、`git diff --check`。
- 任一真實驗收失敗立刻 rollback，不進行第二次盲目 promotion。

## 回報

- 變更檔案、測試、殘餘風險與主線精確執行指令。
- 不 commit、不 merge、不 push；由主線 review 後收 commit。

## Result

- promotion 工具整合 commit：`7f4359d`。
- 真實 promotion report：`artifacts/model_runtime_promotion/promotion.json`，`status=GO`、`executed=true`、`rollback=null`。
- before SHA-256：`76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675`。
- after／candidate SHA-256：`ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`；loadable、warning count 0。
- rollback backup：`models/backup/latest_lgbm.pre-runtime-migration.pkl`，SHA 與 before 完全一致。
- post-promotion real shadow：`artifacts/shadow/daily_v2/daily-v2-20260709-post-promotion-v4/`。
- comparison 與 production-switch gate 均為 `GO`；Top10 10／10、順序完全一致、8 個核心分數最大 absolute difference 均為 `0.0`。
- canonical checkout 全套 119 tests 通過（1 skipped）；`git diff --check` 通過。
- daily scripts、publish script、launchd plist、automation config、features 與 baseline ranking 的 hash／mtime 不變；未 reload launchd、未發送通知。
