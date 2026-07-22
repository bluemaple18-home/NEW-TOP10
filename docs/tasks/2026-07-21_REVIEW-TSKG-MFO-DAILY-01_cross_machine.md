---
card_id: REVIEW-TSKG-MFO-DAILY-01
chain_id: TSKG-MFO-DAILY-01
title: Cross-machine independent review of daily T86 market-flow pipeline
status: ACCEPTED_MAINLINE
type: review
owner: Codex 主線
assignee: independent-cross-machine-review-thread
created_on: 2026-07-21
thickness: standard
risk: high
model: gpt-5.5
reasoning: high
model_reason: 跨 20 個檔案審查逐證券 T86 單位、快照契約、原子寫入、automation 單次抓取與既有 market-context 相容性；邊界已由兩張實作卡固定，不需重新做架構決策
source_kind: commit
source_sha: dfc30dc4a8466b914c642c1b38ea206dd388aa7c
candidate_parent: c84120be3ca0fb9efa6ed367ddac70e3b1a801b8
source_branch: codex/tskg-mfo-daily-01
review_branch: codex/top10new-review-tskg-mfo-daily-01-20260721-153932
worktree_mode: independent-cross-machine-worktree
evidence_path: docs/evidence/REVIEW-TSKG-MFO-DAILY-01/review.md
---

# REVIEW-TSKG-MFO-DAILY-01：跨機獨立審查

## Root question

Candidate `dfc30dc4a8466b914c642c1b38ea206dd388aa7c` 是否能在不改 Top10 ranking、不混淆股數與 TWD、不擴張來源治理授權的前提下，安全整合為 TSKG 每日 T86 唯讀資料管線？

## Fixed inputs

- Candidate：`dfc30dc4a8466b914c642c1b38ea206dd388aa7c`
- Parent：`c84120be3ca0fb9efa6ed367ddac70e3b1a801b8`
- Implementation branch：`codex/tskg-mfo-daily-01`
- Cross-machine entry：`.work/current/status.md`、`.work/current/handoff.md`、`.work/current/context_manifest.md`、`.work/current/result.md`
- Contracts：
  - `docs/tasks/2026-07-20_TSKG-MFO-RM-01_flow_read_model.md`
  - `docs/tasks/2026-07-20_TSKG-MFO-T86-01_daily_snapshot.md`
- Candidate evidence：
  - `docs/evidence/TSKG-MFO-RM-01/verification.md`
  - `docs/evidence/TSKG-MFO-T86-01/verification.md`

## Required review

### Correctness

1. `flow_read_model.py` 僅投影已驗證的 `SecurityFlowObservation`，ordering、lookup、summary 與 defensive-copy 行為 deterministic。
2. T86 snapshot 保留 19 欄逐證券資料；所有法人買賣數量明確為 `SHARE`，不得誤標成 TWD value。
3. 日期、closed schema、row uniqueness、checksum、provenance、freshness 與 malformed input 均 fail closed。
4. Fetch path 單次官方唯讀 GET、20 秒 timeout、無 retry loop；寫入採原子替換且不提交 ignored runtime artifact。
5. Daily automation 正常路徑最多抓取一次 T86，market-context consumer 重用同一 artifact，不形成雙重 fetch。

### Regression and boundaries

1. `app/market_context_fetcher.py` 與 `scripts/run_automation.py` 的既有呼叫相容；關閉 T86 功能時不改既有 daily 行為。
2. `config/automation.yaml` 不授權 production ranking、Theme aggregation、API／LLM redistribution 或 UI。
3. 不修改 `RankingPolicy`、`risk_adjusted_score`、模型權重、推薦結果或任何 Top10 feature。
4. TPEx、正式 rate／retention／redistribution governance、ThemeFlow、graph diffusion 維持 blocked。
5. `.work/current` 僅作跨機薄指標，共享路徑使用 repo-relative 或 `<repo-root>`，不得寫入本機絕對路徑。

## Mandatory verification

