# BC-CP2-R3 最小 Capacity-only Fixture Adapter 實作與驗收 Receipt

## Scope receipt

- 工作名稱：`BC-CP2-R3 最小 Capacity-only Fixture Adapter`
- Slice ID：`BC-CP2-R3-CAPACITY-ADAPTER-01`
- Verdict：`IMPLEMENTATION_GO_BOUNDED_CAPACITY_ONLY_ADAPTER / FULL_720_NOT_EXECUTED`
- Candidate 起點：`931f4b5c2b539940f0b1b8e5957dddd7df1a1505`
- Pre-repair candidate：`edd484b2795a2daee9210c18ea600454e6b0f1fc`
- Canonical main：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- R1 fixed SHA：`319eee83cdf6001f094c5bd2597657aa2d3d7c40`
- R2 fixed SHA：`931f4b5c2b539940f0b1b8e5957dddd7df1a1505`
- Formal 720 authority SHA：`1e9ed61e2e5c86adf2159e095ff241ef13127e80`
- Dispatch card hash：`sha256:dcc11205f6a42d3c1676bbf1096306f725c608b83d294aae687fe2d46df0e939`
- Observed at：`2026-09-01T09:17:38Z`
- Boundary：本卡只新增最小 capacity-only harness、red-capable tests 與本 evidence。未修改既有 runner/backtest math/config/configured data/ranking generator/history/features/model/queue/scheduler/workflow/production，未生成 production/configured rankings，未執行 full 720 benchmark，未 merge/push/改 Issue/deploy/external write，未准入 B0 Phase 2、B1 或 C1。

## Direct answer

R3 已建立最小 first-party capacity-only fixture adapter seam。新 harness 會：

1. 從 canonical formal family 取得 expected `720` IDs 與 `sha256:78cd9b8b6fa39935f9037d5b4c8dde3fcc2ae39955414aa51bda96dafb69f6b4` hash。
2. 在任何 filesystem mutation 前先完成 input authority gate：`--requested-ids-file` 只接受完整 canonical 720 family 的 count/set/order；任意 bounded subset 只能用內部/測試用 `--max-scenarios`。
3. 只在 caller-provided、非 broad root、非 repo 內、既有空目錄或不存在的 work root 建立 synthetic capacity fixture；receipt output 必須是該 work root 內的 file，不能等於 root 本身。
4. 用既有 `scripts/run_backtest_strategy_matrix.py` 的 `build_payload(...)` 執行 bounded subset，不重寫 runner/backtest math。
5. 將實際 scenario parameters 重算 canonical `combination_id`，並 fail closed 拒絕 missing、extra、duplicate、unknown、requested/executed mismatch。
6. 明確標出 execution-order boundary：strategy-matrix output 是 score-sorted；本 harness 只主張 requested/executed canonical set/hash parity，不主張 execution order parity。
7. 輸出 capacity-only receipt，包含 scenario count、ID count/hash、wall time、candidate/sec、CPU user/sys、peak RSS、read/write I/O、output sizes、pre/post fixture manifest parity、cleanup、`CAPACITY_ONLY / NOT_RESEARCH_EVIDENCE` boundary。

本卡只驗證 bounded subset 與 identity/safety attacks；full 720 benchmark 未執行。下一張 R4 若要跑 full 720，必須另以此 harness 執行 `--full-family` 或完整 canonical IDs manifest，並由 Mainline/Owner 明確授權。

## P1 repair receipt

Pre-repair candidate `edd484b2795a2daee9210c18ea600454e6b0f1fc` 被 Mainline review 判定 `NO-GO`，原因是：

1. order-only mismatch 被 sorted/set parity 掩蓋；
2. `--requested-ids-file` 對外介面看似可接受任意 canonical subset，但實際 runner seam 只安全支援完整 canonical family 或內部 bounded prefix；
3. cleanup/safe-root 邊界仍可收緊，且 invalid manifest 不應先建立 work root。

