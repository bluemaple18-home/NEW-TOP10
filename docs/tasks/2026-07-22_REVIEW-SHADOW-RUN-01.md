---
task_id: REVIEW-SHADOW-RUN-01
status: REVIEW_GO
review_sha: 08caf5d
card_type: independent-review
reviewed_sha: 19a2d12
ownership: independent reviewer
allowlist:
  - docs/evidence/REVIEW-SHADOW-RUN-01/**
  - .work/REVIEW-SHADOW-RUN-01/**
  - docs/tasks/2026-07-22_REVIEW-SHADOW-RUN-01.md
risk: research/production boundary
---

# REVIEW-SHADOW-RUN-01

請對 candidate `19a2d12` 執行獨立 Review。不得修改 implementation；只可提交 Review 證據與狀態。

## 必查

- diff 範圍只含 SHADOW-RUN-01 implementation allowlist。
- correctness、artifact schema、path portability、deterministic synthetic test。
- `research_only=true`，且不抓資料、不訓練、不改或寫入 production ranking。
- `market_context` 明確 excluded。
- READY_FOR_SHADOW／BLOCKED_BY_GATE 保留來源 gate 判定。
- 使用專案既有相容 `.venv` 重跑 py_compile、兩支 verifier 與 `git diff --check`。

## 輸出

在 `docs/evidence/REVIEW-SHADOW-RUN-01/review.md` 記錄 reviewed SHA、命令、結果、findings 與 `REVIEW_GO` 或 `REVIEW_NO_GO`。若 NO_GO，列出可重現的必要修復，不得自行修 implementation。
