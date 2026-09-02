# B0+C0/BC-CP2 current-tip mainline acceptance review

👉 [假設與目標確認] 目標是驗收目前已整合 main 是否可作 B0+C0/BC-CP2 的非 production 新基線；邊界是只審 current tracked tree，不修 code、不 commit、不 push、不 deploy、不刷新資料、不執行 production/capture/replay/outcome/sealed access；驗收是 `REVIEW_GO_CURRENT_TIP_BASELINE` 或 `REVIEW_NO_GO`。

## Verdict

`REVIEW_GO_CURRENT_TIP_BASELINE`

Reviewed current tip：`db70dde285256af38c17129362b6cbd542d9a977`

This GO only accepts the current integrated B0+C0/BC-CP2 state as a local, non-production baseline for future mainline arbitration. It does not admit B0 Phase 2, C0 Phase 2 execution, B1, C1, Entry-Regime feasibility, Forecast activation, R15, production, push, deploy, scheduler, registry, capture, replay, benchmark, training, outcome, or external writes.

## Fixed Facts

- Canonical base：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
- Forecast-integrated pre-B0 main：`02730a7f02d90f669a284be12cfbb02885cc1b73`
- B0 fixed tip：`1e9ed61e2e5c86adf2159e095ff241ef13127e80`; merge commit `b49b3532f0ac3849a841816c00aae9267fb86a03`
- C0/BC-CP2 fixed tip：`16134bc23992d4ba6a3f254b96c3f6e6eb325616`; merge commit `a6fbf839153e66f267e3855b1893147a888e2ef6`
- Current integrated tip：`db70dde285256af38c17129362b6cbd542d9a977`
- Merge order verified：Forecast -> B0 -> C0/BC-CP2 -> ops recovery -> R13 authority/registration -> R14 admission NO-GO.
- Superseded card fact：the older untracked fixed-tip review card kept `current main=02730a7` and `R13 must remain BLOCKED`; the current-tip task card correctly supersedes those facts.

## Findings

No P0/P1 blocking findings.

P3 residuals:

- C0 Phase 2 dispatch card self-references a prior `ADMIT_C0_PHASE_2`, but this tree has no standalone BC-CP1 decision artifact and the canonical backlog still says Phase 2 is not admitted. The accepted interpretation is narrow: the merged Phase 2 files remain design/evidence artifacts; this review does not newly admit, renew, or extend C0-P2 authority.
- The old fixed-tip task card remains untracked and stale. It is non-blocking because the current-tip task card explicitly supersedes its stale current-main and R13-blocked assumptions.
- Full-720 benchmark was not rerun in this review. This is intentional: current acceptance allowed focused tests and isolated temp probes only; the committed R4 receipt remains the source for full-720 capacity-only evidence.
- The worktree still has unrelated untracked task/handoff cards. This review treats them as non-authoritative unless they are explicitly cited by the current-tip task card.

## Spec Axis

- B0 exact matrix authority remains self-consistent: `proven_legal_count=720`, deterministic product `4 x 6 x 6 x 5 = 720`, and `phase_2_admission=NOT_ADMITTED`.
- B0 E1-E4 classification remains bounded: E1 formal 720 identity confirmed; E2 reusable candidate evaluator not proven; E3 current execution class confirmed; E4 required but capacity-uncharacterized.
- C0 Phase 1/2 evidence keeps design/checkpoint results bounded: Phase 1 does not approve Phase 2/C1/cutover/runtime mutation, the merged Phase 2 files do not by themselves provide current admission authority, and C1 remains blocked by representative capacity and control prerequisites.
- BC-CP2 capacity-only harness remains synthetic and non-production: `CAPACITY_ONLY`, `NOT_RESEARCH_EVIDENCE`, `ranking_generation=false`, `production_invocation=false`, and repo artifact writes disabled.
- R13 current status is `REGISTERED_FORWARD_BUNDLE_VERIFIED` for one exact committed bundle only, with `downstream_authority=NONE`.
- R14 current status is `NO_GO_R14_INSUFFICIENT_DECISION_VALUE`; Entry-Regime feasibility, preregistration, B0 Phase 2, B1, C1, and production remain `NOT_ADMITTED`.

## Standards Axis

