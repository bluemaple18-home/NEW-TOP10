---
card_id: REPAIR-TSKG-MFO-THEME-01-01
chain_id: TOP10-NEXT-WAVE-20260722
status: REPAIR_READY
type: repair
original_candidate: 04f1380d7390609bea854afd354f7f0859f1d3e0
review_no_go_commit: 69282b5
owner: repair executor
allowlist:
  - app/tskg/theme_membership.py
  - tests/test_tskg_theme_flow.py
  - scripts/verify_tskg_theme_flow.py
  - docs/evidence/REPAIR-TSKG-MFO-THEME-01-01/**
  - .work/REPAIR-TSKG-MFO-THEME-01-01/**
  - docs/tasks/2026-07-22_REPAIR-TSKG-MFO-THEME-01-01.md
---

# REPAIR-TSKG-MFO-THEME-01-01

只修原 Reviewer `69282b5` 的兩個 P1，不擴張功能：

1. 對同一 `(security_id, theme_id)` 的重疊 effective intervals 必須 fail closed 或先形成唯一 active membership；equal-split denominator 只能計 distinct active themes。補 overlap regression 與逐 security/全體 mass-conservation assertions。
2. content hash 必須對 membership semantic order canonical；重排輸入不改變 hash／輸出。保留 closed schema 與 duplicate detection，補 reversed/permuted input equivalence。

固定邊界：TWSE-only、TPEx blocked；只採 ALL_INSTITUTIONAL；不改 stale policy、不改 graph/ranking/API/UI，不存取 Yuanta secure attachment。

先用 Reviewer probes 重現 RED；完成後跑原 20 tests、新 regressions、verifier、py_compile、diff/allowlist/privacy。只提交 repair allowlist 與 evidence，交付 candidate 後回原 Reviewer task `019f8948-465d-73e1-8bca-c5d1f7493441` re-review。不得 self-review、merge或 push main。
