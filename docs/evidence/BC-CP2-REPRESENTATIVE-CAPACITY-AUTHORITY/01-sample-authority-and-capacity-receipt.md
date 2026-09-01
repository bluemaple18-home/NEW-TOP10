# BC-CP2 代表性 E3 樣本 Authority 與容量量測 Receipt

## 範圍收據

- 工作名稱：`BC-CP2 代表性 E3 樣本 Authority 與容量量測`
- Slice ID：`BC-CP2-RCA-01`
- Verdict：`NO_GO_MISSING_REPRESENTATIVE_SAMPLE_AUTHORITY`
- Candidate 起點：C0 Phase 2 fixed SHA `a61f143ea5223b6af812e27aac0082121f781343`
- Canonical main：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- B0 Phase 1：`d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98`
- Observed at：`2026-09-01T06:55:11Z`
- 邊界：只做 committed authority reconciliation。未執行 E3 benchmark、未建立便利樣本、未修改既有 evidence、未修改 code/config/workflow/queue/runner/scheduler/backtest/production，未 merge/push/改 Issue/external write，未准入 B0 Phase 2、B1 或 C1。

## Direct Answer

現有 committed authority 不足以建立代表性 E3 容量樣本。B0 固定 evidence 只證明 `720` 作為 formal executable denominator，且明確保留 canonical 720-spec generation、dedupe、identity、partition path 與 E3 capacity 為未證明；C0 Phase 2 fixed evidence 只補到 `NON_REPRESENTATIVE_LEGAL_CHARACTERIZATION`，並明確記錄代表性樣本 authority 不存在。因此本 slice 必須交 `NO_GO_MISSING_REPRESENTATIVE_SAMPLE_AUTHORITY`，不得執行或外推 full-720/daily capacity benchmark。

## Authority Reconciliation

| 問題 | 固定證據 | 判定 |
|---|---|---|
| 是否有 formal denominator？ | B0 固定 `matrix_size=720`，current evaluator=`E3`。 | 有，可作容量問題 denominator。 |
| 是否有 canonical 720 TrialSpec generator/identity？ | B0 記錄 canonical generation、dedupe、identity、partition path 未證明，B1 未准入。 | 無。 |
| 是否有代表性 CandidateDecision / TrialSpec sample selection authority？ | Backlog 記錄 B1/B2 未准入，C1 需等待 CandidateDecision → explicit admission → Canonical TrialSpec。 | 無。 |
| 是否可使用 C0 Phase 2 小樣本量測當代表性樣本？ | C0P2-CAP-004 明確分類為 `NON_REPRESENTATIVE_LEGAL_CHARACTERIZATION`。 | 不可升格。 |
| 是否可執行本 slice 的代表性 E3 benchmark？ | 缺 sample authority；卡片禁止便利樣本升格。 | 不執行。 |

## Measurement Receipt

- Measurement status：`NOT_EXECUTED_AUTHORITY_BLOCKED`
- Representative sample size：`0`
- Wall time：`UNMEASURED`
- Candidate/sec：`UNMEASURED`
- CPU：`UNMEASURED`
- Peak RSS：`UNMEASURED`
- I/O：`UNMEASURED`
- Cleanup：未建立 BC-CP2 benchmark temp output；pre/post cleanup scan 不應有 `<bc-cp2-temp-prefix>` 殘留。
- Non-extrapolation boundary：C0P2-CAP-004 的 1 scenario characterization 只證明 runner envelope 可在隔離 temp fixture 上執行，不得外推為代表性 720/full-daily capacity。

## 最小後續 Frontier

下一個最小 sufficient card 不是容量 benchmark，而是補足 representative sample authority：

1. 固定 canonical 720-spec generation / dedupe / identity / partition / rank-unrank path，或明確裁定等價替代 authority。
2. 固定 CandidateDecision → explicit admission → Canonical TrialSpec 的 sample selection contract。
3. 指定代表性樣本覆蓋規則與抽樣/分層依據，並明確說明 why this sample is representative for E3 capacity。
4. 只有上述 authority 成立後，才執行隔離、有界 E3 benchmark 並記錄 wall time、candidate/sec、CPU、peak RSS、I/O、cleanup 與不可外推邊界。

## Claim Ledger

### Claim BC-CP2-RCA-001

