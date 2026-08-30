# A0 Lane A：reader/writer and terminal boundary inventory

- `as_of`: 2026-08-30
- `execution_base`: `origin/main@4c6d41a44314beb3592ccdf7a9b43d8fe614ad88`
- `scope`: repository committed evidence only；未讀寫 `.work/current`；未做 scheduler/publish/production/runtime mutation。
- `codegraph_status`: `CodeGraph not initialized in <repo-root>`，已改用限域 `rg`/`sed`/`nl` 查證。
- `inventory_method`: limited committed-text search: `rg -l "run_history\\.jsonl?|RUN_HISTORY_JSONL|RUN_HISTORY_JSON" app scripts tests docs config --glob '!.work/current/**'` plus focused reads of Research Spine implementation files.
- `hash_method`: `git hash-object <repo-root>/<path>`

## Structured claims

| claim_id | subject | claim | authority | scope | as_of | evidence_ref | evidence_hash | status | owner | next_action |
|---|---|---|---|---|---|---|---|---|---|---|
| A0-BND-001 | Native lifecycle writer boundary | `app/research/run_receipts.py` is a native lifecycle adapter that writes TrialSpec/Intent/Attempt/Receipt evidence and explicitly avoids train/model/production promotion. | Native implementation | Research receipt writer | 2026-08-30 | `app/research/run_receipts.py:1,29-33,115-248,332-642` | `4156a42507c12090b7d368b83b435bd2cee0fc26` | CONFIRMED | Research Spine owner | Keep receipt writer isolated from model training and production ranking. |
| A0-BND-002 | Terminal states | Canonical terminal statuses include `SUCCEEDED`, `FAILED`, `REJECTED_BEFORE_EXECUTION`, `CANCELLED`; receipt validation requires exact terminal semantics. | Contracts | Terminal state boundary | 2026-08-30 | `app/research/contracts.py:14-24,399-660`; `tests/test_research_spine_contracts.py:246-370` | `7deddc03d80e12d8a57e29fc9e991121061c4aa6`; `18fb8c04cd58488d5e3180f6c5d17eb69f4aa8d5` | CONFIRMED | Research Spine owner | Preserve these terminal states in future adapters and tests. |
| A0-BND-003 | Fail-closed terminal behavior | A claimed success without executed units / observed facts is downgraded or invalidated; orphan reconciliation is sealed `UNKNOWN` and does not guess execution. | Contracts + adapter + tests | Terminal fail-closed boundary | 2026-08-30 | `app/research/contracts.py:337-361,399-660`; `app/research/run_receipts.py:48-87,332-642`; `tests/test_research_spine_contracts.py:232-243,246-370`; `tests/test_research_spine_daily_cutover.py:82-87` | `7deddc03d80e12d8a57e29fc9e991121061c4aa6`; `4156a42507c12090b7d368b83b435bd2cee0fc26`; `18fb8c04cd58488d5e3180f6c5d17eb69f4aa8d5`; `1a9b82da9bd2be2fc4c50f019981d9244f6ab21d` | CONFIRMED | Research Spine owner | Any missing terminal receipt should fail verification, not infer success. |
| A0-BND-004 | Immutable corpus to rebuildable ledger | `observation_ingest` reads immutable corpus/CAS/migration manifests and writes a rebuildable DuckDB ledger/projections; ledger snapshot/hash is derived from source evidence. | Ingestion implementation | Evidence reader / ledger writer | 2026-08-30 | `app/research/observation_ingest.py:1,32-38,41-220,363-385,388-517,518-692,737-959,962-970` | `86d88898425dcc42e173a4e3774143c2c44f6adb` | CONFIRMED | Research Spine owner | Treat DuckDB deletion/rebuild as supported recovery path. |
| A0-BND-005 | Eligibility projection boundary | Eligibility reads ledger facts and writes a projection; legacy adaptive eligibility is disabled and migrated legacy evidence gets weight zero. | Eligibility policy + implementation | Projection reader/writer | 2026-08-30 | `app/research/eligibility.py:1,20-25,49-76,120-228,235-332`; `config/research_eligibility_policy_v1.json:1` | `6e9c9b81c68b3e5430b815e7223ca399bae01f5b`; `d6f4d79fb1eefe2bbd642091df8ccc5cfe9d41b5` | CONFIRMED | Research Spine owner | Do not use eligibility projection as raw evidence source. |
| A0-BND-006 | Legacy migration boundary | `legacy_migration` discovers legacy `run_history` and strategy matrix sources, maps/classifies them, publishes sources/mappings to CAS, and marks conflicts fail-closed/no-winner. | Migration implementation | Legacy reader / manifest writer | 2026-08-30 | `app/research/legacy_migration.py:37-170,183-260`; `docs/evidence/CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1/before_after.md:12-16,26-35` | `147e812dea4874e6acc9425d15cb083c3ed275f9`; `8b2252dffdba6611a836da9edb047990c58e4865` | CONFIRMED | Research Spine owner | Keep legacy rows quarantined unless mapped to native receipt evidence. |
| A0-BND-007 | Compatibility projection boundary | `history_compatibility_projection` rebuilds `artifacts/autonomous_research/run_history.jsonl` and a manifest from ledger/native observations plus frozen legacy rows; this is compatibility output, not canonical evidence. | Projection implementation | Compatibility writer | 2026-08-30 | `app/research/history_compatibility_projection.py:1,21-24,60-191`; `tests/test_research_spine_daily_cutover.py:89-121` | `7a091a6f8885afd04abe09253ec6bb41bf1aaa69`; `1a9b82da9bd2be2fc4c50f019981d9244f6ab21d` | CONFIRMED | Research Spine owner | Consumers may read compatibility output, but must not claim it as canonical execution evidence. |
| A0-BND-008 | Daily quota cutover boundary | Daily quota script ingests Research Spine receipts, verifies the ledger batch, optionally refreshes compatibility `run_history.jsonl`, and keeps daily runner owner/selection/quota outside A0 mutation scope. | Daily runner script + Card A evidence | Scheduler-facing adapter | 2026-08-30 | `scripts/run_daily_research_quota.sh:150-240`; `docs/evidence/CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1/before_after.md:20-22` | `1912db3576851e038510b12b8a4f3a8b7064de34`; `8b2252dffdba6611a836da9edb047990c58e4865` | CONFIRMED | Scheduler/research owner | A0 must not change runner ownership, scheduling, or quota selection. |
| A0-BND-009 | Fog/map reader boundary | Fog map and related scripts read progress/registry/queue and legacy/compatibility history artifacts; they are downstream readers unless explicitly proven to write source evidence. | Focused implementation reads + limited `rg` | Downstream reader inventory | 2026-08-30 | `scripts/build_research_fog_map.py:141-180`; `config/fog_runtime_data_authority_v1.json:7`; limited `rg -l` result | `457d260f663cc1fa39ade1e767bb2317404bf100`; `ff32dfba72fdbccaed8ce196edb0f64e0b1132e1`; `N/A: command evidence` | CONFIRMED | Fog/map owner | Keep Fog UI/runtime authority separate from Research Ledger evidence authority. |
| A0-BND-010 | Reader/writer inventory exhaustiveness | The detailed inventory below is committed-text complete for sorted `combo_id` and `run_history` query universes at base SHA, but it is not proof of runtime writes, generated files, or untracked behavior. | Limited repo text search | Inventory limitation | 2026-08-30 | `rg -l "combo_id" app scripts tests docs config --glob '!.work/current/**' then sort`; `rg -l "run_history json/jsonl OR RUN_HISTORY_JSONL OR RUN_HISTORY_JSON" app scripts tests docs config --glob '!.work/current/**' then sort` | `sha256:11480fd9dc6730d03d0e261e32b9609bde98cf1d2435e53b35223c47b97975e4`; `sha256:188ff687e875bc08d7ae00b027d4c171f4dcb819c43dde1f1b142cc18b80241c` | UNKNOWN | Integrator | For runtime-write claims, collect runtime logs or control-plane evidence in a separate admitted lane. |

