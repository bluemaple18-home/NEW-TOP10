---
id: CLEANUP-35-R1
status: no-go
type: strict-independent-review
candidate_commit: f9b4a71
verdict: NO-GO
---

# CLEANUP-35-R1 Status

## Root Question

`f9b4a71` 是否已完整、可重現地證明四支舊 shadow research 入口 parity，足以安全退休舊入口？

## Candidate Commit

`f9b4a71`

## Verdict

`NO-GO`

## Blocker

Candidate 沒有 committed old/new parity harness；現有 13 個 focused cases 只測新 runner，無法重建 `.work/CLEANUP-35/evidence/parity.json` 的 old/new hash 與全契約比較。

## Open Findings

- `C35-R1-F1`｜`P1`｜缺少可重跑的 old/new valid/missing/failure parity harness；阻塞。
- `C35-R1-F2`｜`P3`｜strict audit tracked script count 應為 429，不是 432；非阻塞。

## Fork

無新研究或 production fork。只允許處理上述 review findings。

## Current State

- candidate code 未修改。
- focused tests、global dry-run、strict audits、daily hashes 與 diff check 已重跑。
- 真實 replay、shadow ranking、training 執行次數為 0。

## Next Card Type

`FIX`

## Next Card Scope

- 僅處理 `C35-R1-F1` 與 `C35-R1-F2`。
- 恢復四支舊入口或提供 frozen legacy fixture，加入可重跑 old/new parity harness。
- 由 harness 產生 parity evidence；修正 audit count。
- 不得改 production ranking、model、weights、publish、automation、daily 四檔或被編排子工具的資料語意。

## Required Evidence

- old/new valid、missing、subprocess failure 的 normalized JSON、exact Markdown、normalized TSV、console JSON、exit code、完整 command order parity。
- 四 stage global dry-run 零 subprocess、零 stage artifact/steps-log mutation。
- focused tests、reference/lifecycle strict-new、完整 pytest、`git diff --check`。
- daily 四檔 SHA-256 維持 card 基線。

## Recommended Model

`gpt-5.6-sol high`；原因是 repair 仍牽涉跨四個 legacy CLI 的核心 acceptance contract。

## Next Step

建立隔離 repair card／worktree，完成 bounded repair 後送回本 Review 對話 re-review；不得由 Reviewer 自行修 candidate。

## Waiting Condition

等待新的 repair commit SHA 與可重跑 parity evidence；在此之前不得 merge 或 push candidate。

## Limits

- Reviewer 不修改 candidate。
- 不 merge、不 push、不 deploy。
- 不執行真實 replay、shadow ranking、training 或長跑 subprocess。
