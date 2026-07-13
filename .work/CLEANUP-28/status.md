# CLEANUP-28 狀態

## Root Question
六支非 `candidate_decision` 的 odd-lot research verifier，能否收斂到同一支具名 profile suite，且不改變 verification payload、checks、summary、CLI exit code 與預設 output path？

## 目前狀態
ACCEPTED。`scripts/verify_odd_lot_research_suite.py` 已支援六個 profile，並保留各 profile 舊 CLI 的 default output path；canonical full pytest 為 `219 passed, 28 subtests passed`。

## Blocker
無。

## Fork
不為上述 worktree-only failure 修改 PM harness、component ledger、daily、model、ranking、builder 或 `candidate_decision` verifier。

## 下一步
封存 CLEANUP-28 任務並回收 worktree；主線繼續下一張清理卡。

## 等待條件
無。

## 限制
此 worktree 未 merge、未 push。