## Known committed `run_history` readers/writers from limited search

| Category | Files | Boundary note |
|---|---|---|
| Native Research Spine writer/projection | `app/research/history_compatibility_projection.py`; `scripts/run_daily_research_quota.sh`; `tests/test_research_spine_daily_cutover.py` | Writes/rebuilds compatibility history from ledger evidence; not canonical raw evidence. |
| Legacy migration / compatibility mapping | `app/research/legacy_migration.py`; `app/research/map_contract.py`; `tests/test_research_legacy_migration.py`; `tests/test_research_map_contract_boundary.py` | Reads legacy history and maps/deweights it; `combo_id` remains compatibility identity. |
| Fog/map downstream readers | `scripts/build_research_fog_map.py`; `app/research/fog_map_domain.py`; `app/research/fog_map_render.py`; `scripts/verify_research_fog_map.py`; `scripts/verify_research_map_v2_schema.py`; `scripts/research_map_linkage_smoke.py`; `config/fog_runtime_data_authority_v1.json`; `scripts/run_top10_fog_map_handoff.py` | Downstream visualization/runtime handoff readers; no A0 authority to mutate. |
| Research manager / autonomous runner | `scripts/run_autonomous_research.py`; `scripts/verify_autonomous_research.py`; `tests/test_top10_agent_status.py`; `app/research/batch_owner.py`; `tests/test_research_batch_owner.py` | Manager state includes `run_history.json` and queue/summary artifacts; A0 only records boundary. |
| Replay / backfill producers and consumers | `scripts/run_weekend_representative_replay.py`; `scripts/run_representative_replay_drain_worker.py`; `scripts/run_weekend_survivor_deep_replay.py`; `scripts/run_liquidity_replay_v2_batch.py`; `scripts/build_liquidity_replay_v2_stage2.py`; `scripts/verify_liquidity_replay_v2_batch.py`; `scripts/backfill_research_map_run_history.py`; `scripts/verify_research_map_run_history_backfill.py`; `scripts/refresh_research_map_from_history.sh` | Legacy/backfill/replay surface; not promoted to canonical evidence without receipt/migration proof. |
| Campaign / inventory / review readers | `scripts/build_research_campaign_progress.py`; `scripts/build_weekend_universe_inventory.py`; `scripts/weekend_training_common.py`; `scripts/build_5913_combo_effectiveness_review.py`; `tests/test_research_knowledge_artifacts.py` | Analytical consumers of history/progress state. |
| Historical docs/evidence containing references | `docs/architecture/top10_harness_team.dashboard.json`; `docs/architecture/AUTONOMOUS_RESEARCH_MANAGER.md`; `docs/tasks/2026-06-10_REVIEW-AUTONOMOUS-RESEARCH-MANAGER.md`; `docs/tasks/2026-06-11_RESEARCH-MAP-01_gamified_fog_of_war_dashboard.md`; `docs/tasks/2026-06-12_LIQUIDITY-REPLAY-01_quality_universe_strict_replay.md`; `docs/tasks/2026-06-12_LIQUIDITY-REPLAY-02_v2_component_batch.md`; `docs/tasks/2026-06-12_LIQUIDITY-REPLAY-03_stage2_risk_capped_candidates.md`; `docs/tasks/2026-06-12_RESEARCH-MAP-V2-02_architecture_handoff.md`; `docs/tasks/2026-06-12_RESEARCH-RESULT-REVIEW-01_5913_combo_effectiveness_review.md`; `docs/tasks/2026-06-13_WEEKEND-TRAINING-00_full_universe_burn_down_plan.md`; `docs/tasks/2026-06-13_WEEKEND-TRAINING-01_universe_inventory_equivalence.md`; `docs/tasks/2026-06-13_WEEKEND-TRAINING-03_representative_replay_runner.md`; `docs/tasks/2026-06-17_WEEKEND-TRAINING-OVERNIGHT-01_full_night_unlock_and_replay_campaign.md`; `docs/tasks/2026-08-02_FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01.md`; `docs/tasks/2026-08-14_CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1.md`; `docs/evidence/CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1/before_after.md`; `docs/evidence/CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1/batch_intent.json`; `docs/evidence/TOP10-STORAGE-RUNAWAY-01/inventory-and-budget.md` | Historical/context evidence only unless a current card promotes it. |

