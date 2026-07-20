---
card_id: REVIEW-TSKG-OSS-ADR-01
chain_id: TSKG-OSS
title: Independent review of TSKG reference adoption ADR
status: CARD_DRAFTED
type: review
owner: Codex 主線
assignee: independent-visible-review-thread
created_on: 2026-07-20
thickness: strict
risk: high
model: gpt-5.5
reasoning: high
model_reason: 需獨立挑戰高風險架構決策的來源治理、adoption matrix、contract 邊界、非策略限制與下一實作卡，但不重新做方案設計
source_kind: commit
source_sha: dfade37ba0c030d764f1f3b7181cead17a6b3756
candidate_parent: ea5655efc5bf171f3584073ac04046699d0cc56e
architecture_source: 59917dd87dda448e77f5fc50ccfb3c1d05775aca
source_branch: codex/tskg-oss-adr-review
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
evidence_path: docs/evidence/REVIEW-TSKG-OSS-ADR-01/review.md
---

# REVIEW-TSKG-OSS-ADR-01：參考資產採用 ADR 獨立審查

## Review target

固定審查 candidate `dfade37ba0c030d764f1f3b7181cead17a6b3756`，parent／ADR card commit 為 `ea5655efc5bf171f3584073ac04046699d0cc56e`，architecture source 為 `59917dd87dda448e77f5fc50ccfb3c1d05775aca`。

Reviewer 只判定，不修改 ADR candidate、不另做架構、不建立下一卡。

## Required review

### Decision integrity

1. 四方案均被實質比較，且只有 `ADAPTER_FIRST_INTERNAL_PATTERNS` 是 primary。
2. ADR 沒有在 consequence、matrix 或 next-card 文字中暗中採用第二個 primary。
3. Rejected alternatives 的理由可由 fixed inputs 支持，不是偏好式結論。

### Adoption matrix

1. 每個 required asset 都出現且只有一個狀態：`REUSE_INTERNAL | REFERENCE_ONLY | DO_NOT_ADOPT | BLOCKED_PENDING_SOURCE_APPROVAL`。
2. Repo FinMind fetcher／integrator／FetchStage、direct T86 parser/status/offline verifier 的狀態不把「程式存在」誤寫為 production active 或 source approval。
3. TWSEMCPServer、FinMind external service／code pattern、twstock、twstocks-crawler、tsec、tsrtc、issue discussion 的 license、data rights、endpoint authorization 與 production approval 分層正確。
4. `SecurityFlowObservation` 與 `ThemeFlowObservation` 的狀態符合既有 contract／handoff，不把 daily observation 當 graph truth。

### Boundary and next card

1. source adapter → raw snapshot／provenance → normalizer → observation contract → graph projection → Top10／LLM read model 的可做／blocked 邊界無跳階。
2. `TSKG-MFO-RM-01` 是唯一 next implementation card，未在 repo 中被實際建立，且不與既有 `SecurityFlowObservation` contract 重複。
3. Next card 可完全以 synthetic／fixture／offline evidence 驗證，不需要 live source、source-specific schema、API、UI 或 Top10 ranking mutation。
4. Top10／LLM read model 不包含 score、weight、signal、prediction、推薦或交易策略語意。
5. Source approval、live connector、rate／retention／redistribution、late correction、ThemeFlow aggregation、graph diffusion 與 UI radar 均留在後續 fork。

### Evidence and standards

1. Substantive claim 可回到卡片 fixed inputs 的具體 section／repo symbol。
2. Verification 的 12/12 claim coverage、16/16 matrix、single decision／next card 與 allowlist 可重現。
3. Candidate changed files 恰為三檔 allowlist，host-neutral，`git diff --check` 通過。
4. ADR 狀態只到 `PROPOSED_CANDIDATE`，沒有自稱 accepted／integrated／source approved。

## Allowlist

- `docs/tasks/2026-07-20_REVIEW-TSKG-OSS-ADR-01_reference_adoption.md`
- `docs/evidence/REVIEW-TSKG-OSS-ADR-01/review.md`

## Evidence writing rule

- 共享文件只用 `<local-only-worktree>`、`<repo-gitdir>`、`<worktree-id>` 與 `<host-path-scan>`。
- 不得保存實際 cwd、git-dir、使用者／主機資訊、本機絕對路徑、本機 file URI 或 host-path pattern 的逐字內容。
- Review 卡與 review evidence 自身也必須納入最後 shared-file gate。

## Forbidden scope

- 不修改 ADR candidate、fixed inputs、code、test、fixture、config、requirements、runtime、API、UI、spec、contract 或 SourcePolicy。
- 不連外補研究、不呼叫金融 endpoint、不安裝／執行外部 code。
- 不建立 `TSKG-MFO-RM-01`，不批准任何 ingestion，不 merge、不 push。
- NO_GO 時只列具體 P0–P2 finding 與 repair acceptance，不自行修復。

## Verdict contract

- `GO`：ADR 可作為後續 `TSKG-MFO-RM-01` 卡片輸入，但仍不構成 source approval 或 implementation authorization。
- `NO_GO`：任一 P0–P2 correctness、source-boundary、contract、scope 或 evidence finding。

輸出必須包含：verdict、reviewed SHA／parent、P0–P3 findings、Decision／Adoption／Boundary／Evidence axes、commands／exit codes、remaining risks。狀態只可到 `REVIEW_GO` 或 `REVIEW_NO_GO`。

## Pre-dispatch receipt

```text
card_path: docs/tasks/2026-07-20_REVIEW-TSKG-OSS-ADR-01_reference_adoption.md
source_kind: commit
source_sha: dfade37ba0c030d764f1f3b7181cead17a6b3756
candidate_parent: ea5655efc5bf171f3584073ac04046699d0cc56e
architecture_source: 59917dd87dda448e77f5fc50ccfb3c1d05775aca
provisioning_branch: codex/tskg-oss-adr-review
source_worktree_clean: pending post-card commit
git_metadata_writable: pending preflight
index_lock: clear at card drafting
unrelated_dirty_paths: [] in review-base worktree
thread_id: pending
worktree_path: pending
turn_status: pending
gate_1_card_contract: drafted
gate_2_visible_thread: pending
gate_3_candidate_delivery: complete
gate_4_independent_review: pending
gate_5_mainline_acceptance: pending
```
