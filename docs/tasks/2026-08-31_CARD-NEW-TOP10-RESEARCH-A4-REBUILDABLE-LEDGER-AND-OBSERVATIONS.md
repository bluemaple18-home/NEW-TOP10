---
id: CARD-NEW-TOP10-RESEARCH-A4-REBUILDABLE-LEDGER-AND-OBSERVATIONS
status: implementation_complete_review_go_mainline_acceptance_pending
type: implementation
issue: 6
depends_on: [4, 5]
baseline: fc42462a200b36af60016b31131b65ba653aa823
---

# CARD-NEW-TOP10-RESEARCH-A4-REBUILDABLE-LEDGER-AND-OBSERVATIONS

日期：2026-08-31

## 1. Root question

在 A1 canonical identity、A2 execution intent/attempt/receipt 與 A3 immutable migration evidence 已進 main 的前提下，現有 DuckDB ledger、Observation、Eligibility 與 failure-classification seams 是否已足以從同一 immutable corpus deterministic rebuild；若仍有可重現缺口，最小需要補哪一段，才能通過 Issue #6 acceptance，而不讓 DuckDB 或 projection 成為新的 canonical authority？

## 2. Admission 與 current state

- Owner 的「繼續」承接唯一 next frontier；bounded implementation與fixed-SHA independent review均已完成，A4目前為 `IMPLEMENTATION_COMPLETE / REVIEW_GO / MAINLINE_ACCEPTANCE_PENDING`。
- Planning baseline：`fc42462a200b36af60016b31131b65ba653aa823`。
- Issue #6：`OPEN`、無留言；依賴 A2/A3 已滿足。
- Mainline gap audit收斂的兩項原始P1與後續review repair findings均已在fixed candidate關閉；剩餘`P0=0 / P1=0`。
- A5–A6 維持 `BLOCKED / NOT_STARTED`，A4 implementation／review完成不構成其admission。

## 3. Issue #6 scope

Issue #6 要求：

- ledger builder 消費 canonical specs、intents、receipts、artifacts 與 migration manifest；
- 可明確執行的 rebuild；
- Observation derivation，同一 run 可一對多；
- versioned eligibility policy 與 provenance；
- versioned failure-classification projection；
- sealed evidence fail closed；
- deterministic rebuild checks。

Acceptance 是：刪除 ledger DB 後，從相同 corpus 與相同 policy versions 重建，得到相同 canonical IDs、counts 與 projection outputs。Observation 是 derived fact，DuckDB 不是 canonical DB；failure-learning JSON/files 最多是 publication snapshot。

## 4. Existing seam inventory

### 4.1 `app/research/observation_ingest.py`

- 已有 `research-ledger.v1` DuckDB schema、`ingest_corpus()`、`--rebuild`、temporary rebuild與 atomic replace。
- 已 ingest A1 TrialSpecs、A2 intents/attempts/receipts/artifacts/execution units，以及 A3 manifests/dispositions/combo edges/quality reports。
- 已有 content/path identity、CAS、correlation、conflict/rejection 與 transaction boundary。
- `research-observation-identity.v1` 以 executed trial lineage、result unit與 versioned metric/attempt policies衍生 `observation_id`；同一 receipt 可從多個 execution units衍生多個 observations。
- `ledger_snapshot()` 已排除 local provenance path 對 logical snapshot 的影響。

### 4.2 `app/research/eligibility.py`

- 已有 versioned policy loading、policy hash、input corpus hash、ledger snapshot hash、projection identity、reason codes與 eligibility decisions。
- sealed/unknown/invalid lineage 已有 fail-closed路徑；eligibility只決定 evidence能否進下游，不做參數學習。

### 4.3 `app/research/failure_classification.py`

- 已有 versioned failure policy、eligibility projection binding與 deterministic projection identity。
- 只對 eligible observations分類 metrics；non-observation/terminal failure另保留 typed failure facts，不推論參數方向。