本 repair/amend 將 requested manifest gate 改為完整 canonical 720 count/set/order，新增 wrong-count、duplicate、unknown、order-only、public run invalid-manifest no-write attack；並將 fixture cleanup 綁定到 resolved `work_root/fixture`，用 `finally` 覆蓋 runner exception。

## Changed-file allowlist

| Path | Purpose |
|---|---|
| `scripts/run_capacity_only_strategy_matrix_harness.py` | 新增最小 capacity-only adapter/harness；不修改既有 runner。 |
| `tests/test_capacity_only_strategy_matrix_harness.py` | 新增 red-capable tests：bounded success、parity attacks、requested-manifest full canonical order gate、invalid-manifest no-write、safe-root/output guards、runner-exception cleanup、metrics/cleanup schema。 |
| `docs/evidence/BC-CP2-R3-MINIMAL-CAPACITY-ONLY-FIXTURE-ADAPTER/01-implementation-and-verification-receipt.md` | 本卡 evidence/handoff。 |

## CodeGraph preflight

| Check | Result |
|---|---|
| `codegraph_status(projectPath=<repo-root>)` | `FAILED` — CodeGraph not initialized in isolated worktree. |
| `codegraph_context(projectPath=<repo-root>, task=BC-CP2-R3...)` | `FAILED` — same initialization boundary. |
| Fallback | Used bounded source/test/evidence reads with `rg` and line-numbered source excerpts. No CodeGraph initialization was performed. |

## Red → green receipt

| Gate | Command shape | Observed result |
|---|---|---|
| Red-capable test before implementation | `<python> -m pytest tests/test_capacity_only_strategy_matrix_harness.py -q` | exit code `2`; collection failed with `ImportError: cannot import name 'run_capacity_only_strategy_matrix_harness' from 'scripts'`. |
| Mainline P1 review on pre-repair candidate | Review of `edd484b2795a2daee9210c18ea600454e6b0f1fc` | `NO-GO`; required order-only manifest gate, honest requested-IDs interface, and stricter cleanup/no-write-on-invalid-input boundary. |
| Targeted green after repair | `<python> -m pytest tests/test_capacity_only_strategy_matrix_harness.py -q` | `7 passed in 1.42s`. |
| Affected regression after repair | `<python> -m pytest tests/test_capacity_only_strategy_matrix_harness.py tests/test_research_parameter_catalog_projection.py tests/test_regime_research_autonomy.py::test_strategy_matrix_filters_ranking_files_before_replay tests/test_regime_research_autonomy.py::test_strategy_matrix_excludes_episode_tail_without_complete_holding_window tests/test_regime_research_autonomy.py::test_exact_match_replay_rejects_holding_window_crossing_episode tests/test_regime_research_autonomy.py::test_strategy_matrix_replay_args_preserve_regime_history -q` | `18 passed in 0.83s`. |
| py_compile | `<python> -m py_compile scripts/run_capacity_only_strategy_matrix_harness.py scripts/run_backtest_strategy_matrix.py scripts/run_autonomous_research.py scripts/run_portfolio_replay.py scripts/run_backtest_replay.py` | exit code `0`. |
| Bounded CLI smoke after repair | `<python> scripts/run_capacity_only_strategy_matrix_harness.py --work-root <temp-work-root> --output <temp-work-root>/receipt.json --max-scenarios 2` | exit code `0`; stdout reported `status=OK`, `scenario_count=2`, `parity=PASS`; receipt reported schema `capacity-only-strategy-matrix-harness.v1`, manifest policy `INTERNAL_BOUNDED_PREFIX_ONLY`, execution order boundary present, cleanup `PASS true`, manifest parity `PASS`, boundary `CAPACITY_ONLY NOT_RESEARCH_EVIDENCE`. |
| diff hygiene | `git diff --check` | exit code `0`. |

