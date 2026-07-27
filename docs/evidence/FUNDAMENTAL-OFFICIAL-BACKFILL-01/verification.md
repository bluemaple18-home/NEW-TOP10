---
id: FUNDAMENTAL-OFFICIAL-BACKFILL-01
status: passed
type: verification
---

# FUNDAMENTAL-OFFICIAL-BACKFILL-01 Verification

## 已執行

```bash
<repo-root>/.venv/bin/python -m pytest -q tests/test_mops_xbrl_fundamentals.py
<repo-root>/.venv/bin/python scripts/import_mops_xbrl_fundamentals.py --start-period 2024Q4 --end-period 2026Q1
<repo-root>/.venv/bin/python scripts/build_fundamental_point_in_time_readiness.py
<repo-root>/.venv/bin/python scripts/verify_fundamental_point_in_time_readiness.py
<repo-root>/.venv/bin/python scripts/build_fundamental_shadow_scores.py --data-dir data/clean --output-prefix fundamental_shadow_mops_full_universe --horizon 10
```

## 證據

- parser／合併優先／日期／service metadata／as-of join：`5 passed`。
- 匯入：`1963/1967`，`99.80%`。
- readiness verifier：`FUNDAMENTAL_POINT_IN_TIME_READINESS_OK`。
- readiness decision：`READY_FOR_POINT_IN_TIME_RESEARCH`。
- shadow：IC `0.0148`、Top–Bottom spread `-0.000413`。
- 完整 `tests/`：`479 passed, 246 subtests passed`。

## 已知環境缺口

`scripts/verify_review_fixes.py` 在目前預設 `.venv` 的 import 階段因缺少非預設 `training` dependency group 中的 `optuna` 而停止。相同 blocker 累計三次後依停損規則未再重試；完整 `tests/` collection 不依賴該 group，已全數通過。
