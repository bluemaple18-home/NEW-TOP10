# FOG-CONTINUOUS-TOPIC-SUPPLY-01 Repair-1 Evidence

## Identity

- role: Repairer
- repair base SHA: `8f2c0c3a6ad19777103932029a85ef6a750fc6f0`
- repair candidate SHA: `SELF`（由包含本檔的單一 repair commit 解析）
- activation token: `act-v1:fb1489af738bbc04faafd06e6d5deedf703473299ec2ab51d21874b7cc13fd01`
- exit: `READY_FOR_REREVIEW`
- live worker / LaunchAgent / retry circuit / promotion / cleanup touched: no

## Worktree Capability Preflight

```text
bash /Users/mattkuo/ai-core/scripts/worktree_capability_preflight.sh --check --root <repo-root>

worktree_registered=true
provisioning=ready
python_tests=needs_prepare
codegraph=needs_prepare
code_context=not_ready
```

Graph and Python test runtime were prepared as git-ignored local state only:

```text
python_tests=ready
codegraph=ready
codegraph_indexed_sha=8f2c0c3a6ad19777103932029a85ef6a750fc6f0
```

CodeGraph context was queried for:

- `select_topics_for_run`
- `replenish_development_topics`
- `verify_daily_research_quota`
- `TOPIC_SUPPLY_EXHAUSTED`

## RED Receipts

### FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P1-001

```text
.venv/bin/python -m pytest -q tests/test_autonomous_research_topic_bank.py -k 'non_execute_default_preview'

2 failed
- actionable queue overrode non-execute --topic-index preview:
  expected topic:indexed-second, got topic:queue-first
- manager rejected / cooldown removed diagnostic preview:
  expected rejected/cooldown topic, got []
```

### FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P2-002

```text
.venv/bin/python -m pytest -q tests/test_fog_continuous_topic_supply.py -k 'multi_template_no_exact_date'

1 failed
- receipt had no attempt_budget / ranking_eligibility_cache fields
```

### FOG-CONTINUOUS-TOPIC-SUPPLY-REVIEW-P2-003

```text
.venv/bin/python -m pytest -q tests/test_daily_research_quota_verifier.py -k 'topic_supply_exhausted or no_executable_topic_status'

2 failed
- TOPIC_SUPPLY_EXHAUSTED produced LOW_INFORMATION
- default NO_EXECUTABLE_TOPIC produced LOW_INFORMATION
```

## Fix Summary

- `P1-001`: `select_topics_for_run` now preserves legacy non-execute/default/single-topic preview before queue arbitration and manager gates. `main` already passes active-bank topics as `fallback_topics`, so preview keeps active-bank source semantics while execute/default and explicit queue paths keep queue-first/fallback/dedupe.
- `P2-002`: `replenish_development_topics` now caches ranking eligibility by `(candidate_dir, baseline_dir, horizon, as_of_date)` and emits `attempt_budget`, cache hits/misses, and budget exhaustion in receipts. If the budget stops complete unique inventory search, the outcome is `TOPIC_SUPPLY_ATTEMPT_BUDGET_EXCEEDED`, not `TOPIC_SUPPLY_EXHAUSTED`.
- `P2-003`: quota verifier maps `TOPIC_SUPPLY_EXHAUSTED` to stable `SUPPLY_EXHAUSTED` and maps `NO_EXECUTABLE_TOPIC` to `NO_MORE_EXECUTABLE_TOPIC` without depending on `from_queue=true`.

## GREEN Receipts

```text
.venv/bin/python -m pytest -q tests/test_autonomous_research_topic_bank.py -k 'non_execute_default_preview or queue_first_falls_back'

3 passed, 18 deselected
```

```text
.venv/bin/python -m pytest -q tests/test_fog_continuous_topic_supply.py -k 'multi_template_no_exact_date or supply_reports_exhaustion'

2 passed, 4 deselected
```

```text
.venv/bin/python -m pytest -q tests/test_daily_research_quota_verifier.py -k 'zero_topics or topic_supply_exhausted or no_executable_topic_status'

3 passed, 10 deselected
```

```text
.venv/bin/python -m pytest -q \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_fog_continuous_topic_supply.py \
  tests/test_daily_research_quota_verifier.py

40 passed
```

```text
.venv/bin/python -m pytest -q \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_regime_research_autonomy.py \
  tests/test_fog_continuous_topic_supply.py \
  tests/test_daily_research_quota_verifier.py

105 passed
```

## Shell, Compile, and Runtime Wiring

```text
bash -n scripts/run_fog_research_worker.sh
bash -n scripts/run_daily_research_quota.sh
bash -n tests/test_fog_runtime_time_wiring.sh
.venv/bin/python -m py_compile \
  scripts/run_autonomous_research.py \
  scripts/verify_daily_research_quota.py \
  tests/test_autonomous_research_topic_bank.py \
  tests/test_fog_continuous_topic_supply.py \
  tests/test_daily_research_quota_verifier.py
bash tests/test_fog_runtime_time_wiring.sh

PASS
```

## Full Suite

```text
.venv/bin/python -m pytest -q

1 failed, 616 passed, 4 warnings, 246 subtests passed in 70.10s
```

Only failure:

```text
tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger
```

Independent failed-check dump:

```text
status=FAILED
failed_checks=[evidence_exists]
```

Missing untracked artifacts include:

- `artifacts/model_experiments/long_candidate_validation_report_2026-06-10.json`
- `artifacts/model_experiments/candidate_trail10_retention_diagnostics_2026-06-10.json`
- `artifacts/model_experiments/overlap_first_recommendation_performance_recent_100_2026-06-10.json`
- `data/clean/features.parquet`
- `data/reference/stock_industry_map.csv`
- `data/reference/stock_concept_membership.csv`
- `artifacts/market_context_2026-06-09.json`

Disposition: same missing-artifact environment failure reported by the independent review. This repair did not modify ledger builder/verifier/tests or artifact paths, and the Repair-1 allowlist does not permit fabricating these assets.

## Gates

```text
git diff --check

PASS
```

```text
rg -n '\[DBG-' scripts/run_autonomous_research.py scripts/verify_daily_research_quota.py \
  tests/test_autonomous_research_topic_bank.py tests/test_fog_continuous_topic_supply.py \
  tests/test_daily_research_quota_verifier.py

no matches
```

Final changed-file allowlist audit:

```text
docs/tasks/2026-07-31_FOG-CONTINUOUS-TOPIC-SUPPLY-01_REPAIR-1.md
docs/evidence/FOG-CONTINUOUS-TOPIC-SUPPLY-01/repair_1.md
scripts/run_autonomous_research.py
scripts/verify_daily_research_quota.py
tests/test_autonomous_research_topic_bank.py
tests/test_daily_research_quota_verifier.py
tests/test_fog_continuous_topic_supply.py
```

All are in the Repair-1 exact changed-file allowlist.

## Remaining Risks

- Full suite is not green in this worktree because historical research component evidence artifacts are absent.
- No live autonomous research worker, LaunchAgent, retry circuit, production promotion, closed registry, sealed artifacts, or cleanup actions were performed.
