---
id: CARD-NEW-TOP10-SHADOW-RESEARCH-PLAN-PROPOSAL-V1-RETRY-2
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: implementation
priority: P1
owner: TOP10new research platform
role: implementation
cycle: 12
thickness: standard
risk: medium
model: gpt-5.6-terra
reasoning: medium
model_reason: 將已核准 shadow priority 轉為 deterministic proposal-only artifact；不執行、不改 canonical queue。
date: 2026-08-15
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
canonical_queue_change_allowed: false
evidence_path: docs/evidence/CARD-NEW-TOP10-SHADOW-RESEARCH-PLAN-PROPOSAL-V1/
---

# 建立 Shadow Research Plan Proposal

## 工作名稱

把 Card B 的 HIGH shadow action 轉成可稽核、不可執行的研究計畫提案。

## Root question

能否依已提交的 shadow projection、policy 與 parameter catalog，產出 deterministic、catalog-adjacent 的 proposal，而不寫入 canonical queue 或觸發任何研究執行？

## 已核准來源

- Source commit：`031d1a5`
- `docs/evidence/CARD-NEW-TOP10-ADAPTIVE-SHADOW-QUEUE-V1-RETRY-1/adaptive_shadow_queue_projection.json`
- `config/research_shadow_queue_policy_v1.json`
- `config/research_parameter_catalog.json`
- 目前 HIGH row：`horizon / HIGHER_LOOKS_BETTER / RESEARCH_PARAMETER_EXTENSION_UPWARD`，scope 限 `NARROW_LEADER|BIG_BULL`。

## Ownership

### 允許修改

- `app/research/` 內本卡 proposal schema、builder、verifier。
- `scripts/build_shadow_research_plan_proposal.py`、`scripts/verify_shadow_research_plan_proposal.py` 或等價 bounded CLI。
- 對應 targeted tests。
- `docs/evidence/CARD-NEW-TOP10-SHADOW-RESEARCH-PLAN-PROPOSAL-V1/`。

### 禁止修改

- `artifacts/autonomous_research/next_action_queue.json`、existing manager selection／ordering／quota／rerun／cooldown。
- Parameter catalog、shadow queue policy、Card B committed projection。
- Runner、transaction、publish、scheduler、launchd、背景服務。
- Production model、ranking、signals、promotion、LightGBM、Optuna、dynamic refinement。
- 使用者既有 dirty files與既有 `.work/**`。

## Functional contracts

### `SRP-FR-001`｜Authoritative admission

- 只接受 repo 內已提交的 Card B projection、policy與parameter catalog。
- 驗證來源 identity、semantic hash、policy版本與catalog內容；stale、tampered、external path一律 fail closed。
- 只接受 `HIGH` 且 action=`RESEARCH_PARAMETER_EXTENSION_UPWARD` 的 row。

### `SRP-FR-002`｜Catalog-adjacent proposal

- 提案必含 source projection/row/semantic action identity、scope、parameter、direction、current value、proposed next value、catalog bounds、reason codes與provenance。
- next value只能是 catalog 中緊鄰且向上的合法值；不得插值、外插、改權重或擴大scope。
- 無合法相鄰值時輸出 structured `NO-GO_NO_ADJACENT_VALUE`，不得猜測。

### `SRP-FR-003`｜Deterministic identity

- 相同輸入必須產生相同 proposal ID、semantic hash、排序與bytes。
- 時間戳不得進 identity；duplicate semantic proposal須dedupe；同identity異body須 collision/fail closed。

### `SRP-FR-004`｜Proposal-only boundary

- 產物明示 `execution_allowed=false`、`canonical_queue_write_allowed=false`、`production_change_allowed=false`。
- Builder前後保存 canonical queue、production與scheduler parity；不得建立runner input、transaction或activation token。

## Slices

1. Admission/schema：負向 fixtures 覆蓋 non-HIGH、unsupported action、tampered/stale/external input。
2. Proposal builder：catalog-adjacent value、stable identity、dedupe/collision。
3. CLI/verifier：二跑 byte equality、recompute、parity receipt。
4. Acceptance：targeted tests、`py_compile`、JSON validation、`git diff --check`。

## Acceptance

- 若 catalog 有合法向上鄰值，只產一筆 `horizon` proposal；否則合法 `NO-GO_NO_ADJACENT_VALUE`。
- Proposal provenance完整，scope不得超過 Card B row。
- 二跑 output bytes、proposal ID、semantic hash一致。
- 所有負向 fixtures fail closed。
- Canonical queue、production、scheduler與來源檔案 hash零變更。
- 不新增任何 execution／publish／transaction／scheduler入口。

## Verification

```bash
<repo-root>/.venv/bin/pytest -q tests/test_shadow_research_plan_proposal.py tests/test_adaptive_shadow_queue.py
<repo-root>/.venv/bin/python scripts/verify_shadow_research_plan_proposal.py --self-test
<repo-root>/.venv/bin/python -m py_compile app/research/shadow_plan_proposal.py scripts/build_shadow_research_plan_proposal.py scripts/verify_shadow_research_plan_proposal.py
git diff --check
```

## Stop conditions

- 需要改parameter catalog、shadow policy、canonical queue或執行研究：`BLOCKED_SCOPE_VIOLATION`。
- 已提交來源無法重現或identity不一致：`BLOCKED_EVIDENCE_NOT_REPRODUCIBLE`。
- 同一 blocker第三次失敗：停止並回主線。

## Deliverable

- Candidate commit SHA、changed files、tests、CLI與evidence paths。
- 狀態只可為 `DELIVERED_CANDIDATE`；不得宣稱 integrated、accepted或live。
