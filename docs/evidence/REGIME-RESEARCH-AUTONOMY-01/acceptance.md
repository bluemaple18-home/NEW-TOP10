# REGIME-RESEARCH-AUTONOMY-01 Mainline Acceptance

- Status：`GO`
- Acceptance date：`2026-07-27`
- Mainline base：`7efda43641118f36b10261b4a04e0278bba941a2`
- Final implementation candidate：`b1e3dc191527c24a5d3f5d80b975a81ad8a46543`
- Replacement Review verdict：`GO`
- Replacement Review evidence：`213bdd8c4d39d8df7e58ff349200efbc77222031`
- Mainline merge receipt：`e87450c`

## Acceptance evidence

- Targeted：`52 passed`
- Fixed-SHA verifier：`28/28 OK`
- Statistical-family canary：`PASS`
- Main-workspace full suite：`539 passed, 246 subtests passed`
- `git diff --check`：`PASS`
- Production model SHA-256：
  `ce64379701339bf7eadd696872efa0f64be118b4b8c58582e90691ec175c8a5d`
- Production baseline SHA-256：
  `c219b1b3c31c9b77f0a20cbeaeff87047bf88511f08dd642200f9d9370f832e7`

隔離 Reviewer worktree 曾出現一個
`ResearchComponentLedgerTest.test_verifier_accepts_generated_ledger` failure。
主工作區具備 ignored research artifacts 後完整測試全綠，證實該 failure 是
worktree provisioning debt，不是 candidate regression。

## Accepted boundary

- 已接受 closed-regime research governance、public statistical-family trust
  boundary、dataset／split／episode lineage 與 sealed date／slice lineage 的
  fail-closed 驗證。
- validation profiles 目前只覆蓋 `242/720`，不得宣稱完整參數搜尋。
- available-data run 目前只有 `2/14` independent units，研究結論仍是
  `INSUFFICIENT_EVIDENCE`。
- 本輪沒有修改 production ranking、權重或模型。
