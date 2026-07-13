# CLEANUP-29 結果

## 結論

已新增 `scripts/build_regime_conditional_suite.py`，提供 `shadow_rankings` 與 `hybrid_report` 兩個 profile；兩支舊 builder 在 parity 與 consumer gate 通過後退休。

## 證據

- parity、consumer 與驗證摘要：`.work/CLEANUP-29/evidence/parity.json`
- frozen tests：`tests/test_regime_conditional_suite.py`

## 驗證

- focused tests：PASS，7 passed。
- reference／lifecycle strict-new：PASS。
- `py_compile`、`git diff --check`：PASS。
- daily 四檔 hash gate：PASS，與 CLEANUP-28 基線相同。
- full pytest（canonical）：PASS，226 passed、28 subtests passed；4 個既有套件 deprecation warnings。

## 限制與下一步

已完成主線整合；不需重建正式研究 artifact。下一步為封存任務並移除 task worktree。
