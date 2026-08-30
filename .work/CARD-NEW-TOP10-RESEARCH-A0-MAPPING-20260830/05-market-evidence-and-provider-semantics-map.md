# A0 Lane B 05 - Market Evidence and Provider Semantics Map

as_of: 2026-08-30
base: origin/main@4c6d41a44314beb3592ccdf7a9b43d8fe614ad88
scope: read-only provider/evidence semantics mapping; no provider adapter/runtime/schema/config mutation
stop_status: IDENTITY_GRAIN_AMBIGUITY_TRIGGERED

## Evidence notes

- CodeGraph status: unavailable for this worktree; CodeGraph reported that the lane worktree was not initialized. Bounded `rg`/file-read fallback used.
- `.work/current` was not read or written.
- Evidence hashes below are Git blob hashes for repository files or GitHub blob SHAs for pinned OMI prior art.
- OMI is supplemental prior art only; it is not runtime authority for NEW-TOP10.
- Negative provider/receipt findings are bounded to committed evidence under `<repo-root>/app`, `<repo-root>/scripts`, `<repo-root>/config`, `<repo-root>/docs/operations`, and `<repo-root>/docs/RESEARCH_SPINE_BACKLOG.md`; runtime artifacts and `.work/current` were excluded by card boundary.

## Evidence index

| evidence_ref | evidence_hash | notes |
|---|---:|---|
| `<repo-root>/app/data_fetcher.py` | `0ac7a2d97deeb667d72c43b75eea3130084fb6f9` | TWSE/TPEX fetch, retry, requests fallback, provider logs |
| `<repo-root>/app/pipeline/fetch_stage.py` | `d040a5a7a8ca2a8cb4e2df4accb31690d1648532` | provider selection between validation snapshot and live orchestrator; FinMind skip semantics |
| `<repo-root>/app/finmind_integrator.py` | `185599d9b36e71b8b73ac581a1a44609cd6a52a1` | FinMind chip/margin integration behavior |
| `<repo-root>/app/finmind_fetcher.py` | `bea7c2e317db147e2847f5f2d7616caaf031b969` | FinMind DataLoader calls |
| `<repo-root>/app/pipeline/validation_snapshot.py` | `96f7b3bc4a3e779f2a9d4d37b3ace95e87ff9d18` | digest-pinned offline provider |
| `<repo-root>/app/pipeline/validation.py` | `ddffc0011f1bacd706fe5c5b8882ff5383b6d086` | dataset freshness/coverage validator |
| `<repo-root>/config/reference_sources.yaml` | `4f745990509104e35579c8f13033529febbff182` | reference source scrape configuration |
| `<repo-root>/config/fog_runtime_data_authority_v1.json` | `ff32dfba72fdbccaed8ce196edb0f64e0b1132e1` | existing data authority config, not market provider authority |
| `OMI README.md @ 2d54c5983b8597babd804110f022a5f299e45a9d` | `047fcd88dffc6b76b4edbf40859f827757db184f` | local-first, source/freshness/fallback visibility |
| `OMI backend/app/market_data/contracts.py @ 2d54c5983b8597babd804110f022a5f299e45a9d` | `9f6879c327c993f709ca21a40cbbb30ea7f60663` | SourceLineage, EvidenceFreshness, health states |
| `OMI backend/app/market_data/acquisition_observability.py @ 2d54c5983b8597babd804110f022a5f299e45a9d` | `fb9e63de9b8d09aa49b02909c8b1b41d9c547d75` | acquisition diagnostics |
| `OMI backend/app/market_data/dataset_lifecycle.py @ 2d54c5983b8597babd804110f022a5f299e45a9d` | `a335044b6d174386a5d631475053770ca573fab1` | dataset lifecycle and bounded operation result |
| `OMI backend/app/market_data/provider_policy.py @ 2d54c5983b8597babd804110f022a5f299e45a9d` | `402c4e62c61fdd0755db1dc673e49ae06f0539f7` | pure provider routing policy |
| `OMI backend/app/market_data/resolution.py @ 2d54c5983b8597babd804110f022a5f299e45a9d` | `d9b7f1892eb34ae8d425a05bcd4b20e14bba10a5` | candidate selection, fallback, freshness/session semantics |

