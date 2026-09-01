# FM0 Existing Seam Map and Absorption Boundary

日期：2026-09-02
slice_id：`FM0-CONTRACT-ABSORPTION-01`
fixed source SHA：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
狀態：`DOCS_ONLY / RESEARCH_ONLY / NO_RUNTIME_MUTATION`

## 1. Root Question

NEW-TOP10 是否能在不改 #13／#14、BC-CP2、M4-M7、queue／runner、production ranking 的前提下，把 multivariate forecasting 需要的資料、執行、receipt 與 observation 契約吸收到現有 Research Spine。

本份 evidence 的答案是：可以吸收，但只能作為 vendor-neutral forecast contract 的下一張實作卡；不能把現有 strategy-specific seams 誤判為 forecast-ready，也不能把 TimesFM-3 升為 authority、runtime dependency 或 subsystem。

## 2. Evidence Base

### 2.1 Repo Anchors

| Area | Fixed anchor | 現況 |
|---|---:|---|
| Research Spine backlog | `docs/RESEARCH_SPINE_BACKLOG.md:147-157`, `:204-209`, `:245-278`, `:340-366` | canonical truth 是 immutable spec/intent/attempt/receipt/artifact；Observation/Eligibility/Learning 是 rebuildable projections；B0/C0 Phase 2 尚未 admission。 |
| Dataset Bundle | `app/research/dataset_bundle.py:19-58`, `:60-138`, `:281-360` | `research-dataset-bundle.v1` 是 consumer-scoped identity，但 consumer matrix 只列 M4 training/ranking 與 strategy matrix features。 |
| TrialSpec | `app/research/contracts.py:281-321` | `research-trial-spec.v1` 欄位固定，`parameters` 必須等於 strategy canonical parameter set，`dataset_authority.dataset_hash` 與 `ranking_source_authority.ranking_source_hash` 仍是必填。 |
| Intent / Attempt | `app/research/contracts.py:324-382` | 已能 pre-bind requested dataset bundle id/ref，但 shape 仍以 requested trial IDs 為核心。 |
| RunReceipt | `app/research/contracts.py:638-860`, `app/research/run_receipts.py:128-213`, `:620-760` | receipt 已能保存 requested/executed truth、bundle binding、artifacts、lineage；目前 artifact resolver 與 executed unit shape 綁 strategy matrix result。 |
| Feature as-of | `app/modeling/feature_contract.py:101-153`, `:248-345` | M4 有基本面 as-of join：`available_from/published_at/as_of_date` 只 backward join 到 trade date；缺值保留。 |
| Observation / Eligibility | `app/research/observation_ingest.py:1-160`, `app/research/eligibility.py:1-160` | Observation 是 receipt/executed unit/result artifact 的 derived fact；Eligibility 是 versioned projection，且只決定 evidence 能否下游學習。 |
| Strategy matrix | `scripts/run_backtest_strategy_matrix.py`, `scripts/compare_strategy_matrices.py`, `docs/tasks/2026-05-29_BACKTEST-09_strategy_matrix.md` | 現有 matrix 是策略回測矩陣，不是 forecast benchmark matrix。 |

### 2.2 Official Donor Facts

官方 Google Research 於 2026-08-31 發布 TimesFM-3，描述其支援 multivariate forecasting、multiple targets、past covariates、past-future dynamic covariates、single-pass horizon decode 與 10th-90th quantile forecasts。官方 GitHub README 同步標示 Latest Model Version 為 TimesFM 3.0，且 pretrained 3.0 weights 使用 `timesfm-non-commercial-license-v1.0`，限制 non-commercial/non-production use。Hugging Face model card/license 也標示 `google/timesfm-3.0-pytorch` 的 license 為 `timesfm-non-commercial-license-v1.0`。

Sources:

- Google Research Blog, "TimesFM-3: A zero-shot foundation model for multivariate forecasting", 2026-08-31: https://www.research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting/
- Google Research GitHub, `google-research/timesfm`, README lines showing TimesFM 3.0 checkpoint/latest version/license notice: https://github.com/google-research/timesfm
- Hugging Face, `google/timesfm-3.0-pytorch`, model card and LICENSE: https://huggingface.co/google/timesfm-3.0-pytorch and https://huggingface.co/google/timesfm-3.0-pytorch/blob/main/LICENSE

## 3. Seam Decisions