- CodeGraph-first requirement satisfied: index available with 833 files / 17,789 nodes; context query was run before source/test review.
- Commit ancestry and merge order passed: canonical base is ancestor of Forecast pre-B0; Forecast pre-B0 is ancestor of B0 merge; B0 merge is ancestor of C0/BC merge; C0/BC merge is ancestor of current tip.
- Merge payload audit passed: `b49b353` contains only the B0 five-file payload; `a6fbf83` contains the C0/BC payload plus the capacity-only harness/test.
- Relevant forecast-path drift passed: no forecast source/test/config path changed after `02730a7` in the B0/C0/BC merge range.
- Scoped whitespace audit passed: `git diff --check 02730a7..db70dde -- app scripts tests docs/evidence docs/tasks config` returned exit 0.
- Hardcoded local path audit passed for blocking scope: capacity harness uses `/private/tmp` only as a broad-root rejection guard; evidence commands use `<tmp>`/isolated temp roots. No blocking local path dependency was found in accepted runtime/test scope.

## Verification

- `git status --short --branch`: current branch `main`, ahead of `origin/main` by 13 commits; untracked task/handoff cards preserved.
- `git merge-base --is-ancestor 35bb992 02730a7`: exit 0.
- `git merge-base --is-ancestor 02730a7 b49b353`: exit 0.
- `git merge-base --is-ancestor b49b353 a6fbf83`: exit 0.
- `git merge-base --is-ancestor a6fbf83 db70dde`: exit 0.
- `git show --cc --stat b49b353`: only B0 evidence/task payload, 5 files changed.
- `git show --cc --stat a6fbf83`: C0/BC evidence/task payload plus `scripts/run_capacity_only_strategy_matrix_harness.py` and `tests/test_capacity_only_strategy_matrix_harness.py`, 35 files changed.
- `git diff --name-only 02730a7..a6fbf83 -- app/research app/trading tests/test_forecast* tests/test_*forecast* config`: no output.
- `.venv/bin/python -m pytest tests/test_capacity_only_strategy_matrix_harness.py tests/test_research_parameter_catalog_projection.py tests/test_regime_research_autonomy.py::test_strategy_matrix_filters_ranking_files_before_replay tests/test_regime_research_autonomy.py::test_strategy_matrix_excludes_episode_tail_without_complete_holding_window tests/test_regime_research_autonomy.py::test_exact_match_replay_rejects_holding_window_crossing_episode tests/test_regime_research_autonomy.py::test_strategy_matrix_replay_args_preserve_regime_history -q`: 18 passed.
- `.venv/bin/python -m pytest tests/test_r13_forward_receipt_authority.py tests/test_ranking_provenance_receipt.py tests/test_storage_safety.py -q`: 110 passed, 31 subtests passed.
- `.venv/bin/python -m pytest tests/test_forecast_contracts.py tests/test_forecast_fixture.py -q`: 31 passed.
- `.venv/bin/python -m pytest tests/test_historical_ranking_replay_set_lineage.py tests/test_regime_research_boundaries.py -q`: 12 passed, 3 third-party deprecation warnings from `shap`.
- `.venv/bin/python -m py_compile scripts/run_capacity_only_strategy_matrix_harness.py scripts/run_backtest_strategy_matrix.py scripts/run_autonomous_research.py scripts/run_portfolio_replay.py scripts/run_backtest_replay.py app/research/r13_forward_receipt_authority.py`: exit 0.
- `.venv/bin/python -m app.research.r13_forward_receipt_authority --verify`: exit 0; status `REGISTERED_FORWARD_BUNDLE_VERIFIED`; four bundle files `MATCHED`; `errors=[]`; `downstream_authority=NONE`.
- Isolated temp capacity probe with `--max-scenarios 2`: exit 0; `scenario_count=2`; parity `PASS`; receipt boundary `CAPACITY_ONLY / NOT_RESEARCH_EVIDENCE`; manifest parity `PASS`; fixture cleanup `PASS`.

## Safe Next Step

Mainline can treat `db70dde285256af38c17129362b6cbd542d9a977` as the current non-production baseline for choosing the next frontier. The next frontier should not be BC-CP2/R14 waiting or accumulation. It should be a separately admitted non-BC-CP2 work item chosen from current backlog state.
