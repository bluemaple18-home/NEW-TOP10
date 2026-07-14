---
id: CLEANUP-35-R1
status: no-go
type: strict-independent-review
candidate_commit: f9b4a71
verdict: NO-GO
---

# CLEANUP-35-R1 Review

## Verdict

`NO-GO`

Candidate 的 runner 實作經靜態比對後未發現明確 production 邊界破壞，focused tests、全域 dry-run、strict audits 與 daily hash 也通過；但四個舊入口已刪除，而核心 old/new parity acceptance 沒有可由 repository 重跑的 harness。這使最重要的退役前契約仍無法獨立驗證。

## Review Boundary

- base commit：`9748b95`
- candidate commit：`f9b4a71`
- diff：`9748b95..f9b4a71`
- do not touch：candidate code、tests、config、既有 candidate evidence
- 禁止執行：真實 replay、shadow ranking、training、長跑 subprocess

## Findings

### C35-R1-F1

- finding_id：`C35-R1-F1`
- severity：`P1`
- category：`testing / spec compliance`
- path:line：`tests/test_shadow_research_campaign.py:16`
- trigger：嘗試從 candidate commit 重建 `.work/CLEANUP-35/evidence/parity.json` 宣稱的 old/new normalized parity。
- evidence：focused test 只 import `run_shadow_research_campaign`；`pytest --collect-only` 收到 13 cases，但沒有載入 parent 四支舊入口，也沒有 `9748b95` source loader、parity generator 或 hash assertion。`rg` 只找到靜態 `.work/CLEANUP-35/evidence/parity.json` 宣告，找不到產生該證據的程式。
- risk：四支舊入口已刪除；若 CLI/default、完整 command plan、JSON/Markdown/TSV、console 或 exit semantics 有漂移，現有測試仍可能全綠。這直接違反 parent card 的退役前 acceptance，且失去可重跑的 rollback/parity 證明。
- required_fix：先恢復四支舊入口，或提供同等可重跑的 frozen legacy fixture；新增 committed parity harness，同時執行 old/new valid、missing、subprocess failure fixture，逐項比較 normalized payload、exact Markdown、normalized TSV、console JSON、exit code 與完整 command order，再由該 harness 產生 parity evidence。
- verification：在乾淨 worktree 執行單一 parity command，必須重建 `.work/CLEANUP-35/evidence/parity.json` 並逐 stage PASS；測試需在故意改動任一 CLI default／command argument／schema field 時可失敗。
- confidence：`high`

### C35-R1-F2

- finding_id：`C35-R1-F2`
- severity：`P3`
- category：`evidence accuracy`
- path:line：`.work/CLEANUP-35/result.md:23`
- trigger：在 candidate commit 執行 lifecycle/reference `--strict-new`。
- evidence：兩支 audit 都回報 `429 tracked scripts`，不是 result 記錄的 `432`；這符合四舊刪除、一新增加的淨減 3。
- risk：PASS verdict 不受影響，但 evidence summary 無法逐字對上實際命令輸出，增加後續 acceptance 誤判成本。
- required_fix：把兩處 tracked script count 修正為 `429`，並留下實際可重跑命令。
- verification：兩支 strict audit 的輸出與 result 記錄一致。
- confidence：`high`

## Spec Axis

- `FAIL`：parent card 明定 old/new valid/missing/failure parity 是刪除舊入口前的必要契約；candidate 只有不可重建的摘要 artifact。
- 其餘已核對：四個 stage、主要 CLI/default、command ordering、failure semantics、global dry-run、daily 四檔 do-not-touch 均未發現額外阻塞問題。

## Standards Axis

- subprocess 使用 argv list，未引入 shell injection。
- focused tests 使用 mocked subprocess／temporary root，未觸發真實 replay 或 training。
- lifecycle/reference strict-new 均 PASS。
- 主要缺口是 acceptance evidence 不可重跑，不是風格問題。

## Verification Summary

- focused pytest：`13 passed`
- global CLI dry-run：四個 stage 都 exit 0，manifest 均為 `SKIPPED`，command count 分別為 `4 / 60 / 23 / 0`
- reference audit：`429 tracked scripts`，`strict-new: PASS`
- lifecycle audit：`429 tracked scripts`，`strict-new: PASS`
- py_compile：PASS
- daily 四檔 SHA-256：與 card 基線完全一致
- candidate diff check：PASS
- full pytest：`265 passed, 1 failed, 28 subtests passed, 4 warnings`；唯一失敗是已揭露的 gitignored research ledger evidence 缺失，與 candidate diff 無直接關聯
- 真實 replay / shadow ranking / training 次數：`0`

## Testing Gaps

- 未能從 repository 重建 candidate 宣稱的 old/new parity hash。
- candidate 所述 local-only ledger adapter 沒有保留可重跑命令；review 只能重現未套 adapter 的既有單一失敗。

## Open Questions

無。阻塞條件與 bounded repair scope 已足夠明確。

## Evidence

完整命令與輸出摘要見 `.work/CLEANUP-35-R1/evidence/verification.md`。
