# CARD-NEW-TOP10-RESEARCH-A2-EXECUTION-INTENT-AND-RECEIPT

日期：2026-08-31
狀態：`A2_LOCAL_CANDIDATE_IMPLEMENTED / REVIEW_PENDING`
GitHub authority：Issue #4 `CARD-NEW-TOP10-RESEARCH-A2-EXECUTION-INTENT-AND-RECEIPT`（唯讀觀察：`OPEN`）
Execution baseline：`origin/main@c738f3eed4d62757835a4036a99aa43d8288c953`
工作模式：`STRICT / CORE_BOUNDED / EXISTING_LIFECYCLE_ADAPTER_ONLY`

## 1. Root question

NEW-TOP10 能否只延伸既有 `ExecutionIntent → AttemptStarted → immutable terminal receipt` seam，讓每個受控 attempt 在執行前綁定 A1 requested dataset bundle evidence，並在受控 resolution point 以第一方證據綁定 executed bundle、terminal cause、artifacts 與 failure facts；同時不改 backtest math、不從 filesystem 猜測事實，也不建立第二套 lifecycle／ledger／registry／DB？

本卡是已由 Owner 接受的 bounded implementation plan，但本次授權只允許建立 task card。任何 code、test、schema、runtime mutation 仍為 `NOT STARTED`，必須另行取得實作授權。

## 2. Authority、admission 與 pinned evidence

### 2.1 Authority order

1. Owner 於 2026-08-31 明示批准 A2 admission，但限制為「只建立 bounded task card，不開始實作」。
2. Issue #4 `CARD-NEW-TOP10-RESEARCH-A2-EXECUTION-INTENT-AND-RECEIPT`：ExecutionIntent、run/attempt identity、immutable terminal receipt、requested/executed truth、artifact/failure evidence 與 orphan detection 的 governing scope。
3. A1 canonical mainline：PR #12 merge `0b39937399eddd0535372ece51ddc25bc38fe6a6`；A1 closeout reconciliation `c738f3eed4d62757835a4036a99aa43d8288c953`；A1 dataset bundle contract與 validator為 `USE_AS_IS`。
4. `.work/CARD-NEW-TOP10-RESEARCH-A0-MAPPING-20260830/09-a1-admission-and-a2-prerequisites.md`：`A0-INT-A2-001`～`003`。
5. `.work/CARD-NEW-TOP10-RESEARCH-A0-MAPPING-20260830/03-reader-writer-and-terminal-boundary-inventory.md`：既有 authority、writer 與 terminal boundary evidence。
6. 現有 runtime seam：`app/research/contracts.py`、`app/research/receipt_store.py`、`app/research/run_receipts.py`、`scripts/run_autonomous_research.py` 與其受影響 tests。

較低層 evidence 不得擴張 Owner boundary。dated backlog 或歷史 `.work` 僅能提供 evidence，不能推翻 current Owner decision；本卡也不自行修改 backlog、frontier 或 Issue #4 remote state。

### 2.2 Admission disposition

```text
A0 = COMPLETE / ACCEPTED
A1 = COMPLETE / MAINLINE_ACCEPTED
A2 = OWNER_ADMITTED_TASK_CARD_ONLY / IMPLEMENTATION_NOT_STARTED
A3–A6 = BLOCKED / NOT_STARTED
```

本卡存在不等於 A2 implementation 已獲執行授權，也不自動解除 A3–A6。Issue #4 仍為 `OPEN`；本卡沒有外部 write 或關票授權。

### 2.3 CodeGraph fallback

開卡時對 `<repo-root>` 的 CodeGraph 查詢回報 `CodeGraph not initialized`。依規範改採 bounded `rg` 與 focused reads，只查上述既有 lifecycle seam、A1 bundle validator、直接受影響 tests 與 A0 03/09 evidence。此 fallback 不構成全 repo runtime inventory；若施工發現另一個 active terminal writer 或 execution authority，必須 stop，不得自行合併語意。

### 2.4 Implementation evidence / receipt preflight

strict fact gate（2026-08-31 implementation start）：

