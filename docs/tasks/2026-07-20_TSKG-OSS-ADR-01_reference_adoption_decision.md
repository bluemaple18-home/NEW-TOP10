---
card_id: TSKG-OSS-ADR-01
chain_id: TSKG-OSS
title: Decide reference adoption and next TSKG implementation frontier
status: INTEGRATED
type: architecture-decision
owner: Codex 主線
assignee: independent-visible-thread
created_on: 2026-07-20
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: 需同時綜合既有 caller／test 證據、外部開源 License 與資料使用邊界、來源治理 blocker、資金觀測契約及 Top10／LLM 下游，並產出可約束後續實作的單一架構決策
source_kind: commit
source_sha: 59917dd87dda448e77f5fc50ccfb3c1d05775aca
source_branch: codex/tskg-mfo-src-01
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
deliverable_path: docs/adr/ADR-TSKG-OSS-01_reference_adoption.md
evidence_path: docs/evidence/TSKG-OSS-ADR-01/verification.md
---

# TSKG-OSS-ADR-01：參考資產採用與下一個實作 frontier

## Root question

完成既有 FinMind／T86 資產盤點與外部開源 scout 後，TSKG 應採用哪些內部模式、只參考哪些外部專案、拒絕哪些直接沿用方式；在 MOPS／TWSE source approval 仍 blocked 的前提下，下一張可以安全實作的卡是什麼？

本卡產生架構決策，不開發、不批准資料來源、不解除既有 source governance blocker。

## Fixed inputs

- `docs/specs/TSKG_v1.1.md`
- `docs/handoff/handoff_20260720_tide_tskg_concepts.md`
- `docs/tasks/2026-07-20_UI-MFR-00_market_flow_radar_backlog.md`
- `docs/research/TSKG-MFO-SRC-01_twse_institutional_flow_source.md`
- `docs/research/TSKG-OSS-01_existing_asset_reuse_audit.md`
- `docs/evidence/TSKG-OSS-01/verification.md`
- `docs/research/TSKG-OSS-02_external_open_source_reference_scout.md`
- `docs/evidence/TSKG-OSS-02/verification.md`
- `docs/evidence/REVIEW-TSKG-OSS-01-02/review.md`
- `docs/evidence/REVIEW-TSKG-OSS-ACCEPT-01/review.md`
- `docs/evidence/REVIEW-TSKG-OSS-ACCEPT-02/review.md`

Reviewed research inputs：

- OSS-01 candidate `f6a4f8fd263364d8dfe94f47f02e0e22cb6a8507`
- repaired OSS-02 candidate `a29e007baf431e98eab005082baddda258b2be7a`
- final acceptance repair candidate `7630b710d88262f691b0b8039b9b2a7d19492ba8`

## Decision options

ADR 必須比較並選定一個主方案：

1. `ADAPTER_FIRST_INTERNAL_PATTERNS`：沿用 repo 內已驗證的 contract、status、parser 與離線 verifier 形狀；外部 OSS 只作 reference，不把任何資料服務視為已核准 source。
2. `THIRD_PARTY_DATA_DEPENDENCY`：直接依賴 FinMind 或其他二次整理 API 作 TSKG ingestion。
3. `OSS_STACK_ADOPTION`：直接採用或大幅移植 TWSEMCPServer／其他 crawler stack。
4. `WAIT_FOR_SOURCE_APPROVAL`：在 source approval 前完全不做任何可執行的下一切片。

若選混合方案，必須指定唯一 primary option，其他僅能作附屬策略，不能模糊成「都可以」。

## Must produce

ADR 至少包含：

1. Context、Decision、Status、Consequences、Rejected alternatives。
2. 一張 adoption matrix，逐項判定：
   - repo 內 FinMind fetcher／integrator／FetchStage；
   - repo 內 direct T86 parser／status／offline verifier patterns；
   - `SecurityFlowObservation`／`ThemeFlowObservation`；
   - TWSEMCPServer；
   - FinMind external service／code patterns；
   - twstock；
   - twstocks-crawler、tsec、tsrtc、T86 issue discussion。
