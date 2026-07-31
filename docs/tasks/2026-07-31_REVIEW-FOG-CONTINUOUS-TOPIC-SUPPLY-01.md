---
id: REVIEW-FOG-CONTINUOUS-TOPIC-SUPPLY-01
status: REVIEW_NO_GO
type: review
ownership: reviewer
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: candidate 變更 1,264 行並觸及 scheduler selection、worker terminal semantics、deterministic supply 與 development/production 邊界，需獨立 full review
chain_id: FOG-CONTINUOUS-RESEARCH-AVAILABILITY
parent_card_id: FOG-CONTINUOUS-TOPIC-SUPPLY-01
base_sha: 8cff3d0acbe2cea94f198166cc3a9a581b21319a
candidate_sha: 1674e293daeb759888b950be59d8c30d6020e833
---

# REVIEW-FOG-CONTINUOUS-TOPIC-SUPPLY-01

## Role

你是本卡獨立 Reviewer，不是 Executor、Repairer或 mainline Integrator。

- 只審查 `base_sha..candidate_sha` 的行為、證據與測試。
- 禁止修改 source code、tests、runtime、candidate commit或 main。
- Findings first；Reviewer不能用 Executor自述代替獨立證據。
- 只輸出 `REVIEW_GO` 或 `REVIEW_NO_GO`，並提交 review evidence。

## Root question

Candidate是否真的解除「queue仍有 9 題但 scheduler無題可跑」的 routing deadlock，
並以 bounded、deterministic、development-only方式補題，同時保持
exact-regime、manager lifecycle、cooldown、sealed、promotion與 production
邊界？

## Review scope

- Base：`8cff3d0acbe2cea94f198166cc3a9a581b21319a`
- Candidate：`1674e293daeb759888b950be59d8c30d6020e833`
- Candidate branch：
  `codex/fog-continuous-topic-supply-candidate-20260731`
- Diff：7 files，1,213 additions，51 deletions。
- Risk tier：`full`。

## Must read

1. `AGENTS.md`
2. 本卡
3. `docs/tasks/2026-07-31_FOG-CONTINUOUS-TOPIC-SUPPLY-01.md`
4. `docs/evidence/FOG-CONTINUOUS-TOPIC-SUPPLY-01/verification.md`
5. `.work/FOG-CONTINUOUS-TOPIC-SUPPLY-01/review/review_plan.md`
6. `.work/FOG-CONTINUOUS-TOPIC-SUPPLY-01/review/review_plan.json`
7. `.work/FOG-CONTINUOUS-TOPIC-SUPPLY-01/review/finding_schema.json`

## Mandatory review axes

### Spec axis

- queue-first必須在 default與 explicit queue mode一致生效。
- stale／ineligible queue rows不得阻斷 active fallback。
- queue與fallback重疊時，同輪 topic只執行一次。
- 9個 queued actionable fixture不能再回報 `NO_EXECUTABLE_TOPIC`。
- 補題必須 stable ID、bounded、deterministic、四路去重。
- 真正無題時必須回報 `TOPIC_SUPPLY_EXHAUSTED`且 worker exit 0。

### Standards axis

- current exact-regime eligibility仍是執行 authority。
- manager lifecycle與cooldown不可被 queue或 supply繞過。
- 只讀 immutable development episodes；validation、embargo、sealed排除。
- 不寫 closed experiment registry、不 promotion、不改 production
  ranking/model/weights。
- CLI、worker環境變數與既有 non-execute/topic-index語意不可意外回歸。
- 題目補充不可造成無界 combinatorial scan、重複 I/O或不受控 artifact mutation。

## Required independent verification

- 先以 CodeGraph定位 changed symbols與 callers，再由 source diff確認。
- 逐檔審查 `base_sha..candidate_sha`，對照實作卡 requirements。
- 獨立重跑 routing、fallback、dedupe、9 queued fixture。
- 獨立重跑 stable supply、四路去重、true exhaustion、development boundary。
- 檢查 worker對 `TOPIC_SUPPLY_EXHAUSTED`的 terminal／exit語意。
- 檢查 full-suite唯一失敗是否確為獨立 worktree缺少未版控 artifacts；
  若無法獨立證明，不得當成無關失敗略過。
- 執行 `git diff --check`、changed-file audit與 `rg -n '\\[DBG-'`。

## Finding contract

Finding至少包含：

- `finding_id`
- `severity`: P0 / P1 / P2 / P3
- `category`
- `path:line`
- 觸發條件與可重現證據
- risk
- suggested fix
- validation gap
- confidence

P0／P1、production safety risk、可利用 security issue或重複 warning pattern
必須 `REVIEW_NO_GO`。P2／P3需明確判斷是否阻塞本卡 acceptance。

## Exact changed-file allowlist

- 本卡狀態欄位
- `.work/FOG-CONTINUOUS-TOPIC-SUPPLY-01/review/**`
- `docs/evidence/FOG-CONTINUOUS-TOPIC-SUPPLY-01/independent_review.md`

不得修改 candidate source、tests、原 verification evidence或任何 runtime artifact。

## Forbidden

- 修 code或tests
- merge／rebase／cherry-pick candidate
- push `main`
- deploy、live worker、LaunchAgent、circuit、promotion
- archive／cleanup Executor thread、branch或worktree

## Exit

提交單一 review commit並回報：

- reviewed base／candidate full SHA
- findings（或明確「未發現阻塞問題」）
- Spec axis verdict
- Standards axis verdict
- independent test evidence
- full-suite failure disposition
- remaining risks
- `REVIEW_GO` 或 `REVIEW_NO_GO`

若 `REVIEW_NO_GO`，必須提供可直接開 Repair卡的 finding IDs與 regression要求。
