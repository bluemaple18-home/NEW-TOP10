# TOP10 storage guard integration receipt 2026-08-27

## 範圍

- Base: `f09b9b2453bb1fa0166f5a03461e7f971da8f7ea`
- Integrated storage chain through candidate: `281086c2dcb209e2793e255b7f17218832c0fb5c`
- Worktree: `/tmp/top10-storage-guard-integration-20260827`
- Branch: `codex/top10-storage-guard-integration-20260827`
- Method: selective file-level integration from candidate storage chain, plus one current-main merge edit in `scripts/run_daily_research_quota.sh`.

## 邊界

- Did not push.
- Did not deploy.
- Did not run live workload, FOG cycle, reclaim, stop-loss, provider send, or external delivery.
- Did not load, unload, enable, disable, or mutate live launchd control plane.
- Repo plist files were parsed and statically checked only.

## 整合判斷

- Direct branch merge was rejected as too broad because `HEAD..281086c` included unrelated research-chain files.
- Integrated only storage guard chain paths:
  - `app/storage_safety.py`
  - `scripts/storage_safety.py`
  - `scripts/run_with_storage_guard.sh`
  - `scripts/storage_validation/fog_research_worker.py`
  - storage policy, storage operation docs, storage tasks, and storage evidence under `docs/`
  - storage/FOG validation tests
  - eight repo schedule plist wrapper changes
- Preserved current main changes in `scripts/run_daily_research_quota.sh`; only changed the run archive stem from timestamped per-run files to same-day fixed files.

## 驗證

- CodeGraph:
  - `/tmp/top10-storage-guard-integration-20260827` was not initialized.
  - Fallback CodeGraph query against `/Users/mattkuo/TOP10new` identified `tests/test_scheduler_ownership.py`, `tests/test_daily_workflow_v2.py`, and storage safety related tests as affected context.
- Required source/rule reads:
  - `AGENTS.md`
  - `/Users/mattkuo/ai-core/rules/24-storage-capacity-safety.md`
  - `git show f118617d698864280541788cf607f0205defba73:docs/tasks/2026-08-03_REVIEW-TOP10-STORAGE-GUARD-FIRST-WRITE-COALESCE-01.md`
- Environment:
  - `uv sync`: pass after sandbox escalation for existing uv cache access.
- Focused storage tests:
  - `uv run pytest tests/test_storage_safety.py tests/test_fog_storage_validation.py`
  - Result: `65 passed in 6.44s`
- Scheduler/daily workflow safe tests:
  - `uv run pytest tests/test_scheduler_ownership.py tests/test_daily_workflow_v2.py`
  - Result: `14 passed in 45.50s`
- Repo-only scheduler verifier:
  - `uv run python scripts/verify_scheduler_ownership.py --repo-only`
  - Result: `SCHEDULER_OWNERSHIP_GO`
- Plist parse:
  - `plutil -lint` for eight storage job plists plus `com.new-top10.webui.plist`
  - Result: all `OK`
- Shell syntax:
  - `bash -n scripts/run_with_storage_guard.sh`: pass
  - `bash -n scripts/run_daily_research_quota.sh`: pass
- Python compile:
  - `uv run python -m py_compile app/storage_safety.py scripts/storage_safety.py scripts/storage_validation/fog_research_worker.py`
  - Result: pass
- Static storage policy/plist assertion:
  - Jobs: 8
  - `launch_verified=false`: pass
  - wrapper prefix: pass
  - `RunAtLoad=false`: pass
  - no `KeepAlive`: pass
- Diff whitespace:
  - `git diff --check`: pass
  - `git diff --cached --check`: pass

## Full-suite note

Full suite was run once before final commit assembly:

- `uv run pytest`
- Result: `7 failed, 977 passed, 4 warnings in 95.62s`

Base A/B for the seven failed tests on clean `f09b9b2453bb1fa0166f5a03461e7f971da8f7ea`:

- `tests/test_autonomous_research_topic_bank.py::AutonomousResearchTopicBankTests::test_main_routes_nine_actionable_queue_topics_when_active_bank_is_empty`: fails on base
- `tests/test_feature_promotion_decision.py::FeaturePromotionDecisionTests::test_complete_versioned_evidence_is_a_synthetic_go_only`: fails on base
- `tests/test_native_evidence_activation.py::test_execution_plan_is_strict_identity_and_safety_contract`: fails on base
- `tests/test_regime_research_autonomy.py::test_closed_manager_cli_writes_registration_split_and_append_only_trace`: fails on base
- `tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`: fails on base
- `tests/test_shadow_replay_coverage_plan.py::test_cli_accepts_exact_main_authority_root`: fails on base
- `tests/test_isolated_shadow_plan_replay.py::test_authoritative_proposal_admission_passes`: passed on base; this test is HEAD/blob authority-sensitive and failed only during dirty pre-commit full-suite state.

Conclusion: storage-focused acceptance is green. Six full-suite failures are pre-existing on base. The one extra dirty-state failure should be rechecked after the integration commit if mainline requires a post-commit full-suite receipt.
