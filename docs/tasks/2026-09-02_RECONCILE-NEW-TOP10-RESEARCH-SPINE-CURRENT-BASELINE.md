---
id: RECONCILE-NEW-TOP10-RESEARCH-SPINE-CURRENT-BASELINE
chain_id: RESEARCH-SPINE-AUTHORITY-RECONCILIATION-02
status: accepted
type: mainline-control-reconciliation
risk: high
production_change_allowed: false
runtime_change_allowed: false
network_allowed: false
---

# Research Spine current-baseline authority reconciliation

## 工作名稱 → 正在做什麼 → 現在狀態

`Research Spine Current-Baseline Reconciliation` → 將 canonical backlog 從 F0／BC-CP1 舊快照對齊已驗收的 current tip → `DOCS_ONLY / ACCEPTED`

## 固定輸入

- F0 reconciliation：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- B0 merge：`b49b3532f0ac3849a841816c00aae9267fb86a03`
- C0／BC merge：`a6fbf839153e66f267e3855b1893147a888e2ef6`
- R14 admission review baseline：`db70dde285256af38c17129362b6cbd542d9a977`
- current-tip acceptance：`78d3b3b1d246dd37f8a1094ff85ba5175dae995e`
- acceptance evidence：`docs/evidence/REVIEW-NEW-TOP10-B0-C0-BC-CP2-CURRENT-TIP-MAINLINE-ACCEPTANCE/review.md`

## 裁決

- F0、B0-P1、C0-P1 與 current integrated non-production baseline 已接受。
- C0 Phase 2 文件雖已整合，但 repo 內沒有獨立 BC-CP1 admission decision artifact；canonical current authority 仍不得據此宣稱 C0-P2、B0-P2、B1 或 C1 已准入。
- BC-CP2 R1–R14 可保留為已驗收 evidence trail；R13 僅固定單一 bundle，`downstream_authority=NONE`；R14 維持 `NO_GO_R14_INSUFFICIENT_DECISION_VALUE`。
- 下一個唯一治理 gate 是 `BC-CP1_AUTHORITY_RECONCILIATION`，只重建或重新裁決 Phase 2 authority provenance，不執行 Phase 2、benchmark、capture、replay 或 runtime mutation。

## 邊界與驗收

- 只修改本卡與 `docs/RESEARCH_SPINE_BACKLOG.md`。
- 不修改 code、config、workflow、schema、queue、runner、model、ranking、backtest、scheduler、publish 或 production。
- 不 push、deploy、改 Issue、刷新資料或執行 external write。
- 驗收：backlog 不再把 F0、B0-P1、C0-P1 寫成待辦；不存在從已 merge 文件自動推導 Phase 2 admission 的文字；`git diff --check` 通過。
