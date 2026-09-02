---
id: DECIDE-NEW-TOP10-BC-CP2-R14-ADMISSION
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: owner-mainline-admission-decision
risk: critical
model: gpt-5.6-sol
reasoning: high
production_change_allowed: false
runtime_change_allowed: false
network_allowed: false
---

# BC-CP2 R14 admission decision

## 工作名稱 → 正在做什麼 → 現在狀態

`R14 Admission Decision` → 判定一個已註冊的 R13 forward bundle 之後，是否存在能實質推進 Entry-Regime feasibility 的最小 R14 → `OWNER_AUTHORIZED / READY_FOR_READ_ONLY_DECISION`

## Root question

R13-R2 exact bundle 已成為 committed evidence，R13-R5 R1 authority已 `REVIEW_GO`。在 historical corpus永久 `NON_ADMISSION`、h20 overlap-component grain與三角色split不變的前提下，下一個新交易日的單次 forward capture、或一個 bounded自然累積計畫，是否足以成為有決策價值的 R14；還是它只會造成無期限等待而無法接近 capacity gate？

## Fixed authority

- Main fixed HEAD：`0e39b550a3b1df502bef350447521037a54254af`。
- R13 authority CLI：`app/research/r13_forward_receipt_authority.py`；預期 `REGISTERED_FORWARD_BUNDLE_VERIFIED / downstream_authority=NONE`。
- R13 re-review：`docs/evidence/REVIEW-NEW-TOP10-BC-CP2-R13-R5-COMMITTED-BUNDLE-AUTHORITY/re-review-r1.md`。
- V2 feasibility contract：`docs/tasks/2026-09-01_CARD-NEW-TOP10-ENTRY-REGIME-COHORT-CURRENT-BASELINE-FEASIBILITY-V2.md`。
- Entry-Regime architecture：`docs/architecture/entry_regime_cohort_replay_v1.md`，包含 h20、overlap component、global chronological split、雙 embargo與 `n_min`。
- R11/R12/R13 evidence與 forward receipt contract只作 committed authority；任何 local runtime current-state claim需重新唯讀驗證。

## 必答問題

1. 一個 R13 bundle解除哪些 blocker、沒有解除哪些 blocker？不得把 registration等同 admission/capacity。
2. 依 `n_min`、development/validation/sealed三角色、h20 overlap與雙 embargo，從目前一個 independent forward observation到可跑 feasibility的理論最小 capture數與最小 trading-day span為何？必須列公式、假設與保守下界；不得用 raw dates/stock rows冒充independent components。
3. 每日連續 capture是否因holding interval相交而只形成少數/單一 overlap component？若是，R14不得把「每天收一筆」宣稱成線性capacity增長。
4. 目前本機是否已有新的 completed trade date與fresh features/events/universe/authority可供下一次真 forward capture？只准讀 date/status/schema/hash metadata，不得讀 outcome/target/performance。
5. R14若 GO，必須精確定義單張執行卡能產生的decision value、停止條件、累積里程碑、registration方式與為何不是futureware；若無法，應明確NO-GO並把本鏈移出active frontier。

## Candidate forks

- `GO_R14_SINGLE_NEXT_DATE_FORWARD_CAPTURE_CARD`：只在下一筆能解除明確、可量測的 authority gap時可選。
- `GO_R14_BOUNDED_FORWARD_ACCUMULATION_CONTRACT_CARD`：只在存在有限上限、里程碑與合理時間跨度，且不需scheduler/registry/new runtime時可選。
- `DEFER_R14_FRESH_COMPLETED_DATE_NOT_AVAILABLE`：唯一 blocker只是尚無新 completed date，且R14本身已有決策價值時可選。
- `NO_GO_R14_INSUFFICIENT_DECISION_VALUE`：單次/bounded累積不能在合理邊界內接近capacity，或只是把等待包裝成工作。
- `BLOCKED_R14_AUTHORITY_CONFLICT`：committed authority互相衝突，無法安全裁決。

## 允許範圍

- 唯讀檢查上述 docs/source/tests、Git committed state、R13 verifier結果。
- 唯讀檢查 local features/events/universe與completed-date authority的 date/status/schema/hash metadata；不得讀 outcome-bearing columns。
- 產出 `docs/evidence/BC-CP2-R14-ADMISSION/01-admission-decision.md`。

## 禁止範圍

- 不執行 capture、registration、ranking generation、replay、capacity/split、benchmark、training或outcome/sealed access。
- 不修改 code/tests/config/workflow/ranking/data/bundle/既有 evidence；不新增scheduler、registry、ledger、database、canonical writer或runtime。
- 不改 h20、D+1、taxonomy、roles、split、embargo、component grain或 `n_min`來製造GO。
- 不准入 Entry-Regime feasibility、preregistration、historical corpus、B0 Phase 2、B1、C1或production。
- 不 commit、push、merge、deploy或external write。

## 驗收

- 唯一 verdict取自 candidate forks，並清楚列 root question／blocker／candidate fork／current state／next step／waiting condition／limits。
- 明確區分 confirmed facts、derived lower bounds與assumptions；若時間下界過長，必須誠實判定是否仍有decision value。
- 列 `why_not_less`、`why_not_more`、`do_not_absorb`與停止/rollback path。
- 若GO，下一張卡spec需無歧義；若NO-GO，指出主線應回哪個已准入/可裁決frontier，而不是默認等待。
- `git diff --check`通過；changed-files allowlist只有本decision evidence（task card由Mainline預先建立）。
