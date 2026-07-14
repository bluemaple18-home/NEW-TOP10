---
id: CLEANUP-34
status: done
type: strict-implementation
---

# CLEANUP-34 Status

## Root Question

能否在完整證明三支 weekend readiness builder 的 valid/missing 輸出 parity 與 verifier consumer gates 後，收斂成單一具名 profile 入口並退休舊入口？

## Blocker

None。第一次 worktree full pytest 的唯一失敗是既有 ledger verifier 找不到 gitignored research/data artifacts；未 copy/symlink artifact，改以 local-only harness 借用 canonical checkout 的 evidence root 後，候選 worktree 完整測試通過。

## Fork

未分叉。沒有修改 research inventory/rollup/map 語意，也沒有觸碰 production runtime。

## Current Status

已新增 `scripts/build_weekend_readiness_audit.py`，保留 `campaign`、`ranking-dir-smoke`、`unsupported-unlock` 三個 profile。valid/missing parity、三支 verifier CLI consumer gates、strict audits、完整 pytest、daily hash 與 diff gates 均通過，三支舊 builder 已退休。

## Next Step

交回原主線做 commit-based review；不 merge、不 push。

## Waiting Condition

None。

## Limits

未執行 replay、baseline materialization、artifact copy/symlink；未修改每日報牌、publish、模型、權重、正式 ranking、launchd、plist、automation 或 production 狀態。
