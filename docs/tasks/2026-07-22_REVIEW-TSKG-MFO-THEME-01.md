---
card_id: REVIEW-TSKG-MFO-THEME-01
chain_id: TOP10-NEXT-WAVE-20260722
status: READY_FOR_REVIEW
type: independent-correctness-boundary-review
reviewed_sha: 04f1380d7390609bea854afd354f7f0859f1d3e0
owner: independent reviewer
allowlist:
  - docs/evidence/REVIEW-TSKG-MFO-THEME-01/**
  - .work/REVIEW-TSKG-MFO-THEME-01/**
  - docs/tasks/2026-07-22_REVIEW-TSKG-MFO-THEME-01.md
---

# REVIEW-TSKG-MFO-THEME-01

獨立 Review candidate `04f1380d7390609bea854afd354f7f0859f1d3e0`。只審不修。

## 必查

- membership closed schema、content hash、effective interval、evidence locator 與 stale/missing/duplicate fail-closed。
- `ALL_INSTITUTIONAL` selection 是否避免總法人與分類重複計算。
- `EQUAL_SPLIT_ACROSS_ACTIVE_THEMES` 在多重 membership 下是否守恆、無 silent double count。
- buy/sell/net、coverage、missing/stale/zero coverage 與 cross-date semantics。
- deterministic canonical output／hash，不受 input order 影響。
- TWSE-only、TPEx blocked；無 price/return/prediction/recommendation/ranking/graph mutation。
- 重跑 20 tests、verifier、py_compile、diff check、allowlist/privacy scan。

## 輸出

只新增本 Review evidence/status，提交單一 review commit，回報 `REVIEW_GO`／`REVIEW_NO_GO`、findings 與 reviewed SHA。不得 self-repair、merge、push main或存取 Yuanta secure attachment。