## F1：committed `combo_id` producer/consumer universe

- Universe query: `rg -l "combo_id" app scripts tests docs config --glob '!.work/current/**' | sort`
- Universe hash: `sha256:11480fd9dc6730d03d0e261e32b9609bde98cf1d2435e53b35223c47b97975e4`
- Row count: 51 files.
- Classification rule: `PRODUCER` writes/builds `combo_id` rows; `CONSUMER` reads/validates/renders them; `BOTH` does both; `REFERENCE_ONLY` is docs/tests/evidence/config reference, not runtime code.

| path | class | symbol/entry | exact lines | blob_hash |
|---|---|---|---|---|
| `tests/test_weekend_universe_inventory_snapshot.py` | REFERENCE_ONLY | fixture/doc reference | 22,24,30,31,107,126,135,137,138,139,140,149,165 | `e71a491e9af2ddeba6ad726033a347d236c6b06c` |
| `tests/test_research_spine_daily_cutover.py` | REFERENCE_ONLY | fixture/doc reference | 94,127,131 | `1a9b82da9bd2be2fc4c50f019981d9244f6ab21d` |
| `tests/test_representative_replay_lifecycle.py` | REFERENCE_ONLY | fixture/doc reference | 25,43,46,60,65,75,88,94,104,106,107,121,124,128,145,159,172,182,191,193,194 | `1b6602c32af2538d0d57c7dc35e38a74464d97f7` |
| `docs/tasks/2026-06-13_WEEKEND-TRAINING-03_representative_replay_runner.md` | REFERENCE_ONLY | fixture/doc reference | 78 | `eb204ecb495a61147c3f0820c359f85264c56bda` |
| `tests/test_research_fog_map_refactor.py` | REFERENCE_ONLY | fixture/doc reference | 130 | `c3ef326d5bf98b7a3d10733070af350c071d0dc6` |
| `tests/test_research_fog_map_burn_down.py` | REFERENCE_ONLY | fixture/doc reference | 165 | `6d7411a8df0598d58e065c86c498f4bdec322d7c` |
| `tests/test_weekend_readiness_audit.py` | REFERENCE_ONLY | fixture/doc reference | 112 | `0f72cb266f04145f7070efcf6c1db85db5d01b0a` |
| `tests/test_summary_only_frontier_queue.py` | REFERENCE_ONLY | fixture/doc reference | 17,19,20,21,25,26,56 | `8efd4816e7d3b73b6780447d57a419f7baf67a2a` |
| `tests/test_research_map_contract_boundary.py` | REFERENCE_ONLY | fixture/doc reference | 23,33,34,45,46,52,58,66,106,122,123 | `2e324b87e842383d3e6e0b7137322e49f899ae52` |
| `tests/test_representative_replay_drain_worker.py` | REFERENCE_ONLY | fixture/doc reference | 51,52,67,74,75,115,197,201,257,258 | `80d519e827e6b81a5deadee8627425001233d048` |
| `tests/test_research_parameter_catalog_projection.py` | REFERENCE_ONLY | fixture/doc reference | 42,45 | `75ccd5b62401d51cc0b8fae6cb59af060a91b915` |
| `tests/test_regime_research_autonomy.py` | REFERENCE_ONLY | fixture/doc reference | 514,515 | `7298373cca38d64f4ed2d7e8ffabfd5380e7f664` |
| `scripts/build_weekend_frontier_queue.py` | BOTH | script entry/helper | 54,60,68,93,108,127,128,148,178,180 | `cd8c00bd7482797c8a6d787be995d0b58fbef803` |
| `scripts/build_research_campaign_progress.py` | CONSUMER | script entry/helper | 222,233,243,254,286,291 | `c4a3fb185c6d6361bce339ae0408f744a5764305` |
| `scripts/run_autonomous_research.py` | CONSUMER | script entry/helper | 1446,1448,1450 | `b8c7955277c066944dfc43cd74fd80f79da04b50` |
| `scripts/verify_liquidity_replay_v2_batch.py` | CONSUMER | script entry/helper | 100,106,107,109,111,112 | `6e012a0f00d77fe5b006dec802017058e3a3b6f9` |
| `scripts/build_liquidity_replay_v2_stage2.py` | BOTH | script entry/helper | 131,262,292,295 | `f8ffe1c8ce44095e451afe4c48cbfcf55d3ff988` |
| `scripts/run_weekend_representative_replay.py` | BOTH | script entry/helper | 94,120,136,143 | `4c0b05a93953787de4d684c93213fa07297ec2a4` |
| `scripts/verify_regime_research_autonomy.py` | REFERENCE_ONLY | script entry/helper | 354,355 | `7d64d92c5b9572b6f92494f9ba181fef2438eaab` |
| `docs/tasks/2026-07-06_WEEKEND-TRAINING-22_summary_only_trace_archive.md` | REFERENCE_ONLY | fixture/doc reference | 46 | `3a34a12f6cbbae38c1e43e9137b1951abf6a2e33` |
| `scripts/build_5913_combo_effectiveness_review.py` | CONSUMER | script entry/helper | 192,268,313,349,408,415,423,434,446 | `f18dfad4ee7bc6f93f883932b9a5a9d9dd3adcf8` |
| `scripts/build_weekend_readiness_audit.py` | CONSUMER | script entry/helper | 645 | `20d0572938792fba97f4a26b34c91eabfa50ffc5` |
| `docs/tasks/2026-06-12_LIQUIDITY-REPLAY-02_v2_component_batch.md` | REFERENCE_ONLY | fixture/doc reference | 134 | `0edbd2f966ffb12f8b51633ba51bfaade4a627a9` |
| `scripts/verify_weekend_frontier_queue.py` | CONSUMER | script entry/helper | 58,60,62,63 | `acf47cc771ffee9b20f891818f1864aa8b4ddb6e` |
| `scripts/run_liquidity_replay_v2_batch.py` | BOTH | script entry/helper | 117,118,119,305,323,352,367,372,373 | `b754a721f23aa35fb531f702a5e464dd9e7cca5b` |
| `scripts/verify_research_fog_map.py` | CONSUMER | script entry/helper | 359,362,363,369 | `6b074aa92b0a3e0470910c56d7d7325aee2e2a73` |
| `scripts/backfill_research_map_run_history.py` | BOTH | script entry/helper | 198,249,302,339,346 | `1a5a59fdde81b29f6cb3288fdc9973989e61b1db` |
| `scripts/verify_weekend_survivor_deep_replay.py` | CONSUMER | script entry/helper | 48,53 | `77d1817149fd2a2c098cdbab2094879e40ad0fa6` |
| `scripts/research_map_linkage_smoke.py` | CONSUMER | script entry/helper | 84,99 | `ffb0fd3cd3e85631d6d970dc8460f3cce70a417d` |
| `scripts/run_weekend_survivor_deep_replay.py` | BOTH | script entry/helper | 68,109,172 | `b57fb0d9a53c2ec9cf2030106f455d7c155b8bd4` |
| `scripts/build_weekend_universe_inventory.py` | BOTH | script entry/helper | 14,34,76,81,82,87,99,107,129,132,133,136,143,145 | `80eadf902b5e81182b117435b38b78efb6e403a4` |
| `docs/tasks/2026-08-02_FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01_repair-02.md` | REFERENCE_ONLY | fixture/doc reference | 33 | `8954792c5773f24127648b09d6715c5c99b82870` |
| `scripts/verify_weekend_representative_replay.py` | CONSUMER | script entry/helper | 43,45,47,57 | `0830c112f4a35f7a5bac25f448be598ee8823ba8` |
| `scripts/verify_weekend_universe_inventory.py` | CONSUMER | script entry/helper | 58,60,63,69,94 | `3c061a48da10cdf9f8183aa556bd62ab9b7e8e0b` |
| `scripts/trace_weekend_training_artifact.py` | CONSUMER | script entry/helper | 151,152,154,161,176,195,199 | `1bd60c6ef9da8f1563473ffd14a22f060f0aa584` |
| `scripts/weekend_training_common.py` | BOTH | script entry/helper | 32,306,309,352,358,372 | `c916f2df17745c32d0b2b8dd7b8eb2232577c49b` |
| `scripts/verify_research_map_run_history_backfill.py` | CONSUMER | script entry/helper | 4,60,65,66,68,74,83 | `1e125a25f8db87377142b35118bd3f7a0d320c39` |
| `scripts/build_weekend_training_rollup.py` | CONSUMER | script entry/helper | 213,224,335 | `3a067e28fe5aaf87b9b1841b4697455719736bc4` |
| `scripts/run_representative_replay_drain_worker.py` | BOTH | script entry/helper | 145,147,151,158,249,250,259,260,269 | `3b4322a7d2b96707648e6febece73762a93a1f31` |
| `scripts/build_research_fog_map.py` | CONSUMER | script entry/helper | 63 | `457d260f663cc1fa39ade1e767bb2317404bf100` |
| `app/research/history_compatibility_projection.py` | BOTH | build_native_rows/latest_completed_by_combo | 17,125,148 | `7a091a6f8885afd04abe09253ec6bb41bf1aaa69` |
| `app/research/map_contract.py` | BOTH | combo_id/v2_combo_id/canonicalize/apply_run_history | 33,48,98,135,193,211,212,214,221,223,233,234,246,249,272,273,281,284,285,286,287,288,299,320,339,354,404,411,412 | `133e7017df2d4cb63c3c0605caf34ca7584608df` |
| `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-I5/circuit_recovery_verification.json` | REFERENCE_ONLY | fixture/doc reference | 65 | `83344891b50a809ae5e55a4caeff71c6b84f8c79` |
| `app/research/legacy_migration.py` | BOTH | map_record migration payload | 157 | `147e812dea4874e6acc9425d15cb083c3ed275f9` |
| `app/research/fog_map_domain.py` | CONSUMER | app reader/render helper | 25,530,578,590,655,664 | `b54fa88311c9aa8b080a898cfce01b1173f4c3c0` |
| `docs/evidence/FOG-RUNTIME-TIME-AUTHORITY-01-I5/bounded_dry_inventory_verification.json` | REFERENCE_ONLY | fixture/doc reference | 65 | `48724b03e04d3697d174a913b159cfec662fccba` |
| `docs/tasks/2026-08-14_CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1.md` | REFERENCE_ONLY | fixture/doc reference | 116,126,550,567,596 | `d06db1477a11d53a707a0ba1de56eab74c2a2b54` |
| `app/research/fog_map_render.py` | CONSUMER | app reader/render helper | 2027,2067,2107 | `5ece90778761220735f6f86901926def5c26424c` |
| `docs/tasks/2026-06-12_RESEARCH-MAP-V2-02_architecture_handoff.md` | REFERENCE_ONLY | fixture/doc reference | 76 | `3907b8d94c65b89d846680f9e5ce705b755eb725` |
| `docs/tasks/2026-06-12_RESEARCH-MAP-V2-01_worldview_schema_upgrade.md` | REFERENCE_ONLY | fixture/doc reference | 171,222 | `24bba5831b15f608524189a5cdfd292d7e281093` |
| `docs/tasks/2026-06-13_WEEKEND-TRAINING-01_universe_inventory_equivalence.md` | REFERENCE_ONLY | fixture/doc reference | 30 | `75a8743a6d13ff5e00c4e98c76ddb4149cb6df25` |

