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
- Repair observation: `2026-09-01T06:12:53Z`; parent before repair `aab6760436be0bc3fadbe860f61502c4744dd106`.
- Boundary: evidence-only。未執行 production、daily quota、scheduler、publish、dual-write、canary、cutover 或 bridge removal；未修改 runtime/code/config/workflow/schema/database/queue/runner/scheduler/model/ranking/backtest。

## Direct answer

C0 Phase 2 仍不能定案 full daily capacity。固定 input 允許 C0 使用 `720` 作 formal denominator，並以 `E3` 作 current evaluator；但代表性 sample 權限不存在，`E2` reusable intermediate 仍是 `NOT_PROVEN`，`E4` forward-shadow cadence 仍是 `REQUIRED_BUT_UNCHARACTERIZED`。本次 repair 只補到 `NON_REPRESENTATIVE_LEGAL_CHARACTERIZATION`：證明最小 E3 runner envelope 可在隔離 temp fixture 上執行並量到資源足跡；不得外推為 720/full-daily capacity。

## Capacity evidence table

| Field | Evidence value | Classification |
|---|---|---|
| immutable inputs | B0 fixed input: `matrix_size=720`, current evaluator `E3`, `E2=NOT_PROVEN`, `E4=REQUIRED_BUT_UNCHARACTERIZED` | measured/governing fact from fixed B0 evidence |
| sample authority | No B0/B2 admitted CandidateDecision or canonical TrialSpec sample authority is present in this worktree or dispatch | missing authority |
| representative sample size | `0` authorized representative candidates | measured authorization fact |
| characterization authority | `NON_REPRESENTATIVE_LEGAL_CHARACTERIZATION`; temp fixture only: 1 strategy-matrix scenario, 1 ranking file, 2 ranking rows, 12 OHLC feature rows | measured characterization fact, non-representative |
| wall time | representative benchmark: `UNMEASURED`; non-representative characterization: `1.060459s` wall | unknown / measured characterization fact |
| candidate/sec | representative benchmark: `UNMEASURED`; non-representative characterization: `0.942988` scenario/sec for 1 scenario | unknown / measured characterization fact |
| CPU | representative benchmark: `UNMEASURED`; non-representative characterization: `0.671197s` user CPU, `0.145377s` system CPU | unknown / measured characterization fact |
| peak RSS | representative benchmark: `UNMEASURED`; non-representative characterization: raw `ru_maxrss=189988864` from child process resource accounting | unknown / measured characterization fact |
| I/O | representative benchmark: `UNMEASURED`; non-representative temp files before cleanup: features `4226` bytes, ranking `368` bytes, output JSON `4922` bytes, output Markdown `287` bytes; resource counters `inblock_delta=0`, `oublock_delta=0` | unknown / measured characterization fact |
| cache/intermediate reuse | Source proves feature frame is loaded once per matrix, but each scenario calls full portfolio replay; path-dependent candidate reuse is not proven | observed code fact |
| temporary output boundary | Fresh temp prefix `<fresh-temp-prefix>`; observed instance is recorded as `<fresh-temp>` only; cleanup parity: removed, and no matching temp dirs remained afterward | boundary / cleanup fact |
| rerunnable command | Use `<repo-root>/.venv/bin/python` to create the tiny fixture in fresh temp, then invoke `scripts/run_backtest_strategy_matrix.py --max-ranking-files 1 --top-n 2 --horizons 3 --stop-loss-pcts none --take-profit-pcts none --max-group-exposures none --output <temp>/output/strategy_matrix.json`; no dependency install/sync | measured characterization command |

## Bounded E3 characterization receipt

