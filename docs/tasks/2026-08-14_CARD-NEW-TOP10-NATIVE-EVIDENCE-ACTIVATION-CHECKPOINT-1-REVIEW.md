---
id: CARD-NEW-TOP10-NATIVE-EVIDENCE-ACTIVATION-CHECKPOINT-1-REVIEW
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: code-review
priority: P1
owner: TOP10new research platform
role: reviewer
cycle: 0
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: 獨立反證 immutable corpus、capacity fail-closed 與 execution-plan authority。
date: 2026-08-14
production_change_allowed: false
live_activation_allowed: false
---

# Native Evidence Activation Checkpoint 1 Review

## 審查目標

獨立審查 candidate `52b1daf894edd4a159abb46641b4b7a339f5f5b0` 相對來源
`529ecadd694cf39b0a06938cee97ca08ec268734` 的 NEA-SLICE-000/001。

## 必查契約

- 測試不得改寫 canonical Research Spine 任一 immutable entity、CAS 或 ledger。
- 既有污染只能版本化 quarantine，不得刪除或改寫。
- capacity policy 拒絕 bool、UNKNOWN、可下調的 20 GiB／10% floor。
- baseline lock 必須驗完整 write-set、resolved containment、symlink、exists、hash 與 pre-activation provenance。
- execution plan 只允許 development/coarse isolated checkpoint；拒絕 sealed、UNKNOWN、UNSCOPED 與 authority mismatch。
- 本 checkpoint 最多授權 `PREFLIGHT_ONLY`／`ISOLATED_TEST_ALLOWED`。
- queue、scheduler、daily、live canary、production 必須零變更。

## 驗收

- 先做 source-context impact 查詢。
- 重跑 targeted 與相關回歸。
- 必須加入或執行反例，不接受只讀既有測試結果。
- 檢查 candidate diff、evidence receipt、`git diff --check`。
- 只回報 `GO` 或 `NO-GO` 與可重現證據。
- Reviewer 不得修檔、commit、push 或建立 replacement。
