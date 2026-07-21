---
card_id: REVIEW-TSKG-OSS-01-02
chain_id: TSKG-OSS
title: Independent review of local asset and external OSS research
status: REVIEW_GO
type: review
owner: Codex 主線
assignee: independent-visible-review-thread
created_on: 2026-07-20
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 兩份研究候選均為文件與唯讀證據，需跨核 repo call-chain、GitHub/PyPI metadata、License 與結論邊界，但不負責架構選型
source_kind: fixed_candidate_commits
source_card_commit: 1a2b0eab8a3ed625d85fdeef6ce4ddb4726a7208
candidate_oss_01: f6a4f8fd263364d8dfe94f47f02e0e22cb6a8507
candidate_oss_02: d935c4fcb9e67faf124984dd07c93d72722a470e
source_branch: codex/tskg-mfo-src-01
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/REVIEW-TSKG-OSS-01-02/review.md
---

# REVIEW-TSKG-OSS-01-02：既有資產與外部開源研究獨立審查

## Review target

固定審查兩個互不相依、共同 parent 為 `1a2b0eab8a3ed625d85fdeef6ce4ddb4726a7208` 的 candidate：

- `TSKG-OSS-01`：`f6a4f8fd263364d8dfe94f47f02e0e22cb6a8507`
- `TSKG-OSS-02`：`d935c4fcb9e67faf124984dd07c93d72722a470e`

Reviewer 只判定，不修改 candidate。只有兩份候選都達到 GO，主線才可整合並建立 `TSKG-OSS-ADR-01`。

## Required review

### Candidate OSS-01

1. 核對 FinMind fetcher／integrator／FetchStage／indicator 與 T86 market-context caller、verifier、artifact consumer 的 repo 證據。
2. 檢查 `ACTIVE | FALLBACK | SHADOW | DORMANT | BROKEN | UNKNOWN` 是否過度宣稱 live／production 狀態。
3. 檢查 `REUSE | REFERENCE_ONLY | DO_NOT_REUSE | NEEDS_VALIDATION` 是否符合 `SecurityFlowObservation` raw-only、TWD、source-policy 邊界。
4. 核對沒有把「程式存在」寫成「來源已核准」。

### Candidate OSS-02

1. 逐一核對 canonical repo/package/discussion URL、最近 release/activity date、License 與 directness。
2. 檢查 FinMind code license 與 data-use note 是否正確分層。
3. 檢查 `TWSEMCPServer` 的 T86 相關性與 MIT 證據；不得把其 README／CLAUDE 說明當官方 endpoint 授權。
4. 檢查 twstock request-limit、twstocks-crawler metadata、tsec/tsrtc license 未見等保守措辭。
5. 確認同一專案未拆名額灌水，且「沒有成熟 T86 專用 repo」沒有被寫成全域絕對事實。

### Combined consistency

1. 兩份報告對 FinMind、T86、來源核准與 production reuse 不得互相衝突。
2. 下一張 ADR 的輸入、blocker 與不可沿用事項要足夠明確。
3. 驗證 exact allowlist、host-path scan、`git diff --check`、candidate parent／SHA。

## External boundary

- 可唯讀開啟候選已引用的 GitHub repo／LICENSE／release／issue、PyPI metadata 與官方專案文件。
- 禁止 clone、下載 archive/dataset、安裝、執行外部 code、登入、token、金融資料 endpoint、rate test 或任何 remote write。
- failed／retrieved_limited 來源不得承載 substantive finding。

## Allowlist

- `docs/tasks/2026-07-20_REVIEW-TSKG-OSS-01-02_reuse_research.md`
- `docs/evidence/REVIEW-TSKG-OSS-01-02/review.md`

## Forbidden scope

- 不修改 OSS-01／02 candidate 文件或 commit。
- 不修改 app、scripts、tests、config、requirements、runtime、API、UI、TSKG contract 或 SourcePolicy。
- 不產生 source selection ADR、不批准來源、不 merge、不 push。
- NO_GO 時只列具檔案／行號、證據與修復驗收條件的 findings；Repair 由主線另開卡。

## Verdict contract

- `GO`：兩個固定 candidate 均可作為後續 ADR 的可信輸入。
- `NO_GO`：任一 candidate 有 P0–P2 correctness／evidence／scope finding。
- P3 或未驗證 live 行為可列 remaining risk，但不得被誤寫為已驗證。

Review 輸出必須包含：`verdict`、`reviewed_commits`、P0–P3 findings、Spec axis、Standards axis、source ledger、commands/exit codes、remaining risks。狀態只可到 `REVIEW_GO` 或 `REVIEW_NO_GO`。

## Pre-dispatch receipt

```text
card_path: docs/tasks/2026-07-20_REVIEW-TSKG-OSS-01-02_reuse_research.md
source_card_commit: 1a2b0eab8a3ed625d85fdeef6ce4ddb4726a7208
candidate_oss_01: f6a4f8fd263364d8dfe94f47f02e0e22cb6a8507
candidate_oss_02: d935c4fcb9e67faf124984dd07c93d72722a470e
source_worktree_clean: pending review-card commit
git_metadata_writable: pending preflight
index_lock: clear at card drafting
unrelated_dirty_paths: [] in source worktree
thread_id: pending
worktree_path: pending
turn_status: pending
gate_1_card_contract: drafted
gate_2_visible_thread: pending
gate_3_candidate_delivery: complete for both fixed candidates
gate_4_independent_review: REVIEW_GO
gate_5_mainline_acceptance: accepted by docs/evidence/TSKG-OSS-ADR-01/acceptance.md
```
