# A0 Lane B 04 - Dataset and Features Lineage Map

as_of: 2026-08-30
base: origin/main@4c6d41a44314beb3592ccdf7a9b43d8fe614ad88
scope: read-only mapping; no dataset/runtime/schema/code mutation
stop_status: IDENTITY_GRAIN_AMBIGUITY_TRIGGERED

## Evidence notes

- CodeGraph status: unavailable for this worktree; CodeGraph reported that the lane worktree was not initialized. Fallback used: bounded `rg`, `sed`, `nl`, `git hash-object`, and committed-file checks only.
- `.work/current` was not read or written.
- Evidence hashes below are Git blob hashes for repository files unless prefixed otherwise.
- Dataset identity is not treated as a path. Existing runtime contracts increasingly use `sha256:<content>` hashes; this map keeps path as a locator only.
- Negative findings are bounded to this lane's committed-evidence search universe: `<repo-root>/app`, `<repo-root>/scripts`, `<repo-root>/config`, `<repo-root>/docs/operations`, and `<repo-root>/docs/RESEARCH_SPINE_BACKLOG.md`; runtime artifacts and `.work/current` were excluded by card boundary.

## Evidence index

| evidence_ref | evidence_hash | notes |
|---|---:|---|
| `<repo-root>/AGENTS.md` | `a00b7fc1a95c04b53ec7f65da0f7d66c93b15c12` | project constraints |
| `<repo-root>/docs/operations/CURRENT_OPERATIONAL_FRONTIER.md` | `0e2a12569f94065e1026062e47498b5cdb582be0` | current A0 boundary |
| `<repo-root>/docs/RESEARCH_SPINE_BACKLOG.md` | `9e84f150e37c3b717df5a85a0e5be57b38b4439b` | A0 bundle and claim contract |
| `<repo-root>/app/data_fetcher.py` | `0ac7a2d97deeb667d72c43b75eea3130084fb6f9` | TWSE/TPEX provider acquisition |
| `<repo-root>/app/pipeline_cli.py` | `1aa6a129e5c90cc66defc50cb2bbf012fd84160a` | ETL stage ordering |
| `<repo-root>/app/pipeline/fetch_stage.py` | `d040a5a7a8ca2a8cb4e2df4accb31690d1648532` | raw provider/snapshot input into ETL |
| `<repo-root>/app/pipeline/indicator_stage.py` | `9b1cee766af3d75a93e2f80b7b9dfda65c5cc88d` | technical and volume indicator transform |
| `<repo-root>/app/pipeline/event_stage.py` | `b91616ade1f1cc0e14091865b25bd60902fde957` | `events.parquet` and `features.parquet` writer |
| `<repo-root>/app/pipeline/filter_stage.py` | `9ed4cc556b4457317f9e2568a6d2c487160cc4bd` | `universe.parquet` writer |
| `<repo-root>/app/pipeline/validation.py` | `ddffc0011f1bacd706fe5c5b8882ff5383b6d086` | dataset contract validator |
| `<repo-root>/app/pipeline/validation_snapshot.py` | `96f7b3bc4a3e779f2a9d4d37b3ace95e87ff9d18` | offline digest-pinned provider seam |
| `<repo-root>/app/modeling/feature_contract.py` | `1d000c54df79fc6c09acd2a0c386c3ee41e9c520` | M4 merged feature frame |
| `<repo-root>/app/agent_b_modeling.py` | `a537e6802d9a84b053fa5ed4dd9ddcbf07dfc2e6` | training consumer |
| `<repo-root>/app/agent_b_ranking.py` | `8441466b84e5d91f1592bb26b25db3abf89f80d7` | ranking consumer |
| `<repo-root>/app/research/contracts.py` | `7deddc03d80e12d8a57e29fc9e991121061c4aa6` | TrialSpec contract |
| `<repo-root>/app/research/run_receipts.py` | `4156a42507c12090b7d368b83b435bd2cee0fc26` | requested/executed receipt lifecycle |
| `<repo-root>/app/research/ranking_provenance_receipt.py` | `f6257d74493b0660f164220e16d8cf1c7fe5e366` | ranking provenance bundle |
| `<repo-root>/app/research/shadow_replay_availability.py` | `2f5d3fef96042fa880d54e6e965b9fc85c6a5da4` | replay input availability inventory |
| `<repo-root>/scripts/fog_daily_source_lineage.py` | `7c1c9c6036f25ca15b0c6fd38b28bbd28da001fe` | partial daily source lineage over features path/hash/date |
| `<repo-root>/scripts/run_backtest_strategy_matrix.py` | `3453780dc1791d68e782d0d8693ce8dfa8e641c0` | strategy matrix execution authority |
| `<repo-root>/scripts/build_historical_ranking_replay_set.py` | `9d9b5ff40b58353b80ef7444dc310e17d3ee5c97` | historical ranking replay set producer |

