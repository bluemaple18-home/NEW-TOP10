# REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01 Delivery Summary

- status: `DELIVERED_CANDIDATE`
- chain: new successor chain; not `REGIME-RESEARCH-AUTONOMY-01` Repair-3
- source baseline: `b07b685b07d8a5944a86a92803c4198f96929f4b`
- model requested by card: `gpt-5.6-sol / high`
- runtime disclosure: exact model build and reasoning label were not exposed for audit
- merge / push / deploy / promotion: none

## Red → green

- Phase 0 red: a content-addressed, append-only `REGISTERED` three-combination
  `local_profile` family produced `ok=true`, `correction_family_size=3`, and
  `corrected_alpha=0.016666666666666666`.
- Focused red command result: `4 failed, 33 deselected`.
- Focused green result: `4 passed, 33 deselected`.
- Final targeted result: `39 passed`.
- Red receipt:
  `docs/evidence/REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01/phase0-red-baseline.md`.

## Trust-boundary contract

- Public exact-regime matrix reconstructs authority from the fixed repo contract.
- Registration must match one manager registry `PRE_REGISTRATION` record and its
  content hash.
- Registration binds contract hash, explicit 720 global IDs and hash, family ID/size,
  exact legal partition IDs/hash, exact regime, development/validation/embargo/sealed
  episode IDs/hash, split artifact, and dataset lineage.
- Unknown contract, wrong global IDs/hash, local family, illegal partition,
  duplicate/missing tested IDs, and registry hash mismatch fail closed.
- Corrected alpha remains `0.05 / 720`.
- Exact sign-test evidence requires at least 14 independent units before a public
  720-family run may be interpreted as `NO_STRATEGY`.

## Canary receipts

Consolidated receipt:

- path:
  `docs/evidence/REGIME-STATISTICAL-FAMILY-TRUST-BOUNDARY-01/canary-receipts.json`
- SHA-256:
  `8d9c583d251ec5c75a39f8812d9b5c78b9c36609b33e5c9325c3274bbde49b44`
- interval:
  `2026-07-27T11:09:55.740825+00:00` →
  `2026-07-27T11:10:03.346968+00:00`

Canary A:

- status: `PASS`
- public CLI tested count: 3
- result: `INSUFFICIENT_EVIDENCE`
- family reason: `INVALID_CORRECTION_FAMILY`
- duration: `1.075308s`

Canary B:

- status: `PASS`
- baseline / candidate scenario count: `81 / 81`
- shared global family size: `720`
- corrected alpha: `0.00006944444444444444`
- durations: baseline `1.110562s`, candidate `1.12105s`
- same experiment ID and registry record hash used for both invocations

Canary C:

- status: `PASS`
- coverage status: `PARTITION_COVERAGE_INCOMPLETE`
- profile counts: standard `81`, risk_guard `81`, long_horizon `81`, tight_exit `36`
- unique union: `242 / 720`
- missing: `478`
- cross-profile overlap: `32`
- policy: duplicates within one partition forbidden; cross-profile overlap counts once
  in union and never proves complete coverage

Canary D:

- status: `PASS`
- source: repo-existing features, rankings, and industry map; no download
- as-of history: rebuilt by the existing history builder from those inputs
- exact regime: `RISK_OFF|`
- episodes: available `13`; development `6`, validation `1`, embargo `5`, sealed `1`
- bounded inputs: `2` ranking files, `20` stocks, `708` derived feature rows
- actual maximum independent units: `2`
- required independent units under `0.05 / 720`: `14`
- statistical-unit gap: `12`
- result: `INSUFFICIENT_EVIDENCE`
- state trace:
  `PRE_REGISTRATION → COARSE_SCREEN → INSUFFICIENT_EVIDENCE`
- builder duration: `2.635739s`
- matrix duration: `1.424785s`

## Input and production hashes

- contract:
  `sha256:e81c0ca71f7b9e2e0f187ec17dac8de92509287c39b60e5ad6349074244dce16`
- existing features:
  `sha256:057177ae3348c023ab2994ccc97a82a7228386b776e9ae65c35f2b22662d88af`
- generated as-of history:
  `sha256:5952df7d542a15be5d8ed316028806ae15d08fbcd225b4dbaa9ea349d7309639`
- bounded feature subset:
  `sha256:f3b1b786afbd85eb6976f2419728f0ee5af8cac20811a56547de947ba9f63824`
- `models/latest_lgbm.pkl`:
  `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`
- `models/baseline_stats.json`:
  `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7`

Production hashes match the blocked Repair-2 evidence.

## Verification

- targeted: `39 passed`
- full suite: `525 passed`, `1 failed`, `246 subtests passed`
- only failure:
  `tests/test_research_component_ledger.py::ResearchComponentLedgerTest::test_verifier_accepts_generated_ledger`
- classification: existing baseline debt already reproduced and recorded in Repair-1/2;
  this successor does not modify the ledger test or its implementation paths
- `git diff --check`: pass

## New problems

1. `PARTITION_COVERAGE_INCOMPLETE`: current profiles cover only 242 of 720 unique
   combinations; 478 remain outside profile union.
2. `AVAILABLE_DATA_STATISTICAL_UNIT_GAP`: the bounded real-data run has 2 independent
   units versus the theoretical minimum 14; the next valid rerun condition is at least
   14 independent exact-regime episode trades under the unchanged family and alpha.
3. Legacy repo `market_regime_history_*.json` artifacts lack `as_of_date`; formal canary
   use requires rebuilding history from source features with the current as-of builder.
