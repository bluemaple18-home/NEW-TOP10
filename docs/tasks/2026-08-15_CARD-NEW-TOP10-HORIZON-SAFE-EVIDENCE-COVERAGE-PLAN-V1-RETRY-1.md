---
id: CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-COVERAGE-PLAN-V1-RETRY-1
supersedes: CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-COVERAGE-PLAN-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: data-evidence-plan
priority: P1
owner: TOP10new research platform
role: implementation
cycle: 15
thickness: standard
risk: medium
model: gpt-5.6-terra
reasoning: medium
model_reason: 原 create endpoint 無回應且未產生 formal thread／worktree；同 scope retry，只產生 deterministic plan，採節省模式 Terra medium。
date: 2026-08-15
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
canonical_queue_change_allowed: false
network_allowed: false
evidence_path: docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-COVERAGE-PLAN-V1/
---

# Horizon-safe Evidence Coverage Plan V1

## 工作名稱

建立 exact-regime ranking authority 補齊計畫。

## Root question

現有本機 committed authority 能否在不下載、不改 production、不執行 replay 的前提下，規劃最小的一組 baseline／candidate ranking materialization，使同一 `NARROW_LEADER|BIG_BULL` 日期同時符合 horizon 10／20，並為後續兩條 `PROVEN_NON_SEALED` lineage 提供合法輸入？

## 固定事實

- Card E audit：`docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-AVAILABILITY-AUDIT-V1/availability_audit.json`。
- 目前 verdict：`NO-GO_EVIDENCE_UNAVAILABLE`。
- exact-regime allowed dates：15；現有 baseline／candidate ranking 各25日，但 matched intersection於 horizon 10／20皆為空。
- 缺口：`MISSING_LINEAGE_AUTHORITY`、`MISSING_NON_SEALED_AUTHORITY`、`MISSING_CROSS_ROOT_MATCHED_INTERSECTION`。
- Canonical horizon seam：`scripts/run_backtest_strategy_matrix.py::exact_horizon_safe_ranking_dates`。
- Baseline materializer：`scripts/build_historical_ranking_replay_set.py`。
- Candidate materializer：`scripts/research_regime_shadow_ranking.py`。

## Ownership

### 允許修改

- 新增 `app/research/shadow_replay_coverage_plan.py`。
- 新增 `tests/test_shadow_replay_coverage_plan.py`。
- 新增 `docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-COVERAGE-PLAN-V1/`。

### 禁止修改

- Card E audit與Card D evidence。
- 任何既有 ranking、feature、regime、model、config、universe或industry map。
- `artifacts/backtest/historical_rankings_current_model/`。
- `artifacts/backtest/shadow_rankings_regime_guard_recent/`。
- Canonical queue、manager state、runner、scheduler、launchd、daily quota。
- Production model、ranking、signals、promotion。
- 網路、下載、資料回填、synthetic authority。
- 執行 materializer、strategy matrix、comparison或Card D replay。
- 使用者既有 dirty files與 `.work/**`。

## Requirements

- `HSECP-FR-001`：只讀重算 Card E audit identity與固定 source hashes；drift或非 `NO-GO_EVIDENCE_UNAVAILABLE` fail closed。
- `HSECP-FR-002`：重用 canonical horizon helper，從 exact-regime allowed dates選出同時可承載 horizon 10／20的最小 shared date set。
- `HSECP-FR-003`：逐一驗證 baseline materializer與candidate materializer的 committed input authority、hash、日期涵蓋及 output collision。
- `HSECP-FR-004`：輸出 plan-only canonical JSON；argv只可使用repo-relative path與固定 bounded dates，不得執行。
- `HSECP-FR-005`：不得把「可 materialize」寫成「lineage已證明」；後者只能由後續正式 replay evidence證明。

## Slices

### `HSECP-001`｜Shared date selection

- `traces_to`: `HSECP-FR-001`, `HSECP-FR-002`
- 驗證 Card E audit與authority drift。
- 候選日期必須同時屬於 exact-regime allowed dates，且 canonical helper對 horizon 10與20均接受。
- Deterministic選擇最小 shared set；同分時依日期字串排序。

### `HSECP-002`｜Materialization authority contract

- `blocked_by`: `HSECP-001`
- `traces_to`: `HSECP-FR-003`, `HSECP-FR-005`
- Baseline至少綁定 features、universe、model、signals config與materializer source hashes。
- Candidate至少綁定planned baseline ranking、regime history、industry map與materializer source hashes。
- 目標 ranking檔若已存在、source缺失、symlink、path escape或hash drift，plan必須 fail closed。

### `HSECP-003`｜Canonical plan與verifier

- `blocked_by`: `HSECP-002`
- `traces_to`: `HSECP-FR-004`, `HSECP-FR-005`
- 產出 byte-deterministic JSON與獨立 verify mode。
- Status只允許 `READY_FOR_MATERIALIZATION`、`NO-GO_PLAN_UNAVAILABLE`、`BLOCKED_AUTHORITY_CONFLICT`。
- Plan明列下一卡預期新增的 exact ranking paths、兩段 bounded argv、source hashes、selected dates、horizons與尚未證明的 lineage gates。

## Acceptance

- 至少一個 shared date同時通過 horizon 10／20，否則合法交付 `NO-GO_PLAN_UNAVAILABLE`與最小缺口。
- Plan只描述新增缺失 ranking檔；不得覆寫現有檔案。
- `lineage_authority_status`與`non_sealed_authority_status`在本卡只能是 `PENDING_MATERIALIZATION_AND_REPLAY`。
- Canonical JSON二跑 byte-identical；不得含 absolute path、mtime或generated timestamp。
- Card E、固定 inputs、canonical queue、scheduler與production pre/post hash一致。
- Targeted pytest、CLI verifier、`py_compile`、JSON validation、`git diff --check`通過。
- 單一 candidate commit；不得 merge、push、deploy或宣稱 integrated。

## Stop conditions

- 需要新增資料來源、下載、改模型／signals、放寬 exact-regime或horizon gate：`BLOCKED_SCOPE_VIOLATION`。
- Canonical helper無法唯讀重用：`BLOCKED_RUNNER_CONTRACT`。
- 找不到不覆寫既有檔案的 shared date：`NO-GO_PLAN_UNAVAILABLE`。

## Verification

```bash
uv run pytest -q tests/test_shadow_replay_coverage_plan.py
uv run python -m app.research.shadow_replay_coverage_plan --verify docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-COVERAGE-PLAN-V1/coverage_plan.json
uv run python -m py_compile app/research/shadow_replay_coverage_plan.py tests/test_shadow_replay_coverage_plan.py
jq empty docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-COVERAGE-PLAN-V1/*.json
git diff --check
```
