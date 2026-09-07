---
id: REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01
status: mainline-accepted-local
type: repair
owner_admission: 2026-09-07
---

# Fog 與 External Review 共用寫入面容量接線修復

## Root question

能否以既有 Storage Guard policy 的最小擴充，讓 Fog 長週期與 `external-review-preflight` 的既有合法寫入在同一 runtime 重疊時仍完整納入容量計量，而不被誤判為 `REGISTERED_WRITE_OUTSIDE_METER`，且不削弱未知寫入 fail-closed？

## 使用者需求

### 共用寫入面必須被 Fog meter 納管 <!-- US-001 -->

- **FR-001**：Fog policy 必須明示納管 production 已觀察到的共用路徑 `artifacts/external_review`，不得擴成整個 `artifacts`。 <!-- FR-001 traces_to: US-001 -->
- **FR-002**：共用路徑的新增、修改與刪除必須計入 Fog inventory，且不得再產生 `REGISTERED_WRITE_OUTSIDE_METER`。 <!-- FR-002 traces_to: US-001 -->
- **FR-003**：Fog 自身未登記的 source／其他未知路徑寫入仍須 fail closed；不得以忽略 sibling writes 或停用 snapshot 達成 GREEN。 <!-- FR-003 traces_to: US-001 -->
- **FR-004**：不得新增 scheduler、global lock、ledger、registry、writer attribution service 或第二套 runtime state；不更動 daily／external-review 排程。 <!-- FR-004 traces_to: US-001 -->
- **FR-005**：Fog 既有 hard ceilings、`launch_verified`、cleanup allowlist 與 natural acceptance evidence contract 不得放寬。 <!-- FR-005 traces_to: US-001 -->

1. **Given** Fog snapshot 前後由 sibling job 在 `artifacts/external_review` 新增及刪除檔案，**When** Storage Guard 依 Fog policy reconciliation，**Then** changed paths 全部被 meter 覆蓋且不回 `REGISTERED_WRITE_OUTSIDE_METER`。 <!-- AS-US001-01 traces_to: FR-001, FR-002 -->
2. **Given** `artifacts/external_review` 有固定大小與檔數，**When** Fog 執行 `measure_paths`，**Then** inventory 精確包含該路徑，沒有重複計數。 <!-- AS-US001-02 traces_to: FR-001, FR-002 -->
3. **Given** child 寫入 `source.py` 或其他 Fog 未登記路徑，**When** Storage Guard 比對 project snapshot，**Then**仍回 unknown-write fail closed。 <!-- AS-US001-03 traces_to: FR-003 -->
4. **Given** 修補後 policy，**When** 載入所有 jobs 與 retention rules，**Then** schema、ceilings、launch verification 與既有 job policy 均保持有效。 <!-- AS-US001-04 traces_to: FR-004, FR-005 -->

- **SC-001**：Mainline 的 observed-path probe 由 RED 轉 GREEN。 <!-- SC-001 traces_to: US-001 -->
- **SC-002**：Storage Guard、Fog natural acceptance 與 policy regressions 全綠。 <!-- SC-002 traces_to: US-001 -->
- **SC-003**：production policy 變更通過兩名獨立 blind Reviewer；只有無未解 P0/P1 才可提交。 <!-- SC-003 traces_to: US-001 -->
- **SC-004**：部署前重新取得 capacity PASS、marker identity 與 rollback prestate；不得 kickstart。 <!-- SC-004 traces_to: US-001 -->

## 已保存的 production RED

- Runtime：`/Users/mattkuo/TOP10-runtime-automation-26c8834`。
- Fog invocation：`fog-research-worker-20260907T090500Z-80610`。
- Marker：`REGISTERED_WRITE_OUTSIDE_METER`；child exit `143`，final process group quiescent。
- Sibling invocation：`external-review-preflight-20260907T094000Z-1210`；17:40:01–17:40:05 執行，刪除三個 2026-07-31 retention files並寫入三個 17:40 provider-preflight artifacts。
- Deterministic probe：目前 Fog policy 會把 `artifacts/external_review/{old,new}.json` 回為 registered-unmetered changed paths，exit `1`。

## 可證偽假說

1. 若根因是 Fog meter 漏列 production 共享的 `artifacts/external_review`，只加入該 exact subtree 後 observed-path probe 應轉 GREEN，且該 subtree bytes/files 會被計入 inventory。
2. 若根因其實是 Fog child 自己越界寫入，external-review receipt、artifact mtime 與 retention removal 不會同時綁在 17:40 sibling invocation；目前 live evidence 已否證此假說。
3. 單純移動排程只能降低重疊機率，不能修正同一 runtime 的 deterministic shared-write contract；因此不採 schedule workaround。

## 最小充分設計

- 沿用既有 `meter_paths` 作唯一容量 authority，把已量測的 shared subtree 加入 Fog meter；這表示「Fog 執行期間此 subtree 的容量變化也受 Fog hard ceilings 保護」，不宣稱檔案由 Fog 寫入。
- 保留全專案 snapshot、registered/unknown write gate 與逐 job ceilings。

### why_not_less

只清 marker 或只部署上一張 acceptance 修補，下一個 17:40 重疊仍會再次停止 Fog。

### why_not_more

不為單一已量測 shared subtree 新增全域 lock、scheduler priority、writer ledger 或 process attribution framework。

### do_not_absorb

不修 external-review child exit `1`、不調排程、不改 Fog 研究邏輯、不碰 ME-D1、ranking、model 或 publish。

## 垂直切片

| Slice | Scope | traces_to | Blocking edge | Verification |
|---|---|---|---|---|
| `FOG-XJM-SLICE-001` | observed sibling add/delete RED 與 inventory assertion | `FR-001`–`FR-003`, `AS-US001-01`–`03`, `SC-001` | 無；目前 frontier | 單一 RED→GREEN test |
| `FOG-XJM-SLICE-002` | exact shared subtree policy/documentation update | `FR-001`, `FR-004`, `FR-005`, `AS-US001-04` | `FOG-XJM-SLICE-001` | policy loader＋invariant tests |
| `FOG-XJM-SLICE-003` | affected regressions、雙盲 review、fixed-candidate evidence | `SC-002`–`SC-004` | `FOG-XJM-SLICE-002` | pytest＋review＋preflight |

## 允許修改

- `docs/operations/top10-storage-policy.json`
- `docs/operations/top10-storage-safety.md`
- `tests/test_storage_safety.py`
- 本卡 `.work/`、`.ai/` 與 `docs/evidence/` 文件

## 禁區

- 不修改 `app/storage_safety.py` 或其他 production source。
- 不把 Fog meter 擴成整個 `artifacts`。
- 不新增 lock／ledger／scheduler／runtime state，不改任何 plist。
- 實作與 review 階段不清 marker、不 deploy、不 kickstart、不 push。
- 未通過雙盲 review 不得提交或進 production。

## Evidence

- `.work/REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-01/`
- `docs/evidence/REPAIR-TOP10-FOG-CROSS-JOB-SHARED-METER-20260907.md`