## Current lineage map

```text
Provider acquisition or validation snapshot
  - TWSE RWD MI_INDEX / TPEX daily quotes via DataFetcherOrchestrator
  - validation-only digest-pinned snapshot provider
  - FinMind chip data best-effort integration
        |
        v
FetchStage normalized daily rows
  - tradable universe filter
  - duplicate (date, stock_id) dedupe with market priority
        |
        v
IndicatorStage
  - TechnicalIndicators.calculate_all_indicators()
  - VolumeIndicators.calculate_all_volume_indicators()
        |
        v
FundamentalStage / EventStage / FilterStage
  - revenue/fundamental values are best-effort or missing, not synthetic
  - EventStage writes data/clean/events.parquet and data/clean/features.parquet
  - FilterStage writes data/clean/universe.parquet
        |
        v
PipelineDataValidator
  - shape, keys, numeric columns, latest coverage, latest market counts
        |
        v
Consumers
  - LightGBMTrainer.load_features() for training
  - StockRanker.load_daily_data() for daily ranking
  - historical ranking/replay/Research Spine receipts
```

## Dataset grain reconciliation

| field/name | producer | consumer | actual grain | same-name ambiguity | unique authority | mapping evidence |
|---|---|---|---|---|---|---|
| raw acquisition / payload attempt | `AsyncTWSEFetcher`, `AsyncTPEXFetcher`, `DataFetcherOrchestrator` | FetchStage and downstream ETL diagnostics | per provider/day request, response, fallback method, normalized rows | no same-name field found; absence is a measured gap | no durable authority found in bounded search | `app/data_fetcher.py` success logs only; bounded query `raw_receipt|provider_attempt|acquisition_receipt|acquisition.*receipt|SourceLineage` over `<repo-root>/app`, `<repo-root>/scripts`, `<repo-root>/config`, `<repo-root>/docs/operations`, `<repo-root>/docs/RESEARCH_SPINE_BACKLOG.md` found no live raw acquisition receipt |
| `features.parquet` artifact | `EventStage` | validator, many scripts, Research Spine source manifests | one parquet file bytes at a locator path | yes when called "dataset" by receipts | partial: artifact hash authority exists, path is only locator | `app/pipeline/event_stage.py`; `app/pipeline/validation.py`; `scripts/fog_daily_source_lineage.py` names `features_path`, `features_sha256`, `daily_source_date` |
| `dataset_authority.dataset_hash` / strategy-matrix `dataset_hash` | `begin_topic_attempt()` and `run_backtest_strategy_matrix.py` | TrialSpec validators, receipt finalizer, observation ingest/learning | hash of a one-file `dataset_manifest` when `features_path` is a file | yes: field name says dataset but code validates exactly one file hash | unique only for the `features.parquet` artifact grain | `app/research/run_receipts.py:128-131`, `app/research/run_receipts.py:465-467`, `scripts/run_backtest_strategy_matrix.py:626-659` |
| M4 effective feature frame | `load_m4_feature_frame()` / `build_m4_feature_frame()` | `LightGBMTrainer`, `StockRanker`, historical replay producer | derived frame from `features.parquet`, optional `events.parquet`, fundamentals cache, `config/signals.yaml`, and transformation code | yes if downstream interprets `dataset_hash` as the M4 frame identity | no single authority found that deterministically maps the one-file `dataset_hash` to all M4 inputs and transform version | `app/modeling/feature_contract.py:84-151`, `app/agent_b_modeling.py:76-104`, `app/agent_b_ranking.py:197-229`, `scripts/build_historical_ranking_replay_set.py:140-401` |
| ranking replay source bundle | `scripts/build_historical_ranking_replay_set.py` and `ranking_provenance_receipt` | replay/admission and provenance review | multi-artifact bundle: features/universe/config/model/ranking receipts | separate from `dataset_hash`; can coexist but does not resolve M4 dataset name | authority exists for replay bundle only | `scripts/build_historical_ranking_replay_set.py:260-381`, `app/research/ranking_provenance_receipt.py:143-191` |