### 4.4 Existing tests

- `tests/test_research_ledger.py` 已覆蓋 idempotent ingest、delete/rebuild snapshot equality、copy-path deweight、CAS corruption rollback、failed atomic rebuild保留舊 ledger、invalid/dangling/collision quarantine、A1/A2 correlation及path-independent snapshot。
- `tests/test_research_eligibility_failure.py` 已覆蓋 eligibility reproducibility、sealed/unknown fail closed、legacy/non-observation、versioned activation exclusion、failure classification、policy content identity與invalid policy rejection。
- A3 tests 已覆蓋 migration disposition、authority refs、one-to-many/unresolved與rebuild attribution。

## 5. Mainline gap audit first

現存 seam 已覆蓋 Issue #6 多數表面需求；因此 implementation 前必須先產生 mainline gap matrix：

| Issue requirement | Existing owner/seam | Existing proof | Missing proof or defect | Decision |
|---|---|---|---|---|
| corpus → ledger | `observation_ingest` | directly affected tests | 無新增缺口 | `USE_AS_IS` |
| delete + rebuild | `ingest_corpus(rebuild=True)` | snapshot equality tests | ledger logical snapshot已deterministic；projection artifact bytes受wall-clock timestamp影響 | ledger=`USE_AS_IS`；projection=`ADAPT` |
| one-to-many observations | execution units → observations | ledger tests | 無新增缺口 | `USE_AS_IS` |
| eligibility provenance | `eligibility` | eligibility tests | identity已綁policy/corpus/snapshot，但immutable existing payload可取代fresh computed payload | `ADAPT` |
| failure projection | `failure_classification` | failure tests | existing artifact直接載入，validator只驗schema；可接受forged counts/classifications | `ADAPT` |
| sealed fail-closed | receipt/bundle/stage + eligibility | A2/A3/eligibility tests | 無新增缺口 | `USE_AS_IS` |

### 5.1 Measured P1 gaps

- **P1-A4-001 — deterministic artifact bytes**：同一corpus與policy刪除ledger及eligibility/failure artifacts後重建，兩次`projection_id`相同，但`generated_at`取wall-clock，造成immutable artifact bytes不同。位置為`app/research/eligibility.py` payload materialization與`app/research/failure_classification.py` payload materialization。這違反相同identity可重建相同canonical artifact的契約。
- **P1-A4-002 — forged immutable artifact accepted**：既有eligibility artifact被竄改counts/decisions後，builder只比identity keys並以existing payload取代fresh computed payload；failure builder更直接載入existing payload，且兩者validator主要只驗schema。重跑可接受forged empty/altered decisions/classifications，並可能把不一致資料寫入projection DB tables。

最小scope固定為：

1. 使projection canonical payload不受wall-clock timestamp影響；timestamp須deterministic或明確排除於canonical immutable artifact/identity，且同identity重建exact bytes。
2. fresh recompute payload必須與既有immutable artifact做exact canonical match；不得以existing payload取代computed truth。不同即fail-loud collision/tamper。
3. 強化eligibility/failure schema、projection ID、counts、decision/classification與input/ref consistency validation。
4. DB projection rows在寫入前驗既有projection identity/hash/rows；collision需rollback整筆transaction，不得`INSERT OR IGNORE`掩蓋不同payload。
5. 新增delete ledger + eligibility + failure artifacts的exact-byte end-to-end rebuild gate，並綁入Research Spine verifier。

現成ledger core、A1–A3 ingest/correlation與sealed fail-closed維持`USE_AS_IS`，禁止重寫。

## 6. Authority、identity 與 correlation contract

