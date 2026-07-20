---
card_id: TSKG-OSS-01
chain_id: TSKG-OSS
title: TSKG existing FinMind and T86 asset reuse audit
status: DELIVERED_CANDIDATE
type: research
owner: Codex 主線
assignee: visible-thread
created_on: 2026-07-20
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 需要跨 app、pipeline、tests、docs 與 Git 歷史判斷現有 FinMind／T86 路徑的真實狀態，但不做架構決策或程式修改
source_kind: commit
source_sha: da0d0b20bb1838ef8dc9dffcb926fca72562a419
source_branch: codex/tskg-mfo-src-01
worktree_mode: platform-managed-independent-worktree
main_cwd: <repo-root>
expected_worktree_cwd: platform-assigned-and-not-equal-to-main-cwd
deliverable_path: docs/research/TSKG-OSS-01_existing_asset_reuse_audit.md
evidence_path: docs/evidence/TSKG-OSS-01/verification.md
---

# TSKG-OSS-01：既有 FinMind／T86 資產沿用盤點

## Root question

TOP10 repo 目前已有哪些 FinMind、TWSE T86、三大法人資料元件；哪些只是歷史程式、哪些仍在呼叫鏈上、哪些可作為 TSKG 參考，哪些明確不可直接沿用？

本卡只做 repo-first 唯讀盤點與文件化，不開發、不修程式、不呼叫外部 API。

## Known facts

- `app/finmind_fetcher.py` 已含三大法人與融資融券取數介面。
- `app/finmind_integrator.py` 已含前 N 檔、法人分類、pivot 與 merge 邏輯。
- `app/pipeline/fetch_stage.py` 已有 FinMind integration 接點。
- `app/market_context_fetcher.py` 已有 TWSE `T86` response path。
- `docs/References.md` 與 2026-05 market-context 文件已記錄 FinMind／T86。
- 上述存在性不等於目前 production 有效、來源已核准或適合直接搬入 TSKG。

## Must produce

1. 既有資產清單：檔案、symbol、責任、輸入、輸出、呼叫者、測試、Git 首次／最近變更。
2. 資料流圖：FinMind 路徑與 direct T86 路徑分開標示。
3. 狀態分類：`ACTIVE | FALLBACK | SHADOW | DORMANT | BROKEN | UNKNOWN`，每項須有 repo 證據。
4. 沿用矩陣：`REUSE | REFERENCE_ONLY | DO_NOT_REUSE | NEEDS_VALIDATION`，說明對 TSKG `SecurityFlowObservation` 的對應與缺口。
5. 明確區分「已有程式」、「可執行」、「已測試」、「已核准 production source」。
6. 列出下一張 synthesis 卡需要回答、但本卡不得自行決定的問題。

## Allowlist

- `docs/tasks/2026-07-20_TSKG-OSS-01_existing_asset_reuse_audit.md`
- `docs/research/TSKG-OSS-01_existing_asset_reuse_audit.md`
- `docs/evidence/TSKG-OSS-01/verification.md`

## Forbidden scope

- 不修改 `app/**`、`scripts/**`、`tests/**`、`config/**`、requirements、runtime、API、UI 或 TSKG contract。
- 不執行會存取 FinMind、TWSE、TPEx 或其他外部服務的程式。
- 不補猜 production 狀態；找不到 caller、測試或 artifact 時標 `UNKNOWN`。
- 不批准來源、不宣稱 FinMind／T86 可直接進 TSKG。
- 不處理外部 GitHub／PyPI 專案；那是 `TSKG-OSS-02` 的責任。

## Verification

- Repo 搜尋範圍、Git log/blame 指令與結果可重現。
- 每個 ACTIVE/FALLBACK/BROKEN 判定至少有一個 caller、test、artifact 或明確缺口證據。
- changed files 完全符合 allowlist。
- host-specific path scan 與 `git diff --check` 通過。
- 候選交付包含完整 commit SHA；狀態只可到 `DELIVERED_CANDIDATE`。

## Stop conditions

- 需要啟動 runtime、外部 API 或修改 code 才能判斷時，記 `NEEDS_VALIDATION` 並停在本卡邊界。
- 發現新的獨立問題鏈，只列 candidate fork，不自行擴卡。
- 同一 blocker 失敗三次即停止。

## Pre-dispatch receipt

```text
card_path: docs/tasks/2026-07-20_TSKG-OSS-01_existing_asset_reuse_audit.md
provisioning_source_sha: da0d0b20bb1838ef8dc9dffcb926fca72562a419
provisioning_branch: codex/tskg-mfo-src-01
source_worktree_clean: true at candidate preflight
git_metadata_writable: true for candidate commit via platform-approved git write
index_lock: clear at card drafting and candidate preflight
unrelated_dirty_paths: []
thread_id: 019f7e58-df0f-7eb1-808d-369fa5c02206
worktree_path: <local-only-worktree verified in preflight>
turn_status: DELIVERED_CANDIDATE
gate_1_card_contract: drafted
gate_2_visible_thread: receipt confirmed
gate_3_candidate_delivery: candidate commit pending until final SHA recorded
gate_4_independent_review: pending
gate_5_mainline_acceptance: pending
```

## Candidate result

本卡完成 repo-first 唯讀盤點，未呼叫 FinMind、TWSE、TPEx 或其他外部金融資料服務，未修改 app、scripts、tests、config、requirements、runtime、API、UI 或 TSKG contract。

- Research deliverable：`docs/research/TSKG-OSS-01_existing_asset_reuse_audit.md`
- Verification evidence：`docs/evidence/TSKG-OSS-01/verification.md`
- 主要結論：現有 FinMind 個股籌碼路徑可作 `REFERENCE_ONLY`，但不得直接作 TSKG ingestion；TWSE `T86` market context parser 有 caller、synthetic verifier 與 artifact 消費端，可參考其 parser/status 形狀，但 target source governance 仍由 `TSKG-MFO-SRC-01` 保持 `KEEP_BLOCKED`。
- 後續 synthesis 卡仍需決定 source approval、單位換算、逐股欄位語意、raw retention、late correction 與 TSKG `SecurityFlowObservation` adapter 邊界。