## Current provider semantics

```text
FetchStage selection
  if TOP10_STORAGE_VALIDATION_MODE=1:
    ValidationSnapshotProvider
    - digest-pinned local snapshot
    - no FinMind external acquisition
  else:
    DataFetcherOrchestrator
    - TWSE daily quotes
    - TPEX daily quotes
    - FinMind chip/margin best effort

DataFetcherOrchestrator
  per business day:
    AsyncTWSEFetcher.fetch_daily_quotes()
    AsyncTPEXFetcher.fetch_daily_quotes()
    concatenate successful frames
  provider result semantics:
    success => in-memory data_source_log row
    failure/empty => warning or None
    no immutable provider attempt receipt found

TWSE
  source URL: https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX
  params: date, ALLBUT0999, response=json
  retry statuses: 301/302/303/307/308/429/503
  special fallback: if async path sees 307, try synchronous requests fallback

TPEX
  source URL: https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php
  params: zh-tw ROC date and AL securities
  fallback parser: accepts aaData or tables format

FinMind
  source: FinMind DataLoader
  provider role: institutional, margin, daily short-sale balances
  failure semantics: return empty DataFrame or skip with warning; TOP10 keeps availability flags when merged
```

## Negative finding search ledger

| finding | bounded search universe | query terms | result classification |
|---|---|---|---|
| no durable live provider-attempt receipt found | `<repo-root>/app`, `<repo-root>/scripts`, `<repo-root>/config`, `<repo-root>/docs/operations`, `<repo-root>/docs/RESEARCH_SPINE_BACKLOG.md` | `raw_receipt`, `raw payload`, `provider_attempt`, `acquisition_receipt`, `acquisition.*receipt`, `SourceLineage` | `UNKNOWN`: bounded search found provider code, Research Spine hashes, and daily `features_sha256` lineage, but no committed live receipt tying raw provider payload/fallback/session to normalized rows and dataset hash |
| provider/dataset/resolved health not first-class current TOP10 contracts | same bounded universe | `provider_health`, `DatasetHealth`, `ResolvedEvidence`, `dataset_lifecycle` | `UNKNOWN`: OMI has prior-art vocabulary; NEW-TOP10 committed evidence does not show equivalent live market provider health contracts |
| live freshness/session/release-window authority not durable | same bounded universe | `freshness`, `latest_market_coverage`, `daily_source_date`, `market_run_date`, `session` | `UNKNOWN`: validators and `fog_daily_source_lineage` cover latest date/hash, but no provider session/release-window receipt was found |

## Structured claims

### CLAIM-MARKET-001

claim_id: CLAIM-MARKET-001
subject: TWSE provider selection and fallback
claim: TWSE live quote acquisition uses TWSE RWD `MI_INDEX` with `ALLBUT0999`; it retries redirect/rate-limit/service statuses and only invokes synchronous `requests` fallback when a 307 response triggered `requests_fallback_reason`.
authority: `repository_committed_code`
scope: `A0 Lane B / provider selection and fallback`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/data_fetcher.py:47-90`, `<repo-root>/app/data_fetcher.py:99-119`
evidence_hash: `0ac7a2d97deeb667d72c43b75eea3130084fb6f9`
status: CONFIRMED
owner: A0 Integrator
next_action: A1 admission input: provider evidence would need receipt fields for async status, fallback reason, endpoint, params, and final method.

### CLAIM-MARKET-002

claim_id: CLAIM-MARKET-002
subject: TPEX provider selection
claim: TPEX live quote acquisition uses the TPEx OTC daily quote endpoint and supports both `aaData` and `tables` payload shapes; it records success rows, while bounded committed-evidence search did not find a durable provider attempt receipt.
authority: `repository_committed_code`
scope: `A0 Lane B / provider selection and payload parsing`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/data_fetcher.py:195-244`, `<repo-root>/app/data_fetcher.py:250-288`
evidence_hash: `0ac7a2d97deeb667d72c43b75eea3130084fb6f9`
status: CONFIRMED
owner: A0 Integrator
next_action: A1 admission input: keep parser compatibility as current behavior; provider receipt remains a prerequisite only if Research Spine admission requires live source lineage.

