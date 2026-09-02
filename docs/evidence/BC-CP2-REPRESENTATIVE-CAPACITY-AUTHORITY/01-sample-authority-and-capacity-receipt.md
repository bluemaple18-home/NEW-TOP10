# BC-CP2 代表性 E3 樣本 Authority 與容量量測 Receipt

## 範圍收據

- 工作名稱：`BC-CP2 代表性 E3 樣本 Authority 與容量量測`
- Slice ID：`BC-CP2-RCA-01`
- Verdict：`PARTIAL_GO_CANDIDATE_SPACE_CENSUS_AUTHORITY / NO_GO_E3_WORKLOAD_BENCHMARK_AUTHORITY`
- Candidate 起點：C0 Phase 2 fixed SHA `a61f143ea5223b6af812e27aac0082121f781343`
- Prior BC-CP2 candidate：`36ba9df44539cc42e663a48be7d6f8577fd888fc`
- B0 repaired fixed SHA：`1e9ed61e2e5c86adf2159e095ff241ef13127e80`
- Canonical main：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- Observed at：`2026-09-01T07:29:49Z`
- 邊界：只重判 committed authority。未執行 E3 benchmark、未建立便利樣本、未修改 C0/B0 既有 evidence、未修改 code/config/workflow/queue/runner/scheduler/backtest/production，未 merge/push/改 Issue/external write，未准入 B0 Phase 2、B1 或 C1。

## Direct Answer

原 `NO_GO_MISSING_REPRESENTATIVE_SAMPLE_AUTHORITY` 前提已被新 B0 repaired fixed evidence 部分修正：formal 720 candidate-space census authority 現在成立。B0 已證明 formal 720 generation、720 個 unique deterministic `combination_id`、legal ID hash、global family authority，以及 validation-profile partition checks。

但這仍不是可執行 E3 容量 benchmark 的完整 authority。validation profiles 只覆蓋 `242` 個 unique legal IDs，缺 `478` 個 global IDs，且跨 partition overlap `32` 個 IDs；它們不能被宣稱為完整 coverage 或代表性 workload。dataset / ranking / context workload authority 也仍未固定，且 B0/C0 都保留 E3 throughput 為未量測。因此本 repair 不執行 benchmark，結論是：candidate-space census 可用；representative E3 workload benchmark 仍 `NO-GO`。

## Authority Reconciliation

| 問題 | 固定證據 | 判定 |
|---|---|---|
| formal 720 candidate-space census authority 是否成立？ | B0 repaired evidence 證明 `parameter_combinations()` 產生 720 legal combinations、720 unique IDs、global family hash 與 validation partition checks。 | `GO_FOR_CANDIDATE_SPACE_CENSUS_AUTHORITY` |
| validation profiles 是否可當完整 coverage 或代表性樣本？ | 四個 public profiles 共覆蓋 242 unique IDs、缺 478、跨 partition overlap 32。 | 不可；只是不完整 bounded partitions。 |
| dataset/ranking/context workload authority 是否成立？ | B0P1-BC-004 指出 exact regime/episode/dataset/ranking/stage 是 cost context；C0 Phase 2 仍只證明非代表性 1-scenario characterization。 | 未成立。 |
| 是否可執行 representative E3 capacity benchmark？ | 候選空間 census 成立，但 workload sample selection、dataset/ranking/context authority 與 capacity envelope 未固定。 | 不執行；`NO_GO_E3_WORKLOAD_BENCHMARK_AUTHORITY`。 |
| 是否准入 B0 Phase 2/B1/C1？ | 任務卡禁止；B0/C0 evidence 仍保留 B1/C1 gate。 | 不准入。 |

## Measurement Receipt

- Measurement status：`NOT_EXECUTED_WORKLOAD_AUTHORITY_BLOCKED`
- Candidate-space census authority：`PROVEN_FOR_FORMAL_EXECUTABLE_720_FAMILY`
- Candidate-space denominator：`720`
- Validation-profile coverage：`242` unique covered / `478` missing / `32` overlap
- Representative workload sample size：`0`
- Dataset/ranking/context workload authority：`MISSING`
- Wall time：`UNMEASURED`
- Candidate/sec：`UNMEASURED`
- CPU：`UNMEASURED`
- Peak RSS：`UNMEASURED`
- I/O：`UNMEASURED`
- Cleanup：本 repair 未建立 BC-CP2 benchmark temp output；pre/post cleanup scan 不應有 `<bc-cp2-temp-prefix>` 殘留。
- Non-extrapolation boundary：C0P2-CAP-004 的 1 scenario characterization 只證明 runner envelope 可在隔離 temp fixture 上執行，不得外推為代表性 720/full-daily capacity。

## 最小後續 Frontier

下一個最小 sufficient card 應從「候選空間 authority」轉向「workload benchmark authority」：

1. 固定 720 formal family 的 sample selection rule：full census、stratified subset，或其他明確代表性規則。
2. 固定 dataset / ranking / exact regime / episode / stage workload input authority，說明其為何代表 E3 capacity。
3. 指定 benchmark isolation、temporary output boundary、cleanup/parity、wall time、candidate/sec、CPU、peak RSS、I/O 欄位。
4. 只有上述 workload authority 成立後，才執行 E3 benchmark；仍不得將 validation profiles 的 242 covered IDs 當 full coverage。

## Claim Ledger

### Claim BC-CP2-RCA-001

