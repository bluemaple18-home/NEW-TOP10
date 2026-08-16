---
id: CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: implementation
risk: high
model: gpt-5.6-terra
reasoning: high
cycle: 22
production_change_allowed: false
runtime_change_allowed: false
network_allowed: false
---

# Entry-Regime Cohort H20 Feasibility Audit V1

## 工作名稱 → 正在做什麼 → 現在狀態

`Entry-Regime Cohort H20 Feasibility Audit V1` → 建立 outcome-free cohort capacity 與 split 可行性證據 → `READY_FOR_IMPLEMENTATION`

## Root question

在不計算任何報酬、不開封 sealed outcome、不改 production 的前提下，current reconciled authority 是否有足夠的 entry-regime cohort 獨立樣本，能安全進入 h20 preregistration？

## 固定 authority

- `docs/evidence/CARD-NEW-TOP10-ENTRY-REGIME-COHORT-ARCHITECTURE-DECISION-V1/decision.json`
- `docs/architecture/entry_regime_cohort_replay_v1.md`
- 只接受 current reconciled authority；legacy 不得 pooling。
- h20、D+1、ranking-date as-of exact identity固定。

## Slice

### ERCF-S01：唯讀 inventory 與契約鎖定

- 找出 canonical ranking-date inventory、current regime history與 market calendar來源。
- hash-bind ranking/model/config/universe/top-N、regime/taxonomy/calendar與 architecture decision。
- selection只能讀 ranking date `D` 當下可知資料。

### ERCF-S02：全域 split capacity

- 建立 `entry-cohort-calendar-split.v1` 的單一全域 chronological allocation。
- development→validation、validation→sealed都做 outcome-interval purge。
- 每個邊界 embargo至少20個 market trade days。
- `[ranking_date, entry_date, exit_date]` 不得跨 role。

### ERCF-S03：相依性與 cohort capacity

- 統計 grain固定為 `ranking_date × scenario × top-N portfolio`。
- holding interval相交者合併為 overlap component。
- 回報 cohort × role 的 selection、calendar/path completeness、exclusion與 independent component count。
- Future regime path只能作 availability/描述性診斷，不能影響 selection或 split。

### ERCF-S04：決策、驗證與 Review

- 只允許 `FEASIBLE_FOR_PREREGISTRATION`、`NO_GO_INSUFFICIENT_ENTRY_COHORT_CAPACITY`、`BLOCKED_EVIDENCE_OR_CONTRACT_CONFLICT`。
- verifier、負向 tests、`git diff --check`與獨立 Review全部通過才可整合。

## 禁止資料與操作

- 不讀取或輸出 return、PnL、win rate、Sharpe、alpha、promotion score或任何 outcome metric。
- 不開 sealed outcome，不沿用舊 episode split／sealed registry／multiple-testing authority。
- 不寫 raw data，不發 network request，不改 runtime、ranking、model、queue、scheduler或 production。
- 不用 future path決定 cohort、eligibility、exclusion、權重、參數或停止條件。

## Fail-closed gates

- authority/source hash漂移、未 committed或 lineage不完整即 blocked。
- ranking date重複／缺失、D row缺失、UNKNOWN、transition、`as_of_date != D`即結構化排除或 blocked；不得 fallback latest row。
- D+1/h20 calendar不足、跨 role、embargo不足20、split間 outcome interval重疊即 blocked。
- raw date／個股數不得冒充 independent n。
- `n_min=max(20, ceil(log2(M/0.05)))`；至少一個事前固定 cohort在 development、validation、sealed capacity都達標才可 GO。
- sealed slice只能建立 freshness/hash receipt，本卡不得讀其 outcome。

## 允許產出

- `app/research/entry_regime_cohort_feasibility.py`
- `tests/test_entry_regime_cohort_feasibility.py`
- `docs/evidence/CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1/feasibility.json`
- 必要的純離線 fixture／契約文件；不得修改 production path。

## 驗收

- 結果 deterministic、portable、canonical JSON，沒有 timestamp或絕對路徑。
- 所有輸入 committed/hash-bound；working tree drift會 fail closed。
- tests證明 future path不能改 selection、舊 split不能 reuse、雙 boundary purge/embargo、overlap component與 false GO拒絕。
- evidence只含 capacity、coverage、exclusion、hash與 split metadata，零 outcome metric。
- reviewer無 P0/P1；main integration後重跑 verifier與聚焦 tests通過。
