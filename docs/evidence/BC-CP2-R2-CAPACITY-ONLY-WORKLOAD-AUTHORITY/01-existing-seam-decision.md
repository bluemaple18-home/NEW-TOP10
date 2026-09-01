# BC-CP2-R2 Capacity-only 720 Workload Authority Decision

## Scope receipt

- 工作名稱：`BC-CP2-R2 Capacity-only 720 Workload Authority`
- Slice ID：`BC-CP2-R2-CAPACITY-AUTH-01`
- Verdict：`NO_GO_EXISTING_SEAM / GO_FOR_MINIMAL_CAPACITY_FIXTURE_ADAPTER_CARD`
- Current candidate base：`319eee83cdf6001f094c5bd2597657aa2d3d7c40`
- Canonical main：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- R1 fixed SHA：`319eee83cdf6001f094c5bd2597657aa2d3d7c40`
- C0 Phase 2 fixed SHA：`a61f143ea5223b6af812e27aac0082121f781343`
- Formal 720 authority SHA：`1e9ed61e2e5c86adf2159e095ff241ef13127e80`
- Dispatch card hash：`sha256:2e428c02fb7813930e69f508ebf584c5db3092020b18bf798a4fae69ef4afe50`
- Observed at：`2026-09-01T09:20:00Z`
- Boundary：本卡只做唯讀 source/tests/evidence 與 scenario-enumeration-only probe。未生成 ranking、未跑 720 benchmark、未執行 portfolio replay、未修改 code/config/workflow/queue/runner/scheduler/backtest/production，未修改 configured artifacts，未 merge/push/改 Issue/external write，未准入 B0 Phase 2、B1 或 C1。

## Direct answer

現有 first-party fixture／verification harness 不能在不修改 code/config/data 的情況下，作為 formal 720 capacity-only full census 的可執行 authority。

已證明的部分很窄：formal 720 candidate-space generation 與 full CLI dimension expansion 都可重現，scenario-enumeration-only probe 觀測到 `legal_combination_count=720`、`global_family_size=720`、`cli_scenario_count_from_full_values=720`。這只證明 runner 可由四個 executable dimensions 產生 720 個參數組合；不是 capacity benchmark，也不是 research-valid workload。

阻擋 capacity-only benchmark 的 exact gap 有兩個：

1. `scripts/run_backtest_strategy_matrix.py` 沒有 direct canonical 720 ID execution adapter。`--requested-trial-spec-ids` 只寫入 `research_spine.requested_trial_spec_ids` 作 receipt metadata，不用來選擇或驗證要執行的 scenario set；實際 scenario set 仍由 CLI dimension values 展開。
2. 現有 first-party executable fixture `scripts/verify_backtest_strategy_matrix.py` 只建立 synthetic 1 ranking file / 2 stocks / short OHLC fixture，跑 `2×2×2×2=16` scenarios，並把 verification artifact 寫到 repo `artifacts/`；它沒有 formal 720 input adapter、resource metric envelope、manifest parity contract，且不是 configured exact-regime workload。R1 後 configured snapshot 本身也在真實 runner 卡於 `NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE`，不能作為 formal 720 capacity run 的 admitted workload。

因此本卡回 `NO_GO_EXISTING_SEAM`。唯一最小下一卡應是 `BC-CP2-R3-MINIMAL-CAPACITY-ONLY-FIXTURE-ADAPTER`：新增或指定一個 first-party capacity-only adapter/harness，只接受 canonical formal 720 IDs 或其 deterministic full-family manifest，建立 synthetic/read-only capacity fixture、resource metrics、I/O manifest parity、cleanup 與 `CAPACITY_ONLY / NOT_RESEARCH_EVIDENCE` 邊界；仍不得把該結果提升為 research-valid workload 或 B1/C1 admission。

## CodeGraph preflight

| Check | Result |
|---|---|
| `codegraph_status(projectPath=<repo-root>)` | `FAILED` — CodeGraph not initialized in this isolated worktree. |
| `codegraph_context(projectPath=<repo-root>, task=BC-CP2-R2...)` | `FAILED` — same initialization boundary. |
| Fallback | Used bounded `rg` and fixed source/test/evidence reads only. No index initialization was performed. |

## Scenario-enumeration-only probe

This probe imported committed Python functions and did not call `build_payload(...)`, `run_portfolio_from_price_frame(...)`, any ranking generator, or any benchmark runner. It wrote no output files.