- 受影響檔案：`app/research/contracts.py`、`app/research/run_receipts.py`、`tests/test_research_spine_contracts.py`、`tests/test_autonomous_research_receipts.py`、本 task card。`app/research/dataset_bundle.py` 為 A1 `USE_AS_IS`，僅呼叫 public validator/builder/publisher，不改語意。
- public interfaces：`validate_research_intent()`、`validate_attempt_started()`、`validate_orphan_reconciliation()`、`validate_run_receipt()`、`begin_topic_attempt()`、`finish_topic_attempt()`、`reconcile_orphan_attempts()`；新增介面若需要，只能服務既有 begin→execute→finish seam。
- 資料欄位：Intent/AttemptStarted pre-bind `requested_dataset_bundle_id` 與 immutable manifest ref；receipt 綁定 requested/executed bundle refs、controlled terminal cause evidence、六種 terminal status、orphan unknown facts、legacy `dataset_hash=FEATURES_ARTIFACT_V1` compatibility evidence；不得以 path/mtime/current filesystem 推斷 executed truth。
- 驗證步驟：先跑 targeted RED fixture；GREEN 後跑 `tests/test_research_spine_contracts.py`、`tests/test_autonomous_research_receipts.py`、`tests/test_research_dataset_bundle.py`、受影響 runner/backtest invariance test、`git diff --check`；最後建立單一 local candidate commit 並回報 SHA。

## 3. Product fit 與 minimum-sufficient boundary

### 3.1 Why not less

只在 terminal receipt 補一個 bundle ID、只保存 requested 值、或事後掃 path，無法證明 execution 前請求什麼、實際解析成什麼、差異由何種 authority 允許，也無法把 timeout／abort／orphan 分開。最小充分範圍必須同時涵蓋 pre-attempt requested binding、controlled executed binding、exact terminal taxonomy、immutable evidence 與 fail-closed tests。

### 3.2 Why not more

現有 canonical JSON、TrialSpec、Intent、AttemptStarted、immutable receipt writer、CAS、orphan reconciliation 與 A1 bundle schema已提供足夠 seam。A2 不需要新 lifecycle/FSM、Dataset Registry、Research Ledger、DB、event store、provider resolver、OpenLineage/MLflow/DVC/OMI runtime，亦不需要重寫 direct strategy-matrix engine。

### 3.3 Do not absorb

- 不吸收 prior-art backend、remote tracker 或第二套 canonical writer。
- 不把 path、mtime、翌日 scan、projection、DuckDB row 或 current filesystem 升為 execution fact。
- 不把 timeout scheduler、process supervisor、provider fallback、ranking/publish policy或 production promotion塞進 A2。
- 不改 backtest calculation、scenario enumeration、ranking selection、feature generation 或 dataset bundle semantics。
- 不實作 A3 legacy migration、A4 Observation、A5 Ledger/Learning、A6 compatibility removal。

## 4. Exact lifecycle and identity contract

### 4.1 Existing seam only

A2 只能在既有 forward-only path 上加 contract：

```text
begin_topic_attempt
  -> immutable ExecutionIntent
  -> immutable AttemptStarted
  -> existing execute_topic / strategy-matrix invocation
  -> controlled result-resolution point
  -> finish_topic_attempt
  -> immutable terminal receipt
```

Intent 與 AttemptStarted 必須在 runner invocation 前 durable write 成功；任一 pre-write 失敗時不得啟動 runner。A2 不另建 state machine；既有 immutable corpus是 canonical evidence，任何 projection 都可重建且不是 authority。

### 4.2 Identity grain、exactly-once 與 idempotency

- `intent_id` 表示一次 immutable request；`run_id` 表示一次 attempt；`attempt_event_id` 表示該 attempt 的 started event；`receipt_id` 是 terminal receipt canonical content hash。
- 一個 `run_id` 恰好對應一個 AttemptStarted 與至多一個 terminal receipt。每個正常可控制的 terminal path必須產生恰一份 receipt。
- terminal write 必須使用既有 exclusive-create／immutable writer。相同 `run_id` + byte-identical payload 重放可 idempotent 成功；相同 `run_id` + 不同 payload 必須 `IDENTITY_COLLISION` fail loud，禁止 overwrite、append second terminal 或 last-write-wins。
- receipt 已 commit 後到達的 timeout/cancel/abort/failure signal不得改寫 terminal fact。retry 必須建立新 `run_id`；不得補寫舊 attempt 的 executed facts。
- `requested_trial_spec_ids`、`intent_id`、`run_id`、`attempt_event_id` 必須在 Intent、AttemptStarted、artifacts 與 receipt之間 exact correlation；缺失或衝突 fail closed。

