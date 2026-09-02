# BC-CP1 current checkpoint decision

## Decision

`ADMIT_C0_PHASE_2 / SPENT_AND_CLOSED`

這是依 Owner 明確授權、以 current accepted inputs 重新作成的 standalone BC-CP1 decision，不把 C0 Phase 2 task 的自我引用當作歷史裁決證據。

## Known facts

- B0-P1：formal executable family `720`、canonical generation／identity／partition 已證明；E2 reusable evaluator `NOT_PROVEN`、E3 是 current evaluator、E4 `REQUIRED_BUT_UNCHARACTERIZED`，larger product matrix authority 缺失。
- C0-P1：direct immutable TrialSpec runner seam、TrialSpec-ID-only queue、per-item claim／lease 均缺失；代表性 capacity、live bridge activity與cutover readiness未證明。
- C0-P2：已在固定 task boundary 內交付 `05`–`10` 設計／證據；它只定義 measured gaps、non-representative characterization、shadow／rollback plan與 C1 blockers，沒有 runtime mutation。
- Current-tip review `78d3b3b`：B0＋C0／BC-CP2 integrated tree 為 `REVIEW_GO_CURRENT_TIP_BASELINE`；R13 `downstream_authority=NONE`，R14維持NO-GO。

## Gate evaluation

| BC-CP1 question | Current decision |
|---|---|
| Proven matrix authority | formal executable `720`; larger product universe仍未知 |
| Full-scan／adaptive boundary | 候選集合 authority成立；E3/E4與search policy仍不可升格 |
| Direct TrialSpec runner | 不存在 |
| Capacity dependency envelope | 可用 `720 / E3 / E2_NOT_PROVEN / E4_UNCHARACTERIZED` 作設計輸入；不得宣稱research-valid daily capacity |
| Phase-2 measured gaps | C0的capacity、claim/lease、retry/orphan、bridge parity、rollback缺口已界定 |
| Cross-lane authority conflict | 無阻擋 bounded C0 design evidence的衝突；存在阻擋C1/runtime的明確缺口 |

因此允許的最小充分 verdict 是 `ADMIT_C0_PHASE_2`，且僅覆蓋已完成的 evidence-only design scope。`ADMIT_B0_PHASE_2` 或 `ADMIT_BOTH_PHASE_2_WITH_DEPENDENCIES` 會額外開啟尚未被本決策證明必要的 search-policy／B1 recommendation 工作，超過 minimum sufficient。

## Why not less／why not more／do not absorb

- Why not less：只保留「找不到舊裁決」會讓已驗收的 C0-P2 evidence 永久缺少 checkpoint provenance。
- Why not more：C0-P2 已明確證明 C1 prerequisites仍缺；R14亦無近期 decision value。沒有證據支持擴張到 B0-P2、B1、C1或production。
- Do not absorb：不新增 runtime、queue、claim service、database、registry、scheduler、model adapter或第二套 authority system。

## Authority lifecycle

- admitted scope：C0 Phase 2 `05`–`10` evidence-only design。
- completion：既有 fixed artifact chain已整合，current-tip independent acceptance已通過。
- current state：`SPENT_AND_CLOSED`；沒有持續 execution authority。
- downstream：C1與所有 runtime／cutover工作仍須獨立 admission。

## Verdict boundary

本 decision 不授權 B0-P2、B1、B2、C1、Entry-Regime feasibility、R15、TFM3 download／inference、benchmark、capture、replay、training、outcome、push、deploy或production。