### CLAIM-MARKET-003

claim_id: CLAIM-MARKET-003
subject: Provider success/failure semantics
claim: Within the bounded committed-evidence search universe, current provider success semantics are row-count logs and merged market tags; failure semantics are mostly `None`, empty DataFrame, warnings, and skipped FinMind stats. Provider Health, Dataset Health, and Resolved Evidence Health were not found as separated first-class current TOP10 contracts.
authority: `repository_committed_code`
scope: `A0 Lane B / freshness session authority`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/data_fetcher.py:176-183`, `<repo-root>/app/data_fetcher.py:237-242`, `<repo-root>/app/pipeline/fetch_stage.py:52-70`; bounded query `provider_health|DatasetHealth|ResolvedEvidence|dataset_lifecycle`
evidence_hash: `app/data_fetcher.py=0ac7a2d97deeb667d72c43b75eea3130084fb6f9; app/pipeline/fetch_stage.py=d040a5a7a8ca2a8cb4e2df4accb31690d1648532`
status: UNKNOWN
owner: A0 Integrator
next_action: Treat separated provider/dataset/resolved health as a measured gap; do not create a new shared control plane in A0.

### CLAIM-MARKET-004

claim_id: CLAIM-MARKET-004
subject: Validation snapshot provider
claim: Validation mode selects a local snapshot provider, requires snapshot coverage for the requested ETL window, records snapshot path/hash/coverage metadata, and disables FinMind external acquisition.
authority: `repository_committed_code`
scope: `A0 Lane B / validation provider semantics`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/pipeline/fetch_stage.py:25-37`, `<repo-root>/app/pipeline/fetch_stage.py:52-57`, `<repo-root>/app/pipeline/validation_snapshot.py:69-88`, `<repo-root>/app/pipeline/validation_snapshot.py:90-112`
evidence_hash: `app/pipeline/fetch_stage.py=d040a5a7a8ca2a8cb4e2df4accb31690d1648532; app/pipeline/validation_snapshot.py=96f7b3bc4a3e779f2a9d4d37b3ace95e87ff9d18`
status: CONFIRMED
owner: A0 Integrator
next_action: Use as known-good digest-pinned input seam for tests; do not claim live market evidence from it.

### CLAIM-MARKET-005

