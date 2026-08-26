# TOP10 storage guard integration receipt 2026-08-27

## 範圍與 lineage

- Base: `f09b9b2453bb1fa0166f5a03461e7f971da8f7ea`
- Common ancestor: `cb9a6aedc348c494d984fa168d9c3fb7e089da80`
- Integrated complete storage chain: `ad7eea3dd2756875c8143f6caf2c71e6e41bb9be..281086c2dcb209e2793e255b7f17218832c0fb5c`
- Worktree: `/tmp/top10-storage-guard-integration-20260827`
- Branch: `codex/top10-storage-guard-integration-20260827`
- Method: selective file-level integration of the complete candidate storage chain, plus one current-main merge edit in `scripts/run_daily_research_quota.sh`.
- Scope proof: `git log --reverse cb9a6ae..281086c` enumerates the whole storage sequence from scheduled-growth bounds through first-write coalescing. This integration does **not** claim that only terminal commit `281086c` was applied.

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

### Daily quota conflict resolution

- Current-main-only logic retained: immutable time context validation, `RESEARCH_BATCH_ID`, batch intent publication, research-spine verification, ledger ingestion and verification, and the history compatibility projection.
- Storage-only change retained: `RUN_ARCHIVE_STEM="autonomous_research_daily_quota_${RUN_DATE}"`. Two cycles on the same trading day therefore overwrite the same JSON/Markdown archive pair instead of retaining timestamped duplicates.
- The static regression in `tests/test_storage_safety.py::StorageSafetyRegressionTest::test_research_quota_archive_respects_hard_file_limit_across_cycles` exercises two same-date cycles and asserts at most two archive files.

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

## Recovery 驗證（整合提交後）

以下檢查在整合提交 `943b23d8d8546dfaf5c7fad793a8949800789a9b` 上重新執行；不執行
FOG、live workload、reclaim、stop-loss、provider send 或任何 launchd control-plane 動作。

- Focused affected suite：
  `uv run pytest tests/test_storage_safety.py tests/test_fog_storage_validation.py tests/test_daily_research_batch_owner_shell.py tests/test_scheduler_ownership.py tests/test_daily_workflow_v2.py`
  → `80 passed in 17.33s`。
- Shell syntax：`bash -n scripts/run_with_storage_guard.sh scripts/run_daily_research_quota.sh` → PASS。
- Plist static parse：八個 storage job plist 與 `com.new-top10.webui.plist` 均為 `plutil -lint: OK`；僅解析，未載入、啟用或改動 launchd。
- Whitespace：`git diff --check HEAD^ HEAD` 與 `git diff --check` → PASS。
- Daily conflict proof：相對 `281086c` 的 daily quota diff 保留 71 行 current-main
  batch/ledger/history logic，另有 5 行 storage archive-stem 調整；前述 focused suite 與兩週期 archive regression 均通過。

### Full suite 與固定 base A/B

- 整合提交：`uv run pytest` → `7 failed, 977 passed, 4 warnings in 82.25s`。
- 為避免將 full-suite 紅燈歸咎於 storage chain，從固定 base
  `f09b9b2453bb1fa0166f5a03461e7f971da8f7ea` 建立暫時、唯讀比對 snapshot，重跑七個 failing node。
  結果為 `6 failed, 1 passed in 1.12s`；比對完成後 snapshot 已移除。
- 以下六項在 base 與整合提交均失敗，屬既有 research／evidence contract gap，而非本次 storage diff：
  - `tests/test_autonomous_research_topic_bank.py::AutonomousResearchTopicBankTests::test_main_routes_nine_actionable_queue_topics_when_active_bank_is_empty`
  - `tests/test_feature_promotion_decision.py::FeaturePromotionDecisionTests::test_complete_versioned_evidence_is_a_synthetic_go_only`
  - `tests/test_native_evidence_activation.py::test_execution_plan_is_strict_identity_and_safety_contract`
  - `tests/test_regime_research_autonomy.py::test_closed_manager_cli_writes_registration_split_and_append_only_trace`
  - `tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`
  - `tests/test_shadow_replay_coverage_plan.py::test_cli_accepts_exact_main_authority_root`
- 僅 `tests/test_isolated_shadow_plan_replay.py::test_authoritative_proposal_admission_passes`
  在 base 通過、整合提交失敗；失敗為 `PROPOSAL_VERIFICATION_FAILED`。此 test 對目前
  `HEAD` 的 proposal/blob authority 敏感，且不在 storage allowlist；本整合未修改其 source、proposal 或 evidence，故保留為非 storage blocker，不以越界修補掩蓋。

## 結論

Storage-focused acceptance 為 PASS：完整 chain 已整合、daily quota 的兩側邏輯均保留、受影響測試與靜態 gate 全綠。
Full suite 仍有上述七項非 storage 紅燈，因此本 receipt 不宣稱全套回歸 PASS，也不授權啟用任何排程；依容量安全規則，live activation 維持 `NO-GO`。