## Identity-grain verdict

`IDENTITY_GRAIN_AMBIGUITY_TRIGGERED`: bounded committed evidence shows that the same `dataset_hash` / `dataset_authority.dataset_hash` field is produced and validated as a one-file `features.parquet` artifact hash, while model/ranking consumers load an effective M4 frame from additional inputs and transformation logic. No deterministic mapping evidence was found that binds the one-file hash to `events.parquet`, fundamentals cache, `config/signals.yaml`, and the M4 transform version. This is an architecture blocker for A1 admission, not a simple missing-evidence note.

## Structured claims

### CLAIM-DATASET-001

claim_id: CLAIM-DATASET-001
subject: `data/clean/features.parquet` producer
claim: `features.parquet` is currently written by `EventStage` after fetch, indicator, fundamental, and event stages have transformed the in-memory frame; the write itself is a parquet artifact publication, not a separately named immutable dataset identity.
authority: `repository_committed_code`
scope: `A0 Lane B / dataset lineage`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/pipeline_cli.py` builds `FetchStage -> IndicatorStage -> FundamentalStage -> EventStage -> FilterStage -> ReportStage`; `<repo-root>/app/pipeline/event_stage.py:24-27` writes `features.parquet`.
evidence_hash: `app/pipeline_cli.py=1aa6a129e5c90cc66defc50cb2bbf012fd84160a; app/pipeline/event_stage.py=b91616ade1f1cc0e14091865b25bd60902fde957`
status: CONFIRMED
owner: A0 Integrator
next_action: A1 admission input: define canonical dataset identity as content/spec/coverage/version tuple; do not use filesystem path alone.

### CLAIM-DATASET-002

claim_id: CLAIM-DATASET-002
subject: Raw market input acquisition
claim: Live ETL fetch obtains TWSE and TPEX daily quote frames per business day, normalizes fields, tags market as `TWSE` or `TPEX`, and concatenates all successful per-day provider results.
authority: `repository_committed_code`
scope: `A0 Lane B / raw market input -> normalized rows`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/data_fetcher.py:37-90`, `<repo-root>/app/data_fetcher.py:195-244`, `<repo-root>/app/data_fetcher.py:303-361`
evidence_hash: `0ac7a2d97deeb667d72c43b75eea3130084fb6f9`
status: CONFIRMED
owner: A0 Integrator
next_action: A1 admission input: raw provider payload receipt, endpoint identity, and fetch session evidence remain prerequisites to evaluate before admitting market-source lineage.

### CLAIM-DATASET-003

claim_id: CLAIM-DATASET-003
subject: Provider acquisition receipt
claim: In the bounded committed-evidence search universe, live TWSE/TPEX acquisition records only in-memory success logs with date/source/records/status/method; no live contract evidence was found that persists raw payload hash, endpoint URL, provider response metadata, session, request id, or fallback chain as immutable dataset evidence.
authority: `repository_committed_code`
scope: `A0 Lane B / acquisition and persistence receipt`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/data_fetcher.py:176-183`, `<repo-root>/app/data_fetcher.py:237-242`, `<repo-root>/app/data_fetcher.py:389-401`; bounded query `raw_receipt|provider_attempt|acquisition_receipt|acquisition.*receipt|SourceLineage` over `<repo-root>/app`, `<repo-root>/scripts`, `<repo-root>/config`, `<repo-root>/docs/operations`, `<repo-root>/docs/RESEARCH_SPINE_BACKLOG.md`
evidence_hash: `0ac7a2d97deeb667d72c43b75eea3130084fb6f9`
status: UNKNOWN
owner: A0 Integrator
next_action: Search excluded runtime artifacts only if separately authorized; otherwise treat raw acquisition receipt as a measured gap.

### CLAIM-DATASET-004

claim_id: CLAIM-DATASET-004
subject: Offline validation input seam
claim: Validation mode can replace live provider acquisition with a digest-pinned snapshot and records snapshot metadata in `context['stats']['validation_snapshot']`, but that seam is validation-only and does not prove live provider lineage for production ETL.
authority: `repository_committed_code`
scope: `A0 Lane B / validation provider semantics`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/pipeline/fetch_stage.py:25-37`; `<repo-root>/app/pipeline/validation_snapshot.py:33-88`
evidence_hash: `app/pipeline/fetch_stage.py=d040a5a7a8ca2a8cb4e2df4accb31690d1648532; app/pipeline/validation_snapshot.py=96f7b3bc4a3e779f2a9d4d37b3ace95e87ff9d18`
status: CONFIRMED
owner: A0 Integrator
next_action: Reuse digest-pinned snapshot semantics as a possible test fixture pattern only; do not treat it as live provider evidence.

