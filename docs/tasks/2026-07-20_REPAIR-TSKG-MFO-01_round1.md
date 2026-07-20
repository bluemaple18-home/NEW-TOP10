---
card_id: REPAIR-TSKG-MFO-01-1
chain_id: TSKG-MFO
title: Repair MFO-01 RFC3339 and invalid JSON error gates
status: CARD_DRAFTED
type: repair
repair_generation: 1
owner: Codex 主線
assignee: independent visible repair task
created_on: 2026-07-20
thickness: minimal
risk: medium
model: gpt-5.4
reasoning: medium
model_reason: 兩個 P2 finding 均已定位且修法與測試邊界明確，屬單模組 bounded repair
source_kind: commit
source_sha: 24657766a3484d77f3383b5ee8237df0e0614926
candidate_sha: 11c68e9c32812a394788c95bc69a8763a92a8929
review_thread: 019f7e09-5c64-7dd1-8018-e97e0bafc865
review_evidence: docs/evidence/REVIEW-TSKG-MFO-01/review.md
mainline_dispatcher: current TSKG root task
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
operation_level: local_code_repair
evidence_path: docs/evidence/REPAIR-TSKG-MFO-01/repair-1.md
---

# REPAIR-TSKG-MFO-01-1

## Goal

只修獨立 Review 的兩個 P2 finding：

1. `observed_at/retrieved_at` 必須是 RFC 3339 UTC **字串**；`from_mapping()` 不得接受 Python `datetime` 或其他非字串物件。
2. `from_file()` 遇到語法損壞 JSON 時，必須把 `json.JSONDecodeError` 轉譯為 `FlowObservationContractError`，保留 exception chaining；不得吞掉 `OSError`。

## TDD contract

### F-01 RFC3339 type gate

- 先新增 aware UTC `datetime` 的 `observed_at`／`retrieved_at` negative tests，確認 RED。
- implementation 在呼叫 `parse_utc_instant()` 前要求兩欄皆為 `str`。
- list/dict/null/bool 與既有 malformed probes 仍統一為 `FlowObservationContractError`。

### F-02 invalid JSON envelope

- 先新增 temporary invalid JSON file test，確認 `JSONDecodeError` RED。
- `from_file()` 只捕捉 `json.JSONDecodeError`，轉為 `FlowObservationContractError` 並保留 `__cause__`。
- 新增不存在檔案 probe，確認 `FileNotFoundError`／`OSError` 不被吞掉。

## Allowlist

- `app/tskg/flow_observation.py`
- `tests/test_tskg_mfo01.py`
- `docs/tasks/2026-07-20_REPAIR-TSKG-MFO-01_round1.md`
- `docs/evidence/REPAIR-TSKG-MFO-01/repair-1.md`

## Verification

```text
<repo-root>/.venv/bin/python -m unittest \
  tests.test_tskg_mfo01 tests.test_tskg_slc01 tests.test_tskg_src01
```

另需重跑 reviewer 109 組 malformed type probes或等價 table-driven probes、`git diff --check`、exact allowlist 與 host-path scan。

## Forbidden scope

- 不修改 Review evidence／Review card、原 MFO-01 card／verification、fixture 或 exports。
- 不新增依賴、外部存取、API、UI、Top10、Theme／rolling formula 或 source adapter。
- 不整合、不 push、不自行改 Review verdict。
- 不處理 Python 3.13 provisioning；caveat 原樣保留。

## Delivery contract

建立 Repair candidate commit，回報 full SHA、parent、changed files、RED/GREEN、46-test regression、malformed probes、remaining risk。結果只能是 `REPAIR_DELIVERED` 或 `BLOCKED`，之後回原 reviewer re-review。

## Result

`PENDING_REPAIR`
