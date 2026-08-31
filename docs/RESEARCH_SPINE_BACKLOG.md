# NEW-TOP10 Research Spine Backlog

更新：2026-08-31

狀態：`CURRENT DOMAIN EXECUTION ORDER / A0_ACCEPTED / A1_MAINLINE_ACCEPTED / A2_MAINLINE_ACCEPTED / A3_AWAITING_SEPARATE_OWNER_ADMISSION`

Repository：`bluemaple18-home/NEW-TOP10`

母卡：[#1 CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1](https://github.com/bluemaple18-home/NEW-TOP10/issues/1)

> 本檔是 NEW-TOP10 Research Spine 的本地施工排序。
>
> AI Core 的共用架構與治理 canonical authority 是 `aicore/docs/ai-core-backlog.md`，pinned remote baseline 為 `c896cbff126a57384f5f436b80ceaa2e14a22999`；dated backlog、舊 work cards、reading maps 與實驗只可作 historical evidence。
>
> GitHub Issues 是可執行工作卡；本檔負責依賴順序、admission gate 與 current frontier。不得掃描 Issue 後自行跳卡。

---

## 1. Current unique frontier

### Current arbitration (2026-08-31)

`#2 A0 = COMPLETE / ACCEPTED`。`#3 A1 = COMPLETE / MAINLINE_ACCEPTED`，其 PR #12 canonical merge SHA 為 `0b39937399eddd0535372ece51ddc25bc38fe6a6`。`#4 A2 = COMPLETE / MAINLINE_ACCEPTED / DIRECT_FF_MAIN`：原 candidate `3f7347f30b274201e5c66f649e5919de16d1f6e9` 的 mainline acceptance 發現 run artifact `topic_runs` membership omission／duplicate P1，已由 `5edd87e7df75bb44517f6c2b46d48780cf3476f2` 修復並直接 fast-forward 至 `main`（無 PR）；獨立 fixed-SHA re-review 為 `GO / no P0/P1`，驗證為 `149 passed` 與 `git diff --check` pass。Issue #4 保持 `OPEN / REMOTE_CLOSEOUT_PENDING`。Research frontier 現為 `#5 A3 = BLOCKED / AWAITING_SEPARATE_OWNER_ADMISSION`，不得自行派工或開始 A3；`#6–#8 A4–A6` 均維持 `BLOCKED / NOT_STARTED`。

`#9` 保持 `OPEN / LONG-TERM HARDENING`，不阻擋 read-only A0；Research lane（含 A0/research）不得執行 scheduler、publish 或 production mutation。#9 未來若需 operational hardening，須另行取得對應授權。`#10` 等待 2026-08-31 17:30（Asia/Taipei）natural-run observation；該 observation 未完成前不得宣稱 close 或 promotion。

目前沒有可自行派工的 Research Spine 子卡；唯一 frontier 是 A3 的另行 Owner admission：

- [x] [#2 A0 — Precheck and Prior Art](https://github.com/bluemaple18-home/NEW-TOP10/issues/2) — `COMPLETE / ACCEPTED`
- [x] [#3 A1 — Canonical Identity and Parameter Catalog](https://github.com/bluemaple18-home/NEW-TOP10/issues/3) — `COMPLETE / MAINLINE_ACCEPTED`；PR #12 merge=`0b39937399eddd0535372ece51ddc25bc38fe6a6`；Issue #3=`OPEN / REMOTE_CLOSEOUT_PENDING`

A3 未取得另行 Owner admission 前，下列卡均不得開始：

- [x] [#4 A2 — ExecutionIntent and Immutable Receipt](https://github.com/bluemaple18-home/NEW-TOP10/issues/4) — `COMPLETE / MAINLINE_ACCEPTED / DIRECT_FF_MAIN`；`main@5edd87e7df75bb44517f6c2b46d48780cf3476f2`；Issue #4=`OPEN / REMOTE_CLOSEOUT_PENDING`
- [ ] [#5 A3 — Legacy Migration and Reconciliation](https://github.com/bluemaple18-home/NEW-TOP10/issues/5) — `BLOCKED / AWAITING_SEPARATE_OWNER_ADMISSION`；依賴 #3、#4 已滿足，但尚未 admission
- [ ] [#6 A4 — Rebuildable Ledger and Observations](https://github.com/bluemaple18-home/NEW-TOP10/issues/6) — `BLOCKED / NOT_STARTED`；blocked by #5
- [ ] [#7 A5 — Matched Learning Projection](https://github.com/bluemaple18-home/NEW-TOP10/issues/7) — `BLOCKED / NOT_STARTED`；blocked by #6
- [ ] [#8 A6 — Deprecation, Rebuild and Bridge Removal Gates](https://github.com/bluemaple18-home/NEW-TOP10/issues/8) — `BLOCKED / NOT_STARTED`；blocked by #5、#6 and #7

Card B（Decision Projection）與 Card C（Control Cutover）尚未 admission；不得因 Card A 子卡存在就提前施工。

### A0 evidence bundle（10 files，historical acceptance input）

A0 的已接受交付以同一版本／日期的下列十檔 evidence bundle 審閱；缺檔不得以狀態文案替代：

1. `01-current-authority-map.md` — execution authority、reconciliation predecessor、canonical backlog 與 baseline manifest。
2. `02-current-identity-map.md` — mission、lane、card、owner 與 identity grain。
3. `03-reader-writer-and-terminal-boundary-inventory.md` — reader/writer、terminal state 與 boundary ownership。
4. `04-dataset-and-features-lineage-map.md` — dataset、`features.parquet`、coverage、hash、validation 與 lineage。
5. `05-market-evidence-and-provider-semantics-map.md` — market evidence、provider selection、fallback 與 OMI prior art。
6. `06-ai-core-and-prior-art-matrix.md` — AI Core current seams 與 OMI prior-art 的 `USE_AS_IS`／`CONFIGURE`／`WRAP`／`ADAPT`／`COPY_CODE`／`CUSTOM_REQUIRED`／`REJECT` 決策。
7. `07-schema-and-migration-hazards.md` — schema、migration、compatibility bridge 與 rollback hazards。
8. `08-open-questions-and-measured-gaps.md` — UNKNOWN、UNPINNED_RUNTIME_ARTIFACT、open questions 與 measured gaps。
9. `09-a1-admission-and-a2-prerequisites.md` — 僅記錄 A1 admission criteria 與 A2 prerequisites，不執行 A1/A2。
10. `10-upstream-ai-core-proposals.md` — 只提出需回推 AI Core 的 proposals，不建立 local authority。

所有 lanes 必須使用 structured claim/evidence contract：每個 claim 至少包含 `claim_id`、`subject`、`claim`、`authority`、`scope`、`as_of`、`evidence_ref`、`evidence_hash`、`status`（`CONFIRMED`／`UNKNOWN`／`UNPINNED_RUNTIME_ARTIFACT`／`CONFLICT`）、`owner` 與 `next_action`。缺個別 evidence 時標示 `UNKNOWN` 或 `UNPINNED_RUNTIME_ARTIFACT` 並繼續；只有 governing-authority conflict、identity-grain ambiguity、terminal-boundary ambiguity 或 required runtime mutation 才 stop。Integrator 是唯一 cross-lane synthesis writer；各 lane 不得自行改寫 cross-lane synthesis。

---

## 2. Governing architecture and authority order

權威順序如下，後者不得推翻前者：

1. Reconciliation predecessor／observed baseline：`origin/main@0baeef6f7bd62c521e46a782b28a83940855d59f`；不是 A0 execution base。A0 execution base 必須是 reconciliation 進入 `origin/main` 後的新 SHA，並由 A0 baseline manifest 釘選。
2. AI Core canonical backlog：`aicore/docs/ai-core-backlog.md`（pinned remote baseline `c896cbff126a57384f5f436b80ceaa2e14a22999`）。
3. NEW-TOP10 parent architecture contract：Issue #1。
4. 本檔的 execution order 與各子卡 scope／acceptance。
5. dated backlogs、old `.work`、`aeae2c3` historical draft/reference，以及 OMI `lulu930128/open-market-intelligence@2d54c5983b8597babd804110f022a5f299e45a9d`（`prior_art_only`）。

歷史 evidence 不得默默恢復為 authority；`aeae2c3` 不 merge、不作 execution base。

AI Core canonical backlog 之外，A0 必須閱讀並引用其 pinned baseline 下仍有效的 [Personal Mode runtime/safety prior-art receipt](https://github.com/bluemaple18-home/aicore/blob/main/docs/research/PERSONAL-MODE-RUNTIME-SAFETY-PRIOR-ART-20260825.md) 與 [prior-art implementation admission rule](https://github.com/bluemaple18-home/aicore/blob/main/rules/24-prior-art-implementation-admission.md)。dated backlog 僅列為 historical evidence，不得取代上述 current canonical reading set。

### 2026-08-25 rebaseline compatibility gate

A0 必須正面處理 AI Core current locks：

- borrow/configure/wrap/adapt before custom implementation；
- 不建立第二套 Codex／Claude runtime 或通用 lifecycle engine；
- runtime-specific IDs 是 `RUNTIME_FACT`，不得直接升格為 Mission／research authority；
- 沒有 measured unmet need，不新增共用 authority ledger／registry／FSM／database；
- 舊 canonical-owner、work-event、registry-projection 等工作只作 evidence，除非 current backlog 重新 admission。

因此，NEW-TOP10 的 Research Ledger 只有在 A0 已證明以下條件並完成各卡獨立 admission 時才可進 A1–A6：

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
FRONTIER: #5 A3 separate Owner admission
A0: COMPLETE / ACCEPTED
A1: COMPLETE / MAINLINE_ACCEPTED (PR #12 merge 0b39937399eddd0535372ece51ddc25bc38fe6a6)
A2: COMPLETE / MAINLINE_ACCEPTED / DIRECT_FF_MAIN (main 5edd87e7df75bb44517f6c2b46d48780cf3476f2; Issue #4 OPEN / REMOTE_CLOSEOUT_PENDING)
A3: BLOCKED / AWAITING_SEPARATE_OWNER_ADMISSION
A4–A6: BLOCKED / NOT_STARTED
NOT ADMITTED: Card B / Card C
```
