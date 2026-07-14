---
id: CLEANUP-35-F1
status: ready-for-re-review
type: strict-bounded-repair
candidate_commit: f9b4a71
findings: [C35-R1-F1, C35-R1-F2]
---

# CLEANUP-35-F1 Status

## Root Question

是否已用可由乾淨 repository 重跑的 old/new parity harness 關閉 `C35-R1-F1/F2`，且沒有執行真實 replay/training 或擴大 candidate scope？

## Repair Commit

本文件所在的單一 atomic repair commit；最終 SHA 由 handoff 回報，避免 commit 內容自我引用不可能固定的 SHA。

## Findings Addressed

- `C35-R1-F1`：新增 `scripts/verify_shadow_research_campaign_parity.py`，從 `9748b95` Git objects 載入 frozen legacy source，執行四 stage 的 valid、missing、failure synthetic fixtures，比較 normalized JSON、exact Markdown、normalized TSV、console JSON、exit code 與 command order。
- `C35-R1-F1` mutation sensitivity：故意改動 `A1_SCHEMA_VERSION` 時，harness 觀察到 parity `FAIL`。
- `C35-R1-F2`：reference/lifecycle strict audit 對最終 tracked 集合均回報 `430 tracked scripts`；相較 R1 的 429，新增的 1 支正是本 repair 必要 verifier，文件已按實際輸出更新。

## Evidence Command

`uv run python scripts/verify_shadow_research_campaign_parity.py`

完整命令與結果：`.work/CLEANUP-35-F1/evidence/verification.md`。

## Remaining Risk

- 完整 pytest 仍有 R1 已揭露的既有 research ledger evidence 缺口：`267 passed, 1 failed, 28 subtests passed, 4 warnings`；唯一 failure 不在 repair diff。
- 最終 acceptance 必須由原 `CLEANUP-35-R1` reviewer 在 repair commit 上獨立重跑並裁決；本卡不宣稱 GO。

## Next Card Type

`RE_REVIEW`

## Re-review Owner

`CLEANUP-35-R1`

## Waiting Condition

等待原 reviewer 取得 repair commit SHA，在乾淨 worktree 重跑 parity、focused tests、strict audits 與必要回歸後更新 verdict。

## Limits

真實 replay、shadow ranking、training 與長跑 subprocess 執行次數為 `0`；未 merge、未 push、未 deploy。
