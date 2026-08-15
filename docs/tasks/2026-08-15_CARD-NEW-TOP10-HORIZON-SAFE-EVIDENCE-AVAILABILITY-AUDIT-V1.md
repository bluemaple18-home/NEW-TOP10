---
id: CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-AVAILABILITY-AUDIT-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: data-evidence-audit
priority: P1
owner: TOP10new research platform
role: implementation
cycle: 14
thickness: standard
risk: medium
model: gpt-5.6-terra
reasoning: medium
model_reason: 既有 NO-GO 已固定；本卡只做 bounded availability 診斷與 deterministic evidence，不改 runner、資料或 authority，採節省模式的平衡執行層。
date: 2026-08-15
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
canonical_queue_change_allowed: false
network_allowed: false
evidence_path: docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-AVAILABILITY-AUDIT-V1/
---

# Horizon-safe Evidence Availability Audit V1

## 工作名稱

盤點 horizon 10／20 exact-regime evidence 可用性。

## Root question

在不下載、不補造、不重跑 replay 的前提下，現有 committed／local development-only authority 是否存在至少兩個 `NARROW_LEADER|BIG_BULL` lineages，可安全形成 `horizon=10` 與 `20` 的 matched comparison？若沒有，最小且可稽核的缺口是什麼？

## 固定來源

- Baseline commit：本卡 source commit 的 parent `70ec5ad5fdcff7c3911dedfb6b176244c0679495`。
- Card D result：`docs/evidence/CARD-NEW-TOP10-ISOLATED-SHADOW-PLAN-REPLAY-V1/final_result.json`。
- Ranking roots：
  - `artifacts/backtest/historical_rankings_current_model/`
  - `artifacts/backtest/shadow_rankings_regime_guard_recent/`
- Feature source：`data/clean/features.parquet`。
- Regime authority：`artifacts/market_regime_history.json`。
- 判定 seam：`scripts/run_backtest_strategy_matrix.py::exact_horizon_safe_ranking_dates`。

## Ownership

### 允許修改

- 新增 bounded availability audit module／CLI（優先 `app/research/shadow_replay_availability.py`）。
- 對應 targeted tests。
- `docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-AVAILABILITY-AUDIT-V1/`。

### 禁止修改

- 既有 ranking、feature、regime、proposal、Card D evidence。
- `artifacts/autonomous_research/next_action_queue.json` 與任何 canonical queue／manager state。
- Runner、batch owner、scheduler、launchd、daily quota。
- Production model、ranking、signals、promotion。
- 網路下載、資料回填、synthetic ranking／regime／lineage。
- 執行 Card D replay、strategy matrix或 comparison command。
- 使用者既有 dirty files與 `.work/**`。

## Slices

### `HSEA-001`｜Authority inventory

- `traces_to`: `ISR-FR-002`, `ISR-FR-005`
- 唯讀列出兩個 ranking roots、regime authority與 feature date coverage的可解析日期、hash、缺檔與衝突。
- 不以檔名或 mtime 單獨證明 regime／lineage。

### `HSEA-002`｜Horizon-safe intersection

- `blocked_by`: `HSEA-001`
- `traces_to`: `ISR-FR-002`, `ISR-FR-005`
- 重用正式 `exact_horizon_safe_ranking_dates` 判定語意或同一 canonical helper；不得建立第二套 horizon 安全算法。
- 產出每個 ranking root × horizon `{10,20}` 的候選日期、排除理由與 exact-regime authority。
- 明確計算是否存在兩個獨立、同條件、`PROVEN_NON_SEALED` lineages。

### `HSEA-003`｜Deterministic verdict

- `blocked_by`: `HSEA-002`
- `traces_to`: `ISR-FR-004`, `ISR-FR-005`
- 產出 canonical JSON audit與 verifier；二跑 byte-identical（generated timestamp不得進 identity body）。
- Verdict 只允許：
  - `GO_REPLAY_INPUTS_AVAILABLE`
  - `NO-GO_EVIDENCE_UNAVAILABLE`
  - `BLOCKED_AUTHORITY_CONFLICT`
- `NO-GO` 必須指出最小缺口：缺 ranking date、forward horizon、exact regime、lineage authority、non-sealed authority或跨 root matched intersection。

## Acceptance

- 不執行 replay／matrix／comparison，不新增或修改任何 source data。
- Availability matrix可由固定 inputs重算；每個日期包含 accepted／excluded與 structured reason codes。
- 不把 `horizon=20` 可用誤當 `horizon=10` 可用；不把15個 allowed dates誤當 horizon-safe。
- External path、traversal、symlink escape、hash／authority drift皆 fail closed。
- Canonical queue、scheduler、production及所有固定來源 pre/post hash一致。
- Targeted pytest、CLI verifier、`py_compile`、JSON validation、`git diff --check`通過。
- 交付單一 candidate commit與完整 SHA；不得宣稱 accepted、integrated或 live。

## Stop conditions

- 需要下載、補資料、修改 regime authority或放寬 exact-regime gate：`BLOCKED_SCOPE_VIOLATION`。
- Canonical helper無法唯讀重用且需改 runner contract：交付 `BLOCKED_RUNNER_CONTRACT`，不得順手修 runner。
- 現有 evidence不足：合法交付 `NO-GO_EVIDENCE_UNAVAILABLE`，並附可重現缺口矩陣。

## Verification

```bash
uv run pytest -q tests/test_shadow_replay_availability.py
uv run python -m app.research.shadow_replay_availability --verify docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-AVAILABILITY-AUDIT-V1/availability_audit.json
uv run python -m py_compile app/research/shadow_replay_availability.py tests/test_shadow_replay_availability.py
jq empty docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-AVAILABILITY-AUDIT-V1/*.json
git diff --check
```