### CLAIM-DATASET-005

claim_id: CLAIM-DATASET-005
subject: Normalized dataset validation
claim: The current validator treats `features`, `events`, and `universe` as downstream contracts and checks required columns, row/stock coverage, unique keys, numeric sanity, latest-date column coverage, and latest TWSE/TPEX market coverage for `features.parquet`.
authority: `repository_committed_code`
scope: `A0 Lane B / coverage and validation`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/pipeline/validation.py:109-180`, `<repo-root>/app/pipeline/validation.py:257-335`
evidence_hash: `ddffc0011f1bacd706fe5c5b8882ff5383b6d086`
status: CONFIRMED
owner: A0 Integrator
next_action: A1 admission input: validation checks are existing surface; immutable dataset identity/source receipt remains unresolved.

### CLAIM-DATASET-006

claim_id: CLAIM-DATASET-006
subject: M4 feature frame transformation
claim: Training and ranking consumers do not read only raw `features.parquet`; they build an M4 feature frame by normalizing keys, joining `events.parquet`, joining local fundamentals as-of, coercing feature groups, and returning metadata with coverage/notes.
authority: `repository_committed_code`
scope: `A0 Lane B / transformation and consumer-visible features`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/modeling/feature_contract.py:84-151`
evidence_hash: `1d000c54df79fc6c09acd2a0c386c3ee41e9c520`
status: CONFIRMED
owner: A0 Integrator
next_action: A1 admission input: resolve whether dataset identity names the one-file artifact or the effective M4 frame; if the latter, include all M4 inputs and transform version.

### CLAIM-DATASET-007

claim_id: CLAIM-DATASET-007
subject: Training consumer
claim: `LightGBMTrainer.load_features()` reads `features.parquet` plus sibling `events.parquet` through the M4 feature contract; if production `features.parquet` is missing it may fall back to `data/test/features_test.parquet`, so training dataset identity is branch-dependent.
authority: `repository_committed_code`
scope: `A0 Lane B / consumer publication`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/agent_b_modeling.py:76-104`
evidence_hash: `a537e6802d9a84b053fa5ed4dd9ddcbf07dfc2e6`
status: CONFIRMED
owner: A0 Integrator
next_action: A1 admission input: requested and executed dataset evidence need explicit fallback branch semantics before downstream research admission.

### CLAIM-DATASET-008

claim_id: CLAIM-DATASET-008
subject: Ranking consumer
claim: `StockRanker.load_daily_data()` requires `features.parquet`, loads the M4 feature frame, and uses `universe.parquet` if present; if the universe file is missing or empty it falls back to all feature stocks.
authority: `repository_committed_code`
scope: `A0 Lane B / ranking consumer`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/agent_b_ranking.py:197-229`
evidence_hash: `8441466b84e5d91f1592bb26b25db3abf89f80d7`
status: CONFIRMED
owner: A0 Integrator
next_action: Treat universe fallback as part of executed dataset evidence; do not infer universe identity from `features.parquet`.

### CLAIM-DATASET-009