1. A1 TrialSpec、parameter catalog、dataset bundle與artifact identity是 requested/executed research identity authority。
2. A2 ExecutionIntent → AttemptStarted → terminal receipt是 execution fact與terminal boundary authority。
3. A3 migration manifest/disposition/mapping authority是 legacy evidence如何被遷移的 authority；legacy evidence不得覆寫A1/A2。
4. Observation只能由已驗證的 executed receipt unit + result artifact + executed TrialSpec correlation衍生；不得由 requested intent、path、mtime、latest row或 compatibility output猜測。
5. 一個 run/receipt可有零到多個 observations；每個 observation必須綁定唯一 execution/result unit、receipt、executed trial與source artifact evidence。
6. Eligibility與failure classification是 versioned projections；必須綁 input corpus hash、logical ledger snapshot hash、policy version/hash及上游 projection identity。
7. DuckDB、eligibility/failure JSON與publication snapshots皆可刪除重建，不是 raw truth或canonical writer。

## 7. Assumptions

- **AS-A4-001**：A1–A3 mainline evidence足以作為 rebuild inputs；A4不需要新的 canonical writer。 `traces_to: FR-A4-001, FR-A4-003, SC-A4-001`
- **AS-A4-002**：相同 immutable corpus與相同 policy versions應產生相同 logical IDs/counts/projection payload；local DB path與generated timestamp不得進 semantic identity。 `traces_to: FR-A4-004, FR-A4-007, SC-A4-004`
- **AS-A4-003**：Observation是一對零到多的 derived fact，不是 receipt或artifact的替代 authority。 `traces_to: FR-A4-003, SC-A4-002`
- **AS-A4-004**：Issue引用但本機不存在的 AI Core `.work` receipts只能作 historical/unavailable references；其缺席不阻擋可由 current repo + Issue直接證明的 admission或gap audit。 `traces_to: FR-A4-001, SC-A4-008`

## 8. Minimum sufficient decision

### why_not_less

只驗 DuckDB檔案可重新建立，不足以證明 A1–A3 correlation、canonical IDs/counts、projection policy provenance與sealed fail-closed都可重現；至少需要逐 requirement gap audit與端到端 delete→rebuild→projection comparison。

### why_not_more

repo已有 ledger schema、atomic rebuild、observation derivation、eligibility與failure projections。A4不需要第二個 DB/ledger、event store、runtime authority、universal provenance service或全面 event sourcing。

### do_not_absorb

- 不吸收 A5 matched learning、parameter direction、learning summaries或recommendation logic。
- 不碰 scheduler、provider、features、ranking、publish、production、backtest math、#9/#10或`.work/current`。
- 不引入 MLflow backend、W3C PROV/RDF subsystem、OpenLineage service或新 canonical registry。
- 不把 JSON publication snapshot、DuckDB row或projection receipt提升為raw evidence。

## 9. Functional requirements

- **FR-A4-001**：產生 Issue requirement → existing seam → evidence → gap → decision matrix，先證明缺口再改實作。 `traces_to: Issue#6, AS-A4-001, SC-A4-008`
- **FR-A4-002**：ledger builder只消費通過A1–A3 schema/identity/hash/ref/correlation驗證的immutable corpus；invalid input fail closed且不得partial ingest。 `traces_to: SC-A4-001, SC-A4-006`
- **FR-A4-003**：Observation以executed receipt unit/result artifact/executed trial衍生，支援一個run零到多個observations並保留完整provenance。 `traces_to: AS-A4-003, SC-A4-002`
- **FR-A4-004**：相同corpus與policies的incremental ingest、clean rebuild與delete/rebuild產生相同logical IDs/counts/snapshot。 `traces_to: AS-A4-002, SC-A4-003, SC-A4-004`
- **FR-A4-005**：Eligibility projection綁定policy version/hash、corpus hash、ledger snapshot與reason evidence；sealed、unknown、ambiguous及invalid lineage fail closed。 `traces_to: SC-A4-005`
- **FR-A4-006**：Failure classification綁定classifier policy version/hash與eligibility projection；不得把non-observation或ineligible evidence分類成可學策略結果。 `traces_to: SC-A4-005, SC-A4-007`
- **FR-A4-007**：projection output的semantic identity不受local path、temporary DB name或generated timestamp影響；publication files可重建。 `traces_to: AS-A4-002, SC-A4-004`
- **FR-A4-008**：DuckDB rebuild使用temporary target、完整validation與atomic replace；失敗保留上一份valid ledger。 `traces_to: SC-A4-006`
- **FR-A4-009**：A4不得建立新的authority/DB/runtime seam，且不修改A1–A3 immutable evidence。 `traces_to: SC-A4-001, SC-A4-008`

