---
id: REVIEW-NEW-TOP10-HORIZON-SAFE-EVIDENCE-COVERAGE-PLAN-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: code-review
priority: P1
role: reviewer
cycle: 15
thickness: strict
risk: medium
model: gpt-5.5
reasoning: high
base_sha: c7b7d890995ae51aec83374f7168e5087c922fef
candidate_sha: e8755ba96ca662cf76383cfdb870ad1c9931acec
production_change_allowed: false
network_allowed: false
---

# Review Horizon-safe Evidence Coverage Plan V1

## 工作名稱

獨立審查 coverage plan candidate 的 NO-GO、authority 與 fail-closed 契約。

## Root question

Candidate `e8755ba96ca662cf76383cfdb870ad1c9931acec` 是否真能證明 `NO-GO_PLAN_UNAVAILABLE`，且沒有把 helper 語意、local artifacts 或自產 JSON 誤當成 lineage authority？

## 固定範圍

- Base：`c7b7d890995ae51aec83374f7168e5087c922fef`。
- Candidate：`e8755ba96ca662cf76383cfdb870ad1c9931acec`。
- 原卡：`docs/tasks/2026-08-15_CARD-NEW-TOP10-HORIZON-SAFE-EVIDENCE-COVERAGE-PLAN-V1-RETRY-1.md`。
- Review plan：主 repo `.work/REVIEW-NEW-TOP10-HORIZON-SAFE-EVIDENCE-COVERAGE-PLAN-V1/review/`，僅作唯讀輔助；結論仍須直接核對 candidate。
- Candidate 714 added lines，依 review-orchestrator 為 `full`。

## 必查

1. 分開 Spec axis／Standards axis。
2. Correctness：canonical helper 是否以正確資料與 horizon 10／20 使用；空集合是否真代表無合法 shared date。
3. Authority：Card E identity、source hash、committed input、symlink／path escape／collision、baseline→candidate dependency 是否 fail closed。
4. Evidence：輸出 JSON 是否可獨立驗證、byte deterministic，且未宣稱 materialization、lineage 或 non-sealed authority 已成立。
5. Regression／security：CLI、repo-relative path、absolute path leakage、command argv、讀檔邊界、production／queue／scheduler 零 mutation。
6. Test gap：不得只採信 candidate 自帶 6 tests；加入至少一個 adversarial fixture 或獨立重算，證明主要 NO-GO seam。
7. Maintainability：556 行新 module 是否存在重複 authority engine、不必要複雜度或無法重現的本機耦合。
8. 重跑原卡 verifier、targeted tests、`py_compile`、JSON validation、`git diff --check`。

## Verdict

- 有 P0／P1、錯誤 NO-GO、authority 漂移或 safety risk：`REVIEW_CHANGES_REQUIRED`。
- 無阻塞 finding：`REVIEW_APPROVED`，列出 P2／P3、剩餘風險與驗證缺口。
- Findings 必須含 `path:line`、觸發條件、證據、風險、建議修法、validation gap、confidence。

## 邊界

- 唯讀 review；不得修改 candidate、不得修碼、不得 merge／push／deploy。
- 不執行 materializer、strategy matrix、comparison、replay、network、production、queue 或 scheduler mutation。
- 不得另開 reviewer／repair thread。

## 交付

- 回 verdict、findings、驗證命令與結果、candidate SHA、worktree clean 狀態。