```yaml
claim_id: BC-CP2-RCA-001
claim: BC-CP2 trace preflight inputs exist: B0P1-BC-002, B0P1-BC-004, and B0P1-BC-005 are present in the B0 fixed checkpoint evidence, and C0P2-CAP-004 is present in the C0 Phase 2 fixed capacity evidence.
classification: TRACE_PREFLIGHT_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98; a61f143ea5223b6af812e27aac0082121f781343
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/04-bc-checkpoint-input.md; docs/evidence/CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK/phase-2/05-capacity-and-intermediate-reuse-audit.md
source_range_or_section: B0 04 lines 58-133; C0 05 lines 122-137
observed_at: 2026-09-01T06:55:11Z
confidence: HIGH
conflict_with: treating BC-CP2 as untraceable or detached from B0/C0 fixed receipts.
implication: This slice can decide sample authority against the intended fixed evidence set.
open_question: none for trace existence.
owner: BC-CP2 evidence worker
```

### Claim BC-CP2-RCA-002

```yaml
claim_id: BC-CP2-RCA-002
claim: B0 fixed evidence proves exact mathematical 720-count and fixes E3 as current evaluator, but it explicitly does not prove canonical 720-spec generation, dedupe, identity, partition path, or daily/full-scan replay capacity.
classification: DENOMINATOR_PROVEN_SAMPLE_AUTHORITY_NOT_PROVEN
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/04-bc-checkpoint-input.md; docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/03-e1-e4-initial-cost-classification.md
source_range_or_section: B0 04 lines 13-31,58-133; B0 03 lines 3-25,39-83
observed_at: 2026-09-01T06:55:11Z
confidence: HIGH
conflict_with: using 720 exact count as authority to select a representative benchmark sample.
implication: Capacity measurement may use 720 as a denominator only after separate representative sample authority is fixed.
open_question: who admits the canonical sample selection contract before benchmark execution.
owner: B0/C0 Integrator
```

### Claim BC-CP2-RCA-003

```yaml
claim_id: BC-CP2-RCA-003
claim: C0 Phase 2 fixed evidence records no representative sample authority, representative sample size 0, and only a NON_REPRESENTATIVE_LEGAL_CHARACTERIZATION from a 1-scenario temp fixture.
classification: C0_FIXED_NON_REPRESENTATIVE_CHARACTERIZATION
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: a61f143ea5223b6af812e27aac0082121f781343
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK/phase-2/05-capacity-and-intermediate-reuse-audit.md
source_range_or_section: lines 18-45,62-64,122-137
observed_at: 2026-09-01T06:55:11Z
confidence: HIGH
conflict_with: promoting the C0 Phase 2 temp fixture into representative 720/full-daily capacity evidence.
implication: BC-CP2 must preserve full representative capacity as UNMEASURED.
open_question: which admitted CandidateDecision or canonical TrialSpec sample set should be measured.
owner: C0 capacity owner / BC-CP2 Integrator
```

### Claim BC-CP2-RCA-004

```yaml
claim_id: BC-CP2-RCA-004
claim: The canonical backlog keeps B1 and B2 not admitted and states C1 must wait for CandidateDecision to explicit admission to Canonical TrialSpec, so current committed backlog does not provide representative CandidateDecision or TrialSpec sample authority.
classification: BACKLOG_PHASE_GATE_BLOCKER
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: docs/RESEARCH_SPINE_BACKLOG.md
source_range_or_section: lines 260-276,408-425
observed_at: 2026-09-01T06:55:11Z
confidence: HIGH
conflict_with: admitting B1/B2/C1 implicitly through a capacity benchmark slice.
implication: BC-CP2 cannot create or infer the missing sample authority inside this receipt.
open_question: whether a future B1/B2/equivalent card will define sample selection and admission.
owner: Mainline Integrator / Owner
```

### Claim BC-CP2-RCA-005

```yaml
claim_id: BC-CP2-RCA-005
claim: This slice did not run an E3 benchmark because representative sample authority is missing; the correct verdict is NO_GO_MISSING_REPRESENTATIVE_SAMPLE_AUTHORITY rather than NON_REPRESENTATIVE_LEGAL_CHARACTERIZATION or numeric capacity.
classification: BC_CP2_VERDICT
source_repo: local candidate evidence
source_sha_or_version: c6e9870238fadf306b82875709de96d793a338d5
source_path_or_official_url: docs/tasks/2026-09-01_DISPATCH-NEW-TOP10-BC-CP2-REPRESENTATIVE-CAPACITY-AUTHORITY.md; docs/evidence/BC-CP2-REPRESENTATIVE-CAPACITY-AUTHORITY/01-sample-authority-and-capacity-receipt.md
source_range_or_section: task card lines 1-13 and this receipt sections Direct Answer, Authority Reconciliation, Measurement Receipt as first committed in candidate c6e9870238fadf306b82875709de96d793a338d5
observed_at: 2026-09-01T06:55:11Z
confidence: HIGH
conflict_with: running a benchmark from a convenience sample or inventing representative identity.
implication: The next frontier is authority repair/design, not capacity execution.
open_question: exact next card ID and owner for representative sample authority.
owner: BC-CP2 evidence worker
```
