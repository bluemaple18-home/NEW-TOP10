---
id: REVIEW-NEW-TOP10-STORAGE-GUARD-METER-CANONICALIZATION
status: GO
type: review
risk: high
candidate: c9ff889497fa7bbfa8b827cbf5d0e0542df77291
base: baf003432fd96e07b834905fa4edf78245dcd57d
model_lane: gpt-5.5-high
chain_id: FOG-CADENCE-METER-CANONICALIZATION
---

# 獨立審查 Fog storage meter canonicalization 修復

## 五行派工卡

- 目標：獨立 review `baf0034..c9ff889`，判定是否可進 Mainline 整合。
- 範圍：候選 diff、repair 卡、`measure_paths()` 與直接相關 tests；必要時查 CodeGraph 與執行唯讀測試。
- 禁區：Review-only；不得修改 code／docs、不得 commit、不得清 restart-denied、不得操作 launchd、不得重跑 live workload、push 或 deploy。
- 驗收：分開 spec／standards 軸；檢查 overlapping roots、不同順序、symlink、canonical-root relative identity、missing/file meter path、Python 相容性、效能測試是否真正防止 O(files) resolve，並核對 60s／95%／容量門檻未變。
- 交付：findings 依 P0–P3，必含 path:line、觸發條件、風險、建議修法、validation gap、confidence；只有 P0/P1 阻塞，無阻塞問題時仍列剩餘風險與缺口。

## 固定證據

- Repair 卡：`docs/tasks/2026-09-03_REPAIR-NEW-TOP10-STORAGE-GUARD-METER-CANONICALIZATION.md`。
- Candidate：`c9ff889497fa7bbfa8b827cbf5d0e0542df77291`，parent 必須為 `baf003432fd96e07b834905fa4edf78245dcd57d`。
- Worker 回報 RED：100 regular files／重疊 roots 在舊實作觸發 150 次逐檔 `Path.resolve()`。
- Worker 回報 GREEN：完整 `tests/test_storage_safety.py` 為 `66 passed, 31 subtests passed`；13,140-file fixture median `0.7168s → 0.3298s`。
- 本 review 不授權接受 live activation；即使 code review GO，restart marker 與 disabled launchd 仍須保持。

## Review Verdict

- 2026-09-03：初審 `c9ff889` 為 `NO-GO`：P1 regular-file meter root 漏算為 0；P2 repo-internal symlink meter root 先 resolve 後被接受。
- 2026-09-03：Repair Gen1 `6449c78c9616523942dc4b357321fc09b8637a0f` 修復兩項 finding；原 Reviewer re-review 判定 P1/P2 均 resolved，`GO / no P0-P1 blockers`。
- Re-review evidence：4 targeted tests passed；完整 `tests/test_storage_safety.py` 為 `68 passed, 31 subtests passed`；`git diff --check` clean；candidate worktree clean；storage policy hash與 60s／95%／容量／RSS／swap／launch policy 均未變。
- 剩餘風險：目前只有 unit／regression 與 synthetic benchmark 證據；未重跑 live workload。restart-denied marker 與 disabled launchd 必須保持，直到另行取得 live retry authority。