```text
probe_kind=SCENARIO_ENUMERATION_ONLY
legal_combination_count 720
combination_id_hash sha256:78cd9b8b6fa39935f9037d5b4c8dde3fcc2ae39955414aa51bda96dafb69f6b4
global_family_size 720
global_combination_ids_hash sha256:78cd9b8b6fa39935f9037d5b4c8dde3fcc2ae39955414aa51bda96dafb69f6b4
cli_scenario_count_from_full_values 720
cli_parameter_space_hash sha256:e918d111d27dda636964a3bd4e519cfe1c99e3047101f5459ee404481e9d0eed
strategy_matrix_defaults {'horizon': '3,5,10', 'stop_loss_pct': 'none,0.08', 'take_profit_pct': 'none,0.15', 'max_group_exposure': 'none,0.35'}
first_scenario {'horizon': 3, 'stop_loss_pct': None, 'take_profit_pct': None, 'max_group_exposure': None}
last_scenario {'horizon': 20, 'stop_loss_pct': 0.12, 'take_profit_pct': 0.3, 'max_group_exposure': 0.55}
```

Interpretation：formal 720 can be enumerated and converted into full CLI value space, but this does not establish canonical ID-driven execution, workload realism, resource metrics, or benchmark authority.

## Existing-seam matrix

| Seam | Evidence | Capacity-only verdict | Research-valid verdict |
|---|---|---|---|
| Formal 720 candidate-space generator | `parameter_combinations(...)` creates `combination_id` from executable dimensions; `statistical_family_contract(...)` fixes global family size/hash. Scenario-enumeration-only probe reproduced 720. | `GO_FOR_DENOMINATOR_AND_ID_MANIFEST` | Not a workload; no dataset/ranking/context authority. |
| Strategy matrix runner scenario scaling | `build_payload(...)` expands scenarios from CLI values and loops each scenario through portfolio replay; full CLI values can enumerate 720. | `PARTIAL`: runner can scale scenario list by dimensions. | Not sufficient; exact regime and horizon-safe dates still gate configured research execution. |
| Direct canonical ID / TrialSpec input | `parse_args(...)` accepts `--requested-trial-spec-ids`, but `build_payload(...)` only records it under `research_spine`; no filter or equality check maps those IDs to executed `combination_id`s. | `MISSING`: capacity-only full census cannot be driven by canonical 720 IDs without adapter or verifier. | `MISSING`: C1 direct TrialSpec seam remains blocked. |
| First-party synthetic verifier | `verify_backtest_strategy_matrix.py` creates temp synthetic ranking/features and invokes runner with horizons `1,2`, stop `none,0.05`, take `none,0.1`, group `none,0.3`, expecting `scenario_count=16`; it also writes `artifacts/backtest_strategy_matrix_verification_latest.json`. | `NO_GO`: useful smoke fixture, not formal 720, not resource-measured, not repo-write-free. | Not research evidence; synthetic and not exact-regime. |
| Configured exact-regime snapshot after R1 | R1 rebuilt v2 history and enumerated 12 identities, but true runner command failed before benchmark at `NO_HORIZON_SAFE_EXACT_REGIME_RANKING_DATE: horizon=3 allowed_date_count=6`. | `NO_GO_FOR_CONFIGURED_FULL_720`: cannot use current configured snapshot as capacity workload without resolving horizon-safe date coverage or choosing a capacity-only synthetic policy. | `NO_GO`: legal research workload still blocked. |
| Shared setup / reuse | Strategy matrix loads price frame once per matrix and records `features_load_policy=load_once_per_matrix`, but calls `run_portfolio_from_price_frame(...)` for every scenario. | Capacity benchmark must measure E3 cost; no E2 shortcut may be assumed. | E2 remains `NOT_PROVEN`. |
| I/O and cleanup envelope | Runner writes JSON and Markdown output; verifier temp input cleanup exists but verification artifact writes to repo; C0 Phase 2 one-scenario characterization recorded temp cleanup and metrics only for non-representative fixture. | Needs a dedicated capacity-only adapter with temp output boundary, manifest parity, resource metrics and cleanup check. | Not research-valid workload. |
| Fail-closed behavior | Existing runner fails on missing exact-regime inputs, missing episode IDs, non-development episode scope, and no horizon-safe exact-regime ranking dates. | Good fail-closed primitives exist; they do not replace missing workload authority. | Correctly blocks configured research benchmark. |

## Minimal next card

`BC-CP2-R3-MINIMAL-CAPACITY-ONLY-FIXTURE-ADAPTER`

