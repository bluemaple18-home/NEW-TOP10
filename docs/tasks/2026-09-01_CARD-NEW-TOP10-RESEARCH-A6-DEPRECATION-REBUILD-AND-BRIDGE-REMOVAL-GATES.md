---
id: CARD-NEW-TOP10-RESEARCH-A6-DEPRECATION-REBUILD-AND-BRIDGE-REMOVAL-GATES
status: IMPLEMENTATION_COMPLETE / REVIEW_GO / MAINLINE_ACCEPTANCE_PENDING
type: implementation
issue: 8
depends_on: [4, 5, 6, 7]
baseline: bb617e98aabefcc52bbf7cb1834fb5fba715d60a
---

# A6 Deprecation、Rebuild 與 Bridge Removal Gates

日期：2026-09-01

👉 [假設與目標確認] 目標：A6 closure 僅修復 fail-closed 驗證缺口；邊界：不啟動 Card B/C、production、scheduler 或 ranking/backtest math；驗收：fixed-SHA 可重跑、六項 P1 攻擊探針拒絕且受影響回歸通過。

## Root question

A1–A5 已進 main 後，能否用單一可重跑證據證明 Research Spine 可從 first-party immutable corpus 完整重建、`run_history` 不再是新 run truth authority，且每條 compatibility bridge 都有可執行的退場條件，而不啟動 Card B／Card C？

## Current state

- A1–A5 已完成 mainline acceptance；Issue #4–#7 已關閉。
- Issue #8 為唯一 next frontier，依賴已清空；A6=`ADMITTED / IMPLEMENTATION_READY`。
- 現有 ledger、eligibility、failure、matched learning 與 history compatibility projection 已有局部 rebuild tests，但缺單一 A6 closure receipt。
- `run_history` reader／projection、legacy migration、backfill 與 adapter seams 尚未形成完整 owner／removal condition／removal test／target stage inventory。
- Card B、Card C、production、scheduler mutation 與 ranking math 均未 admission。

## Measured gaps

1. 缺少從同一 immutable corpus 刪除 rebuildable outputs 後，對 A1–A5 identities、counts、ledger snapshot 與 projections 做一次性 deterministic reconciliation 的 closure gate。
2. 缺少證據證明新 run 的 success／failure／orphan state 可只靠 first-party intent／attempt／receipt／artifact 重建，且不需 `run_history` 或 post-hoc filesystem backfill 建立 truth。
3. compatibility readers、writers、projections、dual paths 與 backfill scripts 缺完整、可驗證的 removal metadata；不得直接刪除以假裝完成。

## Scope

- 先產 Issue requirement → existing seam → evidence → measured gap → decision matrix。
- 建立或補強單一 end-to-end rebuild／reconciliation gate與精簡 closure receipt。
- 對新 run 明確標示 `run_history` 為 derived compatibility／archival read-only，而非 truth authority。
- 盤點所有相關 bridge，逐項保存 owner、removal condition、removal test、target removal stage 與目前狀態。
- 證明正常新 run 不要求 post-hoc filesystem backfill；backfill 只可作 isolated recovery／historical migration。
- 只輸出 A0–A5 發現的 upstream AI Core proposal list，不對 AI Core 或外部服務 write。

## Out of scope

- 不刪除 compatibility path，除非既有 removal test 已證明 cutover safe；本卡預設只建立 gate。
- 不修改 LightGBM、backtest、ranking、publish、production、scheduler 或 provider semantics。
- 不做 Card B priority/search/decision projection，也不做 Card C control cutover。
- 不新增 authority ledger、registry、FSM、database、canonical writer 或第二套 runtime。

## Requirements

- **US-001**：Owner 可用一個可重跑 gate 證明 A1–A5 spine 從 first-party corpus deterministic rebuild。 <!-- US-001 -->
- **US-002**：Owner 可證明新 run truth 不依賴 `run_history` 或 post-hoc backfill。 <!-- US-002 -->
- **US-003**：Owner 可查看每條 compatibility bridge 的責任人與可執行退場證據。 <!-- US-003 -->

- **AS-US001-01**：刪除 rebuildable ledger／projection outputs 後，以相同 corpus／policies 重建，canonical identities、counts、logical snapshots 與 projection payloads 完全一致。 <!-- AS-US001-01 traces_to: FR-001, FR-002 -->
- **AS-US002-01**：新 run 的成功、失敗與 orphan fixtures 在沒有 `run_history` 與 backfill input 時仍可由 first-party evidence 重建；缺 evidence 時 fail closed。 <!-- AS-US002-01 traces_to: FR-003, FR-004 -->
- **AS-US003-01**：每條 bridge 都有完整 removal metadata，且 removal test 可執行；缺任何欄位即 closure NO-GO。 <!-- AS-US003-01 traces_to: FR-005, FR-006 -->