### 4.3 A1 dataset bundle binding

- Intent 必須在 invocation 前引用 `requested_dataset_bundle_id` 與其 immutable manifest evidence ref；不能只引用 legacy `dataset_hash` 或 path。
- requested manifest 必須先通過 A1 `validate_dataset_bundle()` 並可由 immutable evidence重算 ID，才可建立 Intent/AttemptStarted。無效 request 在 lifecycle intake boundary fail closed：不建立 attempt、不得呼叫 runner，也不得偽造 terminal receipt。只有 valid attempt 已 durable started後、runner invocation前的 eligibility／invocation precondition失敗，才使用 `REJECTED_BEFORE_EXECUTION`。
- executed bundle只能在現有 runner 產生完整第一方 execution authority的受控 resolution point 綁定；不得由 terminal writer掃 sibling files或 current filesystem補齊。
- terminal receipt 必須引用 `executed_dataset_bundle_id`、immutable manifest evidence ref，以及 A1 `validate_requested_executed_bundle_refs()` 可驗證的 exact envelope。
- requested/executed IDs相同時禁止 `resolution_delta`；不同時必須有 A1-valid typed delta、deterministic changed paths/roles、resolution authority及 immutable evidence refs。invalid／unexplained mismatch不得宣稱 `SUCCEEDED`。
- legacy `dataset_hash` 繼續只代表 `FEATURES_ARTIFACT_V1`。沒有 contemporaneous A1 bundle evidence的 attempt只能標示 legacy diagnostic／not executable，禁止 synthesize bundle identity。

### 4.4 Terminal taxonomy

下列狀態互斥，且只描述 first-party observed terminal cause：

| status | exact semantics | required evidence |
|---|---|---|
| `SUCCEEDED` | runner已開始並完成；所有要求的 executed units、bundle binding、lineage與 artifacts均有效。 | complete observed execution facts；不得有 `failure`。 |
| `FAILED` | runner已開始，且在沒有已接受 cancel、deadline timeout或 safety/system abort cause時，由 domain/runtime/subprocess error終止；亦包含聲稱成功但完整事實驗證失敗。 | typed failure reason；可保存 validated partial facts，但不得補猜。 |
| `REJECTED_BEFORE_EXECUTION` | valid Intent／AttemptStarted已建立，但 runner invocation前的 post-start eligibility或invocation-precondition validation fail closed。 | `NOT_STARTED`、無 executed units、typed rejection evidence。 |
| `CANCELLED` | 在 receipt commit前，受控 executor明確接受 user/operator cancellation request；原因不是 deadline或 safety abort。 | cancellation request/observer evidence、accepted timestamp與 typed reason。 |
| `TIMED_OUT` | 已宣告且寫入 attempt policy的 deadline被受控 timeout observer判定超過；receipt commit前尚無其他 terminal。 | deadline、observed timestamp、timeout policy/version與 observer evidence。 |
| `ABORTED` | runner已開始，受控 executor或 supervisor因明確 safety/system invariant主動終止；不是 user cancellation、deadline或一般 domain failure。 | abort initiator、typed invariant/reason、observed timestamp與 supervisor/executor evidence。 |

分類先比較 first-party cause evidence 的 `observed_at`；最早成立的 cause獲得 terminal ownership。只有 timestamps相同或無法排序時，才套用固定 tie-break：已接受的 explicit cancellation → 已觀察 deadline timeout → 已接受的 safety/system abort → caught domain/runtime failure。receipt一旦 immutable commit，late signal不得改寫。排序與 tie-break必須寫入 contract version並用 race fixture驗證；不得由 exception class名稱臨時猜測。

### 4.5 `ORPHANED_ATTEMPT` is not `ABORTED`

`ORPHANED_ATTEMPT` 是 reconciliation fact，不是 terminal receipt status。SIGKILL、host crash、斷電或任何無 first-party terminal observer的中斷無法保證 terminal writer執行；只能在既有 AttemptStarted無 receipt且達到 pinned reconciliation policy後，寫 immutable reconciliation：executed bundle、parameters、lineage與result保持 `UNKNOWN`。不得因 process消失、檔案存在、mtime或下次排程推斷 `ABORTED`／`FAILED`／`SUCCEEDED`。只有 supervisor/executor在中斷當下取得足夠第一方 evidence並成功 exclusive-create terminal receipt，才可使用 `ABORTED`。