## 10. Success criteria

- **SC-A4-001**：A1 TrialSpec/bundle、A2 intent/attempt/receipt/artifact與A3 migration refs能端到端correlate；dangling、mismatch或collision在observation前被拒絕。 `traces_to: FR-A4-002, FR-A4-009`
- **SC-A4-002**：fixture證明單一receipt的zero/one/many observation cardinality，且每個observation identity/provenance可重算。 `traces_to: FR-A4-003`
- **SC-A4-003**：同corpus重複ingest不增加semantic evidence weight或重複observations。 `traces_to: FR-A4-004`
- **SC-A4-004**：刪除DuckDB後重建，canonical IDs、table counts、logical snapshot及eligibility/failure projection semantic payload一致。 `traces_to: FR-A4-004, FR-A4-007`
- **SC-A4-005**：sealed/unknown/ambiguous/invalid lineage一律不可eligible；policy content變更產生新projection identity。 `traces_to: FR-A4-005, FR-A4-006`
- **SC-A4-006**：tampered CAS、invalid schema、dangling ref、identity collision或rebuild exception不得留下partial新ledger，且舊ledger仍可讀。 `traces_to: FR-A4-002, FR-A4-008`
- **SC-A4-007**：failure projection只分類eligible strategy observations，並保存classifier/eligibility provenance；不產生A5 learning。 `traces_to: FR-A4-006`
- **SC-A4-008**：gap audit逐項判定`USE_AS_IS / CHARACTERIZE / ADAPT`，沒有measured gap的項目零實作；完整verification與獨立review無未解P0/P1。 `traces_to: FR-A4-001, FR-A4-009, AS-A4-004`

## 11. Vertical slices 與 checkpoints

### Slice A4.1 — Mainline gap audit（COMPLETE）

- 逐項映射 Issue #6、A1–A3 authority、現存 seams與tests。
- 執行現有 focused tests並保存baseline evidence；不修改code。
- checkpoint：已固定`P1-A4-001`與`P1-A4-002`；其餘seams維持`USE_AS_IS`。
- `traces_to: FR-A4-001, SC-A4-008`

### Slice A4.2 — Deterministic projection artifact RED → GREEN

- RED：同corpus/policies分別fresh build、刪ledger+projection artifacts、clean rebuild；IDs相同但eligibility/failure bytes不同。
- GREEN：canonical projection payload的time metadata deterministic或non-canonical化，使相同identity產生exact bytes；projection ID規則保持content-verifiable。
- checkpoint：不得改ledger/observation identity或移除必要provenance；timestamp處理方式必須有validator與rebuild test鎖定。
- `traces_to: FR-A4-004, FR-A4-007, SC-A4-004`

### Slice A4.3 — Immutable artifact與DB collision RED → GREEN

- RED：竄改既有eligibility/failure artifact的counts、decisions/classifications、projection ID或refs；重跑不得接受或以existing取代computed。
- GREEN：fresh computed payload先通過完整schema/id/count/ref validation，再與existing canonical payload exact match；artifact或DB既有資料不同時fail loudly並rollback。
- checkpoint：沿用現有artifact writer與projection tables；若需新table/DB即停止。不得用`INSERT OR IGNORE`掩蓋semantic collision。
- `traces_to: FR-A4-005, FR-A4-006, FR-A4-008, FR-A4-009, SC-A4-005, SC-A4-006, SC-A4-007`

