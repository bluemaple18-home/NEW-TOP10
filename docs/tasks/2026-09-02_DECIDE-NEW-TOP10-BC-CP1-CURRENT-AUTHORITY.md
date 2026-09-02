---
id: DECIDE-NEW-TOP10-BC-CP1-CURRENT-AUTHORITY
chain_id: BC-CP1-CURRENT-AUTHORITY-01
status: decided
type: mainline-checkpoint-decision
risk: critical
production_change_allowed: false
runtime_change_allowed: false
network_allowed: false
owner_authorization: explicit
---

# BC-CP1 current authority decision

## 工作名稱 → 正在做什麼 → 現在狀態

`BC-CP1 Current Authority` → 用已接受的 B0-P1／C0-P1 inputs 補上缺失的 standalone checkpoint 裁決 → `ADMIT_C0_PHASE_2 / SPENT_AND_CLOSED`

## Root question／blocker／fork

- Root question：目前 accepted baseline 中，哪一個 Phase 2 具備足夠、可重現且不升格的 BC-CP1 authority？
- Blocker：既有 C0 Phase 2 task 自稱來自 `ADMIT_C0_PHASE_2`，但 repo 沒有 standalone BC-CP1 decision artifact。
- Candidate forks：B0-P2、C0-P2、TimesFM／TFM3；其中 TFM3 另需 Owner 授權下載／inference，B0-P2 尚缺本 checkpoint admission，C0-P2 已有完整 bounded evidence 與 current-tip independent acceptance。

## 固定輸入

- canonical B0/C0 source：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- B0-P1 fixed tip：`1e9ed61e2e5c86adf2159e095ff241ef13127e80`
- C0-P1／C0-P2 source chain：`c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba` → `a61f143ea5223b6af812e27aac0082121f781343`
- current-tip acceptance：`78d3b3b1d246dd37f8a1094ff85ba5175dae995e`
- backlog reconciliation：`03fbc5c`
- Owner authorization：本 task 直前對話中的明確「授權」。

## Verdict

`ADMIT_C0_PHASE_2`

此 verdict 僅補足已完成 C0 Phase 2 設計／證據工作的 checkpoint provenance。其 authority 固定於 `docs/tasks/2026-09-01_DISPATCH-NEW-TOP10-C0-PHASE-2-CAPACITY-AND-CUTOVER-DESIGN.md` 的 evidence-only scope，並因成果已整合及驗收而標記 `SPENT_AND_CLOSED`；不得用來重跑 capacity、修改 runtime、啟動 cutover、移除 bridge 或准入 C1。

B0-P2、B1、B2、C1、R15、Entry-Regime feasibility、TFM3 download／inference 與 production 均維持 `NOT_ADMITTED`。

## 驗收

- 詳細 decision evidence：`docs/evidence/BC-CP1-CURRENT-AUTHORITY-RECONCILIATION/01-current-checkpoint-decision.md`
- canonical backlog 必須同步記錄 `C0_P2_ACCEPTED_CLOSED` 與其無持續 execution authority 邊界。
- 只允許 docs/control metadata；`git diff --check` 必須通過。
