---
id: CARD-NEW-TOP10-CANONICAL-RESEARCH-BATCH-OWNER-CONTRACT-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: architecture_contract
priority: P1
owner: TOP10new research platform
role: implementer
cycle: 1
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: Batch owner 涉及 scheduler、runner 與 immutable research spine 的跨程序 authority，需先鎖 strict contract。
date: 2026-08-14
production_change_allowed: false
live_activation_allowed: false
---

# Canonical Research Batch Owner Contract V1

## 工作名稱

建立不可偽造的 daily research batch owner authority。

## 背景

Native Evidence Activation Checkpoint 1 已完成 capacity fail-closed，但 runner owner gate 經兩輪 Repair 後仍有同一 P1：

- `UNSCOPED` direct execute 已拒絕。
- 但任何 caller 只要提供符合 `research-YYYY-MM-DD-HHMMSS-PID` 的字串，就能被 `_valid_research_batch_owner()` 視為 daily owner。
- Batch ID 格式是 identity syntax，不是 execution authority。

依「同一 blocker 第三次失敗即停」規則，禁止再做 Repair-3 條件補丁。本卡建立缺失的 canonical owner contract。

## 固定輸入

- Rejected candidate：`36ba6fed9d4a28b8be5b874db1dfbd81eb7ba2e6`
- Parent candidate：`ceb6b7bfc87087d38f38be5c53b3938fd4da35d5`
- Reviewer thread：`019fff37-cb09-7403-bf98-332c37eeb8c5`
- Finding：`NEA-P1-RUNNER-PLAN-BYPASS`
- Reviewer verdict：`NO-GO`

## 核心契約

### `BATCH-OWNER-FR-001`｜Identity 不等於 Authority

- Batch ID regex 只能驗格式。
- Runner 不得因 batch ID 看起來合法就授權 canonical native-spine write。

### `BATCH-OWNER-FR-002`｜Pre-launch Immutable Batch Intent

Daily scheduler 在啟動 runner 前，必須 exclusive-create 一份 immutable Batch Intent，至少包含：

- `batch_id`
- scheduler owner / entrypoint identity
- exact runner argv hash
- project / repo identity
- requested research stage 與 allowed stage set
- output root、spine root、ledger path
- catalog / policy version與hash
- created_at、execution epoch
- `does_not_train_model=true`
- `does_not_change_production_ranking=true`
- `production_promotion_allowed=false`

Intent identity 必須由 canonical content hash產生；路徑與 body identity 必須一致。相同 identity／相同 bytes 可 idempotent；不同 bytes 必須 collision/fail closed。

### `BATCH-OWNER-FR-003`｜Runner Independent Verification

Runner 必須自行驗證：

- Batch Intent 存在於可信 canonical corpus。
- content hash、schema、path containment、repo identity、argv hash、execution epoch均一致。
- `batch_id` 與 caller claim一致。
- canonical native roots只有在 authority驗證成功後才可寫入。

缺失、stale、mismatch、symlink escape、partial env override或未知 authority一律在 main body／subprocess／receipt write前 fail closed。

### `BATCH-OWNER-FR-004`｜Existing Daily Owner Compatibility

- 唯一 scheduler仍為 `scripts/run_daily_research_quota.sh`。
- 不建立第二 scheduler／launchd。
- Daily shell只新增 pre-launch intent publication與exact reference傳遞，不改 queue、topic ordering、quota、rerun/cooldown或 development cap。
- Runner exception仍依既有 batch receipt／ledger流程處理；不得吞掉原 exit status。

### `BATCH-OWNER-FR-005`｜Isolation Compatibility

- 測試與手動 fixture只有在 output、spine、ledger、manager/history等完整 write-set都 resolve 到隔離 root時可無 canonical Batch Intent 執行。
- 任一 target落回 canonical root即 fail closed。
- Symlink、`..`、relative-path escape不得視為隔離。

## Frontier Slices

### `BATCH-OWNER-SLICE-001`｜Schema 與 Immutable Store

- 先新增 strict Batch Intent schema與validator。
- 使用既有 immutable writer／exclusive-create，不建立第二套 generic store。
- 補 canonical ID、collision、path/body mismatch、symlink與stale epoch測試。

### `BATCH-OWNER-SLICE-002`｜Daily Publisher

- 在 existing daily shell呼叫 runner前publish intent。
- Intent publication失敗時 runner subprocess call count必須為0。
- 保留 scheduler、selection、quota與exit-code相容。

### `BATCH-OWNER-SLICE-003`｜Runner Verifier

- 以 intent reference＋hash驗證 owner authority。
- 移除／禁止 regex-only owner authorization。
- 驗證發生於任何 canonical write前。

### `BATCH-OWNER-SLICE-004`｜Adversarial Compatibility Gate

- forged valid-looking batch ID：FAIL。
- copied/stale intent：FAIL。
- intent argv／root／epoch mismatch：FAIL。
- partial env、symlink、path traversal：FAIL。
- exact daily owner：PASS。
- isolated complete write-set：PASS。

## 允許修改

- `app/research/` 內既有 research-spine contract／immutable writer直接相關檔案
- `scripts/run_daily_research_quota.sh`
- `scripts/run_autonomous_research.py`
- 對應 targeted tests
- 本卡 versioned evidence

## 禁止事項

- 不動 ai-core。
- 不建立第二 scheduler、launchd、Universe、Fog Map、queue或ledger。
- 不改 queue selection、priority、quota、rerun/cooldown。
- 不執行 live research、sealed research或 production canary。
- 不改 ranking、LightGBM、signals、production config或promotion。
- 不刪改既有 immutable receipts、attempts、intents或CAS。
- 不進 Card B、Adaptive Queue、Optuna或dynamic refinement。

## Required Tests

1. regex-valid forged batch ID無 intent：FAIL。
2. malformed／missing／stale／collision intent：FAIL。
3. batch ID、argv、repo、epoch、stage、root任一 mismatch：FAIL。
4. symlink／relative traversal／partial canonical root：FAIL。
5. intent publish失敗時 runner未啟動。
6. exact daily batch owner可執行既有流程。
7. isolated complete write-set可執行且 canonical corpus inventory/hash不變。
8. queue/order/quota/rerun/scheduler parity。
9. production guard pre/post hash不變。
10. targeted tests與 `git diff --check`。

## GO Gate

- Canonical write authorization不能由任何 caller自述字串取得。
- Daily Batch Intent可從 scheduler publish一路驗到 runner，requested／executed authority一致。
- Reviewer原 forged-batch repro fail closed。
- Existing daily與isolated tests相容。
- Reviewer回 `GO` 前不得合併、live activation或開 Card B。

## Rollback

- 本卡未接 live前可整體停用。
- 若後續 integration異常，runner拒絕 canonical native write並保留既有非 adaptive queue流程；不得以 regex fallback。