Required scope:

1. Input：canonical formal 720 ID manifest from `parameter_combinations(...)` / `statistical_family_contract(...)`, or deterministic full-family manifest hash equivalent to `sha256:78cd9b8b6fa39935f9037d5b4c8dde3fcc2ae39955414aa51bda96dafb69f6b4`.
2. Adapter：map every requested canonical ID to exactly one executed scenario; fail if missing, extra, duplicate, or order-only mismatch.
3. Fixture：capacity-only synthetic/read-only fixture large enough for max horizon `20`, top_n `10`, group map, ranking dates and feature rows; explicitly labeled `CAPACITY_ONLY / NOT_RESEARCH_EVIDENCE`.
4. Metrics：wall time, candidate/sec, user/sys CPU, peak RSS, read/write I/O, output sizes, scenario count, ID count/hash, pre/post manifest parity, cleanup.
5. Boundary：no ranking generation, no production invocation, no research validity claim, no B0 Phase 2/B1/C1 admission.

Classification:

- Minimal code repair：required if the project wants a reusable first-party harness that accepts canonical IDs and proves exact requested/executed parity.
- B0 Phase 2 policy decision：required only if capacity-only synthetic workload semantics must be blessed as sufficient for a future capacity benchmark despite not being research-valid.
- B1 implementation：not required for this R3 capacity-only adapter unless it is promoted into admitted TrialSpec execution, queue/claim/lease/retry, or research-valid workload.

why_not_less：

- A source-only receipt or scenario-enumeration probe cannot measure runner capacity and cannot prove canonical requested/executed ID parity.
- Reusing `verify_backtest_strategy_matrix.py` unchanged would only prove a 16-scenario synthetic smoke and would write a verifier artifact to repo.

why_not_more：

- Do not repair horizon-safe configured workload in the same card; that is research-valid workload authority, not capacity-only fixture authority.
- Do not add queue/claim/lease/retry, B1 TrialSpec execution, dual-write, canary, rollback drill, or production path.

do_not_absorb：

- ranking generation or new ranking artifacts
- runner/backtest math changes
- research contract, split policy, configured data, or production config changes
- queue/scheduler/bridge/control-plane implementation
- claims that capacity-only synthetic results are representative research evidence

## Claim Ledger

### Claim BC-CP2-R2-001

```yaml
claim_id: BC-CP2-R2-001
claim: The only proven formal denominator is the 720 executable candidate family; scenario-enumeration-only probe reproduced legal_combination_count=720, global_family_size=720, and the canonical combination_id_hash/global_combination_ids_hash.
classification: FORMAL_720_ENUMERATION_AUTHORITY_ONLY
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070; 1e9ed61e2e5c86adf2159e095ff241ef13127e80; local probe at 319eee83cdf6001f094c5bd2597657aa2d3d7c40
source_path_or_official_url: scripts/run_autonomous_research.py; app/research/parameter_catalog.py; tests/test_research_parameter_catalog_projection.py; config/research_parameter_catalog.json; config/regime_research_contract.json; docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/04-bc-checkpoint-input.md
source_range_or_section: run_autonomous_research.py lines 493-608,655-688; tests/test_research_parameter_catalog_projection.py lines 55-70; B0 04 lines 17-35,60-77; scenario-enumeration-only probe in this receipt
observed_at: 2026-09-01T09:20:00Z
confidence: HIGH
conflict_with: treating 720 enumeration as benchmark execution, research-valid workload, B1 admission, or production readiness.
implication: A future capacity benchmark may use 720 as denominator/ID manifest, but must still establish execution parity and workload boundary.
open_question: whether capacity-only synthetic workload semantics are policy-authorized for benchmark use.
owner: B0/C0 capacity owner
```

### Claim BC-CP2-R2-002

```yaml
claim_id: BC-CP2-R2-002
claim: Existing strategy matrix execution is dimension-driven, not canonical-ID-driven: requested_trial_spec_ids are recorded as research_spine metadata, while executed scenarios are generated from CLI dimension values.
classification: DIRECT_CANONICAL_ID_EXECUTION_SEAM_MISSING
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: scripts/run_backtest_strategy_matrix.py; scripts/run_autonomous_research.py; docs/evidence/CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK/phase-2/10-c1-prerequisites-and-admission-blockers.md
source_range_or_section: run_backtest_strategy_matrix.py lines 64-104,580-607,692-703,741-757; run_autonomous_research.py lines 2071-2164,3990-4155; C0 10 lines 25-42,69-75
observed_at: 2026-09-01T09:20:00Z
confidence: HIGH
conflict_with: claiming the runner can directly accept canonical TrialSpec or 720 IDs as execution authority.
implication: Existing seam cannot prove exact requested/executed parity for canonical 720 IDs without a minimal adapter or verifier repair.
open_question: exact TrialSpec manifest shape remains a B1/direct-execution concern if promoted beyond capacity-only.
owner: Runner seam owner / future R3 card owner
```

