---
id: REVIEW-NEW-TOP10-HORIZON-SAFE-REGIME-FEASIBILITY-AUDIT-V1
chain_id: NEW-TOP10-RESEARCH-SPINE-V1
status: ready
type: code-review
priority: P1
role: reviewer
cycle: 16
thickness: standard
risk: medium
model: gpt-5.6-terra
reasoning: medium
model_reason: 三個新增唯讀檔案、無 production mutation；沿用單一 Reviewer thread，以 Terra medium 做完整獨立審查。
date: 2026-08-16
base_sha: c2d137854d4f6fe66dec243e34e193589fed1db3
candidate_sha: 1565bafa158f9f1e2f7405361942472bef753521
production_change_allowed: false
network_allowed: false
---

# Review Horizon-safe Regime Feasibility Audit V1

## 工作名稱

獨立審查 h10／h20 exact-regime feasibility audit。

## Root question

Candidate 是否在不修改 authority、不跑 replay、不放寬 gate 的前提下，正確且 fail-closed 地盤點現有 exact-regime episode 的 h10／h20 feasibility？

## Review scope

- Base：`c2d137854d4f6fe66dec243e34e193589fed1db3`。
- Candidate：`1565bafa158f9f1e2f7405361942472bef753521`。
- 只審查 candidate 相對 base 的三個新增檔案。
- 完整檢查 correctness、authority boundary、determinism、path／symlink、false-positive feasibility、test gap、production isolation。

## 必查事項

- `BLOCKED_AUTHORITY_CONFLICT` 是否真由 committed authority 缺失推導，而非錯誤綁定 worktree／main。
- Existing untracked `artifacts/market_regime_history.json`、`data/clean/features.parquet` 不得被誤當 committed truth。
- Canonical episode builder與 horizon helper 必須原樣重用；不得合併 episode或跨 episode window。
- Fixed scope 最大 episode 長度、safe dates與 shared dates不可在 conflict 狀態下被偽造。
- Evidence只可宣稱 feasibility／conflict；`lineage_authority_status` 必須維持 `UNPROVEN`。
- Absolute path、symlink、path escape、source drift與 hash identity 必須 fail closed。
- 不得修改 candidate；不得 merge、push、deploy、network、materialize或 replay。

## Verification

```bash
uv run pytest -q tests/test_shadow_replay_regime_feasibility.py tests/test_shadow_replay_coverage_plan.py
uv run python -m app.research.shadow_replay_regime_feasibility --verify docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-REGIME-FEASIBILITY-AUDIT-V1/feasibility_audit.json
uv run python -m py_compile app/research/shadow_replay_regime_feasibility.py tests/test_shadow_replay_regime_feasibility.py
jq empty docs/evidence/CARD-NEW-TOP10-HORIZON-SAFE-REGIME-FEASIBILITY-AUDIT-V1/feasibility_audit.json
git diff --check c2d137854d4f6fe66dec243e34e193589fed1db3 1565bafa158f9f1e2f7405361942472bef753521
```

## Verdict

- 有 P0／P1：`REVIEW_CHANGES_REQUIRED`，提供 finding ID、path:line、reproducer與修復驗收。
- 無 P0／P1：`REVIEW_APPROVED`，列出 residual risks。