## 5. Stable requirements

### User story

- **US-A2-001**：作為 Research Spine owner，我需要從 immutable first-party evidence區分一次 attempt 的 requested truth、executed truth與 terminal cause，使成功、失敗、拒絕、取消、逾時、受控中止及未知 orphan不被混為一談。

### Functional requirements

- **FR-A2-001**：valid request通過 intake後，在 runner invocation前以既有 writer immutable寫入 Intent與AttemptStarted；intake／pre-write失敗不得建立或執行 attempt。 `traces_to: US-A2-001`
- **FR-A2-002**：Intent immutable綁定 A1-valid requested bundle ID、manifest evidence ref與 requested TrialSpecs。 `traces_to: US-A2-001`
- **FR-A2-003**：只在受控 resolution point綁定 A1-valid executed bundle與 requested/executed delta。 `traces_to: US-A2-001`
- **FR-A2-004**：terminal receipt exact支援 §4.4 六種互斥狀態及 typed cause evidence。 `traces_to: US-A2-001`
- **FR-A2-005**：每個 controlled attempt terminal exactly once；replay idempotent、collision fail loud、retry使用新 run ID。 `traces_to: US-A2-001`
- **FR-A2-006**：receipt保存 actual executed units、bundle refs、artifact hashes/refs、validation errors與 failure evidence；不得以 requested 值填 executed facts。 `traces_to: US-A2-001`
- **FR-A2-007**：orphan reconciliation維持 unknown-fact evidence，且與 `ABORTED`互斥。 `traces_to: US-A2-001`
- **FR-A2-008**：legacy `dataset_hash` compatibility writer保持原語意，具明確 owner、A6 removal condition及 removal/non-regression test。 `traces_to: US-A2-001`
- **FR-A2-009**：既有 backtest math、scenario outputs與 ranking selection保持 byte/semantic equivalent。 `traces_to: US-A2-001`

### Success criteria

- **SC-A2-001**：valid attempt的 controlled success、failure、pre-execution reject、cancel、timeout與abort各產恰一份 validator-accepted immutable terminal receipt；invalid intake不產 attempt或receipt。 `traces_to: US-A2-001, FR-A2-001, FR-A2-004, FR-A2-005`
- **SC-A2-002**：hard crash fixture只產 orphan reconciliation，且所有未觀察 execution facts為 `UNKNOWN`。 `traces_to: US-A2-001, FR-A2-007`
- **SC-A2-003**：requested/executed bundle equal與authorized mismatch fixtures均由A1 validator通過；missing/invalid/unexplained evidence fail closed。 `traces_to: US-A2-001, FR-A2-002, FR-A2-003, FR-A2-006`
- **SC-A2-004**：duplicate terminal重放為idempotent或collision；永不覆寫既有 receipt。 `traces_to: US-A2-001, FR-A2-005`
- **SC-A2-005**：existing representative strategy-matrix fixture在變更前後的 scenario數值、decision與 artifact payload不變；只有新增的 lifecycle envelope/evidence可不同。 `traces_to: US-A2-001, FR-A2-009`
- **SC-A2-006**：legacy-only records不被誤標為 exact bundle evidence；compatibility test與A6 removal test均存在。 `traces_to: US-A2-001, FR-A2-008`

## 6. Compatibility ownership、rollback 與 removal

- compatibility writer owner：Research Spine A2 owner（`app/research/run_receipts.py` lifecycle adapter），範圍只限既有 `dataset_hash=FEATURES_ARTIFACT_V1` 與新 bundle binding的 additive dual-write／read seam。
- removal owner：A6 owner；A2不得執行 removal。
- removal condition：所有 active A2 writers/readers已通過 requested/executed bundle round-trip、mismatch、terminal taxonomy、orphan、historical corpus rebuild與 rollback tests；新 attempt不再依賴 legacy-only field；A6另行 admission並明示 migration coverage。
- removal test：關閉 compatibility writer的 test fixture後，新-schema attempts仍可從 immutable corpus重建全部 A2 facts；legacy fixture仍被 quarantine而非誤升級，且 historical immutable evidence不被刪除或重寫。
- rollback：A2 feature seam必須可停止新 bundle fields emission/consumption並回到現有 lifecycle behavior；已寫 immutable evidence保留。rollback不得將新 bundle ID降格為 legacy hash，也不得改寫 receipt。