```yaml
claim_id: BC-CP2-RCA-001
claim: BC-CP2 repaired trace inputs exist: B0P1-BC-002, B0P1-BC-004, and B0P1-BC-005 are present in the B0 repaired fixed checkpoint evidence, and C0P2-CAP-004 is present in the C0 Phase 2 fixed capacity evidence.
classification: TRACE_PREFLIGHT_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 1e9ed61e2e5c86adf2159e095ff241ef13127e80; a61f143ea5223b6af812e27aac0082121f781343
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/04-bc-checkpoint-input.md; docs/evidence/CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK/phase-2/05-capacity-and-intermediate-reuse-audit.md
source_range_or_section: B0 04 lines 60-135; C0 05 lines 122-137
observed_at: 2026-09-01T07:29:49Z
confidence: HIGH
conflict_with: treating BC-CP2 as detached from repaired B0 authority or prior C0 capacity evidence.
implication: This repair may replace the old missing-candidate-space premise with the repaired B0 fixed facts.
open_question: none for trace existence.
owner: BC-CP2 evidence worker
```

### Claim BC-CP2-RCA-002

```yaml
claim_id: BC-CP2-RCA-002
claim: B0 repaired fixed evidence proves formal 720 candidate-space census authority: canonical generation, 720 unique deterministic combination IDs, legal ID hash, global family size, and validation-profile partition checks are proven for the formal executable 720 family.
classification: CANDIDATE_SPACE_CENSUS_AUTHORITY_PROVEN
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 1e9ed61e2e5c86adf2159e095ff241ef13127e80
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/04-bc-checkpoint-input.md; docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/03-e1-e4-initial-cost-classification.md
source_range_or_section: B0 04 lines 7-35,60-77; B0 03 lines 3-23,31-47
observed_at: 2026-09-01T07:29:49Z
confidence: HIGH
conflict_with: the prior BC-CP2 receipt premise that no representative candidate-space authority existed at all.
implication: BC-CP2 may use the formal 720 family as candidate-space census authority, while keeping B1 and execution capacity separate.
open_question: rank/unrank convenience path and larger product matrix authority remain outside this repair.
owner: B0/C0 Integrator
```

### Claim BC-CP2-RCA-003

```yaml
claim_id: BC-CP2-RCA-003
claim: Validation profiles are not full coverage or representative workload authority: B0 repaired evidence records 242 unique covered legal IDs, 478 missing global IDs, and 32 overlapping IDs across public profiles.
classification: VALIDATION_PROFILE_COVERAGE_INCOMPLETE
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 1e9ed61e2e5c86adf2159e095ff241ef13127e80
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/04-bc-checkpoint-input.md; docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/03-e1-e4-initial-cost-classification.md
source_range_or_section: B0 04 lines 21-35; B0 03 lines 17-23
observed_at: 2026-09-01T07:29:49Z
confidence: HIGH
conflict_with: treating validation profiles as a full-scan sample or representative 720 workload.
implication: Any benchmark based only on validation profiles must be labeled bounded/incomplete, not representative full-family capacity.
open_question: whether future benchmark should full-census all 720 or define a separate stratified representative rule.
owner: Future workload benchmark owner
```

### Claim BC-CP2-RCA-004

```yaml
claim_id: BC-CP2-RCA-004
claim: Dataset, ranking, and context workload authority remains missing for representative E3 capacity: B0 keeps exact regime, episode, dataset, ranking source, and stage as cost context rather than count multipliers, while C0 Phase 2 records only a non-representative 1-scenario characterization and representative capacity remains unmeasured.
classification: E3_WORKLOAD_BENCHMARK_AUTHORITY_MISSING
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 1e9ed61e2e5c86adf2159e095ff241ef13127e80; a61f143ea5223b6af812e27aac0082121f781343
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/04-bc-checkpoint-input.md; docs/evidence/CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK/phase-2/05-capacity-and-intermediate-reuse-audit.md; docs/evidence/CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK/phase-2/10-c1-prerequisites-and-admission-blockers.md
source_range_or_section: B0 04 lines 29-35,98-115; C0 05 lines 18-45,62-64,122-137; C0 10 lines 23-43,84-99
observed_at: 2026-09-01T07:29:49Z
confidence: HIGH
conflict_with: running or reporting representative E3 capacity from candidate-space census alone.
implication: This repair must not run benchmark or report full-720/daily capacity.
open_question: which admitted dataset/ranking/context workload should represent E3 capacity.
owner: C0 capacity owner / future benchmark owner
```

### Claim BC-CP2-RCA-005

```yaml
claim_id: BC-CP2-RCA-005
claim: The repaired BC-CP2 verdict is PARTIAL_GO_CANDIDATE_SPACE_CENSUS_AUTHORITY / NO_GO_E3_WORKLOAD_BENCHMARK_AUTHORITY: candidate-space census is now fixed by B0 repaired evidence, but representative workload authority is still missing, so no benchmark was executed.
classification: BC_CP2_REPAIRED_VERDICT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 1e9ed61e2e5c86adf2159e095ff241ef13127e80; a61f143ea5223b6af812e27aac0082121f781343
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/04-bc-checkpoint-input.md; docs/evidence/CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK/phase-2/05-capacity-and-intermediate-reuse-audit.md; docs/evidence/CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK/phase-2/10-c1-prerequisites-and-admission-blockers.md
source_range_or_section: B0 04 lines 7-35,60-77,98-135; C0 05 lines 18-45,62-64,122-137; C0 10 lines 23-43,84-99
observed_at: 2026-09-01T07:29:49Z
confidence: HIGH
conflict_with: preserving the old absolute NO_GO premise, or treating formal 720 census authority as sufficient workload benchmark authority.
implication: The next frontier is workload sample authority and benchmark design, not B0 Phase 2/B1/C1 admission.
open_question: exact next card ID and owner for representative E3 workload benchmark authority.
owner: BC-CP2 evidence worker
```
