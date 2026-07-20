---
card_id: REPAIR-TSKG-OSS-02
chain_id: TSKG-OSS
title: Correct TWSEMCPServer release metadata evidence
status: CARD_DRAFTED
type: repair
owner: Codex 主線
assignee: independent-visible-repair-thread
created_on: 2026-07-20
thickness: minimal
risk: low
model: gpt-5.4
reasoning: medium
model_reason: 單一 P2 文件證據修正，需重新核對 canonical repo 的 release 日期與驗證紀錄，但不涉及架構或 runtime
source_kind: commit
source_sha: d935c4fcb9e67faf124984dd07c93d72722a470e
review_commit: 5919ca987367aac50287f156ef3101610f335310
reviewer_thread_id: 019f7e60-0da2-71d1-b9cb-76f794312ee6
source_branch: codex/tskg-oss-02-repair
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
deliverable_path: docs/research/TSKG-OSS-02_external_open_source_reference_scout.md
evidence_path: docs/evidence/TSKG-OSS-02/verification.md
---

# REPAIR-TSKG-OSS-02：修正 TWSEMCPServer release 證據

## Repair target

只修復獨立審查指出的單一 P2 finding：

- `TSKG-OSS-02` candidate 把 `TWSEMCPServer` 的 latest release 寫成 `v1.3.0 / 2026-05-22`。
- Reviewer 於 2026-07-20 從 canonical GitHub repository 核對為 `v1.8.0 / 2026-07-19`。
- 需同步修正研究報告與 verification evidence，不能只替換版本字串。

## Must produce

1. 重新唯讀開啟 `https://github.com/twjackysu/TWSEMCPServer`，核對 latest release tag 與日期。
2. 在研究報告的候選表與詳細說明同步更新 release／activity metadata，附 canonical URL 與查閱日期。
3. 在 verification evidence 記錄本次更正、實際來源、commands／checks 與 exit code。
4. 保留既有邊界：README／CLAUDE 只能證明專案宣稱與 T86 直接相關，不能證明 TWSE endpoint 授權、source approval 或 production 可用性。
5. 其餘候選與排序若未受這筆新證據影響，不得順手重寫；若排序確實受影響，只能做最小一致性修正並說明原因。

## Allowlist

- `docs/tasks/2026-07-20_REPAIR-TSKG-OSS-02_release_metadata.md`
- `docs/research/TSKG-OSS-02_external_open_source_reference_scout.md`
- `docs/evidence/TSKG-OSS-02/verification.md`

## Forbidden scope

- 不修改 OSS-01、review evidence、code、config、requirements、runtime、API、UI、TSKG contract 或 SourcePolicy。
- 不 clone、下載 archive／dataset、安裝、執行外部 code、登入、使用 token、呼叫金融資料 endpoint 或 remote write。
- 不新增原 review 未要求的研究範圍，不產生 ADR，不批准任何 ingestion。
- 不回到 implementation 或 reviewer thread 直接改；本 Repair 必須由獨立 visible thread 交付 candidate。

## Verification

- Canonical repo page 成功讀取，source ledger 記為 `retrieved`；失敗時不得猜測版本。
- 報告所有 `TWSEMCPServer` release tag／日期描述彼此一致。
- `rg` 確認舊的 `v1.3.0`／`2026-05-22` 不再作為 latest release 結論殘留。
- changed files 完全符合 allowlist。
- host-specific path scan 與 `git diff --check` 通過。
- 候選交付完整 commit SHA，狀態只可到 `REPAIR_READY`。
- 完成後回原 reviewer thread `019f7e60-0da2-71d1-b9cb-76f794312ee6` re-review；不得另開 reviewer 重置 finding。

## Stop conditions

- Canonical repo 需要登入或無法確認 release 時，停止並回報證據不足。
- 同一 blocker 累計失敗三次即停止。
- 若 canonical repo 同一頁顯示互相衝突的 tag／日期，不自行推論，列出衝突交回主線。

## Pre-dispatch receipt

```text
card_path: docs/tasks/2026-07-20_REPAIR-TSKG-OSS-02_release_metadata.md
source_kind: commit
source_sha: d935c4fcb9e67faf124984dd07c93d72722a470e
review_commit: 5919ca987367aac50287f156ef3101610f335310
provisioning_branch: codex/tskg-oss-02-repair
source_worktree_clean: pending post-card commit
git_metadata_writable: pending preflight
index_lock: clear at card drafting
unrelated_dirty_paths: [] in repair-base worktree
thread_id: pending
worktree_path: pending
turn_status: pending
gate_1_card_contract: drafted
gate_2_visible_thread: pending
gate_3_candidate_delivery: pending
gate_4_same_reviewer_re_review: pending
gate_5_mainline_acceptance: pending
```
