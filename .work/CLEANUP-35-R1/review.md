---
id: CLEANUP-35-R1
status: go
type: strict-independent-re-review
candidate_commit: f9b4a71
repair_commit: ef0f7c3
reviewed_commit: ef0f7c3
verdict: GO
---

# CLEANUP-35-R1 Review

## Verdict

`GO`

原 `NO-GO` 的兩項 findings 已由 `ef0f7c3` 關閉。Reviewer 在原 R1 worktree 獨立重跑 committed parity harness、focused tests、strict audits、py_compile、daily hashes 與完整 pytest；repair 沒有修改 candidate runner、daily/publish、production ranking、model、weights 或 automation。

## Re-review Boundary

- chain_id：`CLEANUP-35`
- base candidate：`f9b4a71`
- original review evidence：`b7d7e4d`
- repair card commit：`e00919b`
- repair commit：`ef0f7c3`
- repair diff：`e00919b..ef0f7c3`
- 本輪只判定：`C35-R1-F1`、`C35-R1-F2`
- 禁止執行：真實 replay、shadow ranking、training、長跑 subprocess

## Finding Closure

### C35-R1-F1 — RESOLVED

- 原 severity：`P1`
- repair path：`scripts/verify_shadow_research_campaign_parity.py`
- evidence：committed harness 固定從 `9748b95` Git objects 載入四支 legacy entrypoint；四 stage × valid/missing/failure 共 12 組皆 PASS。
- comparison axes：normalized JSON、exact Markdown、normalized TSV、console JSON、exit code、executed/artifact command order 全部一致。
- reproducibility：獨立執行 `uv run python scripts/verify_shadow_research_campaign_parity.py` exit 0，重建 parity evidence 後 worktree 無 diff。
- sensitivity：`A1_SCHEMA_VERSION` mutation 被判為 parity `FAIL`，證明 harness 不是只驗 happy-path 或手寫 PASS。
- boundary：harness 只允許 `git show` 讀 frozen source；stage subprocess 全部由 in-process fake 攔截，真實 replay/ranking/training 次數為 0。
- closure：`RESOLVED`

### C35-R1-F2 — RESOLVED

- 原 severity：`P3`
- repair path：`.work/CLEANUP-35/result.md`
- evidence：新增 verifier 後，reference/lifecycle strict audit 都獨立回報 `430 tracked scripts` 且 PASS；result/status 已同步為 430。
- closure：`RESOLVED`

## Spec Axis

`PASS`

- 退役前 old/new parity 已具備 committed、可重跑、mutation-sensitive 的證據。
- CLI/default、command ordering、JSON/Markdown/TSV、console 與 exit semantics 的原 finding 已被 12 組比較關閉。
- candidate runner 本體未因 repair 改動。

## Standards Axis

`PASS`

- Harness 使用 argv list 呼叫固定 `git show`，沒有 shell invocation。
- Synthetic fixture 全部位於 temporary directory。
- Focused tests 會直接執行 parity harness 並驗證 mutation failure。
- Repair diff 僅包含兩項 findings 所需 verifier、tests 與 evidence/docs。

## Independent Verification

- parity harness：`PASS`
- focused pytest：`15 passed`
- reference strict-new：`430 tracked scripts`，PASS
- lifecycle strict-new：`430 tracked scripts`，PASS
- py_compile：PASS
- repair diff check：PASS
- daily 四檔 SHA-256：與原 card 基線一致
- full pytest：`267 passed, 1 failed, 28 subtests passed, 4 warnings`
- 真實 replay / shadow ranking / training：`0`

## Remaining Risk

完整 pytest 唯一 failure 仍是 `test_research_component_ledger` 缺 gitignored historical evidence；此缺口已在原 R1 記錄，且不在 `e00919b..ef0f7c3` repair diff。它不阻擋本輪兩項 findings closure，但主線不得把此 GO 擴張解讀成整個 repository 零失敗。

## Open Findings

無。`C35-R1-F1/F2` 均已關閉。

## Evidence

本輪命令與輸出摘要：`.work/CLEANUP-35-R1/evidence/re-review-ef0f7c3.md`。