- **FR-001**：A6 gate 必須從 A1 TrialSpec／dataset、A2 intent／attempt／receipt、A3 migration、A4 ledger／eligibility／failure、A5 learning projection依序重建。 <!-- FR-001 traces_to: US-001 -->
- **FR-002**：相同 inputs 必須產生相同 canonical IDs、counts、logical ledger snapshot與projection semantic payload；local path、mtime與wall clock不得影響結果。 <!-- FR-002 traces_to: US-001 -->
- **FR-003**：新 run terminal／orphan truth只能由first-party immutable evidence與既有policy建立；`run_history`只能是derived compatibility projection。 <!-- FR-003 traces_to: US-002 -->
- **FR-004**：backfill seam必須被分類為historical migration或isolated recovery；正常新 run驗收不得讀取backfill output建立truth。 <!-- FR-004 traces_to: US-002 -->
- **FR-005**：bridge inventory每列必須包含owner、direction、authority、read/write mode、removal condition、removal test、target stage與status。 <!-- FR-005 traces_to: US-003 -->
- **FR-006**：closure verifier對缺欄位、無法執行的removal test、authority inversion、unexplained delta或新 run backfill dependency一律fail loudly。 <!-- FR-006 traces_to: US-003 -->

## Success criteria

- **SC-001**：單一驗證入口完成clean rebuild與A1–A5 reconciliation，重跑結果一致。 <!-- SC-001 traces_to: US-001, FR-001, FR-002 -->
- **SC-002**：success／failure／orphan fixtures證明新 run不需`run_history`或post-hoc backfill，且缺first-party evidence時拒絕。 <!-- SC-002 traces_to: US-002, FR-003, FR-004 -->
- **SC-003**：所有盤點到的bridge均通過schema與removal-test inspection，零unknown owner、零missing removal condition。 <!-- SC-003 traces_to: US-003, FR-005, FR-006 -->
- **SC-004**：production、LightGBM與backtest math無差異；Card B／C維持NOT_STARTED。 <!-- SC-004 traces_to: US-001, US-002, FR-006 -->
- **SC-005**：完整affected regression與`git diff --check`通過，獨立fixed-SHA review剩餘`P0=0 / P1=0`。 <!-- SC-005 traces_to: US-001, US-002, US-003, FR-001, FR-006 -->

## Vertical slices

### A6.1 — Gap matrix 與 bridge inventory

- 先盤點reader／writer／projection／migration／backfill seams及現有proof；無measured gap不得改code。
- 產生machine-checkable bridge inventory與validator RED fixtures。
- `traces_to: FR-005, FR-006, SC-003`

### A6.2 — End-to-end clean rebuild closure

- 用isolated fixture刪除rebuildable outputs後重建A1–A5，對帳identities、counts、snapshot與projection payload。
- 任一unexplained delta或non-determinism即NO-GO。
- blocking edge：A6.1完成。
- `traces_to: FR-001, FR-002, SC-001`

### A6.3 — New-run authority／no-backfill proof

- 覆蓋success、failure、orphan與missing-first-party-evidence fixtures。
- 證明`run_history`僅derived/read-only；正常新 run不消費backfill output建立truth。
- blocking edge：A6.1完成。
- `traces_to: FR-003, FR-004, SC-002`

### A6.4 — Closure receipt 與 proposal list

- 綁定A6.1–A6.3驗證結果、bridge removal evidence與upstream AI Core proposal list。
- 不執行bridge removal、AI Core write或Card B/C。
- blocking edge：A6.2與A6.3完成。
- `traces_to: FR-005, FR-006, SC-003, SC-004, SC-005`

## Dispatch and limits

- Implementation：`strict/core-bounded → GPT-5.5 high`，獨立worktree。
- Fixed-SHA Reviewer：`GPT-5.5 high`；Review只裁決，不修改。
- 如有bounded Repair：預設`Terra medium`，最多2代，原Reviewer re-review。
- Worker交付candidate SHA、changed files、驗證命令、bridge inventory與remaining P0/P1。
- 不得merge、push、關閉Issue #8或啟動Card B／C；須回Mainline另行驗收與Owner授權。

## Final review handoff

- Status：`IMPLEMENTATION_COMPLETE / REVIEW_GO / MAINLINE_ACCEPTANCE_PENDING`
- Reviewed implementation SHA：`6f6796c5da549b3c62698b336cacdda63ced6c6d`
- Repair closure：Repair-1 與 Repair-2 已完成；remaining `P0=0 / P1=0`。
- Verification：focused=`26 passed`；affected=`182 passed`；fixed-fixture CLI=`PASS`；checked-in receipt canonical match=`PASS`；`git diff --check`=`PASS`。
- Scope：Card B／C=`NOT_STARTED`；未 merge、push 或關閉 Issue。
