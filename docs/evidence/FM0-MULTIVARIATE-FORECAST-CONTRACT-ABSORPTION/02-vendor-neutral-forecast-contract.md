# FM0 Vendor-Neutral Forecast Contract

日期：2026-09-02
slice_id：`FM0-CONTRACT-ABSORPTION-01`
fixed source SHA：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
狀態：`DOCS_ONLY / CONTRACT_DRAFT / NOT_IMPLEMENTED`

## 1. Contract Purpose

本契約描述 NEW-TOP10 可以如何用現有 Research Spine 吸收多變量預測研究，但不指定 TimesFM、Chronos、Toto、LightGBM 或任何 vendor executor。它只定義 forecast task 的資料閉包、時間可見性、執行 profile、receipt artifacts 與 evaluation observation。

所有 generic 類別不得使用 `TimesFM*` 命名；TimesFM-3 僅為 donor evidence。

## 2. Proposed Identity Objects

### 2.1 ForecastTask

`ForecastTask` 是 forecast research 的 requested task identity，不是 model profile，也不是 strategy matrix scenario。

Required conceptual fields:

| Field | Meaning |
|---|---|
| `schema_version` | `forecast-task.v1` |
| `canonicalization_version` | `research-canonical-json.v1` |
| `task_id` | content hash over task payload |
| `forecast_origin` | 預測起點；所有 non-future-known input 必須滿足 `available_at <= forecast_origin` |
| `horizon` | ordered future target offsets or calendar dates |
| `context_window` | historical lookback policy |
| `target_channels` | ordered target channel refs |
| `covariate_channels` | ordered covariate channel refs |
| `calendar_policy_ref` | trading/calendar alignment policy hash/ref |
| `missingness_policy_ref` | missing handling policy hash/ref |
| `output_contract_ref` | expected point/quantile/output shape contract |
| `usage_policy_ref` | license/output usage boundary ref |
| `safety` | must preserve no production ranking mutation by default |

### 2.2 ModelProfile

`ModelProfile` is executor metadata, not task truth.

Required conceptual fields:

| Field | Meaning |
|---|---|
| `schema_version` | `forecast-model-profile.v1` |
| `profile_id` | content hash |
| `executor_family` | vendor-neutral id, e.g. `FOUNDATION_TS_ZERO_SHOT` or `LOCAL_BASELINE` |
| `implementation_ref` | source package/code ref if used |
| `checkpoint_ref` | checkpoint/model artifact ref, nullable for classical baseline |
| `license_ref` | source/checkpoint/license refs, separated by artifact class |
| `runtime_constraints` | CPU/GPU/memory/inference mode limits |
| `supported_outputs` | `point`, `quantile`, intervals |

`implementation_ref`、`checkpoint_ref`、`license_ref` 必須分離，因 TimesFM-3 類 donor 可能 source code 與 pretrained weights 採不同 license。

### 2.3 UsagePolicy

`UsagePolicy` controls where forecast outputs may flow.

Minimum statuses:

```text
RESEARCH_ONLY
SHADOW_BENCHMARK_ONLY
NO_PRODUCTION_SIGNAL_EXPORT
NO_B_DECISION_CONSUMPTION
NO_M4_M5_M6_M7_MUTATION
COMMERCIAL_OR_PRODUCTION_BLOCKED_BY_LICENSE
```

TimesFM-3 default usage policy must include every restrictive status above until a separate license authority says otherwise.

## 3. Dataset Bundle Extension

Existing A1 envelope should be reused as authority, but a new consumer is required:

```yaml
consumer_id: FORECAST_SHADOW_V1
contract_version: forecast-shadow-dataset.v1
```

Required forecast roles:

| Role | Purpose | Current seam decision |
|---|---|---|
| `TARGET_SERIES_MANIFEST` | ordered forecast target series and target shape | `NEW_VERSION_LATER` |
| `PAST_ONLY_COVARIATE_MANIFEST` | historical-only covariates; horizon values must be unavailable/masked | `NEW_VERSION_LATER` |
| `FUTURE_KNOWN_COVARIATE_MANIFEST` | covariates known at origin for future horizon | `NEW_VERSION_LATER` |
| `STATIC_COVARIATE_MANIFEST` | static per-series attributes | `NEW_VERSION_LATER` |
| `AVAILABILITY_MANIFEST` | per value or per source `event_at/available_at` proof | `NEW_VERSION_LATER` |
| `MISSINGNESS_MANIFEST` | missing/null/imputation masks and policy binding | `NEW_VERSION_LATER` |
| `CALENDAR_ALIGNMENT_MANIFEST` | target/covariate calendar, trading day and horizon alignment | `NEW_VERSION_LATER` |
| `SOURCE_COMPONENTS_MANIFEST` | optional bridge to existing features/events/fundamentals/universe artifacts | `WRAP` |

The dataset bundle identity must include ordered channel manifests. Sorting for canonical JSON may normalize object keys, but channel order must be represented by explicit integer `order_index` values and verified as contiguous and unique.

## 4. Temporal Availability Contract

Forecast data visibility must use three timestamps:

| Field | Definition |
|---|---|
| `event_at` | when the economic/market event belongs on the timeline |
| `available_at` | when the value became observable to the system |
| `forecast_origin` | the cut point from which the forecast is made |

Classification:

```text
target context:
  event_at <= forecast_origin
  available_at <= forecast_origin

target horizon:
  event_at > forecast_origin
  value unavailable or masked before execution

past-only covariate:
  event_at <= forecast_origin
  available_at <= forecast_origin

future-known covariate:
  event_at > forecast_origin
  available_at <= forecast_origin

forbidden leakage:
  available_at > forecast_origin and value is visible to executor
```

Existing M4 `fundamental_available_from` backward join is a usable pattern, not sufficient as-is. Forecast must preserve both `event_at` and `available_at` because future-known covariates intentionally have future `event_at` but past/current `available_at`.

## 5. TrialSpec Integration

Current `research-trial-spec.v1` can supply identity principles but not the forecast field shape.

Recommended next-card path:

```yaml
schema_version: research-trial-spec.v2
trial_variant: FORECAST_SHADOW
execution_profile:
  profile_kind: forecast-model-executor.v1
  forecast_task_ref: sha256:<forecast-task>
  model_profile_ref: sha256:<model-profile>
  usage_policy_ref: sha256:<usage-policy>
```

Alternative if v2 is too broad:

```yaml
schema_version: forecast-trial-spec.v1
canonicalization_version: research-canonical-json.v1
trial_spec_id: sha256:<content>
forecast_task_ref: sha256:<forecast-task>
dataset_bundle_ref: sha256:<forecast dataset bundle>
execution_profile_ref: sha256:<forecast-model-profile>
usage_policy_ref: sha256:<usage-policy>
safety: ...
```

FM0 does not choose between these; the next implementation card must make that decision with tests.

Forbidden integration:

- Do not put forecast `context_window`, `horizon`, `target_channels`, `covariates` into existing strategy `parameters`.
- Do not reuse `ranking_source_authority` as a fake forecast source.
- Do not claim current validator accepts forecast tasks.

## 6. RunReceipt Integration

Reuse:

- terminal status and terminal cause taxonomy;
- requested/executed split;
- dataset bundle binding;
- artifact CAS;
- identity match and resolution events;
- fail-closed lineage assertions.

Add in next card:

| Artifact | Required identity |
|---|---|
| `raw_point_forecast` | content hash, target channel IDs, horizon index, forecast origin |
| `raw_quantile_forecast` | content hash, quantile levels, target channel IDs, horizon index |
| `postprocessed_forecast` | optional, must bind preprocessing/postprocessing policy refs |
| `forecast_manifest` | ties task/profile/dataset/output artifacts together |
| `preprocessing_receipt` | transform policy and input/output hash binding |
| `postprocessing_receipt` | calibration, positivity, quantile crossing, clipping or rescaling policy |
| `license_receipt` | source/checkpoint/output usage policy propagation |

The existing `finish_topic_attempt()` strategy matrix receipt builder is `DO_NOT_USE` for forecast. A next card may add a thin forecast receipt builder that calls shared validators after the schema supports forecast units.

## 7. Forecast Evaluation Observation

Forecast evaluation must be a separate projection, not an extension of strategy observations.

Minimum metrics:

| Metric | Purpose |
|---|---|
| `MAE` | point forecast absolute error |
| `MASE` | scale-adjusted error against naive baseline |
| `QLIKE` | volatility/positive target use case if applicable |
| `pinball_loss` | quantile forecast quality |
| `interval_coverage` | probabilistic calibration |
| `interval_width` | sharpness |
| `baseline_delta` | comparison against declared baseline |

Minimum provenance:

- forecast task ID;
- executed forecast spec ID;
- dataset bundle ID;
- target channel IDs;
- forecast origin and horizon;
- model profile ID;
- usage policy ID;
- output artifact IDs;
- evaluation dataset/actuals authority;
- metric policy version.

Promotion rule:

```text
ForecastEvaluationObservation
  -> separate review/admission
  -> possible B-layer research evidence
```

Until then:

```text
NO_B_DECISION_CONSUMPTION
NO_M4/M5/M6/M7_MUTATION
NO_PRODUCTION_SIGNAL_EXPORT
```

## 8. Forecast Benchmark Matrix Boundary

Forecast benchmark matrix may compare executor/profile/task variants, but it is not B0 strategy matrix.

Allowed:

- compare forecast models against naive/statistical baselines;
- compare univariate vs multivariate inputs;
- compare covariate availability policies;
- evaluate point and probabilistic forecast metrics.

Forbidden:

- using B0 matrix count or candidate priority as forecast benchmark authority;
- promoting forecast benchmark winner into Strategy Matrix;
- modifying #13, #14, BC-CP2 or C0 runner/queue;
- using forecast metrics as direct ranking or trade signal.

## 9. Next-Card Acceptance Shape

A bounded implementation card may be admitted only if it remains:

```text
DOCS_AND_SCHEMA_ONLY or CONTRACT_PLUS_VALIDATOR_ONLY
NO_MODEL_DOWNLOAD
NO_INFERENCE
NO_PRODUCTION
NO_EXTERNAL_WRITE
NO_QUEUE_RUNNER_MUTATION
```

Required tests for that card:

- forecast dataset bundle validates ordered channel manifests;
- invalid channel order, duplicate channel IDs and missingness ambiguity fail closed;
- `available_at > forecast_origin` visible to executor fails closed;
- future-known covariates are allowed only when `available_at <= forecast_origin` and `event_at > forecast_origin`;
- TrialSpec variant rejects strategy-parameter pollution;
- receipt validates point/quantile artifact refs and license policy refs;
- forecast observations are not inserted into strategy observation tables.
