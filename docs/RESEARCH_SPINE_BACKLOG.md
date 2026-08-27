# NEW-TOP10 Research Spine Backlog

更新：2026-08-25

狀態：`CURRENT DOMAIN EXECUTION ORDER / A0 ONLY DISPATCHABLE`

Repository：`bluemaple18-home/NEW-TOP10`

母卡：[#1 CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1](https://github.com/bluemaple18-home/NEW-TOP10/issues/1)

> 本檔是 NEW-TOP10 Research Spine 的本地施工排序。
>
> AI Core 的共用架構與治理 authority 仍以 `bluemaple18-home/aicore` 的 **2026-08-25 current backlog** 為準；舊 AI Core work cards、reading maps 與實驗只可作 evidence，不得覆蓋 current rebaseline。
>
> GitHub Issues 是可執行工作卡；本檔負責依賴順序、admission gate 與 current frontier。不得掃描 Issue 後自行跳卡。

---

## 1. Current unique frontier

目前唯一可派工子卡：

- [ ] [#2 A0 — Precheck and Prior Art](https://github.com/bluemaple18-home/NEW-TOP10/issues/2)

A0 完成並經主線接受前，下列卡全部 blocked：

- [ ] [#3 A1 — Canonical Identity and Parameter Catalog](https://github.com/bluemaple18-home/NEW-TOP10/issues/3) — blocked by #2
- [ ] [#4 A2 — ExecutionIntent and Immutable Receipt](https://github.com/bluemaple18-home/NEW-TOP10/issues/4) — blocked by #3
- [ ] [#5 A3 — Legacy Migration and Reconciliation](https://github.com/bluemaple18-home/NEW-TOP10/issues/5) — blocked by #3 and #4
- [ ] [#6 A4 — Rebuildable Ledger and Observations](https://github.com/bluemaple18-home/NEW-TOP10/issues/6) — blocked by #4 and #5
- [ ] [#7 A5 — Matched Learning Projection](https://github.com/bluemaple18-home/NEW-TOP10/issues/7) — blocked by #6
- [ ] [#8 A6 — Deprecation, Rebuild and Bridge Removal Gates](https://github.com/bluemaple18-home/NEW-TOP10/issues/8) — blocked by #4, #5, #6 and #7

Card B（Decision Projection）與 Card C（Control Cutover）尚未 admission；不得因 Card A 子卡存在就提前施工。

---

## 2. Governing architecture and authority order

施工時依序閱讀，後者不得推翻前者：

1. [AI Core current dated backlog — 2026-08-25](https://github.com/bluemaple18-home/aicore/blob/main/docs/ai-core-backlog-20260825.md)
2. [AI Core canonical backlog index](https://github.com/bluemaple18-home/aicore/blob/main/docs/ai-core-backlog.md)
3. [AI Core Personal Mode runtime/safety prior-art receipt](https://github.com/bluemaple18-home/aicore/blob/main/docs/research/PERSONAL-MODE-RUNTIME-SAFETY-PRIOR-ART-20260825.md)
4. [AI Core prior-art implementation admission rule](https://github.com/bluemaple18-home/aicore/blob/main/rules/24-prior-art-implementation-admission.md)
5. NEW-TOP10 parent architecture contract：Issue #1
6. 本檔的 execution order
7. 各子卡 scope / acceptance
8. 歷史 AI Core / NEW-TOP10 evidence

### 2026-08-25 rebaseline compatibility gate

A0 必須正面處理 AI Core current locks：

- borrow/configure/wrap/adapt before custom implementation；
- 不建立第二套 Codex／Claude runtime 或通用 lifecycle engine；
- runtime-specific IDs 是 `RUNTIME_FACT`，不得直接升格為 Mission／research authority；
- 沒有 measured unmet need，不新增共用 authority ledger／registry／FSM／database；
- 舊 canonical-owner、work-event、registry-projection 等工作只作 evidence，除非 current backlog 重新 admission。

因此，NEW-TOP10 的 Research Ledger 只有在 A0 證明以下條件時才可進 A1–A6：

1. 它是量化研究 domain 的 evidence index / rebuildable projection，不是新的 AI Core runtime authority；
2. immutable spec / intent / receipt / artifact evidence 解決的是 NEW-TOP10 已存在且可量測的 truth gap；
3. 現成 runtime、OpenLineage、MLflow、DVC、Optuna 或既有 NEW-TOP10 結構無法透過 `USE_AS_IS → CONFIGURE → WRAP → ADAPT` 滿足 acceptance；
4. DuckDB 可刪除重建，不能成為 canonical truth；
5. 任何通用 primitive gap 必須回推 AI Core，不得在 NEW-TOP10 永久 fork。

若 A0 判定 parent #1 與 2026-08-25 AI Core rebaseline 有 material conflict，A0 必須停在 architecture decision，不得自行創造 local workaround。

---

## 3. Target Research Spine

```text
ResearchDefinition
        ↓ compile
Canonical Execution Spec
  └─ QuantResearchTrialSpec domain payload
        ↓
Authorization / Eligibility
        ↓
ExecutionIntent
        ↓
Existing Backtest Engine
        ↓
Immutable Execution Receipt
        ↓
Observation Derivation
        ↓
Research Ledger
        ├─ Coverage / Fog Map
        ├─ Learning
        ├─ Failure classification
        ├─ Priority
        ├─ Queue
        └─ PM / Ops
```

### Raw/canonical evidence

- normalized immutable execution specification；
- authorization / eligibility evidence required by the accepted architecture；
- ExecutionIntent；
- terminal execution receipt；
- immutable artifact content / content hashes；
- explicit legacy migration manifest。

### Rebuildable projections

- Observation；
- DuckDB Research Ledger indexes / tables；
- eligibility and failure classification；
- matched learning；
- Fog Map / Coverage；
- Priority / Candidate / Queue；
- PM / Ops summaries。

Core invariant：

> 刪除 DuckDB 後，必須只靠 immutable evidence、versioned definitions/policies 與 migration manifest 重建。新 run 不得靠事後掃 filesystem 猜測實際執行內容。

---

## 4. External prior art — official reading map

| Source | Official documentation | Open-source repository | Intended reuse | Explicit non-goal |
|---|---|---|---|---|
| OpenLineage | [Run Cycle](https://openlineage.io/docs/spec/run-cycle/) | [OpenLineage/OpenLineage](https://github.com/OpenLineage/OpenLineage) | ADAPT run lifecycle、START/terminal events、lineage facets | 不把 OpenLineage backend 當 NEW-TOP10 authority |
| MLflow | [Architecture overview](https://mlflow.org/docs/latest/self-hosting/architecture/overview/) | [mlflow/mlflow](https://github.com/mlflow/mlflow) | ADAPT run metadata / artifact separation | 不把 MLflow tracking DB 當 canonical truth |
| DVC Experiments | [Experiment management source](https://github.com/treeverse/dvc.org/blob/main/content/docs/user-guide/experiment-management/index.md) | [iterative/dvc](https://github.com/iterative/dvc) | ADAPT reproducibility、version provenance、comparison concepts | 不以隱藏 Git refs 取代 Research Spine identity |
| Optuna | [TrialState](https://optuna.readthedocs.io/en/stable/reference/generated/optuna.trial.TrialState.html) | [optuna/optuna](https://github.com/optuna/optuna) | ADAPT Study / Trial / attempt / state ontology | 不導入 optimizer 或 search authority 到 Card A |
| W3C PROV | [PROV-O](https://www.w3.org/TR/prov-o/) | Standard specification | ADAPT Entity / Activity / provenance vocabulary | 無充分理由不建 RDF subsystem |
| Event Sourcing | [Martin Fowler — Event Sourcing](https://martinfowler.com/eaaDev/EventSourcing.html) | Pattern reference | ADAPT immutable facts + rebuildable projections | 不要求每個 subsystem 全面 event-sourced |

A0 的 prior-art matrix 必須逐項給出：

```text
USE_AS_IS
CONFIGURE
WRAP
ADAPT
COPY_CODE
CUSTOM_REQUIRED
REJECT
```

每個 `CUSTOM_REQUIRED` 都要回答：固定版本／固定 acceptance 下，前面每一層為何失敗。

---

## 5. Historical AI Core evidence — evidence only

下列可用來理解舊設計與失敗案例，但不是 2026-08-25 execution authority：

- `docs/task_cards/READING-MAP-AICORE-BACKLOG-20260823.md`
- `docs/task_cards/CARD-AICORE-PRIOR-ART-FIRST-ABSORPTION-20260822.md`
- `.work/CARD-AICORE-UNIFIED-EXECUTION-CONTROL-PLANE-V2-REVIEW-001/result.md`
- `.work/CARD-AICORE-UNIFIED-EXECUTION-CONTROL-PLANE-V2-PHASE1-SCHEMA-CHARACTERIZATION-001/result.md`
- `.work/CARD-AICORE-CANONICAL-OWNER-AUDIT-V1-20260810/result.md`
- `.work/CARD-AICORE-CANONICAL-OWNER-AUDIT-V1-20260810/evidence/canonical-source-map.md`
- `.work/CARD-AICORE-WORK-EVENT-CONTRACT-V1-20260810/result.md`
- `.work/CARD-AICORE-REGISTRY-PROJECTION-V1-20260810/brief.md`
- `.work/CARD-AICORE-REGISTRY-PROJECTION-V1-20260810/evidence/rebuild-receipt.md`
- `.work/CARD-AICORE-CP2-CANONICAL-AUTHORITY-GENERATION-DECISION-20260812/evidence/transaction-contract.md`
- `.work/CARD-AICORE-CP2-CANONICAL-AUTHORITY-GENERATION-DECISION-20260812/evidence/writer-fence-map.md`
- `.work/CARD-AICORE-CP2-CANONICAL-AUTHORITY-GENERATION-DECISION-20260812/evidence/rollback-contract.md`

使用規則：

```text
Historical evidence may inform a decision.
Historical authority may not silently revive.
```

---

## 6. Scope locks for Card A

Card A 不碰：

- priority policy；
- candidate ranking；
- adaptive optimizer / search algorithm；
- queue ordering / execution control；
- daily quota / scheduler redesign；
- backtest mathematics / strategy logic；
- production promotion；
- LightGBM production system；
- UI redesign。

任何 compatibility bridge 都必須保存：

- owner；
- removal condition；
- removal test；
- target removal card / stage。

---

## 7. Monitoring and closeout rule

節省監工模式：

- 不在每個小實作點重審；
- 每張子卡只檢查 architecture contract、authority、scope、acceptance 與 evidence；
- 偏航時才攔截；
- 前置卡未 accepted，不開下一卡；
- 子卡完成不等於母卡完成；
- #8 通過且母卡總驗收完成後，才可關閉 #1。

目前施工指令：

```text
DISPATCHABLE: #2 A0 only
BLOCKED: #3–#8
NOT ADMITTED: Card B / Card C
```
