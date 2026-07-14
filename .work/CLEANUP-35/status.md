---
id: CLEANUP-35
status: done
type: strict-implementation
---

# CLEANUP-35 Status

## Root Question

能否在不執行真實 replay/training 的前提下，完整證明四支 shadow research 舊入口 parity，收斂為單一具名 stage runner 並安全退休舊入口？

## Blocker

None。完整 pytest 在乾淨 worktree 首次執行時，既有 research component ledger verifier 因 gitignored 歷史 research/data artifacts 不存在而單獨失敗；local-only 唯讀 evidence-root adapter 指向 canonical checkout 後，同一測試與完整 suite 均通過，未修改 repo ledger 契約、未複製或 symlink artifact。

## Fork

未分叉。沒有調整 replay、training、ranking、model、publish 或 production automation。

## Current Status

已新增 `scripts/run_shadow_research_campaign.py`，保留 `a1-forward`、`candidate-stress`、`overnight-training`、`risk-matrix-summary` 四個 stage。valid/missing/failure 舊新 normalized parity、全域 dry-run 零副作用、mocked failure semantics、strict audits、完整 pytest 與 daily hashes 均通過，四支舊入口已退休。

## Next Step

交回原主線做 commit-based review；不 merge、不 push。

## Waiting Condition

None。

## Limits

驗收期間 subprocess 全部 mocked；真實 replay、shadow ranking、training 與長跑 subprocess 執行次數為 0。未修改既有研究 artifacts、daily/publish、模型、權重、正式 ranking、launchd、plist 或 automation。