```bash
cd <repo-root>
git status --short
git show --stat --oneline dfc30dc4a8466b914c642c1b38ea206dd388aa7c
git diff --check c84120be3ca0fb9efa6ed367ddac70e3b1a801b8..dfc30dc4a8466b914c642c1b38ea206dd388aa7c
.venv/bin/python -m unittest \
  tests.test_tskg_flow_read_model \
  tests.test_tskg_twse_t86 \
  tests.test_tskg_t86_automation \
  tests.test_tskg_mfo01 \
  tests.test_tskg_slc01 \
  tests.test_tskg_src01
.venv/bin/python scripts/verify_market_context_fetcher.py
.venv/bin/python scripts/verify_daily_market_coverage_gate.py
.venv/bin/python scripts/verify_daily_pipeline_window_override.py
.venv/bin/python scripts/verify_resource_guard.py
```

真實單日 GET 已有 candidate evidence；本 Review 預設不重跑外部 endpoint。若另一台使用者明確授權，最多重跑一次卡片指定日期，並把 runtime artifact 保持 ignored。

## Allowlist

- `docs/tasks/2026-07-21_REVIEW-TSKG-MFO-DAILY-01_cross_machine.md`
- `docs/evidence/REVIEW-TSKG-MFO-DAILY-01/review.md`

## Forbidden scope

- Review 只判定，不修改 candidate code、config、fixture、tests、implementation evidence 或 `.work/current`。
- 不 merge、不 push `main`、不 deploy、不建立 scheduler／API／UI、不申請或擴張任何外部資料權限。
- `NO_GO` 時只列 P0–P2 finding、`path:line`、觸發條件、風險與 repair acceptance；不得在 Review 線直接修復。

## Verdict contract

- `REVIEW_GO`：Spec／Standards 均通過，無 P0–P2 finding，candidate 可交主線 acceptance。
- `REVIEW_NO_GO`：任何 correctness、單位、雙重 fetch、相容性、治理或證據阻塞 finding。

輸出必須包含 reviewed SHA／parent、GO／NO_GO、P0–P3 findings、Spec axis、Standards axis、commands／exit codes、changed-file allowlist、未重跑項目與剩餘風險。

## Pre-dispatch receipt

```text
card_path: docs/tasks/2026-07-21_REVIEW-TSKG-MFO-DAILY-01_cross_machine.md
source_kind: commit
source_sha: dfc30dc4a8466b914c642c1b38ea206dd388aa7c
candidate_parent: c84120be3ca0fb9efa6ed367ddac70e3b1a801b8
source_branch: codex/tskg-mfo-daily-01
review_branch: codex/top10new-review-tskg-mfo-daily-01-20260721-153932
source_worktree_clean: true at card drafting
unrelated_dirty_paths: []
thread_id: 019f839f-5faf-72a3-9ea3-5b847cfeb709
worktree_path: local-only isolated Codex worktree; remove after acceptance
turn_status: cross-machine review completed on 2026-07-22
gate_1_card_contract: complete
gate_2_visible_thread: receipt supplied by source machine; thread unavailable on reviewer host
gate_3_candidate_delivery: complete
gate_4_independent_review: REVIEW_GO
gate_5_mainline_acceptance: complete
```

## Review result

- Verdict：`REVIEW_GO`
- Reviewed SHA：`dfc30dc4a8466b914c642c1b38ea206dd388aa7c`
- Parent：`c84120be3ca0fb9efa6ed367ddac70e3b1a801b8`
- Blocking findings：無 P0–P2。
- Non-blocking finding：1 個 P3，詳見 `docs/evidence/REVIEW-TSKG-MFO-DAILY-01/review.md`。
- Mainline acceptance 已完成；candidate 能力以 `66b26f8` 適配當時較新的 daily orchestrator，並由 `02ab4a9` 合入主線。

## Mainline acceptance

- 正式 Review：`REVIEW_GO`，review commit `cc7355c`。
- Candidate implementation 沒有直接 merge；主線以 integration commit `66b26f8` 保留同一 T86／read-model 契約，並維持較新的 automation 架構。
- Review card/evidence 已以 commits `2bfbb4a`、`2ab556c` 帶入 `main`。
- Acceptance evidence：`docs/evidence/TSKG-MFO-DAILY-01/acceptance.md`。
- Cleanup：指定 implementation/review branches 與本次 isolated worktree 於 acceptance push 後移除；原 thread 在 reviewer host 不存在，記錄為無可封存實體。
