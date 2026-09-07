---
id: REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01
status: candidate-green-deploy-blocked
type: repair
owner_admission: 2026-09-07
---

# Fog natural acceptance evidence bounded repair

## Root question

能否沿用既有 Storage Guard archive receipt、Fog harness artifact 與排程欄位，把同一次 invocation 的 terminal artifact 與自然 cadence 證據接回 receipt，且在任一證據缺失時維持 fail closed？

## 使用者需求

### Invocation-bound acceptance evidence <!-- US-001 -->

- **FR-001**：Fog worker 成功週期必須以 atomic、immutable、invocation-bound artifact 保存 `artifact_run_date`、`run_id`、`invocation_id` 與 terminal result。 <!-- FR-001 traces_to: US-001 -->
- **FR-002**：Storage Guard 只能在 child exit 且 process group quiescent 後讀取 exact invocation evidence；不得讀未綁定 invocation 的 `latest`。 <!-- FR-002 traces_to: US-001 -->
- **FR-003**：natural provenance 必須由 `scheduled_at`、`invocation_id`、Fog plist cadence 與既有 archived receipt 驗證；PPID=1 只可作 candidate，不可直接證明 natural。 <!-- FR-003 traces_to: US-001 -->
- **FR-004**：只有 artifact/date、natural cadence、child exit、process-group quiescence、denial marker absence 與 worker lock absence 全部成立時才累加 accepted natural cycles。 <!-- FR-004 traces_to: US-001 -->
- **FR-005**：連續兩個合格週期才可標 `ACCEPTED`；任何中斷或證據缺口重設為 pending/0。 <!-- FR-005 traces_to: US-001 -->

1. **Given** child exit=0 但 exact invocation artifact evidence 缺失，**When** 寫 final receipt，**Then** `NATURAL_ACCEPTANCE_PENDING` 且 `accepted_natural_cycles=0`。 <!-- AS-US001-01 traces_to: FR-001, FR-002, FR-004 -->
2. **Given** artifact date 與 terminal result 正確但 cadence provenance 尚未驗證，**When** 寫 final receipt，**Then** 仍為 pending/0。 <!-- AS-US001-02 traces_to: FR-003, FR-004 -->
3. **Given** exact artifact 與 cadence 都正確且其餘 gates 通過，**When** 寫 final receipt，**Then** accepted counter 由前一份合格 archived receipt 遞增。 <!-- AS-US001-03 traces_to: FR-001, FR-002, FR-003, FR-004 -->
4. **Given** 兩輪連續合格 invocation，**When** 第二輪完成，**Then** `accepted_natural_cycles=2` 且 `acceptance_status=ACCEPTED`。 <!-- AS-US001-04 traces_to: FR-005 -->
5. **Given** latest-only、錯 invocation、錯 date/hash、symlink、錯 cadence、denial marker 或殘留 Fog lock，**When** 驗證，**Then** fail closed，不累加。 <!-- AS-US001-05 traces_to: FR-002, FR-003, FR-004 -->

- **SC-001**：先有能重現目前 blocker 的 observable RED，再做最小 GREEN。 <!-- SC-001 traces_to: US-001 -->
- **SC-002**：targeted unit/integration、shell syntax 與既有 Storage Guard/Fog regressions 通過。 <!-- SC-002 traces_to: US-001 -->
- **SC-003**：`git diff --check` 通過，diff 僅限本卡。 <!-- SC-003 traces_to: US-001 -->

## 最小充分設計

- terminal evidence 是單次 invocation artifact，不是新 ledger；長期計數 authority 仍為既有 archived receipt。
- cadence verifier 只讀現有 Fog plist 與 archived receipts，驗證相鄰 `scheduled_at` 間隔及 invocation timestamp binding；不建立第二套 scheduler state。
- 第一個無前序 cadence anchor 的週期不能自證；首個可驗證週期最多累加為 1，下一個連續週期才可 ACCEPTED。

### why_not_less

只填 receipt 欄位或信任 latest 仍無法證明 artifact lineage；只信 PPID=1 仍無法區分 kickstart。

### why_not_more

不新增 DB、ledger、scheduler、daemon、activation token 或通用 acceptance framework；這張只修 Fog 既有接縫。

### do_not_absorb

不處理其他 recurring jobs、不改 Fog 研究邏輯、不切 production、不回填既有 2026-09-07 OK receipt。

## 垂直切片

| Slice | Scope | traces_to | Blocking edge | Verification |
|---|---|---|---|---|
| `FOG-NAE-SLICE-001` | invocation-bound terminal artifact writer/validator | `FR-001`, `FR-002`, `AS-US001-01`, `AS-US001-05` | 無；目前 frontier | RED→GREEN unit test |
| `FOG-NAE-SLICE-002` | wrapper metadata export、worker terminal wiring | `FR-001`, `FR-002` | `FOG-NAE-SLICE-001` | shell fixture/integration |
| `FOG-NAE-SLICE-003` | archived-receipt cadence verifier 與 counter gate | `FR-003`–`FR-005`, `AS-US001-02`–`05` | `FOG-NAE-SLICE-001` | RED→GREEN receipt tests |
| `FOG-NAE-SLICE-004` | focused regression、雙盲 review、evidence reconciliation | `SC-001`–`SC-003` | `FOG-NAE-SLICE-002`, `FOG-NAE-SLICE-003` | targeted suite＋review |

Checkpoint：完成 `SLICE-001/002` 後確認 artifact identity/atomicity；完成 `SLICE-003` 後跑四個 acceptance scenarios，再進 review。

## 允許修改

- `app/storage_safety.py`
- `app/fog_natural_acceptance.py`（可新增）
- `scripts/run_with_storage_guard.sh`
- `scripts/run_fog_research_worker.sh`
- `scripts/write_fog_terminal_evidence.py`（可新增）
- `tests/test_storage_safety.py`
- `tests/test_fog_natural_acceptance.py`（可新增）
- `tests/test_fog_storage_validation.py`
- 本卡 `.work/` 與 evidence 文件

## 禁區

- 不 manual kickstart、不清 restart-denied marker。
- 不把 `PPID=1` 或 `trigger_type=natural` 直接硬寫為 verified。
- 不讀未綁定 invocation 的 latest artifact/receipt 作 acceptance。
- 不把既有 `fog-research-worker-20260907T070804Z-4310` 回填成 accepted。
- 不修改 production runtime、不 deploy、不 push、不新增 heartbeat。
- 不碰 ME-D1、ranking、model、publish、Research Matrix 或研究選題邏輯。

## Evidence

- `.work/REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-01/evidence/`
- `docs/evidence/REPAIR-TOP10-FOG-NATURAL-ACCEPTANCE-EVIDENCE-20260907.md`

## Mainline acceptance

- 本地 bounded repair、targeted regression 與雙盲重審均已通過。
- 目前只可宣告 `CANDIDATE_GREEN / NATURAL_ACCEPTANCE_PENDING / NON_PRODUCTION`。
- 尚未 deploy；既有 receipt 不回填，必須待部署後由兩個新的合格自然週期形成 live acceptance。
- Owner 已於 2026-09-07 授權 commit 與 production deploy；deploy preflight 隨後發現既有 runtime 的 Fog restart-denied marker，根因為 invocation `fog-research-worker-20260907T090500Z-80610` 偵測到 `REGISTERED_WRITE_OUTSIDE_METER`。依本卡禁止清 marker 的邊界，deployment fail closed，沒有執行 activation。
