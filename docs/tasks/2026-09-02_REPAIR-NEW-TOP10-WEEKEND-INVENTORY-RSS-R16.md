---
id: REPAIR-NEW-TOP10-WEEKEND-INVENTORY-RSS-R16
status: READY_FOR_EXTERNAL_REVALIDATION
type: runtime-repair
risk: high
baseline: a9bdcd7
---

# Weekend Inventory RSS Repair — R16

👉 [假設與目標確認] 目標：修復 R16 `build_weekend_universe_inventory.py` 的單程序 RSS 超限；邊界：不縮減 topic／scenario、不放寬 2 GiB ceiling、不啟用 launchd、不 push／deploy；驗收：建立可重跑記憶體 RED，最小修復後同一訊號 GREEN，語義回歸通過。

## Failure evidence

- R16 verdict：`NO-GO / PROCESS_TREE_RSS_BUDGET_EXCEEDED`。
- process-tree peak：`2,236,661,760 bytes`。
- 最大 contributor：`build_weekend_universe_inventory.py --write-bounded-frontier-queue`，單 PID RSS `2,202,353,664 bytes`。
- memory pressure 維持 `1`、swap 減少；guard 正確停止第一輪，未執行第二輪。

## Falsifiable hypotheses

1. 若主因是 `assign_equivalence` 為每筆 row 再保留 group list reference 並排序／建立 eligible list，改成兩段式 compact group summary 後，等價分類語義應不變，synthetic peak allocation 應明顯下降。
2. 若 row 本體才是唯一主因，單改 group summary 後 synthetic peak 不會越過預設門檻，需另開 bounded streaming repair；本卡不得直接縮 workload。

## Feedback loop

- RED command：`.venv/bin/python -m pytest -q tests/test_weekend_universe_inventory_snapshot.py::test_summary_only_bounded_cli_does_not_materialize_full_inventory`；舊路徑 peak allocation `45,875,440 bytes`，超過 `35,000,000` 門檻。
- GREEN command：同一命令修後 `1 passed`。

## Acceptance

- 等價代表選取、group size 與 burn-down 狀態完全保留。
- 記憶體回歸測試能抓住舊演算法的 allocation 尖峰。
- 受影響 tests、完整相關測試、`git diff --check` 與 debug marker scan 通過。
- 本機修復不宣稱 external capacity PASS；R17 需另取得明確授權。

## History

- 2026-09-02：R16 evidence 已保存；CodeGraph 指向 `assign_equivalence` 與 bounded frontier queue 為主要 public seam。
- 2026-09-02：假說 1 部分成立但不足以提供安全餘裕；group transient 約 `27 bytes/row`，僅移除該結構仍接近 2 GiB。採用更小的 existing seam：summary-only + bounded queue 改為兩段 streaming，第一段只保留 compact equivalence summary，第二段聚合 counts 並最多保留 144 筆代表。
- 2026-09-02：full-record／`--include-records` 路徑與既有 public API 保持不變；streaming 與 full-record 的 summary 語義比對通過。
- 2026-09-02：受影響回歸 `85 passed, 31 subtests passed`；retry circuit shell test PASS。尚未宣稱 external capacity PASS，等待 R17 明確授權。