CLI smoke stderr contained Arrow CPU-cache sysctl warnings from the sandboxed runtime. The harness returned `0`, wrote only under `<temp-work-root>`, and cleanup removed the synthetic fixture.

## Adapter contract verification

| Requirement | Evidence | Status |
|---|---|---|
| Canonical formal family source | `formal_family()` calls `parameter_combinations(...)` and `statistical_family_contract(...)`; tests assert expected count `720`. | `PASS` |
| Requested manifest authority | `select_requested_scenarios(...)` requires exactly one selector; public requested IDs must match full canonical family count/set/order; bounded subset is available only through `max_scenarios` internal/test path. | `PASS` |
| Input failure has no filesystem side effect | Public `run_capacity_probe(...)` invalid manifest test asserts wrong-count requested manifest raises before work root exists. | `PASS` |
| Canonical ID parity | `validate_requested_executed_parity(...)` recomputes IDs from executed scenario parameters and compares canonical sorted set/hash, while receipt labels runner output order as score-sorted. | `PASS` |
| Missing/extra/duplicate/unknown/mismatch fail closed | Tests cover duplicate executed IDs, missing executed ID, unknown executed ID, unknown requested ID, wrong-count requested manifest, duplicate requested manifest, and order-only requested manifest swap. | `PASS` |
| Existing runner reuse | Harness invokes `strategy_matrix.build_payload(...)`; no existing runner/backtest math file was modified. | `PASS` |
| Repo-write-free guard | `ensure_safe_work_root(...)` rejects broad roots, repo-contained work roots, and existing non-empty roots; `ensure_output_inside_work_root(...)` rejects receipt output outside work root or equal to work root. | `PASS` |
| Fixture capability | Synthetic fixture has top_n `10`, max horizon `20`, one temp ranking file, 10 stocks, at least 22 trade days, and temp group map scoped into replay args. | `PASS` |
| Metrics schema | Receipt records wall time, candidate/sec, user/sys CPU, peak RSS, inblock/oublock deltas, output sizes. | `PASS` |
| I/O parity and cleanup | Fixture manifest hash is collected before/after runner call; tests assert pre/post hash equality, cleanup PASS, and runner exception removes `work_root/fixture` in `finally`. | `PASS` |
| Non-extrapolation | Receipt boundary and tests assert `CAPACITY_ONLY` and `NOT_RESEARCH_EVIDENCE`; R3 did not run full 720. | `PASS` |

## Source hashes and protected scope

| Path | SHA-256 |
|---|---|
| `scripts/run_capacity_only_strategy_matrix_harness.py` | `sha256:b99f7c58a130aa7a705f25b28e99c4f5b3100fdefbb23dbbb5d5a4040aec2400` |
| `tests/test_capacity_only_strategy_matrix_harness.py` | `sha256:1932b1058a30f452f72e2751947788d6cbbb002c977272aeaba8dcceb4e48597` |
| `scripts/run_backtest_strategy_matrix.py` | `sha256:39b42aac6d7c232c9bbb4f1d8981b55ca43826758d91cd3a45281ff19f590b43` |
| `scripts/run_autonomous_research.py` | `sha256:2c5b9b11c22b13aeae78045a721c362f1ad65390ea69eac075e69f0807df951c` |
| `config/research_parameter_catalog.json` | `sha256:e88079414dfae381b96bd4a46326e38b8288447710008ecfe9c1d73b6ec66500` |
| `config/regime_research_contract.json` | `sha256:e3ada41e5a9de4f471750f298718ba815582db550abd9b537a73b66bd818bc34` |
| `<local-data-root>/artifacts/market_regime_history_2026-05-29.json` | `sha256:4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70` |

Protected-scope interpretation：`git diff --name-only 931f4b5c2b539940f0b1b8e5957dddd7df1a1505..HEAD` is limited to the allowlist above after this evidence is amended. Existing runner/backtest/config/configured artifact hashes are unchanged from pre-R3 observations.

## Next frontier