## 7. Vertical implementation slices

### `A2-VS-001`｜Terminal contract and exactly-once guard

- `traces_to: FR-A2-004, FR-A2-005, FR-A2-007; SC-A2-001, SC-A2-002, SC-A2-004`
- 交付：以 public validators固定六種 terminal semantics、cause evidence、orphan/abort區隔與 duplicate/collision規則。
- TDD：RED fixtures先覆蓋 timeout、abort、cancel race、hard-crash orphan及duplicate terminal；GREEN只延伸既有 contract/writer seam。
- blocking edges：無；但開始前必須另行取得 A2 implementation授權。
- likely files：`app/research/contracts.py`、`app/research/run_receipts.py`、`tests/test_research_spine_contracts.py`、`tests/test_autonomous_research_receipts.py`。
- verification：targeted contract/receipt tests；immutable writer collision regression。

### `A2-VS-002`｜Pre-attempt requested bundle binding

- `traces_to: FR-A2-001, FR-A2-002, FR-A2-008; SC-A2-003, SC-A2-006`
- 交付：valid intake的 Intent與AttemptStarted在 invocation前引用A1-valid requested bundle/manifest evidence；invalid或legacy-only intake不建立 attempt且不呼叫 runner；valid started attempt的後續 eligibility failure才 terminalize為 `REJECTED_BEFORE_EXECUTION`。
- TDD：RED fixture spy證明 invalid intake的 attempt/receipt count與 runner call count均為0，另以 valid-but-ineligible fixture證明 pre-execution rejection有唯一 receipt；GREEN以 adapter呼叫 A1 validator，不修改 `dataset_bundle.py`語意。
- blocking edges：`A2-VS-001`。
- likely files：`app/research/contracts.py`、`app/research/run_receipts.py`、`app/research/dataset_bundle.py`（`USE_AS_IS`；若需改語意則 stop）、`tests/test_autonomous_research_receipts.py`。
- verification：requested bundle equal/invalid/legacy-only fixtures；pre-attempt durable-write ordering。

### `A2-VS-003`｜Controlled executed bundle and terminal binding

- `traces_to: FR-A2-003, FR-A2-004, FR-A2-005, FR-A2-006; SC-A2-001, SC-A2-003, SC-A2-004`
- 交付：在既有 controlled runner resolution point取得 executed manifest，呼叫A1 requested/executed validator，將actual bundle delta、artifacts與failure facts寫入唯一 terminal receipt。
- TDD：RED fixtures覆蓋 exact match、authorized fallback、unexplained mismatch、partial/corrupt artifact與重複 terminal；GREEN只改 adapter與受控 orchestration seam。
- blocking edges：`A2-VS-001`, `A2-VS-002`。
- likely files：`app/research/contracts.py`、`app/research/run_receipts.py`、`scripts/run_autonomous_research.py`、`tests/test_autonomous_research_receipts.py`；`scripts/run_backtest_strategy_matrix.py`預設不改，若證據顯示必須修改 math path則 stop。
- verification：receipt validator、CAS refs、requested/executed delta與fail-closed matrix。

### `A2-VS-004`｜Lifecycle matrix, math invariance and compatibility proof

- `traces_to: FR-A2-004, FR-A2-006, FR-A2-007, FR-A2-008, FR-A2-009; SC-A2-001, SC-A2-002, SC-A2-005, SC-A2-006`
- 交付：整合 success/failure/reject/cancel/timeout/abort/orphan matrix、representative backtest invariance fixture、compatibility owner/removal test與 rollback evidence。
- TDD：RED補足未覆蓋 acceptance；GREEN只能修 lifecycle adapter，不能調整 backtest期望值來掩蓋 drift。
- blocking edges：`A2-VS-003`。
- likely files：上述受影響 tests與既有 runner receipt tests；禁止新增 DB、registry或 production fixture。
- verification：affected matrix + representative existing backtest test + corpus rebuild/rollback fixture + `git diff --check`。

## 8. Dependency frontier and checkpoints

```text
CURRENT_FRONTIER = TASK_CARD_REVIEW_ONLY
IMPLEMENTATION_FRONTIER_AFTER_SEPARATE_AUTHORIZATION = A2-VS-001

A2-VS-001 -> A2-VS-002 -> A2-VS-003 -> A2-VS-004
A3–A6 remain BLOCKED
```

