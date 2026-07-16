---
card_id: RESEARCH-AUDITOR-01R1
parent_card: RESEARCH-AUDITOR-01
title: Repair Research Auditor date contract and candidate evidence
status: DELIVERED_CANDIDATE
ownership: mainline
thickness: standard
risk: medium
model: gpt-5.5
reasoning: medium
model_reason: 修復既有稽核契約缺口，需定義日期輸入邊界並補 fixture，不改 production ranking。
source_kind: commit
source_sha: f0fe163c30d6cd4bb6edcde5a6e8e0a107e23734
main_cwd: <repo-root>
worktree_path: <repo-root>
thread_status: local-card-only
---

# RESEARCH-AUDITOR-01R1

## Scope

- 修正 Research Auditor 的日期一致性契約。
- 修正 parent card 的 candidate SHA evidence。
- 補日期一致、日期錯位、無法辨識日期的 tests。

## Allowlist

- `app/research_auditor.py`
- `tests/test_research_auditor.py`
- `docs/tasks/2026-07-17_RESEARCH-AUDITOR-01.md`
- 本卡與 review evidence。

## Forbidden scope

- 不修改 ranking、LightGBM、ETL source、模型權重或 production artifact。
- 不引入外部 API、Claude plugin、MCP 或新資料源。
- 不直接沿用 parent implementation thread；修復需從 candidate SHA 重新驗證。

## Acceptance / verification

1. 日期契約明確寫入 report schema。
2. ranking 與 features/fundamentals 日期一致時可通過。
3. 日期錯位時必須 fail loud，或在明確定義的非阻塞來源情況輸出 warning。
4. 日期不可辨識時不得靜默回報完整 GO。
5. `.venv/bin/python -m pytest -q tests/test_research_auditor.py`、`py_compile`、`git diff --check` 通過。
6. Candidate SHA 固定為 `f0fe163c30d6cd4bb6edcde5a6e8e0a107e23734`，修復後產生新 candidate，回 parent reviewer re-review。

## Progress

- 日期契約已加入：單日來源要求 exact match；歷史來源要求 max date 不得晚於 ranking date。
- 已補 exact/historical pass 與 future-date blocking fixtures。
- Candidate commit：`22fe86d`。
- Candidate scope：`app/research_auditor.py`、`tests/test_research_auditor.py`、兩張任務卡。
- 下一狀態：回 parent reviewer re-review。