`BC-CP2-R4-FULL-720-CAPACITY-ONLY-BENCHMARK`

Minimum R4 entry conditions:

1. Mainline explicitly authorizes full 720 execution.
2. Run this R3 harness with `--full-family` or a canonical requested IDs manifest that exactly equals the formal 720 family count/set/order.
3. Keep all writes inside `<temp-work-root>` or an explicitly authorized evidence artifact path.
4. Record wall time, candidate/sec, CPU, peak RSS, I/O, output sizes, manifest parity, cleanup and protected hashes.
5. Preserve `CAPACITY_ONLY / NOT_RESEARCH_EVIDENCE`; do not claim research-valid workload, production readiness, B0 Phase 2, B1 or C1 admission.

## Claim Ledger

### Claim BC-CP2-R3-001

```yaml
claim_id: BC-CP2-R3-001
claim: The new harness obtains the canonical formal family from first-party committed generation functions and records the expected 720 count/hash before selecting any bounded capacity subset; public requested IDs must equal the complete canonical family in canonical order.
classification: CANONICAL_FORMAL_FAMILY_INPUT_GO
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: 35bb9927eb0eac9a624dcaf0dcffcbf88857c070; local candidate file sha256:b99f7c58a130aa7a705f25b28e99c4f5b3100fdefbb23dbbb5d5a4040aec2400
source_path_or_official_url: scripts/run_capacity_only_strategy_matrix_harness.py; scripts/run_autonomous_research.py; app/research/parameter_catalog.py
source_range_or_section: harness lines 113-172,400-420; run_autonomous_research.py lines 493-608; parameter_catalog.py lines 87-178
observed_at: 2026-09-01T09:17:38Z
confidence: HIGH
conflict_with: hard-coded 720 counts, non-canonical ad hoc scenario IDs, or arbitrary requested-ID subsets through the public manifest interface.
implication: Future capacity benchmark can use this harness as a canonical family/ID input seam without pretending bounded subsets are public manifest authority.
open_question: full-family benchmark remains unexecuted until R4 authority.
owner: BC-CP2-R3 implementation worker
```

### Claim BC-CP2-R3-002

```yaml
claim_id: BC-CP2-R3-002
claim: Requested/executed parity fails closed for duplicate, unknown, missing, extra, and mismatch cases by recomputing canonical IDs from executed scenario parameters; execution parity is canonical set/hash parity only because strategy-matrix output order is score-sorted.
classification: CANONICAL_ID_PARITY_FAIL_CLOSED_GO
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: local candidate file sha256:b99f7c58a130aa7a705f25b28e99c4f5b3100fdefbb23dbbb5d5a4040aec2400; test file sha256:1932b1058a30f452f72e2751947788d6cbbb002c977272aeaba8dcceb4e48597
source_path_or_official_url: scripts/run_capacity_only_strategy_matrix_harness.py; tests/test_capacity_only_strategy_matrix_harness.py
source_range_or_section: harness lines 212-247,486-511; tests lines 38-112
observed_at: 2026-09-01T09:17:38Z
confidence: HIGH
conflict_with: treating requested_trial_spec_ids metadata-only receipt fields as execution authority or claiming runner execution order parity.
implication: R3 closes the R2 gap for capacity-only requested/executed ID parity without modifying the existing runner.
open_question: B1 direct TrialSpec execution remains outside this harness.
owner: BC-CP2-R3 implementation worker
```

### Claim BC-CP2-R3-003

