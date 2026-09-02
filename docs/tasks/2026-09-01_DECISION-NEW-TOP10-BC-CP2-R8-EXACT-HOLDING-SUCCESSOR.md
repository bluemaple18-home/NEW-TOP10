# 工作名稱：BC-CP2 R8 Exact-holding Path 與 Successor 裁決

任務簡介：依 R5–R7 固定證據，裁決 configured exact-holding regime path 是否繼續，以及是否存在不放寬現行 authority 的 successor 方向。

## 固定證據

- R5：`1035ca82a56a4b182be0508498ed10676b064da9`
- R6：`b7ba1fc6065d6221353f7362db92ac7638bb8017`
- R7：`e1a30830d0ab2ee24af0f81d703cbf350be4819e`
- R7 census：28 exact identities；16 有 rows；2 split-OK；0 具 h3/h5/h10/h20 safe development dates。
- 既有 prior-art cards：
  - `docs/tasks/2026-08-16_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-ARCHITECTURE-DECISION-V1.md`
  - `docs/tasks/2026-08-16_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1.md`

## Mainline decision

- `KEEP_CONFIGURED_EXACT_HOLDING_PATH_CLOSED`
- `DO_NOT_RELAX_TAXONOMY_SPLIT_EPISODE_OR_HORIZON`
- `ENTRY_REGIME_COHORT_IS_SEPARATE_SUCCESSOR_CANDIDATE`
- `SUCCESSOR_NOT_ADMITTED`

理由：現行 exact-holding path 的缺口是 identity episode continuity authority，不是 runner 或 ranking availability。合併 taxonomy、放寬 split、跨 episode holding 或縮短 horizon 都會改變研究問題，不能當成 repair。既有 Entry-Regime Cohort 將 attribution 固定在 entry 時點並把 future regime path 限為診斷，提供較小且語意獨立的 successor seam；但其 2026-08-16 卡片早於 current canonical backlog，不能自動視為已准入。

## 邊界

- 本裁決不修改 code、config、data、taxonomy、split、episode、horizon、ranking、runner或 production。
- 不准入 B0 Phase 2、B1、C0 Phase 2、C1、production canary或 replay。
- R6 fog ranking root 仍只是第二依賴；successor 未准入前不得綁定或切換。
- 未 merge、push、改 Issue、deploy或 external write。

## 唯一 handoff

若 Owner 要繼續 h20 regime-conditioned research，下一張只能是 current-baseline 的 `ENTRY-REGIME-COHORT-FEASIBILITY-RECONCILIATION`：先唯讀核對舊 architecture decision／feasibility card 與 current R7、canonical backlog、ranking provenance 是否相容；不得直接實作或 replay。

現在狀態：`MAINLINE_DECIDED / EXACT_HOLDING_CLOSED / SUCCESSOR_OWNER_ADMISSION_REQUIRED`