### Slice A4.4 — Exact-byte delete/rebuild gate與verifier binding

- 從同一immutable corpus與固定policies產生first build，保存ledger snapshot與eligibility/failure bytes；刪除ledger及兩類projection artifacts後clean rebuild。
- 比對canonical IDs、counts、logical snapshot與eligibility/failure exact bytes；將此gate綁入既有Research Spine verifier。
- checkpoint：任一unexplained delta、non-determinism或projection authority inversion即NO-GO。
- `traces_to: FR-A4-004..FR-A4-008, SC-A4-003..SC-A4-007`

### Slice A4.5 — Full regression與fixed-SHA review handoff

- 保存exact changed files、RED/GREEN、full regression、diff check與local candidate SHA，再做獨立review；remote equality、push與mainline acceptance須另行取得Owner授權。
- 只修reproducible P0/P1；A4 GO不自動admit A5–A6。
- `traces_to: SC-A4-008`

## 12. TDD contract

1. 先characterize current mainline；現存PASS不是measured gap。
2. 每個implementation change前必須有單一責任RED fixture。
3. GREEN只允許最小owner seam修復；禁止順手重構或schema擴張。
4. 直接受影響測試通過後，才跑A1–A4完整regression。
5. hostile cases至少包含correlation mismatch、one-to-many identity、sealed fail-closed、tamper/collision、delete/rebuild與atomic failure。

## 13. Locked bounded implementation files

- `app/research/eligibility.py`
- `app/research/failure_classification.py`
- `tests/test_research_eligibility_failure.py`
- `tests/test_research_ledger.py`（只新增delete/rebuild end-to-end gate時）
- `scripts/verify_research_spine_batch.py`（只加入A4 verifier binding）
- 本task card與必要current-status docs

`app/research/observation_ingest.py`、ledger schema與A1–A3 ingest/correlation目前不在implementation scope；除非新RED證明上述P1無法在projection owner seam修復，否則不得修改。任何額外file先回報measured need。

## 14. Verification contract

Focused baseline/gap audit：

```bash
.venv/bin/python -m pytest \
  tests/test_research_ledger.py \
  tests/test_research_eligibility_failure.py \
  tests/test_research_legacy_migration.py -q
```

Acceptance regression：

```bash
.venv/bin/python -m pytest \
  tests/test_research_spine_contracts.py \
  tests/test_research_dataset_bundle.py \
  tests/test_autonomous_research_receipts.py \
  tests/test_research_receipt_store.py \
  tests/test_research_legacy_migration.py \
  tests/test_research_ledger.py \
  tests/test_research_eligibility_failure.py \
  tests/test_research_spine_daily_cutover.py \
  tests/test_research_batch_owner.py \
  tests/test_isolated_external_review_backfill.py \
  tests/test_isolated_daily_backfill.py \
  tests/test_shadow_replay_authority_reconciliation.py \
  tests/test_strategy_component_registry.py \
  tests/test_strategy_archetype_evidence_map.py -q

rg -n "FR-A4-|SC-A4-|AS-A4-|traces_to" \
  docs/tasks/2026-08-31_CARD-NEW-TOP10-RESEARCH-A4-REBUILDABLE-LEDGER-AND-OBSERVATIONS.md

git diff --check
```

本次local candidate evidence需包含：baseline SHA、gap matrix、RED/GREEN command/result、delete/rebuild comparison、exact files、local candidate SHA、independent review與remaining P0/P1。remote equality、push與mainline acceptance不在本次「繼續」授權內，須另行取得Owner明示授權後才能執行或宣稱。

## 15. Historical / unavailable references

Issue #6 引用下列 AI Core `.work` receipts，但在 baseline `fc42462a200b36af60016b31131b65ba653aa823` 的本機 repo 均不存在：