claim_id: CLAIM-MARKET-005
subject: Freshness and market coverage
claim: Current committed validation checks latest `features.parquet` date and TWSE/TPEX latest-market coverage; within the bounded committed-evidence search universe, no durable session/release-window authority was found for the live ETL provider attempt.
authority: `repository_committed_code`
scope: `A0 Lane B / freshness`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/pipeline/validation.py:235-335`; `<repo-root>/scripts/fog_daily_source_lineage.py:85-139`; bounded query `freshness|latest_market_coverage|daily_source_date|market_run_date|session`
evidence_hash: `ddffc0011f1bacd706fe5c5b8882ff5383b6d086`
status: UNKNOWN
owner: A0 Integrator
next_action: A1 admission input: classify session/release-window evidence as an admission prerequisite or defer it explicitly; A0 does not set A2 scope.

### CLAIM-MARKET-006

claim_id: CLAIM-MARKET-006
subject: FinMind chip provider
claim: FinMind integration is a best-effort enrichment over top-volume stocks and preserves availability flags when merged; failure paths skip or return empty data rather than materializing a provider-level immutable attempt receipt.
authority: `repository_committed_code`
scope: `A0 Lane B / provider fallback and missing semantics`
as_of: 2026-08-30
evidence_ref: `<repo-root>/app/finmind_integrator.py`; `<repo-root>/app/finmind_fetcher.py`
evidence_hash: `app/finmind_integrator.py=185599d9b36e71b8b73ac581a1a44609cd6a52a1; app/finmind_fetcher.py=bea7c2e317db147e2847f5f2d7616caaf031b969`
status: CONFIRMED
owner: A0 Integrator
next_action: If chip signals enter Research Spine TrialSpec identity, include FinMind provider availability and call budget/coverage in executed evidence.

### CLAIM-MARKET-007

claim_id: CLAIM-MARKET-007
subject: Acquisition and persistence receipt
claim: Within the bounded committed-evidence search universe, no append-only acquisition receipt evidence was found that links raw provider payload bytes to normalized rows, parquet outputs, validation result, and Research Spine dataset hash.
authority: `repository_committed_code`
scope: `A0 Lane B / acquisition-persistence receipt`
as_of: 2026-08-30
evidence_ref: bounded query `raw_receipt|raw payload|provider_attempt|acquisition_receipt|acquisition.*receipt|SourceLineage|dataset_hash|dataset_manifest` over `<repo-root>/app`, `<repo-root>/scripts`, `<repo-root>/config`, `<repo-root>/docs/operations`, `<repo-root>/docs/RESEARCH_SPINE_BACKLOG.md`; inspected provider/receipt files cited in evidence index.
evidence_hash: `SEARCH_FALLBACK_NO_SINGLE_FILE_HASH`
status: UNKNOWN
owner: A0 Integrator
next_action: Mark as measured gap; if accepted, fill with minimum wrapper around current ETL stats and content hashes rather than a new database.

### CLAIM-MARKET-008

claim_id: CLAIM-MARKET-008
subject: OMI current-state lens
claim: OMI pinned README states the product keeps source, freshness, fallback, missing, and partial states visible, and separates research output from autonomous trading.
authority: `prior_art_only`
scope: `A0 Lane B / OMI supplemental lens`
as_of: 2026-08-30
evidence_ref: `https://raw.githubusercontent.com/lulu930128/open-market-intelligence/2d54c5983b8597babd804110f022a5f299e45a9d/README.md`
evidence_hash: `047fcd88dffc6b76b4edbf40859f827757db184f`
status: CONFIRMED
owner: A0 Integrator
next_action: Adopt as product semantics vocabulary only; do not copy OMI UI/runtime.

### CLAIM-MARKET-009

claim_id: CLAIM-MARKET-009
subject: OMI SourceLineage and freshness semantics
claim: OMI has a provider-neutral `SourceLineage` model with provider, source, authority, raw contract version, event/received/fetched timestamps, cache hit, observation id, raw receipt id, and content hash, plus explicit EvidenceFreshness and health status enums.
authority: `prior_art_only`
scope: `A0 Lane B / possible adoption`
as_of: 2026-08-30
evidence_ref: `OMI backend/app/market_data/contracts.py @ 2d54c5983b8597babd804110f022a5f299e45a9d`
evidence_hash: `9f6879c327c993f709ca21a40cbbb30ea7f60663`
status: CONFIRMED
owner: A0 Integrator
next_action: A1 admission input: ADAPT only the field vocabulary if source lineage is required; do not import OMI pydantic models wholesale.

### CLAIM-MARKET-010

claim_id: CLAIM-MARKET-010
subject: OMI provider routing and resolver semantics
claim: OMI separates pure provider routing policy from provider I/O, then resolves pre-acquired observations with freshness/session/policy checks and explicit selected/fallback/partial/stale/missing/policy-unsatisfied health.
authority: `prior_art_only`
scope: `A0 Lane B / possible adoption`
as_of: 2026-08-30
evidence_ref: `OMI backend/app/market_data/provider_policy.py`, `OMI backend/app/market_data/resolution.py @ 2d54c5983b8597babd804110f022a5f299e45a9d`
evidence_hash: `provider_policy=402c4e62c61fdd0755db1dc673e49ae06f0539f7; resolution=d9b7f1892eb34ae8d425a05bcd4b20e14bba10a5`
status: CONFIRMED
owner: A0 Integrator
next_action: A1 admission input or A2 prerequisite vocabulary only: possible adoption is `ADAPT`; current A0 must not implement a resolver/control plane.

