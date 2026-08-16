---
id: CARD-NEW-TOP10-AUTHORITY-SNAPSHOT-RECONCILIATION-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: data-authority-contract
priority: P1
owner: TOP10new research platform
role: implementation
cycle: 17
thickness: standard
risk: medium
model: gpt-5.6-terra
reasoning: medium
model_reason: authority fork 已由主線定界為既有 committed evidence chain；本卡只做 bounded hash reconciliation，不做架構裁決或 production mutation。
date: 2026-08-16
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
canonical_queue_change_allowed: false
network_allowed: false
evidence_path: docs/evidence/CARD-NEW-TOP10-AUTHORITY-SNAPSHOT-RECONCILIATION-V1/
---

# Authority Snapshot Reconciliation V1

## 工作名稱

以 committed evidence chain 綁定 ignored runtime authority snapshot。

## Root question

在不提交或改寫 `artifacts/market_regime_history.json`、`data/clean/features.parquet` 的前提下，能否由 committed coverage plan 綁定 committed availability audit，再以其中固定 path／hash 驗證目前 runtime bytes，產生可供下一張 feasibility audit 使用的 deterministic authority receipt？

## 固定事實

- 目前 feasibility status：`BLOCKED_AUTHORITY_CONFLICT`。
- 兩個 runtime source 受 `.gitignore` 管理；raw bytes 不應被誤稱為 committed truth。
- Committed coverage plan 已綁定 availability audit 的 repo-relative path 與 SHA-256。
- Committed availability audit 已記錄兩個 runtime source 的固定 path、SHA-256 與 date coverage。
- CodeGraph：`ready`，indexed HEAD `3a0c9a0355dfb7549de6c5a0d19531b32354e03b`；語意 query 指向 `shadow_replay_regime_feasibility::_committed_record/_authority_record` seam，原始碼確認 raw-file git tracking 假設是 blocker。

## Authority contract

- `committed authority` 指 coverage-plan → availability-audit 的 committed content-addressed chain。
- Raw regime／features 只可作被 receipt hash 驗證的 ignored runtime payload，不得宣稱本身已 commit。
- Chain 任一 path、hash、schema、status、symlink、missing bytes 或 source hash 不符，必須 fail closed。
- Receipt 只能解除「snapshot identity」衝突；不得宣稱 lineage、non-sealed status、ranking materialization、formal replay 或 production readiness 已證明。

## Ownership

### 允許修改

- 新增 `app/research/shadow_replay_authority_reconciliation.py`。
- 新增 `tests/test_shadow_replay_authority_reconciliation.py`。
- 新增 `docs/evidence/CARD-NEW-TOP10-AUTHORITY-SNAPSHOT-RECONCILIATION-V1/reconciliation.json`。

### 禁止修改

- `artifacts/market_regime_history.json`、`data/clean/features.parquet`。
- 既有 evidence、ranking、model、config、universe、industry map。
- Canonical queue、manager、runner、scheduler、launchd、daily quota、production surfaces。
- 網路、下載、資料回填、raw dataset commit、replay、materialization。
- 使用者 dirty files與 `.work/**`。

## Requirements

- `ASR-FR-001`：只接受 canonical committed coverage plan；重算其 availability-audit file hash，禁止 caller 指定任意 manifest。
- `ASR-FR-002`：從 committed availability audit 讀取 canonical regime／features path與 SHA-256；拒絕 absolute path、escape、symlink與 schema/status 不符。
- `ASR-FR-003`：stream hash runtime bytes並 exact-match；不得以 git tracking status 判定 raw payload authority。
- `ASR-FR-004`：輸出 canonical JSON，明列 chain records、runtime records、date coverage、reason codes與 `lineage_authority_status=UNPROVEN`。
- `ASR-FR-005`：status只允許 `READY_FOR_FEASIBILITY_AUDIT`、`BLOCKED_AUTHORITY_CONFLICT`；任何 conflict 不得輸出 ready。

## Slices

### `ASR-001`｜RED：committed-chain fixture

- `traces_to`: `ASR-FR-001`, `ASR-FR-002`, `ASR-FR-003`
- 建立 ignored raw payload＋committed plan/audit chain fixture。
- 先證明目前 raw-file `_committed_record` 路徑會阻擋合法 hash-bound payload。

### `ASR-002`｜最小 reconciler

- `blocked_by`: `ASR-001`
- `traces_to`: `ASR-FR-001`, `ASR-FR-002`, `ASR-FR-003`
- 實作固定 chain驗證與 streaming hash；不新增通用 manifest framework。

### `ASR-003`｜Receipt與 hostile verifier

- `blocked_by`: `ASR-002`
- `traces_to`: `ASR-FR-004`, `ASR-FR-005`
- 覆蓋 plan/audit/runtime hash drift、path escape、nested symlink、missing source、false-ready與二跑 byte identity。

## Acceptance

- 正向 fixture與目前 authority root只在完整 hash chain一致時輸出 `READY_FOR_FEASIBILITY_AUDIT`。
- Raw sources在輸出中明列 `commit_status=IGNORED_HASH_BOUND`；不得寫成 `MATCHED`或`COMMITTED`。
- 任一 hostile mutation輸出 `BLOCKED_AUTHORITY_CONFLICT`或受控 verifier failure；不得 traceback／absolute path。
- Evidence二跑 byte-identical；protected surfaces與raw source pre/post hash一致。
- Targeted pytest、CLI verifier、`py_compile`、JSON validation、`git diff --check`通過。
- 單一 candidate commit；不得 merge、push、deploy或宣稱 integrated。

## Verification

```bash
uv run pytest -q tests/test_shadow_replay_authority_reconciliation.py tests/test_shadow_replay_regime_feasibility.py
uv run python -m app.research.shadow_replay_authority_reconciliation --verify docs/evidence/CARD-NEW-TOP10-AUTHORITY-SNAPSHOT-RECONCILIATION-V1/reconciliation.json
uv run python -m py_compile app/research/shadow_replay_authority_reconciliation.py tests/test_shadow_replay_authority_reconciliation.py
jq empty docs/evidence/CARD-NEW-TOP10-AUTHORITY-SNAPSHOT-RECONCILIATION-V1/reconciliation.json
git diff --check
```

## Stop conditions

- 需要提交／改寫 raw sources、下載、資料回填或改 production：`BLOCKED_SCOPE_VIOLATION`。
- Existing evidence chain缺 path/hash/schema authority且無法唯讀驗證：`BLOCKED_AUTHORITY_CONFLICT`。
- 需要新的通用 manifest framework或改既有 lineage schema：停回主線另卡。

## Deliverable

- 回報 candidate SHA、changed files、RED/GREEN、evidence status、驗證結果、剩餘 blocker。