```yaml
claim_id: BC-CP2-R3-003
claim: The harness is repo-write-free by contract: it rejects broad roots, repo-contained roots, existing non-empty roots, output outside/equal to work root, validates public requested manifests before creating the work root, and removes only the resolved work_root/fixture directory after execution or runner exception.
classification: REPO_WRITE_FREE_AND_CLEANUP_GUARD_GO
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: local candidate file sha256:b99f7c58a130aa7a705f25b28e99c4f5b3100fdefbb23dbbb5d5a4040aec2400; test file sha256:1932b1058a30f452f72e2751947788d6cbbb002c977272aeaba8dcceb4e48597
source_path_or_official_url: scripts/run_capacity_only_strategy_matrix_harness.py; tests/test_capacity_only_strategy_matrix_harness.py
source_range_or_section: harness lines 78-110,334-344,400-458; tests lines 100-153,176-190; bounded CLI smoke in this receipt
observed_at: 2026-09-01T09:17:38Z
confidence: HIGH
conflict_with: using repo artifacts as capacity-probe output, deleting broad/unverified paths, or leaving temp fixture state after failed runner execution.
implication: Capacity-only probes can be isolated from production/configured artifacts and can prove cleanup/parity before R4.
open_question: R4 must still choose an authorized temp/evidence output root for full 720.
owner: BC-CP2-R3 implementation worker
```

### Claim BC-CP2-R3-004

```yaml
claim_id: BC-CP2-R3-004
claim: The synthetic capacity fixture supports max horizon 20, top_n 10, group exposure plumbing, ranking/OHLC dates, and explicit CAPACITY_ONLY / NOT_RESEARCH_EVIDENCE labeling, while still reusing the existing strategy matrix build path.
classification: CAPACITY_ONLY_FIXTURE_AND_RUNNER_REUSE_GO
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: local candidate file sha256:b99f7c58a130aa7a705f25b28e99c4f5b3100fdefbb23dbbb5d5a4040aec2400; canonical runner sha256:39b42aac6d7c232c9bbb4f1d8981b55ca43826758d91cd3a45281ff19f590b43
source_path_or_official_url: scripts/run_capacity_only_strategy_matrix_harness.py; scripts/run_backtest_strategy_matrix.py; tests/test_capacity_only_strategy_matrix_harness.py
source_range_or_section: harness lines 250-397,438-453,470-551; strategy_matrix.py lines 580-669,692-783; tests lines 11-35,156-173
observed_at: 2026-09-01T09:17:38Z
confidence: HIGH
conflict_with: creating a second backtest runner or modifying existing backtest math.
implication: R3 adds only an adapter/harness seam; actual strategy-matrix computation remains first-party runner code.
open_question: full 720 runtime envelope remains unmeasured.
owner: BC-CP2-R3 implementation worker
```

### Claim BC-CP2-R3-005

```yaml
claim_id: BC-CP2-R3-005
claim: Verification passed for red→green, Mainline P1 repair, bounded success, identity attacks, requested-manifest full canonical order attacks, invalid-manifest no-write, safe-root/output guards, runner-exception cleanup, metrics/cleanup schema, affected regressions, py_compile, and protected configured artifact hash; no full 720 benchmark was executed.
classification: R3_VERIFICATION_GO_FULL_720_NOT_EXECUTED
source_repo: bluemaple18-home/NEW-TOP10
source_sha_or_version: local candidate verification at parent 931f4b5c2b539940f0b1b8e5957dddd7df1a1505; configured artifact sha256:4501c9ce8f8886bba731c70226379403644a69d73dd162586084691f75eb2a70
source_path_or_official_url: tests/test_capacity_only_strategy_matrix_harness.py; scripts/run_capacity_only_strategy_matrix_harness.py; <local-data-root>/artifacts/market_regime_history_2026-05-29.json
source_range_or_section: Red → green receipt; Adapter contract verification; Source hashes and protected scope sections in this receipt
observed_at: 2026-09-01T09:17:38Z
confidence: HIGH
conflict_with: claiming full-720 capacity numbers, production readiness, or research-valid workload authority from bounded R3 tests.
implication: Mainline may open R4 full-720 capacity-only benchmark card after independent review, but R3 itself is not benchmark/admission evidence.
open_question: R4 full-family wall time, candidate/sec, CPU, RAM, I/O and output size remain unmeasured.
owner: BC-CP2-R3 implementation worker
```