- Checkpoint CP-A2-01（`A2-VS-002`後）：重跑 contracts/receipt/A1 bundle affected tests；驗證 runner未被 invalid pre-bind呼叫、無第二套 writer、backtest artifacts未改。
- Checkpoint CP-A2-02（`A2-VS-004`後）：獨立 Reviewer檢查 terminal taxonomy、orphan/abort、idempotency、bundle delta、math invariance與compatibility removal evidence；任何 P0/P1 為 NO-GO。
- 不得跳過 blocker從 later slice開工；本卡完成審查前與另行 implementation授權前，所有 slices均不得開始。

## 9. Acceptance scenarios

- **AS-A2-001**：Given valid requested bundle，When建立 attempt，Then Intent/AttemptStarted已先 immutable commit，之後才可呼叫 runner。 `traces_to: US-A2-001, FR-A2-001, FR-A2-002`
- **AS-A2-002**：Given requested/executed bundles相同，When terminalize success，Then receipt無delta且兩側 manifest refs可重算。 `traces_to: US-A2-001, FR-A2-003, SC-A2-003`
- **AS-A2-003**：Given authorized fallback，When executed bundle不同，Then exact typed delta與 evidence refs通過A1 validator；unexplained mismatch fail closed。 `traces_to: US-A2-001, FR-A2-003, FR-A2-006, SC-A2-003`
- **AS-A2-004**：Given各受控 terminal cause，When terminal writer執行，Then只產一份符合§4.4的receipt；late signal不能覆寫。 `traces_to: US-A2-001, FR-A2-004, FR-A2-005, SC-A2-001, SC-A2-004`
- **AS-A2-005**：Given AttemptStarted後hard crash且無observer receipt，When reconciliation到期，Then只產`ORPHANED_ATTEMPT`並把 execution facts標`UNKNOWN`。 `traces_to: US-A2-001, FR-A2-007, SC-A2-002`
- **AS-A2-006**：Given legacy-only attempt，When A2 reader驗證，Then它維持 diagnostic/quarantine，不能被合成 exact bundle evidence。 `traces_to: US-A2-001, FR-A2-008, SC-A2-006`
- **AS-A2-007**：Given representative strategy matrix fixture，When套用A2 adapter，Then所有 backtest numeric outputs與decisions不變。 `traces_to: US-A2-001, FR-A2-009, SC-A2-005`

## 10. Validation contract for a future implementation

實作者必須先做 trace preflight，再依 slice採 RED → GREEN。至少執行：

```bash
<repo-root>/.venv/bin/python -m pytest \
  tests/test_research_spine_contracts.py \
  tests/test_autonomous_research_receipts.py \
  tests/test_research_dataset_bundle.py

# 另加由 bounded diff 決定的 direct runner/backtest affected tests；不得只跑新測試。
git diff --check
```

驗收 evidence 必須包含：RED failure、GREEN pass、六種 terminal receipts、orphan unknown fixture、duplicate/collision、requested/executed equal與fallback、invalid evidence fail-closed、representative math invariance、compatibility rollback/removal test，以及 bounded diff。若 exact affected runner test無法在施工前 pin，必須先標 `UNKNOWN` 並 stop 由 Mainline裁決，不能自創低覆蓋驗收替代。

## 11. Stop conditions

遇到下列任一條立即停止並回報 exact blocker：

1. 發現另一個 governing terminal writer、lifecycle authority或 active receipt schema，形成 authority conflict。
2. `run_id`／attempt／receipt identity grain無法維持 one-attempt/one-terminal，或 direct matrix boundary存在 material ambiguity。
3. timeout／cancel／abort無法由受控第一方 observer精確區分，或只能靠 filesystem/process disappearance推測。
4. executed bundle只能靠事後 path scan、legacy hash reinterpretation或修改A1 validator語意取得。
5. 需要改 backtest math、scenario enumeration、features、provider、ranking、scheduler、publish、production或建立新 runtime authority。
6. 需要修改 `app/research/dataset_bundle.py` 的 A1 contract語意，而不是 `USE_AS_IS` 呼叫。
7. 需要啟動 A3–A6、改 `.work/current`、改 GitHub Issue、push或merge。

