---
id: ENV-06
status: completed
type: compatibility
priority: P0
model: gpt-5.6-sol
---

# sklearn 1.8→1.9 模型 runtime migration candidate

## 目標

在不覆蓋 `models/latest_lgbm.pkl`、不改正式 `.venv` 的前提下，建立可重現的 runtime migration candidate 與等價證據，消除 `InconsistentVersionWarning`。

## 方法邊界

- 載入正式模型時捕捉 1.8→1.9 warning；只在指定 shadow output 重新序列化 candidate。
- candidate 必須在目前 Python 3.12／sklearn 1.9 runtime 下重新載入且不產生 `InconsistentVersionWarning`。
- 原模型與 candidate 的 LightGBM model string／feature names 必須完全一致。
- calibrator 對 deterministic probability grid（至少 1001 點）的輸出最大差異必須 `<=1e-12`。
- model dict metadata／feature names／horizon 等契約不得遺失。
- 產出 source/candidate SHA-256、runtime versions、warning、equivalence metrics 與 verdict JSON。

## 可改範圍

- 新增 `app/modeling/model_runtime_migration.py` 或等價最小模組。
- 新增 `scripts/build_model_runtime_migration_candidate.py` 薄 CLI。
- 新增對應 fixture tests。
- 本卡 status／result。

## 不可改範圍

- `models/latest_lgbm.pkl`、任何正式 model symlink／latest pointer。
- `pyproject.toml`、`uv.lock`、canonical `.venv`。
- ranking、daily、notify、launchd、features、正式 artifacts。
- 不得把 candidate 宣稱為 production model；promotion 另開 rollout 卡。

## 主線驗收

- fixture 測試需涵蓋 warning capture、candidate reload、模型／calibrator 等價、output path isolation、拒絕覆蓋 source。
- 主線只在 `artifacts/shadow/model_runtime_migration/` 建 candidate。
- candidate 完成後，以 real shadow adapter 指向 candidate model-dir 重跑 `2026-07-09`；Top10、順序、核心分數必須與正式 baseline 完全一致。
- production inputs 與 live daily 控制檔 hash／mtime 不變。
- `git diff --check` 通過；不 commit、不 merge、不 push。

## Result

- migration verdict：`artifacts/shadow/model_runtime_migration/verdict.json`，狀態 `GO`。
- source SHA-256：`76f530f6491f996f4838500acacbde40a10c90f43116cec0dcc69fb6b4935675`，hash／mtime 不變。
- candidate SHA-256：`ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`，僅位於 shadow。
- source warning 1、candidate reload warning 0；LightGBM model string、feature names、metadata、horizon 完全相同。
- calibrator 1001 點最大 absolute difference `0.0`（tolerance `1e-12`）。
- candidate 真資料 shadow：`artifacts/shadow/daily_v2/daily-v2-20260709-candidate-v3/`，comparison 與 production-switch gate 皆為 `GO`。
- 5 個 migration fixture tests 與整套 109 tests 通過（1 skipped）；整合 commit：`836288c`。
