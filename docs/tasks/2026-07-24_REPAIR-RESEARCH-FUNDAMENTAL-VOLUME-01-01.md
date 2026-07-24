---
card_id: REPAIR-RESEARCH-FUNDAMENTAL-VOLUME-01-01
chain_id: RESEARCH-FUNDAMENTAL-VOLUME-20260724
status: REPAIR_CANDIDATE_READY
type: bounded-repair
repair_generation: 1
repair_limit: 2
reviewed_candidate: 4deb72660dce9fc15f44d45e30307eb24f0caae1
review_no_go_sha: 9a90e5317c8c61745bd7273cdc865019399b9525
original_reviewer_thread: 019f9241-fe47-7ef0-accf-3e021a49c401
ownership: repair executor
thickness: strict
risk: research evidence integrity, independent verification, daily automation regression
model: gpt-5.6-sol
reasoning: high
model_reason: 修復一個 append-only integrity P1 與兩個 verifier completeness P2，需 adversarial fixtures 與原 Reviewer re-review。
worktree: codex/repair-research-fundamental-volume-01-01
evidence_path: docs/evidence/REPAIR-RESEARCH-FUNDAMENTAL-VOLUME-01-01/repair.md
---

# Repair Fundamental Readiness + Volume Climax Shadow

## Fixed findings

只修 `docs/evidence/REVIEW-RESEARCH-FUNDAMENTAL-VOLUME-01/review.md` 的三個 findings：

1. `F-01 / P1`：Volume daily runner 對既有 ledger 不變量未 fail closed。
2. `F-02 / P2`：Fundamental verifier 重用 builder，並非獨立重算。
3. `F-03 / P2`：Volume verifier 未完整覆蓋 frozen contract。

不得新增研究訊號、調整門檻、補外部資料或改 production ranking／model／weights／push。

## Allowlist

- `scripts/run_volume_climax_warning_append_only_shadow.py`
- `scripts/verify_volume_climax_warning_append_only_shadow.py`
- `scripts/verify_fundamental_point_in_time_readiness.py`
- `scripts/verify_overlay_shadow_daily_monitor.py`
- 直接受影響的 `tests/**`
- `docs/evidence/REPAIR-RESEARCH-FUNDAMENTAL-VOLUME-01-01/**`
- `.work/REPAIR-RESEARCH-FUNDAMENTAL-VOLUME-01-01/**`
- 本卡狀態

若必須修改 builder 或 config 才能修正共同邏輯，先在 evidence 說明原因；不得靜默擴 scope。

## Acceptance

### F-01

- runner 在寫入前驗證既有 observations 日期唯一、嚴格排序、全部晚於 seal。
- 驗證 frozen config／config SHA、每筆 source hash、warning-only、no-ranking-change、no-push 與 promotion fail-closed。
- corrupt ledger 的 duplicate、pre-seal、mutated warning semantics、missing source hash 全部非零失敗。
- component failure 使 combined receipt 為 `PARTIAL`，production daily 仍 allow-failure。

### F-02

- Fundamental verifier 不 import 或呼叫 `build_payload`。
- 以獨立資料讀取／聚合重算：
  - stock coverage。
  - point-in-time liquidity Top200。
  - D+10 maturity exclusion。
  - 最近 252 日 research gate。
  - 80% model gate。
- mutation fixture 能抓到 builder／artifact 與獨立 oracle 分歧。

### F-03

- 明確驗證 config SHA、source hashes、`production_ranking_changed=false`、`push_sent=false`、唯一 warning text。
- 59／60／61 observation boundary 仍保持 `promotion_ready=false`；本輪不得建立自動 promotion。
- 任一 contract 欄位缺漏或語意改寫皆非零。

## Required verification

```bash
<repo-root>/.venv/bin/python -m py_compile \
  scripts/run_volume_climax_warning_append_only_shadow.py \
  scripts/verify_volume_climax_warning_append_only_shadow.py \
  scripts/verify_fundamental_point_in_time_readiness.py \
  scripts/verify_overlay_shadow_daily_monitor.py
<repo-root>/.venv/bin/python scripts/verify_fundamental_point_in_time_readiness.py
<repo-root>/.venv/bin/python scripts/verify_volume_climax_warning_append_only_shadow.py
<repo-root>/.venv/bin/python scripts/run_overlay_shadow_daily_monitor.py
<repo-root>/.venv/bin/python scripts/verify_overlay_shadow_daily_monitor.py
<repo-root>/.venv/bin/python -m pytest -q \
  tests/test_overlay_shadow_daily_automation.py \
  tests/test_daily_automation_orchestrator.py
git diff --check
```

## Delivery

提交單一 Repair candidate，回報完整 SHA、parent、changed files、RED→GREEN、corrupt／mutation／boundary fixtures 與剩餘風險。不得自行 Review、merge、push main 或宣稱 accepted。完成後必須回原 Reviewer thread `019f9241-fe47-7ef0-accf-3e021a49c401` re-review。
