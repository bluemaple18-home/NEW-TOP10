---
id: CARD-NEW-TOP10-RESEARCH-A5-MATCHED-LEARNING-PROJECTION
status: REPAIR_1_COMPLETE / READY_FOR_REREVIEW
type: implementation
issue: 7
depends_on: [6]
baseline: ce41e65811817e7c29d68c05debd42470dca1384
---

# A5 Matched Learning Projection

## Root question

既有 matched-learning seam 是否能只從 A4 已驗證的 eligible observations 與 versioned policy，產生 deterministic、rebuildable、explainable 的 learning projection；若不能，最小缺口是什麼？

## Current state

- Issue #6 已完成並關閉；Issue #7 為唯一解除 blocker 的 next frontier。
- A5=`ADMITTED / IMPLEMENTATION_READY`；A6=`BLOCKED / NOT_STARTED`。
- 現有 `app/research/parameter_learning.py`、policy、tests 與 verifier 只能作待驗 seam，不因既有或曾通過測試而自動視為 A5 accepted。
- Baseline audit 已觀察到 wall-clock payload 與既有 artifact 取代 fresh recompute truth 的風險；Worker 必須先用 RED 固定是否構成可重現缺口。

## Scope

- deterministic matched comparisons from eligible observations；明確 comparable cohort 與 baseline/candidate relationship。
- independent lineage、neighbor/robustness evidence references、failure-classification derived evidence 與完整 policy/catalog/projection provenance。
- 同一 inputs 與 policy version 可刪除重建相同 IDs、counts、semantic payload 與 canonical bytes。
- publication snapshot/report 僅在 Issue #7 acceptance 確有需要時建立。

## Constraints

- 不建立新的 learning truth DB、authority、registry、runtime 或 canonical writer。
- 不做 priority、candidate ranking、optimizer、queue control、scheduler、production、ranking/model/signal/promotion 變更。
- 不讓 sealed、unknown、legacy diagnostic、topic-level、ineligible 或非獨立 evidence 形成 parameter direction。
- 不修改 A1–A4 immutable evidence；A6 不啟動。
- 只改有 RED 證明的最小 owner seam；無 measured gap 的既有能力維持 `USE_AS_IS`。

## Vertical slices

- `A5-SLICE-001` — baseline characterization 與 gap matrix；`blocked_by: none`；`traces_to: FR-A5-001, SC-A5-001`。
- `A5-SLICE-002` — 最小 deterministic/fail-closed projection closure；`blocked_by: A5-SLICE-001`；`traces_to: FR-A5-001..FR-A5-004, SC-A5-001..SC-A5-004`。
- `A5-SLICE-003` — rebuild verifier、consumer-invariance 與 regression；`blocked_by: A5-SLICE-002`；`traces_to: SC-A5-001..SC-A5-005`。

Current frontier：`A5-SLICE-001`。Slice 1 未固定 measured gap 前不得開始 mutation；Slice 2 完成後先 checkpoint，再進 Slice 3。

## Requirements and acceptance

- `FR-A5-001`：learning 只讀 A4 eligible observations，並綁定 eligibility、failure、policy、catalog 與 corpus provenance。
- `FR-A5-002`：matched comparison 只能在除單一 tested parameter 外其餘 cohort dimensions 等價時成立，且保存 pair/lineage evidence refs。
- `FR-A5-003`：direction、flat、peak、basin、interaction 與 failure-learning classification 只由 matched independent evidence衍生；不足時明確 `INSUFFICIENT_EVIDENCE`。
- `FR-A5-004`：projection artifact 可刪除重建；tamper、identity/count/ref/DB collision 必須 fail closed，不能以既有 artifact 覆蓋 fresh truth。
- `SC-A5-001`：相同 eligible observations + policy version 兩次 clean rebuild 產生 exact-equal IDs、counts、semantic payload 與 bytes。
- `SC-A5-002`：topic/regime/dataset/ranking source/research stage/lineage/profile 或其他 parameter 任一不等價時，不產 matched direction evidence。
- `SC-A5-003`：sealed/unknown/ineligible/legacy diagnostic/topic-level evidence不能進 learning；single-lineage、重複 evidence unit 不得被算成 independent support。
- `SC-A5-004`：artifact/identity/count/ref/collision hostile fixtures fail loud 且不留下 partial derived state。
- `SC-A5-005`：既有 shadow/knowledge/replay consumer 行為不因 A5 admission而取得新的 execution-control authority；A5 不產 priority、queue 或 optimizer output。

## Allowed surface

- `app/research/parameter_learning.py`
- `tests/test_parameter_learning.py`
- `scripts/verify_adaptive_learning.py`（僅 verifier binding）
- 本 task card與必要 mainline status control metadata
- 其他檔案只有新 RED 證明 owner seam 不足時才可提案，未經 Mainline 接受不得修改。

## Verification and handoff

- Targeted RED/GREEN：matched cohort、independence、rebuild bytes、tamper/collision、insufficient evidence、consumer invariance。
- A1–A5 affected regression、既有 adaptive shadow/knowledge/replay compatibility、`git diff --check`。
- 交付單一 local candidate SHA、exact changed files、命令結果與 remaining `P0/P1`；不得 merge、push、關閉 Issue #7 或啟動 A6。
- Strict fixed-SHA independent review 必須 `GO / remaining P0=0 / P1=0` 才能回 Mainline acceptance。

## Worker evidence

- Worktree: `a5-matched-learning-20260831-230428`
- Branch: `codex/top10new-a5-matched-learning-20260831-230428`
- Baseline: `ce41e65811817e7c29d68c05debd42470dca1384`
- RED fixed:
  - `generated_at` caused clean rebuild semantic/byte drift.
  - canonical existing artifact could replace fresh projection truth.
  - single-lineage contrasts could classify direction despite lacking independent support.
  - execution profile mismatch could still form a matched contrast.
- GREEN:
  - `uv run pytest tests/test_parameter_learning.py -q` -> `12 passed`
  - `uv run pytest tests/test_parameter_learning.py tests/test_native_evidence_replay.py tests/test_adaptive_shadow_queue.py tests/test_research_spine_contracts.py -q` -> `71 passed`
- Residual non-A5 fixture failure:
  - `uv run pytest tests/test_parameter_learning.py tests/test_native_evidence_replay.py tests/test_adaptive_shadow_queue.py tests/test_isolated_shadow_plan_replay.py -q` -> `64 passed / 2 failed`
  - Failures are existing isolated-shadow committed proposal/runner receipt fixture validation errors, outside A5 allowed surface.
- Remaining P0/P1: pending independent fixed-SHA review.

## Repair-1 receipt

- Status：`REPAIR_1_COMPLETE / READY_FOR_REREVIEW`。
- Fixed P1：缺失／空白 lineage 一律得到 `INSUFFICIENT_EVIDENCE`；direction fixtures均提供有效 lineage。
- Fixed P1：parameter-learning、native replay 與 adaptive shadow support 共用完整 canonical execution-profile identity，profile 任一欄位不等價不再形成 matched contrast。
- Fixed P1：learning artifact 現驗證 exact top-level keys、identity/provenance、counts/list parity、contrast ID及低／高 observation/evidence refs；collision/tamper不會取代 fresh recompute truth。
- Repair verification：`50 passed` targeted parameter-learning/native-replay/adaptive-shadow tests；`git diff --check` pass。
- Remaining P0/P1：等待 fixed-SHA independent re-review；Repair 自身未發現未關閉 P0/P1。
