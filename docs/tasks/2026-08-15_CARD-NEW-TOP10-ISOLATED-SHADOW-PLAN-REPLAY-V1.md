---
id: CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: architecture-implementation
priority: P1
owner: TOP10new research platform
role: implementation
cycle: 13
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: 本卡會讓 proposal 進入真實 development-only runner；雖禁止 live cutover，仍需嚴格鎖定 execution identity、容量與隔離寫入。
date: 2026-08-15
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
canonical_queue_change_allowed: false
evidence_path: docs/evidence/CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1/
---

# 隔離執行 Shadow Plan Replay

## 工作名稱

把已核准的 `horizon 10 → 20` proposal 轉成最多 4 個 development-only execution units，經正式 Runner 在隔離根目錄完成可重現比較。

## Root question

在 `NARROW_LEADER|BIG_BULL` 相同研究條件下，`horizon=20` 相對 `horizon=10` 是否能形成可信、可重播的新 evidence，而不觸碰 canonical queue、scheduler 或 production？

## 已核准來源

- Source commit：`28708ee3956fd0b6c9400dc21ecfb72920b46312`
- `docs/evidence/CARD-NEW-TOP10-SHADOW-RESEARCH-PLAN-PROPOSAL-V1/shadow_research_plan_proposal.json`
- Proposal status：`PASS`
- 唯一 action：`horizon 10 → 20`
- Scope：`NARROW_LEADER|BIG_BULL`

## Ownership

### 允許修改

- `app/research/` 內本卡 isolated replay bundle、runner adapter、verifier直接相關檔案。
- 本卡 bounded CLI與 targeted tests。
- `docs/evidence/CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1/`。

### 禁止修改

- `artifacts/autonomous_research/next_action_queue.json`、manager selection／ordering／quota／cooldown。
- Proposal、parameter catalog、shadow queue policy與既有 committed evidence。
- `scripts/run_daily_research_quota.sh`、launchd／scheduler、背景服務。
- Production model、ranking、signals、promotion、LightGBM。
- Optuna、dynamic refinement、額外參數掃描或超過本卡矩陣。
- 使用者既有 dirty files與既有 `.work/**`。

## Functional contracts

### `ISR-FR-001`｜Authoritative proposal admission

- 只接受 repo 內 committed proposal exact path與identity。
- 驗證 proposal status、semantic hash、proposal ID、boundary、protected parity及來源hash。
- 非 `horizon 10 → 20`、scope擴大、external／traversal／symlink input一律 fail closed。

### `ISR-FR-002`｜Bounded paired matrix

- 固定兩個獨立 lineages；每 lineage只比較 `horizon=10` 與 `20`，最多4 units。
- 除 horizon 外所有研究條件、資料集、ranking source、split與scope必須相同。
- 不得自行新增權重、參數值、topic或sealed validation。

### `ISR-FR-003`｜Formal runner and isolated writes

- 必須走既有 canonical batch owner／正式 autonomous research runner seam，不得用 synthetic result冒充。
- Stage固定 `DEVELOPMENT_SCREEN`；corpus、ledger、manager root、output全部位於本卡隔離根目錄。
- Execution identity、correlation、attempt、argv與return code必須落 immutable receipt。

### `ISR-FR-004`｜Capacity and parity

- 啟動前容量 gate必須 `GO`；硬上限：4 units、64 MiB新增量、250 files。
- 超限或預估不可知即 `NO-GO_CAPACITY`；不得 fallback到共享root。
- 前後 canonical queue、scheduler與production hashes必須一致。

### `ISR-FR-005`｜Evidence result

- 每 unit必須是 `SUCCEEDED / OBSERVED / EXACT / VALID / PROVEN_NON_SEALED` 才可形成比較。
- 產出 horizon 10 vs 20 matched contrasts、兩 lineage結果與明确分類；失敗可合法 `NO-GO`，不得包裝成正向證據。
- 本卡只交 development evidence；不得自動回寫shadow queue、建立下一輪或promotion。

## Slices

1. Admission／bundle schema與負向 fixtures。
2. 4-unit deterministic execution plan與identity。
3. 隔離正式 Runner execution＋immutable receipts。
4. Result verifier、capacity/parity、targeted regression與rollback proof。

## Acceptance

- 計畫恰為2 lineages × horizons `{10,20}`，最多4 units。
- 所有 units走正式 runner；無 synthetic、sealed或shared-root evidence。
- 二跑計畫 identity一致；execution receipts可重播並可稽核。
- 4 units全部合格才輸出比較；否則 structured `NO-GO`。
- 容量在64 MiB／250 files內；canonical queue、scheduler、production零變更。
- Targeted pytest、CLI verifier、`py_compile`、JSON validation、`git diff --check`全綠。

## Stop conditions

- 正式Runner無法在隔離root接收完整4-unit矩陣：`BLOCKED_RUNNER_CONTRACT`。
- 需要改catalog、queue、scheduler、production或執行sealed validation：`BLOCKED_SCOPE_VIOLATION`。
- 真實資料或正式入口不足：`NO-GO_EVIDENCE_UNAVAILABLE`，不得用synthetic替代。
- 容量gate非GO或同一blocker第三次失敗：停止並回主線。

## Deliverable

- Candidate commit SHA、exact execution matrix、receipts、結果分類、測試與evidence paths。
- 狀態只可為 `DELIVERED_CANDIDATE` 或 structured `NO-GO/BLOCKED`；不得宣稱 integrated、accepted或live。
