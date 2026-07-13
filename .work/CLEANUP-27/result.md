---
id: CLEANUP-27
status: accepted
type: acceptance
---

# CLEANUP-27 Result

## Status
ACCEPTED；已整合為 `a525fda`。

## Evidence
- `evidence/parity.json`：四 profile valid/invalid、Markdown、四支 verifier 與 consumer gate PASS。
- focused：21 passed；suite + audit tests：31 passed、2 subtests passed。
- reference/lifecycle `--strict-new`、compile、diff check、scoped scan、daily hash gate：PASS。
- worktree full pytest：200 passed、28 subtests passed、1 個既有 `evidence_exists` environment-limit failure。
- canonical full pytest：201 passed、28 subtests passed。

## Scope
新增 `scripts/build_odd_lot_decision_suite.py`；退休四支舊 builder；同步 lifecycle；未碰 daily／模型／正式排名。

## Next step
封存任務並回收 worktree；六支 odd-lot verifier 的共用化另開任務。
