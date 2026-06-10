# STRATEGY-COMPONENT-REGISTRY-01｜Initial Registry

## Root Question

現有研究成果能不能整理成「樂高零件庫」，讓後續策略不是每次從零開始亂湊。

## Scope

- 只讀既有 artifact / reference / config。
- 建立策略零件 registry。
- 每個零件記錄：
  - `component_id`
  - `category`
  - `status`
  - `evidence`
  - `where_it_helps`
  - `where_it_hurts`
  - `allowed_next_use`
  - `blocked_uses`
  - `metrics`
- 建立 verifier，防止把 reference / diagnostic / rejected 零件誤當正式 alpha。

## Non-Goals

- 不抓新資料。
- 不重訓模型。
- 不重跑 ranking。
- 不改 production ranking。
- 不改 Clawd 推播。
- 不做 promotion decision。

## Artifacts

- `artifacts/model_experiments/strategy_component_registry_YYYY-MM-DD.json`
- `artifacts/model_experiments/strategy_component_registry_YYYY-MM-DD.md`
- `artifacts/model_experiments/strategy_component_registry_verification_latest.json`

## Initial Components

| Component | Category | Status |
| --- | --- | --- |
| `candidate_ranking` | ranking_source | `CONDITIONAL_CANDIDATE` |
| `trail10` | exit_rule | `REUSABLE_CANDIDATE` |
| `overlap_first` | ranking_transform | `REJECTED` |
| `chip_flow` | risk_overlay | `DIAGNOSTIC_ONLY` |
| `fundamental_revenue` | feature_group | `DATA_UNAVAILABLE` |
| `industry_map` | data_source | `REFERENCE_AVAILABLE` |
| `concept_membership` | data_source | `REFERENCE_AVAILABLE` |
| `notification_bucket` | message_rule | `MESSAGE_AVAILABLE` |
| `market_regime_history` | regime_gate | `NEEDS_TEST` |
| `market_context` | data_source | `DIAGNOSTIC_ONLY` |

## Decision

```text
REGISTRY_READY
```

This is not a strategy by itself. It is the memory layer for future strategy composition.

Next mainline:

```text
conditional_switch_research_for_candidate_trail10
```

## Boundary

- `REFERENCE_AVAILABLE` 不等於 alpha validated。
- `DIAGNOSTIC_ONLY` 不可進 production ranking。
- `REJECTED` 不可被重新包裝成 publish ordering。
- `CONDITIONAL_CANDIDATE` 只能進條件式切換研究，不可無條件切正式。