claim_id: CLAIM-DATASET-009
subject: TrialSpec requested dataset reference
claim: `begin_topic_attempt()` computes a source manifest for `features_path`, derives `dataset_hash`, and stores it in each TrialSpec as `dataset_authority.dataset_hash` plus `execution_profile.dataset_manifest`.
authority: `repository_committed_code`
scope: `A0 Lane B / TrialSpec requested dataset reference`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/research/run_receipts.py:98-172`; `<repo-root>/app/research/contracts.py` validates `dataset_authority`.
evidence_hash: `app/research/run_receipts.py=4156a42507c12090b7d368b83b435bd2cee0fc26; app/research/contracts.py=7deddc03d80e12d8a57e29fc9e991121061c4aa6`
status: CONFIRMED
owner: A0 Integrator
next_action: Preserve this content-hash direction; expand identity only where measured gaps require source/version/coverage detail.

### CLAIM-DATASET-010

claim_id: CLAIM-DATASET-010
subject: Executed dataset evidence
claim: `finish_topic_attempt()` requires each strategy matrix row to include `execution_authority.dataset_hash` and `dataset_manifest`; it rejects unresolved manifests or mismatched dataset hash, then records executed dataset hash in execution units and requested/executed resolution events.
authority: `repository_committed_code`
scope: `A0 Lane B / executed dataset evidence`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/research/run_receipts.py:432-470`, `<repo-root>/app/research/run_receipts.py:490-586`, `<repo-root>/app/research/run_receipts.py:620-635`
evidence_hash: `4156a42507c12090b7d368b83b435bd2cee0fc26`
status: CONFIRMED
owner: A0 Integrator
next_action: A1 admission input: executed dataset evidence is artifact-hash evidence only until raw market-source and M4 effective-frame grain are reconciled.

### CLAIM-DATASET-011

claim_id: CLAIM-DATASET-011
subject: Strategy matrix dataset publication
claim: `run_backtest_strategy_matrix.py` puts `features_path` into a `dataset_manifest`, stores `_file_sha256(features_path)` as `dataset_hash`, and includes it in `execution_authority` per scenario.
authority: `repository_committed_code`
scope: `A0 Lane B / backtest consumer publication`
as_of: 2026-08-30
evidence_ref: `<repo-root>/scripts/run_backtest_strategy_matrix.py:626-658`
evidence_hash: `3453780dc1791d68e782d0d8693ce8dfa8e641c0`
status: CONFIRMED
owner: A0 Integrator
next_action: Keep strategy-matrix evidence as executed artifact evidence; do not let it substitute raw acquisition proof.

### CLAIM-DATASET-012

claim_id: CLAIM-DATASET-012
subject: Ranking provenance source immutability
claim: Ranking replay capture snapshots feature/universe/config/model inputs before and after generation, refuses producer source drift, creates content-addressed model snapshots, and emits per-ranking receipts plus a complete manifest.
authority: `repository_committed_code`
scope: `A0 Lane B / publication and consumer receipt`
as_of: 2026-08-30
evidence_ref: `<repo-root>/scripts/build_historical_ranking_replay_set.py:260-381`; `<repo-root>/app/research/ranking_provenance_receipt.py:143-191`
evidence_hash: `scripts/build_historical_ranking_replay_set.py=9d9b5ff40b58353b80ef7444dc310e17d3ee5c97; app/research/ranking_provenance_receipt.py=f6257d74493b0660f164220e16d8cf1c7fe5e366`
status: CONFIRMED
owner: A0 Integrator
next_action: Possible A1 adoption: wrap existing receipt pattern for Research Spine dataset identity rather than introduce a second registry.

### CLAIM-DATASET-013

claim_id: CLAIM-DATASET-013
subject: Current materialized `data/clean/features.parquet`
claim: A0 Lane B did not inspect untracked/runtime parquet bytes and therefore cannot confirm current materialized row count, date range, content hash, or producer run for `data/clean/features.parquet`.
authority: `A0_card_boundary`
scope: `A0 Lane B / committed evidence only`
as_of: 2026-08-30
evidence_ref: `<task-card>/CARD-NEW-TOP10-RESEARCH-A0-LANE-B-20260830.md`; `<repo-root>/docs/operations/CURRENT_OPERATIONAL_FRONTIER.md`
evidence_hash: `card_file=not_git_tracked; docs/operations/CURRENT_OPERATIONAL_FRONTIER.md=0e2a12569f94065e1026062e47498b5cdb582be0`
status: UNPINNED_RUNTIME_ARTIFACT
owner: A0 Integrator
next_action: If later required, authorize a separate runtime artifact inspection; do not infer runtime dataset state from committed code.

### CLAIM-DATASET-014