缺個別 artifact evidence可標 `UNKNOWN` 並繼續設計；但 governing-authority conflict、identity-grain ambiguity、terminal-boundary ambiguity或 required out-of-scope mutation必須 stop。

## 12. This task-card-only acceptance

本次只驗收：

- 檔案只有本 task card；
- status 明確為 `IMPLEMENTATION_NOT_STARTED`；
- FR/SC/AS/VS IDs唯一且 `traces_to` 無 dangling reference；
- slices、blocking edges、frontier、checkpoints、likely files、validation與stop conditions完整；
- 不宣稱 Issue #4、A2 runtime或A3–A6已完成；
- `git diff --check` 通過，並由不同責任線做 architecture review。

本卡通過 review 仍只代表可供後續另行授權的 implementation contract；沒有 runtime mutation、push、merge或外部 write。

## 13. Local implementation receipt

2026-08-31 local dispatch `/private/tmp/a2-execution-intent-receipt-implementation-dispatch.md` 已授權在專用 worktree 實作 A2-VS-001～004；本節只記錄 local candidate evidence，不代表 Issue #4 remote state、push、merge、production、A3–A6 已完成。

### 13.1 Changed files

- `app/research/contracts.py`：新增六種 terminal status contract、terminal cause validator、terminal cause ordering helper、Intent/AttemptStarted requested bundle欄位、receipt bundle binding與 orphan unknown bundle fact。
- `app/research/run_receipts.py`：在既有 begin→execute→finish seam 以 A1 `dataset_bundle.py` public API pre-bind requested bundle、於 controlled matrix resolution point validate executed bundle、補 terminal cause evidence與 idempotent/collision-safe terminal receipt。
- `tests/test_research_spine_contracts.py`、`tests/test_autonomous_research_receipts.py`、`tests/test_research_receipt_store.py`、`tests/test_research_spine_daily_cutover.py`：補 RED/GREEN coverage 與 fixture schema alignment。
- 本 task card：補 strict fact gate 與 execution receipt。

### 13.2 RED / GREEN evidence

- RED：`uv run python -m pytest tests/test_research_spine_contracts.py tests/test_autonomous_research_receipts.py -q` → expected failure at collection: `ImportError: cannot import name 'TERMINAL_CAUSE_POLICY_VERSION'`。
- GREEN targeted：`.venv/bin/python -m pytest tests/test_research_spine_contracts.py tests/test_autonomous_research_receipts.py -q` → `40 passed in 0.96s`。
- GREEN task-card matrix：`.venv/bin/python -m pytest tests/test_research_spine_contracts.py tests/test_autonomous_research_receipts.py tests/test_research_dataset_bundle.py -q` → `68 passed in 0.82s`。
- GREEN affected runner/backtest matrix：`.venv/bin/python -m pytest tests/test_research_spine_daily_cutover.py tests/test_research_receipt_store.py tests/test_research_parameter_catalog_projection.py tests/test_regime_research_autonomy.py::test_strategy_matrix_filters_ranking_files_before_replay tests/test_regime_research_autonomy.py::test_strategy_matrix_excludes_episode_tail_without_complete_holding_window tests/test_regime_research_autonomy.py::test_strategy_matrix_replay_args_preserve_regime_history -q` → `24 passed in 0.82s`。
- GREEN combined affected matrix：`.venv/bin/python -m pytest tests/test_research_spine_contracts.py tests/test_autonomous_research_receipts.py tests/test_research_dataset_bundle.py tests/test_research_spine_daily_cutover.py tests/test_research_receipt_store.py tests/test_research_parameter_catalog_projection.py tests/test_regime_research_autonomy.py::test_strategy_matrix_filters_ranking_files_before_replay tests/test_regime_research_autonomy.py::test_strategy_matrix_excludes_episode_tail_without_complete_holding_window tests/test_regime_research_autonomy.py::test_strategy_matrix_replay_args_preserve_regime_history -q` → `92 passed in 1.50s`。
- Diff check：`git diff --check` → pass。

### 13.3 Acceptance coverage

