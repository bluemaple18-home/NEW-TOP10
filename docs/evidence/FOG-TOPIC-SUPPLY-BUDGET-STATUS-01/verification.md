# FOG-TOPIC-SUPPLY-BUDGET-STATUS-01 Verification

## Scope

- Base SHA: `85ca3efb403519925d28afc8d94ed43f5111b2b3`
- Worktree: isolated detached worktree, clean before activation changes.
- Capability preflight:
  - `bash <ai-core>/scripts/worktree_capability_preflight.sh --check --root .`
    - `worktree_registered=true`
    - `python_tests=needs_prepare`
    - `codegraph=needs_prepare`
  - `bash <ai-core>/scripts/worktree_capability_preflight.sh --prepare --require-python-tests --with-codegraph --root .`
    - sandbox run: Python test prepare blocked by uv cache permission; CodeGraph indexed `85ca3efb403519925d28afc8d94ed43f5111b2b3`.
    - escalated rerun: `provisioning=ready`, `python_tests=ready`, `codegraph=ready`.
- CodeGraph:
  - `codegraph_status`: 732 files, 14853 nodes, 33998 edges.
  - `codegraph_context` and `codegraph_explore` run before source decision; relevant allowlist entry points were `replenish_development_topics`, daily quota verifier, and Fog worker terminal predicates.

## RED Regression Evidence

Production code was not changed before these RED checks.

1. Main downgraded budget-incomplete topic supply:
   - Command: `.venv/bin/python -m pytest tests/test_fog_continuous_topic_supply.py::test_main_preserves_attempt_budget_exceeded_topic_supply_status`
   - Result: failed.
   - Failure: expected `TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED`, actual `NO_EXECUTABLE_TOPIC`.

2. Quota verifier marked budget-incomplete as no-more-work:
   - Command: `.venv/bin/python -m pytest tests/test_daily_research_quota_verifier.py::DailyResearchQuotaVerifierTest::test_attempt_budget_exceeded_is_retryable_not_no_more_work`
   - Result: failed.
   - Failure: expected `PARTIAL_RETRYABLE_TOPIC_SUPPLY`, actual `PARTIAL_NO_MORE_WORK`.

3. Worker wiring lacked retryable budget-incomplete semantics:
   - Command: `bash tests/test_fog_runtime_time_wiring.sh`
   - Result: failed.
   - Failure: worker script lacked `TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED` / `PARTIAL_RETRYABLE_TOPIC_SUPPLY` observable wiring.

## GREEN Verification

- Targeted main regression:
  - Command: `.venv/bin/python -m pytest tests/test_fog_continuous_topic_supply.py::test_main_preserves_attempt_budget_exceeded_topic_supply_status tests/test_fog_continuous_topic_supply.py::test_main_reports_true_supply_exhaustion_and_exits_zero`
  - Result: `2 passed`.
- Targeted verifier regression:
  - Command: `.venv/bin/python -m pytest tests/test_daily_research_quota_verifier.py::DailyResearchQuotaVerifierTest::test_attempt_budget_exceeded_is_retryable_not_no_more_work tests/test_daily_research_quota_verifier.py::DailyResearchQuotaVerifierTest::test_topic_supply_exhausted_has_stable_research_value_status tests/test_daily_research_quota_verifier.py::DailyResearchQuotaVerifierTest::test_no_executable_topic_status_is_not_supply_exhausted`
  - Result: `3 passed`.
- Worker wiring:
  - Command: `bash tests/test_fog_runtime_time_wiring.sh`
  - Result: passed.
- Affected suites:
  - Command: `.venv/bin/python -m pytest tests/test_fog_continuous_topic_supply.py tests/test_daily_research_quota_verifier.py`
  - Result: `21 passed`.
- Shell syntax:
  - Command: `bash -n scripts/run_fog_research_worker.sh`
  - Result: passed.
  - Command: `bash -n tests/test_fog_runtime_time_wiring.sh`
  - Result: passed.
- Python compile:
  - Command: `.venv/bin/python -m py_compile scripts/run_autonomous_research.py scripts/verify_daily_research_quota.py tests/test_fog_continuous_topic_supply.py tests/test_daily_research_quota_verifier.py`
  - Result: passed.
- Diff hygiene:
  - Command: `git diff --check`
  - Result: passed.
- DBG audit:
  - Command: `rg -n "DBG|DEBUG|pdb|breakpoint\\(" scripts/run_autonomous_research.py scripts/verify_daily_research_quota.py scripts/run_fog_research_worker.sh tests/test_fog_continuous_topic_supply.py tests/test_daily_research_quota_verifier.py tests/test_fog_runtime_time_wiring.sh`
  - Result: no matches.

## Full Pytest

- Command: `.venv/bin/python -m pytest`
- Result: `1 failed, 618 passed, 4 warnings`.
- Failure: `tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`.
- Diagnostic: failure check was `evidence_exists`; missing historical artifacts/reference data under `artifacts/model_experiments/`, `artifacts/`, and `data/reference/`.
- Scope assessment: this is outside this card allowlist and not caused by the topic supply budget status change. No allowlist expansion was made.

## Behavior Mapping

- FR-BUDGET-01: main no-topic outcome now preserves `TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED` and full `topic_supply` receipt.
- FR-BUDGET-02: verifier maps budget-incomplete/no-runs to `PARTIAL_RETRYABLE_TOPIC_SUPPLY` with `research_value_status=TOPIC_SUPPLY_ATTEMPT_BUDGET_RETRYABLE`; exit remains 0 through `SUCCESS_STATES`.
- FR-BUDGET-03: worker treats retryable topic supply as continue, not terminal/no-more-work.
- SC-BUDGET-01: `TOPIC_SUPPLY_EXHAUSTED` and `NO_EXECUTABLE_TOPIC` targeted regressions remain terminal/no-more-work.
- SC-BUDGET-02: main -> verifier -> worker observable regression is covered by targeted tests and shell wiring.

## Independent Review

- Fixed candidate：`6af35c839f85040ba24648b226949dc31e584e6c`。
- Review receipt commit：`81a024cb8fda1e8c398041a32af2f0135047f0b2`。
- Verdict：`REVIEW_GO`。
- 未解 P0／P1：無。
- Reviewer另以CLI probe確認attempt-budget retryable、true exhaustion與一般
  no-executable三種狀態都維持exit 0。

## Mainline Acceptance

- Candidate整合commit：`5b543af`。
- Review receipt整合commit：`c5908ab`。
- Affected suites：`21 passed`。
- Mainline full suite：`619 passed, 4 warnings, 246 subtests passed`。
- Shell wiring／syntax、`py_compile`、`git diff --check`：PASS。

2026-07-31 16:26:02 +0800 的下一次自然排程：

- run id：`fog-research-2026-07-31-20260731082601931846`
- decision：`DEVELOPMENT_CANDIDATE`
- selected topics／topic runs：`1 / 1`
- verifier：`PARTIAL_NO_MORE_WORK`、failed count `0`、
  research value `HAS_FOLLOWUP_SIGNAL`
- `TOP10_FOG_MAP_HANDOFF_OK`
- representative replay drain：6 batches、144 completed、0 failed
- worker完成時間：16:43:37 +0800
- LaunchAgent：`LastExitStatus=0`

16:11前一輪的replay drain失敗已確認為磁碟空間耗盡，不是本卡routing或
queue regression。完成已結束worktree與暫存檔清理後，可用空間恢復；
未重啟LaunchAgent、未清circuit、未人工kickstart或執行live probe。
