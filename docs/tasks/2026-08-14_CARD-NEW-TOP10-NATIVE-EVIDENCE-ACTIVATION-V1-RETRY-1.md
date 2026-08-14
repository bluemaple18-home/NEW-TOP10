---
id: CARD-NEW-TOP10-NATIVE-EVIDENCE-ACTIVATION-V1-RETRY-1
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
model_reason: 修復原 Reviewer reservation 的 role-card mismatch，沿用唯一 Reviewer slot 反證 Checkpoint 1。
date: 2026-08-14
production_change_allowed: false
live_activation_allowed: false
---

# Native Evidence Activation Checkpoint 1 Reviewer Retry 1

## 原因

原 reservation 誤用 implementation 實體卡，因此在 create 前 fail-closed。
本卡只修復 dispatch identity；不重跑 implementation、不建立第二個 Reviewer chain。

## 審查對象

- Source：`529ecadd694cf39b0a06938cee97ca08ec268734`
- Candidate：`52b1daf894edd4a159abb46641b4b7a339f5f5b0`
- 範圍：NEA-SLICE-000／001

## 必查

- canonical Research Spine／CAS／ledger 測試隔離與 immutable quarantine。
- capacity floor、UNKNOWN、bool 與 policy downgrade fail-closed。
- baseline write-set、containment、symlink、hash 與 causal provenance。
- development/coarse-only execution plan 與 batch/intent/run/policy/script/argv binding。
- 僅允許 `PREFLIGHT_ONLY`／`ISOLATED_TEST_ALLOWED`。
- queue、daily、scheduler、live canary、production 零變更。

## Reviewer 邊界

唯讀審查與測試。不得修檔、commit、push、merge 或建立 replacement。
回報 `GO` 或 `NO-GO`，所有缺口需附可重現反例。
