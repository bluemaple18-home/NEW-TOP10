---
id: CARD-NEW-TOP10-ENTRY-REGIME-COHORT-ARCHITECTURE-DECISION-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: architecture-decision
risk: critical
model: gpt-5.6-sol
reasoning: high
cycle: 21
production_change_allowed: false
runtime_change_allowed: false
network_allowed: false
---

# Entry-Regime Cohort Architecture Decision V1

## Root question

Exact-holding-regime h20 已正式 NO-GO 後，如何保留 h20 與 as-of 安全性，同時建立可驗證、非 post-hoc、不中途改 production 的 regime-conditioned research contract？

## 固定證據

- `docs/evidence/CARD-NEW-TOP10-EXACT-REGIME-EVIDENCE-PHASE-CLOSURE-V1/closure.json`
- current：81 episodes、0 h20-safe exact identities；固定 scope 最長 8 日。
- legacy：598 trade days、139 episodes、0 h20-safe exact identities；authority 不可 admission。

## 候選

1. 保持 entire-holding exact regime：維持 NO-GO。
2. 縮短 horizon：改變原研究目標，不得默認採用。
3. 合併 episode／忽略 transition／base-only：可能隱藏語意放寬，不得默認採用。
4. Entry-regime cohort：ranking/entry 時點使用 as-of exact identity；holding 可跨 regime，完整記錄 transition path，h20 outcome歸因於 entry cohort。

## 必答契約

- selection eligibility、outcome attribution、transition diagnostics、promotion gate 必須分離。
- entry identity只能使用 ranking/entry 當下可知資料；future regime path只能作 outcome diagnostics。
- 不得把 cohort attribution宣稱為 entire-holding exact-regime causal evidence。
- 不得自動沿用舊 episode split、sealed reuse或 multiple-testing authority。
- 明確定義 overlap、embargo、sealed split、最低 cohort樣本與 fail-closed條件。

## 允許產出

- `docs/architecture/entry_regime_cohort_replay_v1.md`
- `docs/evidence/CARD-NEW-TOP10-ENTRY-REGIME-COHORT-ARCHITECTURE-DECISION-V1/decision.json`
- 必要的離線 verifier與tests。

## 禁止

- runtime、ranking、model、queue、scheduler、production、raw data、回填、replay執行。
- 修改既有 regime taxonomy 或重寫舊 evidence。

## 決策狀態

- `SELECT_ENTRY_REGIME_COHORT_FOR_FEASIBILITY`
- `KEEP_CLOSED_NO_SAFE_SUCCESSOR`
- `BLOCKED_EVIDENCE_OR_CONTRACT_CONFLICT`

## Frontier

- `ERCA-S01`：兩個獨立唯讀分析：方案設計與反證；`traces_to`: root question。
- `ERCA-S02`：整合 architecture contract＋machine-readable decision；`blocked_by`: `ERCA-S01`。
- `ERCA-S03`：獨立 Review；`blocked_by`: `ERCA-S02`。
- successor implementation只允許做 feasibility audit，不得直接 replay。

## 驗收

- closure evidence hash-bound且 committed。
- 選定方案必須同時保留 h20、as-of、transition可觀測、research-only。
- 明確拒絕 future leakage、false causal claim、split reuse與 promotion shortcut。
- verifier、tests、`git diff --check`通過；無 runtime diff。
