---
id: REPAIR-NEW-TOP10-HORIZON-SAFE-EVIDENCE-AVAILABILITY-AUDIT-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: bounded-repair
priority: P1
owner: TOP10new research platform
role: repair
cycle: 15
thickness: standard
risk: medium
model: gpt-5.6-terra
reasoning: medium
model_reason: 已有單一可重現 verifier drift；只修穩定 authority identity 與回歸測試，採節省模式平衡執行層。
date: 2026-08-15
production_change_allowed: false
live_activation_allowed: false
scheduler_change_allowed: false
canonical_queue_change_allowed: false
network_allowed: false
evidence_path: docs/evidence/REPAIR-NEW-TOP10-HORIZON-SAFE-EVIDENCE-AVAILABILITY-AUDIT-V1/
---

# Repair Horizon-safe Audit Post-integration Identity Drift

## Root question

如何讓 availability evidence 在 candidate fast-forward 整合後仍可重算驗證，同時保留同 repo registered-worktree 與固定 source drift 的 fail-closed 邊界？

## Reproduction

Source／integrated HEAD：`66be50bbe78d8d2913f31aa206b2984ea43d7ae8`。

```bash
<repo-root>/.venv/bin/python -m app.research.shadow_replay_availability \
  --authority-root <repo-root> \
  --verify docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-AVAILABILITY-AUDIT-V1/availability_audit.json
```

實際：`AUDIT_RECOMPUTE_MISMATCH`。原因：evidence identity 保存 pre-merge `authority_head/tree`；整合 audit code 本身即改變 HEAD/tree，但 fixed data authority 未漂移。

## Ownership

允許修改：

- `app/research/shadow_replay_availability.py`
- `tests/test_shadow_replay_availability.py`
- 原 Card E evidence，或本 Repair evidence（只限必要更新）

禁止修改：

- Ranking roots、features、regime、Card D evidence
- Queue、scheduler、production、model、signals
- Replay／matrix／comparison執行
- 網路、資料下載／回填
- 使用者 dirty files與 `.work/**`

## Requirements

- `HSEA-R1-FR-001`：合法 authority root 的 identity 不因無關 code commit 改變。
- `HSEA-R1-FR-002`：固定資料來源任一內容漂移時 verifier 必須 fail closed。
- `HSEA-R1-FR-003`：canonical evidence deterministic、跨機且不含 runtime 絕對路徑。

## Slices

### `HSEA-R1-001`｜Stable authority identity

- `traces_to`: `HSEA-R1-FR-001`, `HSEA-R1-FR-003`
- Repo/worktree registration只證明 runtime root合法，不得讓無關 code HEAD movement污染固定 data authority identity。
- Evidence identity以固定來源 hash／schema與必要 repo identity為準；不得含絕對路徑。

### `HSEA-R1-002`｜Post-integration regression

- `blocked_by`: `HSEA-R1-001`
- `traces_to`: `HSEA-R1-FR-001`, `HSEA-R1-FR-002`
- 建立 fixture：先產 evidence，再提交只影響 audit code或無關檔案的 commit；verify仍 PASS。
- Ranking／features／regime／Card D任一內容漂移：verify FAIL。
- Different repo、unregistered worktree、symlink、traversal仍 fail closed。

### `HSEA-R1-003`｜Canonical evidence repair

- `blocked_by`: `HSEA-R1-002`
- `traces_to`: `HSEA-R1-FR-003`
- 重建 deterministic canonical evidence。
- 二跑 byte-identical；不得出現 machine absolute path。

## Acceptance

- 上述 mainline repro轉 PASS。
- Targeted pytest、CLI verifier、`py_compile`、`jq empty`、absolute-path gate、`git diff --check`全綠。
- Current verdict／fixed source facts不得被修碼改寫：仍為 `NO-GO_EVIDENCE_UNAVAILABLE`；25／25 ranking dates、282 feature dates、regime AVAILABLE。
- Production／canonical queue／scheduler／fixed sources pre/post parity一致。
- 交付單一 repair candidate commit；不得 push、deploy或宣稱 live。

## Stop conditions

- 需要放寬同 repo／registered-worktree boundary：`BLOCKED_AUTHORITY_CONTRACT`。
- 需要修改 fixed source或重跑 replay：`BLOCKED_SCOPE_VIOLATION`。