## F3：committed `run_history` reader/writer universe

- Universe query: `rg -l "run_history\\.jsonl?|RUN_HISTORY_JSONL|RUN_HISTORY_JSON" app scripts tests docs config --glob '!.work/current/**' | sort`
- Universe hash: `sha256:188ff687e875bc08d7ae00b027d4c171f4dcb819c43dde1f1b142cc18b80241c`
- Row count: 51 files.
- Classification rule: `READ` reads or verifies `run_history`; `WRITE` creates/appends/rebuilds it; `BOTH` does both; `REFERENCE_ONLY` is docs/tests/evidence/config reference, not runtime code.

| path | class | target | exact lines | blob_hash |
|---|---|---|---|---|
| `docs/architecture/AUTONOMOUS_RESEARCH_MANAGER.md` | REFERENCE_ONLY | json | 104,111 | `54877a0b7b547ba217922195346b827a44627299` |
| `tests/test_research_spine_daily_cutover.py` | REFERENCE_ONLY | json+jsonl | 92,106 | `1a9b82da9bd2be2fc4c50f019981d9244f6ab21d` |
| `config/fog_runtime_data_authority_v1.json` | REFERENCE_ONLY | json+jsonl | 7 | `ff32dfba72fdbccaed8ce196edb0f64e0b1132e1` |
| `docs/architecture/top10_harness_team.dashboard.json` | REFERENCE_ONLY | json+jsonl | 271,374 | `a9d36a4f4affaaac0dbf584f5fba1074dceda788` |
| `scripts/run_top10_fog_map_handoff.py` | READ | json+jsonl | 86,224 | `cd07010adb8c824982142746df78c125762c97f8` |
| `scripts/verify_research_map_v2_schema.py` | READ | json+jsonl | 104 | `dfa63c8542d8dbbadae2ee30c01d81662c374319` |
| `tests/test_research_batch_owner.py` | REFERENCE_ONLY | json | 82,393 | `5abe699c9b95ef51e68118bc9eb93e8220107d7f` |
| `scripts/refresh_research_map_from_history.sh` | READ | json+jsonl | 2 | `ad2949fe097fc6eef7352fd18133ff933de1ab9a` |
| `tests/test_research_legacy_migration.py` | REFERENCE_ONLY | json+jsonl | 41,52,114,118 | `52ce94fe4434dfa9fe58eecf5ce26ff9941b78f3` |
| `docs/evidence/CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1/batch_intent.json` | REFERENCE_ONLY | json | 1 | `541ce97b5b8eadc7e465da724e7d0d09763dc16a` |
| `docs/evidence/TOP10-STORAGE-RUNAWAY-01/inventory-and-budget.md` | REFERENCE_ONLY | json+jsonl | 14 | `c328edfcafdb6f7444a7d7653e23175398b19c6f` |
| `scripts/run_autonomous_research.py` | BOTH | json | 3025 | `b8c7955277c066944dfc43cd74fd80f79da04b50` |
| `tests/test_top10_agent_status.py` | REFERENCE_ONLY | json+jsonl | 111 | `c1f0d9578bd8d91001161ccd073eae215f752e6a` |
| `scripts/verify_autonomous_research.py` | READ | json | 205 | `e6f2df912f1646eeef2b78ea1998ed6055a7f164` |
| `tests/test_research_knowledge_artifacts.py` | REFERENCE_ONLY | json+jsonl | 70,72 | `9cdba15f652955de098d641cb70072ca1f58f869` |
| `tests/test_research_map_contract_boundary.py` | REFERENCE_ONLY | json+jsonl | 74 | `2e324b87e842383d3e6e0b7137322e49f899ae52` |
| `docs/evidence/CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1/before_after.md` | REFERENCE_ONLY | json | 5 | `8b2252dffdba6611a836da9edb047990c58e4865` |
| `scripts/verify_research_fog_map.py` | READ | json+jsonl | 148 | `6b074aa92b0a3e0470910c56d7d7325aee2e2a73` |
| `scripts/verify_liquidity_replay_v2_batch.py` | READ | json+jsonl | 15 | `6e012a0f00d77fe5b006dec802017058e3a3b6f9` |
| `scripts/run_daily_research_quota.sh` | WRITE | json+jsonl | 219 | `1912db3576851e038510b12b8a4f3a8b7064de34` |
| `scripts/build_liquidity_replay_v2_stage2.py` | BOTH | json+jsonl | 19 | `f8ffe1c8ce44095e451afe4c48cbfcf55d3ff988` |
| `scripts/weekend_training_common.py` | READ | json+jsonl | 41 | `c916f2df17745c32d0b2b8dd7b8eb2232577c49b` |
| `scripts/build_research_campaign_progress.py` | READ | json+jsonl | 127,263 | `c4a3fb185c6d6361bce339ae0408f744a5764305` |
| `scripts/build_5913_combo_effectiveness_review.py` | READ | json+jsonl | 19 | `f18dfad4ee7bc6f93f883932b9a5a9d9dd3adcf8` |
| `scripts/build_research_fog_map.py` | READ | json+jsonl | 145,146 | `457d260f663cc1fa39ade1e767bb2317404bf100` |
| `scripts/run_representative_replay_drain_worker.py` | WRITE | json+jsonl | 325 | `3b4322a7d2b96707648e6febece73762a93a1f31` |
| `scripts/fog_authority_contracts.py` | REFERENCE_ONLY | json+jsonl | 31 | `8de650fc21d832f0b18cc56271f5b13c2a10a4e4` |
| `scripts/research_map_linkage_smoke.py` | READ | json+jsonl | 118 | `ffb0fd3cd3e85631d6d970dc8460f3cce70a417d` |
| `scripts/backfill_research_map_run_history.py` | BOTH | json+jsonl | 23,32,34 | `1a5a59fdde81b29f6cb3288fdc9973989e61b1db` |
| `scripts/verify_research_map_run_history_backfill.py` | READ | json+jsonl | 30 | `1e125a25f8db87377142b35118bd3f7a0d320c39` |
| `scripts/run_liquidity_replay_v2_batch.py` | BOTH | json+jsonl | 23 | `b754a721f23aa35fb531f702a5e464dd9e7cca5b` |
| `scripts/build_weekend_universe_inventory.py` | READ | json+jsonl | 205 | `80eadf902b5e81182b117435b38b78efb6e403a4` |
| `app/research/legacy_migration.py` | READ | json+jsonl | 39,50 | `147e812dea4874e6acc9425d15cb083c3ed275f9` |
| `app/research/fog_map_domain.py` | READ | json+jsonl | 816 | `b54fa88311c9aa8b080a898cfce01b1173f4c3c0` |
| `app/research/contracts.py` | REFERENCE_ONLY | json+jsonl | 744,807 | `7deddc03d80e12d8a57e29fc9e991121061c4aa6` |
| `app/research/fog_map_render.py` | READ | json+jsonl | 1737,2402 | `5ece90778761220735f6f86901926def5c26424c` |
| `app/research/batch_owner.py` | BOTH | json | 220,374,449 | `252d03c505413189c71bf4d4896e89fe0ff96507` |
| `app/research/history_compatibility_projection.py` | BOTH | json+jsonl | 22,65 | `7a091a6f8885afd04abe09253ec6bb41bf1aaa69` |
| `docs/tasks/2026-08-14_CARD-NEW-TOP10-RESEARCH-LEDGER-AND-LEARNING-CORE-V1.md` | REFERENCE_ONLY | json+jsonl | 309,310,487,489,520,521,552 | `d06db1477a11d53a707a0ba1de56eab74c2a2b54` |
| `docs/tasks/2026-06-13_WEEKEND-TRAINING-00_full_universe_burn_down_plan.md` | REFERENCE_ONLY | json+jsonl | 101 | `980e5a33bea8aef7fb5062ed20e2bb98faa7567d` |
| `docs/tasks/2026-06-12_LIQUIDITY-REPLAY-01_quality_universe_strict_replay.md` | REFERENCE_ONLY | json+jsonl | 35 | `b097dbac8158a186722012d53c9d074072207d66` |
| `docs/tasks/2026-06-11_RESEARCH-MAP-01_gamified_fog_of_war_dashboard.md` | REFERENCE_ONLY | json | 71 | `389c5114184815cac37edf36d093775eed23c1bd` |
| `docs/tasks/2026-06-12_RESEARCH-RESULT-REVIEW-01_5913_combo_effectiveness_review.md` | REFERENCE_ONLY | json+jsonl | 27 | `e61f9dc76144e968e379fa11905201f2e6e02604` |
| `docs/tasks/2026-08-02_FOG-REPRESENTATIVE-REPLAY-NO-PROGRESS-01.md` | REFERENCE_ONLY | json+jsonl | 34 | `0345fe31d8f2acce167f738531e9934a04a02389` |
| `docs/tasks/2026-06-12_RESEARCH-MAP-V2-02_architecture_handoff.md` | REFERENCE_ONLY | json+jsonl | 67,102 | `3907b8d94c65b89d846680f9e5ce705b755eb725` |
| `docs/tasks/2026-06-12_LIQUIDITY-REPLAY-03_stage2_risk_capped_candidates.md` | REFERENCE_ONLY | json+jsonl | 75 | `077fafb2defded9fa774a7ce504836420ce99b69` |
| `docs/tasks/2026-06-13_WEEKEND-TRAINING-03_representative_replay_runner.md` | REFERENCE_ONLY | json+jsonl | 69 | `eb204ecb495a61147c3f0820c359f85264c56bda` |
| `docs/tasks/2026-06-13_WEEKEND-TRAINING-01_universe_inventory_equivalence.md` | REFERENCE_ONLY | json+jsonl | 15 | `75a8743a6d13ff5e00c4e98c76ddb4149cb6df25` |
| `docs/tasks/2026-06-10_REVIEW-AUTONOMOUS-RESEARCH-MANAGER.md` | REFERENCE_ONLY | json | 9,28,93 | `4410344cac512b29e709e28582031d742c117809` |
| `docs/tasks/2026-06-17_WEEKEND-TRAINING-OVERNIGHT-01_full_night_unlock_and_replay_campaign.md` | REFERENCE_ONLY | json+jsonl | 181 | `31a7d1a50b1124d3aab99db3194977d21f0b92f5` |
| `docs/tasks/2026-06-12_LIQUIDITY-REPLAY-02_v2_component_batch.md` | REFERENCE_ONLY | json+jsonl | 24 | `0edbd2f966ffb12f8b51633ba51bfaade4a627a9` |

## F4：inventory completeness boundary

- Completeness means committed text at base `origin/main@4c6d41a44314beb3592ccdf7a9b43d8fe614ad88` matching the exact re-runnable queries above.
- It does not prove dynamic runtime reads/writes, untracked files, generated artifact behavior, external scheduler behavior, or production load.
- CodeGraph was retried for this repair and still returned uninitialized; all source inventory therefore uses the explicit `rg` universe plus file blob hashes.

## Terminal boundary summary

- Success requires validated executed units and observed execution facts.
- Failed/rejected/cancelled paths must remain explicit terminal receipts, not inferred from filesystem side effects.
- Missing terminal receipt is a fail-closed condition.
- Orphan reconciliation uses `UNKNOWN`; it must not guess requested/executed or sealed-use facts.

## Conflicts / unknowns surfaced

- `UNKNOWN`: runtime writes and untracked/generated artifacts were intentionally not inspected; A0 has no authority to mutate or observe live runtime.
- `UNKNOWN`: limited text search is not a dynamic dataflow proof.
- No terminal-boundary `CONFLICT` was found in Lane A’s allowed evidence.
