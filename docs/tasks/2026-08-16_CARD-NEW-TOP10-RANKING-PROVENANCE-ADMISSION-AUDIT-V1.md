---
id: CARD-NEW-TOP10-RANKING-PROVENANCE-ADMISSION-AUDIT-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: evidence-audit
risk: high
model: gpt-5.6-terra
reasoning: high
cycle: 23
production_change_allowed: false
runtime_change_allowed: false
network_allowed: false
---

# Ranking Provenance Admission Audit V1

## 工作名稱 → 正在做什麼 → 現在狀態

`Ranking Provenance Admission Audit V1` → 稽核歷史 ranking 產生當下是否已固定完整 provenance → `READY_FOR_IMPLEMENTATION`

## Root question

目前 h20 entry-cohort feasibility 被 model/config/universe/top-N provenance 阻擋。既有 committed artifacts 是否能證明每個 ranking date 的 artifact、producer/model、config、universe與top-N在產生當下已被 immutable 綁定？

## 固定輸入

- `docs/evidence/CARD-NEW-TOP10-ENTRY-REGIME-COHORT-H20-FEASIBILITY-AUDIT-V1/feasibility.json`
- `docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-AVAILABILITY-AUDIT-V1/availability_audit.json`
- 既有 ranking manifest、產生器 receipts／metadata／analysis artifacts與其 committed bytes。

## Admission contract

每個 scenario × ranking date 必須同時證明：

- ranking artifact path與content hash；
- producer source／entrypoint identity與commit/content hash；
- model artifact/version hash；
- config/signals/parameter hash；
- universe membership或immutable universe snapshot hash；
- top-N與排序／tie-break policy；
- 以上 lineage 在 ranking 產生當下已存在，且可連回同一 artifact identity。

## Fail-closed

- 現在重新 hash 現況只能證明 current bytes，不能回填「當時已固定」。
- protected production surface hash不等於 per-ranking producer/model/config/universe/top-N lineage。
- 檔名、mtime、資料夾名稱、latest model、目前 config或推測預設值均不得補缺欄。
- scenario/date alias、manifest漂移、來源未 committed、證據時間順序不明、跨 artifact identity混接即拒絕 admission。
- 不得讀 return、price、OHLC、PnL、win rate、Sharpe、alpha、target或任何 outcome；不得執行 replay。

## 狀態

- `ADMITTED_RANKING_PROVENANCE_COMPLETE`
- `NO_GO_RANKING_PROVENANCE_INCOMPLETE`
- `BLOCKED_EVIDENCE_CONFLICT`

只有第一個狀態可解除 feasibility 的 provenance blocker；其餘不得修改既有 feasibility status。

## 允許產出

- `app/research/ranking_provenance_admission.py`
- `tests/test_ranking_provenance_admission.py`
- `docs/evidence/CARD-NEW-TOP10-RANKING-PROVENANCE-ADMISSION-AUDIT-V1/admission.json`

## 驗收

- deterministic、portable、canonical JSON；無 timestamp與絕對路徑。
- 所有證據 committed/hash-bound；working drift fail closed。
- 清楚列出每個 scenario/date與六項 lineage欄位的 PROVEN/MISSING/CONFLICT，不以 current defaults補值。
- false admission、latest fallback、現況 hash冒充歷史 provenance、scenario/date alias與 outcome key均有負測。
- verifier、聚焦 tests、`git diff --check`與獨立 Review通過。
