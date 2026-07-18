---
id: TSKG-SRC-01-mainline-acceptance
status: INTEGRATED
accepted_at: 2026-07-19
accepted_by: Codex 主線
accepted_successor: 2d81414185446e83a34df28c37f54989515d7f76
review_artifact_commit: 0dc53cb4cec9fe8cac7d3a0305d68cdf887ff725
integration_head_before_acceptance_record: 1096d95b09f4085ea548da9bbe1d90f1368622c1
---

# TSKG-SRC-01 Mainline Acceptance

## Status

`REVIEW_GO / INTEGRATED`

本狀態只接受 synthetic/offline fail-closed Source Gate。它不代表任何真實公開來源
已核准，也不解除 OQ-SRC-01；SLC-02 仍為 blocked。

## Evidence and lineage

- Card commit：`4f0470e133b763d5d5c5a232acddf3ab2bc94de8`。
- 原 candidate：`bcbf773f8dbee51e84488b1ea3c11fabbad7a28a`。
- 初審：`REVIEW_NO_GO`，review commit
  `31715802f794f411986abdebb6f368ce31b35834`。
- Repair card：`717e1c6dffedf254661a12ab41b1092bfae948d9`。
- Repair successor：`2d81414185446e83a34df28c37f54989515d7f76`。
- 同一 reviewer re-review：`REVIEW_GO`，commit
  `0dc53cb4cec9fe8cac7d3a0305d68cdf887ff725`。

## Finding dispositions

- F-01 generic mapping 製造 `PUBLIC+APPROVED`：`RESOLVED`；OQ-SRC-01 未解除時
  一律拒絕，reader 0 calls。
- F-02 duplicate JSON last-wins：`RESOLVED`；raw JSON 在 mapping 建構前遞迴拒絕
  duplicate members。
- F-03 Unicode compatibility traversal：`RESOLVED`；validation、allowlist matching、
  receipt 與 reader callback 共用同一 canonical path。
- 新增阻塞 findings：無。

## Verification

- 主線重跑 SRC-01 17 tests＋SLC-01 22 regression tests，共 39/39。
- Reviewer matrix：51/51；三個 exploit 全部 blocked；10 個 denied requests 的
  reader 呼叫數為 0。
- `py_compile`、changed-file allowlist、`git diff --check`、network/dependency/
  production/prohibited/host-path scans：全部通過。
- Registry checksum：
  `0ea9bfca08d343f796aa093d162d4c9153b6a7fd8c94064d870a9d89b8a07b4d`。

## Mainline integration proof

- 整合前主線：`300571e11d7d9cfe00c7ff297feeef768697ca1a`。
- card、candidate、Repair card、Repair successor、最終 Review 五個 commits 依序
  cherry-pick，無衝突；接受紀錄前主線為
  `1096d95b09f4085ea548da9bbe1d90f1368622c1`。
- 使用者原有 `.gitignore`、research config/scripts 與元大輔助檔均未納入整合。
- 未修改 `app/api/main.py`、dependency manifests 或 production source adapters。

## Remaining blocker and next decision

- OQ-SRC-01 仍須 source/compliance owner 對一個特定來源核准 terms/legal basis、
  robots、method/path/media、rate/concurrency、retention、deletion 與 redistribution。
- 在該 immutable decision artifact 存在前，任何 `PUBLIC+APPROVED` 都必須 fail closed，
  SLC-02 不得開始。
- Reader callback 現在接收 canonical path；後續真實 adapter 必須依此介面實作，
  不得重新解析或替換路徑。