claim_id: CLAIM-DATASET-014
subject: `dataset_hash` grain ambiguity
claim: `dataset_authority.dataset_hash` and strategy-matrix `dataset_hash` are validated as the hash of a one-file `features.parquet` manifest, but model/ranking consumers use an effective M4 frame assembled from `features.parquet`, optional `events.parquet`, fundamentals cache, `config/signals.yaml`, and transform code; no deterministic mapping from the one-file hash to that effective frame was found in the bounded committed-evidence search universe.
authority: `repository_committed_code`
scope: `A0 Lane B / architecture stop`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/research/run_receipts.py:128-131`, `<repo-root>/app/research/run_receipts.py:465-467`, `<repo-root>/scripts/run_backtest_strategy_matrix.py:626-659`, `<repo-root>/app/modeling/feature_contract.py:84-151`, `<repo-root>/app/agent_b_modeling.py:76-104`, `<repo-root>/app/agent_b_ranking.py:197-229`; bounded query `load_m4_feature_frame|build_m4_feature_frame|features_sha256|dataset_hash|dataset_manifest|events.parquet|fundamental|config/signals.yaml`
evidence_hash: `app/research/run_receipts.py=4156a42507c12090b7d368b83b435bd2cee0fc26; scripts/run_backtest_strategy_matrix.py=3453780dc1791d68e782d0d8693ce8dfa8e641c0; app/modeling/feature_contract.py=1d000c54df79fc6c09acd2a0c386c3ee41e9c520; app/agent_b_modeling.py=a537e6802d9a84b053fa5ed4dd9ddcbf07dfc2e6; app/agent_b_ranking.py=8441466b84e5d91f1592bb26b25db3abf89f80d7`
status: CONFLICT
owner: A0 Integrator
next_action: Stop at architecture blocker: A1 admission input is to choose and name the canonical dataset grain, then require deterministic mapping from requested `dataset_hash` to executed consumer-visible inputs.

## Measured gaps

1. Raw market input identity is not yet a first-class immutable dataset receipt. Current committed code normalizes provider payloads and writes parquet, but bounded committed-evidence search did not find a durable raw payload hash/session/fallback/endpoint receipt.
2. Effective M4 dataset identity spans `features.parquet`, `events.parquet`, fundamentals cache, config, and transformation code. Existing Research Spine hashes mostly pin file bytes/manifest; they do not fully name a dataset version contract.
3. Universe fallback in ranking and test fallback in training are observable code paths. Any A1 identity catalog needs to record requested and executed dataset branch explicitly.
4. Validator covers shape and latest-market coverage, but validation result is not itself tied to a durable dataset identity for each run in the live ETL path.
5. Strategy matrix and ranking provenance receipts are useful existing seams. Minimum-sufficient adoption likely means wrapping/extending these receipts, not building a new generic runtime registry.

## Stop assessment

- governing-authority conflict: not observed
- identity-grain ambiguity: `IDENTITY_GRAIN_AMBIGUITY_TRIGGERED`; same `dataset_hash` name is one-file artifact authority in receipts while consumer-visible M4 dataset requires additional inputs with no deterministic mapping evidence
- terminal-boundary ambiguity: not observed
- required runtime mutation: not required and not performed

stop_status: IDENTITY_GRAIN_AMBIGUITY_TRIGGERED

## OMI supplemental lens

Source: `lulu930128/open-market-intelligence@2d54c5983b8597babd804110f022a5f299e45a9d`, `authority=prior_art_only`.

- Current TOP10 capability: artifact-level hashes, TrialSpec dataset_authority, executed dataset_hash, ranking provenance receipts, and dataset validators.
- Equivalent OMI capability: provider-neutral market observation lineage, dataset lifecycle contracts, provider policy, resolver quality/freshness semantics.
- Actual TOP10 gap: raw market acquisition and dataset lifecycle are not yet represented as bounded provider-neutral observations or operation receipts.
- Possible adoption: A1 admission input only; ADAPT vocabulary and thin contract shape for source lineage, bounded refresh result, and dataset health; use current TOP10 receipts as local wrapper.
- Not applicable: do not import OMI runtime, SQLite/Alembic schema, provider adapters, resolver/control plane, or UI concepts into Card A.
- Not yet proven: exact OMI pinned code behavior beyond inspected README and market_data files is supplemental only; no runtime compatibility or copy-code acceptance was established.