- 六種 controlled terminal statuses：`SUCCEEDED`、`FAILED`、`REJECTED_BEFORE_EXECUTION`、`CANCELLED`、`TIMED_OUT`、`ABORTED` 由 public validator接受，`ORPHANED_ATTEMPT`仍僅為 reconciliation fact。
- orphan unknown fixture：`facts_unknown` 包含 `executed_dataset_bundle`，不推斷 abort/failure/success。
- exactly-once：byte-identical terminal replay idempotent，same `run_id` different payload raises `ImmutableCollisionError`。
- bundle binding：valid requested bundle在 attempt 前 immutable publish；invalid requested bundle不建立 attempt/receipt；executed bundle只由 matrix authority綁定並用 A1 validator檢查；unexplained executed bundle mismatch fail closed。
- compatibility：legacy `dataset_hash` 保持 `FEATURES_ARTIFACT_V1` 語意，新增 bundle欄位為 additive；`app/research/dataset_bundle.py` 未修改。
- representative invariance：受影響 strategy-matrix tests pass，未修改 backtest math/features/provider/ranking/scheduler/publish/production。

### 13.4 Residual risk

- Additional script check `.venv/bin/python scripts/verify_backtest_strategy_matrix.py` currently fails before A2 path on existing catalog validation: `ValueError: horizon 包含 catalog 外值：[1, 2]`。本 candidate 未修改該 verifier或 backtest math；以現有 pytest strategy-matrix invariance tests作為 bounded acceptance evidence。

### 13.5 P1 repair receipt

2026-08-31 local repair dispatch `/private/tmp/a2-implementation-p1-repair-dispatch.md` 僅授權修 Reviewer NO-GO 的兩個 P1。本 repair 未 push、未 merge、未寫 GitHub Issue、未啟動 A3-A6，且未修改 provider、features、backtest、ranking、scheduler、publish、production或 learning。

#### Changed files

- `app/research/contracts.py`：`AttemptStarted` 與 terminal receipt 對 empty `run_id`／`intent_id`／requested trial IDs fail closed。
- `scripts/run_autonomous_research.py`：真實 `KeyboardInterrupt` callsite 現在提供第一方 `CANCELLED` terminal cause evidence，包含 cancellation request id、accepted timestamp、typed reason、observer與 immutable evidence ref。
- `scripts/verify_research_spine_batch.py`：batch verifier 逐層 correlate intent、attempt、receipt與 run artifact 的 `run_id`、`intent_id`、`attempt_event_id`、requested trial IDs、requested bundle ID/ref；空值、路徑 stem 不一致與跨檔 mismatch 均 fail closed。
- `tests/test_research_spine_contracts.py`、`tests/test_research_spine_daily_cutover.py`、`tests/test_research_batch_owner.py`：補 P1-A/P1-B regression。
- 本 task card：補 local P1 repair receipt。

#### RED / GREEN evidence

- RED focused repro：`.venv/bin/python -m pytest tests/test_research_spine_contracts.py::test_attempt_started_rejects_empty_identity_fields_and_trials tests/test_research_spine_daily_cutover.py::test_batch_verifier_rejects_attempt_bundle_identity_tampering tests/test_research_spine_daily_cutover.py::test_batch_verifier_rejects_receipt_attempt_event_tampering tests/test_research_spine_daily_cutover.py::test_batch_verifier_rejects_run_artifact_membership_tampering tests/test_research_batch_owner.py::test_runner_keyboard_interrupt_emits_single_cancelled_receipt_with_first_party_evidence -q` → `5 failed in 1.40s`。
- GREEN focused repro：same command → `5 passed in 1.28s`。
- GREEN affected matrix：`.venv/bin/python -m pytest tests/test_research_spine_contracts.py tests/test_autonomous_research_receipts.py tests/test_research_dataset_bundle.py tests/test_research_spine_daily_cutover.py tests/test_research_receipt_store.py tests/test_research_parameter_catalog_projection.py tests/test_research_batch_owner.py tests/test_regime_research_autonomy.py::test_strategy_matrix_filters_ranking_files_before_replay tests/test_regime_research_autonomy.py::test_strategy_matrix_excludes_episode_tail_without_complete_holding_window tests/test_regime_research_autonomy.py::test_strategy_matrix_replay_args_preserve_regime_history -q` → `113 passed in 1.57s`。

#### P1 closure

- P1-A closed：runner `KeyboardInterrupt` path writes exactly one contract-valid `CANCELLED` receipt and preserves original interrupt propagation.
- P1-B closed：attempt empty identity and batch-level tampering of bundle binding、receipt attempt event與 run artifact membership all fail closed。
