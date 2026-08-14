---
id: CARD-NEW-TOP10-CANONICAL-BATCH-OWNER-SCHEDULER-AUTHORITY-REPAIR-1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: repair
priority: P1
owner: TOP10new research platform
role: repair
cycle: 1
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
date: 2026-08-14
production_change_allowed: false
live_activation_allowed: false
---

# Canonical Batch Owner Scheduler Authority Repair 1

## 工作名稱

鎖死唯一 daily research scheduler owner。

## 固定輸入

- Base：`dc6a157f8fef148bcf076c74e708f7fa94aaef13`
- Rejected candidate：`5df1fce0ef7426e804a9b0c6cc819b18cf51f3c3`
- Reviewer task：`019fff37-cb09-7403-bf98-332c37eeb8c5`
- Verdict：`NO-GO`
- Finding：`P1-FORGED-BATCH-INTENT-SCHEDULER-OWNER`

## 問題

目前 Batch Intent 已能驗證 identity、hash、argv、execution epoch、stage 與 write paths，但 publisher CLI 允許 caller 自選 `--scheduler`。Runner verifier 也沒有將下列事實綁定至唯一 canonical daily owner：

- `scheduler.owner = daily_research_quota`
- `scheduler.entrypoint = scripts/run_daily_research_quota.sh`
- `scheduler.entrypoint_hash = current canonical shell hash`

因此任意 caller 可以用其他 entrypoint 產生結構合法、hash 正確的 intent，自行取得 canonical native-spine write authority。

## 修復切片

### `BATCH-OWNER-REPAIR-001`｜先鎖反例

`traces_to`: `BATCH-OWNER-FR-002`, `BATCH-OWNER-FR-003`, `BATCH-OWNER-FR-004`

先加入 public-interface 測試：

1. Intent 其他欄位、hash、argv、epoch全部有效，但 scheduler entrypoint 為 runner，本次必須 fail closed。
2. Scheduler owner 錯誤、entrypoint path 錯誤、entrypoint hash stale，分別 fail closed。
3. Publisher CLI 不得讓 caller 以公開參數選擇任意 scheduler。
4. 拒絕必須發生在 runner body、Research Spine、manager、ledger write 之前。

### `BATCH-OWNER-REPAIR-002`｜Canonical scheduler authority

`traces_to`: `BATCH-OWNER-FR-002`, `BATCH-OWNER-FR-003`

- Canonical owner identity由單一程式常數／契約產生，不由 caller 輸入。
- Publisher 固定使用 `<repo-root>/scripts/run_daily_research_quota.sh`。
- Runner 以目前 repo 中 canonical shell bytes重算 hash並比對 Intent。
- Path 必須 resolve 到 repo 內 exact canonical entrypoint；symlink、`..`、alternate path、missing file、hash mismatch全部 fail closed。
- Intent content hash與immutable path/body identity規則保持不變。

### `BATCH-OWNER-REPAIR-003`｜Compatibility gate

`traces_to`: `BATCH-OWNER-FR-004`, `BATCH-OWNER-FR-005`, `BATCH-OWNER-FR-006`

- `scripts/run_daily_research_quota.sh` 仍是唯一 scheduler。
- 不改 runner selection、topic order、quota、rerun/cooldown、development cap。
- Publisher failure仍保證 runner call count為0並保留原 exit code。
- 完整 isolated write-set相容性保留；任何 canonical/partial/symlink write-set仍 fail closed。
- 不改 ranking、model、signals、strategy config、promotion。

## Blocking edges 與 frontier

- Frontier：`BATCH-OWNER-REPAIR-001` 可立即開始。
- `REPAIR-002` blocked by `REPAIR-001` RED evidence。
- `REPAIR-003` blocked by `REPAIR-002` GREEN。
- 本卡完成前禁止 integration、live canary、daily activation或 Adaptive Queue。

## Required verification

```bash
uv run pytest -q tests/test_research_batch_owner.py tests/test_daily_research_batch_owner_shell.py
uv run pytest -q tests/test_autonomous_research_receipts.py tests/test_research_spine_daily_cutover.py
uv run python -m py_compile app/research/batch_owner.py scripts/publish_research_batch_intent.py scripts/run_autonomous_research.py
bash -n scripts/run_daily_research_quota.sh
git diff --check
```

若 `tests/test_native_evidence_activation.py` 仍因 untracked runtime artifact 缺失失敗，必須提供 base/candidate 同樣失敗證據並標 `PRE-EXISTING`；不得用補造正式 artifact 掩蓋。

## Acceptance

- Forged scheduler intent 100% fail closed。
- Canonical daily shell intent通過。
- Publisher CLI 無任意 scheduler authoring surface。
- 拒絕發生於任何 canonical write前。
- Existing daily shell、isolated fixture與Research Spine receipt regression通過。
- Production-sensitive path diff為0。
- Candidate commit完成但不得 merge、push、deploy。
- 最後回原 Reviewer task做同一 finding re-review。

## Rollback

捨棄 Repair candidate，保留 rejected candidate branch與 immutable reviewer evidence；不修改正式 corpus、ledger或scheduler部署狀態。
