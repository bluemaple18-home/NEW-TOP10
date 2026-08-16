---
id: CARD-NEW-TOP10-RECONCILED-REGIME-FEASIBILITY-V2
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: data-evidence-audit
priority: P1
owner: TOP10new research platform
role: implementation
cycle: 18
thickness: standard
risk: medium
model: gpt-5.6-terra
reasoning: medium
model_reason: snapshot authority 已由 cycle 17 固定；本卡只重用現有 episode 與 horizon helpers 產生 bounded V2 audit。
date: 2026-08-16
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
canonical_queue_change_allowed: false
network_allowed: false
evidence_path: docs/evidence/CARD-NEW-TOP10-RECONCILED-REGIME-FEASIBILITY-V2/
---

# Reconciled Regime Feasibility V2

## 工作名稱

以 reconciled authority snapshot 重跑 exact-regime h10／h20 feasibility。

## Root question

Authority reconciliation 為 `READY_FOR_FEASIBILITY_AUDIT` 後，目前 hash-bound regime／features snapshot 是否存在同一 immutable episode 內可承載 entry delay 1 與 h10／h20 的 shared ranking date？

## 固定事實

- Reconciliation receipt：`docs/evidence/CARD-NEW-TOP10-AUTHORITY-SNAPSHOT-RECONCILIATION-V1/reconciliation.json`。
- Raw sources維持 ignored、hash-bound；不得改稱 committed raw truth。
- 初步唯讀盤點：81 episodes，0 feasible identities；正式結果只認本卡 deterministic evidence。
- Canonical seams：`build_regime_episodes`、`exact_horizon_safe_ranking_dates`、cycle 16 `episode_matrix`。

## Ownership

### 允許修改

- 新增 `app/research/shadow_replay_reconciled_feasibility.py`。
- 新增 `tests/test_shadow_replay_reconciled_feasibility.py`。
- 新增 `docs/evidence/CARD-NEW-TOP10-RECONCILED-REGIME-FEASIBILITY-V2/feasibility.json`。

### 禁止修改

- Raw regime／features、既有 evidence、ranking、model、config、queue、manager、runner、scheduler、production。
- 網路、下載、回填、regime identity調整、episode合併、horizon放寬、materialization、replay。
- 使用者 dirty files與 `.work/**`。

## Requirements

- `RRF-FR-001`：先完整重算 cycle 17 reconciliation；非 ready立即 fail closed。
- `RRF-FR-002`：從 receipt固定 path讀 raw sources，重驗 nested symlink與hash，不接受 caller自訂來源。
- `RRF-FR-003`：原樣重用 canonical episode matrix與 h10／h20 helper；不得跨 episode window。
- `RRF-FR-004`：輸出全部 episode、feasible identities、fixed scope與 reconciliation identity；canonical bytes、無 absolute path／timestamp。
- `RRF-FR-005`：status只允許 `READY_FOR_SCOPE_DECISION`、`NO-GO_NO_ELIGIBLE_REGIME`、`BLOCKED_AUTHORITY_CONFLICT`；0 feasible 必須 NO-GO。

## Slices

- `RRF-001`：reconciliation gate＋source load；`traces_to`: `RRF-FR-001`, `RRF-FR-002`。
- `RRF-002`：canonical matrix；`blocked_by`: `RRF-001`；`traces_to`: `RRF-FR-003`。
- `RRF-003`：evidence／verifier／hostile tests；`blocked_by`: `RRF-002`；`traces_to`: `RRF-FR-004`, `RRF-FR-005`。

## Acceptance

- Current authority合法輸出正式 status；若0 feasible，reason=`NO_SHARED_HORIZON_SAFE_EXACT_REGIME_DATE`。
- Reconciliation drift、source drift、symlink、false-ready、episode跨界全部 controlled fail。
- `lineage_authority_status=UNPROVEN`；不得宣稱 replay／promotion ready。
- 兩跑 byte identity；targeted pytest、verifier、`py_compile`、JSON、`git diff --check`通過。
- 單一 candidate commit；不得 push／deploy。

## Verification

```bash
uv run pytest -q tests/test_shadow_replay_reconciled_feasibility.py tests/test_shadow_replay_authority_reconciliation.py tests/test_shadow_replay_regime_feasibility.py
uv run python -m app.research.shadow_replay_reconciled_feasibility --verify docs/evidence/CARD-NEW-TOP10-RECONCILED-REGIME-FEASIBILITY-V2/feasibility.json
uv run python -m py_compile app/research/shadow_replay_reconciled_feasibility.py tests/test_shadow_replay_reconciled_feasibility.py
jq empty docs/evidence/CARD-NEW-TOP10-RECONCILED-REGIME-FEASIBILITY-V2/feasibility.json
git diff --check
```

## Stop conditions

- 需要改 source、identity、episode或horizon：`BLOCKED_SCOPE_VIOLATION`。
- Reconciliation不再 ready：`BLOCKED_AUTHORITY_CONFLICT`。

## Deliverable

- Candidate SHA、正式 status、episode／feasible counts、驗證、下一個 fork。