### CLAIM-MARKET-011

claim_id: CLAIM-MARKET-011
subject: OMI dataset lifecycle
claim: OMI dataset lifecycle prior art names dataset owner, read/projection/capability IDs, expected state, eligibility, refresh operation, bounds, postcondition, and operation result fields; this maps to TOP10's missing dataset lifecycle contract but is broader than Card A's current scope.
authority: `prior_art_only`
scope: `A0 Lane B / possible adoption and non-goal`
as_of: 2026-08-30
evidence_ref: `OMI backend/app/market_data/dataset_lifecycle.py @ 2d54c5983b8597babd804110f022a5f299e45a9d`
evidence_hash: `a335044b6d174386a5d631475053770ca573fab1`
status: CONFIRMED
owner: A0 Integrator
next_action: A1 admission input: if dataset identity is admitted, adopt only bounded fields needed for NEW-TOP10 research datasets; reject full lifecycle runtime/database adoption.

## OMI prior-art decision

| Area | Current TOP10 | Equivalent OMI capability | Actual gap | Possible adoption | Not applicable | Not yet proven |
|---|---|---|---|---|---|---|
| Source lineage | provider rows normalized into `features.parquet`; limited in-memory source logs | `SourceLineage` with provider/source/timestamps/cache/raw receipt/content hash | raw payload and session are not tied to dataset hash | ADAPT field vocabulary | OMI runtime models/database | runtime compatibility |
| Provider fallback | TWSE has retry and 307 requests fallback; FinMind skips on failure | provider policy and acquisition diagnostic | fallback chain not persisted as receipt | ADAPT minimal fallback receipt fields | shared provider router | production provider behavior |
| Freshness/session | parquet latest-date and market coverage checks | EvidenceFreshness, MarketSession, resolver status | no durable live session/release-window proof in A0 evidence | ADAPT status vocabulary if admission needs it | OMI resolver/control plane | exact session calendar semantics |
| Dataset lifecycle | validator and Research Spine hashes exist | dataset lifecycle contract with owner/expected state/refresh bounds/postcondition | dataset identity lacks lifecycle owner/refresh operation contract | WRAP existing validators and receipts | registry/database import | live repairability |
| Acquisition diagnostics | warnings/stats only | bounded acquisition diagnostics | no immutable attempt result | ADAPT small receipt | external subscriptions/leases | raw payload retention policy |

## Measured gaps

1. Provider attempt identity is not durable: request id, endpoint, params, status sequence, fallback method, fetched/received time, raw payload/content hash, and normalization version are not part of current live ETL evidence.
2. Dataset freshness and market coverage are validated after publication, but validation result is not bound to a dataset identity/receipt in the live path.
3. FinMind is clearly best effort and availability-aware after merge, but source coverage, call budget, provider errors, and raw evidence are not represented in TrialSpec dataset authority.
4. OMI shows a credible ADAPT path for field vocabulary and bounded receipts; it should not be absorbed as runtime, registry, resolver, provider adapter, SQLite schema, or UI.
5. Identity grain reconciliation is owned by the dataset lineage map; provider semantics cannot resolve it alone.

## Stop assessment

- governing-authority conflict: not observed
- identity-grain ambiguity: `IDENTITY_GRAIN_AMBIGUITY_TRIGGERED` in `04-dataset-and-features-lineage-map.md`; provider map inherits the architecture blocker and does not override it
- terminal-boundary ambiguity: not observed
- required runtime mutation: not required and not performed

stop_status: IDENTITY_GRAIN_AMBIGUITY_TRIGGERED