### Claim BC-CP2-R2-003

```yaml
claim_id: BC-CP2-R2-003
claim: The checked-in first-party verifier is a 16-scenario synthetic smoke harness, not a formal 720 capacity harness: it creates one synthetic ranking file and short OHLC fixture, runs a 2×2×2×2 matrix, and writes a verification artifact under repo artifacts.
classification: EXISTING_FIXTURE_NOT_FORMAL_720_CAPACITY_HARNESS
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: scripts/verify_backtest_strategy_matrix.py
source_range_or_section: lines 1-2,61-82,84-107,133-163
observed_at: 2026-09-01T09:20:00Z
confidence: HIGH
conflict_with: treating verifier pass, synthetic smoke, or repo artifact write as capacity-only full census authority.
implication: Capacity-only full census needs a dedicated isolated harness or adapter before benchmark execution.
open_question: whether future R3 should modify this verifier or add a separate capacity-only harness.
owner: Capacity harness owner
```

### Claim BC-CP2-R2-004

```yaml
claim_id: BC-CP2-R2-004
claim: R1 repaired the configured market-regime history as-of blocker, but the configured exact-regime workload still fails before benchmark because no horizon-safe exact-regime ranking date exists for the first split-OK identity at horizon=3.
classification: CONFIGURED_RESEARCH_WORKLOAD_STILL_FAILS_CLOSED
source_repo: bluemaple18-home/NEW-TOP10; local configured artifact evidence
source_sha_or_version: 319eee83cdf6001f094c5bd2597657aa2d3d7c40
source_path_or_official_url: docs/evidence/BC-CP2-R1-CONFIGURED-REGIME-HISTORY-V2-REBUILD/01-rebuild-and-next-gate-receipt.md; scripts/run_backtest_strategy_matrix.py
source_range_or_section: R1 receipt lines 19-30,130-189; run_backtest_strategy_matrix.py lines 153-199,226-265,520-577
observed_at: 2026-09-01T09:20:00Z
confidence: HIGH
conflict_with: using the configured snapshot as an admitted formal 720 benchmark workload after R1 without resolving horizon-safe ranking coverage.
implication: Research-valid workload authority remains blocked; capacity-only benchmark must either wait for that repair or use a separately authorized synthetic capacity workload.
open_question: whether the next frontier should be configured horizon-safe repair or capacity-only synthetic policy/adapter first.
owner: BC-CP2 / future workload authority owner
```

### Claim BC-CP2-R2-005

```yaml
claim_id: BC-CP2-R2-005
claim: Current capacity evidence remains non-representative: C0 Phase 2 measured one legal E3 temp fixture and existing BC-CP2 receipts explicitly prohibit extrapolating source inspection, verifier pass, or one-scenario characterization into 720/full-daily capacity.
classification: CAPACITY_EVIDENCE_NOT_FULL_CENSUS_READY
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: a61f143ea5223b6af812e27aac0082121f781343; c3cdd3db493e8c314ded5336181f43c520756440
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK/phase-2/05-capacity-and-intermediate-reuse-audit.md; docs/evidence/BC-CP2-REPRESENTATIVE-CAPACITY-AUTHORITY/01-sample-authority-and-capacity-receipt.md; docs/evidence/BC-CP2-FULL-720-E3-CAPACITY-BENCHMARK/01-full-720-capacity-receipt.md
source_range_or_section: C0 05 lines 18-48,50-64,122-137; BC-CP2 sample receipt lines 15-54,112-128; full-720 receipt lines 17-24,76-87,226-246
observed_at: 2026-09-01T09:20:00Z
confidence: HIGH
conflict_with: declaring GO_FOR_SEPARATE_BENCHMARK_CARD from existing fixtures without canonical ID parity and capacity-only workload authority.
implication: This card must return NO_GO_EXISTING_SEAM and constrain the next card to minimal capacity-only fixture adapter authority.
open_question: none for existing-seam NO-GO; benchmark remains not executed.
owner: BC-CP2-R2 evidence worker
```
