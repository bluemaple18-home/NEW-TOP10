---
card_id: TSKG-OSS-02
chain_id: TSKG-OSS
title: TSKG external open-source reference scout
status: DELIVERED_CANDIDATE
type: research
owner: Codex 主線
assignee: visible-thread
created_on: 2026-07-20
thickness: minimal
risk: low
model: gpt-5.4
reasoning: medium
model_reason: 只需對少量已知候選做官方 repo／package／discussion 的唯讀事實驗證與排序，不負責架構或 source approval
source_kind: commit
source_sha: da0d0b20bb1838ef8dc9dffcb926fca72562a419
source_branch: codex/tskg-mfo-src-01
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
deliverable_path: docs/research/TSKG-OSS-02_external_open_source_reference_scout.md
evidence_path: docs/evidence/TSKG-OSS-02/verification.md
---

# TSKG-OSS-02：外部開源參考盤點

## Root question

目前有哪些仍可查證的開源專案、套件、Issue／Discussion，能作為台股三大法人、TWSE T86、request 控制、欄位正規化與更新流程的參考？

本卡只做小型、可引用的 reference scout，不開發、不修改 runtime、不做 source approval。

## Candidate seed

- FinMind repository、文件、releases、issues／discussions。
- twstock repository、文件、PyPI、issues。
- `twstocks-crawler` 或其他確實存在且直接相關的候選。
- 專門命名為 T86 crawler／parser／wrapper 的候選；找不到也要明記。

## Must produce

最多 8 個候選，每個都要有：

1. canonical repository/package/discussion URL。
2. 解決問題與可參考的具體檔案、模組或討論主題。
3. 最近 release／commit／issue activity，附查閱日期；不能只寫「活躍」。
4. License 與可參考邊界；若缺 license，明確標示。
5. 與 T86／三大法人資料的直接程度：`DIRECT | ADJACENT | NOT_RELEVANT`。
6. 風險：資料來源、rate limit、維護度、格式漂移、二次整理。
7. 最值得 synthesis 卡閱讀的前三項，不能把同一專案的 repo／docs／release 拆成三個名額灌水。

## Allowlist

- `docs/tasks/2026-07-20_TSKG-OSS-02_external_open_source_reference_scout.md`
- `docs/research/TSKG-OSS-02_external_open_source_reference_scout.md`
- `docs/evidence/TSKG-OSS-02/verification.md`

## Forbidden scope

- 不修改 code、config、requirements、runtime、API、UI、TSKG contract 或 SourcePolicy。
- 不 clone、安裝、執行、登入、申請 token、呼叫金融資料 endpoint 或下載 dataset。
- 不把 README 宣稱當作實際維護證據；要看 release／commit／issue 的可查日期。
- 不評估交易策略、模型效果或預測能力。
- 不決定最終採用方案；那是後續 `TSKG-OSS-ADR-01` 的責任。

## Verification

- 每個引用 URL 必須實際成功讀取；failed／not_used 另列。
- 關鍵維護與 license 判定至少由 repo metadata＋LICENSE/package metadata 交叉驗證。
- Source tracker 記錄 `retrieved | retrieved_limited | failed | not_used`。
- changed files 完全符合 allowlist。
- host-specific path scan 與 `git diff --check` 通過。
- 候選交付包含完整 commit SHA；狀態只可到 `DELIVERED_CANDIDATE`。

## Stop conditions

- 需要登入、token、安裝或執行外部 code 時停止，改記限制。
- 同一 URL／blocker 失敗三次即停止。
- 找不到 T86 專用 repo 時不得拿一般股票套件冒充。

## Pre-dispatch receipt

```text
card_path: docs/tasks/2026-07-20_TSKG-OSS-02_external_open_source_reference_scout.md
provisioning_source_sha: da0d0b20bb1838ef8dc9dffcb926fca72562a419
provisioning_branch: codex/tskg-mfo-src-01
source_worktree_clean: pending post-card commit
git_metadata_writable: pending preflight
index_lock: clear at card drafting
unrelated_dirty_paths: [] in source worktree
thread_id: 019f7e58-df13-7d60-80c9-885af3e23f0f
worktree_path: <local-only>/Users/matt/.codex/worktrees/245a/TOP10new
turn_status: DELIVERED_CANDIDATE
gate_1_card_contract: drafted
gate_2_visible_thread: satisfied
gate_3_candidate_delivery: satisfied
gate_4_independent_review: pending
gate_5_mainline_acceptance: pending
```