- `.work/CARD-AICORE-REGISTRY-PROJECTION-V1-20260810/brief.md`
- `.work/CARD-AICORE-REGISTRY-PROJECTION-V1-20260810/evidence/rebuild-receipt.md`
- `.work/CARD-AICORE-REGISTRY-PROJECTION-V1-20260810/evidence/verification.md`
- `.work/CARD-AICORE-CANONICAL-OWNER-AUDIT-V1-20260810/result.md`

這些只能列為`historical_reference / unavailable_locally`，不得當current authority、不得以記憶重建其內容，也不得阻擋可由Issue #6與current repo直接證明的A4 admission/gap audit。若未來取得原文，只能作prior-art comparison，不能覆蓋A1–A3 mainline authority。

## 16. Stop conditions

遇到下列任一情況立即停止並回報exact evidence：

1. A1–A3 identity、artifact、terminal或migration authority發生material conflict。
2. Observation必須靠path/mtime/latest row/requested-only facts猜出executed lineage。
3. deterministic rebuild需要改寫或刪除immutable corpus。
4. DuckDB/projection需要升格成canonical writer或第二authority。
5. 修復需要第二DB/ledger/runtime、A5 learning、scheduler/provider/features/ranking/publish/production/backtest math或#9/#10 mutation。
6. sealed/unknown/ambiguous evidence可經任一路徑進入eligible observation。
7. rebuild出現unexplained canonical ID/count/projection drift，或failure留下partial ledger。
8. main/Issue #6 scope變更造成material conflict，或出現reproducible P0/P1。

## 17. Rollback / remove

- DuckDB、eligibility/failure projections與publication snapshots都可直接刪除，再由同一immutable corpus與固定policies重建。
- A4 adaptation必須versioned；rollback是停止使用新policy/schema adapter並以先前accepted version clean rebuild，不改寫A1–A3 evidence。
- 若新增derived table/field，其removal test必須證明移除後A1–A3 ingest與既有projection仍可由corpus重建。
- 不以備份DB作canonical rollback source；rollback authority仍是immutable evidence + versioned definitions/policies。

## 18. Current status

`A4 = IMPLEMENTATION_COMPLETE / REVIEW_GO / MAINLINE_ACCEPTANCE_PENDING`。

### 18.1 Fixed candidate 與 verification

- Fixed candidate SHA：`ba6df2c7593641d1b446ef556aec2857c7760326`。
- Independent final Reviewer：`GO`；remaining findings：`P0=0 / P1=0`。
- Targeted hostile verification：`10 passed`。
- A1–A4與downstream compatibility regression：`206 passed`。
- `git diff --check`：`PASS`。
- Candidate目前只存在local branch；`NOT PUSHED / NOT MERGED / NOT CANONICAL`。Mainline acceptance與任何remote write仍須另行授權。

### 18.2 Repair generations 與finding closure

- Repair generation 1關閉：legacy DB decision/reason exact symmetric set缺口、no-run orphan rows、DB collision先於artifact publication、rollback不得留下partial derived artifact，以及舊`generated_at` v1 artifact與deterministic v2 projection的side-by-side immutable migration策略。
- Repair generation 2關閉：TOCTOU cleanup不得因precheck時target不存在，就刪除其後由concurrent writer建立的artifact；cleanup現在只接受本次writer成功回傳`CREATED`作為ownership evidence。
- Eligibility與failure projection皆保留fail-loud collision、DB transaction rollback、exact-byte v2 rebuild與舊v1 immutable bytes不改寫契約。

### 18.3 Mainline 與operational boundary

- Issue #6仍為`OPEN / UNMODIFIED`；尚未close或留言。
- A5–A6維持`BLOCKED / NOT_STARTED`，不得由A4 Review GO自動啟動。
- Operational Issue #10為獨立觀測lane；A4證據不得推論其已完成、已關閉或改變其狀態。
- 未觸碰`.work/current`、scheduler、provider、features、ranking、publish、production或backtest math。

下一步僅為fixed candidate mainline acceptance；在另行授權前不得push、merge、關閉Issue #6或啟動A5–A6。
