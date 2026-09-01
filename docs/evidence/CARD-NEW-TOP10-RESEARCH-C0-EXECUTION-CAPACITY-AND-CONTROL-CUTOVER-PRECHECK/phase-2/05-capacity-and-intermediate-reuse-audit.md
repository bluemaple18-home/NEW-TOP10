# C0 Phase 2 — Capacity and Intermediate Reuse Audit

## Scope receipt

- Work item: `CARD-NEW-TOP10-RESEARCH-C0-EXECUTION-CAPACITY-AND-CONTROL-CUTOVER-PRECHECK`
- Phase: `phase-2`
- Candidate lineage: dispatch card is untracked input from this worker branch; parent HEAD before this evidence is `c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba`.
- NEW-TOP10 canonical source SHA: `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- B0 Phase 1 fixed SHA: `d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98`
- C0 Phase 1 fixed SHA: `c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba`
- AI Core dispatch baseline: `21801303adff285268f7646df94dc53da31a835f`
- Observed at: `2026-09-01T05:47:34Z`
- Boundary: evidence-only。未執行 production、daily quota、scheduler、publish、dual-write、canary、cutover 或 bridge removal；未修改 runtime/code/config/workflow/schema/database/queue/runner/scheduler/model/ranking/backtest。

## Direct answer

C0 Phase 2 仍不能定案 full daily capacity。固定 input 允許 C0 使用 `720` 作 formal denominator，並以 `E3` 作 current evaluator；但代表性 sample 權限不存在，`E2` reusable intermediate 仍是 `NOT_PROVEN`，`E4` forward-shadow cadence 仍是 `REQUIRED_BUT_UNCHARACTERIZED`。因此本文件交付 `MISSING_REPRESENTATIVE_SAMPLE_AUTHORITY`，不是 throughput benchmark。

## Capacity evidence table

| Field | Evidence value | Classification |
|---|---|---|
| immutable inputs | B0 fixed input: `matrix_size=720`, current evaluator `E3`, `E2=NOT_PROVEN`, `E4=REQUIRED_BUT_UNCHARACTERIZED` | measured/governing fact from fixed B0 evidence |
| sample authority | No B0/B2 admitted CandidateDecision or canonical TrialSpec sample authority is present in this worktree or dispatch | missing authority |
| representative sample size | `0` authorized representative candidates | measured authorization fact |
| synthetic characterization | attempted only as isolated `/private/tmp` characterization, but did not run because `.venv/bin/python` is absent | toolchain preflight fact |
| wall time | representative benchmark: `UNMEASURED`; failed toolchain preflight: `0.00 real / 0.00 user / 0.00 sys` | unknown / preflight fact |
| candidate/sec | `UNMEASURED`; no representative or synthetic runner execution completed | unknown |
| CPU | `UNMEASURED`; no benchmark execution completed | unknown |
| peak RSS | `UNMEASURED`; `/usr/bin/time -l` did not capture runner RSS because Python executable was absent | unknown |
| I/O | benchmark I/O `UNMEASURED`; no temp output created by the failed preflight | unknown / preflight fact |
| cache/intermediate reuse | Source proves feature frame is loaded once per matrix, but each scenario calls full portfolio replay; path-dependent candidate reuse is not proven | observed code fact |
| temporary output boundary | Intended boundary was `/private/tmp/top10-c0-phase2-characterization-*`; no benchmark output was produced | boundary fact |
| rerunnable command | `/usr/bin/time -l .venv/bin/python - <<'PY' ... synthetic 16-scenario runner characterization ... PY` | failed preflight command, not benchmark |

## Intermediate reuse audit

| Candidate intermediate | Evidence | Reuse conclusion |
|---|---|---|
| Price/features frame | `run_backtest_strategy_matrix.py` loads the price frame before the scenario loop. | Input-load reuse exists; it is not E2 candidate evaluation reuse. |
| Portfolio replay state | Each scenario calls `run_portfolio_from_price_frame(...)` with horizon/stop/take/group settings. | Current evaluation remains E3 path-dependent replay. |
| Native evidence replay bundle | Existing committed manifest reports two isolated cycles, capacity PASS, cleanup PASS, parity unchanged. | Useful pattern for bounded isolated evidence; not representative for 720 E3 daily capacity. |
| Adaptive shadow queue/proposal | Policy and proposal artifacts are shadow-only with canonical queue writes disabled. | Useful design reference for protected-surface parity; not executable capacity proof. |
| A6 compatibility projection | Derived from ledger/native receipts to legacy run history. | Rebuildable bridge output, not an intermediate that short-circuits E3 replay. |

## Fact / projection / unknown split

- Measured or governing facts: formal denominator `720`; current evaluator `E3`; `E2=NOT_PROVEN`; `E4=REQUIRED_BUT_UNCHARACTERIZED`; `.venv/bin/python` absent in this isolated worktree; no representative sample authority.
- Projection: if a future admitted benchmark uses native-evidence style isolation, it can record bytes/file count/parity/cleanup and reuse that measurement shape.
- Unknown: representative candidate/sec, wall time, CPU, peak RSS, I/O, full 720 daily feasibility, path-dependent intermediate reuse, E4 observation cadence.

## Claim ledger

### Claim C0P2-CAP-001

```yaml
claim_id: C0P2-CAP-001
claim: C0 Phase 2 capacity input is fixed to matrix_size=720, current evaluator=E3, E2=NOT_PROVEN, E4=REQUIRED_BUT_UNCHARACTERIZED, and context axes do not multiply the denominator.
classification: GOVERNING_INPUT_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: d2c15a19d5bc8788a3d5d447ff82a9bdd43b4d98
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-RESEARCH-B0-MATRIX-AUTHORITY-AND-SEARCH-DESIGN/phase-1/04-bc-checkpoint-input.md
source_range_or_section: lines 17-35,153-170
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: numeric capacity estimates without benchmark; multiplying exact regime/episode/dataset/ranking/stage into 720
implication: Capacity planning may use 720 as denominator but must keep throughput and context-specific replay cost unknown until measured.
open_question: representative E3 benchmark and E4 cadence remain missing.
owner: C0 capacity owner
```

### Claim C0P2-CAP-002

```yaml
claim_id: C0P2-CAP-002
claim: Current strategy-matrix code loads features once per matrix, but each scenario still invokes full portfolio replay, so path-dependent E2 reusable candidate evaluation is not proven.
classification: OBSERVED_CODE_FACT
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: scripts/run_backtest_strategy_matrix.py
source_range_or_section: lines 580-624,705-724
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: treating features_load_once_per_matrix as reusable candidate evaluation.
implication: C0 should size current performance evaluation as E3 replay, not vectorized or cached E2 evaluation.
open_question: which ranking/entry/holding/exit intermediates could be reused without changing backtest math.
owner: Backtest/runtime owner
```

### Claim C0P2-CAP-003

```yaml
claim_id: C0P2-CAP-003
claim: Native evidence activation and replay bundle provide a reusable isolation/parity/capacity-recording pattern, but their two historical bounded cycles are not a B0 representative 720-capacity benchmark.
classification: REUSABLE_INTERMEDIATE_PATTERN_NOT_CAPACITY_PROOF
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070
source_path_or_official_url: docs/evidence/CARD-NEW-TOP10-NATIVE-EVIDENCE-ACTIVATION-V1/capacity_and_real_canary.json; scripts/native_evidence_replay_bundle.py
source_range_or_section: capacity_and_real_canary.json lines 1-103; native_evidence_replay_bundle.py lines 34-46,188-430
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: using native evidence canary pass as 720-matrix throughput proof.
implication: Future benchmark should copy the measurement envelope, not the capacity conclusion.
open_question: admitted representative sample identity and measurement command remain absent.
owner: C0 benchmark owner
```

### Claim C0P2-CAP-004

```yaml
claim_id: C0P2-CAP-004
claim: This worker could not run even a synthetic bounded characterization through the project Python path because `.venv/bin/python` is absent; no benchmark output, candidate/sec, CPU, RSS, or I/O measurement was produced.
classification: LOCAL_TOOLCHAIN_PREFLIGHT_FACT
source_repo: local isolated worktree
source_sha_or_version: c7d30f3dc1da413ab40ce143e1f6931f2d8a97ba
source_path_or_official_url: <isolated-worktree>
source_range_or_section: command `/usr/bin/time -l .venv/bin/python - <<'PY' ... PY` returned `time: .venv/bin/python: No such file or directory`; `0.00 real 0.00 user 0.00 sys`
observed_at: 2026-09-01T05:47:34Z
confidence: HIGH
conflict_with: claiming a local runner benchmark was completed in this candidate.
implication: Capacity evidence must stay at missing-authority / unmeasured status.
open_question: whether a future admitted worker may create/sync `.venv` or use an approved existing environment.
owner: C0 capacity worker / environment owner
```
