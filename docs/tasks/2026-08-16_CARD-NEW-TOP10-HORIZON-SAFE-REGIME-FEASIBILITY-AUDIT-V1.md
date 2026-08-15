---
id: CARD-NEW-TOP10-HORIZON-SAFE-REGIME-FEASIBILITY-AUDIT-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: data-evidence-audit
priority: P1
owner: TOP10new research platform
role: implementation
cycle: 16
thickness: standard
risk: medium
model: gpt-5.6-terra
reasoning: medium
model_reason: 現有證據已證明固定 scope 最長 episode 僅 3 個交易日；本卡只做 deterministic feasibility audit，不改模型、不跑 replay，採節省模式 Terra medium。
date: 2026-08-16
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
canonical_queue_change_allowed: false
network_allowed: false
evidence_path: docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-REGIME-FEASIBILITY-AUDIT-V1/
---

# Horizon-safe Regime Feasibility Audit V1

## 工作名稱

盤點現有 immutable regime authority 是否存在可承載 h10／h20 的 exact-regime scope。

## Root question

在不下載、不改 regime 定義、不放寬 horizon gate、不 materialize ranking、不執行 replay 的前提下，現有 committed market-regime 與 feature trade-date authority 中，是否存在至少一個 exact-regime episode 可完整承載 entry delay 1 加 h10／h20 holding window，並可作為下一階段合法 scope decision 的依據？

## 固定事實

- Coverage plan：`docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-COVERAGE-PLAN-V1/coverage_plan.json`。
- 目前 status：`NO-GO_PLAN_UNAVAILABLE`；reason：`NO_SHARED_HORIZON_SAFE_EXACT_REGIME_DATE`。
- 固定 scope `NARROW_LEADER|BIG_BULL` 的 10 個 immutable episodes 長度為 1～3 個交易日，無法承載 h10／h20。
- Canonical horizon seam：`scripts/run_backtest_strategy_matrix.py::exact_horizon_safe_ranking_dates`。
- 本卡只回答 feasibility；不得自行改選 production scope 或宣稱 lineage 已證明。

## Ownership

### 允許修改

- 新增 `app/research/shadow_replay_regime_feasibility.py`。
- 新增 `tests/test_shadow_replay_regime_feasibility.py`。
- 新增 `docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-REGIME-FEASIBILITY-AUDIT-V1/`。

### 禁止修改

- 所有既有 evidence、ranking、feature、regime、model、config、universe、industry map。
- Canonical queue、manager state、runner、scheduler、launchd、daily quota。
- Production model、ranking、signals、promotion。
- 網路、下載、資料回填、synthetic authority。
- 執行 materializer、strategy matrix、comparison或 replay。
- 使用者既有 dirty files與 `.work/**`。

## Requirements

- `HSRF-FR-001`：只讀綁定 coverage plan、market regime、features與 canonical helper 的 committed hash；任何 drift fail closed。
- `HSRF-FR-002`：依 canonical regime identity 與 episode builder 列出全部 exact-regime episodes，不接受手工合併、alias 或跨 episode window。
- `HSRF-FR-003`：重用 canonical horizon helper，對每個 identity 分別計算 h10、h20 safe ranking dates 與 shared dates。
- `HSRF-FR-004`：輸出 deterministic canonical JSON，明列 episode 長度、safe dates、shared dates、可行 identity 與固定 scope 的不可行證據。
- `HSRF-FR-005`：只輸出 scope-decision input；不得自動選定新 production scope、materialize ranking或將 feasibility 寫成 replay proof。

## Slices

### `HSRF-001`｜Authority inventory

- `traces_to`: `HSRF-FR-001`, `HSRF-FR-002`
- 驗證 committed inputs與 coverage-plan identity。
- 以 canonical builder 建 episode inventory；identity、episode ID、交易日範圍與長度排序固定。

### `HSRF-002`｜Canonical feasibility matrix

- `blocked_by`: `HSRF-001`
- `traces_to`: `HSRF-FR-003`, `HSRF-FR-004`
- 對每個 identity 重用 canonical helper計算 h10／h20。
- shared date 必須在同一 immutable episode 內完整承載 ranking、entry與 holding window。

### `HSRF-003`｜Decision artifact與 verifier

- `blocked_by`: `HSRF-002`
- `traces_to`: `HSRF-FR-004`, `HSRF-FR-005`
- Status只允許 `READY_FOR_SCOPE_DECISION`、`NO-GO_NO_ELIGIBLE_REGIME`、`BLOCKED_AUTHORITY_CONFLICT`。
- 產出 byte-deterministic JSON與獨立 verify mode；不得含 absolute path、mtime或生成時間。

## Acceptance

- 固定 scope `NARROW_LEADER|BIG_BULL` 明列最大 episode 長度與 h10／h20 shared date 空集合。
- 每個 feasible identity 必須至少有一個同時通過 h10／h20的 shared date；排序 deterministic。
- 若無 identity 可行，合法交付 `NO-GO_NO_ELIGIBLE_REGIME`，不得改 gate 或捏造資料。
- `lineage_authority_status`只能為 `UNPROVEN`。
- Evidence二跑 byte-identical；fixed inputs與 protected surfaces pre/post hash一致。
- Targeted pytest、CLI verifier、`py_compile`、JSON validation、`git diff --check`通過。
- 單一 candidate commit；不得 merge、push、deploy或宣稱 integrated。

## Stop conditions

- 需要下載、改 regime identity、改 episode builder、放寬 exact-regime／horizon gate：`BLOCKED_SCOPE_VIOLATION`。
- Canonical helper無法唯讀重用：`BLOCKED_RUNNER_CONTRACT`。
- Committed authority或 coverage plan drift：`BLOCKED_AUTHORITY_CONFLICT`。

## Verification

```bash
uv run pytest -q tests/test_shadow_replay_regime_feasibility.py tests/test_shadow_replay_coverage_plan.py
uv run python -m app.research.shadow_replay_regime_feasibility --verify docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-REGIME-FEASIBILITY-AUDIT-V1/feasibility_audit.json
uv run python -m py_compile app/research/shadow_replay_regime_feasibility.py tests/test_shadow_replay_regime_feasibility.py
jq empty docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-REGIME-FEASIBILITY-AUDIT-V1/*.json
git diff --check
```
