# FM0 License Boundary and Next-Card Admission

日期：2026-09-02
slice_id：`FM0-CONTRACT-ABSORPTION-01`
fixed source SHA：`35bb9927eb0eac9a624dcaf0dcffcbf88857c070`
狀態：`DOCS_ONLY / ADMISSION_DECISION`

## 1. License Boundary

Official donor evidence shows a split license boundary:

Official sources checked:

- Google Research Blog, "TimesFM-3: A zero-shot foundation model for multivariate forecasting", 2026-08-31: https://www.research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting/
- Google Research GitHub, `google-research/timesfm`: https://github.com/google-research/timesfm
- Hugging Face model card/license for `google/timesfm-3.0-pytorch`: https://huggingface.co/google/timesfm-3.0-pytorch and https://huggingface.co/google/timesfm-3.0-pytorch/blob/main/LICENSE

| Artifact class | Official status observed 2026-09-02 | FM0 disposition |
|---|---|---|
| TimesFM source repository | GitHub repo presents Apache-2.0 repository license and TimesFM 3.0 usage docs. | `REFERENCE_ONLY`; not a NEW-TOP10 authority. |
| TimesFM 2.5 and earlier weights | GitHub README says model weights up to 2.5 remain Apache-2.0. | Out of FM0 runtime scope; no download/inference. |
| TimesFM 3.0 pretrained weights | GitHub README and Hugging Face model card/license identify `timesfm-non-commercial-license-v1.0`; non-commercial/non-production restriction. | `DO_NOT_USE` for production; `NOT_ADMITTED` for shadow benchmark until separate prerequisites pass. |
| TimesFM outputs | License text distinguishes outputs from model derivatives, but usage remains constrained by non-commercial/non-production purpose. | Output usage policy must propagate model/checkpoint license status before any evaluation or downstream use. |

FM0 is not legal advice. It is an engineering admission boundary: without an explicit commercial/production license authority, TimesFM-3 cannot be used for production, paid, client, ranking, trading signal, or M4-M7 decision mutation.

## 2. Required License Propagation

Any future forecast receipt must preserve separated refs:

```yaml
license_receipt:
  source_code_license_ref: ...
  checkpoint_license_ref: ...
  inference_code_license_ref: ...
  output_usage_policy_ref: ...
  model_profile_ref: ...
  forecast_task_ref: ...
  effective_usage_status:
    - RESEARCH_ONLY
    - SHADOW_BENCHMARK_ONLY
    - NO_PRODUCTION_SIGNAL_EXPORT
    - NO_B_DECISION_CONSUMPTION
    - NO_M4_M5_M6_M7_MUTATION
```

If any license ref is unknown, absent, conflicting, or non-commercial/non-production while the requested use is production-like, execution must fail closed before model loading or inference.

## 3. TFM3-S1 Admission Prerequisites

`TFM3-S1 Restricted Shadow Benchmark` remains:

```text
REGISTERED
NOT_ADMITTED
NO_DOWNLOAD
NO_INFERENCE
NO_PRODUCTION
```

Minimum prerequisites before admission can be reconsidered:

1. Forecast Contract implementation card accepted and merged, including dataset bundle consumer, TrialSpec variant, receipt artifact refs and forecast observation projection.
2. License policy object can represent non-commercial/non-production restrictions and fail closed on production-like uses.
3. No code path exports forecast outputs to ranking, recommendation, M4-M7, Strategy Matrix, publication or external services.
4. Benchmark task uses local/synthetic or clearly licensed datasets with explicit `event_at/available_at/forecast_origin`.
5. Model acquisition plan is explicit and reviewed: no accidental checkpoint download during tests, imports, examples or CI.
6. Evaluation plan includes at least one non-TimesFM baseline, so the benchmark tests the contract and not a donor-specific adapter.
7. Storage/runtime footprint is bounded before any large checkpoint or artifact cache is created.
8. Output artifacts are quarantined as shadow evaluation only and cannot be consumed by B-layer without a separate promotion card.

## 4. Next-Card Decision

Decision: `GO_NEXT_CARD` for `P2 / FC1 Forecast Contract Implementation`.

Allowed next-card scope:

| Area | Allowed |
|---|---|
| Dataset Bundle | Add `FORECAST_SHADOW_V1 / forecast-shadow-dataset.v1` consumer and validator tests. |
| Temporal contract | Add `event_at / available_at / forecast_origin` availability manifest validation. |
| TrialSpec | Add forecast variant or thin forecast spec with shared content hash identity. |
| Receipt | Add schema-only or validator-only support for forecast artifact refs and license propagation. |
| Observation | Add separate forecast evaluation projection shape; no B-layer consumption. |

Forbidden next-card scope:

- no model download;
- no inference;
- no TimesFM adapter;
- no production ranking mutation;
- no queue/runner/capacity mutation;
- no #13/#14/BC-CP2 edits;
- no new DB/registry/canonical writer;
- no external write.

Recommended status:

```text
FC1 = PROPOSED / MAY_ADMIT_AFTER_MAINLINE_ACCEPTANCE
TFM3-S1 = HOLD / NOT_ADMITTED
```

## 5. why_not_less / why_not_more / do_not_absorb

### why_not_less

如果只記錄 license note，後續卡仍可能在沒有 dataset/time/output/receipt guard 的情況下載模型或把 outputs 混進 ranking evidence。License boundary 必須連到 execution profile、receipt artifacts 與 downstream usage policy。

### why_not_more

FM0 不需要實作 license engine、legal approval workflow、model registry、checkpoint scanner 或 commercial-license procurement。現階段只需讓下一卡有明確 fail-closed schema target。

### do_not_absorb

- 不把 TimesFM-3 checkpoint 納入 repo、CI、tests、artifacts 或 examples。
- 不把 non-commercial research benchmark視為 production readiness。
- 不把 TimesFM output 視為 B0/B-layer decision evidence。
- 不把 license receipt 變成第三套 authority；它只是 RunReceipt 的 usage evidence。

## 6. Final FM0 Verdict

```text
FM0 = COMPLETE / DOCS_ONLY
Forecast Contract implementation = GO_NEXT_CARD
TFM3-S1 Restricted Shadow Benchmark = HOLD / NOT_ADMITTED
Production use = NO_GO
External write = NOT_AUTHORIZED
```
