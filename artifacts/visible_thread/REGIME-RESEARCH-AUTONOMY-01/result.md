# REGIME-RESEARCH-AUTONOMY-01 Result

- status: `DELIVERED_CANDIDATE`
- review_required: `true`
- merge_allowed: `false`
- push_performed: `false`
- deploy_performed: `false`
- production_promotion_allowed: `false`
- candidate_sha: see `candidate_sha.txt` written after the candidate commit

## Current Regime → Topic

Closed mode reads `market-regime-history.v2` and requires every row to carry
`as_of_date == trade_date`. The manager selects the latest row not later than the requested
research date, records exact `base_regime + sorted family_tags`, and refuses
`UNKNOWN`／transition context. Topic priority is a deterministic product of relevance,
evidence gap, information gain, product value and feasibility divided by compute cost.
The topic also records why it was selected, its coverage gap and estimated combinations
resolved on either success or failure.

## Exact-match Historical Episodes

History rows are admitted only when base regime and the complete family tag set both match.
Base-only match, different tags, transition rows and `UNKNOWN` are excluded from formal
metrics. Consecutive exact identities become deterministic episodes. Development,
validation, embargo and sealed splits consume complete episodes; embargo trade days must
cover the label horizon and an episode cannot cross splits.

## Split Contamination

Pre-registration freezes research question, baseline, regime, dataset hash, split ID,
parameter-space hash, metric-policy hash and sealed episode IDs. Experiment ID is derived
from the immutable payload. The JSONL registry is append-only; any previously used sealed
episode is rejected with its source experiment ID.

## Cross-experiment Composition

Combining components from more than one experiment requires a fresh composition experiment
ID and fresh sealed episodes. Reusing an old source ID or used sealed data is rejected before
validation. Funnel transitions are also append-only and cannot skip stages.

## Parameter Universe and Coverage

The machine-readable inventory proves the four dimensions currently executable by the
existing matrix:

- horizon: 4 values
- stop loss: 6 values
- take profit: 6 values
- group exposure: 5 values

This yields 720 deterministic legal combination IDs and a reproducible parameter-space
hash. It is deliberately marked `PARTIAL_BLOCKED_SOURCE_UNKNOWN`; the unproven
two-million-level universe is not guessed. Coverage counts only legal combination IDs and
reports processed, pending, blocked, insufficient and passed state by exact regime.

## Insufficient Evidence and NO_STRATEGY

Insufficient samples return `INSUFFICIENT_EVIDENCE`; a fully evaluated round with no passing
candidate returns `NO_STRATEGY`. Raw best score is diagnostic-only in closed mode.
Bonferroni correction, stable neighboring parameters and drawdown control must all pass
before a candidate may advance.

## Universal Gate

The gate requires a proven-complete parameter universe, closed per-regime coverage, no
remaining high-value region, frozen parameters, independent fresh sealed OOS by regime and
no failure in any sufficiently sampled regime. Full-period average cannot mask a failed
regime. Because the full parameter source is not yet proven, this candidate keeps universal
research locked.

## Production No-change

The verifier restricts changed paths to this card's allowlist and confirms the production
model hashes are unchanged. No formal ranking, score weight, model, push, deploy or promotion
state was modified.

## Remaining Risks

1. This isolated worktree has no representative `features.parquet` or historical ranking
   CSVs, so exact-match runtime replay still needs controlled real-data evidence.
2. The two-million-level full parameter inventory source remains unknown; only the existing
   executable four-dimensional 720-combination space is proven.
3. Existing matrix outputs do not yet provide candidate p-values and neighbor-stability
   evidence; closed mode therefore conservatively returns `NO_STRATEGY` instead of advancing.
4. The full suite retains one baseline provisioning failure because historical ledger
   evidence files are absent; the same failure reproduces on pure `7efda43`.
