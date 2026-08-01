---
id: FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01-REVIEW-RETRY-1
status: QUEUED
type: review
ownership: reviewer
thickness: strict
risk: high
model: gpt-5.6-sol
reasoning: high
model_reason: candidate改動current／historical universe scope與fail-closed verifier，且原Reviewer建立無receipt，需以相同chain的正式replacement完成獨立高風險審查
chain_id: FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT
parent_card_id: FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01
supersedes_card_id: FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01-REVIEW
cycle: 1
base_sha: 6c5faff42569d6bb3b345b5253bcb00a62f9f37b
candidate_sha: 980fa4f77f23522d6671bd15d09b62bfedc16c5b
---

# FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01 Independent Review Retry 1

## Replacement boundary

這是原Reviewer派工因`REVIEW_THREAD_CREATE_NO_RECEIPT`而建立的唯一replacement。
沿用同一chain、role、cycle、base與candidate；不得擴張審查範圍，也不得把原派工視為已執行。

## Role and scope

你是獨立Reviewer，不是Executor、Repairer、Integrator或live operator。

- 固定審查`6c5faff42569d6bb3b345b5253bcb00a62f9f37b..980fa4f77f23522d6671bd15d09b62bfedc16c5b`。
- 先讀主卡、原Review卡、candidate diff與RED／GREEN evidence，再獨立執行必要驗證。
- 不得修改production code或測試；發現問題只寫finding與verdict。

## Review questions

1. Producer是否以current canonical expanded universe作`full_universe_total`，同時保留historical rollup實際source scope，而非偽造新增classification？
2. 合法stale-smaller partial是否滿足current total、classified subset、pending delta與category conservation，且map verifier可通過？
3. over-classified、negative／missing pending、category sum mismatch、missing／mismatched source scope是否仍fail closed？
4. same-scope full classification是否仍為100%，base／expanded／executed progress與HTML contract是否未退化？
5. candidate是否只改主卡allowlist，無topic supply、dimension、queue／retry、ranking／model／promotion／closed registry變更？
6. Executor所列兩個full-suite failure是否確為candidate外環境／時區問題，而非本卡regression？

## Fixed evidence

- 主卡：`docs/tasks/2026-08-01_FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01.md`
- 原Review卡：`docs/tasks/2026-08-01_FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01_review.md`
- 驗證：`docs/evidence/FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01/verification.md`
- Candidate：`980fa4f77f23522d6671bd15d09b62bfedc16c5b`
- Candidate changed files：7；production files僅`app/research/fog_map_domain.py`、`scripts/verify_research_fog_map.py`。

## Required verification

- `git diff --check 6c5faff42569d6bb3b345b5253bcb00a62f9f37b..980fa4f77f23522d6671bd15d09b62bfedc16c5b`
- 獨立讀完整diff與新測試，核對allowlist及fail-closed語意。
- `.venv/bin/python -m pytest -q tests/test_research_fog_map_burn_down.py tests/test_research_fog_map_refactor.py`
- `.venv/bin/python -m pytest`
- 必要時以temp fixture呼叫producer／verifier public seam；禁止寫live artifacts。
- `.venv/bin/python -m py_compile app/research/fog_map_domain.py scripts/verify_research_fog_map.py tests/test_research_fog_map_burn_down.py`
- DBG audit與review receipt `git diff --check`。

## Finding policy

- 只以P0／P1阻擋：資料不守恆、錯誤放行、current universe失真、candidate導致handoff failure、越界改動或無法重現核心GREEN。
- P2／P3記錄為non-blocking residual risk，不得產生`REVIEW_NO_GO`。
- 不得直接修finding；`REVIEW_NO_GO`交回主線建立唯一Repair card。

## Exact changed-file allowlist

- 本review retry卡狀態欄位
- `.work/FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01/review/**`

## Forbidden

- 修改candidate production code／tests或重寫Executor evidence。
- 清／旋轉circuit、LaunchAgent任何操作、人工live run／probe、deploy。
- merge、push main、建PR、cleanup thread／branch／worktree。

## Exit

產生`.work/FOG-MAP-BURN-DOWN-UNIVERSE-ALIGNMENT-01/review/review_receipt.md`，內容含fixed base／candidate／review commit、checks、findings、allowlist audit、remaining risks，以及唯一verdict：`REVIEW_GO`或`REVIEW_NO_GO`。

Reviewer只交review commit，不得宣稱已整合或runtime恢復。