- Classification: `NON_REPRESENTATIVE_LEGAL_CHARACTERIZATION`
- Interpreter: `<repo-root>/.venv/bin/python`, Python `3.12.12`, reused read-only from canonical project environment; no dependency install/sync.
- Executed code: candidate worktree `scripts/run_backtest_strategy_matrix.py` on parent `aab6760436be0bc3fadbe860f61502c4744dd106`; runtime code content remains bounded to canonical source SHA `35bb9927eb0eac9a624dcaf0dcffcbf88857c070`.
- Fixture identity: generated only under `<fresh-temp-prefix>`; 1 ranking file named `ranking_2026-01-02.csv`; 2 ranking rows (`1101`, `2330`); 12 feature rows (`2` stocks × `6` business days from `2026-01-02`); horizon `3`; stop/take/group all `none`.
- Runner command shape: `<repo-root>/.venv/bin/python scripts/run_backtest_strategy_matrix.py --rankings-dir <temp>/rankings --features <temp>/features.parquet --max-ranking-files 1 --top-n 2 --horizons 3 --stop-loss-pcts none --take-profit-pcts none --max-group-exposures none --output <temp>/output/strategy_matrix.json`
- Result: return code `0`; output summary showed `scenario_count=1`, `scenario_rows=1`, `best_scenario_id=h3_slnone_tpnone_gcnone`, `features_load_policy=load_once_per_matrix`, `resource_mode=read_existing_artifacts_only`.
- Resource measurement: wall `1.060459s`; candidate/sec `0.942988`; user CPU `0.671197s`; system CPU `0.145377s`; peak RSS raw `ru_maxrss=189988864`; `inblock_delta=0`; `oublock_delta=0`.
- Output boundary before cleanup: `features.parquet` `4226` bytes; `rankings/ranking_2026-01-02.csv` `368` bytes; `output/strategy_matrix.json` `4922` bytes; `output/strategy_matrix.md` `287` bytes.
- Cleanup/parity: temp instance removed after measurement; later `<tmp-scan>` found no `<fresh-temp-prefix>` directories.
- Measurement limit: Arrow emitted sandbox sysctl warnings while probing CPU cache metadata; the runner still returned code `0`. These warnings are environment characterization noise, not capacity failure evidence.

## Intermediate reuse audit

| Candidate intermediate | Evidence | Reuse conclusion |
|---|---|---|
| Price/features frame | `run_backtest_strategy_matrix.py` loads the price frame before the scenario loop. | Input-load reuse exists; it is not E2 candidate evaluation reuse. |
| Portfolio replay state | Each scenario calls `run_portfolio_from_price_frame(...)` with horizon/stop/take/group settings. | Current evaluation remains E3 path-dependent replay. |
| Native evidence replay bundle | Existing committed manifest reports two isolated cycles, capacity PASS, cleanup PASS, parity unchanged. | Useful pattern for bounded isolated evidence; not representative for 720 E3 daily capacity. |
| Adaptive shadow queue/proposal | Policy and proposal artifacts are shadow-only with canonical queue writes disabled. | Useful design reference for protected-surface parity; not executable capacity proof. |
| A6 compatibility projection | Derived from ledger/native receipts to legacy run history. | Rebuildable bridge output, not an intermediate that short-circuits E3 replay. |

## Fact / projection / unknown split

- Measured or governing facts: formal denominator `720`; current evaluator `E3`; `E2=NOT_PROVEN`; `E4=REQUIRED_BUT_UNCHARACTERIZED`; no representative sample authority; canonical project interpreter is available for read-only characterization; one non-representative E3 temp fixture completed with measured wall/CPU/RSS/I/O envelope.
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
claim: A smallest legal E3 characterization completed through candidate-worktree code using the existing canonical project interpreter and fresh temp fixture, measuring 1 scenario in 1.060459s wall / 0.942988 scenario per second with raw ru_maxrss=189988864, but it is explicitly non-representative and cannot be extrapolated to the 720 daily denominator.
classification: NON_REPRESENTATIVE_LEGAL_CHARACTERIZATION
source_repo: local isolated worktree / bluemaple18-home/NEW-TOP10
source_sha_or_version: candidate parent aab6760436be0bc3fadbe860f61502c4744dd106; canonical source 35bb9927eb0eac9a624dcaf0dcffcbf88857c070; Python 3.12.12 via <repo-root>/.venv/bin/python
source_path_or_official_url: scripts/run_backtest_strategy_matrix.py; <fresh-temp>/features.parquet; <fresh-temp>/rankings/ranking_2026-01-02.csv; <fresh-temp>/output/strategy_matrix.json
source_range_or_section: Bounded E3 characterization receipt in this file; command shape `<repo-root>/.venv/bin/python scripts/run_backtest_strategy_matrix.py --rankings-dir <temp>/rankings --features <temp>/features.parquet --max-ranking-files 1 --top-n 2 --horizons 3 --stop-loss-pcts none --take-profit-pcts none --max-group-exposures none --output <temp>/output/strategy_matrix.json`; output summary scenario_count=1, returncode=0, cleanup_removed=true
observed_at: 2026-09-01T06:12:53Z
confidence: HIGH
conflict_with: claiming representative 720/full-daily capacity from a single temp fixture, verifier pass, or convenience sample.
implication: C0 may record an executable E3 envelope, but C1 capacity remains blocked until an admitted representative sample and full measurement authority exist.
open_question: which admitted CandidateDecision or canonical TrialSpec sample set should be used for representative 720-capacity measurement.
owner: C0 capacity worker / environment owner
```