3. 每項使用 `REUSE_INTERNAL | REFERENCE_ONLY | DO_NOT_ADOPT | BLOCKED_PENDING_SOURCE_APPROVAL`，並說明 code license、data rights、endpoint authorization、production approval 的差異。
4. 明確保留：
   - 程式存在不等於 production active；
   - OSS License 不等於資料可再利用；
   - README／CLAUDE endpoint 描述不等於官方授權；
   - MOPS／TWSE ingestion、rate、retention、redistribution 仍未批准；
   - 資金觀測是公開資料 observation，不是策略、feature、score 或 prediction。
5. 畫出最小責任邊界：source adapter → raw snapshot／provenance → normalizer → observation contract → graph projection → Top10／LLM read model；指出哪一層目前可做、哪一層仍 blocked。
6. 決定唯一下一張 implementation card：卡號、root question、allowlist 類型、input/output contract、驗收與 stop conditions。不得直接建立該 implementation card。
7. 列出後續才處理的 fork：source approval、live connector、rate/retention、late correction、ThemeFlow aggregation、graph diffusion、UI radar；不得把它們混進下一張最小實作。
8. 提供可供 Top10／LLM 使用的最小 read-model 邊界，但不得定義選股策略、分數、權重、補漲模型或交易訊號。

## Expected decision pressure

- 優先消除重複 runtime、第二套 parser／graph／source client。
- 能借鏡不代表要安裝或依賴；能呼叫 endpoint 不代表已核准 ingestion。
- 下一切片應能用 synthetic／fixture／offline evidence 驗證，不得依賴 live 金融資料服務才能通過。
- 若現有 `SecurityFlowObservation` contract 已足夠，下一卡應補最小 adapter／projection 邊界，而不是重寫 contract；若不足，必須引用具體缺口。

## Allowlist

- `docs/tasks/2026-07-20_TSKG-OSS-ADR-01_reference_adoption_decision.md`
- `docs/adr/ADR-TSKG-OSS-01_reference_adoption.md`
- `docs/evidence/TSKG-OSS-ADR-01/verification.md`

## Forbidden scope

- 不修改任何 code、test、fixture、config、requirements、runtime、API、UI、TSKG spec、既有 contract 或 SourcePolicy。
- 不呼叫外部金融資料 endpoint，不連外補做新的廣泛研究，不 clone／install／run 外部 code。
- 不批准 MOPS、TWSE、FinMind 或任何 external ingestion。
- 不把 external code 複製、vendoring、加入 dependency 或建立第二套 runtime。
- 不制定交易策略、模型特徵、權重、分數或 prediction。

## Verification

- 所有 substantive claim 可回指 fixed inputs 的具體 section／repo symbol。
- adoption matrix 無互斥狀態衝突。
- ADR 只有一個 primary decision 與一個 next implementation card。
- source approval blocker 與可離線實作邊界明確分離。
- exact changed files 符合 allowlist。
- 共享文件 host-path gate 與 `git diff --check` 通過。
- 交付完整 candidate SHA；狀態只可到 `PROPOSED_CANDIDATE`。

## Stop conditions

- fixed inputs 對 contract／source status 有無法調和的衝突時，停止並列出 conflict，不自行猜測。
- 若決策需要 live endpoint、外部安裝、法務判定或新 source approval，停止在 blocked boundary。
- 同一 blocker 累計失敗三次即停止。

## Pre-dispatch receipt

```text
card_path: docs/tasks/2026-07-20_TSKG-OSS-ADR-01_reference_adoption_decision.md
source_kind: commit
source_sha: 59917dd87dda448e77f5fc50ccfb3c1d05775aca
provisioning_branch: codex/tskg-mfo-src-01
previous_acceptance_card_id: TSKG-OSS-ACCEPT-02
previous_reviewer_thread_id: 019f7e7a-241e-7412-86f6-9e69538c7e28
source_worktree_clean: true before ADR edits
git_metadata_writable: true by host-level preflight
index_lock: clear at ADR preflight
unrelated_dirty_paths: [] at ADR preflight
thread_id: <current-visible-thread>
worktree_path: <local-only-worktree verified in preflight>
turn_status: INTEGRATED
gate_1_card_contract: passed
gate_2_visible_thread: passed by current delegated task context
gate_3_candidate_delivery: final SHA bound by external final receipt
gate_4_independent_review: REVIEW_GO at 659ff161ffe0be7b8f9840f8f012716b833eab0b
gate_5_mainline_acceptance: accepted by docs/evidence/TSKG-OSS-ADR-01/acceptance.md
```
