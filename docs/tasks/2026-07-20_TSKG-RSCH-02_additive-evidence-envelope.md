---
card_id: TSKG-RSCH-02
chain_id: TSKG-RSCH
title: Additive TSKG research evidence envelope
status: PENDING
type: implementation
owner: Codex 主線
assignee: TSKG-RSCH-02 contract implementation line
thickness: standard
risk: medium
model: gpt-5.5
reasoning: high
model_reason: 需把 identity、source、time、conflict 與 evidence 語意縮成向後相容的 research-only contract，避免誤阻擋歷史研究或形成第二套 workflow engine
source_kind: commit
source_sha: <accepted-sha-from-TSKG-RSCH-01>
mainline_dispatcher: TSKG root thread
previous_card: TSKG-RSCH-01
worktree_mode: independent-clean-worktree
main_cwd: <repo-root>
expected_worktree_cwd: not-equal-to-main-cwd
evidence_path: docs/evidence/TSKG-RSCH-02/
---

# TSKG-RSCH-02：Additive research evidence envelope

## Dependency

只有 `TSKG-RSCH-01` 被主線接受，且 inventory 證明欄位需求後才能啟動。

## Goal

建立獨立、additive、versioned 的 research evidence envelope 與 verifier，供新研究或 reuse checkpoint 使用；不修改既有 queue／ledger runtime，不要求歷史 artifact 全面 migration。

## Minimum contract

- `schema_version`
- `research_id`、`usage_intent`
- `adoption_mode`：`GRANDFATHERED/CHECK_ON_REUSE/REQUIRED_NOW`
- `identity_assessment`：status、entity refs、resolver/version 或 `NOT_EVALUATED`
- `source_assessment`：source refs、policy status／receipt refs 或 `NOT_EVALUATED`
- `temporal_scope`：as-of、valid/observed interval 或 unknown reason
- `conflict_assessment`：`NONE/OPEN/RESOLVED/UNKNOWN` 與 evidence refs
- `evidence_refs`、`decision`、`blocking_reasons`

## Behavior

- `GRANDFATHERED` 可缺新維度，但不得宣稱通過新契約。
- `CHECK_ON_REUSE` 只有在 reuse/promotion/model-input 使用點驗證。
- `REQUIRED_NOW` 缺 identity/source/time/conflict 關鍵欄位時 fail closed。
- verifier 只產 decision artifact，不寫 queue、不改 ledger、不啟動研究。
- 不呼叫 TSKG router、source reader、外部服務或 production API。

## Likely allowlist

- `app/research/tskg_evidence_contract.py`
- `scripts/verify_tskg_research_evidence.py`
- `tests/test_tskg_research_evidence_contract.py`
- `docs/evidence/TSKG-RSCH-02/**`
- 本卡 Result/status

## Forbidden scope

- 不修改 `scripts/build_pm_approved_work_queue.py`、`scripts/model_experiment_ledger.py`、`scripts/build_research_component_ledger.py` 或 promotion workflow。
- 不 migration 歷史 artifacts、不改 research verdict、不執行研究。
- 不把 advisory uncertainty 轉成交易訊號或模型權重。

## Verification

- Public-behavior tests 覆蓋三種 adoption mode、unknown、ambiguous、open conflict、closed shape、stable decision 與歷史相容。
- 重複驗證 byte-equivalent；輸入缺漏時錯誤可重現。
- `git diff --check` 與 changed-file allowlist 通過。

## Result

`PENDING_INVENTORY`