| Seam | Decision | Why |
|---|---|---|
| Canonical JSON / content hash | `USE_AS_AUTHORITY` | Existing `research-canonical-json.v1` and `content_hash()` already provide path-independent identity; forecast contract should reuse this authority. |
| Dataset Bundle envelope | `USE_AS_AUTHORITY` | Existing envelope and component identity model are sufficient for a forecast dataset closure. |
| Dataset Bundle consumer matrix | `NEW_VERSION_LATER` | Current `_CONSUMER_MATRIX` has no forecast consumer and only supports singleton `member_key=primary`; forecast needs ordered multi-channel targets/covariates and availability manifests. |
| Existing component roles | `WRAP` | `FEATURES_ARTIFACT`, `EVENTS_ARTIFACT`, `FUNDAMENTALS_SNAPSHOT`, `UNIVERSE_ARTIFACT` can be input sources, but forecast task needs roles that expose temporal/channel semantics. |
| Fundamentals as-of logic | `WRAP` | Existing backward as-of join proves the leakage guard pattern, but forecast needs explicit `event_at / available_at / forecast_origin` classification. |
| TrialSpec identity | `USE_AS_AUTHORITY` | The content-hash identity and requested/executed split are reusable. |
| Current TrialSpec schema | `NEW_VERSION_LATER` | Existing `parameters` must equal strategy parameter set; forecast needs horizon/context/channel/task metadata without polluting strategy matrix params. |
| ExecutionIntent / AttemptStarted | `ADAPT_LATER` | Existing pre-bind of trial IDs and dataset bundle ref should be preserved, but forecast attempt needs a forecast task ref and executor profile shape. |
| RunReceipt identity / terminal taxonomy | `USE_AS_AUTHORITY` | Existing terminal receipt authority, terminal cause, bundle binding, and artifact CAS are reusable. |
| Current strategy receipt builder | `DO_NOT_USE` | `finish_topic_attempt()` resolves strategy matrix artifacts and scenario rows; it cannot be called forecast-ready. |
| Artifacts CAS | `USE_AS_IS` | Immutable artifact capture is compatible with raw point forecast, quantile forecast and manifest artifacts. |
| Observation derivation principle | `USE_AS_AUTHORITY` | Observation must remain derived from executed receipt + result artifact + executed spec correlation. |
| Current strategy Observation schema | `NEW_VERSION_LATER` | Existing metrics are return/drawdown/win-rate/trade-count/score; forecast needs MAE/MASE/QLIKE/pinball/coverage/width/baseline delta. |
| Eligibility projection principle | `USE_AS_AUTHORITY` | Versioned, fail-closed eligibility is reusable. |
| Current Eligibility policy | `ADAPT_LATER` | It assumes strategy observations and adaptive learning gates; forecast evaluation must remain separately gated. |
| B0 strategy matrix | `DO_NOT_USE` | Forecast benchmark matrix must not consume or modify #13 B0 strategy matrix authority. |
| C0 runner / queue inventory | `DO_NOT_USE` | FM0 does not authorize queue/runner/capacity mutation or C0 Phase 2. |
| TimesFM source code | `DO_NOT_USE` for authority, `REFERENCE_ONLY` as donor evidence | Source may inform contract risk, but generic classes must not use `TimesFM*` names. |
| TimesFM-3 checkpoint | `DO_NOT_USE` | Non-commercial/non-production license and task card forbid download/inference. |

## 4. Minimum Sufficient Absorption Boundary

### why_not_less

只登記一張 TimesFM 卡或只在 TrialSpec 放 `model_name` 不足以防止資料洩漏、channel order drift、license contamination、point/quantile artifact ambiguity，也無法證明 forecast output 沒被混入 B0 strategy evidence。

最小需要固定五個接點：

1. Forecast dataset consumer contract。
2. Forecast task/profile identity。
3. Forecast execution-profile reference。
4. Forecast artifacts in RunReceipt。
5. Forecast evaluation observation projection。

### why_not_more

現有 Research Spine 已提供 canonical JSON、dataset bundle envelope、TrialSpec identity、Intent/Attempt/Receipt lifecycle、artifact CAS、Observation/Eligibility projection pattern。FM0 不需要新 DB、registry、ledger、runtime、queue、adapter、model loader、schema implementation 或 production gate。

### do_not_absorb

- 不吸收 TimesFM naming into generic contract。
- 不吸收 TimesFM-3 checkpoint、weights、inference code 或 notebook。
- 不吸收 BigQuery/Vertex/Google Sheets integration。
- 不吸收 B0 strategy matrix、#13、#14、BC-CP2 或 C0 queue/runner mutation。
- 不吸收 M4-M7 production decision chain。
- 不建立第二套 authority、registry、database 或 canonical writer。

## 5. Gap Summary

| Gap | Severity for forecast | Required next action |
|---|---|---|
| No forecast consumer in dataset bundle matrix | Blocking | Add `FORECAST_SHADOW_V1 / forecast-shadow-dataset.v1` in a separate implementation card. |
| No ordered channel manifest | Blocking | Define `channel_id`, `role`, `order_index`, `series_binding`, `calendar_alignment`, `availability_class`. |
| No explicit `event_at/available_at/forecast_origin` contract | Blocking | Wrap M4 as-of semantics into forecast temporal availability rules. |
| TrialSpec parameter validator is strategy-only | Blocking | Add forecast TrialSpec variant or thin `forecast-trial-spec.v1`. |
| Receipt builder validates strategy matrix artifacts only | Blocking | Add forecast receipt builder after contract implementation. |
| Observation/Eligibility metrics are strategy-only | Blocking | Add separate forecast evaluation projection and keep promotion to B-layer blocked. |
| TimesFM-3 license is non-commercial/non-production | Blocking for production | Keep TFM3-S1 `NOT_ADMITTED / NO_DOWNLOAD / NO_INFERENCE / NO_PRODUCTION`. |

## 6. FM0 Decision

`GO_NEXT_CARD` for a bounded Forecast Contract implementation card.

`HOLD` for TFM3-S1. It remains `REGISTERED / NOT_ADMITTED / NO_DOWNLOAD / NO_INFERENCE / NO_PRODUCTION`.
